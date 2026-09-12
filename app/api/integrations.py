"""Agent Access integration surface consumed by the frontend PWA.

Per CONTRATO-INTEGRACION.md: "La PWA no habla directamente con un proceso MCP
privilegiado. Consulta al backend de Vector52." These endpoints let the
frontend show MCP-related UI state without ever holding a direct connection
to `v52-mcp` (a separate repository/process).

Rule enforced here: "Mientras v52-mcp no esté conectado y probado, status
debe devolver UNAVAILABLE o INTEGRATION_PENDING. La interfaz nunca
transforma un mock en READY." `v52_mcp_server_url` is empty until a real
MCP server is wired up, so every response below reports UNAVAILABLE with an
honest reason instead of simulating success.
"""

from __future__ import annotations

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
    "v52-mcp is a separate service that is not connected to this backend yet. "
    "See docs/ARQUITECTURA-REPOSITORIOS.md and CONTRATO-INTEGRACION.md."
)

# Documented P0 tool catalog (PROYECTO-FINAL.md §8 / CONTRATO-INTEGRACION.md
# "MCP mapping"). Shown to the frontend as a preview of what will exist once
# v52-mcp is connected — never presented as callable today.
_DOCUMENTED_TOOLS: list[McpToolDescriptor] = [
    McpToolDescriptor(name="case_status", description="Estado y warnings del caso.", payment="FREE"),
    McpToolDescriptor(name="evidence_get", description="Evidencia por ID.", payment="FREE"),
    McpToolDescriptor(
        name="edge_explain", description="Por qué existe una relación (WHY THIS LINK?).", payment="FREE"
    ),
    McpToolDescriptor(name="package_verify", description="Verifica un paquete .v52.", payment="FREE"),
    McpToolDescriptor(
        name="anchor_lookup", description="Busca procedencia HSK del expediente.", payment="FREE"
    ),
    McpToolDescriptor(
        name="claim_audit",
        description="Ejecuta un análisis costoso acotado (deep/IA).",
        payment="X402",
    ),
]


@router.get(
    "/integrations/mcp/status",
    response_model=McpStatusResponse,
    summary="Report whether the MCP Agent Access channel is connected",
)
async def mcp_status(settings: Settings = Depends(get_settings)) -> McpStatusResponse:
    if not settings.mcp_integration_configured:
        return McpStatusResponse(
            state=McpIntegrationState.UNAVAILABLE,
            server_configured=False,
            reason=_NOT_CONNECTED_REASON,
        )
    # V52_MCP_SERVER_URL is set but no live handshake is implemented yet.
    # Report UNKNOWN rather than fabricating READY from an unverified URL.
    return McpStatusResponse(
        state=McpIntegrationState.UNKNOWN,
        server_configured=True,
        reason="V52_MCP_SERVER_URL is configured but connectivity has not been verified.",
        warnings=["MCP handshake is not implemented; configuring the URL alone does not mean READY."],
    )


@router.get(
    "/integrations/mcp/tools",
    response_model=McpToolsResponse,
    summary="List MCP tools (documented catalog; not callable until v52-mcp is connected)",
)
async def mcp_tools(settings: Settings = Depends(get_settings)) -> McpToolsResponse:
    if not settings.mcp_integration_configured:
        return McpToolsResponse(
            state=McpIntegrationState.UNAVAILABLE,
            tools=[],
            reason=_NOT_CONNECTED_REASON,
        )
    return McpToolsResponse(
        state=McpIntegrationState.UNKNOWN,
        tools=_DOCUMENTED_TOOLS,
        reason="Catalog reflects the documented P0 tools; live availability is unverified.",
    )


@router.post(
    "/agent-jobs",
    response_model=AgentJobResponse,
    summary="Submit a job to the MCP agent (unavailable until v52-mcp is connected)",
)
async def submit_agent_job(
    body: AgentJobRequest,
    settings: Settings = Depends(get_settings),
) -> AgentJobResponse:
    if not settings.mcp_integration_configured:
        raise HTTPException(
            status_code=503,
            detail=_NOT_CONNECTED_REASON,
        )
    raise HTTPException(
        status_code=503,
        detail=(
            "V52_MCP_SERVER_URL is configured but job dispatch is not implemented yet. "
            "This endpoint will not fabricate a job."
        ),
    )


@router.get(
    "/agent-jobs/{job_id}",
    response_model=AgentJobResponse,
    summary="Read MCP agent job status",
)
async def get_agent_job(job_id: str) -> AgentJobResponse:
    # No agent job can exist yet: submit_agent_job never creates one while
    # v52-mcp is disconnected. A 404 here is accurate, not a placeholder.
    raise HTTPException(
        status_code=404,
        detail=f"Agent job '{job_id}' not found. The MCP agent channel is not connected yet.",
    )
