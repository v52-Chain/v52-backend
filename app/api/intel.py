"""Free, unauthenticated DeFi Subgraph Intel status.

Only runs one cheap `_meta` query per chain (indexing status, not pool/swap
data), so unlike the pool/activity/scan surface in app/api/agent.py this stays
outside the x402 channel — it enhances discoverability without incurring the
query cost the paid tier protects.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.api.defi_core import get_chain_status
from app.config import Settings, get_settings
from app.models.defi_intel import ChainKey, DefiEntrypointsStatusResponse

router = APIRouter(prefix="/v1/intel/defi", tags=["defi-intel"])

_CHAINS: tuple[ChainKey, ...] = ("ethereum", "avalanche", "hsk")


@router.get(
    "/status",
    response_model=DefiEntrypointsStatusResponse,
    summary="Report configured DeFi subgraph status for HSK, Avalanche and Ethereum Mainnet",
)
async def defi_status(
    settings: Settings = Depends(get_settings),
) -> DefiEntrypointsStatusResponse:
    """Per-chain subgraph configuration + live indexing status (`_meta`).

    Free discovery surface for the paid pool/activity/scan endpoints under
    `/v1/agent/intel/defi/*`. Never returns pool or swap data itself.
    """
    statuses = list(
        await asyncio.gather(*(get_chain_status(settings, chain) for chain in _CHAINS))
    )
    return DefiEntrypointsStatusResponse(chains=statuses, retrieved_at=datetime.now(UTC))
