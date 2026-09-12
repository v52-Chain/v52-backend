"""Shared deterministic wallet-flow acquisition used by access adapters."""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, date, datetime, time

from fastapi import HTTPException

from app.config import Settings
from app.evidence.provenance import utcnow
from app.models.wallet_flow import WalletFlowLimits, WalletFlowResponse
from app.providers.alchemy_transfers import AlchemyTransfersProvider
from app.providers.base import ProviderError

_ADDRESS = re.compile(r"^0x[a-fA-F0-9]{40}$")


async def acquire_wallet_flow(
    *,
    chain_id: int,
    address: str,
    limit: int,
    from_date: date | None,
    to_date: date | None,
    settings: Settings,
) -> WalletFlowResponse:
    """Shared deterministic core used by public, web-wallet and agent channels."""
    if chain_id != 1:
        raise HTTPException(
            status_code=422,
            detail="Only Ethereum Mainnet (chain_id 1) is supported in this MVP.",
        )
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be before or equal to to_date.")
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
    from_datetime = datetime.combine(from_date, time.min, tzinfo=UTC) if from_date else None
    to_datetime = datetime.combine(to_date, time.max, tzinfo=UTC) if to_date else None
    max_pages = 10 if from_date or to_date else 1
    try:
        incoming, outgoing = await asyncio.gather(
            provider.acquire(
                address=address,
                direction="IN",
                limit=limit,
                from_datetime=from_datetime,
                to_datetime=to_datetime,
                max_pages=max_pages,
            ),
            provider.acquire(
                address=address,
                direction="OUT",
                limit=limit,
                from_datetime=from_datetime,
                to_datetime=to_datetime,
                max_pages=max_pages,
            ),
        )
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    warnings = [
        "This view contains direct native/ERC-20 transfers only; "
        "internal protocol semantics are not inferred.",
        "A connection is evidence of transfer, not proof of identity, ownership or wrongdoing.",
    ]
    if from_date or to_date:
        warnings.append(
            "The date window is filtered from paginated Alchemy metadata and capped at "
            f"{max_pages} pages per direction; absence of results is not proof of no activity."
        )
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
            from_date=from_date,
            to_date=to_date,
            max_pages_per_direction=max_pages,
        ),
        warnings=warnings,
    )
