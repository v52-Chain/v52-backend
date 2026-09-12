"""
Base provider interface.

All remote providers must subclass BaseProvider and implement acquire().
Secrets MUST NOT appear in exceptions, log messages, or response bodies.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from app.models.evidence import ProviderStatus

logger = logging.getLogger(__name__)

# Patterns used to detect accidental secret leakage in error strings.
_SECRET_PATTERNS = [
    re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"(?i)(api[_-]?key\s*=\s*)[^\s&]+"),
    re.compile(r"(?i)(token\s*=\s*)[^\s&]+"),
    re.compile(r"(?i)(Authorization:\s*)[^\s]+"),
    # Infura/Alchemy style endpoints that embed keys in the URL path
    re.compile(r"(https?://[^/]+/v\d+/)[A-Za-z0-9_-]{16,}"),
    re.compile(r"(https?://[^/\s]+/(?:v\d+|api)/)[^\s/?#&]+"),
]


def redact(text: str) -> str:
    """Replace known secret patterns with [REDACTED] in a string."""
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(r"\1[REDACTED]", text)
    return text


class ProviderError(Exception):
    """
    Raised when a remote provider returns an error, times out, or is misconfigured.
    The message is always safe to surface in API responses and logs.
    """

    def __init__(
        self,
        message: str,
        status: ProviderStatus = ProviderStatus.FAILED,
        *,
        code: str = "PROVIDER_ERROR",
        retryable: bool = False,
        provider: str | None = None,
    ) -> None:
        super().__init__(redact(message))
        self.status = status
        self.code = code
        self.retryable = retryable
        self.provider = provider

    def to_api_error(self) -> dict[str, object]:
        """Return a contract-safe API error payload."""
        payload: dict[str, object] = {
            "code": self.code,
            "message": str(self),
            "retryable": self.retryable,
        }
        if self.provider:
            payload["provider"] = self.provider
        return payload


class BaseProvider(ABC):
    """
    Abstract base for all remote evidence providers.

    Subclasses must:
      - implement acquire()
      - never include secrets in raised exceptions
      - set a meaningful name and version
    """

    name: str = "base"
    version: str = "0.1.0"

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds
        self._status: ProviderStatus = ProviderStatus.UNKNOWN

    @property
    def status(self) -> ProviderStatus:
        return self._status

    @abstractmethod
    async def acquire(self, **kwargs: Any) -> Any:
        """Acquire evidence from the remote provider.  Must never block indefinitely."""
        ...

    def _set_ok(self) -> None:
        self._status = ProviderStatus.OK

    def _set_failed(self) -> None:
        self._status = ProviderStatus.FAILED

    def _set_degraded(self) -> None:
        self._status = ProviderStatus.DEGRADED

    def _set_timeout(self) -> None:
        self._status = ProviderStatus.TIMEOUT
