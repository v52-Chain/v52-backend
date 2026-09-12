"""Wallet flow API tests. Live credentials are never required."""

from __future__ import annotations

import json

import respx
from eth_account import Account
from eth_account.messages import encode_defunct
from httpx import Request, Response

from app.config import Settings, get_settings
from app.main import app

ALCHEMY_URL = "https://eth-mainnet.g.alchemy.com/v2/test-secret"
WALLET = "0x" + "a" * 40
SENDER = "0x" + "b" * 40
RECIPIENT = "0x" + "c" * 40


def _settings() -> Settings:
    return Settings(
        V52_ENV="development",
        V52_ALCHEMY_ETH_RPC_URL=ALCHEMY_URL,
        V52_DATA_DIR="./test-evidence-vault",
    )


def _unconfigured_settings() -> Settings:
    return Settings(
        _env_file=None,
        V52_ENV="development",
        ALCHEMY_API_KEY="",
        V52_RPC_URL="",
        V52_ALCHEMY_ETH_RPC_URL="",
        V52_GRAPH_ENDPOINT="",
    )


def _web_headers(client) -> dict[str, str]:
    account = Account.create()
    challenge = client.post(
        "/v1/auth/wallet/challenge",
        json={"address": account.address, "chain_id": 1},
    ).json()
    signature = account.sign_message(
        encode_defunct(text=challenge["message"])
    ).signature.to_0x_hex()
    session = client.post(
        "/v1/auth/wallet/verify",
        json={
            "nonce": challenge["nonce"],
            "message": challenge["message"],
            "signature": signature,
        },
    ).json()
    return {"Authorization": f"Bearer {session['access_token']}"}


def test_wallet_flow_rejects_invalid_address(client) -> None:
    response = client.post(
        "/v1/web/investigations/wallet-flow",
        headers=_web_headers(client),
        json={"target_address": "not-a-wallet"},
    )
    assert response.status_code == 422


def test_wallet_flow_requires_alchemy(client) -> None:
    app.dependency_overrides[get_settings] = _unconfigured_settings
    try:
        response = client.post(
            "/v1/web/investigations/wallet-flow",
            headers=_web_headers(client),
            json={"target_address": WALLET},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert "V52_ALCHEMY_ETH_RPC_URL" in response.json()["detail"]


def test_wallet_flow_rejects_inverted_date_window(client) -> None:
    app.dependency_overrides[get_settings] = _settings
    try:
        response = client.post(
            "/v1/web/investigations/wallet-flow",
            headers=_web_headers(client),
            json={
                "target_address": WALLET,
                "from_date": "2026-09-12",
                "to_date": "2026-09-01",
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert "from_date" in str(response.json()["detail"])


@respx.mock
def test_wallet_flow_returns_normalized_directions(client) -> None:
    def responder(request: Request) -> Response:
        body = json.loads(request.content)
        params = body["params"][0]
        incoming = "toAddress" in params
        transfer = {
            "uniqueId": "0xhash:log:1" if incoming else "0xhash:log:2",
            "hash": "0x" + ("1" if incoming else "2") * 64,
            "blockNum": "0x10",
            "from": SENDER if incoming else WALLET,
            "to": WALLET if incoming else RECIPIENT,
            "value": 1.25 if incoming else 0.5,
            "asset": "ETH" if incoming else "USDC",
            "category": "external" if incoming else "erc20",
            "rawContract": {"address": None if incoming else "0x" + "d" * 40},
            "metadata": {"blockTimestamp": "2026-09-12T12:00:00Z"},
        }
        return Response(
            200,
            json={"jsonrpc": "2.0", "id": body["id"], "result": {"transfers": [transfer]}},
        )

    respx.post(ALCHEMY_URL).mock(side_effect=responder)
    app.dependency_overrides[get_settings] = _settings
    try:
        response = client.post(
            "/v1/web/investigations/wallet-flow",
            headers=_web_headers(client),
            json={"target_address": WALLET, "limit": 10},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()["result"]
    assert data["address"] == WALLET
    assert data["incoming"][0]["direction"] == "IN"
    assert data["incoming"][0]["counterparty"] == SENDER
    assert data["outgoing"][0]["direction"] == "OUT"
    assert data["outgoing"][0]["counterparty"] == RECIPIENT
    assert data["source"]["method"] == "alchemy_getAssetTransfers"
    assert data["limits"]["requested_per_direction"] == 10


@respx.mock
def test_wallet_flow_filters_by_date(client) -> None:
    def responder(request: Request) -> Response:
        body = json.loads(request.content)
        params = body["params"][0]
        incoming = "toAddress" in params
        transfers = [
            {
                "uniqueId": f"in-range:{incoming}",
                "hash": "0x" + "3" * 64,
                "blockNum": "0x20",
                "from": SENDER if incoming else WALLET,
                "to": WALLET if incoming else RECIPIENT,
                "value": 2,
                "asset": "ETH",
                "category": "external",
                "metadata": {"blockTimestamp": "2026-08-15T12:00:00Z"},
            },
            {
                "uniqueId": f"too-old:{incoming}",
                "hash": "0x" + "4" * 64,
                "blockNum": "0x10",
                "from": SENDER if incoming else WALLET,
                "to": WALLET if incoming else RECIPIENT,
                "value": 4,
                "asset": "ETH",
                "category": "external",
                "metadata": {"blockTimestamp": "2026-07-01T12:00:00Z"},
            },
        ]
        return Response(
            200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"transfers": transfers}}
        )

    respx.post(ALCHEMY_URL).mock(side_effect=responder)
    app.dependency_overrides[get_settings] = _settings
    try:
        response = client.post(
            "/v1/web/investigations/wallet-flow",
            headers=_web_headers(client),
            json={
                "target_address": WALLET,
                "limit": 10,
                "from_date": "2026-08-01",
                "to_date": "2026-08-31",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()["result"]
    assert len(data["incoming"]) == 1
    assert len(data["outgoing"]) == 1
    assert data["limits"]["from_date"] == "2026-08-01"
    assert data["limits"]["to_date"] == "2026-08-31"
    assert data["limits"]["max_pages_per_direction"] == 10


def test_legacy_public_wallet_flow_is_not_exposed(client) -> None:
    response = client.get(f"/v1/wallets/1/{WALLET}/flow")
    assert response.status_code == 404
