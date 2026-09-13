"""Wallet authentication and authenticated browser investigation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.wallet_flow import acquire_wallet_flow
from app.config import Settings, get_settings
from app.models.access import (
    WalletChallengeRequest,
    WalletChallengeResponse,
    WalletFlowJobRequest,
    WalletIdentityResponse,
    WalletSessionResponse,
    WalletVerifyRequest,
    WebWalletFlowResponse,
)
from app.security.wallet_sessions import (
    WalletPrincipal,
    WalletSessionStore,
    get_wallet_sessions,
    require_wallet_session,
)

router = APIRouter(prefix="/v1", tags=["web-access"])


@router.post("/auth/wallet/challenge", response_model=WalletChallengeResponse)
async def wallet_challenge(
    body: WalletChallengeRequest,
    settings: Settings = Depends(get_settings),
    store: WalletSessionStore = Depends(get_wallet_sessions),
) -> WalletChallengeResponse:
    return store.create_challenge(
        address=body.address,
        chain_id=body.chain_id,
        public_origin=settings.v52_public_origin,
    )


@router.post("/auth/wallet/verify", response_model=WalletSessionResponse)
async def wallet_verify(
    body: WalletVerifyRequest,
    store: WalletSessionStore = Depends(get_wallet_sessions),
) -> WalletSessionResponse:
    return store.verify_challenge(
        nonce=body.nonce,
        message=body.message,
        signature=body.signature,
    )


@router.get("/auth/wallet/me", response_model=WalletIdentityResponse)
async def wallet_me(
    principal: WalletPrincipal = Depends(require_wallet_session),
) -> WalletIdentityResponse:
    return WalletIdentityResponse(
        address=principal.address,
        chain_id=principal.chain_id,
        expires_at=principal.expires_at,
    )


@router.post(
    "/web/investigations/wallet-flow",
    response_model=WebWalletFlowResponse,
    summary="Run a wallet-authenticated browser investigation",
)
async def web_wallet_flow(
    body: WalletFlowJobRequest,
    principal: WalletPrincipal = Depends(require_wallet_session),
    settings: Settings = Depends(get_settings),
) -> WebWalletFlowResponse:
    result = await acquire_wallet_flow(
        chain_id=body.chain_id,
        address=body.target_address,
        limit=body.limit,
        from_date=body.from_date,
        to_date=body.to_date,
        settings=settings,
        channel="WEB",
        actor_wallet=principal.address,
    )
    return WebWalletFlowResponse(actor_wallet=principal.address, result=result)
