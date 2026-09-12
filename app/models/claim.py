"""
Claim models — Request / Response and CaseRecord Pydantic schemas.

Contract owner: Saúl (Pydantic models) + Omar (frontend contract).
Any field change requires review from both developers.

Validated rules:
  - chain_id must be 1 (Ethereum only for P0)
  - transaction_hash must be 66-char hex string starting with 0x
  - subject must be 42-char hex address starting with 0x
  - claim must be non-empty, max 1000 chars
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from app.models.evidence import EvidenceRecord, EvidenceStatus
from app.models.protocol import ProtocolAction
from app.models.verdict import Verdict

# ── Validation patterns ───────────────────────────────────────────────────────
_TX_HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

SUPPORTED_CHAIN_IDS = {1}  # Ethereum mainnet only for P0


class CaseStatus(StrEnum):
    """Overall status of an audit case."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


class Predicate(BaseModel):
    """A single verifiable claim predicate with its evidence evaluation."""

    id: str
    statement: str
    result: bool | None = None
    confidence: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    reasoning: str | None = None


class ContributionSummary(BaseModel):
    """Subject contribution summary — amounts in string form to avoid float errors."""

    subject: str
    amount_in_raw: str | None = None
    amount_out_raw: str | None = None
    token_in_symbol: str | None = None
    token_out_symbol: str | None = None
    percentage_of_pool_volume: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ProvenanceSummary(BaseModel):
    """Traceability summary from raw evidence to verdict."""

    case_id: str
    tx_hash: str
    chain_id: int
    evidence_record_ids: list[str] = Field(default_factory=list)
    vault_paths: list[str] = Field(default_factory=list)
    adapter_versions: list[str] = Field(default_factory=list)


# ── Request ───────────────────────────────────────────────────────────────────


class ClaimAuditRequest(BaseModel):
    """
    Minimum request payload for POST /v1/claim-audit.
    Validates chain ID, tx hash format, claim length and subject address format.
    """

    chain_id: int = Field(
        description="EIP-155 chain ID.  Only Ethereum mainnet (1) is supported in P0."
    )
    transaction_hash: str = Field(
        description="Full 32-byte transaction hash in hex, prefixed with 0x."
    )
    claim: str = Field(min_length=1, max_length=1000, description="Human-readable claim to audit.")
    subject: str = Field(description="Ethereum address of the alleged subject (0x…).")
    use_ai: bool = Field(
        default=False,
        description="If true, an AI explanation (L5) is appended.  Non-authoritative.",
    )

    @field_validator("chain_id")
    @classmethod
    def validate_chain_id(cls, v: int) -> int:
        if v not in SUPPORTED_CHAIN_IDS:
            msg = f"chain_id {v} is not supported.  Supported: {sorted(SUPPORTED_CHAIN_IDS)}."
            raise ValueError(msg)
        return v

    @field_validator("transaction_hash")
    @classmethod
    def validate_tx_hash(cls, v: str) -> str:
        if not _TX_HASH_RE.match(v):
            raise ValueError(
                "transaction_hash must be a 0x-prefixed 64-character hex string (32 bytes)."
            )
        return v.lower()

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, v: str) -> str:
        if not _ADDRESS_RE.match(v):
            raise ValueError(
                "subject must be a 0x-prefixed 40-character hex string (20 bytes / EVM address)."
            )
        return v.lower()


# ── Response ──────────────────────────────────────────────────────────────────


class ClaimAuditResponse(BaseModel):
    """
    Minimum response payload from POST /v1/claim-audit.
    Frontend never receives provider secrets or raw credentials.
    """

    case_id: str
    status: CaseStatus
    verdict: Verdict | None = None
    summary: str = ""
    predicates: list[Predicate] = Field(default_factory=list)
    evidence_for: list[EvidenceRecord] = Field(default_factory=list)
    evidence_against: list[EvidenceRecord] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    protocol_action: ProtocolAction | None = None
    contribution: ContributionSummary | None = None
    provenance: ProvenanceSummary | None = None
    timing_ms: dict[str, int] = Field(
        default_factory=dict,
        description="Milliseconds per pipeline stage.  No credentials in keys or values.",
    )


# ── Case Record ───────────────────────────────────────────────────────────────


class CaseRecord(BaseModel):
    """
    Persisted case metadata (written to file-based store in P0, MongoDB in P1).
    Raw evidence is referenced by path + hash, never duplicated here.
    """

    case_id: str
    chain_id: int
    transaction_hash: str
    subject: str
    claim: str
    status: CaseStatus = CaseStatus.PENDING
    verdict: Verdict | None = None
    evidence_status: EvidenceStatus = EvidenceStatus.PENDING
    evidence_record_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    warnings: list[str] = Field(default_factory=list)
    timing_ms: dict[str, int] = Field(default_factory=dict)
