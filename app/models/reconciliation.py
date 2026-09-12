"""Graph/RPC reconciliation models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ReconciliationStatus(StrEnum):
    """Allowed reconciliation outcomes from FRANCO.md."""

    CORROBORATED = "CORROBORATED"
    MISMATCH = "MISMATCH"
    INDEXER_LAG_SUSPECTED = "INDEXER_LAG_SUSPECTED"
    RPC_UNAVAILABLE = "RPC_UNAVAILABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ReconciliationResult(BaseModel):
    """Comparison between one indexed event and one RPC log."""

    status: ReconciliationStatus
    evidence_ids: list[str] = Field(default_factory=list)
    transaction_hash: str | None = None
    log_index: int | None = None
    contract_address: str | None = None
    block_number: int | None = None
    block_hash: str | None = None
    compared_fields: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
