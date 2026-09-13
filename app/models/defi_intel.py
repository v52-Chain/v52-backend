"""Public API models for the multi-chain DeFi Subgraph Intel surface.

Data is queried live from The Graph subgraphs configured per chain (see
app/providers/factory.py and app/api/defi_core.py). Nothing here is invented:
when a chain's subgraph is not configured, or a query returns errors, that is
surfaced as a warning — never silently backfilled with guesses.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ChainKey = Literal["ethereum", "avalanche", "hsk"]
SubgraphSchema = Literal["uniswap_v3", "uniswap_v2"]

_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def _validate_pool_address(value: str) -> str:
    normalized = value.strip().lower()
    if not _ADDRESS_RE.fullmatch(normalized):
        raise ValueError("pool_address must be 0x followed by 40 hexadecimal characters.")
    return normalized


class SubgraphMeta(BaseModel):
    """Mirrors TheGraphProvider._extract_meta — indexing status for a query."""

    block_number: int | None = None
    block_hash: str | None = None
    deployment: str | None = None
    has_indexing_errors: bool | None = None


class DefiTokenRef(BaseModel):
    address: str
    symbol: str | None = None
    decimals: int | None = None


class DefiPoolSummary(BaseModel):
    """One AMM pool/pair — the on-chain contract that executes swaps for it."""

    pool_id: str = Field(description="Pool/pair contract address as reported by the subgraph.")
    subgraph_schema: SubgraphSchema
    token0: DefiTokenRef
    token1: DefiTokenRef
    fee_tier: int | None = Field(
        default=None,
        description="Uniswap V3 fee tier in hundredths of a bip. Null for V2-style pairs.",
    )
    liquidity: str | None = Field(default=None, description="Raw V3 liquidity, as reported.")
    reserve0: str | None = Field(default=None, description="V2-style reserve of token0.")
    reserve1: str | None = Field(default=None, description="V2-style reserve of token1.")
    total_value_locked_usd: str | None = None
    volume_usd: str | None = None
    tx_count: str | None = None


class DefiPoolsResponse(BaseModel):
    chain: ChainKey
    network: str
    subgraph_schema: SubgraphSchema
    pools: list[DefiPoolSummary] = Field(default_factory=list)
    meta: SubgraphMeta = Field(default_factory=SubgraphMeta)
    retrieved_at: datetime
    warnings: list[str] = Field(default_factory=list)


class DefiSwapEvent(BaseModel):
    swap_id: str
    pool_id: str
    timestamp: int | None = None
    transaction_hash: str | None = None
    sender: str | None = None
    recipient: str | None = None
    amount0: str | None = None
    amount1: str | None = None
    amount_usd: str | None = None


class DefiPoolActivityResponse(BaseModel):
    chain: ChainKey
    network: str
    subgraph_schema: SubgraphSchema
    pool_id: str
    swaps: list[DefiSwapEvent] = Field(default_factory=list)
    meta: SubgraphMeta = Field(default_factory=SubgraphMeta)
    retrieved_at: datetime
    warnings: list[str] = Field(default_factory=list)


class DefiChainStatus(BaseModel):
    chain: ChainKey
    network: str
    configured: bool
    subgraph_schema: SubgraphSchema | None = None
    meta: SubgraphMeta | None = None
    warnings: list[str] = Field(default_factory=list)


class DefiEntrypointsStatusResponse(BaseModel):
    chains: list[DefiChainStatus]
    retrieved_at: datetime


class DefiScanChainResult(BaseModel):
    chain: ChainKey
    status: DefiChainStatus
    pools: list[DefiPoolSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DefiScanResponse(BaseModel):
    results: list[DefiScanChainResult] = Field(default_factory=list)
    retrieved_at: datetime
    warnings: list[str] = Field(default_factory=list)


# ── x402 agent job requests/responses ────────────────────────────────────────


class DefiPoolsJobRequest(BaseModel):
    chain: ChainKey
    limit: int = Field(default=10, ge=1, le=50)


class DefiPoolActivityJobRequest(BaseModel):
    chain: ChainKey
    pool_address: str
    limit: int = Field(default=20, ge=1, le=100)

    _pool_address = field_validator("pool_address")(_validate_pool_address)


class DefiScanJobRequest(BaseModel):
    chains: list[ChainKey] = Field(default_factory=lambda: ["ethereum", "avalanche", "hsk"])
    pools_limit: int = Field(default=10, ge=1, le=25)

    @field_validator("chains")
    @classmethod
    def _dedupe_chains(cls, value: list[ChainKey]) -> list[ChainKey]:
        if not value:
            raise ValueError("chains must contain at least one chain.")
        seen: list[ChainKey] = []
        for chain in value:
            if chain not in seen:
                seen.append(chain)
        return seen


class AgentDefiPoolsResponse(BaseModel):
    channel: Literal["AGENT_X402"] = "AGENT_X402"
    request_id: str
    result: DefiPoolsResponse


class AgentDefiPoolActivityResponse(BaseModel):
    channel: Literal["AGENT_X402"] = "AGENT_X402"
    request_id: str
    result: DefiPoolActivityResponse


class AgentDefiScanResponse(BaseModel):
    channel: Literal["AGENT_X402"] = "AGENT_X402"
    request_id: str
    result: DefiScanResponse
