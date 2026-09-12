"""
Tests for Evidence Vault (append-only, SHA-256, no overwrite).

These tests run entirely without network access or live credentials.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evidence.preservation import canonicalize, sha256_of, sha256_of_canonical
from app.storage.evidence_vault import EvidenceVault, EvidenceVaultError

# ── Preservation helpers ──────────────────────────────────────────────────────

def test_canonicalize_is_deterministic() -> None:
    data = {"b": 2, "a": 1, "c": [3, 1, 2]}
    assert canonicalize(data) == canonicalize(data)


def test_canonicalize_sorts_keys() -> None:
    a = canonicalize({"z": 1, "a": 2})
    b = canonicalize({"a": 2, "z": 1})
    assert a == b


def test_sha256_of_canonical_stable() -> None:
    data = {"tx": "0xabc", "block": 100}
    h1 = sha256_of_canonical(data)
    h2 = sha256_of_canonical(data)
    assert h1 == h2
    assert len(h1) == 64  # hex SHA-256


def test_sha256_of_canonical_different_for_different_data() -> None:
    h1 = sha256_of_canonical({"a": 1})
    h2 = sha256_of_canonical({"a": 2})
    assert h1 != h2


# ── EvidenceVault ─────────────────────────────────────────────────────────────

def test_preserve_raw_writes_files(tmp_data_dir: Path) -> None:
    vault = EvidenceVault(tmp_data_dir)
    raw_path, digest = vault.preserve_raw("case_1", "ev_test_001", {"key": "value"})

    assert raw_path.endswith(".json")
    assert len(digest) == 64
    full = tmp_data_dir / raw_path
    assert full.exists()


def test_preserve_raw_sha256_sidecar(tmp_data_dir: Path) -> None:
    vault = EvidenceVault(tmp_data_dir)
    raw_path, digest = vault.preserve_raw("case_1", "ev_test_002", {"x": 42})

    sidecar = (tmp_data_dir / raw_path).with_suffix(".sha256")
    assert sidecar.exists()
    assert sidecar.read_text().strip() == digest


def test_preserve_raw_refuses_overwrite(tmp_data_dir: Path) -> None:
    vault = EvidenceVault(tmp_data_dir)
    vault.preserve_raw("case_1", "ev_same", {"first": True})

    with pytest.raises(EvidenceVaultError, match="append-only"):
        vault.preserve_raw("case_1", "ev_same", {"second": True})


def test_verify_raw_passes_for_unmodified(tmp_data_dir: Path) -> None:
    vault = EvidenceVault(tmp_data_dir)
    raw_path, digest = vault.preserve_raw("case_2", "ev_verify", {"data": "ok"})

    assert vault.verify_raw(raw_path, digest) is True


def test_verify_raw_fails_for_modified_file(tmp_data_dir: Path) -> None:
    vault = EvidenceVault(tmp_data_dir)
    raw_path, digest = vault.preserve_raw("case_3", "ev_tamper", {"data": "original"})

    # Tamper with the file directly.
    full_path = tmp_data_dir / raw_path
    full_path.write_bytes(b'{"data":"tampered"}')

    assert vault.verify_raw(raw_path, digest) is False


def test_verify_raw_fails_for_missing_file(tmp_data_dir: Path) -> None:
    vault = EvidenceVault(tmp_data_dir)
    assert vault.verify_raw("raw/nonexistent/ev.json", "a" * 64) is False


def test_hash_computed_before_transform(tmp_data_dir: Path) -> None:
    """The stored hash must match the canonical JSON at write time, not a transformed form."""
    vault = EvidenceVault(tmp_data_dir)
    payload = {"tx": "0xabc", "block": 100}
    raw_path, digest = vault.preserve_raw("case_4", "ev_raw_hash", payload)

    stored_bytes = (tmp_data_dir / raw_path).read_bytes()
    expected_digest = sha256_of(stored_bytes)
    assert digest == expected_digest


def test_list_case_files(tmp_data_dir: Path) -> None:
    vault = EvidenceVault(tmp_data_dir)
    vault.preserve_raw("case_5", "ev_a", {"a": 1})
    vault.preserve_raw("case_5", "ev_b", {"b": 2})

    files = vault.list_case_files("case_5")
    assert len(files) == 2
    assert all(f.endswith(".json") for f in files)
    assert files == sorted(files)  # must be sorted


def test_list_case_files_empty_for_unknown_case(tmp_data_dir: Path) -> None:
    vault = EvidenceVault(tmp_data_dir)
    assert vault.list_case_files("nonexistent_case") == []
