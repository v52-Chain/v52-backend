"""Browser-wallet authentication and machine-channel contract tests."""

from __future__ import annotations

from eth_account import Account
from eth_account.messages import encode_defunct

from app.config import Settings
from app.main import app
from app.payments.x402 import configure_x402
from app.security.wallet_sessions import WalletSessionStore, get_wallet_sessions


def _authenticated_session(client) -> tuple[str, str]:
    account = Account.create()
    store = WalletSessionStore()
    app.dependency_overrides[get_wallet_sessions] = lambda: store
    challenge_response = client.post(
        "/v1/auth/wallet/challenge",
        json={"address": account.address, "chain_id": 1},
    )
    assert challenge_response.status_code == 200
    challenge = challenge_response.json()
    signature = account.sign_message(
        encode_defunct(text=challenge["message"])
    ).signature.to_0x_hex()
    verify_response = client.post(
        "/v1/auth/wallet/verify",
        json={
            "nonce": challenge["nonce"],
            "message": challenge["message"],
            "signature": signature,
        },
    )
    assert verify_response.status_code == 200
    return verify_response.json()["access_token"], account.address.lower()


def test_wallet_challenge_creates_verified_browser_session(client) -> None:
    try:
        token, address = _authenticated_session(client)
        response = client.get(
            "/v1/auth/wallet/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.pop(get_wallet_sessions, None)

    assert response.status_code == 200
    assert response.json()["channel"] == "WEB"
    assert response.json()["address"] == address


def test_wallet_challenge_is_single_use(client) -> None:
    account = Account.create()
    store = WalletSessionStore()
    app.dependency_overrides[get_wallet_sessions] = lambda: store
    try:
        challenge = client.post(
            "/v1/auth/wallet/challenge",
            json={"address": account.address, "chain_id": 1},
        ).json()
        signature = account.sign_message(
            encode_defunct(text=challenge["message"])
        ).signature.to_0x_hex()
        payload = {**challenge, "signature": signature}
        payload.pop("expires_at")
        first = client.post("/v1/auth/wallet/verify", json=payload)
        replay = client.post("/v1/auth/wallet/verify", json=payload)
    finally:
        app.dependency_overrides.pop(get_wallet_sessions, None)

    assert first.status_code == 200
    assert replay.status_code == 401


def test_web_investigation_requires_verified_wallet(client) -> None:
    response = client.post(
        "/v1/web/investigations/wallet-flow",
        json={"target_address": "0x" + "a" * 40},
    )
    assert response.status_code == 401


def test_agent_capabilities_fail_closed_when_x402_is_disabled(client) -> None:
    capabilities = client.get("/v1/agent/capabilities")
    paid_route = client.post(
        "/v1/agent/investigations/wallet-flow",
        json={"target_address": "0x" + "a" * 40},
    )

    assert capabilities.status_code == 200
    assert capabilities.json()["ready"] is False
    assert capabilities.json()["automatic_payment_owner"] == "MCP_CLIENT"
    assert paid_route.status_code == 503


def test_web_capabilities_fail_closed_when_x402_is_disabled(client) -> None:
    capabilities = client.get("/v1/web/capabilities")

    assert capabilities.status_code == 200
    body = capabilities.json()
    assert body["ready"] is False
    assert body["channel"] == "WEB_X402"
    assert body["endpoint"] == "/v1/web/investigations/wallet-flow"
    assert body["automatic_payment_owner"] == "CONNECTED_WALLET"
    assert body["authentication"] == "SIGNED_CHALLENGE"


def test_x402_middleware_can_be_configured_without_contacting_facilitator() -> None:
    from fastapi import FastAPI

    x402_app = FastAPI()
    settings = Settings(
        V52_X402_ENABLED=True,
        V52_X402_FACILITATOR_URL="https://relayer.example/api/v1/plugins/x402/call",
        V52_X402_FACILITATOR_API_KEY="test-only-relayer-token",
        V52_X402_PAY_TO="0x" + "1" * 40,
    )
    configure_x402(x402_app, settings)

    assert any(
        middleware.cls.__name__ == "PaymentMiddlewareASGI"
        for middleware in x402_app.user_middleware
    )


def test_x402_routes_register_the_browser_wallet_flow_endpoint() -> None:
    """The web channel must be payment-gated exactly like the agent channel —
    not just session-gated — or the frontend's x402-signed request never
    receives a 402 challenge to respond to."""
    from fastapi import FastAPI

    x402_app = FastAPI()
    settings = Settings(
        V52_X402_ENABLED=True,
        V52_X402_FACILITATOR_URL="https://relayer.example/api/v1/plugins/x402/call",
        V52_X402_FACILITATOR_API_KEY="test-only-relayer-token",
        V52_X402_PAY_TO="0x" + "1" * 40,
    )
    configure_x402(x402_app, settings)

    payment_middleware = next(
        m for m in x402_app.user_middleware if m.cls.__name__ == "PaymentMiddlewareASGI"
    )
    routes = payment_middleware.kwargs["routes"]

    assert "POST /v1/web/investigations/wallet-flow" in routes
    assert routes["POST /v1/web/investigations/wallet-flow"].accepts[0].price["amount"] == (
        settings.v52_x402_wallet_flow_price
    )
