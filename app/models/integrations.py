"""Contracts for the Agent Access integration surface (`CONTRATO-INTEGRACION.md`).

The PWA never talks to a privileged MCP process directly. It consults these
Vector52 backend endpoints instead. While `v52-mcp` is not connected and
verified, every response here must report `UNAVAILABLE` honestly — never a
mock promoted to `READY`.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class McpIntegrationState(StrEnum):
    """States defined by CONTRATO-INTEGRACION.md for the Agent Access interface."""

    UNAVAILABLE = "UNAVAILABLE"
    READY = "READY"
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    RUNNING = "RUNNING"
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class McpToolDescriptor(BaseModel):
    """One live tool advertised by the verified Vector52 MCP service."""

    name: str
    description: str
    payment: Literal["FREE", "X402"]
    price_atomic: str | None = None


class McpStatusResponse(BaseModel):
    state: McpIntegrationState
    server_configured: bool
    reason: str
    service: str | None = None
    version: str | None = None
    backend_ready: bool | None = None
    warnings: list[str] = Field(default_factory=list)


class McpToolsResponse(BaseModel):
    state: McpIntegrationState
    tools: list[McpToolDescriptor] = Field(default_factory=list)
    reason: str


class AgentJobRequest(BaseModel):
    tool_name: str = Field(min_length=1, max_length=100)
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentJobResponse(BaseModel):
    job_id: str
    tool_name: str
    state: McpIntegrationState
    created_at: datetime
    updated_at: datetime
    result: dict[str, Any] | None = None
    reason: str | None = None
