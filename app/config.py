"""
Application configuration — loads from environment / .env file.

Usage:
    from app.config import get_settings
    settings = get_settings()

Rules (from architecture doc section 15):
  - .env NEVER enters Git.
  - .env.example contains no secrets.
  - Tokens must not appear in logs, errors or .v52 packages.
  - Frontend never receives provider keys.
  - V52_RPC_URL and V52_GRAPH_ENDPOINT are required in production (V52_ENV=production).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_REDACTED = "***REDACTED***"


class Settings(BaseSettings):
    """
    All configuration is read from environment variables (or .env).
    Secrets are NEVER included in log output — use settings.safe_repr() for logging.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Runtime ───────────────────────────────────────────────────────────────
    v52_env: str = Field(default="development", alias="V52_ENV")

    # ── Ethereum RPC ──────────────────────────────────────────────────────────
    v52_rpc_url: str = Field(default="", alias="V52_RPC_URL")
    v52_alchemy_eth_rpc_url: str = Field(default="", alias="V52_ALCHEMY_ETH_RPC_URL")

    # ── The Graph ─────────────────────────────────────────────────────────────
    v52_graph_endpoint: str = Field(default="", alias="V52_GRAPH_ENDPOINT")
    v52_graph_api_key: str = Field(default="", alias="V52_GRAPH_API_KEY")

    # ── Evidence Vault ────────────────────────────────────────────────────────
    v52_data_dir: str = Field(default="./evidence_vault", alias="V52_DATA_DIR")

    # ── Storage backend ───────────────────────────────────────────────────────
    v52_storage_backend: str = Field(default="file", alias="V52_STORAGE_BACKEND")

    # ── MongoDB (P1) ──────────────────────────────────────────────────────────
    v52_mongodb_uri: str = Field(default="", alias="V52_MONGODB_URI")
    v52_mongodb_database: str = Field(default="vector52", alias="V52_MONGODB_DATABASE")

    # ── Upstash Redis (optional) ──────────────────────────────────────────────
    v52_cache_enabled: bool = Field(default=False, alias="V52_CACHE_ENABLED")
    v52_upstash_redis_rest_url: str = Field(default="", alias="V52_UPSTASH_REDIS_REST_URL")
    v52_upstash_redis_rest_token: str = Field(default="", alias="V52_UPSTASH_REDIS_REST_TOKEN")
    v52_cache_ttl_seconds: int = Field(default=120, alias="V52_CACHE_TTL_SECONDS")

    # ── AI (non-authoritative, L5) ────────────────────────────────────────────
    v52_ai_enabled: bool = Field(default=False, alias="V52_AI_ENABLED")
    v52_ai_api_key: str = Field(default="", alias="V52_AI_API_KEY")

    # ── Computed properties ───────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.v52_env.lower() == "production"

    @property
    def data_dir(self) -> Path:
        return Path(self.v52_data_dir)

    @property
    def rpc_configured(self) -> bool:
        return bool(self.v52_rpc_url)

    @property
    def alchemy_eth_rpc_url(self) -> str:
        """Alchemy endpoint used by Transfers API, with legacy RPC fallback."""
        return self.v52_alchemy_eth_rpc_url or self.v52_rpc_url

    @property
    def alchemy_configured(self) -> bool:
        return bool(self.alchemy_eth_rpc_url)

    @property
    def graph_configured(self) -> bool:
        return bool(self.v52_graph_endpoint)

    @field_validator("v52_storage_backend")
    @classmethod
    def validate_storage_backend(cls, v: str) -> str:
        allowed = {"file", "mongo"}
        if v not in allowed:
            raise ValueError(f"V52_STORAGE_BACKEND must be one of {allowed}, got '{v}'.")
        return v

    @model_validator(mode="after")
    def validate_production_requirements(self) -> Settings:
        """In production mode, critical URLs must be set."""
        if self.is_production:
            missing = []
            if not self.v52_rpc_url:
                missing.append("V52_RPC_URL")
            if not self.v52_graph_endpoint:
                missing.append("V52_GRAPH_ENDPOINT")
            if missing:
                raise ValueError(
                    f"Missing required configuration for production: {', '.join(missing)}. "
                    "Check your environment variables."
                )
        return self

    def safe_repr(self) -> dict:
        """Return a dict safe to log — secrets are redacted."""
        return {
            "v52_env": self.v52_env,
            "rpc_configured": self.rpc_configured,
            "alchemy_configured": self.alchemy_configured,
            "graph_configured": self.graph_configured,
            "v52_data_dir": self.v52_data_dir,
            "v52_storage_backend": self.v52_storage_backend,
            "v52_cache_enabled": self.v52_cache_enabled,
            "v52_ai_enabled": self.v52_ai_enabled,
            "v52_mongodb_database": self.v52_mongodb_database,
            # All secrets are redacted:
            "v52_rpc_url": _REDACTED if self.v52_rpc_url else "(not set)",
            "v52_alchemy_eth_rpc_url": (
                _REDACTED if self.v52_alchemy_eth_rpc_url else "(not set)"
            ),
            "v52_graph_api_key": _REDACTED if self.v52_graph_api_key else "(not set)",
            "v52_mongodb_uri": _REDACTED if self.v52_mongodb_uri else "(not set)",
            "v52_ai_api_key": _REDACTED if self.v52_ai_api_key else "(not set)",
            "v52_upstash_redis_rest_token": (
                _REDACTED if self.v52_upstash_redis_rest_token else "(not set)"
            ),
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton.  Call invalidate_settings() in tests."""
    return Settings()


def invalidate_settings() -> None:
    """Clear the settings cache.  Use in tests that override environment variables."""
    get_settings.cache_clear()
