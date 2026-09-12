"""Application configuration loaded from environment or .env.

Secrets must never appear in logs, HTTP responses or .v52 packages. Use
settings.safe_repr() for logging.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_REDACTED = "***REDACTED***"


class Settings(BaseSettings):
    """Runtime settings for the Vector52 backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # Runtime
    v52_env: str = Field(default="development", alias="V52_ENV")
    v52_cors_origins: str = Field(default="", alias="V52_CORS_ORIGINS")

    # Legacy single Ethereum RPC. Kept only as a fallback during migration.
    v52_rpc_url: str = Field(default="", alias="V52_RPC_URL")

    # FRANCO.md RPC configuration. The V52_* variants are accepted for
    # compatibility with earlier local work and tests.
    v52_alchemy_eth_rpc_url: str = Field(
        default="",
        validation_alias=AliasChoices("ALCHEMY_ETH_RPC_URL", "V52_ALCHEMY_ETH_RPC_URL"),
    )
    v52_alchemy_avax_rpc_url: str = Field(
        default="",
        validation_alias=AliasChoices("ALCHEMY_AVAX_RPC_URL", "V52_ALCHEMY_AVAX_RPC_URL"),
    )
    v52_hsk_rpc_url: str = Field(
        default="",
        validation_alias=AliasChoices("HSK_RPC_URL", "V52_HSK_RPC_URL"),
    )
    rpc_timeout_ms: int = Field(
        default=12000,
        ge=100,
        le=120000,
        validation_alias=AliasChoices("RPC_TIMEOUT_MS", "V52_RPC_TIMEOUT_MS"),
    )
    rpc_max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        validation_alias=AliasChoices("RPC_MAX_RETRIES", "V52_RPC_MAX_RETRIES"),
    )
    alchemy_eth_chain_id: int = Field(
        default=1,
        ge=1,
        validation_alias=AliasChoices("ALCHEMY_ETH_CHAIN_ID", "V52_ALCHEMY_ETH_CHAIN_ID"),
    )
    alchemy_avax_chain_id: int = Field(
        default=43114,
        ge=1,
        validation_alias=AliasChoices("ALCHEMY_AVAX_CHAIN_ID", "V52_ALCHEMY_AVAX_CHAIN_ID"),
    )
    hsk_chain_id: int = Field(
        default=177,
        ge=1,
        validation_alias=AliasChoices("HSK_CHAIN_ID", "V52_HSK_CHAIN_ID"),
    )

    # The Graph
    v52_graph_endpoint: str = Field(default="", alias="V52_GRAPH_ENDPOINT")
    v52_graph_api_key: str = Field(default="", alias="V52_GRAPH_API_KEY")

    # Evidence Vault
    v52_data_dir: str = Field(default="./evidence_vault", alias="V52_DATA_DIR")

    # Storage backend
    v52_storage_backend: str = Field(default="file", alias="V52_STORAGE_BACKEND")

    # MongoDB (P1)
    v52_mongodb_uri: str = Field(default="", alias="V52_MONGODB_URI")
    v52_mongodb_database: str = Field(default="vector52", alias="V52_MONGODB_DATABASE")

    # Upstash Redis (optional)
    v52_cache_enabled: bool = Field(default=False, alias="V52_CACHE_ENABLED")
    v52_upstash_redis_rest_url: str = Field(default="", alias="V52_UPSTASH_REDIS_REST_URL")
    v52_upstash_redis_rest_token: str = Field(default="", alias="V52_UPSTASH_REDIS_REST_TOKEN")
    v52_cache_ttl_seconds: int = Field(default=120, alias="V52_CACHE_TTL_SECONDS")

    # AI explanations (optional, non-authoritative)
    v52_ai_enabled: bool = Field(default=False, alias="V52_AI_ENABLED")
    v52_ai_api_key: str = Field(default="", alias="V52_AI_API_KEY")

    @property
    def is_production(self) -> bool:
        return self.v52_env.lower() == "production"

    @property
    def data_dir(self) -> Path:
        return Path(self.v52_data_dir)

    @property
    def cors_origins(self) -> list[str]:
        """Explicit browser origins allowed to call the API; never use a wildcard in production."""
        return [
            origin.strip().rstrip("/")
            for origin in self.v52_cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def alchemy_eth_rpc_url(self) -> str:
        """Ethereum Alchemy endpoint, with legacy V52_RPC_URL fallback."""
        return self.v52_alchemy_eth_rpc_url or self.v52_rpc_url

    @property
    def alchemy_configured(self) -> bool:
        return bool(self.alchemy_eth_rpc_url)

    @property
    def alchemy_avax_rpc_url(self) -> str:
        return self.v52_alchemy_avax_rpc_url

    @property
    def alchemy_avax_configured(self) -> bool:
        return bool(self.alchemy_avax_rpc_url)

    @property
    def hsk_rpc_url(self) -> str:
        return self.v52_hsk_rpc_url

    @property
    def hsk_rpc_configured(self) -> bool:
        return bool(self.hsk_rpc_url)

    @property
    def rpc_configured(self) -> bool:
        """Backward-compatible flag for Ethereum RPC availability."""
        return self.alchemy_configured

    @property
    def rpc_timeout_seconds(self) -> float:
        return self.rpc_timeout_ms / 1000

    @property
    def graph_configured(self) -> bool:
        return bool(self.v52_graph_endpoint)

    @field_validator("v52_storage_backend")
    @classmethod
    def validate_storage_backend(cls, value: str) -> str:
        allowed = {"file", "mongo"}
        if value not in allowed:
            raise ValueError(f"V52_STORAGE_BACKEND must be one of {allowed}, got '{value}'.")
        return value

    @model_validator(mode="after")
    def validate_production_requirements(self) -> Settings:
        """Production must have live Ethereum RPC and The Graph endpoints."""
        if self.is_production:
            missing = []
            if not self.alchemy_eth_rpc_url:
                missing.append("ALCHEMY_ETH_RPC_URL")
            if not self.v52_graph_endpoint:
                missing.append("V52_GRAPH_ENDPOINT")
            if missing:
                raise ValueError(
                    "Missing required configuration for production: "
                    f"{', '.join(missing)}. Check your environment variables."
                )
        return self

    def safe_repr(self) -> dict[str, object]:
        """Return a dict safe to log."""
        return {
            "v52_env": self.v52_env,
            "cors_origins": self.cors_origins,
            "rpc_configured": self.rpc_configured,
            "alchemy_configured": self.alchemy_configured,
            "alchemy_avax_configured": self.alchemy_avax_configured,
            "hsk_rpc_configured": self.hsk_rpc_configured,
            "graph_configured": self.graph_configured,
            "rpc_timeout_ms": self.rpc_timeout_ms,
            "rpc_max_retries": self.rpc_max_retries,
            "alchemy_eth_chain_id": self.alchemy_eth_chain_id,
            "alchemy_avax_chain_id": self.alchemy_avax_chain_id,
            "hsk_chain_id": self.hsk_chain_id,
            "v52_data_dir": self.v52_data_dir,
            "v52_storage_backend": self.v52_storage_backend,
            "v52_cache_enabled": self.v52_cache_enabled,
            "v52_ai_enabled": self.v52_ai_enabled,
            "v52_mongodb_database": self.v52_mongodb_database,
            "v52_rpc_url": _REDACTED if self.v52_rpc_url else "(not set)",
            "alchemy_eth_rpc_url": _REDACTED if self.alchemy_eth_rpc_url else "(not set)",
            "alchemy_avax_rpc_url": _REDACTED if self.alchemy_avax_rpc_url else "(not set)",
            "hsk_rpc_url": _REDACTED if self.hsk_rpc_url else "(not set)",
            "v52_graph_api_key": _REDACTED if self.v52_graph_api_key else "(not set)",
            "v52_mongodb_uri": _REDACTED if self.v52_mongodb_uri else "(not set)",
            "v52_ai_api_key": _REDACTED if self.v52_ai_api_key else "(not set)",
            "v52_upstash_redis_rest_token": (
                _REDACTED if self.v52_upstash_redis_rest_token else "(not set)"
            ),
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton. Call invalidate_settings() in tests."""
    return Settings()


def invalidate_settings() -> None:
    """Clear the settings cache. Use in tests that override environment variables."""
    get_settings.cache_clear()
