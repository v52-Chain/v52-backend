"""Settings tests for FRANCO.md RPC configuration and CORS."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings


def test_settings_accept_franco_rpc_env_names() -> None:
    settings = Settings(
        _env_file=None,
        V52_ENV="development",
        ALCHEMY_ETH_RPC_URL="https://eth-mainnet.g.alchemy.com/v2/eth-secret",
        ALCHEMY_AVAX_RPC_URL="https://avax-mainnet.g.alchemy.com/v2/avax-secret",
        HSK_RPC_URL="https://hsk.example/rpc/hsk-secret",
        RPC_TIMEOUT_MS=9000,
        RPC_MAX_RETRIES=1,
        V52_GRAPH_ENDPOINT="",
    )

    assert settings.alchemy_configured is True
    assert settings.alchemy_avax_configured is True
    assert settings.hsk_rpc_configured is True
    assert settings.rpc_timeout_seconds == 9
    assert settings.rpc_max_retries == 1

    safe = settings.safe_repr()
    assert safe["alchemy_eth_rpc_url"] == "***REDACTED***"
    assert "eth-secret" not in str(safe)


def test_cors_origins_are_explicit_and_normalized() -> None:
    settings = Settings(
        V52_CORS_ORIGINS=(
            "https://vector52.vercel.app/, "
            "https://preview.vector52.example"
        )
    )

    assert settings.cors_origins == [
        "https://vector52.vercel.app",
        "https://preview.vector52.example",
    ]


def test_cors_origins_default_to_empty() -> None:
    assert Settings(V52_CORS_ORIGINS="").cors_origins == []


def test_configured_cors_origin_is_returned_on_preflight(monkeypatch) -> None:
    from app.config import invalidate_settings
    from app.main import create_app

    origin = "https://vector52.vercel.app"
    monkeypatch.setenv("V52_CORS_ORIGINS", origin)
    invalidate_settings()

    with TestClient(create_app()) as client:
        response = client.options(
            "/healthz",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
