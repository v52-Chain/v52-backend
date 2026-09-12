"""Shared public API envelope models."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EnvelopeStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class ApiError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    provider: str | None = None


class ApiEnvelope(BaseModel):
    request_id: str = Field(default_factory=lambda: f"req_{uuid.uuid4().hex[:12]}")
    status: EnvelopeStatus
    data: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[ApiError] = Field(default_factory=list)


def envelope(
    status: EnvelopeStatus,
    *,
    data: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    errors: list[ApiError] | None = None,
) -> ApiEnvelope:
    return ApiEnvelope(
        status=status,
        data=data or {},
        warnings=warnings or [],
        errors=errors or [],
    )
