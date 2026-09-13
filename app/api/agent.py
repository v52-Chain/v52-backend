"""Machine-facing endpoints consumed by the Vector52 MCP server."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.api.defi_core import run_full_scan, run_pool_activity, run_pools_scan
from app.api.wallet_flow import acquire_wallet_flow
from app.config import Settings, get_settings
from app.models.access import (
    AgentCapabilitiesResponse,
    AgentDefiIntelCapabilities,
    AgentWalletFlowResponse,
    WalletFlowJobRequest,
)
from app.models.defi_intel import (
    AgentDefiPoolActivityResponse,
    AgentDefiPoolsResponse,
    AgentDefiScanResponse,
    DefiPoolActivityJobRequest,
    DefiPoolsJobRequest,
    DefiScanJobRequest,
)

router = APIRouter(prefix="/v1/agent", tags=["agent-x402"])


def _atomic_usdc_to_display(value: str) -> str:
    atomic = int(value)
    whole, fraction = divmod(atomic, 1_000_000)
    return f"{whole}.{fraction:06d}".rstrip("0").rstrip(".")


@router.get("/capabilities", response_model=AgentCapabilitiesResponse)
async def agent_capabilities(
    settings: Settings = Depends(get_settings),
) -> AgentCapabilitiesResponse:
    warnings = []
    if not settings.x402_configured:
        warnings.append(
            "x402 is not ready. Configure and enable the facilitator only after "
            "verify and settle pass."
        )
    return AgentCapabilitiesResponse(
        ready=settings.x402_configured,
        network=settings.v52_x402_network,
        asset=settings.v52_x402_asset,
        pay_to=settings.v52_x402_pay_to,
        amount_atomic=settings.v52_x402_wallet_flow_price,
        amount_display=_atomic_usdc_to_display(settings.v52_x402_wallet_flow_price),
        defi_intel=AgentDefiIntelCapabilities(
            pools_amount_atomic=settings.v52_x402_defi_pools_price,
            pool_activity_amount_atomic=settings.v52_x402_defi_pool_activity_price,
            scan_amount_atomic=settings.v52_x402_defi_scan_price,
        ),
        warnings=warnings,
    )


@router.post(
    "/investigations/wallet-flow",
    response_model=AgentWalletFlowResponse,
    summary="Run an x402-paid wallet investigation for an MCP client",
)
async def agent_wallet_flow(
    body: WalletFlowJobRequest,
    settings: Settings = Depends(get_settings),
) -> AgentWalletFlowResponse:
    if not settings.x402_configured:
        raise HTTPException(
            status_code=503,
            detail="The x402 agent channel is disabled or incompletely configured.",
        )
    result = await acquire_wallet_flow(
        chain_id=body.chain_id,
        address=body.target_address,
        limit=body.limit,
        from_date=body.from_date,
        to_date=body.to_date,
        settings=settings,
    )
    return AgentWalletFlowResponse(
        request_id=f"agent_{uuid.uuid4().hex}",
        result=result,
    )


def _require_x402(settings: Settings) -> None:
    if not settings.x402_configured:
        raise HTTPException(
            status_code=503,
            detail="The x402 agent channel is disabled or incompletely configured.",
        )


@router.post(
    "/intel/defi/pools",
    response_model=AgentDefiPoolsResponse,
    summary="x402-paid: top DeFi pools/pairs by liquidity for one chain (HSK/Avalanche/Ethereum)",
)
async def agent_defi_pools(
    body: DefiPoolsJobRequest,
    settings: Settings = Depends(get_settings),
) -> AgentDefiPoolsResponse:
    """Scan a chain's busiest AMM pools/pairs — the on-chain swap contracts themselves."""
    _require_x402(settings)
    result = await run_pools_scan(settings, chain=body.chain, limit=body.limit)
    return AgentDefiPoolsResponse(request_id=f"agent_{uuid.uuid4().hex}", result=result)


@router.post(
    "/intel/defi/pool-activity",
    response_model=AgentDefiPoolActivityResponse,
    summary="x402-paid: recent swap activity for one specific DeFi pool/pair",
)
async def agent_defi_pool_activity(
    body: DefiPoolActivityJobRequest,
    settings: Settings = Depends(get_settings),
) -> AgentDefiPoolActivityResponse:
    """Drill down into one pool/pair's recent swaps — priced above the pools listing."""
    _require_x402(settings)
    result = await run_pool_activity(
        settings, chain=body.chain, pool_address=body.pool_address, limit=body.limit
    )
    return AgentDefiPoolActivityResponse(request_id=f"agent_{uuid.uuid4().hex}", result=result)


@router.post(
    "/intel/defi/scan",
    response_model=AgentDefiScanResponse,
    summary="x402-paid: multi-chain vital-points DeFi scan (HSK + Avalanche + Ethereum)",
)
async def agent_defi_scan(
    body: DefiScanJobRequest,
    settings: Settings = Depends(get_settings),
) -> AgentDefiScanResponse:
    """Fan out status + top-pools across every requested chain in one paid call."""
    _require_x402(settings)
    result = await run_full_scan(settings, chains=body.chains, pools_limit=body.pools_limit)
    return AgentDefiScanResponse(request_id=f"agent_{uuid.uuid4().hex}", result=result)
