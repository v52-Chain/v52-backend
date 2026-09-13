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
            path = scope.get("path", "")
            is_agent_payment_route = isinstance(path, str) and path.startswith("/v1/agent/")
            if not is_agent_payment_route and "facilitator" not in str(exc).lower():
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


class NoProxyHTTPFacilitatorClient(HTTPFacilitatorClient):
    """HTTP facilitator client that ignores ambient proxy variables.

    x402 payments are server-to-server calls to an explicit facilitator URL.
    Letting `httpx` inherit HTTP_PROXY/HTTPS_PROXY from a developer shell can
    make local tests fail even while `curl` reaches the facilitator directly.
    """

    def _get_sync_client(self) -> httpx.Client:
        return httpx.Client(timeout=self._timeout, follow_redirects=True, trust_env=False)

    def _get_async_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                trust_env=False,
            )
        return self._http_client


def configure_x402(app: FastAPI, settings: Settings) -> None:
    """Protect agent routes only when every settlement setting is present."""
    if not settings.x402_configured:
        return

    facilitator = NoProxyHTTPFacilitatorClient(
        FacilitatorConfig(
            url=settings.v52_x402_facilitator_url,
            auth_provider=BearerAuthProvider(settings.v52_x402_facilitator_api_key),
        )
    )
    server = x402ResourceServer(facilitator)
    network = cast(Network, settings.v52_x402_network)
    server.register(network, ExactEvmServerScheme())

    routes: dict[str, RouteConfig] = {
        "POST /v1/agent/investigations/wallet-flow": RouteConfig(
            accepts=[
                PaymentOption(
                    scheme="exact",
                    pay_to=settings.v52_x402_pay_to,
                    price={
                        "amount": settings.v52_x402_wallet_flow_price,
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
            ],
            mime_type="application/json",
            description="Vector52 wallet-flow forensic acquisition",
        )
    }
    app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)
    app.add_middleware(FacilitatorFailoverMiddleware)
