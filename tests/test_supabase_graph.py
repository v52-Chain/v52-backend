"""Supabase graph-persistence integration. Never blocks or breaks acquisition.

Covers app/storage/supabase_graph.py directly (the RPC call itself) and its
fire-and-forget wiring in app/api/wallet_flow.py.acquire_wallet_flow.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
import respx
from httpx import Request, Response

from app.api.wallet_flow import _background_tasks, acquire_wallet_flow
from app.config import Settings
from app.models.wallet_flow import WalletFlowLimits, WalletFlowResponse
from app.storage.supabase_graph import ingest_wallet_flow

SUPABASE_URL = "https://example.supabase.co"
RPC_URL = f"{SUPABASE_URL}/rest/v1/rpc/graph_ingest_wallet_flow"
SERVICE_ROLE_KEY = "test-service-role-key"  # not a real secret; test fixture only
WALLET = "0x" + "a" * 40
ALCHEMY_URL = "https://eth-mainnet.g.alchemy.com/v2/test-secret"


def _flow_response() -> WalletFlowResponse:
    return WalletFlowResponse(
        address=WALLET,
        acquired_at="2026-09-13T12:00:00Z",
        incoming=[],
        outgoing=[],
        limits=WalletFlowLimits(
            requested_per_direction=25,
            returned_incoming=0,
            returned_outgoing=0,
            truncated=False,
        ),
        warnings=[],
    )


def _unconfigured() -> Settings:
    return Settings(_env_file=None, V52_ENV="development")


def _configured() -> Settings:
    return Settings(
        _env_file=None,
        V52_ENV="development",
        V52_SUPABASE_ENABLED=True,
        V52_SUPABASE_URL=SUPABASE_URL,
        V52_SUPABASE_SERVICE_ROLE_KEY=SERVICE_ROLE_KEY,
    )


def test_supabase_not_configured_by_default() -> None:
    settings = _unconfigured()
    assert settings.supabase_configured is False


def test_enabled_without_url_or_key_is_not_configured() -> None:
    settings = Settings(_env_file=None, V52_ENV="development", V52_SUPABASE_ENABLED=True)
    assert settings.supabase_configured is False


@respx.mock
async def test_ingest_is_a_noop_when_not_configured() -> None:
    # No route registered: respx raises if the code attempts any HTTP call.
    await ingest_wallet_flow(
        result=_flow_response(),
        channel="WEB",
        settings=_unconfigured(),
    )


@respx.mock
async def test_ingest_posts_expected_rpc_payload() -> None:
    def responder(request: Request) -> Response:
        return Response(200, json="11111111-1111-1111-1111-111111111111")

    route = respx.post(RPC_URL).mock(side_effect=responder)
    settings = _configured()

    await ingest_wallet_flow(
        result=_flow_response(),
        channel="AGENT_X402",
        settings=settings,
        actor_wallet=None,
        external_request_id="agent_test123",
    )

    assert route.called
    sent = route.calls.last.request
    assert sent.headers["apikey"] == SERVICE_ROLE_KEY
    assert sent.headers["authorization"] == f"Bearer {SERVICE_ROLE_KEY}"
    import json as _json

    payload = _json.loads(sent.content)
    assert payload["p_channel"] == "AGENT_X402"
    assert payload["p_external_request_id"] == "agent_test123"
    assert payload["p_result"]["address"] == WALLET


@respx.mock
async def test_ingest_swallows_http_error_status(caplog: pytest.LogCaptureFixture) -> None:
    respx.post(RPC_URL).mock(return_value=Response(500, json={"message": "boom"}))
    await ingest_wallet_flow(result=_flow_response(), channel="WEB", settings=_configured())
    assert "Supabase graph ingestion failed" in caplog.text


@respx.mock
async def test_ingest_swallows_network_error(caplog: pytest.LogCaptureFixture) -> None:
    respx.post(RPC_URL).mock(side_effect=httpx.ConnectError("refused"))
    await ingest_wallet_flow(result=_flow_response(), channel="WEB", settings=_configured())
    assert "Supabase graph ingestion request failed" in caplog.text


@respx.mock
async def test_acquire_wallet_flow_does_not_schedule_task_when_unconfigured() -> None:
    respx.post(ALCHEMY_URL).mock(
        return_value=Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"transfers": []}})
    )
    settings = Settings(
        _env_file=None,
        V52_ENV="development",
        V52_ALCHEMY_ETH_RPC_URL=ALCHEMY_URL,
    )
    before = len(_background_tasks)
    await acquire_wallet_flow(
        chain_id=1,
        address=WALLET,
        limit=5,
        from_date=None,
        to_date=None,
        settings=settings,
        channel="WEB",
    )
    assert len(_background_tasks) == before


@respx.mock
async def test_acquire_wallet_flow_fires_supabase_ingestion_when_configured() -> None:
    respx.post(ALCHEMY_URL).mock(
        return_value=Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"transfers": []}})
    )
    rpc_route = respx.post(RPC_URL).mock(
        return_value=Response(200, json="11111111-1111-1111-1111-111111111111")
    )
    settings = Settings(
        _env_file=None,
        V52_ENV="development",
        V52_ALCHEMY_ETH_RPC_URL=ALCHEMY_URL,
        V52_SUPABASE_ENABLED=True,
        V52_SUPABASE_URL=SUPABASE_URL,
        V52_SUPABASE_SERVICE_ROLE_KEY=SERVICE_ROLE_KEY,
    )

    result = await acquire_wallet_flow(
        chain_id=1,
        address=WALLET,
        limit=5,
        from_date=None,
        to_date=None,
        settings=settings,
        channel="WEB",
        actor_wallet=WALLET,
    )
    # The request already succeeded before ingestion is awaited — proving the
    # HTTP response never depends on Supabase — so wait for it explicitly here
    # only to assert on it.
    pending = list(_background_tasks)
    if pending:
        await asyncio.gather(*pending)

    assert result.address == WALLET
    assert rpc_route.called
    payload = rpc_route.calls.last.request.content
    assert b'"p_channel":"WEB"' in payload or b'"p_channel": "WEB"' in payload
