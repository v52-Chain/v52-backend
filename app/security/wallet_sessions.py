"""Short-lived, single-use wallet challenges and opaque browser sessions."""

from __future__ import annotations

import hashlib
import secrets
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.models.access import WalletChallengeResponse, WalletSessionResponse

_CHALLENGE_TTL = timedelta(minutes=5)
_SESSION_TTL = timedelta(hours=8)


@dataclass(frozen=True)
class ChallengeRecord:
    address: str
    chain_id: int
    message: str
    expires_at: datetime


@dataclass(frozen=True)
class WalletPrincipal:
    address: str
    chain_id: int
    expires_at: datetime


class WalletSessionStore:
    """In-memory MVP store; replace with Redis before horizontally scaling."""

    def __init__(self) -> None:
        self._challenges: dict[str, ChallengeRecord] = {}
        self._sessions: dict[str, WalletPrincipal] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _token_digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _purge(self, now: datetime) -> None:
        self._challenges = {
            key: value for key, value in self._challenges.items() if value.expires_at > now
        }
        self._sessions = {
            key: value for key, value in self._sessions.items() if value.expires_at > now
        }

    def create_challenge(
        self, *, address: str, chain_id: int, public_origin: str
    ) -> WalletChallengeResponse:
        now = datetime.now(UTC)
        expires_at = now + _CHALLENGE_TTL
        nonce = secrets.token_urlsafe(18)
        origin = public_origin.rstrip("/")
        domain = urlparse(origin).netloc or "localhost"
        message = "\n".join(
            (
                f"{domain} wants you to sign in with your Ethereum account:",
                address,
                "",
                "Authenticate this browser session to Vector52. "
                "No blockchain transaction will be sent.",
                "",
                f"URI: {origin}",
                "Version: 1",
                f"Chain ID: {chain_id}",
                f"Nonce: {nonce}",
                f"Issued At: {now.isoformat()}",
                f"Expiration Time: {expires_at.isoformat()}",
            )
        )
        with self._lock:
            self._purge(now)
            self._challenges[nonce] = ChallengeRecord(
                address=address.lower(),
                chain_id=chain_id,
                message=message,
                expires_at=expires_at,
            )
        return WalletChallengeResponse(nonce=nonce, message=message, expires_at=expires_at)

    def verify_challenge(
        self, *, nonce: str, message: str, signature: str
    ) -> WalletSessionResponse:
        now = datetime.now(UTC)
        with self._lock:
            self._purge(now)
            record = self._challenges.pop(nonce, None)
        if record is None or record.expires_at <= now:
            raise HTTPException(status_code=401, detail="Wallet challenge is invalid or expired.")
        if not secrets.compare_digest(record.message, message):
            raise HTTPException(
                status_code=401, detail="Signed message does not match the challenge."
            )
        try:
            recovered = Account.recover_message(
                encode_defunct(text=message), signature=signature
            ).lower()
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Wallet signature is invalid.") from exc
        if not secrets.compare_digest(recovered, record.address):
            raise HTTPException(status_code=401, detail="Signature does not belong to the wallet.")

        token = secrets.token_urlsafe(32)
        expires_at = now + _SESSION_TTL
        principal = WalletPrincipal(
            address=record.address,
            chain_id=record.chain_id,
            expires_at=expires_at,
        )
        with self._lock:
            self._sessions[self._token_digest(token)] = principal
        return WalletSessionResponse(
            access_token=token,
            address=principal.address,
            chain_id=principal.chain_id,
            expires_at=principal.expires_at,
        )

    def resolve(self, token: str) -> WalletPrincipal | None:
        now = datetime.now(UTC)
        with self._lock:
            self._purge(now)
            return self._sessions.get(self._token_digest(token))


wallet_sessions = WalletSessionStore()
bearer = HTTPBearer(auto_error=False)


def get_wallet_sessions() -> WalletSessionStore:
    return wallet_sessions


async def require_wallet_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    store: WalletSessionStore = Depends(get_wallet_sessions),
) -> WalletPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="A verified wallet session is required.")
    principal = store.resolve(credentials.credentials)
    if principal is None:
        raise HTTPException(status_code=401, detail="Wallet session is invalid or expired.")
    return principal
