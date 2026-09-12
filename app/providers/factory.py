"""Provider factory and chain alias resolution."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.providers.rpc import AlchemyRpcProvider, HskRpcProvider, JsonRpcProvider


@dataclass(frozen=True)
class ChainConfig:
    """Public chain metadata used by RPC endpoints and status checks."""

    key: str
    chain_id: int
    network: str
    provider_label: str
    configured: bool


def configured_chains(settings: Settings) -> dict[str, ChainConfig]:
    """Return chain configs keyed by canonical chain key."""
    return {
        "ethereum": ChainConfig(
            key="ethereum",
            chain_id=settings.alchemy_eth_chain_id,
            network="ethereum-mainnet",
            provider_label="alchemy",
            configured=settings.alchemy_configured,
        ),
        "avalanche": ChainConfig(
            key="avalanche",
            chain_id=settings.alchemy_avax_chain_id,
            network=_avalanche_network_name(settings.alchemy_avax_chain_id),
            provider_label="alchemy",
            configured=settings.alchemy_avax_configured,
        ),
        "hsk": ChainConfig(
            key="hsk",
            chain_id=settings.hsk_chain_id,
            network="hsk",
            provider_label="hsk_rpc",
            configured=settings.hsk_rpc_configured,
        ),
    }


def normalize_chain(chain: str | int, settings: Settings) -> ChainConfig | None:
    """Resolve a path value such as eth, 1, avax or hsk into ChainConfig."""
    raw = str(chain).strip().lower()
    chains = configured_chains(settings)
    aliases = {
        "1": "ethereum",
        "eth": "ethereum",
        "ethereum": "ethereum",
        "ethereum-mainnet": "ethereum",
        "mainnet": "ethereum",
        "43114": "avalanche",
        "43113": "avalanche",
        "avax": "avalanche",
        "avalanche": "avalanche",
        "avalanche-mainnet": "avalanche",
        "fuji": "avalanche",
        "avalanche-fuji": "avalanche",
        str(settings.hsk_chain_id): "hsk",
        "hsk": "hsk",
        "hashkey": "hsk",
        "hashkey-chain": "hsk",
    }
    key = aliases.get(raw)
    if key is None:
        return None
    return chains[key]


def get_rpc_provider_for_chain(
    settings: Settings,
    chain: str | int,
) -> JsonRpcProvider | None:
    """Build the configured provider for a chain, or None if unavailable/unknown."""
    chain_config = normalize_chain(chain, settings)
    if chain_config is None or not chain_config.configured:
        return None

    timeout_seconds = settings.rpc_timeout_seconds
    max_retries = settings.rpc_max_retries
    if chain_config.key == "ethereum":
        return AlchemyRpcProvider(
            settings.alchemy_eth_rpc_url,
            expected_chain_id=settings.alchemy_eth_chain_id,
            network="ethereum-mainnet",
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
    if chain_config.key == "avalanche":
        return AlchemyRpcProvider(
            settings.alchemy_avax_rpc_url,
            expected_chain_id=settings.alchemy_avax_chain_id,
            network=_avalanche_network_name(settings.alchemy_avax_chain_id),
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
    if chain_config.key == "hsk":
        return HskRpcProvider(
            settings.hsk_rpc_url,
            expected_chain_id=settings.hsk_chain_id,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
    return None


def _avalanche_network_name(chain_id: int) -> str:
    if chain_id == 43113:
        return "avalanche-fuji"
    return "avalanche-mainnet"
