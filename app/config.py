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

# Alchemy JSON-RPC URL templates. A single ALCHEMY_API_KEY is combined with the
# network subdomain to build the authenticated endpoint, so the key never has
# to be pasted into a full URL by hand for each chain.
_ALCHEMY_ETH_MAINNET_URL = "https://eth-mainnet.g.alchemy.com/v2/{api_key}"
_ALCHEMY_AVAX_MAINNET_URL = "https://avax-mainnet.g.alchemy.com/v2/{api_key}"
_ALCHEMY_AVAX_FUJI_URL = "https://avax-fuji.g.alchemy.com/v2/{api_key}"

# V52EvidenceRegistry deployments, one per HSK network. Mirrors
# v52-onchain/deployments/hsk-{testnet,mainnet}.json — must be updated by hand
# if those deployments change (no cross-repo artifact pipeline yet, same
# caveat as the vendored ABI in app/onchain/abi/V52EvidenceRegistry.json).
# HSK_NETWORK selects which row is used for every field below unless the
# matching HSK_* env var is set explicitly, in which case that explicit value
# always wins over the network default.
_HSK_NETWORK_DEFAULTS: dict[str, dict[str, str | int]] = {
    "testnet": {
        "chain_id": 133,
        "rpc_url": "https://testnet.hsk.xyz",
        "explorer_url": "https://testnet-explorer.hsk.xyz",
        "evidence_registry_address": "0x3422820Ef9FBC8e0206E4CBcB6369dBd14BE18c4",
    },
    "mainnet": {
        "chain_id": 177,
        "rpc_url": "https://mainnet.hsk.xyz",
        "explorer_url": "https://hsk.blockscout.com",
        "evidence_registry_address": "0xf7565Ec1e00206955286B8536c779A7221E62A9c",
    },
}

# Legacy hardcoded defaults, kept byte-for-byte identical to pre-HSK_NETWORK
# behavior for anyone who never sets HSK_NETWORK: chain_id 177, testnet
# explorer, empty RPC/address (i.e. "not configured" until set explicitly).
_LEGACY_HSK_CHAIN_ID = 177
_LEGACY_HSK_EXPLORER_URL = "https://testnet-explorer.hsk.xyz"


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
    v52_public_origin: str = Field(default="http://localhost:5173", alias="V52_PUBLIC_ORIGIN")

    # Legacy single Ethereum RPC. Kept only as a fallback during migration.
    v52_rpc_url: str = Field(default="", alias="V52_RPC_URL")

    # FRANCO.md RPC configuration. The V52_* variants are accepted for
    # compatibility with earlier local work and tests.
    #
    # Preferred: set ALCHEMY_API_KEY alone. The backend builds the Ethereum and
    # Avalanche RPC URLs from it using Alchemy's standard network subdomains.
    # ALCHEMY_ETH_RPC_URL / ALCHEMY_AVAX_RPC_URL remain as an explicit override
    # for a custom Alchemy app URL or a non-Alchemy JSON-RPC endpoint.
    v52_alchemy_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("ALCHEMY_API_KEY", "V52_ALCHEMY_API_KEY"),
    )
    v52_alchemy_eth_rpc_url: str = Field(
        default="",
        validation_alias=AliasChoices("ALCHEMY_ETH_RPC_URL", "V52_ALCHEMY_ETH_RPC_URL"),
    )
    v52_alchemy_avax_rpc_url: str = Field(
        default="",
        validation_alias=AliasChoices("ALCHEMY_AVAX_RPC_URL", "V52_ALCHEMY_AVAX_RPC_URL"),
    )
    # Which HSK deployment to anchor against. Every HSK_* field below is an
    # explicit override; when left unset (and HSK_NETWORK is also unset),
    # existing single-network deployments keep behaving exactly as before
    # (empty RPC/address, chain_id 177, testnet explorer). Setting
    # HSK_NETWORK to "testnet" or "mainnet" is what activates automatic
    # resolution of RPC URL / chain ID / registry address / explorer from
    # _HSK_NETWORK_DEFAULTS for any field left unset.
    v52_hsk_network: str | None = Field(
        default=None,
        validation_alias=AliasChoices("HSK_NETWORK", "V52_HSK_NETWORK"),
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
    v52_hsk_chain_id_override: int | None = Field(
        default=None,
        validation_alias=AliasChoices("HSK_CHAIN_ID", "V52_HSK_CHAIN_ID"),
    )

    # HSK V52EvidenceRegistry (manifest anchoring). The registry only ever
    # receives hashes, a schema version and a non-sensitive case_id — never
    # the manifest itself, wallets under investigation or claims. See
    # v52-onchain/contracts/hsk/V52EvidenceRegistry.sol and
    # v52-onchain/README.md for the full contract.
    v52_hsk_evidence_registry_address_override: str = Field(
        default="",
        validation_alias=AliasChoices(
            "HSK_EVIDENCE_REGISTRY_ADDRESS", "V52_HSK_EVIDENCE_REGISTRY_ADDRESS"
        ),
    )
    # Signer wallet: always network-specific, never has a network default —
    # mainnet and testnet keys must never be interchangeable, and the mainnet
    # V52EvidenceRegistry owner/issuer is the x402 agent key by historical
    # accident (see v52-onchain/README.md HSK Mainnet security note); rotate
    # to a dedicated key before relying on this for real anchoring.
    v52_hsk_anchor_private_key: str = Field(
        default="",
        validation_alias=AliasChoices("HSK_ANCHOR_PRIVATE_KEY", "V52_HSK_ANCHOR_PRIVATE_KEY"),
    )
    v52_hsk_explorer_url_override: str = Field(
        default="",
        validation_alias=AliasChoices("HSK_EXPLORER_URL", "V52_HSK_EXPLORER_URL"),
    )
    v52_hsk_anchor_gas_limit: int = Field(
        default=400_000,
        ge=21_000,
        validation_alias=AliasChoices("HSK_ANCHOR_GAS_LIMIT", "V52_HSK_ANCHOR_GAS_LIMIT"),
    )
    v52_hsk_methodology_version: str = Field(
        default="v52-contribution-0.1.0",
        validation_alias=AliasChoices(
            "HSK_METHODOLOGY_VERSION", "V52_HSK_METHODOLOGY_VERSION"
        ),
    )

    # The Graph — legacy single-chain fields. Kept as the Ethereum fallback so
    # existing deployments (V52_GRAPH_ENDPOINT/V52_GRAPH_API_KEY only) keep
    # working unchanged.
    v52_graph_endpoint: str = Field(default="", alias="V52_GRAPH_ENDPOINT")
    v52_graph_api_key: str = Field(default="", alias="V52_GRAPH_API_KEY")

    # The Graph — per-chain configuration for the multi-chain DeFi Subgraph
    # Intel feature (docs/SUBGRAPHS.md). Each chain is independently optional:
    # an unconfigured chain reports UNCONFIGURED honestly rather than
    # inventing data. `schema` selects which GraphQL shape the query builder
    # in app/api/defi_core.py speaks — "uniswap_v3" (pools/feeTier/liquidity)
    # or "uniswap_v2" (pairs/reserve0/reserve1), matching the family most
    # subgraphs on that chain fork.
    v52_graph_endpoint_ethereum: str = Field(default="", alias="V52_GRAPH_ENDPOINT_ETHEREUM")
    v52_graph_api_key_ethereum: str = Field(default="", alias="V52_GRAPH_API_KEY_ETHEREUM")
    v52_graph_schema_ethereum: str = Field(default="uniswap_v3", alias="V52_GRAPH_SCHEMA_ETHEREUM")

    v52_graph_endpoint_avalanche: str = Field(default="", alias="V52_GRAPH_ENDPOINT_AVALANCHE")
    v52_graph_api_key_avalanche: str = Field(default="", alias="V52_GRAPH_API_KEY_AVALANCHE")
    v52_graph_schema_avalanche: str = Field(
        default="uniswap_v2", alias="V52_GRAPH_SCHEMA_AVALANCHE"
    )

    v52_graph_endpoint_hsk: str = Field(default="", alias="V52_GRAPH_ENDPOINT_HSK")
    v52_graph_api_key_hsk: str = Field(default="", alias="V52_GRAPH_API_KEY_HSK")
    v52_graph_schema_hsk: str = Field(default="uniswap_v2", alias="V52_GRAPH_SCHEMA_HSK")

    @field_validator(
        "v52_graph_schema_ethereum", "v52_graph_schema_avalanche", "v52_graph_schema_hsk"
    )
    @classmethod
    def validate_graph_schema(cls, value: str) -> str:
        allowed = {"uniswap_v3", "uniswap_v2"}
        if value not in allowed:
            raise ValueError(f"Graph schema must be one of {allowed}, got '{value}'.")
        return value

    @field_validator("v52_hsk_network", mode="before")
    @classmethod
    def validate_hsk_network(cls, value: str | None) -> str | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        allowed = set(_HSK_NETWORK_DEFAULTS)
        normalized = value.strip().lower()
        if normalized not in allowed:
            raise ValueError(f"HSK_NETWORK must be one of {sorted(allowed)}, got '{value}'.")
        return normalized

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

    # x402 Agent channel (optional)
    v52_x402_enabled: bool = Field(default=False, alias="V52_X402_ENABLED")
    v52_x402_facilitator_url: str = Field(default="", alias="V52_X402_FACILITATOR_URL")
    v52_x402_facilitator_api_key: str = Field(default="", alias="V52_X402_FACILITATOR_API_KEY")
    v52_x402_pay_to: str = Field(default="", alias="V52_X402_PAY_TO")
    v52_x402_network: str = Field(default="eip155:43113", alias="V52_X402_NETWORK")
    v52_x402_asset: str = Field(
        default="0x5425890298aed601595a70AB815c96711a31Bc65",
        alias="V52_X402_ASSET",
    )
    v52_x402_wallet_flow_price: str = Field(default="1000", alias="V52_X402_WALLET_FLOW_PRICE")
    # DeFi Subgraph Intel pricing tiers (docs/SUBGRAPHS.md §4). Priced by
    # query cost/value: a single chain's top pools is the cheapest read; a
    # per-pool swap drill-down costs more; a full multi-chain vital-points
    # scan is the most expensive because it fans out to every configured chain.
    v52_x402_defi_pools_price: str = Field(default="400", alias="V52_X402_DEFI_POOLS_PRICE")
    v52_x402_defi_pool_activity_price: str = Field(
        default="900", alias="V52_X402_DEFI_POOL_ACTIVITY_PRICE"
    )
    v52_x402_defi_scan_price: str = Field(default="2500", alias="V52_X402_DEFI_SCAN_PRICE")

    # MCP Agent Access integration (optional). Empty by default: v52-mcp is a
    # separate repository/process not yet connected to this backend. Until a
    # real URL is configured AND verified reachable, /v1/integrations/mcp/*
    # must report UNAVAILABLE honestly — never a mock promoted to READY.
    v52_mcp_server_url: str = Field(default="", alias="V52_MCP_SERVER_URL")

    @property
    def mcp_integration_configured(self) -> bool:
        return bool(self.v52_mcp_server_url)

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
    def alchemy_api_key_configured(self) -> bool:
        return bool(self.v52_alchemy_api_key)

    @property
    def alchemy_eth_rpc_url(self) -> str:
        """Ethereum Alchemy endpoint.

        Priority: explicit ALCHEMY_ETH_RPC_URL override, then a URL built from
        ALCHEMY_API_KEY, then the legacy V52_RPC_URL fallback.
        """
        if self.v52_alchemy_eth_rpc_url:
            return self.v52_alchemy_eth_rpc_url
        if self.v52_alchemy_api_key:
            return _ALCHEMY_ETH_MAINNET_URL.format(api_key=self.v52_alchemy_api_key)
        return self.v52_rpc_url

    @property
    def alchemy_configured(self) -> bool:
        return bool(self.alchemy_eth_rpc_url)

    @property
    def alchemy_avax_rpc_url(self) -> str:
        """Avalanche Alchemy endpoint, built from ALCHEMY_API_KEY when not overridden."""
        if self.v52_alchemy_avax_rpc_url:
            return self.v52_alchemy_avax_rpc_url
        if self.v52_alchemy_api_key:
            template = (
                _ALCHEMY_AVAX_FUJI_URL
                if self.alchemy_avax_chain_id == 43113
                else _ALCHEMY_AVAX_MAINNET_URL
            )
            return template.format(api_key=self.v52_alchemy_api_key)
        return ""

    @property
    def alchemy_avax_configured(self) -> bool:
        return bool(self.alchemy_avax_rpc_url)

    @property
    def _hsk_network_defaults(self) -> dict[str, str | int] | None:
        """Row of _HSK_NETWORK_DEFAULTS for HSK_NETWORK, or None if unset."""
        if self.v52_hsk_network is None:
            return None
        return _HSK_NETWORK_DEFAULTS[self.v52_hsk_network]

    @property
    def hsk_network(self) -> str:
        return self.v52_hsk_network or "(not set)"

    @property
    def hsk_rpc_url(self) -> str:
        """HSK JSON-RPC endpoint: explicit HSK_RPC_URL override, else HSK_NETWORK's default."""
        if self.v52_hsk_rpc_url:
            return self.v52_hsk_rpc_url
        defaults = self._hsk_network_defaults
        return str(defaults["rpc_url"]) if defaults else ""

    @property
    def hsk_chain_id(self) -> int:
        """HSK chain ID: explicit HSK_CHAIN_ID override, else HSK_NETWORK's default."""
        if self.v52_hsk_chain_id_override is not None:
            return self.v52_hsk_chain_id_override
        defaults = self._hsk_network_defaults
        return int(defaults["chain_id"]) if defaults else _LEGACY_HSK_CHAIN_ID

    @property
    def v52_hsk_evidence_registry_address(self) -> str:
        """V52EvidenceRegistry address: explicit override, else HSK_NETWORK's deployment."""
        if self.v52_hsk_evidence_registry_address_override:
            return self.v52_hsk_evidence_registry_address_override
        defaults = self._hsk_network_defaults
        return str(defaults["evidence_registry_address"]) if defaults else ""

    @property
    def v52_hsk_explorer_url(self) -> str:
        """Block explorer base URL: explicit override, else HSK_NETWORK's default."""
        if self.v52_hsk_explorer_url_override:
            return self.v52_hsk_explorer_url_override
        defaults = self._hsk_network_defaults
        return str(defaults["explorer_url"]) if defaults else _LEGACY_HSK_EXPLORER_URL

    @property
    def hsk_rpc_configured(self) -> bool:
        return bool(self.hsk_rpc_url)

    @property
    def hsk_registry_configured(self) -> bool:
        """The read side (GET /v1/anchors/{root}) only needs RPC + address."""
        return bool(self.hsk_rpc_configured and self.v52_hsk_evidence_registry_address)

    @property
    def hsk_anchor_configured(self) -> bool:
        """The write side (POST /v1/cases/{id}/anchor) also needs a signer key."""
        return bool(self.hsk_registry_configured and self.v52_hsk_anchor_private_key)

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

    @property
    def graph_endpoint_ethereum(self) -> str:
        """Ethereum subgraph endpoint: explicit override, else the legacy field."""
        return self.v52_graph_endpoint_ethereum or self.v52_graph_endpoint

    @property
    def graph_api_key_ethereum(self) -> str:
        return self.v52_graph_api_key_ethereum or self.v52_graph_api_key

    @property
    def graph_configured_ethereum(self) -> bool:
        return bool(self.graph_endpoint_ethereum)

    @property
    def graph_configured_avalanche(self) -> bool:
        return bool(self.v52_graph_endpoint_avalanche)

    @property
    def graph_configured_hsk(self) -> bool:
        return bool(self.v52_graph_endpoint_hsk)

    @property
    def x402_configured(self) -> bool:
        """x402 payment channel is fully configured when all required fields are set and enabled."""
        return self.v52_x402_enabled and all(
            (
                self.v52_x402_facilitator_url,
                self.v52_x402_facilitator_api_key,
                self.v52_x402_pay_to,
                self.v52_x402_network,
                self.v52_x402_asset,
            )
        )

    @field_validator("v52_storage_backend")
    @classmethod
    def validate_storage_backend(cls, value: str) -> str:
        allowed = {"file", "mongo"}
        if value not in allowed:
            raise ValueError(f"V52_STORAGE_BACKEND must be one of {allowed}, got '{value}'.")
        return value

    @model_validator(mode="after")
    def validate_production_requirements(self) -> Settings:
        """Production must have live Ethereum RPC. The Graph is optional for MVP."""
        if self.is_production:
            missing = []
            if not self.alchemy_eth_rpc_url:
                missing.append("ALCHEMY_ETH_RPC_URL")
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
            "alchemy_api_key_configured": self.alchemy_api_key_configured,
            "alchemy_configured": self.alchemy_configured,
            "alchemy_avax_configured": self.alchemy_avax_configured,
            "hsk_rpc_configured": self.hsk_rpc_configured,
            "hsk_registry_configured": self.hsk_registry_configured,
            "hsk_anchor_configured": self.hsk_anchor_configured,
            "hsk_network": self.hsk_network,
            "hsk_evidence_registry_address": self.v52_hsk_evidence_registry_address or "(not set)",
            "graph_configured": self.graph_configured,
            "graph_configured_ethereum": self.graph_configured_ethereum,
            "graph_configured_avalanche": self.graph_configured_avalanche,
            "graph_configured_hsk": self.graph_configured_hsk,
            "x402_configured": self.x402_configured,
            "rpc_timeout_ms": self.rpc_timeout_ms,
            "rpc_max_retries": self.rpc_max_retries,
            "alchemy_eth_chain_id": self.alchemy_eth_chain_id,
            "alchemy_avax_chain_id": self.alchemy_avax_chain_id,
            "hsk_chain_id": self.hsk_chain_id,
            "v52_data_dir": self.v52_data_dir,
            "v52_storage_backend": self.v52_storage_backend,
            "v52_cache_enabled": self.v52_cache_enabled,
            "v52_ai_enabled": self.v52_ai_enabled,
            "v52_x402_enabled": self.v52_x402_enabled,
            "v52_x402_network": self.v52_x402_network,
            "mcp_integration_configured": self.mcp_integration_configured,
            "v52_mongodb_database": self.v52_mongodb_database,
            "v52_rpc_url": _REDACTED if self.v52_rpc_url else "(not set)",
            "alchemy_api_key": _REDACTED if self.v52_alchemy_api_key else "(not set)",
            "alchemy_eth_rpc_url": _REDACTED if self.alchemy_eth_rpc_url else "(not set)",
            "alchemy_avax_rpc_url": _REDACTED if self.alchemy_avax_rpc_url else "(not set)",
            "hsk_rpc_url": _REDACTED if self.hsk_rpc_url else "(not set)",
            "hsk_anchor_private_key": (
                _REDACTED if self.v52_hsk_anchor_private_key else "(not set)"
            ),
            "v52_graph_api_key": _REDACTED if self.v52_graph_api_key else "(not set)",
            "v52_graph_endpoint_avalanche": (
                _REDACTED if self.v52_graph_endpoint_avalanche else "(not set)"
            ),
            "v52_graph_endpoint_hsk": _REDACTED if self.v52_graph_endpoint_hsk else "(not set)",
            "v52_mongodb_uri": _REDACTED if self.v52_mongodb_uri else "(not set)",
            "v52_ai_api_key": _REDACTED if self.v52_ai_api_key else "(not set)",
            "v52_x402_facilitator_api_key": (
                _REDACTED if self.v52_x402_facilitator_api_key else "(not set)"
            ),
            "v52_upstash_redis_rest_token": (
                _REDACTED if self.v52_upstash_redis_rest_token else "(not set)"
            ),
            "v52_mcp_server_url": _REDACTED if self.v52_mcp_server_url else "(not set)",
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton. Call invalidate_settings() in tests."""
    return Settings()


def invalidate_settings() -> None:
    """Clear the settings cache. Use in tests that override environment variables."""
    get_settings.cache_clear()
