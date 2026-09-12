"""Public API models for the wallet flow investigation surface."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class FlowTransfer(BaseModel):
    transfer_id: str
    direction: Literal["IN", "OUT"]
    counterparty: str
    tx_hash: str
    block_number: int | None = None
    timestamp: datetime | None = None
    asset: str = "UNKNOWN"
    category: str
    value: str | None = None
    contract_address: str | None = None
    token_id: str | None = None


class WalletFlowSource(BaseModel):
    provider: Literal["alchemy"] = "alchemy"
    method: Literal["alchemy_getAssetTransfers"] = "alchemy_getAssetTransfers"
    authority: Literal["L1_INDEXED"] = "L1_INDEXED"


class WalletFlowLimits(BaseModel):
    requested_per_direction: int
    returned_incoming: int
    returned_outgoing: int
    truncated: bool
    from_date: date | None = None
    to_date: date | None = None
    max_pages_per_direction: int = 1


class WalletFlowResponse(BaseModel):
    chain_id: Literal[1] = 1
    network: Literal["ethereum-mainnet"] = "ethereum-mainnet"
    address: str
    acquired_at: datetime
    incoming: list[FlowTransfer] = Field(default_factory=list)
    outgoing: list[FlowTransfer] = Field(default_factory=list)
    source: WalletFlowSource = Field(default_factory=WalletFlowSource)
    limits: WalletFlowLimits
    warnings: list[str] = Field(default_factory=list)
