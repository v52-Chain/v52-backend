"""
POST /v1/verify — verify the integrity of an uploaded .v52.zip package.

The verifier recomputes SHA-256 hashes for all declared files and fails if:
  - A declared file is missing.
  - A declared file's hash does not match the manifest.
  - There are undeclared files in the ZIP (tamper detection).

It does NOT assert cryptographic signatures or trusted roots (out of scope for P0).
"""

from __future__ import annotations

import io
import json
import logging
import zipfile

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from app.evidence.preservation import sha256_of

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["verify"])

_MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB


class VerifyError(BaseModel):
    file: str
    reason: str


class VerifyResponse(BaseModel):
    status: str  # "PASS" or "FAIL"
    checked_files: int
    errors: list[VerifyError]


@router.post(
    "/verify",
    response_model=VerifyResponse,
    summary="Verify integrity of a .v52.zip package",
)
async def verify_package(file: UploadFile) -> VerifyResponse:
    """
    Upload a .v52.zip file and verify that all declared files match their SHA-256 hashes.

    Returns:
      - status: "PASS" if all checks succeed, "FAIL" otherwise.
      - checked_files: number of files verified.
      - errors: list of integrity violations.
    """
    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Package exceeds maximum size of {_MAX_UPLOAD_BYTES // 1024 // 1024} MB.",
        )

    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=400, detail="Uploaded file is not a valid ZIP archive."
        ) from None

    zip_names = set(zf.namelist())
    errors: list[VerifyError] = []

    # Load manifest.
    if "manifest.json" not in zip_names:
        raise HTTPException(
            status_code=400,
            detail="Package is missing manifest.json — cannot verify integrity.",
        )

    try:
        manifest = json.loads(zf.read("manifest.json"))
    except Exception:
        raise HTTPException(status_code=400, detail="manifest.json is not valid JSON.") from None

    declared_files: dict[str, str] = manifest.get("files", {})
    if not declared_files:
        raise HTTPException(
            status_code=400,
            detail="manifest.json contains no 'files' entries to verify.",
        )

    checked = 0

    # 1. Check each declared file exists and has correct hash.
    for rel_path, expected_sha256 in declared_files.items():
        if rel_path not in zip_names:
            errors.append(VerifyError(file=rel_path, reason="Declared file is missing from ZIP."))
            continue

        actual_sha256 = sha256_of(zf.read(rel_path))
        checked += 1

        if actual_sha256 != expected_sha256.lower():
            errors.append(
                VerifyError(
                    file=rel_path,
                    reason=(
                        f"Hash mismatch: expected {expected_sha256[:16]}…, "
                        f"got {actual_sha256[:16]}…"
                    ),
                )
            )

    # 2. Detect undeclared files (tamper: added files not in manifest).
    for name in zip_names:
        if name == "manifest.json":
            continue
        if name not in declared_files:
            errors.append(
                VerifyError(
                    file=name,
                    reason="File present in ZIP but not declared in manifest.",
                )
            )

    status = "PASS" if not errors else "FAIL"
    logger.info(
        "Package verification: status=%s checked=%d errors=%d file=%s",
        status,
        checked,
        len(errors),
        file.filename,
    )
    return VerifyResponse(status=status, checked_files=checked, errors=errors)
