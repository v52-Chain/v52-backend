"""
File-backed cache of the last HSK anchor transaction submitted for a case.

Layout:
    <data_dir>/anchors/<case_id>.json

This is a convenience cache only — it lets POST /v1/cases/{case_id}/anchor
return a tx_hash without re-scanning HSK event logs on every retry. The
contract itself (queried via GET /v1/anchors/{manifest_root}) remains the
source of truth for whether a manifest is actually anchored.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class AnchorStore:
    def __init__(self, data_dir: Path) -> None:
        self._dir = data_dir / "anchors"
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, case_id: str) -> Path:
        return self._dir / f"{case_id}.json"

    def save(self, case_id: str, record: dict[str, Any]) -> None:
        self._path(case_id).write_text(
            json.dumps(record, indent=2, sort_keys=True), encoding="utf-8"
        )

    def get(self, case_id: str) -> dict[str, Any] | None:
        path = self._path(case_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
