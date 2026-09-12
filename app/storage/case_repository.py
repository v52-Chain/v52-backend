"""
Case Repository — interface and file-backed P0 adapter.

Architecture doc section 5.1:
  - P0 uses file-backed storage.
  - MongoDB adapter (P1) is activated only after the file flow works end-to-end.
  - Raw evidence is referenced by path + hash, never duplicated in the case record.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path

from app.models.claim import CaseRecord, CaseStatus

logger = logging.getLogger(__name__)


# ── Interface ─────────────────────────────────────────────────────────────────


class CaseRepository(ABC):
    """Abstract interface for case persistence."""

    @abstractmethod
    async def save(self, record: CaseRecord) -> None:
        """Persist or update a case record."""

    @abstractmethod
    async def get(self, case_id: str) -> CaseRecord | None:
        """Retrieve a case record by ID.  Returns None if not found."""

    @abstractmethod
    async def update_status(
        self,
        case_id: str,
        status: CaseStatus,
        warnings: list[str] | None = None,
    ) -> None:
        """Update the status (and optional warnings) of an existing case."""

    @abstractmethod
    async def list_all(self) -> list[CaseRecord]:
        """Return all stored case records."""


# ── File-backed P0 adapter ────────────────────────────────────────────────────


class FileCaseRepository(CaseRepository):
    """
    Simple file-backed CaseRepository for P0.

    Layout:
        <data_dir>/cases/<case_id>/case.json

    Each case is stored as a single JSON file.  Concurrent writes are not
    safe for multi-process deployments, but are acceptable for P0 demo use.
    """

    def __init__(self, data_dir: Path) -> None:
        self._cases_dir = data_dir / "cases"
        self._cases_dir.mkdir(parents=True, exist_ok=True)
        logger.info("FileCaseRepository initialized at %s", self._cases_dir)

    def _path(self, case_id: str) -> Path:
        case_dir = self._cases_dir / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        return case_dir / "case.json"

    async def save(self, record: CaseRecord) -> None:
        path = self._path(record.case_id)
        path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        logger.debug("Case saved: %s", record.case_id)

    async def get(self, case_id: str) -> CaseRecord | None:
        path = self._path(case_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return CaseRecord(**data)

    async def update_status(
        self,
        case_id: str,
        status: CaseStatus,
        warnings: list[str] | None = None,
    ) -> None:
        record = await self.get(case_id)
        if record is None:
            raise FileNotFoundError(f"Case '{case_id}' not found in repository.")
        record.status = status
        record.updated_at = datetime.now(UTC)
        if warnings:
            record.warnings.extend(warnings)
        await self.save(record)

    async def list_all(self) -> list[CaseRecord]:
        records: list[CaseRecord] = []
        for case_dir in sorted(self._cases_dir.iterdir()):
            case_file = case_dir / "case.json"
            if case_file.exists():
                try:
                    data = json.loads(case_file.read_text(encoding="utf-8"))
                    records.append(CaseRecord(**data))
                except Exception as exc:
                    logger.warning("Failed to load case from %s: %s", case_file, exc)
        return records
