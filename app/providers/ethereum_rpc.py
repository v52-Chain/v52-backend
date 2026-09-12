"""Backward-compatible Ethereum RPC provider wrapper."""

from __future__ import annotations

from app.models.evidence import ProviderStatus
from app.providers.base import ProviderError
from app.providers.rpc import AlchemyRpcProvider, RpcErrorCode


class EthereumRpcProvider(AlchemyRpcProvider):
    """
    Compatibility wrapper for the original single-chain provider.

    New code should use app.providers.factory.get_rpc_provider_for_chain().
    """

    name = "ethereum_rpc"
    version = "0.2.0"

    def __init__(
        self,
        rpc_url: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 0,
        expected_chain_id: int = 1,
    ) -> None:
        if not rpc_url:
            raise ProviderError(
                "V52_RPC_URL is not configured. Set ALCHEMY_ETH_RPC_URL or "
                "V52_ALCHEMY_ETH_RPC_URL in .env to enable live RPC acquisition.",
                status=ProviderStatus.FAILED,
                code=RpcErrorCode.RPC_UNAVAILABLE,
                provider="alchemy",
            )
        super().__init__(
            rpc_url,
            expected_chain_id=expected_chain_id,
            network="ethereum-mainnet",
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
