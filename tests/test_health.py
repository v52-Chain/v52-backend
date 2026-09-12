"""Tests for GET /healthz."""

from fastapi.testclient import TestClient


def test_healthz_returns_200(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200


def test_healthz_response_schema(client: TestClient) -> None:
    response = client.get("/healthz")
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert isinstance(data["version"], str)


def test_healthz_version_is_semver(client: TestClient) -> None:
    response = client.get("/healthz")
    version = response.json()["version"]
    parts = version.split(".")
    assert len(parts) == 3, f"Expected semver, got: {version}"
    assert all(p.isdigit() for p in parts), f"Non-numeric version part in: {version}"


def test_openapi_schema_available(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    assert "/healthz" in schema["paths"]
