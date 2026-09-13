"""DeFi Subgraph Intel tests — chain resolution, query parsing and endpoints.

No real network calls: The Graph queries are mocked with respx (like
test_wallet_flow.py mocks Alchemy). Live-network coverage for TheGraphProvider
itself already exists in tests/test_providers.py.
"""

from __future__ import annotations

import pytest
import respx
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from httpx import Response
from pydantic import ValidationError

from app.api import agent as agent_module
from app.api.defi_core import get_chain_status, run_full_scan, run_pool_activity, run_pools_scan
from app.config import Settings, get_settings
from app.main import app
from app.payments.x402 import configure_x402
from app.providers.factory import configured_graph_chains, get_graph_provider_for_chain

GRAPH_URL = "https://mock.thegraph.test/eth"
POOL_ADDRESS = "0x" + "a" * 40


def _settings(**overrides) -> Settings:
    base = {"_env_file": None, "V52_ENV": "development", "V52_GRAPH_ENDPOINT": ""}
    base.update(overrides)
    return Settings(**base)


# ── Per-chain configuration resolution (app/providers/factory.py) ────────────


def test_ethereum_falls_back_to_legacy_graph_fields() -> None:
    settings = _settings(V52_GRAPH_ENDPOINT="https://legacy/eth", V52_GRAPH_API_KEY="k")
    chains = configured_graph_chains(settings)
    assert chains["ethereum"].configured is True
    assert chains["ethereum"].endpoint == "https://legacy/eth"
    assert chains["avalanche"].configured is False
    assert chains["hsk"].configured is False


def test_explicit_ethereum_endpoint_overrides_legacy_field() -> None:
    settings = _settings(
        V52_GRAPH_ENDPOINT="https://legacy/eth",
        V52_GRAPH_ENDPOINT_ETHEREUM="https://explicit/eth",
    )
    assert configured_graph_chains(settings)["ethereum"].endpoint == "https://explicit/eth"


def test_avalanche_and_hsk_are_independently_configurable() -> None:
    settings = _settings(V52_GRAPH_ENDPOINT_AVALANCHE="https://gw/avax")
    chains = configured_graph_chains(settings)
    assert chains["avalanche"].configured is True
    assert chains["hsk"].configured is False


def test_invalid_graph_schema_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _settings(V52_GRAPH_SCHEMA_AVALANCHE="not-a-real-schema")


def test_get_graph_provider_for_chain_returns_none_when_unconfigured() -> None:
    assert get_graph_provider_for_chain(_settings(), "avalanche") is None


def test_get_graph_provider_for_chain_resolves_aliases() -> None:
    settings = _settings(V52_GRAPH_ENDPOINT_AVALANCHE="https://gw/avax")
    provider = get_graph_provider_for_chain(settings, "avax")
    assert provider is not None
    assert provider._endpoint == "https://gw/avax"


# ── get_chain_status ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chain_status_reports_unconfigured_with_actionable_warning() -> None:
    status = await get_chain_status(_settings(), "hsk")
    assert status.configured is False
    assert status.chain == "hsk"
    assert "V52_GRAPH_ENDPOINT_HSK" in status.warnings[0]


@pytest.mark.asyncio
@respx.mock
async def test_chain_status_returns_live_meta_when_configured() -> None:
    respx.post(GRAPH_URL).mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "_meta": {
                        "block": {"number": 100, "hash": "0xabc"},
                        "deployment": "Qm123",
                        "hasIndexingErrors": False,
                    }
                }
            },
        )
    )
    settings = _settings(V52_GRAPH_ENDPOINT_ETHEREUM=GRAPH_URL)
    status = await get_chain_status(settings, "ethereum")
    assert status.configured is True
    assert status.subgraph_schema == "uniswap_v3"
    assert status.meta.block_number == 100
    assert status.meta.has_indexing_errors is False


# ── run_pools_scan ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pools_scan_raises_503_when_chain_unconfigured() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await run_pools_scan(_settings(), "avalanche", limit=5)
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
@respx.mock
async def test_pools_scan_parses_uniswap_v3_pools() -> None:
    respx.post(GRAPH_URL).mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "_meta": {
                        "block": {"number": 1, "hash": "0x1"},
                        "deployment": "Qm",
                        "hasIndexingErrors": False,
                    },
                    "pools": [
                        {
                            "id": POOL_ADDRESS,
                            "token0": {"id": "0x" + "b" * 40, "symbol": "WETH", "decimals": 18},
                            "token1": {"id": "0x" + "c" * 40, "symbol": "USDC", "decimals": 6},
                            "feeTier": 3000,
                            "liquidity": "123456",
                            "totalValueLockedUSD": "1000000.5",
                            "volumeUSD": "500.25",
                            "txCount": "42",
                        }
                    ],
                }
            },
        )
    )
    settings = _settings(V52_GRAPH_ENDPOINT_ETHEREUM=GRAPH_URL)
    result = await run_pools_scan(settings, "ethereum", limit=5)

    assert result.chain == "ethereum"
    assert result.subgraph_schema == "uniswap_v3"
    assert len(result.pools) == 1
    pool = result.pools[0]
    assert pool.pool_id == POOL_ADDRESS
    assert pool.token0.symbol == "WETH"
    assert pool.fee_tier == 3000
    assert pool.total_value_locked_usd == "1000000.5"
    assert any("indexing" in w for w in result.warnings)


@pytest.mark.asyncio
@respx.mock
async def test_pools_scan_parses_uniswap_v2_pairs() -> None:
    respx.post(GRAPH_URL).mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "_meta": {
                        "block": {"number": 1, "hash": "0x1"},
                        "deployment": "Qm",
                        "hasIndexingErrors": False,
                    },
                    "pairs": [
                        {
                            "id": "0x" + "d" * 40,
                            "token0": {"id": "0x" + "e" * 40, "symbol": "AVAX", "decimals": 18},
                            "token1": {"id": "0x" + "f" * 40, "symbol": "USDT", "decimals": 6},
                            "reserve0": "1000",
                            "reserve1": "2000",
                            "reserveUSD": "3000.0",
                            "volumeUSD": "100.0",
                            "txCount": "10",
                        }
                    ],
                }
            },
        )
    )
    settings = _settings(
        V52_GRAPH_ENDPOINT_ETHEREUM=GRAPH_URL, V52_GRAPH_SCHEMA_ETHEREUM="uniswap_v2"
    )
    result = await run_pools_scan(settings, "ethereum", limit=5)

    assert result.subgraph_schema == "uniswap_v2"
    pool = result.pools[0]
    assert pool.reserve0 == "1000"
    assert pool.reserve1 == "2000"
    assert pool.total_value_locked_usd == "3000.0"


# ── run_pool_activity ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_pool_activity_parses_uniswap_v3_swaps() -> None:
    respx.post(GRAPH_URL).mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "_meta": {
                        "block": {"number": 5, "hash": "0x5"},
                        "deployment": "Qm",
                        "hasIndexingErrors": False,
                    },
                    "swaps": [
                        {
                            "id": "swap1",
                            "timestamp": 123,
                            "transaction": {"id": "0xtx"},
                            "sender": "0x" + "1" * 40,
                            "recipient": "0x" + "2" * 40,
                            "amount0": "-1.5",
                            "amount1": "2.5",
                            "amountUSD": "100.0",
                        }
                    ],
                }
            },
        )
    )
    settings = _settings(V52_GRAPH_ENDPOINT_ETHEREUM=GRAPH_URL)
    result = await run_pool_activity(settings, "ethereum", POOL_ADDRESS, limit=10)

    assert result.pool_id == POOL_ADDRESS
    assert len(result.swaps) == 1
    swap = result.swaps[0]
    assert swap.transaction_hash == "0xtx"
    assert swap.amount0 == "-1.5"
    assert any("Absence of swaps" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_pool_activity_raises_503_when_chain_unconfigured() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await run_pool_activity(_settings(), "hsk", POOL_ADDRESS, limit=10)
    assert exc_info.value.status_code == 503


# ── run_full_scan ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_full_scan_handles_mixed_chain_configuration() -> None:
    respx.post(GRAPH_URL).mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "_meta": {
                        "block": {"number": 1, "hash": "0x1"},
                        "deployment": "Qm",
                        "hasIndexingErrors": False,
                    },
                    "pools": [],
                }
            },
        )
    )
    settings = _settings(V52_GRAPH_ENDPOINT_ETHEREUM=GRAPH_URL)
    result = await run_full_scan(settings, ["ethereum", "avalanche"], pools_limit=5)

    by_chain = {r.chain: r for r in result.results}
    assert by_chain["ethereum"].status.configured is True
    assert by_chain["ethereum"].pools == []
    assert by_chain["avalanche"].status.configured is False
    assert by_chain["avalanche"].pools == []


# ── Public, free status endpoint (/v1/intel/defi/status) ─────────────────────


def test_defi_status_endpoint_lists_all_three_chains(client) -> None:
    app.dependency_overrides[get_settings] = lambda: _settings()
    try:
        response = client.get("/v1/intel/defi/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    chains = {c["chain"]: c for c in response.json()["chains"]}
    assert set(chains) == {"ethereum", "avalanche", "hsk"}
    assert chains["ethereum"]["configured"] is False
    assert chains["avalanche"]["configured"] is False
    assert chains["hsk"]["configured"] is False


# ── /v1/providers/status stays additive (existing fields untouched) ──────────


def test_providers_status_keeps_original_fields_and_adds_chain_breakdown(client) -> None:
    response = client.get("/v1/providers/status")
    assert response.status_code == 200
    the_graph = response.json()["data"]["the_graph"]
    assert "status" in the_graph
    assert "network" in the_graph
    assert set(the_graph["chains"]) == {"ethereum", "avalanche", "hsk"}


# ── Agent capabilities gains an additive `defi_intel` field ──────────────────


def test_agent_capabilities_reports_defi_intel_pricing(client) -> None:
    response = client.get("/v1/agent/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["endpoint"] == "/v1/agent/investigations/wallet-flow"  # unchanged
    defi_intel = body["defi_intel"]
    assert defi_intel["pools_endpoint"] == "/v1/agent/intel/defi/pools"
    assert defi_intel["pool_activity_endpoint"] == "/v1/agent/intel/defi/pool-activity"
    assert defi_intel["scan_endpoint"] == "/v1/agent/intel/defi/scan"


# ── x402-paid DeFi endpoints fail closed when x402 is disabled ───────────────


def _fresh_agent_app(settings: Settings) -> FastAPI:
    """Router-only app (no payment middleware mounted) — isolates the router's
    own `_require_x402` guard from the real app's process-wide x402 state."""
    fresh = FastAPI()
    fresh.include_router(agent_module.router)
    fresh.dependency_overrides[get_settings] = lambda: settings
    return fresh


def test_agent_defi_endpoints_fail_closed_when_x402_disabled() -> None:
    settings = _settings(V52_X402_ENABLED=False)
    with TestClient(_fresh_agent_app(settings)) as c:
        pools = c.post("/v1/agent/intel/defi/pools", json={"chain": "ethereum"})
        activity = c.post(
            "/v1/agent/intel/defi/pool-activity",
            json={"chain": "ethereum", "pool_address": POOL_ADDRESS},
        )
        scan = c.post("/v1/agent/intel/defi/scan", json={})

    for response in (pools, activity, scan):
        assert response.status_code == 503
        assert "x402 agent channel" in response.json()["detail"]


@respx.mock
def test_agent_defi_pools_returns_data_when_x402_ready_and_graph_configured() -> None:
    respx.post(GRAPH_URL).mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "_meta": {
                        "block": {"number": 1, "hash": "0x1"},
                        "deployment": "Qm",
                        "hasIndexingErrors": False,
                    },
                    "pools": [],
                }
            },
        )
    )
    settings = _settings(
        V52_GRAPH_ENDPOINT_ETHEREUM=GRAPH_URL,
        V52_X402_ENABLED=True,
        V52_X402_FACILITATOR_URL="https://relayer.example",
        V52_X402_FACILITATOR_API_KEY="test-only-token",
        V52_X402_PAY_TO="0x" + "1" * 40,
    )
    with TestClient(_fresh_agent_app(settings)) as c:
        response = c.post(
            "/v1/agent/intel/defi/pools", json={"chain": "ethereum", "limit": 5}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["channel"] == "AGENT_X402"
    assert body["result"]["chain"] == "ethereum"


# ── x402 route registration carries the right per-endpoint price ─────────────


def test_x402_routes_register_defi_intel_endpoints_with_tiered_prices() -> None:
    x402_app = FastAPI()
    settings = Settings(
        V52_X402_ENABLED=True,
        V52_X402_FACILITATOR_URL="https://relayer.example",
        V52_X402_FACILITATOR_API_KEY="test-only-token",
        V52_X402_PAY_TO="0x" + "1" * 40,
        V52_X402_DEFI_POOLS_PRICE="400",
        V52_X402_DEFI_POOL_ACTIVITY_PRICE="900",
        V52_X402_DEFI_SCAN_PRICE="2500",
    )
    configure_x402(x402_app, settings)

    payment_middleware = next(
        m for m in x402_app.user_middleware if m.cls.__name__ == "PaymentMiddlewareASGI"
    )
    routes = payment_middleware.kwargs["routes"]

    assert routes["POST /v1/agent/intel/defi/pools"].accepts[0].price["amount"] == "400"
    assert routes["POST /v1/agent/intel/defi/pool-activity"].accepts[0].price["amount"] == "900"
    assert routes["POST /v1/agent/intel/defi/scan"].accepts[0].price["amount"] == "2500"
    # Existing route keeps its own independent price.
    assert routes["POST /v1/agent/investigations/wallet-flow"].accepts[0].price["amount"] == (
        settings.v52_x402_wallet_flow_price
    )
