"""
Protocol models — Uniswap V3 types and stubs.

These types define the interface that the Uniswap V3 resolver (Jhamil) must
populate.  Saúl owns the type definitions; Jhamil owns the implementation
in app/protocols/uniswap_v3.py.

Rule from architecture doc section 11:
  PROTOCOL VOLUME != SUBJECT CONTRIBUTION
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class TokenInfo(BaseModel):
    """ERC-20 token metadata."""

    address: str = Field(description="Checksummed ERC-20 contract address.")
    symbol: str | None = None
    decimals: int | None = None
    name: str | None = None


class SwapEvent(BaseModel):
    """
    Decoded Uniswap V3 Swap event.
    Amounts use Decimal to avoid float binary representation errors.
    Missing token metadata produces a WARNING, not a fabricated value.
    """

    pool_address: str
    token0: TokenInfo
    token1: TokenInfo
    sender: str
    recipient: str
    router: str | None = None
    # Amounts stored as strings to preserve exactness; parse with Decimal.
    amount0: str = Field(description="Raw amount0 as signed integer string (can be negative).")
    amount1: str = Field(description="Raw amount1 as signed integer string (can be negative).")
    amount_in_raw: str = Field(description="Absolute input amount in raw token units (string).")
    amount_out_raw: str = Field(description="Absolute output amount in raw token units (string).")
    token_in: TokenInfo
    token_out: TokenInfo
    sqrt_price_x96: str | None = None
    liquidity: str | None = None
    tick: int | None = None
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Evidence record IDs (L0/L1) that support this decoded event.",
    )
    warnings: list[str] = Field(default_factory=list)


class ProtocolAction(BaseModel):
    """
    Normalised Uniswap V3 action derived from on-chain evidence.
    Subject contribution is separate from protocol volume.
    """

    protocol: str = Field(default="uniswap_v3")
    action: str = Field(default="swap")
    swap: SwapEvent | None = None
    subject_address: str | None = None
    # Subject contribution — computed by Contribution Analysis, not here.
    contribution_evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    # Computed field: True only if subject's direct contribution can be proven.
    subject_contribution_proven: bool = False
    # If True, presence of Permit2/account-abstraction/router adds WARNING.
    ambiguous_intermediary: bool = False

    @property
    def amount_in(self) -> Decimal | None:
        """Input amount as Decimal; None if swap is missing or amount unresolvable."""
        if self.swap is None:
            return None
        try:
            return Decimal(self.swap.amount_in_raw)
        except Exception:
            return None

    @property
    def amount_out(self) -> Decimal | None:
        """Output amount as Decimal; None if swap is missing or amount unresolvable."""
        if self.swap is None:
            return None
        try:
            return Decimal(self.swap.amount_out_raw)
        except Exception:
            return None
