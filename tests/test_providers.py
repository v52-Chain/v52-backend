"""
Tests for EthereumRpcProvider and TheGraphProvider using httpx mocks (respx).

These tests run WITHOUT live network access.
They verify: success, timeout, HTTP error, RPC error, partial response and
secret URL redaction in error messages.
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response, TimeoutException

from app.providers.base import ProviderError, redact
from app.providers.ethereum_rpc import EthereumRpcProvider
from app.providers.rpc import AlchemyRpcProvider, RpcErrorCode
from app.providers.the_graph import TheGraphProvider

RPC_URL = "https://rpc.example.com/v3/testkey"
GRAPH_URL = "https://gateway.thegraph.com/api/testkey/subgraphs/id/abc123"
TX_HASH = "0x" + "a" * 64


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


def test_redact_removes_alchemy_key_in_url() -> None:
    url = "https://eth-mainnet.g.alchemy.com/v2/alch_exampleSecretKey123456"
    result = redact(url)
    assert "exampleSecretKey" not in result
    assert "[REDACTED]" in result


def test_redact_is_safe_on_clean_text() -> None:
    text = "Transaction 0xabc completed successfully."
    assert redact(text) == text


# ── EthereumRpcProvider ───────────────────────────────────────────────────────

def test_rpc_provider_requires_url() -> None:
    with pytest.raises(ProviderError, match="V52_RPC_URL"):
        EthereumRpcProvider(rpc_url="")


@respx.mock
@pytest.mark.asyncio
async def test_rpc_get_transaction_success() -> None:
    tx_result = {"hash": TX_HASH, "blockNumber": "0x1"}
    respx.post(RPC_URL).mock(
        return_value=Response(200, json={"jsonrpc": "2.0", "id": 1, "result": tx_result})
    )

    provider = EthereumRpcProvider(rpc_url=RPC_URL)
    result = await provider.get_transaction(TX_HASH)
    assert result == tx_result


@respx.mock
@pytest.mark.asyncio
async def test_rpc_get_transaction_returns_none_for_unknown() -> None:
    respx.post(RPC_URL).mock(
        return_value=Response(200, json={"jsonrpc": "2.0", "id": 1, "result": None})
    )

    provider = EthereumRpcProvider(rpc_url=RPC_URL)
    result = await provider.get_transaction(TX_HASH)
    assert result is None


@respx.mock
@pytest.mark.asyncio
async def test_rpc_timeout_raises_provider_error() -> None:
    respx.post(RPC_URL).mock(side_effect=TimeoutException("timeout"))

    provider = EthereumRpcProvider(rpc_url=RPC_URL)
    with pytest.raises(ProviderError, match="timed out"):
        await provider.get_transaction(TX_HASH)

    from app.models.evidence import ProviderStatus
    assert provider.status == ProviderStatus.TIMEOUT


@respx.mock
@pytest.mark.asyncio
async def test_rpc_error_response_raises_provider_error() -> None:
    respx.post(RPC_URL).mock(
        return_value=Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32602, "message": "Invalid params"},
            },
        )
    )

    provider = EthereumRpcProvider(rpc_url=RPC_URL)
    with pytest.raises(ProviderError, match="Invalid params"):
        await provider.get_transaction(TX_HASH)


@respx.mock
@pytest.mark.asyncio
async def test_rpc_error_does_not_contain_secret_url() -> None:
    """Errors from the RPC provider must never expose the secret API key in the URL."""
    respx.post(RPC_URL).mock(side_effect=TimeoutException("timeout"))

    provider = EthereumRpcProvider(rpc_url=RPC_URL)
    try:
        await provider.get_transaction(TX_HASH)
    except ProviderError as exc:
        assert "testkey" not in str(exc), "API key found in error message!"


# ── TheGraphProvider ──────────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_rpc_validate_chain_id_success() -> None:
    respx.post(RPC_URL).mock(
        return_value=Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x1"})
    )

    provider = EthereumRpcProvider(rpc_url=RPC_URL)
    assert await provider.validate_chain_id() == 1


@respx.mock
@pytest.mark.asyncio
async def test_rpc_validate_chain_id_mismatch() -> None:
    respx.post(RPC_URL).mock(
        return_value=Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0xa86a"})
    )

    provider = EthereumRpcProvider(rpc_url=RPC_URL, expected_chain_id=1)
    with pytest.raises(ProviderError) as exc_info:
        await provider.validate_chain_id()

    assert exc_info.value.code == RpcErrorCode.CHAIN_MISMATCH
    assert "testkey" not in str(exc_info.value)


@respx.mock
@pytest.mark.asyncio
async def test_rpc_rate_limit_is_typed() -> None:
    respx.post(RPC_URL).mock(return_value=Response(429, json={"error": "rate limited"}))

    provider = AlchemyRpcProvider(
        RPC_URL,
        expected_chain_id=1,
        network="ethereum-mainnet",
        timeout_seconds=1,
        max_retries=0,
    )
    with pytest.raises(ProviderError) as exc_info:
        await provider.get_transaction(TX_HASH)

    assert exc_info.value.code == RpcErrorCode.PROVIDER_RATE_LIMIT
    assert exc_info.value.retryable is True


@respx.mock
@pytest.mark.asyncio
async def test_rpc_malformed_json_is_typed() -> None:
    respx.post(RPC_URL).mock(return_value=Response(200, content=b"not-json"))

    provider = EthereumRpcProvider(rpc_url=RPC_URL)
    with pytest.raises(ProviderError) as exc_info:
        await provider.get_transaction(TX_HASH)

    assert exc_info.value.code == RpcErrorCode.PROVIDER_INVALID_RESPONSE


def test_graph_provider_requires_endpoint() -> None:
    with pytest.raises(ProviderError, match="V52_GRAPH_ENDPOINT"):
        TheGraphProvider(endpoint="")


@respx.mock
@pytest.mark.asyncio
async def test_graph_query_success_with_meta() -> None:
    gql_response = {
        "data": {
            "_meta": {
                "block": {"number": 12345, "hash": "0xblk"},
                "deployment": "Qm...",
                "hasIndexingErrors": False,
            },
            "swaps": [],
        }
    }
    respx.post(GRAPH_URL).mock(return_value=Response(200, json=gql_response))

    provider = TheGraphProvider(endpoint=GRAPH_URL)
    result = await provider.query(query="{ _meta { block { number } } }", variables={})

    assert result["has_errors"] is False
    assert result["meta"]["block_number"] == 12345
    assert result["meta"]["has_indexing_errors"] is False
    assert len(result["warnings"]) == 0


@respx.mock
@pytest.mark.asyncio
async def test_graph_query_captures_indexing_errors() -> None:
    gql_response = {
        "data": {
            "_meta": {
                "block": {"number": 12345, "hash": "0xblk"},
                "deployment": "Qm...",
                "hasIndexingErrors": True,
            },
            "swaps": [],
        }
    }
    respx.post(GRAPH_URL).mock(return_value=Response(200, json=gql_response))

    provider = TheGraphProvider(endpoint=GRAPH_URL)
    result = await provider.query(query="{ _meta { block { number } } }", variables={})

    assert result["meta"]["has_indexing_errors"] is True
    assert any("hasIndexingErrors" in w for w in result["warnings"])


@respx.mock
@pytest.mark.asyncio
async def test_graph_timeout_raises_provider_error() -> None:
    respx.post(GRAPH_URL).mock(side_effect=TimeoutException("timeout"))

    provider = TheGraphProvider(endpoint=GRAPH_URL)
    with pytest.raises(ProviderError, match="timed out"):
        await provider.query(query="{ swaps { id } }", variables={})


@respx.mock
@pytest.mark.asyncio
async def test_graph_partial_response_is_degraded() -> None:
    """GraphQL errors in the response produce warnings but don't raise exceptions."""
    gql_response = {
        "data": {"swaps": []},
        "errors": [{"message": "indexing error on block 999"}],
    }
    respx.post(GRAPH_URL).mock(return_value=Response(200, json=gql_response))

    provider = TheGraphProvider(endpoint=GRAPH_URL)
    result = await provider.query(query="{ swaps { id } }", variables={})

    assert result["has_errors"] is True
    assert any("Graph error" in w for w in result["warnings"])


def test_graph_endpoint_interpolates_api_key() -> None:
    template = "https://gateway.thegraph.com/api/{api_key}/subgraphs/id/5zvR82"
    provider = TheGraphProvider(endpoint=template, api_key="my-secret-key")
    assert provider._endpoint == "https://gateway.thegraph.com/api/my-secret-key/subgraphs/id/5zvR82"
    assert provider._build_headers()["Authorization"] == "Bearer my-secret-key"

    # When no key provided, removes placeholder cleanly
    provider_no_key = TheGraphProvider(endpoint=template, api_key="")
    assert provider_no_key._endpoint == "https://gateway.thegraph.com/api/subgraphs/id/5zvR82"
    assert "Authorization" not in provider_no_key._build_headers()
