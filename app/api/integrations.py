"""Safe status bridge between the PWA/backend and the Vector52 MCP service.

Paid work travels in one direction: agent -> MCP -> x402 -> backend. The PWA
never receives the MCP wallet or its credentials; it only reads these status
endpoints to render honest connection state and the live tool catalog.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.models.integrations import (
    AgentJobRequest,
    AgentJobResponse,
    McpIntegrationState,
    McpStatusResponse,
    McpToolDescriptor,
    McpToolsResponse,
)

router = APIRouter(prefix="/v1", tags=["agent-access"])

_NOT_CONNECTED_REASON = (
    "v52-mcp has not been deployed/configured for this backend. "
    "Set V52_MCP_SERVER_URL to its public /mcp URL."
)


@dataclass
class McpProbe:
    ready: bool = False
    reason: str = "MCP handshake failed."
    service: str | None = None
    version: str | None = None
    backend_ready: bool | None = None
    tools: list[McpToolDescriptor] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _mcp_http_base(raw_url: str) -> str:
    """Normalize an MCP endpoint URL to its public health/capabilities base."""
    parts = urlsplit(raw_url.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("V52_MCP_SERVER_URL must be an HTTP(S) URL.")
    path = parts.path.rstrip("/")
    if path.endswith("/mcp"):
        path = path[:-4]
    return urlunsplit((parts.scheme, parts.netloc, path, "", "")).rstrip("/")


async def _probe_mcp(server_url: str) -> McpProbe:
    try:
        base = _mcp_http_base(server_url)
    except ValueError as exc:
        return McpProbe(reason=str(exc))

    try:
        async with httpx.AsyncClient(timeout=3.0, follow_redirects=False) as client:
            health_response = await client.get(f"{base}/health")
            capabilities_response = await client.get(f"{base}/capabilities")
        health_response.raise_for_status()
        capabilities_response.raise_for_status()
        health = health_response.json()
        capabilities = capabilities_response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return McpProbe(
            reason="The configured MCP service is unreachable or returned an invalid handshake.",
            warnings=[type(exc).__name__],
        )

    service = health.get("service")
    version = health.get("version")
    if health.get("status") != "ok" or service != "vector52-mcp":
        return McpProbe(
            reason="The configured URL did not identify itself as vector52-mcp.",
            service=str(service) if service else None,
            version=str(version) if version else None,
        )

    raw_tools = capabilities.get("tools")
    backend = capabilities.get("backend") or {}
    if not isinstance(raw_tools, list) or capabilities.get("service") != "vector52-mcp":
        return McpProbe(
            reason="The MCP capabilities document is incomplete.",
            service=service,
            version=version,
        )

    tools: list[McpToolDescriptor] = []
    try:
        for item in raw_tools:
            tools.append(
                McpToolDescriptor(
                    name=item["name"],
                    description=item["description"],
                    payment=item["payment"],
                    price_atomic=item.get("priceAtomic"),
                )
            )
    except (KeyError, TypeError, ValueError) as exc:
        return McpProbe(
            reason="The MCP tool catalog does not match the Vector52 contract.",
            service=service,
            version=version,
            warnings=[type(exc).__name__],
        )

    required = {"vector52_status", "vector52_wallet_flow"}
    advertised = {tool.name for tool in tools}
    backend_ready = bool(backend.get("ready"))
    ready = capabilities.get("status") == "READY" and backend_ready and required <= advertised
    return McpProbe(
        ready=ready,
        reason=(
            "MCP handshake verified; agents can call the paid Vector52 backend."
            if ready
            else "MCP responded, but its backend or required tool set is not ready."
        ),
        service=service,
        version=version,
        backend_ready=backend_ready,
        tools=tools,
    )


@router.get("/integrations/mcp/status", response_model=McpStatusResponse)
async def mcp_status(settings: Settings = Depends(get_settings)) -> McpStatusResponse:
    if not settings.mcp_integration_configured:
        return McpStatusResponse(
            state=McpIntegrationState.UNAVAILABLE,
            server_configured=False,
            reason=_NOT_CONNECTED_REASON,
        )
    probe = await _probe_mcp(settings.v52_mcp_server_url)
    return McpStatusResponse(
        state=McpIntegrationState.READY if probe.ready else McpIntegrationState.UNKNOWN,
        server_configured=True,
        reason=probe.reason,
        service=probe.service,
        version=probe.version,
        backend_ready=probe.backend_ready,
        warnings=probe.warnings,
    )


@router.get("/integrations/mcp/tools", response_model=McpToolsResponse)
async def mcp_tools(settings: Settings = Depends(get_settings)) -> McpToolsResponse:
    if not settings.mcp_integration_configured:
        return McpToolsResponse(
            state=McpIntegrationState.UNAVAILABLE,
            tools=[],
            reason=_NOT_CONNECTED_REASON,
        )
    probe = await _probe_mcp(settings.v52_mcp_server_url)
    return McpToolsResponse(
        state=McpIntegrationState.READY if probe.ready else McpIntegrationState.UNKNOWN,
        tools=probe.tools if probe.ready else [],
        reason=probe.reason,
    )


@router.post("/agent-jobs", response_model=AgentJobResponse)
async def submit_agent_job(
    body: AgentJobRequest,
    settings: Settings = Depends(get_settings),
) -> AgentJobResponse:
    # Deliberately no reverse dispatch. The external agent invokes MCP; MCP then
    # invokes this backend with x402. Sending jobs backend -> MCP would create a
    # confused-deputy payment risk and is not needed for the web frontend.
    raise HTTPException(
        status_code=405 if settings.mcp_integration_configured else 503,
        detail=(
            "Agent jobs must be initiated by Claude/Codex through vector52-mcp; "
            "the backend does not remotely command the wallet-bearing MCP service."
            if settings.mcp_integration_configured
            else _NOT_CONNECTED_REASON
        ),
    )


@router.get("/agent-jobs/{job_id}", response_model=AgentJobResponse)
async def get_agent_job(job_id: str) -> AgentJobResponse:
    raise HTTPException(
        status_code=404,
        detail=f"Agent job '{job_id}' not found. Agent results are returned synchronously through MCP.",
    )
