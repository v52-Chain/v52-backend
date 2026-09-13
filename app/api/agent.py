"""Machine-facing endpoints consumed by the Vector52 MCP server."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.api.wallet_flow import acquire_wallet_flow
from app.config import Settings, get_settings
from app.models.access import (
    AgentCapabilitiesResponse,
    AgentWalletFlowResponse,
    WalletFlowJobRequest,
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
