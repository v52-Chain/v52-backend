"""Settings tests for FRANCO.md RPC configuration."""

from __future__ import annotations

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
