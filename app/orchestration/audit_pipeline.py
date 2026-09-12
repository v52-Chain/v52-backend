"""Full evidence-to-verdict audit pipeline."""

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
from app.evidence.reconciliation import reconcile_graph_swaps_with_rpc
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
from app.providers.factory import get_rpc_provider_for_chain
from app.providers.the_graph import TheGraphProvider
from app.storage.case_repository import FileCaseRepository
from app.storage.evidence_vault import EvidenceVault

logger = logging.getLogger(__name__)


class AuditPipeline:
    """Run the Vector52 audit stages for one request."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.vault = EvidenceVault(settings.data_dir)
        self.repo = FileCaseRepository(settings.data_dir)
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

        acquisition = self._make_acquisition(request.chain_id)

        t0 = time.monotonic()
        l0_record, l0_raw = await acquisition.acquire_l0(case_id, request.transaction_hash)
        timing_ms["rpc_ms"] = int((time.monotonic() - t0) * 1000)
        warnings.extend(l0_record.warnings)

        t1 = time.monotonic()
        l1_record, l1_raw = await acquisition.acquire_l1(case_id, request.transaction_hash)
        timing_ms["graph_ms"] = int((time.monotonic() - t1) * 1000)
        warnings.extend(l1_record.warnings)

        evidence_records = [l0_record, l1_record]

        t_reconcile = time.monotonic()
        reconciliation = reconcile_graph_swaps_with_rpc(
            l1_raw,
            l0_raw,
            evidence_ids=[record.evidence_id for record in evidence_records],
        )
        timing_ms["reconciliation_ms"] = int((time.monotonic() - t_reconcile) * 1000)
        for item in reconciliation:
            warnings.extend(item.warnings)

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

        t3 = time.monotonic()
        contribution = self.contribution_analysis.analyze(protocol_action, request.subject)
        timing_ms["contribution_ms"] = int((time.monotonic() - t3) * 1000)
        warnings.extend(contribution.warnings)

        t4 = time.monotonic()
        predicates = compile_claim(request)
        predicates = evaluate_predicates(predicates, protocol_action, contribution)
        timing_ms["claims_ms"] = int((time.monotonic() - t4) * 1000)

        evidence_for = [
            record for record in evidence_records if record.status == EvidenceStatus.COMPLETE
        ]
        evidence_against: list = []
        verdict, summary, gaps = audit(
            predicates=predicates,
            evidence_for=evidence_for,
            evidence_against=evidence_against,
            protocol_action=protocol_action,
            contribution=contribution,
        )

        case_status = _case_status_from_evidence({record.status for record in evidence_records})

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

        timing_ms["total_ms"] = int((time.monotonic() - t_total) * 1000)

        case_record.status = case_status
        case_record.verdict = verdict
        case_record.evidence_record_ids = [record.evidence_id for record in evidence_records]
        case_record.updated_at = utcnow()
        case_record.warnings = warnings
        case_record.timing_ms = timing_ms
        await self.repo.save(case_record)

        provenance = ProvenanceSummary(
            case_id=case_id,
            tx_hash=request.transaction_hash,
            chain_id=request.chain_id,
            evidence_record_ids=[record.evidence_id for record in evidence_records],
            vault_paths=[record.raw_path for record in evidence_records if record.raw_path],
            adapter_versions=list({record.adapter_version for record in evidence_records}),
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
            reconciliation=reconciliation,
            provenance=provenance,
            timing_ms=timing_ms,
        )

    def _make_acquisition(self, chain_id: int) -> EvidenceAcquisition:
        rpc = get_rpc_provider_for_chain(self.settings, chain_id)
        graph = (
            TheGraphProvider(
                endpoint=self.settings.v52_graph_endpoint,
                api_key=self.settings.v52_graph_api_key,
                timeout_seconds=self.settings.rpc_timeout_seconds,
            )
            if chain_id == 1 and self.settings.graph_configured
            else None
        )
        return EvidenceAcquisition(
            vault=self.vault,
            rpc_provider=rpc,
            graph_provider=graph,
            chain_id=chain_id,
        )


def _case_status_from_evidence(statuses: set[EvidenceStatus]) -> CaseStatus:
    if EvidenceStatus.FAILED in statuses and EvidenceStatus.COMPLETE not in statuses:
        return CaseStatus.FAILED
    if EvidenceStatus.FAILED in statuses or EvidenceStatus.PARTIAL in statuses:
        return CaseStatus.PARTIAL
    if EvidenceStatus.WARNING in statuses:
        return CaseStatus.PARTIAL
    if EvidenceStatus.UNKNOWN in statuses:
        return CaseStatus.UNKNOWN
    return CaseStatus.COMPLETE
