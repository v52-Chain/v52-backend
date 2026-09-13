"""Tests for the backend's safe MCP status bridge."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.integrations import McpProbe, _mcp_http_base
from app.config import Settings, get_settings
from app.main import app
from app.models.integrations import McpToolDescriptor


def _settings(tmp_path: Path, *, mcp_server_url: str = "") -> Settings:
    return Settings(
        _env_file=None,
        V52_ENV="development",
        V52_MCP_SERVER_URL=mcp_server_url,
        V52_GRAPH_ENDPOINT="",
        V52_DATA_DIR=str(tmp_path),
    )


def _ready_probe() -> McpProbe:
    return McpProbe(
        ready=True,
        reason="MCP handshake verified; agents can call the paid Vector52 backend.",
        service="vector52-mcp",
        version="1.1.0",
        backend_ready=True,
        tools=[
            McpToolDescriptor(
                name="vector52_status",
                description="Status",
                payment="FREE",
            ),
            McpToolDescriptor(
                name="vector52_wallet_flow",
                description="Wallet investigation",
                payment="X402",
                price_atomic="1000",
            ),
        ],
    )


def test_mcp_url_normalization() -> None:
    assert _mcp_http_base("https://mcp.example/mcp") == "https://mcp.example"
    assert _mcp_http_base("https://mcp.example/service/mcp") == "https://mcp.example/service"


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
    assert "V52_MCP_SERVER_URL" in body["reason"]


def test_mcp_status_reports_ready_only_after_verified_probe(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    async def fake_probe(_url: str) -> McpProbe:
        return _ready_probe()

    monkeypatch.setattr("app.api.integrations._probe_mcp", fake_probe)
    app.dependency_overrides[get_settings] = lambda: _settings(
        tmp_path, mcp_server_url="https://mcp.example/mcp"
    )
    try:
        response = client.get("/v1/integrations/mcp/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "READY"
    assert body["service"] == "vector52-mcp"
    assert body["backend_ready"] is True


def test_mcp_tools_returns_only_verified_live_catalog(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    async def fake_probe(_url: str) -> McpProbe:
        return _ready_probe()

    monkeypatch.setattr("app.api.integrations._probe_mcp", fake_probe)
    app.dependency_overrides[get_settings] = lambda: _settings(
        tmp_path, mcp_server_url="https://mcp.example/mcp"
    )
    try:
        response = client.get("/v1/integrations/mcp/tools")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "READY"
    assert {tool["name"] for tool in body["tools"]} == {
        "vector52_status",
        "vector52_wallet_flow",
    }
    paid = next(tool for tool in body["tools"] if tool["payment"] == "X402")
    assert paid["price_atomic"] == "1000"


def test_failed_probe_never_fabricates_ready(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    async def fake_probe(_url: str) -> McpProbe:
        return McpProbe(reason="unreachable")

    monkeypatch.setattr("app.api.integrations._probe_mcp", fake_probe)
    app.dependency_overrides[get_settings] = lambda: _settings(
        tmp_path, mcp_server_url="https://mcp.example/mcp"
    )
    try:
        status = client.get("/v1/integrations/mcp/status")
        tools = client.get("/v1/integrations/mcp/tools")
    finally:
        app.dependency_overrides.clear()

    assert status.json()["state"] == "UNKNOWN"
    assert tools.json()["tools"] == []


def test_backend_never_commands_wallet_bearing_mcp(
    client: TestClient, tmp_path: Path
) -> None:
    app.dependency_overrides[get_settings] = lambda: _settings(
        tmp_path, mcp_server_url="https://mcp.example/mcp"
    )
    try:
        response = client.post(
            "/v1/agent-jobs",
            json={"tool_name": "vector52_wallet_flow", "arguments": {}},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 405
    assert "Claude/Codex" in response.json()["detail"]


def test_get_agent_job_is_not_a_fake_job(client: TestClient) -> None:
    response = client.get("/v1/agent-jobs/job_does_not_exist")
    assert response.status_code == 404
