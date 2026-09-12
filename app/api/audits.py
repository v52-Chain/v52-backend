"""Canonical /v1/audits job endpoints."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.evidence.provenance import make_case_id, utcnow
from app.models.api import ApiEnvelope, ApiError, EnvelopeStatus, envelope
from app.models.claim import ClaimAuditRequest
from app.orchestration.audit_pipeline import AuditPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["audits"])

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


class AuditLimits(BaseModel):
    max_hops: int = Field(default=1, ge=0, le=5)
    max_events: int = Field(default=500, ge=1, le=5000)


class AuditSubmitRequest(ClaimAuditRequest):
    """Canonical request with explicit analysis limits."""

    limits: AuditLimits = Field(default_factory=AuditLimits)


@router.post(
    "/audits",
    response_model=ApiEnvelope,
    summary="Submit an audit job",
)
async def submit_audit(
    body: AuditSubmitRequest,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),
) -> ApiEnvelope:
    """Create a filesystem-backed audit job and start execution."""
    case_id = make_case_id(
        chain_id=body.chain_id,
        tx_hash=body.transaction_hash,
        subject=body.subject or ZERO_ADDRESS,
    )
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    _write_job(
        settings.data_dir,
        job_id,
        {
            "job_id": job_id,
            "case_id": case_id,
            "status": EnvelopeStatus.RUNNING,
            "created_at": utcnow().isoformat(),
            "updated_at": utcnow().isoformat(),
            "request": _safe_request_dump(body),
            "warnings": [],
            "errors": [],
            "result": None,
        },
    )
    background_tasks.add_task(_run_job, settings, job_id, case_id, body)
    return envelope(
        EnvelopeStatus.RUNNING,
        data={
            "case_id": case_id,
            "job_id": job_id,
            "limits": body.limits.model_dump(),
        },
    )


@router.get(
    "/audits/{job_id}",
    response_model=ApiEnvelope,
    summary="Read audit job status",
)
async def get_audit_job(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> ApiEnvelope:
    """Return the persisted audit job."""
    job = _read_job(settings.data_dir, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Audit job '{job_id}' not found.")
    status = EnvelopeStatus(job.get("status", EnvelopeStatus.UNKNOWN))
    errors = [ApiError(**item) for item in job.get("errors", [])]
    return envelope(
        status,
        data=job,
        warnings=job.get("warnings", []),
        errors=errors,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=ApiEnvelope,
    summary="Compatibility alias for audit job status",
)
async def get_job_alias(
    job_id: str,
    settings: Settings = Depends(get_settings),
) -> ApiEnvelope:
    return await get_audit_job(job_id, settings)


async def _run_job(
    settings: Settings,
    job_id: str,
    case_id: str,
    body: AuditSubmitRequest,
) -> None:
    try:
        request = ClaimAuditRequest(**body.model_dump(exclude={"limits"}))
        result = await AuditPipeline(settings).run(request, case_id=case_id)
        status = _envelope_status_from_case_status(result.status.value)
        _write_job(
            settings.data_dir,
            job_id,
            {
                "job_id": job_id,
                "case_id": result.case_id,
                "status": status,
                "created_at": _created_at(settings.data_dir, job_id),
                "updated_at": utcnow().isoformat(),
                "request": _safe_request_dump(body),
                "warnings": result.warnings,
                "errors": [],
                "result": result.model_dump(mode="json"),
            },
        )
    except Exception:
        logger.exception("Audit job failed: %s", job_id)
        _write_job(
            settings.data_dir,
            job_id,
            {
                "job_id": job_id,
                "case_id": case_id,
                "status": EnvelopeStatus.FAILED,
                "created_at": _created_at(settings.data_dir, job_id),
                "updated_at": utcnow().isoformat(),
                "request": _safe_request_dump(body),
                "warnings": [],
                "errors": [
                    {
                        "code": "DATASET_PARTIAL",
                        "message": "Audit job failed. See server logs; no secrets were exposed.",
                        "retryable": True,
                    }
                ],
                "result": None,
            },
        )


def _jobs_dir(data_dir: Path) -> Path:
    path = data_dir / "jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _job_path(data_dir: Path, job_id: str) -> Path:
    return _jobs_dir(data_dir) / f"{job_id}.json"


def _write_job(data_dir: Path, job_id: str, payload: dict) -> None:
    serializable = json.loads(json.dumps(payload, default=str))
    _job_path(data_dir, job_id).write_text(
        json.dumps(serializable, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _read_job(data_dir: Path, job_id: str) -> dict | None:
    path = _job_path(data_dir, job_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _created_at(data_dir: Path, job_id: str) -> str:
    job = _read_job(data_dir, job_id) or {}
    return str(job.get("created_at") or utcnow().isoformat())


def _safe_request_dump(body: AuditSubmitRequest) -> dict:
    return body.model_dump(mode="json")


def _envelope_status_from_case_status(status: str) -> EnvelopeStatus:
    if status == "COMPLETE":
        return EnvelopeStatus.COMPLETE
    if status in {"PARTIAL", "DEGRADED"}:
        return EnvelopeStatus.PARTIAL
    if status == "FAILED":
        return EnvelopeStatus.FAILED
    if status == "UNKNOWN":
        return EnvelopeStatus.UNKNOWN
    return EnvelopeStatus.RUNNING
