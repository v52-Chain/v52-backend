"""Optional x402 middleware for machine-to-machine paid investigations."""

from __future__ import annotations

import logging
from typing import cast

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.facilitator_client import AuthHeaders
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.schemas import Network
from x402.server import x402ResourceServer

from app.config import Settings

logger = logging.getLogger(__name__)


class FacilitatorFailoverMiddleware:
    """Turn an unreachable x402 facilitator into a clean 503, not a raw 500.

    The x402 SDK lazily calls the facilitator's `/supported` endpoint on the
    first request to a protected route (`x402ResourceServer.initialize()`).
    If the facilitator (OpenZeppelin Relayer) is down or its tunnel expired,
    that call raises a plain `httpx` transport error or `ValueError` deep
    inside third-party middleware, which would otherwise surface to callers
    as an opaque 500. MCP/agent clients need a distinguishable, retryable
    signal instead.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        except (httpx.HTTPError, ValueError) as exc:
            if "facilitator" not in str(exc).lower():
                raise
            logger.error("x402 facilitator is unreachable: %s", exc)
            response = JSONResponse(
                status_code=503,
                content={
                    "error": "x402_facilitator_unavailable",
                    "detail": (
                        "The x402 payment facilitator is temporarily unreachable. "
                        "Retry the request in a few seconds."
                    ),
                },
            )
            await response(scope, receive, send)


class BearerAuthProvider:
    """Adds the OpenZeppelin Relayer API token only to facilitator calls."""

    def __init__(self, token: str) -> None:
        self._headers = {"Authorization": f"Bearer {token}"}

    def get_auth_headers(self) -> AuthHeaders:
        return AuthHeaders(
            verify=self._headers,
            settle=self._headers,
            supported=self._headers,
            bazaar=self._headers,
        )


def configure_x402(app: FastAPI, settings: Settings) -> None:
    """Protect agent routes only when every settlement setting is present."""
    if not settings.x402_configured:
        return

    facilitator = HTTPFacilitatorClient(
        FacilitatorConfig(
            url=settings.v52_x402_facilitator_url,
            auth_provider=BearerAuthProvider(settings.v52_x402_facilitator_api_key),
        )
    )
    server = x402ResourceServer(facilitator)
    network = cast(Network, settings.v52_x402_network)
    server.register(network, ExactEvmServerScheme())

    def _option(amount: str) -> PaymentOption:
        return PaymentOption(
            scheme="exact",
            pay_to=settings.v52_x402_pay_to,
            price={
                "amount": amount,
                "asset": settings.v52_x402_asset,
                "extra": {
                    "name": "USD Coin",
                    "version": "2",
                    "areFeesSponsored": True,
                },
            },
            network=network,
            max_timeout_seconds=300,
        )

    routes: dict[str, RouteConfig] = {
        "POST /v1/agent/investigations/wallet-flow": RouteConfig(
            accepts=[_option(settings.v52_x402_wallet_flow_price)],
            mime_type="application/json",
            description="Vector52 wallet-flow forensic acquisition",
        ),
        # DeFi Subgraph Intel — priced by query cost/value (docs/SUBGRAPHS.md §4):
        # a single chain's top pools is cheapest, a per-pool swap drill-down
        # costs more, and a multi-chain vital-points scan is the most expensive.
        "POST /v1/agent/intel/defi/pools": RouteConfig(
            accepts=[_option(settings.v52_x402_defi_pools_price)],
            mime_type="application/json",
            description="Vector52 DeFi Subgraph Intel — top pools/pairs by liquidity",
        ),
        "POST /v1/agent/intel/defi/pool-activity": RouteConfig(
            accepts=[_option(settings.v52_x402_defi_pool_activity_price)],
            mime_type="application/json",
            description="Vector52 DeFi Subgraph Intel — per-pool swap activity",
        ),
        "POST /v1/agent/intel/defi/scan": RouteConfig(
            accepts=[_option(settings.v52_x402_defi_scan_price)],
            mime_type="application/json",
            description="Vector52 DeFi Subgraph Intel — multi-chain vital-points scan",
        ),
    }
    app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)
    app.add_middleware(FacilitatorFailoverMiddleware)
