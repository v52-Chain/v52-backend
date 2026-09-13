"""
Audit Pipeline — orchestrates the full evidence → verdict → package flow.

OWNER: Omar (pipeline structure); Saúl, Jhamil review.

The pipeline runs these stages in order:
  1. L0 acquisition (RPC)
  2. L1 acquisition (The Graph)
  3. Protocol decoding (Uniswap V3)
  4. Contribution Analysis
  5. Claim compilation + predicate evaluation
  6. Verdict
  7. Packaging (.v52.zip)

Each stage records timing and propagates partial/failed status without hiding it.
"""

from __future__ import annotations

import logging
import time

from app.claims.auditor import audit
from app.claims.compiler import compile_claim
from app.claims.predicates import evaluate_predicates
from app.config import Settings
from app.contribution.direct_flow import DirectFlowAnalysis
from app.evidence.acquisition import EvidenceAcquisition
from app.evidence.provenance import make_case_id, utcnow
from app.models.claim import (
    CaseRecord,
    CaseStatus,
    ClaimAuditRequest,
    ClaimAuditResponse,
    ProvenanceSummary,
)
from app.models.evidence import EvidenceStatus
from app.packaging.packager import build_v52_zip
from app.protocols.uniswap_v3 import UniswapV3Resolver
from app.providers.ethereum_rpc import EthereumRpcProvider
from app.providers.the_graph import TheGraphProvider
from app.storage.case_repository import FileCaseRepository
from app.storage.evidence_vault import EvidenceVault

logger = logging.getLogger(__name__)


class AuditPipeline:
    """
    Full audit pipeline.

    Instantiated per-request.  All state is local to a single audit run.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.vault = EvidenceVault(settings.data_dir)
        self.repo = FileCaseRepository(settings.data_dir)

        rpc = EthereumRpcProvider(settings.alchemy_eth_rpc_url) if settings.rpc_configured else None
        graph = (
            TheGraphProvider(
                endpoint=settings.v52_graph_endpoint,
                api_key=settings.v52_graph_api_key,
            )
            if settings.graph_configured
            else None
        )
        self.acquisition = EvidenceAcquisition(
            vault=self.vault,
            rpc_provider=rpc,
            graph_provider=graph,
        )
        self.resolver = UniswapV3Resolver()
        self.contribution_analysis = DirectFlowAnalysis()

    async def run(
        self,
        request: ClaimAuditRequest,
        *,
        case_id: str | None = None,
    ) -> ClaimAuditResponse:
        """Execute the full audit pipeline for the given request."""
        t_total = time.monotonic()
        timing_ms: dict[str, int] = {}
        warnings: list[str] = []

        case_id = case_id or make_case_id(
            chain_id=request.chain_id,
            tx_hash=request.transaction_hash,
            subject=request.subject,
        )
        now = utcnow()
        case_record = CaseRecord(
            case_id=case_id,
            chain_id=request.chain_id,
            transaction_hash=request.transaction_hash,
            subject=request.subject,
            claim=request.claim,
            status=CaseStatus.RUNNING,
            created_at=now,
            updated_at=now,
        )
        await self.repo.save(case_record)

        # ── Stage 1: L0 RPC ───────────────────────────────────────────────────
        t0 = time.monotonic()
        l0_record, l0_raw = await self.acquisition.acquire_l0(case_id, request.transaction_hash)
        timing_ms["rpc_ms"] = int((time.monotonic() - t0) * 1000)
        warnings.extend(l0_record.warnings)

        # ── Stage 2: L1 The Graph ─────────────────────────────────────────────
        t1 = time.monotonic()
        l1_record, l1_raw = await self.acquisition.acquire_l1(case_id, request.transaction_hash)
        timing_ms["graph_ms"] = int((time.monotonic() - t1) * 1000)
        warnings.extend(l1_record.warnings)

        evidence_records = [l0_record, l1_record]

        # ── Stage 3: Protocol decoding ────────────────────────────────────────
        t2 = time.monotonic()
        protocol_action = self.resolver.resolve(
            l0_record=l0_record,
            l0_raw=l0_raw,
            l1_record=l1_record,
            l1_raw=l1_raw,
            subject=request.subject,
        )
        timing_ms["protocol_ms"] = int((time.monotonic() - t2) * 1000)
        warnings.extend(protocol_action.warnings)

        # ── Stage 4: Contribution Analysis ───────────────────────────────────
        t3 = time.monotonic()
        contribution = self.contribution_analysis.analyze(protocol_action, request.subject)
        timing_ms["contribution_ms"] = int((time.monotonic() - t3) * 1000)
        warnings.extend(contribution.warnings)

        # ── Stage 5: Claim compilation + evaluation ───────────────────────────
        t4 = time.monotonic()
        predicates = compile_claim(request)
        predicates = evaluate_predicates(predicates, protocol_action, contribution)
        timing_ms["claims_ms"] = int((time.monotonic() - t4) * 1000)

        # ── Stage 6: Verdict ──────────────────────────────────────────────────
        evidence_for = [r for r in evidence_records if r.status == EvidenceStatus.COMPLETE]
        evidence_against: list = []
        verdict, summary, gaps = audit(
            predicates=predicates,
            evidence_for=evidence_for,
            evidence_against=evidence_against,
            protocol_action=protocol_action,
            contribution=contribution,
        )

        # ── Determine case status ─────────────────────────────────────────────
        statuses = {r.status for r in evidence_records}
        if EvidenceStatus.FAILED in statuses and EvidenceStatus.COMPLETE not in statuses:
            case_status = CaseStatus.FAILED
        elif EvidenceStatus.FAILED in statuses or EvidenceStatus.PARTIAL in statuses:
            case_status = CaseStatus.DEGRADED
        elif EvidenceStatus.WARNING in statuses:
            case_status = CaseStatus.DEGRADED
        else:
            case_status = CaseStatus.COMPLETE

        # ── Stage 7: Packaging ────────────────────────────────────────────────
        t5 = time.monotonic()
        try:
            packages_dir = self.settings.data_dir / "packages"
            build_v52_zip(
                case_id=case_id,
                chain_id=request.chain_id,
                tx_hash=request.transaction_hash,
                subject=request.subject,
                claim=request.claim,
                status=case_status.value,
                verdict=verdict.value if verdict else None,
                warnings=warnings,
                vault_dir=self.settings.data_dir,
                output_dir=packages_dir,
            )
        except Exception as exc:
            warnings.append(f"Package build failed: {exc}")
            logger.warning("Package build failed for case %s: %s", case_id, exc)
        timing_ms["packaging_ms"] = int((time.monotonic() - t5) * 1000)

        # ── Persist final case ────────────────────────────────────────────────
        case_record.status = case_status
        case_record.verdict = verdict
        case_record.evidence_record_ids = [r.evidence_id for r in evidence_records]
        case_record.updated_at = utcnow()
        case_record.warnings = warnings
        case_record.timing_ms = timing_ms
        await self.repo.save(case_record)

        timing_ms["total_ms"] = int((time.monotonic() - t_total) * 1000)

        provenance = ProvenanceSummary(
            case_id=case_id,
            tx_hash=request.transaction_hash,
            chain_id=request.chain_id,
            evidence_record_ids=[r.evidence_id for r in evidence_records],
            vault_paths=[r.raw_path for r in evidence_records if r.raw_path],
            adapter_versions=list({r.adapter_version for r in evidence_records}),
        )

        return ClaimAuditResponse(
            case_id=case_id,
            status=case_status,
            verdict=verdict,
            summary=summary,
            predicates=predicates,
            evidence_for=evidence_for,
            evidence_against=evidence_against,
            gaps=gaps,
            warnings=warnings,
            protocol_action=protocol_action,
            contribution=contribution,
            provenance=provenance,
            timing_ms=timing_ms,
        )
