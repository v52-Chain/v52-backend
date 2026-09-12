"""
Tests for EthereumRpcProvider and TheGraphProvider using REAL live network calls.

No mocks are used. These tests verify:
  - Real JSON-RPC calls against Ethereum Mainnet (transaction, receipt, block, logs).
  - Real GraphQL queries against The Graph Decentralized Gateway (Uniswap V3 subgraph).
  - Real error handling (unmined tx, invalid RPC method, invalid GraphQL field).
  - Real network timeout behavior and secret redaction.
"""

from __future__ import annotations

import os

import pytest

from app.evidence.acquisition import _UNISWAP_V3_SWAP_QUERY
from app.models.evidence import ProviderStatus
from app.providers.base import ProviderError, redact
from app.providers.ethereum_rpc import EthereumRpcProvider
from app.providers.the_graph import TheGraphProvider

# os.environ.get(key, default) only falls back when the key is absent — .env
# declares these even when blank, so an empty value must be handled with `or`.
REAL_RPC_URL = os.environ.get("V52_RPC_URL") or "https://eth.drpc.org"
REAL_GRAPH_ENDPOINT = os.environ.get("V52_GRAPH_ENDPOINT") or (
    "https://gateway.thegraph.com/api/{api_key}/subgraphs/id/5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"
)
# No hardcoded fallback: this is a secret and must never live in source. Tests
# that need it are skipped automatically when it isn't configured.
REAL_GRAPH_API_KEY = os.environ.get("V52_GRAPH_API_KEY", "")

requires_graph_api_key = pytest.mark.skipif(
    not REAL_GRAPH_API_KEY,
    reason="V52_GRAPH_API_KEY not configured; set it in .env to run live Graph gateway tests",
)

# Known mined Uniswap V3 swap transaction on Ethereum Mainnet:
REAL_TX_HASH = "0xfa98e7528b5855e46e9bf9cbf9040bc3cfb114ca0c50691f392f1816516e000e"
NON_EXISTENT_TX_HASH = "0x0000000000000000000000000000000000000000000000000000000000000001"


# ── Secret redaction utility ──────────────────────────────────────────────────

def test_redact_removes_bearer_token() -> None:
    text = "Authorization: Bearer supersecrettoken123"
    result = redact(text)
    assert "supersecrettoken123" not in result
    assert "[REDACTED]" in result


def test_redact_removes_api_key_in_url() -> None:
    url = "https://mainnet.infura.io/v3/0123456789abcdef0123456789abcdef"
    result = redact(url)
    assert "0123456789abcdef" not in result


def test_redact_is_safe_on_clean_text() -> None:
    text = "Transaction 0xabc completed successfully."
    assert redact(text) == text


# ── EthereumRpcProvider (Real Network Calls) ──────────────────────────────────

def test_rpc_provider_requires_url() -> None:
    with pytest.raises(ProviderError, match="V52_RPC_URL"):
        EthereumRpcProvider(rpc_url="")


@pytest.mark.asyncio
async def test_rpc_get_transaction_success() -> None:
    """Fetches a real transaction from Ethereum Mainnet via JSON-RPC."""
    provider = EthereumRpcProvider(rpc_url=REAL_RPC_URL)
    tx = await provider.get_transaction(REAL_TX_HASH)

    assert tx is not None
    assert tx["hash"].lower() == REAL_TX_HASH.lower()
    assert tx["blockNumber"] is not None
    assert tx["from"].startswith("0x")
    assert tx["to"].startswith("0x")
    assert provider.status == ProviderStatus.OK


@pytest.mark.asyncio
async def test_rpc_get_transaction_returns_none_for_unknown() -> None:
    """A real Ethereum node returns None for an unknown/unmined transaction."""
    provider = EthereumRpcProvider(rpc_url=REAL_RPC_URL)
    tx = await provider.get_transaction(NON_EXISTENT_TX_HASH)
    assert tx is None


@pytest.mark.asyncio
async def test_rpc_get_receipt_and_block() -> None:
    """Fetches real transaction receipt and block from Ethereum Mainnet."""
    provider = EthereumRpcProvider(rpc_url=REAL_RPC_URL)
    receipt = await provider.get_receipt(REAL_TX_HASH)

    assert receipt is not None
    assert receipt["status"] == "0x1"
    assert receipt["blockNumber"] is not None
    assert len(receipt.get("logs", [])) > 0

    block = await provider.get_block(receipt["blockNumber"])
    assert block is not None
    assert block["number"] == receipt["blockNumber"]
    assert block["hash"].startswith("0x")


@pytest.mark.asyncio
async def test_rpc_acquire_full_l0_evidence() -> None:
    """Full L0 evidence acquisition (tx, receipt, block, logs) from real chain."""
    provider = EthereumRpcProvider(rpc_url=REAL_RPC_URL)
    evidence = await provider.acquire(tx_hash=REAL_TX_HASH)

    assert evidence["transaction"] is not None
    assert evidence["receipt"] is not None
    assert evidence["block"] is not None
    assert len(evidence["logs"]) > 0
    assert len(evidence["warnings"]) == 0
    assert provider.status == ProviderStatus.OK


@pytest.mark.asyncio
async def test_rpc_error_response_raises_provider_error() -> None:
    """Calling an invalid method on a real Ethereum node raises ProviderError.

    Real nodes disagree on how they reject an unknown method: some return
    HTTP 200 with a JSON-RPC `error` object, others return an HTTP error
    status directly. Both are mapped to ProviderError by the provider.
    """
    provider = EthereumRpcProvider(rpc_url=REAL_RPC_URL)
    with pytest.raises(ProviderError, match=r"RPC (HTTP )?error"):
        await provider._call("eth_nonExistentMethod999", [])
    assert provider.status == ProviderStatus.FAILED


@pytest.mark.asyncio
async def test_rpc_timeout_raises_provider_error() -> None:
    """Connecting to a non-routable address times out and raises ProviderError."""
    provider = EthereumRpcProvider(rpc_url="http://10.255.255.1:81", timeout_seconds=0.2)
    with pytest.raises(ProviderError, match="timed out"):
        await provider.get_transaction(REAL_TX_HASH)
    assert provider.status == ProviderStatus.TIMEOUT


@pytest.mark.asyncio
async def test_rpc_error_does_not_contain_secret_url() -> None:
    """Network errors must redact any API key embedded in the URL path."""
    secret_url = "http://10.255.255.1:81/v3/mysecretkey12345"
    provider = EthereumRpcProvider(rpc_url=secret_url, timeout_seconds=0.2)
    try:
        await provider.get_transaction(REAL_TX_HASH)
    except ProviderError as exc:
        assert "mysecretkey12345" not in str(exc), "Secret API key found in error message!"


# ── TheGraphProvider (Real Network Calls) ─────────────────────────────────────

def test_graph_provider_requires_endpoint() -> None:
    with pytest.raises(ProviderError, match="V52_GRAPH_ENDPOINT"):
        TheGraphProvider(endpoint="")


def test_graph_endpoint_interpolates_api_key() -> None:
    template = "https://gateway.thegraph.com/api/{api_key}/subgraphs/id/5zvR82"
    provider = TheGraphProvider(endpoint=template, api_key="my-secret-key")
    assert provider._endpoint == "https://gateway.thegraph.com/api/my-secret-key/subgraphs/id/5zvR82"
    assert provider._build_headers()["Authorization"] == "Bearer my-secret-key"

    # When no key provided, removes placeholder cleanly
    provider_no_key = TheGraphProvider(endpoint=template, api_key="")
    assert provider_no_key._endpoint == "https://gateway.thegraph.com/api/subgraphs/id/5zvR82"
    assert "Authorization" not in provider_no_key._build_headers()


@requires_graph_api_key
@pytest.mark.asyncio
async def test_graph_query_success_with_meta() -> None:
    """Queries real Uniswap V3 subgraph metadata from The Graph Gateway."""
    provider = TheGraphProvider(endpoint=REAL_GRAPH_ENDPOINT, api_key=REAL_GRAPH_API_KEY)
    result = await provider.query(
        query="query { _meta { block { number hash } deployment hasIndexingErrors } }"
    )

    assert result["has_errors"] is False
    assert result["meta"]["block_number"] > 0
    assert result["meta"]["block_hash"].startswith("0x")
    assert result["meta"]["deployment"] == "QmTZ8ejXJxRo7vDBS4uwqBeGoxLSWbhaA7oXa1RvxunLy7"
    assert result["meta"]["has_indexing_errors"] is False
    assert len(result["warnings"]) == 0
    assert provider.status == ProviderStatus.OK


@requires_graph_api_key
@pytest.mark.asyncio
async def test_graph_query_real_swap_event() -> None:
    """Executes the real Uniswap V3 swap query against The Graph Gateway."""
    provider = TheGraphProvider(endpoint=REAL_GRAPH_ENDPOINT, api_key=REAL_GRAPH_API_KEY)
    result = await provider.query(
        query=_UNISWAP_V3_SWAP_QUERY,
        variables={"txHash": REAL_TX_HASH},
    )

    assert result["has_errors"] is False
    swaps = result["response"]["data"]["swaps"]
    assert len(swaps) > 0

    swap = swaps[0]
    assert swap["id"].startswith(REAL_TX_HASH.lower())
    assert "amount0" in swap
    assert "amount1" in swap
    assert "amountUSD" in swap
    assert "pool" in swap
    assert swap["pool"]["token0"]["symbol"] is not None
    assert swap["pool"]["token1"]["symbol"] is not None
    assert provider.status == ProviderStatus.OK


@requires_graph_api_key
@pytest.mark.asyncio
async def test_graph_graphql_error_marks_degraded() -> None:
    """Sending an invalid GraphQL field to the gateway returns errors and sets DEGRADED."""
    provider = TheGraphProvider(endpoint=REAL_GRAPH_ENDPOINT, api_key=REAL_GRAPH_API_KEY)
    result = await provider.query(query="query { nonExistentField999 }")

    assert result["has_errors"] is True
    assert any("Graph error" in w for w in result["warnings"])
    assert provider.status == ProviderStatus.DEGRADED


@pytest.mark.asyncio
async def test_graph_timeout_raises_provider_error() -> None:
    """Connecting to a non-routable address times out and raises ProviderError."""
    provider = TheGraphProvider(endpoint="http://10.255.255.1:81", timeout_seconds=0.2)
    with pytest.raises(ProviderError, match="timed out"):
        await provider.query(query="{ swaps { id } }")
    assert provider.status == ProviderStatus.TIMEOUT
