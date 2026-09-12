"""Contracts shared by the browser-wallet and MCP/x402 access channels."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.wallet_flow import WalletFlowResponse

_EVM_ADDRESS_LENGTH = 42


def _validate_address(value: str) -> str:
    normalized = value.strip().lower()
    if (
        len(normalized) != _EVM_ADDRESS_LENGTH
        or not normalized.startswith("0x")
        or any(character not in "0123456789abcdef" for character in normalized[2:])
    ):
        raise ValueError("Expected an EVM address: 0x followed by 40 hexadecimal characters.")
    return normalized


class WalletChallengeRequest(BaseModel):
    address: str
    chain_id: Literal[1, 43113]

    _address = field_validator("address")(_validate_address)


class WalletChallengeResponse(BaseModel):
    nonce: str
    message: str
    expires_at: datetime


class WalletVerifyRequest(BaseModel):
    nonce: str = Field(min_length=16, max_length=128)
    message: str = Field(min_length=40, max_length=4096)
    signature: str = Field(min_length=132, max_length=512)


class WalletSessionResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth token type, not a secret
    address: str
    chain_id: int
    expires_at: datetime


class WalletIdentityResponse(BaseModel):
    channel: Literal["WEB"] = "WEB"
    address: str
    chain_id: int
    expires_at: datetime


class WalletFlowJobRequest(BaseModel):
    target_address: str
    chain_id: Literal[1] = 1
    limit: int = Field(default=25, ge=1, le=100)
    from_date: date | None = None
    to_date: date | None = None

    _target = field_validator("target_address")(_validate_address)

    @model_validator(mode="after")
    def validate_date_window(self) -> WalletFlowJobRequest:
        if self.from_date and self.to_date and self.from_date > self.to_date:
            raise ValueError("from_date must be before or equal to to_date.")
        return self


class WebWalletFlowResponse(BaseModel):
    channel: Literal["WEB"] = "WEB"
    actor_wallet: str
    result: WalletFlowResponse


class AgentWalletFlowResponse(BaseModel):
    channel: Literal["AGENT_X402"] = "AGENT_X402"
    request_id: str
    result: WalletFlowResponse


class AgentCapabilitiesResponse(BaseModel):
    channel: Literal["AGENT_X402"] = "AGENT_X402"
    ready: bool
    endpoint: str = "/v1/agent/investigations/wallet-flow"
    payment_protocol: Literal["x402"] = "x402"
    network: str
    asset: str
    amount_atomic: str
    automatic_payment_owner: Literal["MCP_CLIENT"] = "MCP_CLIENT"
    warnings: list[str] = Field(default_factory=list)
