"""GET /v1/wallets/{chain_id}/{address}/flow."""

from __future__ import annotations

import asyncio
import re

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.evidence.provenance import utcnow
from app.models.wallet_flow import WalletFlowLimits, WalletFlowResponse
from app.providers.alchemy_transfers import AlchemyTransfersProvider
from app.providers.base import ProviderError

router = APIRouter(prefix="/v1/wallets", tags=["wallet-flow"])
_ADDRESS = re.compile(r"^0x[a-fA-F0-9]{40}$")


@router.get(
    "/{chain_id}/{address}/flow",
    response_model=WalletFlowResponse,
    summary="Acquire incoming and outgoing transfers for a public wallet",
)
async def wallet_flow(
    chain_id: int,
    address: str,
    limit: int = Query(default=25, ge=1, le=100),
    settings: Settings = Depends(get_settings),
) -> WalletFlowResponse:
    if chain_id != 1:
        raise HTTPException(
            status_code=422,
            detail="Only Ethereum Mainnet (chain_id 1) is supported in this MVP.",
        )
    if not _ADDRESS.fullmatch(address):
        raise HTTPException(
            status_code=422,
            detail="Address must be 0x followed by 40 hexadecimal characters.",
        )
    if not settings.alchemy_configured:
        raise HTTPException(
            status_code=503,
            detail="Alchemy is not configured in the backend. Set V52_ALCHEMY_ETH_RPC_URL.",
        )

    provider = AlchemyTransfersProvider(settings.alchemy_eth_rpc_url)
    try:
        incoming, outgoing = await asyncio.gather(
            provider.acquire(address=address, direction="IN", limit=limit),
            provider.acquire(address=address, direction="OUT", limit=limit),
        )
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    warnings = [
        "This view contains direct native/ERC-20 transfers only; "
        "internal protocol semantics are not inferred.",
        "A connection is evidence of transfer, not proof of identity, ownership or wrongdoing.",
    ]
    return WalletFlowResponse(
        address=address.lower(),
        acquired_at=utcnow(),
        incoming=incoming,
        outgoing=outgoing,
        limits=WalletFlowLimits(
            requested_per_direction=limit,
            returned_incoming=len(incoming),
            returned_outgoing=len(outgoing),
            truncated=len(incoming) == limit or len(outgoing) == limit,
        ),
        warnings=warnings,
    )
