"""Tests for the Agent Access / MCP integration surface (CONTRATO-INTEGRACION.md).

These endpoints are consumed by the frontend PWA, never by a live MCP
process (v52-mcp is a separate, not-yet-connected service). Every test here
asserts the honesty rule: while V52_MCP_SERVER_URL is unset, responses must
report UNAVAILABLE, never a mock promoted to READY.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


def _settings(tmp_path: Path, *, mcp_server_url: str = "") -> Settings:
    return Settings(
        _env_file=None,
        V52_ENV="development",
        V52_MCP_SERVER_URL=mcp_server_url,
        V52_GRAPH_ENDPOINT="",
        V52_DATA_DIR=str(tmp_path),
    )


def test_mcp_status_reports_unavailable_when_not_configured(
    client: TestClient, tmp_path: Path
) -> None:
    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path)
    try:
        response = client.get("/v1/integrations/mcp/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "UNAVAILABLE"
    assert body["server_configured"] is False
    assert "v52-mcp" in body["reason"]


def test_mcp_status_reports_unknown_when_url_set_but_unverified(
    client: TestClient, tmp_path: Path
) -> None:
    app.dependency_overrides[get_settings] = lambda: _settings(
        tmp_path, mcp_server_url="https://mcp.example.internal"
    )
    try:
        response = client.get("/v1/integrations/mcp/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "UNKNOWN"
    assert body["server_configured"] is True
    # Never fabricate READY just because a URL is present.
    assert body["state"] != "READY"


def test_mcp_tools_empty_when_not_configured(client: TestClient, tmp_path: Path) -> None:
    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path)
    try:
        response = client.get("/v1/integrations/mcp/tools")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "UNAVAILABLE"
    assert body["tools"] == []


def test_mcp_tools_shows_documented_catalog_when_configured(
    client: TestClient, tmp_path: Path
) -> None:
    app.dependency_overrides[get_settings] = lambda: _settings(
        tmp_path, mcp_server_url="https://mcp.example.internal"
    )
    try:
        response = client.get("/v1/integrations/mcp/tools")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    tool_names = {tool["name"] for tool in body["tools"]}
    assert "case_status" in tool_names
    assert "claim_audit" in tool_names
    claim_audit = next(tool for tool in body["tools"] if tool["name"] == "claim_audit")
    assert claim_audit["payment"] == "X402"


def test_submit_agent_job_rejects_when_mcp_not_connected(
    client: TestClient, tmp_path: Path
) -> None:
    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path)
    try:
        response = client.post(
            "/v1/agent-jobs",
            json={"tool_name": "case_status", "arguments": {"case_id": "case_1"}},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "v52-mcp" in response.json()["detail"]


def test_submit_agent_job_never_fabricates_success_even_when_configured(
    client: TestClient, tmp_path: Path
) -> None:
    app.dependency_overrides[get_settings] = lambda: _settings(
        tmp_path, mcp_server_url="https://mcp.example.internal"
    )
    try:
        response = client.post(
            "/v1/agent-jobs",
            json={"tool_name": "case_status", "arguments": {}},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503


def test_get_agent_job_always_404_since_none_can_exist(client: TestClient) -> None:
    response = client.get("/v1/agent-jobs/job_does_not_exist")
    assert response.status_code == 404
    assert "not connected" in response.json()["detail"]
