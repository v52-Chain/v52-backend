"""
Tests for HSK anchoring: POST /v1/cases/{case_id}/anchor and GET /v1/anchors/{root}.

Two layers:
  - API-level tests use a fake HskRegistryClient (monkeypatched into
    app.api.anchor) so they never touch a network — they verify request
    validation, status/error mapping and the idempotent-replay branch.
  - A small set of unit tests exercise the pure hex/bytes32 helpers.
  - One live, read-only test (skipped unless HSK is configured) queries the
    real deployed contract on HSK testnet for the smoke-test anchor recorded
    in v52-onchain/deployments/hsk-testnet.json — no mocks, no gas cost.
"""

from __future__ import annotations

import io
import json
import os
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.models.claim import CaseRecord, CaseStatus
from app.onchain import hsk_registry as hsk_registry_module
from app.onchain.hsk_registry import (
    AnchorRecord,
    AnchorTxResult,
    HskRegistryError,
    _hex,
    _to_bytes32,
)
from app.storage.case_repository import FileCaseRepository

CASE_ID = "case_1_deadbeef_d8da6b_9f2a1b3c"
MANIFEST_ROOT = "0x" + "11" * 32
METHOD_HASH = "0x" + "22" * 32
ISSUER = "0x0f26475928053737C3CCb143Ef9B28F8eDab04C7"
ZERO_HEX = "0x" + "00" * 32


def _configured_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        V52_ENV="development",
        V52_DATA_DIR=str(tmp_path),
        HSK_RPC_URL="https://testnet.hsk.xyz",
        HSK_EVIDENCE_REGISTRY_ADDRESS="0x3422820Ef9FBC8e0206E4CBcB6369dBd14BE18c4",
        HSK_ANCHOR_PRIVATE_KEY="0x" + "aa" * 32,
    )


def _unconfigured_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        V52_ENV="development",
        V52_DATA_DIR=str(tmp_path),
        HSK_RPC_URL="",
        HSK_EVIDENCE_REGISTRY_ADDRESS="",
        HSK_ANCHOR_PRIVATE_KEY="",
    )


async def _seed_case(tmp_path: Path, case_id: str = CASE_ID) -> None:
    repo = FileCaseRepository(tmp_path)
    now = datetime.now(UTC)
    await repo.save(
        CaseRecord(
            case_id=case_id,
            chain_id=1,
            transaction_hash="0x" + "aa" * 32,
            subject="0x" + "bb" * 20,
            claim="test claim",
            status=CaseStatus.COMPLETE,
            created_at=now,
            updated_at=now,
        )
    )


def _write_package(tmp_path: Path, case_id: str = CASE_ID, include_manifest: bool = True) -> None:
    packages_dir = tmp_path / "packages"
    packages_dir.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        if include_manifest:
            manifest = {"schema_version": "0.1.0", "case_id": case_id}
            zf.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        else:
            zf.writestr("other.json", "{}")
    (packages_dir / f"{case_id}.v52.zip").write_bytes(buf.getvalue())


class _FakeClient:
    """Stands in for HskRegistryClient in API-level tests. No network calls."""

    def __init__(
        self,
        *,
        get_anchor_sequence: list[AnchorRecord | None] | None = None,
        anchor_return: AnchorTxResult | None = None,
        anchor_raises: Exception | None = None,
        find_tx_return: str | None = None,
    ) -> None:
        self._get_anchor_sequence = list(get_anchor_sequence or [None])
        self._anchor_return = anchor_return
        self._anchor_raises = anchor_raises
        self._find_tx_return = find_tx_return
        self.anchor_calls: list[tuple] = []

    def __call__(self, **kwargs) -> _FakeClient:
        # Used as a drop-in replacement for the HskRegistryClient constructor.
        return self

    def get_anchor(self, manifest_root):
        if len(self._get_anchor_sequence) > 1:
            return self._get_anchor_sequence.pop(0)
        return self._get_anchor_sequence[0]

    def anchor(self, manifest_root, methodology_hash, schema_version, case_id, supersedes):
        self.anchor_calls.append(
            (manifest_root, methodology_hash, schema_version, case_id, supersedes)
        )
        if self._anchor_raises is not None:
            raise self._anchor_raises
        return self._anchor_return

    def find_anchor_tx_hash(self, manifest_root, *, block_number=None):
        return self._find_tx_return


def _install_fake_client(monkeypatch, fake: _FakeClient) -> None:
    monkeypatch.setattr("app.api.anchor.HskRegistryClient", fake)


# ── Unit tests: pure helpers ────────────────────────────────────────────────


def test_hex_normalizes_bytes_without_double_prefix():
    assert _hex(b"\x11" * 32) == "0x" + "11" * 32


def test_hex_normalizes_hexbytes_like_string_input():
    assert _hex("0X" + "AB" * 32) == "0x" + "ab" * 32


def test_to_bytes32_accepts_hex_string():
    assert _to_bytes32("0x" + "ff" * 32) == b"\xff" * 32


def test_to_bytes32_accepts_raw_bytes():
    assert _to_bytes32(b"\x01" * 32) == b"\x01" * 32


def test_to_bytes32_rejects_wrong_length():
    with pytest.raises(HskRegistryError):
        _to_bytes32("0x1234")


def test_to_bytes32_rejects_invalid_hex():
    with pytest.raises(HskRegistryError):
        _to_bytes32("0x" + "zz" * 32)


def test_zero_bytes32_hex_constant():
    assert hsk_registry_module.ZERO_BYTES32_HEX == ZERO_HEX


# ── POST /v1/cases/{case_id}/anchor ─────────────────────────────────────────


def test_anchor_case_503_when_not_configured(client: TestClient, tmp_path: Path) -> None:
    app.dependency_overrides[get_settings] = lambda: _unconfigured_settings(tmp_path)
    try:
        response = client.post(f"/v1/cases/{CASE_ID}/anchor")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503


async def test_anchor_case_404_when_case_missing(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    _install_fake_client(monkeypatch, _FakeClient())
    app.dependency_overrides[get_settings] = lambda: _configured_settings(tmp_path)
    try:
        response = client.post("/v1/cases/does_not_exist/anchor")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404


async def test_anchor_case_404_when_package_missing(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    await _seed_case(tmp_path)
    _install_fake_client(monkeypatch, _FakeClient())
    app.dependency_overrides[get_settings] = lambda: _configured_settings(tmp_path)
    try:
        response = client.post(f"/v1/cases/{CASE_ID}/anchor")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404
    assert "package" in response.json()["detail"].lower()


async def test_anchor_case_400_when_manifest_missing_in_zip(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    await _seed_case(tmp_path)
    _write_package(tmp_path, include_manifest=False)
    _install_fake_client(monkeypatch, _FakeClient())
    app.dependency_overrides[get_settings] = lambda: _configured_settings(tmp_path)
    try:
        response = client.post(f"/v1/cases/{CASE_ID}/anchor")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 400


async def test_anchor_case_success_first_time_calls_anchor_once(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    await _seed_case(tmp_path)
    _write_package(tmp_path)

    record = AnchorRecord(
        manifest_root=MANIFEST_ROOT,
        methodology_hash=METHOD_HASH,
        schema_version="0.1.0",
        case_id=CASE_ID,
        issuer=ISSUER,
        block_number=100,
        timestamp=1_700_000_000,
        supersedes=ZERO_HEX,
        exists=True,
    )
    tx_result = AnchorTxResult(
        tx_hash="0x" + "cc" * 32, block_number=100, gas_used=250_000, status=1
    )
    fake = _FakeClient(get_anchor_sequence=[None, record], anchor_return=tx_result)
    _install_fake_client(monkeypatch, fake)

    app.dependency_overrides[get_settings] = lambda: _configured_settings(tmp_path)
    try:
        response = client.post(f"/v1/cases/{CASE_ID}/anchor")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["already_anchored"] is False
    assert body["tx_hash"] == tx_result.tx_hash
    assert body["issuer"] == ISSUER
    assert body["supersedes"] is None  # zero-hash supersedes is surfaced as null
    assert body["explorer_tx_url"].endswith(tx_result.tx_hash)
    assert len(fake.anchor_calls) == 1


async def test_anchor_case_retries_read_after_write_lag(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    """The record may not be readable on the first read right after mining."""
    import app.api.anchor as anchor_module

    await _seed_case(tmp_path)
    _write_package(tmp_path)

    record = AnchorRecord(
        manifest_root=MANIFEST_ROOT,
        methodology_hash=METHOD_HASH,
        schema_version="0.1.0",
        case_id=CASE_ID,
        issuer=ISSUER,
        block_number=100,
        timestamp=1_700_000_000,
        supersedes=ZERO_HEX,
        exists=True,
    )
    tx_result = AnchorTxResult(
        tx_hash="0x" + "cc" * 32, block_number=100, gas_used=250_000, status=1
    )
    # First get_anchor call (pre-check) -> None. Then two lagging reads after
    # the tx is mined, then finally the record becomes visible.
    fake = _FakeClient(get_anchor_sequence=[None, None, None, record], anchor_return=tx_result)
    _install_fake_client(monkeypatch, fake)

    sleep_calls = []

    async def _fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(anchor_module.asyncio, "sleep", _fake_sleep)

    app.dependency_overrides[get_settings] = lambda: _configured_settings(tmp_path)
    try:
        response = client.post(f"/v1/cases/{CASE_ID}/anchor")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["tx_hash"] == tx_result.tx_hash
    assert len(sleep_calls) == 2  # slept between the two failed re-reads


async def test_anchor_case_is_idempotent_when_already_anchored(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    await _seed_case(tmp_path)
    _write_package(tmp_path)

    record = AnchorRecord(
        manifest_root=MANIFEST_ROOT,
        methodology_hash=METHOD_HASH,
        schema_version="0.1.0",
        case_id=CASE_ID,
        issuer=ISSUER,
        block_number=100,
        timestamp=1_700_000_000,
        supersedes=ZERO_HEX,
        exists=True,
    )
    fake = _FakeClient(get_anchor_sequence=[record], find_tx_return="0x" + "dd" * 32)
    _install_fake_client(monkeypatch, fake)

    app.dependency_overrides[get_settings] = lambda: _configured_settings(tmp_path)
    try:
        response = client.post(f"/v1/cases/{CASE_ID}/anchor")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["already_anchored"] is True
    assert fake.anchor_calls == []  # never re-submitted a tx


async def test_anchor_case_maps_retryable_error_to_502(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    await _seed_case(tmp_path)
    _write_package(tmp_path)
    fake = _FakeClient(anchor_raises=HskRegistryError("rpc down", retryable=True))
    _install_fake_client(monkeypatch, fake)

    app.dependency_overrides[get_settings] = lambda: _configured_settings(tmp_path)
    try:
        response = client.post(f"/v1/cases/{CASE_ID}/anchor")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 502


async def test_anchor_case_maps_non_retryable_error_to_400(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    await _seed_case(tmp_path)
    _write_package(tmp_path)
    fake = _FakeClient(anchor_raises=HskRegistryError("reverted: AlreadyAnchored"))
    _install_fake_client(monkeypatch, fake)

    app.dependency_overrides[get_settings] = lambda: _configured_settings(tmp_path)
    try:
        response = client.post(f"/v1/cases/{CASE_ID}/anchor")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 400


# ── GET /v1/anchors/{manifest_root} ─────────────────────────────────────────


def test_get_anchor_422_on_malformed_root(client: TestClient, tmp_path: Path) -> None:
    app.dependency_overrides[get_settings] = lambda: _configured_settings(tmp_path)
    try:
        response = client.get("/v1/anchors/not-a-hash")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


def test_get_anchor_503_when_not_configured(client: TestClient, tmp_path: Path) -> None:
    app.dependency_overrides[get_settings] = lambda: _unconfigured_settings(tmp_path)
    try:
        response = client.get(f"/v1/anchors/{MANIFEST_ROOT}")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503


def test_get_anchor_404_when_not_found(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    _install_fake_client(monkeypatch, _FakeClient(get_anchor_sequence=[None]))
    app.dependency_overrides[get_settings] = lambda: _configured_settings(tmp_path)
    try:
        response = client.get(f"/v1/anchors/{MANIFEST_ROOT}")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404


def test_get_anchor_200_returns_record(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    record = AnchorRecord(
        manifest_root=MANIFEST_ROOT,
        methodology_hash=METHOD_HASH,
        schema_version="0.1.0",
        case_id=CASE_ID,
        issuer=ISSUER,
        block_number=100,
        timestamp=1_700_000_000,
        supersedes=ZERO_HEX,
        exists=True,
    )
    fake = _FakeClient(get_anchor_sequence=[record], find_tx_return="0x" + "ee" * 32)
    _install_fake_client(monkeypatch, fake)
    app.dependency_overrides[get_settings] = lambda: _configured_settings(tmp_path)
    try:
        response = client.get(f"/v1/anchors/{MANIFEST_ROOT}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == CASE_ID
    assert body["issuer"] == ISSUER
    assert body["supersedes"] is None
    assert body["tx_hash"] == "0x" + "ee" * 32


def test_get_anchor_surfaces_supersedes_when_present(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    other_root = "0x" + "33" * 32
    record = AnchorRecord(
        manifest_root=MANIFEST_ROOT,
        methodology_hash=METHOD_HASH,
        schema_version="0.1.0",
        case_id=CASE_ID,
        issuer=ISSUER,
        block_number=100,
        timestamp=1_700_000_000,
        supersedes=other_root,
        exists=True,
    )
    _install_fake_client(monkeypatch, _FakeClient(get_anchor_sequence=[record]))
    app.dependency_overrides[get_settings] = lambda: _configured_settings(tmp_path)
    try:
        response = client.get(f"/v1/anchors/{MANIFEST_ROOT}")
    finally:
        app.dependency_overrides.clear()
    assert response.json()["supersedes"] == other_root


# ── Live, read-only smoke test against the real HSK testnet deployment ─────

_REAL_HSK_RPC = os.environ.get("HSK_RPC_URL", "")
_REAL_REGISTRY = os.environ.get("HSK_EVIDENCE_REGISTRY_ADDRESS", "")
_SMOKE_TEST_MANIFEST_ROOT = (
    "0x2407b6f2529df3afbb2ab609cb236ff00b8421c7a57f78128ee58ed6d54f5005"
)

requires_live_hsk = pytest.mark.skipif(
    not (_REAL_HSK_RPC and _REAL_REGISTRY),
    reason="HSK_RPC_URL / HSK_EVIDENCE_REGISTRY_ADDRESS not configured; set them in .env "
    "to run the live HSK testnet read-only test",
)


@requires_live_hsk
def test_live_get_anchor_reads_real_smoke_test_record(client: TestClient) -> None:
    """No mocks: reads the real anchor created during deployment verification.

    See v52-onchain/deployments/hsk-testnet.json for the recorded tx hash.
    """
    response = client.get(f"/v1/anchors/{_SMOKE_TEST_MANIFEST_ROOT}")
    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == "case_smoke_test_deploy_verification"
    assert body["schema_version"] == "0.1.0"
    assert body["supersedes"] is None
    assert body["issuer"].lower() == ISSUER.lower()


@requires_live_hsk
def test_live_get_anchor_404_for_unused_root(client: TestClient) -> None:
    never_anchored = "0x" + "ab" * 32
    response = client.get(f"/v1/anchors/{never_anchored}")
    assert response.status_code == 404
