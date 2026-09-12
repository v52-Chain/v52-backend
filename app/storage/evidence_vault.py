"""
Evidence Vault — append-only raw evidence storage with SHA-256 integrity.

Rules:
  - Evidence is NEVER overwritten once stored.
  - Raw content is serialized to canonical JSON and hashed before write.
  - Secrets must be stripped from payloads before calling preserve_raw().
  - The vault directory structure is: <data_dir>/raw/<case_id>/<evidence_id>.json
  - A corresponding .sha256 sidecar file is written for independent verification.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.evidence.preservation import canonicalize, sha256_of

logger = logging.getLogger(__name__)


class EvidenceVaultError(Exception):
    """Raised when vault integrity constraints are violated."""


class EvidenceVault:
    """
    Append-only file-based Evidence Vault.

    Each raw evidence payload is written once.  Subsequent calls with the same
    path raise EvidenceVaultError rather than silently overwriting data.

    Directory layout:
        <data_dir>/
          raw/
            <case_id>/
              <evidence_id>.json       ← canonical JSON of raw payload
              <evidence_id>.sha256     ← hex SHA-256 of the .json file
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self._raw_dir = data_dir / "raw"
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        logger.info("EvidenceVault initialized at %s", self.data_dir)

    def preserve_raw(
        self,
        case_id: str,
        evidence_id: str,
        payload: Any,
    ) -> tuple[str, str]:
        """
        Serialize *payload* to canonical JSON, compute SHA-256, and write both
        to disk if the target path does not already exist.

        Returns:
            (raw_path, raw_sha256) — relative path (str) and hex digest.

        Raises:
            EvidenceVaultError: if a file with that path already exists.
        """
        case_dir = self._raw_dir / case_id
        case_dir.mkdir(parents=True, exist_ok=True)

        json_path = case_dir / f"{evidence_id}.json"
        sha_path = case_dir / f"{evidence_id}.sha256"

        if json_path.exists():
            raise EvidenceVaultError(
                f"Evidence already exists at '{json_path}'. "
                "The vault is append-only; overwriting is not permitted."
            )

        # Serialize and hash BEFORE writing (rule: hash before transform).
        canonical_bytes = canonicalize(payload)
        digest = sha256_of(canonical_bytes)

        json_path.write_bytes(canonical_bytes)
        sha_path.write_text(digest, encoding="utf-8")

        relative_path = str(json_path.relative_to(self.data_dir))
        logger.debug(
            "Preserved raw evidence: path=%s sha256=%s…",
            relative_path,
            digest[:16],
        )
        return relative_path, digest

    def verify_raw(self, raw_path: str, expected_sha256: str) -> bool:
        """
        Recompute the SHA-256 of the stored file and compare with the expected digest.
        Returns True if they match, False if the file is missing or modified.
        """
        full_path = self.data_dir / raw_path
        if not full_path.exists():
            logger.warning("verify_raw: file not found at %s", full_path)
            return False
        actual = sha256_of(full_path.read_bytes())
        match = actual == expected_sha256.lower()
        if not match:
            logger.warning(
                "verify_raw: MISMATCH at %s — expected %s, got %s",
                raw_path,
                expected_sha256[:16],
                actual[:16],
            )
        return match

    def read_raw(self, raw_path: str) -> bytes:
        """
        Read and return the raw bytes of a stored evidence file.
        Raises FileNotFoundError if the path does not exist.
        """
        full_path = self.data_dir / raw_path
        if not full_path.exists():
            raise FileNotFoundError(f"Evidence file not found: {raw_path}")
        return full_path.read_bytes()

    def list_case_files(self, case_id: str) -> list[str]:
        """Return relative paths of all raw files for a case, sorted."""
        case_dir = self._raw_dir / case_id
        if not case_dir.exists():
            return []
        return sorted(
            str(p.relative_to(self.data_dir))
            for p in case_dir.iterdir()
            if p.suffix == ".json"
        )
