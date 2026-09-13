"""Settings tests for FRANCO.md RPC configuration and CORS."""

from __future__ import annotations

import pytest
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


def test_settings_build_alchemy_urls_from_single_api_key() -> None:
    settings = Settings(
        _env_file=None,
        V52_ENV="development",
        ALCHEMY_API_KEY="my-shared-key",
        V52_GRAPH_ENDPOINT="",
    )

    assert settings.alchemy_api_key_configured is True
    assert settings.alchemy_eth_rpc_url == "https://eth-mainnet.g.alchemy.com/v2/my-shared-key"
    assert settings.alchemy_avax_rpc_url == "https://avax-mainnet.g.alchemy.com/v2/my-shared-key"
    assert settings.alchemy_configured is True
    assert settings.alchemy_avax_configured is True

    safe = settings.safe_repr()
    assert safe["alchemy_api_key"] == "***REDACTED***"
    assert safe["alchemy_eth_rpc_url"] == "***REDACTED***"
    assert safe["alchemy_avax_rpc_url"] == "***REDACTED***"
    assert "my-shared-key" not in str(safe)


def test_alchemy_api_key_builds_fuji_url_for_testnet_chain_id() -> None:
    settings = Settings(
        _env_file=None,
        ALCHEMY_API_KEY="my-shared-key",
        ALCHEMY_AVAX_CHAIN_ID=43113,
        V52_GRAPH_ENDPOINT="",
    )

    assert settings.alchemy_avax_rpc_url == "https://avax-fuji.g.alchemy.com/v2/my-shared-key"


def test_explicit_alchemy_url_overrides_api_key() -> None:
    settings = Settings(
        _env_file=None,
        ALCHEMY_API_KEY="my-shared-key",
        ALCHEMY_ETH_RPC_URL="https://eth-mainnet.g.alchemy.com/v2/explicit-key",
        V52_GRAPH_ENDPOINT="",
    )

    assert settings.alchemy_eth_rpc_url == "https://eth-mainnet.g.alchemy.com/v2/explicit-key"


def test_no_alchemy_configuration_leaves_urls_empty() -> None:
    settings = Settings(
        _env_file=None,
        ALCHEMY_API_KEY="",
        ALCHEMY_ETH_RPC_URL="",
        ALCHEMY_AVAX_RPC_URL="",
        V52_RPC_URL="",
        V52_GRAPH_ENDPOINT="",
    )

    assert settings.alchemy_api_key_configured is False
    assert settings.alchemy_eth_rpc_url == ""
    assert settings.alchemy_avax_rpc_url == ""
    assert settings.alchemy_configured is False
    assert settings.alchemy_avax_configured is False


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


# The real local .env (loaded process-wide by tests/conftest.py via
# load_dotenv) may already set HSK_RPC_URL/HSK_EVIDENCE_REGISTRY_ADDRESS/
# HSK_CHAIN_ID/HSK_EXPLORER_URL for local development. Since explicit
# overrides always win over the HSK_NETWORK default (by design), these tests
# blank them out explicitly to observe pure HSK_NETWORK resolution — same
# pattern as test_no_alchemy_configuration_leaves_urls_empty above.
_NO_HSK_OVERRIDES = {
    "HSK_RPC_URL": "",
    "HSK_EVIDENCE_REGISTRY_ADDRESS": "",
    "HSK_CHAIN_ID": None,
    "HSK_EXPLORER_URL": "",
}


def test_hsk_network_unset_keeps_legacy_defaults() -> None:
    """No HSK_NETWORK, no explicit HSK_* overrides: behaves exactly as before this feature."""
    settings = Settings(_env_file=None, V52_GRAPH_ENDPOINT="", **_NO_HSK_OVERRIDES)

    assert settings.hsk_rpc_url == ""
    assert settings.hsk_rpc_configured is False
    assert settings.v52_hsk_evidence_registry_address == ""
    assert settings.hsk_registry_configured is False
    assert settings.hsk_chain_id == 177
    assert settings.v52_hsk_explorer_url == "https://testnet-explorer.hsk.xyz"


def test_hsk_network_testnet_resolves_known_deployment() -> None:
    settings = Settings(
        _env_file=None, HSK_NETWORK="testnet", V52_GRAPH_ENDPOINT="", **_NO_HSK_OVERRIDES
    )

    assert settings.hsk_rpc_url == "https://testnet.hsk.xyz"
    assert settings.hsk_chain_id == 133
    assert (
        settings.v52_hsk_evidence_registry_address == "0x3422820Ef9FBC8e0206E4CBcB6369dBd14BE18c4"
    )
    assert settings.v52_hsk_explorer_url == "https://testnet-explorer.hsk.xyz"
    assert settings.hsk_registry_configured is True


def test_hsk_network_mainnet_resolves_known_deployment() -> None:
    settings = Settings(
        _env_file=None, HSK_NETWORK="mainnet", V52_GRAPH_ENDPOINT="", **_NO_HSK_OVERRIDES
    )

    assert settings.hsk_rpc_url == "https://mainnet.hsk.xyz"
    assert settings.hsk_chain_id == 177
    assert (
        settings.v52_hsk_evidence_registry_address == "0xf7565Ec1e00206955286B8536c779A7221E62A9c"
    )
    assert settings.v52_hsk_explorer_url == "https://hsk.blockscout.com"
    assert settings.hsk_registry_configured is True


def test_hsk_network_explicit_override_wins_over_network_default() -> None:
    settings = Settings(
        _env_file=None,
        HSK_NETWORK="mainnet",
        HSK_RPC_URL="https://custom-hsk-rpc.example",
        HSK_EVIDENCE_REGISTRY_ADDRESS="0x" + "ab" * 20,
        HSK_CHAIN_ID=99999,
        HSK_EXPLORER_URL="https://custom-explorer.example",
        V52_GRAPH_ENDPOINT="",
    )

    assert settings.hsk_rpc_url == "https://custom-hsk-rpc.example"
    assert settings.hsk_chain_id == 99999
    assert settings.v52_hsk_evidence_registry_address == "0x" + "ab" * 20
    assert settings.v52_hsk_explorer_url == "https://custom-explorer.example"


def test_hsk_network_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="HSK_NETWORK"):
        Settings(_env_file=None, HSK_NETWORK="devnet", V52_GRAPH_ENDPOINT="")


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
