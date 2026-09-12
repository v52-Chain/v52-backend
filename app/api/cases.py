"""
GET /v1/cases/{case_id}          — retrieve a case record.
GET /v1/cases/{case_id}/evidence — retrieve evidence records for a case.
GET /v1/cases/{case_id}/package  — download the .v52.zip package.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.config import Settings, get_settings
from app.models.claim import CaseRecord
from app.models.evidence import EvidenceRecord
from app.storage.case_repository import FileCaseRepository
from app.storage.evidence_vault import EvidenceVault

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["cases"])


@router.get(
    "/cases/{case_id}",
    response_model=CaseRecord,
    summary="Retrieve a case record",
)
async def get_case(
    case_id: str,
    settings: Settings = Depends(get_settings),
) -> CaseRecord:
    """Return the stored CaseRecord for the given case_id."""
    repo = FileCaseRepository(settings.data_dir)
    record = await repo.get(case_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    return record


@router.get(
    "/cases/{case_id}/evidence",
    response_model=list[EvidenceRecord],
    summary="List evidence records for a case",
)
async def get_case_evidence(
    case_id: str,
    settings: Settings = Depends(get_settings),
) -> list[EvidenceRecord]:
    """
    Return all EvidenceRecord objects associated with a case.
    Records are read from the vault's case directory.
    """
    repo = FileCaseRepository(settings.data_dir)
    case = await repo.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")

    vault = EvidenceVault(settings.data_dir)
    raw_files = vault.list_case_files(case_id)

    # Evidence records are stored as .json files prefixed with "ev_".
    # For P0, we reconstruct EvidenceRecord from the case's evidence_record_ids
    # by loading companion record files if they exist, or returning metadata only.
    records: list[EvidenceRecord] = []
    records_dir = settings.data_dir / "records" / case_id
    if records_dir.exists():
        for f in sorted(records_dir.glob("ev_*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                records.append(EvidenceRecord(**data))
            except Exception as exc:
                logger.warning("Failed to load evidence record %s: %s", f, exc)

    if not records:
        # Fallback: return a summary based on vault files available.
        logger.info(
            "No serialized EvidenceRecords found for case %s; vault has %d raw files.",
            case_id,
            len(raw_files),
        )

    return records


@router.get(
    "/cases/{case_id}/package",
    summary="Download the .v52.zip package for a case",
)
async def get_case_package(
    case_id: str,
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    """
    Return the pre-built .v52.zip package for a case.
    The package is built by POST /v1/claim-audit when the pipeline completes.
    """
    package_path: Path = settings.data_dir / "packages" / f"{case_id}.v52.zip"
    if not package_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Package for case '{case_id}' has not been built yet. "
                "Run a full audit to generate the package."
            ),
        )
    return FileResponse(
        path=str(package_path),
        media_type="application/zip",
        filename=f"{case_id}.v52.zip",
    )
