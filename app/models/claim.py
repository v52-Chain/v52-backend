"""Claim, case and audit response models."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from app.models.evidence import EvidenceRecord, EvidenceStatus
from app.models.protocol import ProtocolAction
from app.models.reconciliation import ReconciliationResult
from app.models.verdict import Verdict

_TX_HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

SUPPORTED_CHAIN_IDS = {1, 177, 43113, 43114}


class CaseStatus(StrEnum):
    """Overall status of an audit case."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class Predicate(BaseModel):
    """A single verifiable claim predicate with its evidence evaluation."""

    id: str
    statement: str
    result: bool | None = None
    confidence: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    reasoning: str | None = None


class TokenAmountValue(BaseModel):
    """Integer/string token amount. Never use floats for money."""

    raw: str
    decimals: int | None = None
    symbol: str | None = None


class ContributionSummary(BaseModel):
    """Subject contribution summary using strings for exact amounts."""

    subject: str
    amount_in_raw: str | None = None
    amount_out_raw: str | None = None
    token_in_symbol: str | None = None
    token_out_symbol: str | None = None
    percentage_of_pool_volume: str | None = None
    counterparty_volume: TokenAmountValue | None = None
    case_flow: TokenAmountValue | None = None
    attributable_value: TokenAmountValue | None = None
    unknown_or_unattributable: TokenAmountValue | None = None
    methodology_version: str = "v52-contribution-0.1.0"
    evidence_ids: list[str] = Field(default_factory=list)
    limits: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ProvenanceSummary(BaseModel):
    """Traceability summary from raw evidence to verdict."""

    case_id: str
    tx_hash: str
    chain_id: int
    evidence_record_ids: list[str] = Field(default_factory=list)
    vault_paths: list[str] = Field(default_factory=list)
    adapter_versions: list[str] = Field(default_factory=list)


class ClaimAuditRequest(BaseModel):
    """Minimum request payload for POST /v1/claim-audit and /v1/audits."""

    chain_id: int = Field(description="EIP-155 chain ID.")
    transaction_hash: str = Field(
        description="Full 32-byte transaction hash in hex, prefixed with 0x."
    )
    claim: str = Field(min_length=1, max_length=1000, description="Human-readable claim.")
    subject: str = Field(description="EVM address of the subject under analysis.")
    use_ai: bool = Field(
        default=False,
        description="If true, an AI explanation may be appended. Non-authoritative.",
    )

    @field_validator("chain_id")
    @classmethod
    def validate_chain_id(cls, value: int) -> int:
        if value not in SUPPORTED_CHAIN_IDS:
            msg = f"chain_id {value} is not supported. Supported: {sorted(SUPPORTED_CHAIN_IDS)}."
            raise ValueError(msg)
        return value

    @field_validator("transaction_hash")
    @classmethod
    def validate_tx_hash(cls, value: str) -> str:
        if not _TX_HASH_RE.match(value):
            raise ValueError(
                "transaction_hash must be a 0x-prefixed 64-character hex string (32 bytes)."
            )
        return value.lower()

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: str) -> str:
        if not _ADDRESS_RE.match(value):
            raise ValueError(
                "subject must be a 0x-prefixed 40-character hex string (20 bytes / EVM address)."
            )
        return value.lower()


class ClaimAuditResponse(BaseModel):
    """Response payload from the audit pipeline."""

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
    reconciliation: list[ReconciliationResult] = Field(default_factory=list)
    provenance: ProvenanceSummary | None = None
    timing_ms: dict[str, int] = Field(
        default_factory=dict,
        description="Milliseconds per pipeline stage. No credentials in keys or values.",
    )


class CaseRecord(BaseModel):
    """Persisted case metadata. Raw evidence is referenced by path and hash."""

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
