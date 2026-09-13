"""Tests for FRANCO.md RPC API endpoints."""

from __future__ import annotations

import json
from pathlib import Path

import respx
from fastapi.testclient import TestClient
from httpx import Request, Response

from app.config import Settings, get_settings
from app.main import app

RPC_URL = "https://eth-mainnet.g.alchemy.com/v2/test-secret"
TX_HASH = "0x" + "a" * 64


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        V52_ENV="development",
        ALCHEMY_API_KEY="",
        ALCHEMY_ETH_RPC_URL=RPC_URL,
        ALCHEMY_AVAX_RPC_URL="",
        HSK_RPC_URL="",
        V52_GRAPH_ENDPOINT="",
        V52_DATA_DIR=str(tmp_path),
        RPC_MAX_RETRIES=0,
    )


def _unconfigured_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        V52_ENV="development",
        ALCHEMY_API_KEY="",
        ALCHEMY_ETH_RPC_URL="",
        ALCHEMY_AVAX_RPC_URL="",
        HSK_RPC_URL="",
        V52_GRAPH_ENDPOINT="",
        V52_DATA_DIR=str(tmp_path),
        RPC_MAX_RETRIES=0,
    )


@respx.mock
def test_provider_status_checks_chain_without_leaking_secret(
    client: TestClient,
    tmp_path: Path,
) -> None:
    respx.post(RPC_URL).mock(
        return_value=Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x1"})
    )
    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path)
    try:
        response = client.get("/v1/providers/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["rpc"]["ethereum"]["status"] == "UP"
    assert body["data"]["rpc"]["ethereum"]["chain_id"] == 1
    assert "test-secret" not in response.text


@respx.mock
def test_provider_status_reports_chain_mismatch(
    client: TestClient,
    tmp_path: Path,
) -> None:
    respx.post(RPC_URL).mock(
        return_value=Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0xa86a"})
    )
    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path)
    try:
        response = client.get("/v1/providers/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["rpc"]["ethereum"]["status"] == "DOWN"
    assert body["errors"][0]["code"] == "CHAIN_MISMATCH"
    assert "test-secret" not in response.text


@respx.mock
def test_rpc_transaction_endpoint_preserves_raw_evidence(
    client: TestClient,
    tmp_path: Path,
) -> None:
    def responder(request: Request) -> Response:
        body = json.loads(request.content)
        method = body["method"]
        if method == "eth_chainId":
            result = "0x1"
        elif method == "eth_getTransactionByHash":
            result = {
                "hash": TX_HASH,
                "blockNumber": "0x10",
                "blockHash": "0x" + "b" * 64,
                "from": "0x" + "c" * 40,
                "to": "0x" + "d" * 40,
            }
        else:
            result = None
        return Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": result})

    respx.post(RPC_URL).mock(side_effect=responder)
    app.dependency_overrides[get_settings] = lambda: _settings(tmp_path)
    try:
        response = client.get(f"/v1/rpc/transactions/ethereum/{TX_HASH}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETE"
    assert body["data"]["result"]["hash"] == TX_HASH
    assert body["data"]["evidence"]["raw_sha256"]
    raw_path = tmp_path / body["data"]["evidence"]["raw_path"]
    assert raw_path.exists()
    assert "test-secret" not in response.text


def test_audits_endpoint_creates_readable_job(client: TestClient, tmp_path: Path) -> None:
    app.dependency_overrides[get_settings] = lambda: _unconfigured_settings(tmp_path)
    payload = {
        "chain_id": 1,
        "transaction_hash": TX_HASH,
        "subject": "0x" + "1" * 40,
        "claim": "The full router volume is attributable to the subject.",
        "limits": {"max_hops": 1, "max_events": 500},
        "use_ai": False,
    }
    try:
        response = client.post("/v1/audits", json=payload)
        job_id = response.json()["data"]["job_id"]
        job_response = client.get(f"/v1/audits/{job_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "RUNNING"
    assert job_response.status_code == 200
    assert job_response.json()["data"]["job_id"] == job_id
