"""Deterministic ERC-20 transfer models.

Addresses are normalized to lowercase hexadecimal so comparisons do not depend
on display casing. Token quantities remain decimal integer strings at every
authority level; a formatted amount is optional derived metadata.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_TX_HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
_UINT_STRING_RE = re.compile(r"^(0|[1-9][0-9]*)$")


class TokenMetadata(BaseModel):
    """Optional, evidenced metadata used only to format a raw token amount."""

    address: str
    symbol: str | None = None
    decimals: int | None = Field(default=None, ge=0, le=255)

    @field_validator("address")
    @classmethod
    def normalize_address(cls, value: str) -> str:
        if not _ADDRESS_RE.fullmatch(value):
            raise ValueError("address must be a 0x-prefixed 20-byte hex value")
        return value.lower()


class DecodedTransfer(BaseModel):
    """An ERC-20 ``Transfer`` event decoded from one exact L0 log."""

    token_address: str
    from_address: str
    to_address: str
    amount_raw: str = Field(description="Exact uint256 value as a base-10 integer string.")
    transaction_hash: str
    block_number: int = Field(ge=0)
    log_index: int = Field(ge=0)
    evidence_ids: list[str] = Field(min_length=1)
    token_symbol: str | None = None
    token_decimals: int | None = Field(default=None, ge=0, le=255)
    amount_formatted: str | None = Field(
        default=None,
        description="Exact decimal representation when evidenced decimals are available.",
    )
    warnings: list[str] = Field(default_factory=list)

    @field_validator("token_address", "from_address", "to_address")
    @classmethod
    def normalize_address(cls, value: str) -> str:
        if not _ADDRESS_RE.fullmatch(value):
            raise ValueError("address must be a 0x-prefixed 20-byte hex value")
        return value.lower()

    @field_validator("transaction_hash")
    @classmethod
    def normalize_transaction_hash(cls, value: str) -> str:
        if not _TX_HASH_RE.fullmatch(value):
            raise ValueError("transaction_hash must be a 0x-prefixed 32-byte hex value")
        return value.lower()

    @field_validator("amount_raw")
    @classmethod
    def validate_amount_raw(cls, value: str) -> str:
        if not _UINT_STRING_RE.fullmatch(value):
            raise ValueError("amount_raw must be a canonical unsigned base-10 integer string")
        return value

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("evidence_ids cannot contain empty identifiers")
        return list(dict.fromkeys(values))

