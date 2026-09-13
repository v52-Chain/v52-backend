"""Small, deterministic credit ledger for the Buildathon web access flow.

The in-memory implementation is intentionally isolated behind one interface so it can
be replaced with Redis/PostgreSQL before production. Settlement IDs make grants
idempotent: the same on-chain payment can never mint the pack twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from threading import RLock


@dataclass(frozen=True)
class CreditSnapshot:
    wallet: str
    available: int
    purchased: int
    consumed: int
    updated_at: datetime


class InsufficientCreditsError(Exception):
    """Raised when a wallet attempts paid work without a credit."""


class CreditLedger:
    """Thread-safe Buildathon ledger with idempotent settlement grants."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._balances: dict[str, int] = {}
        self._purchased: dict[str, int] = {}
        self._consumed: dict[str, int] = {}
        self._updated: dict[str, datetime] = {}
        self._settlements: set[str] = set()

    def snapshot(self, wallet: str) -> CreditSnapshot:
        key = wallet.lower()
        with self._lock:
            return CreditSnapshot(
                wallet=key,
                available=self._balances.get(key, 0),
                purchased=self._purchased.get(key, 0),
                consumed=self._consumed.get(key, 0),
                updated_at=self._updated.get(key, datetime.now(UTC)),
            )

    def grant_settled(self, wallet: str, credits: int, settlement_id: str) -> CreditSnapshot:
        if credits < 1:
            raise ValueError("credits must be positive")
        if not settlement_id:
            raise ValueError("settlement_id is required")
        key = wallet.lower()
        with self._lock:
            if settlement_id not in self._settlements:
                self._settlements.add(settlement_id)
                self._balances[key] = self._balances.get(key, 0) + credits
                self._purchased[key] = self._purchased.get(key, 0) + credits
                self._updated[key] = datetime.now(UTC)
            return self.snapshot(key)

    def consume(self, wallet: str) -> CreditSnapshot:
        key = wallet.lower()
        with self._lock:
            if self._balances.get(key, 0) < 1:
                raise InsufficientCreditsError
            self._balances[key] -= 1
            self._consumed[key] = self._consumed.get(key, 0) + 1
            self._updated[key] = datetime.now(UTC)
            return self.snapshot(key)

    def refund(self, wallet: str) -> CreditSnapshot:
        """Return a reserved credit when acquisition fails before delivering a result."""
        key = wallet.lower()
        with self._lock:
            if self._consumed.get(key, 0) > 0:
                self._balances[key] = self._balances.get(key, 0) + 1
                self._consumed[key] -= 1
                self._updated[key] = datetime.now(UTC)
            return self.snapshot(key)

    def clear(self) -> None:
        """Reset state for deterministic tests."""
        with self._lock:
            self._balances.clear()
            self._purchased.clear()
            self._consumed.clear()
            self._updated.clear()
            self._settlements.clear()


@lru_cache(maxsize=1)
def get_credit_ledger() -> CreditLedger:
    return CreditLedger()

