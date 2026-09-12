"""Optional x402 middleware for machine-to-machine paid investigations."""

from __future__ import annotations

from typing import cast

from fastapi import FastAPI
from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.facilitator_client import AuthHeaders
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.schemas import Network
from x402.server import x402ResourceServer

from app.config import Settings


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
