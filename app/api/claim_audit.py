"""Legacy POST /v1/claim-audit endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.models.claim import ClaimAuditRequest, ClaimAuditResponse
from app.orchestration.audit_pipeline import AuditPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["audit"])


@router.post(
    "/claim-audit",
    response_model=ClaimAuditResponse,
    summary="Submit a claim for evidence-backed audit",
)
async def claim_audit(
    body: ClaimAuditRequest,
    settings: Settings = Depends(get_settings),
) -> ClaimAuditResponse:
    """Run a claim audit through the canonical pipeline."""
    logger.info(
        "Claim audit started: chain_id=%s tx=%s subject=%s",
        body.chain_id,
        body.transaction_hash,
        body.subject,
    )
    return await AuditPipeline(settings).run(body)
