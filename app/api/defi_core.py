"""Shared DeFi Subgraph Intel acquisition — consumed by the free status
endpoint (app/api/intel.py) and the x402-paid agent endpoints (app/api/agent.py).

Scans "vital points" of a chain's DeFi surface — AMM pools/pairs (the swap
contracts themselves) and their recent swap activity — by querying the
subgraph configured for that chain (app/providers/factory.py). Two subgraph
schema families are supported, since most subgraphs on Ethereum/Avalanche
fork one of these two shapes:

  - "uniswap_v3": pools / feeTier / liquidity / totalValueLockedUSD
  - "uniswap_v2": pairs / reserve0 / reserve1 / reserveUSD

Rules (same as app/providers/the_graph.py):
  - Live data is consumed; nothing here is invented.
  - query, variables and _meta are always preserved in the response's `meta`.
  - If a chain's subgraph is not configured, or it errors, that is a
    warning/503 — never a fabricated result.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException

from app.config import Settings
from app.models.defi_intel import (
    ChainKey,
    DefiChainStatus,
    DefiPoolActivityResponse,
    DefiPoolsResponse,
    DefiPoolSummary,
    DefiScanChainResult,
    DefiScanResponse,
    DefiSwapEvent,
    DefiTokenRef,
    SubgraphMeta,
)
from app.providers.base import ProviderError
from app.providers.factory import (
    GraphChainConfig,
    configured_graph_chains,
    get_graph_provider_for_chain,
)

_META_QUERY = "query { _meta { block { number hash } deployment hasIndexingErrors } }"

_POOLS_QUERY_V3 = """
query TopPools($limit: Int!) {
  _meta { block { number hash } deployment hasIndexingErrors }
  pools(first: $limit, orderBy: totalValueLockedUSD, orderDirection: desc) {
    id
    token0 { id symbol decimals }
    token1 { id symbol decimals }
    feeTier
    liquidity
    totalValueLockedUSD
    volumeUSD
    txCount
  }
}
"""

_POOLS_QUERY_V2 = """
query TopPairs($limit: Int!) {
  _meta { block { number hash } deployment hasIndexingErrors }
  pairs(first: $limit, orderBy: reserveUSD, orderDirection: desc) {
    id
    token0 { id symbol decimals }
    token1 { id symbol decimals }
    reserve0
    reserve1
    reserveUSD
    volumeUSD
    txCount
  }
}
"""

_SWAPS_QUERY_V3 = """
query PoolSwaps($pool: String!, $limit: Int!) {
  _meta { block { number hash } deployment hasIndexingErrors }
  swaps(where: { pool: $pool }, orderBy: timestamp, orderDirection: desc, first: $limit) {
    id
    timestamp
    transaction { id }
    sender
    recipient
    amount0
    amount1
    amountUSD
  }
}
"""

_SWAPS_QUERY_V2 = """
query PairSwaps($pool: String!, $limit: Int!) {
  _meta { block { number hash } deployment hasIndexingErrors }
  swaps(where: { pair: $pool }, orderBy: timestamp, orderDirection: desc, first: $limit) {
    id
    timestamp
    transaction { id }
    sender
    to
    amount0In
    amount0Out
    amount1In
    amount1Out
    amountUSD
  }
}
"""

_STALE_INDEX_WARNING = (
    "Pool/pair ranking and amounts reflect the subgraph's own indexing state; "
    "they may lag the chain head by the subgraph's indexing delay."
)
_ABSENCE_WARNING = (
    "Absence of swaps in this window does not prove the pool/pair is inactive; "
    "it only means none were indexed within the returned window."
)


def _extract_meta(response: dict[str, Any]) -> SubgraphMeta:
    root = response.get("data") or {}
    raw = root.get("_meta")
    if not raw:
        return SubgraphMeta()
    block = raw.get("block") or {}
    return SubgraphMeta(
        block_number=block.get("number"),
        block_hash=block.get("hash"),
        deployment=raw.get("deployment"),
        has_indexing_errors=raw.get("hasIndexingErrors"),
    )


def _token_ref(raw: dict[str, Any] | None) -> DefiTokenRef:
    raw = raw or {}
    return DefiTokenRef(
        address=str(raw.get("id", "")).lower(),
        symbol=raw.get("symbol"),
        decimals=raw.get("decimals"),
    )


def _pool_from_v3(raw: dict[str, Any]) -> DefiPoolSummary:
    return DefiPoolSummary(
        pool_id=str(raw.get("id", "")).lower(),
        subgraph_schema="uniswap_v3",
        token0=_token_ref(raw.get("token0")),
        token1=_token_ref(raw.get("token1")),
        fee_tier=raw.get("feeTier"),
        liquidity=raw.get("liquidity"),
        total_value_locked_usd=raw.get("totalValueLockedUSD"),
        volume_usd=raw.get("volumeUSD"),
        tx_count=raw.get("txCount"),
    )


def _pool_from_v2(raw: dict[str, Any]) -> DefiPoolSummary:
    return DefiPoolSummary(
        pool_id=str(raw.get("id", "")).lower(),
        subgraph_schema="uniswap_v2",
        token0=_token_ref(raw.get("token0")),
        token1=_token_ref(raw.get("token1")),
        reserve0=raw.get("reserve0"),
        reserve1=raw.get("reserve1"),
        total_value_locked_usd=raw.get("reserveUSD"),
        volume_usd=raw.get("volumeUSD"),
        tx_count=raw.get("txCount"),
    )


def _nonzero(value: Any) -> bool:
    try:
        return value is not None and float(value) != 0.0
    except (TypeError, ValueError):
        return False


def _swap_from_v3(raw: dict[str, Any], pool_id: str) -> DefiSwapEvent:
    tx = raw.get("transaction") or {}
    return DefiSwapEvent(
        swap_id=str(raw.get("id", "")),
        pool_id=pool_id,
        timestamp=raw.get("timestamp"),
        transaction_hash=tx.get("id"),
        sender=raw.get("sender"),
        recipient=raw.get("recipient"),
        amount0=raw.get("amount0"),
        amount1=raw.get("amount1"),
        amount_usd=raw.get("amountUSD"),
    )


def _swap_from_v2(raw: dict[str, Any], pool_id: str) -> DefiSwapEvent:
    tx = raw.get("transaction") or {}
    amount0 = raw.get("amount0In") if _nonzero(raw.get("amount0In")) else raw.get("amount0Out")
    amount1 = raw.get("amount1In") if _nonzero(raw.get("amount1In")) else raw.get("amount1Out")
    return DefiSwapEvent(
        swap_id=str(raw.get("id", "")),
        pool_id=pool_id,
        timestamp=raw.get("timestamp"),
        transaction_hash=tx.get("id"),
        sender=raw.get("sender"),
        recipient=raw.get("to"),
        amount0=amount0,
        amount1=amount1,
        amount_usd=raw.get("amountUSD"),
    )


def _graph_config(settings: Settings, chain: ChainKey) -> GraphChainConfig:
    return configured_graph_chains(settings)[chain]


async def get_chain_status(settings: Settings, chain: ChainKey) -> DefiChainStatus:
    """Lightweight, single-query status check — safe to expose without payment."""
    cfg = _graph_config(settings, chain)
    if not cfg.configured:
        return DefiChainStatus(
            chain=chain,
            network=cfg.network,
            configured=False,
            warnings=[
                f"The Graph is not configured for chain '{chain}'. "
                f"Set V52_GRAPH_ENDPOINT_{chain.upper()} to enable it."
            ],
        )
    provider = get_graph_provider_for_chain(settings, chain)
    assert provider is not None  # cfg.configured already guarantees this
    try:
        result = await provider.query(query=_META_QUERY)
    except ProviderError as exc:
        return DefiChainStatus(
            chain=chain,
            network=cfg.network,
            configured=True,
            subgraph_schema=cfg.schema,  # type: ignore[arg-type]
            warnings=[str(exc)],
        )
    return DefiChainStatus(
        chain=chain,
        network=cfg.network,
        configured=True,
        subgraph_schema=cfg.schema,  # type: ignore[arg-type]
        meta=_extract_meta(result["response"]),
        warnings=list(result.get("warnings", [])),
    )


async def run_pools_scan(settings: Settings, chain: ChainKey, limit: int) -> DefiPoolsResponse:
    """Top pools/pairs by liquidity for one chain — the chain's busiest swap contracts."""
    cfg = _graph_config(settings, chain)
    if not cfg.configured:
        raise HTTPException(
            status_code=503,
            detail=(
                f"The Graph is not configured for chain '{chain}'. "
                f"Set V52_GRAPH_ENDPOINT_{chain.upper()} in the backend .env."
            ),
        )
    provider = get_graph_provider_for_chain(settings, chain)
    assert provider is not None
    query = _POOLS_QUERY_V3 if cfg.schema == "uniswap_v3" else _POOLS_QUERY_V2
    try:
        result = await provider.query(query=query, variables={"limit": limit})
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    data = result["response"].get("data") or {}
    raw_pools = data.get("pools") if cfg.schema == "uniswap_v3" else data.get("pairs")
    build = _pool_from_v3 if cfg.schema == "uniswap_v3" else _pool_from_v2
    pools = [build(raw) for raw in (raw_pools or [])]

    warnings = list(result.get("warnings", []))
    warnings.append(_STALE_INDEX_WARNING)

    return DefiPoolsResponse(
        chain=chain,
        network=cfg.network,
        subgraph_schema=cfg.schema,  # type: ignore[arg-type]
        pools=pools,
        meta=_extract_meta(result["response"]),
        retrieved_at=datetime.now(UTC),
        warnings=warnings,
    )


async def run_pool_activity(
    settings: Settings, chain: ChainKey, pool_address: str, limit: int
) -> DefiPoolActivityResponse:
    """Recent swaps at one specific pool/pair — a drill-down into a single vital point."""
    cfg = _graph_config(settings, chain)
    if not cfg.configured:
        raise HTTPException(
            status_code=503,
            detail=(
                f"The Graph is not configured for chain '{chain}'. "
                f"Set V52_GRAPH_ENDPOINT_{chain.upper()} in the backend .env."
            ),
        )
    provider = get_graph_provider_for_chain(settings, chain)
    assert provider is not None
    query = _SWAPS_QUERY_V3 if cfg.schema == "uniswap_v3" else _SWAPS_QUERY_V2
    try:
        result = await provider.query(
            query=query, variables={"pool": pool_address, "limit": limit}
        )
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    data = result["response"].get("data") or {}
    raw_swaps = data.get("swaps") or []
    build = _swap_from_v3 if cfg.schema == "uniswap_v3" else _swap_from_v2
    swaps = [build(raw, pool_address) for raw in raw_swaps]

    warnings = list(result.get("warnings", []))
    warnings.append(_ABSENCE_WARNING)

    return DefiPoolActivityResponse(
        chain=chain,
        network=cfg.network,
        subgraph_schema=cfg.schema,  # type: ignore[arg-type]
        pool_id=pool_address,
        swaps=swaps,
        meta=_extract_meta(result["response"]),
        retrieved_at=datetime.now(UTC),
        warnings=warnings,
    )


async def run_full_scan(
    settings: Settings, chains: list[ChainKey], pools_limit: int
) -> DefiScanResponse:
    """Aggregate vital-points scan (status + top pools) across several chains at once."""

    async def _one(chain: ChainKey) -> DefiScanChainResult:
        status = await get_chain_status(settings, chain)
        pools: list[DefiPoolSummary] = []
        warnings = list(status.warnings)
        if status.configured:
            try:
                pools_response = await run_pools_scan(settings, chain, pools_limit)
                pools = pools_response.pools
                warnings.extend(pools_response.warnings)
            except HTTPException as exc:
                warnings.append(str(exc.detail))
        return DefiScanChainResult(chain=chain, status=status, pools=pools, warnings=warnings)

    results = list(await asyncio.gather(*(_one(chain) for chain in chains)))
    return DefiScanResponse(results=results, retrieved_at=datetime.now(UTC))
