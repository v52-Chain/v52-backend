"""
Evidence models — Pydantic schemas for Evidence Records and provider state.

Authority levels:
  L0 CHAIN_PRIMARY  — tx, receipt, block, raw logs via RPC
  L1 INDEXED        — The Graph response and metadata
  L2 DECODED        — ERC-20 and Uniswap interpreted events
  L3 DERIVED        — deterministic Contribution Analysis
  L4 ANALYST        — predicates and verdict
  L5 AI_EXPLANATION — non-authoritative natural language
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AuthorityLevel(StrEnum):
    """Hierarchy of evidence authority; lower numbers are more authoritative."""

    L0_CHAIN_PRIMARY = "L0_CHAIN_PRIMARY"
    L1_INDEXED = "L1_INDEXED"
    L2_DECODED = "L2_DECODED"
    L3_DERIVED = "L3_DERIVED"
    L4_ANALYST = "L4_ANALYST"
    L5_AI_EXPLANATION = "L5_AI_EXPLANATION"


class EvidenceStatus(StrEnum):
    """
    Lifecycle status of a single evidence record.
    A timeout, partial response, or indexing error NEVER becomes COMPLETE.
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    WARNING = "WARNING"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class ProviderStatus(StrEnum):
    """Operational status of a remote provider at acquisition time."""

    OK = "OK"
    DEGRADED = "DEGRADED"
    TIMEOUT = "TIMEOUT"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class EvidenceRecord(BaseModel):
    """
    Minimum Evidence Record as defined in the technical contract (section 9).
    All fields are required.  Raw content is referenced by path + hash,
    never embedded here.
    """

    evidence_id: str = Field(
        description="Unique, stable identifier.  Format: ev_<sha256-prefix>_<uuid4-short>"
    )
    authority_level: AuthorityLevel
    chain_id: int = Field(ge=1, description="EIP-155 chain ID.  Only chain 1 (Ethereum) for P0.")
    source: str = Field(description="Provider name, e.g. 'ethereum_rpc' or 'the_graph'.")
    source_type: str | None = Field(
        default=None,
        description="Logical evidence source type, e.g. RPC_PROVIDER or INDEXED_PROVIDER.",
    )
    provider: str | None = Field(
        default=None,
        description="Redacted public provider label, e.g. alchemy or hsk_rpc.",
    )
    network: str | None = Field(default=None, description="Logical network name.")
    endpoint_id: str | None = Field(
        default=None,
        description="Redacted endpoint identifier. Never contains API keys.",
    )
    method: str = Field(
        description="RPC method or GraphQL operation name used to obtain this record."
    )
    request_fingerprint: str = Field(
        description="SHA-256 of the canonicalized request payload.  Format: sha256:<hex>"
    )
    retrieved_at: datetime = Field(description="UTC timestamp of successful acquisition.")
    raw_path: str = Field(description="Relative path inside evidence_vault to the raw JSON file.")
    raw_sha256: str = Field(description="SHA-256 hex digest of the raw file at raw_path.")
    adapter_version: str = Field(
        default="0.1.0",
        description="Version of the provider adapter that produced this record.",
    )
    status: EvidenceStatus
    warnings: list[str] = Field(default_factory=list)

    # Optional fields for The Graph records (L1)
    block_number: int | None = Field(default=None, description="Block number at indexing time.")
    block_hash: str | None = Field(default=None, description="Block hash when available.")
    indexing_errors: bool | None = Field(
        default=None, description="True if The Graph reported hasIndexingErrors."
    )
    graph_deployment: str | None = Field(
        default=None, description="Subgraph deployment ID when available."
    )

    model_config = {"populate_by_name": True}
