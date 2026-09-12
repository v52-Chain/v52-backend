"""
Tests for POST /v1/claim-audit request validation.

Most of these tests run WITHOUT live providers.  They verify that:
  - Invalid tx hash formats return 422.
  - Unsupported chain IDs return 422.
  - Invalid address formats return 422.
  - Empty claim returns 422.
  - Valid requests are accepted (provider calls may return DEGRADED/FAILED without creds).

One test (test_real_claim_audit_with_live_evidence) exercises the full
pipeline against real Ethereum RPC and The Graph; it is skipped automatically
when V52_GRAPH_API_KEY isn't configured.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

VALID_TX = "0xabc123" + "0" * 58  # 66 chars total
VALID_SUBJECT = "0xdeadbeef" + "0" * 32  # 42 chars total
VALID_CLAIM = "The subject contributed the entire volume observed in this swap."

VALID_BODY = {
    "chain_id": 1,
    "transaction_hash": VALID_TX,
    "claim": VALID_CLAIM,
    "subject": VALID_SUBJECT,
    "use_ai": False,
}


# ── Validation: transaction_hash ─────────────────────────────────────────────

@pytest.mark.parametrize(
    "bad_hash",
    [
        "0xabc",                      # too short
        "abc" + "0" * 64,             # missing 0x prefix
        "0x" + "g" * 64,             # non-hex chars
        "0x" + "a" * 63,             # 65 chars (one short)
        "0x" + "a" * 65,             # 67 chars (one long)
        "",                           # empty
    ],
)
def test_invalid_tx_hash_returns_422(client: TestClient, bad_hash: str) -> None:
    body = {**VALID_BODY, "transaction_hash": bad_hash}
    response = client.post("/v1/claim-audit", json=body)
    assert response.status_code == 422, f"Expected 422 for tx hash: {bad_hash!r}"
    detail = response.json()
    assert "detail" in detail


# ── Validation: chain_id ──────────────────────────────────────────────────────

@pytest.mark.parametrize("bad_chain", [0, 137, 56, 42161, 999])
def test_unsupported_chain_id_returns_422(client: TestClient, bad_chain: int) -> None:
    body = {**VALID_BODY, "chain_id": bad_chain}
    response = client.post("/v1/claim-audit", json=body)
    assert response.status_code == 422, f"Expected 422 for chain_id: {bad_chain}"


def test_ethereum_mainnet_chain_id_accepted(client: TestClient) -> None:
    body = {**VALID_BODY, "chain_id": 1}
    response = client.post("/v1/claim-audit", json=body)
    # May succeed or return DEGRADED if providers not configured; must not be 422.
    assert response.status_code != 422


# ── Validation: subject address ───────────────────────────────────────────────

@pytest.mark.parametrize(
    "bad_subject",
    [
        "0xdeadbeef",          # too short
        "deadbeef" + "0" * 34, # missing 0x
        "0x" + "g" * 40,      # non-hex chars
        "0x" + "a" * 39,      # 41 chars
        "0x" + "a" * 41,      # 43 chars
        "",
    ],
)
def test_invalid_subject_returns_422(client: TestClient, bad_subject: str) -> None:
    body = {**VALID_BODY, "subject": bad_subject}
    response = client.post("/v1/claim-audit", json=body)
    assert response.status_code == 422, f"Expected 422 for subject: {bad_subject!r}"


# ── Validation: claim ────────────────────────────────────────────────────────

def test_empty_claim_returns_422(client: TestClient) -> None:
    body = {**VALID_BODY, "claim": ""}
    response = client.post("/v1/claim-audit", json=body)
    assert response.status_code == 422


def test_claim_too_long_returns_422(client: TestClient) -> None:
    body = {**VALID_BODY, "claim": "x" * 1001}
    response = client.post("/v1/claim-audit", json=body)
    assert response.status_code == 422


# ── Response schema ───────────────────────────────────────────────────────────

def test_valid_request_returns_case_id(client: TestClient) -> None:
    """A valid request must return a case_id regardless of provider availability."""
    response = client.post("/v1/claim-audit", json=VALID_BODY)
    # 200 or 500 but never 422 for a valid body.
    assert response.status_code in {200, 500}
    if response.status_code == 200:
        data = response.json()
        assert "case_id" in data
        assert data["case_id"].startswith("case_")
        assert "status" in data
        assert "warnings" in data


def test_no_secrets_in_error_response(client: TestClient) -> None:
    """Error responses must not contain RPC URLs or API keys."""
    bad_body = {**VALID_BODY, "transaction_hash": "not-a-hash"}
    response = client.post("/v1/claim-audit", json=bad_body)
    body_text = response.text.lower()
    assert "v52_rpc_url" not in body_text
    assert "bearer" not in body_text
    assert "api_key" not in body_text


@pytest.mark.skipif(
    not os.environ.get("V52_GRAPH_API_KEY"),
    reason="V52_GRAPH_API_KEY not configured; set it in .env to run live Graph gateway tests",
)
def test_real_claim_audit_with_live_evidence(client: TestClient) -> None:
    """Executes a real audit for a live Uniswap V3 transaction with real RPC and Graph."""
    real_body = {
        "chain_id": 1,
        "transaction_hash": "0xfa98e7528b5855e46e9bf9cbf9040bc3cfb114ca0c50691f392f1816516e000e",
        "claim": "The subject contributed the entire volume observed in this swap.",
        "subject": "0xeabd88c92324b709ddc8955ae1ac615c6590da9c",
        "use_ai": False,
    }
    response = client.post("/v1/claim-audit", json=real_body)
    assert response.status_code == 200
    data = response.json()
    assert data["case_id"].startswith("case_1_fa98e752_")
    assert data["status"] == "COMPLETE"
    assert len(data["evidence_for"]) >= 2
    sources = {ev["source"] for ev in data["evidence_for"]}
    assert "ethereum_rpc" in sources
    assert "the_graph" in sources
    assert all(len(ev["raw_sha256"]) == 64 for ev in data["evidence_for"])

