"""Best-effort persistence of WalletFlowResponse into Supabase for the graph/dashboard.

This is NOT part of the evidence chain: acquisition, hashing and the API
response returned to the caller never depend on this succeeding. It calls the
single RPC granted to `service_role` in the schema — `graph_ingest_wallet_flow`
— defined in `v52-supabase/supabase/migrations/`. See
docs/SUPABASE_GRAPH_DATA_MODEL.md for the full data model and rationale.

The service-role key is backend-only. It is never returned in a response, and
this module never logs it (see app/providers/base.py:redact for the pattern
followed here).
"""

from __future__ import annotations

import logging
from typing import Literal

import httpx

from app.config import Settings
from app.models.wallet_flow import WalletFlowResponse

logger = logging.getLogger(__name__)

_RPC_PATH = "/rest/v1/rpc/graph_ingest_wallet_flow"

GraphChannel = Literal["WEB", "AGENT_X402", "INTERNAL"]


async def ingest_wallet_flow(
    *,
    result: WalletFlowResponse,
    channel: GraphChannel,
    settings: Settings,
    actor_wallet: str | None = None,
    external_request_id: str | None = None,
) -> None:
    """Persist one investigation snapshot. Never raises — logs and returns on failure.

    Safe to call unconditionally: it no-ops when Supabase isn't configured, so
    callers don't need to guard on `settings.supabase_configured` themselves.
    """
    if not settings.supabase_configured:
        return

    url = settings.v52_supabase_url.rstrip("/") + _RPC_PATH
    headers = {
        "apikey": settings.v52_supabase_service_role_key,
        "authorization": f"Bearer {settings.v52_supabase_service_role_key}",
        "content-type": "application/json",
    }
    payload = {
        "p_result": result.model_dump(mode="json"),
        "p_channel": channel,
        "p_actor_wallet": actor_wallet,
        "p_external_request_id": external_request_id,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        logger.warning(
            "Supabase graph ingestion request failed: %s (channel=%s)",
            exc.__class__.__name__,
            channel,
        )
        return

    if response.status_code >= 400:
        # PostgREST error bodies are JSON with message/details/hint — never raw
        # SQL state that might embed input values, but truncate defensively.
        logger.warning(
            "Supabase graph ingestion failed: HTTP %s (channel=%s) %s",
            response.status_code,
            channel,
            response.text[:300],
        )
