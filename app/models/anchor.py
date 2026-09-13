"""Pydantic models for HSK V52EvidenceRegistry anchoring endpoints."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

BYTES32_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")


class AnchorCaseRequest(BaseModel):
    """Optional body for POST /v1/cases/{case_id}/anchor."""

    supersedes: str | None = Field(
        default=None,
        description=(
            "manifest_root (0x + 64 hex chars) of a prior anchor this one "
            "replaces. Omit for a first-time anchor."
        ),
    )

    @field_validator("supersedes")
    @classmethod
    def validate_supersedes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not BYTES32_RE.match(value):
            raise ValueError(
                "supersedes must be a 0x-prefixed 64-character hex string (32 bytes)."
            )
        return value.lower()


class AnchorCaseResponse(BaseModel):
    """Response payload for POST /v1/cases/{case_id}/anchor."""

    case_id: str
    manifest_root: str
    methodology_hash: str
    schema_version: str
    issuer: str
    supersedes: str | None
    chain_id: int
    tx_hash: str
    block_number: int
    gas_used: int
    explorer_tx_url: str
    explorer_address_url: str
    already_anchored: bool = Field(
        default=False,
        description="True when this exact manifest_root was already anchored (idempotent replay).",
    )


class AnchorLookupResponse(BaseModel):
    """Response payload for GET /v1/anchors/{manifest_root}."""

    manifest_root: str
    methodology_hash: str
    schema_version: str
    case_id: str
    issuer: str
    block_number: int
    timestamp: int
    supersedes: str | None
    chain_id: int
    tx_hash: str | None
    explorer_tx_url: str | None
    explorer_address_url: str
