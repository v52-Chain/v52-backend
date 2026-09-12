"""
POST /v1/claim-audit — submit a claim for evidence-backed audit.

Contract owners: Saúl (Pydantic models) + Omar (frontend contract).
Any field change must be coordinated with both developers.

Validation:
  - chain_id must be 1 (Ethereum mainnet)
  - transaction_hash must be 0x + 64 hex chars
  - subject must be 0x + 40 hex chars
  - claim must be 1-1000 chars

Errors:
  - 422: validation failure (invalid tx hash, unsupported chain, etc.)
  - 400: semantic error (e.g., receipt not found after validation)
  - 500: unexpected internal error (never returns raw exception details)
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
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
from app.models.verdict import Verdict
from app.providers.ethereum_rpc import EthereumRpcProvider
from app.providers.the_graph import TheGraphProvider
from app.storage.case_repository import FileCaseRepository
from app.storage.evidence_vault import EvidenceVault

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["audit"])


def _make_acquisition(settings: Settings) -> EvidenceAcquisition:
    """Build the EvidenceAcquisition with configured providers (or None if unconfigured)."""
    vault = EvidenceVault(settings.data_dir)
    rpc = EthereumRpcProvider(settings.v52_rpc_url) if settings.rpc_configured else None
    graph = (
        TheGraphProvider(
            endpoint=settings.v52_graph_endpoint,
            api_key=settings.v52_graph_api_key,
        )
        if settings.graph_configured
        else None
    )
    return EvidenceAcquisition(vault=vault, rpc_provider=rpc, graph_provider=graph)


@router.post(
    "/claim-audit",
    response_model=ClaimAuditResponse,
    summary="Submit a claim for evidence-backed audit",
    response_description="Audit result with evidence records, verdict and provenance.",
)
async def claim_audit(
    body: ClaimAuditRequest,
    settings: Settings = Depends(get_settings),
) -> ClaimAuditResponse:
    """
    Run a full claim audit pipeline for the given Ethereum transaction.

    The endpoint:
    1. Validates the request (chain, tx hash, subject format).
    2. Acquires L0 (RPC) and L1 (The Graph) evidence.
    3. Preserves raw payloads in the Evidence Vault with SHA-256.
    4. Returns audit results with evidence records, status and provenance.

    Partial or failed provider responses produce DEGRADED status,
    never an invented COMPLETE result.
    """
    t_start = time.monotonic()

    case_id = make_case_id(
        chain_id=body.chain_id,
        tx_hash=body.transaction_hash,
        subject=body.subject,
    )
    logger.info(
        "Claim audit started: case_id=%s tx=%s subject=%s",
        case_id,
        body.transaction_hash,
        body.subject,
    )

    now = utcnow()
    case_record = CaseRecord(
        case_id=case_id,
        chain_id=body.chain_id,
        transaction_hash=body.transaction_hash,
        subject=body.subject,
        claim=body.claim,
        status=CaseStatus.RUNNING,
        created_at=now,
        updated_at=now,
    )

    # Persist initial case record.
    repo = FileCaseRepository(settings.data_dir)
    await repo.save(case_record)

    acquisition = _make_acquisition(settings)
    warnings: list[str] = []
    timing_ms: dict[str, int] = {}

    # ── L0: Ethereum RPC ──────────────────────────────────────────────────────
    t0 = time.monotonic()
    l0_record, _l0_raw = await acquisition.acquire_l0(
        case_id=case_id,
        tx_hash=body.transaction_hash,
    )
    timing_ms["rpc_ms"] = int((time.monotonic() - t0) * 1000)
    warnings.extend(l0_record.warnings)

    # ── L1: The Graph ─────────────────────────────────────────────────────────
    t1 = time.monotonic()
    l1_record, _l1_raw = await acquisition.acquire_l1(
        case_id=case_id,
        tx_hash=body.transaction_hash,
    )
    timing_ms["graph_ms"] = int((time.monotonic() - t1) * 1000)
    warnings.extend(l1_record.warnings)

    # ── Determine overall case status ─────────────────────────────────────────
    evidence_records = [l0_record, l1_record]
    statuses = {r.status for r in evidence_records}

    if EvidenceStatus.FAILED in statuses and EvidenceStatus.COMPLETE not in statuses:
        case_status = CaseStatus.FAILED
    elif EvidenceStatus.FAILED in statuses or EvidenceStatus.PARTIAL in statuses:
        case_status = CaseStatus.DEGRADED
    elif EvidenceStatus.WARNING in statuses:
        case_status = CaseStatus.DEGRADED
    else:
        case_status = CaseStatus.COMPLETE

    # ── Persist updated case ──────────────────────────────────────────────────
    case_record.status = case_status
    case_record.updated_at = utcnow()
    case_record.evidence_record_ids = [r.evidence_id for r in evidence_records]
    case_record.warnings = warnings
    case_record.timing_ms = timing_ms
    await repo.save(case_record)

    timing_ms["total_ms"] = int((time.monotonic() - t_start) * 1000)

    provenance = ProvenanceSummary(
        case_id=case_id,
        tx_hash=body.transaction_hash,
        chain_id=body.chain_id,
        evidence_record_ids=[r.evidence_id for r in evidence_records],
        vault_paths=[r.raw_path for r in evidence_records if r.raw_path],
        adapter_versions=list({r.adapter_version for r in evidence_records}),
    )

    logger.info(
        "Claim audit complete: case_id=%s status=%s total_ms=%d",
        case_id,
        case_status,
        timing_ms["total_ms"],
    )

    return ClaimAuditResponse(
        case_id=case_id,
        status=case_status,
        verdict=Verdict.UNKNOWN,  # Full verdict computation pending protocol + claims modules.
        summary=(
            "Evidence acquisition complete. "
            "Protocol analysis and verdict computation are pending"
            " integration with Jhamil's modules."
        )
        if case_status == CaseStatus.COMPLETE
        else f"Evidence acquisition {case_status.value.lower()}. See warnings for details.",
        evidence_for=[r for r in evidence_records if r.status == EvidenceStatus.COMPLETE],
        evidence_against=[],
        gaps=[
            "Protocol decoding (Uniswap V3 resolver) pending.",
            "Contribution Analysis pending.",
            "Claim predicate evaluation pending.",
        ],
        warnings=warnings,
        provenance=provenance,
        timing_ms=timing_ms,
    )
