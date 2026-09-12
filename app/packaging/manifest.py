"""
.v52 Manifest builder.

The manifest.json file is the root of trust for package verification.
It records version, scope, chain, tx hash, status, warnings and all files
with their SHA-256 hashes.

Rules:
  - The manifest must be built AFTER all evidence files are written.
  - It never includes .env, log files, or any secrets.
  - SHA-256 values are computed fresh at manifest build time.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.evidence.preservation import sha256_of


def build_manifest(
    case_id: str,
    chain_id: int,
    tx_hash: str,
    subject: str,
    claim: str,
    status: str,
    verdict: str | None,
    warnings: list[str],
    file_paths: list[Path],
    base_dir: Path,
    adapter_version: str = "0.1.0",
    schema_version: str = "0.1.0",
) -> dict[str, Any]:
    """
    Build a manifest dict for a .v52.zip package.

    Args:
        case_id:        Unique case identifier.
        chain_id:       EIP-155 chain ID.
        tx_hash:        Transaction hash (0x-prefixed).
        subject:        Subject address.
        claim:          Original claim text.
        status:         Overall case status string.
        verdict:        Verdict string or None if not yet computed.
        warnings:       List of warning messages accumulated during audit.
        file_paths:     Absolute paths to files to include in the package.
        base_dir:       Root directory relative to which paths are stored in manifest.
        adapter_version: Version of the evidence adapter.
        schema_version: Version of the manifest schema.

    Returns:
        Manifest dict ready to serialize as manifest.json.
    """
    files: dict[str, str] = {}
    for path in sorted(file_paths):
        if not path.exists():
            continue
        rel = str(path.relative_to(base_dir))
        files[rel] = sha256_of(path.read_bytes())

    return {
        "schema_version": schema_version,
        "adapter_version": adapter_version,
        "generated_at": datetime.now(UTC).isoformat(),
        "case_id": case_id,
        "scope": {
            "chain_id": chain_id,
            "transaction_hash": tx_hash,
            "subject": subject,
            "claim": claim,
        },
        "status": status,
        "verdict": verdict,
        "warnings": warnings,
        "files": files,
    }
