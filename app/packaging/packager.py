"""
.v52.zip Packager.

Builds a downloadable evidence package from the vault contents of a case.
The ZIP never includes .env files, log files, secrets, or bearer tokens.

Package layout (mirrors architecture doc section 13):
  case.v52.zip
  ├── manifest.json
  ├── evidence/
  │   ├── raw/           ← canonical JSON payloads from vault
  │   └── records/       ← serialized EvidenceRecord objects
  ├── normalized/        ← decoded/normalized events (Jhamil)
  ├── claims/            ← claim predicates (Jhamil + Omar)
  ├── assertions/        ← verdict + evidence citations
  ├── horizons/          ← gaps and unknown limits
  ├── provenance/        ← provenance summary
  └── versions/          ← adapter version metadata
"""

from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path
from typing import Any

from app.evidence.preservation import canonicalize
from app.packaging.manifest import build_manifest

logger = logging.getLogger(__name__)

# Patterns for files/directories that must NEVER be included in a package.
_EXCLUDED_PATTERNS = {
    ".env",
    ".env.local",
    ".env.production",
    "*.log",
    "*.pem",
    "*.key",
}

# Excluded file extensions.
_EXCLUDED_EXTENSIONS = {".log", ".pem", ".key", ".tmp"}


def _is_excluded(path: Path) -> bool:
    """Return True if the given path should be excluded from the package."""
    name = path.name.lower()
    if name.startswith(".env"):
        return True
    if path.suffix.lower() in _EXCLUDED_EXTENSIONS:
        return True
    return False


def build_v52_zip(
    case_id: str,
    chain_id: int,
    tx_hash: str,
    subject: str,
    claim: str,
    status: str,
    verdict: str | None,
    warnings: list[str],
    vault_dir: Path,
    output_dir: Path,
    extra_data: dict[str, Any] | None = None,
) -> Path:
    """
    Build a .v52.zip package for the given case.

    Collects all raw files from the vault for this case, builds the manifest,
    and writes a ZIP to output_dir.

    Args:
        case_id:    Case identifier.
        chain_id:   EIP-155 chain.
        tx_hash:    Transaction hash.
        subject:    Subject address.
        claim:      Original claim text.
        status:     Case status string.
        verdict:    Verdict string or None.
        warnings:   Accumulated warnings.
        vault_dir:  Root of the evidence vault (data_dir).
        output_dir: Directory to write the .v52.zip into.
        extra_data: Optional dict of {archive_path: serializable_object} to include.

    Returns:
        Path to the created .v52.zip file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"{case_id}.v52.zip"

    raw_dir = vault_dir / "raw" / case_id
    file_paths: list[Path] = []

    if raw_dir.exists():
        for f in raw_dir.rglob("*"):
            if f.is_file() and not _is_excluded(f):
                file_paths.append(f)

    manifest = build_manifest(
        case_id=case_id,
        chain_id=chain_id,
        tx_hash=tx_hash,
        subject=subject,
        claim=claim,
        status=status,
        verdict=verdict,
        warnings=warnings,
        file_paths=file_paths,
        base_dir=vault_dir,
    )

    manifest_bytes = canonicalize(manifest)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", manifest_bytes)

        for path in file_paths:
            archive_name = str(path.relative_to(vault_dir))
            zf.write(path, arcname=archive_name)
            logger.debug("Added to package: %s", archive_name)

        # Add any extra serialized data (e.g., normalized events, provenance).
        if extra_data:
            for archive_path, obj in extra_data.items():
                content = canonicalize(obj)
                zf.writestr(archive_path, content)

    zip_path.write_bytes(buf.getvalue())
    logger.info(
        "Package built: %s (%d bytes, %d evidence files)",
        zip_path,
        len(buf.getvalue()),
        len(file_paths),
    )
    return zip_path
