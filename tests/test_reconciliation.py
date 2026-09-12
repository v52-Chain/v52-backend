"""Tests for Graph/RPC reconciliation."""

from __future__ import annotations

from app.evidence.reconciliation import reconcile_graph_event_with_receipt
from app.models.reconciliation import ReconciliationStatus

TX_HASH = "0x" + "a" * 64
POOL = "0x" + "b" * 40
BLOCK_HASH = "0x" + "c" * 64
TOPIC0 = "0x" + "d" * 64
DATA = "0x" + "e" * 64


def _graph_event(**overrides):
    event = {
        "transaction": {"id": TX_HASH, "blockNumber": "16"},
        "pool": {"id": POOL},
        "logIndex": "3",
        "blockHash": BLOCK_HASH,
        "topics": [TOPIC0],
        "data": DATA,
    }
    event.update(overrides)
    return event


def _receipt(**log_overrides):
    log = {
        "transactionHash": TX_HASH,
        "logIndex": "0x3",
        "address": POOL,
        "blockNumber": "0x10",
        "blockHash": BLOCK_HASH,
        "topics": [TOPIC0],
        "data": DATA,
    }
    log.update(log_overrides)
    return {
        "transactionHash": TX_HASH,
        "blockNumber": "0x10",
        "blockHash": log.get("blockHash"),
        "logs": [log],
    }


def test_reconciliation_corrobates_matching_graph_event() -> None:
    result = reconcile_graph_event_with_receipt(_graph_event(), _receipt())

    assert result.status == ReconciliationStatus.CORROBORATED
    assert result.log_index == 3
    assert result.contract_address == POOL


def test_reconciliation_reports_mismatch() -> None:
    result = reconcile_graph_event_with_receipt(
        _graph_event(),
        _receipt(address="0x" + "f" * 40),
    )

    assert result.status == ReconciliationStatus.MISMATCH
    assert any("contract" in warning for warning in result.warnings)


def test_reconciliation_warns_on_block_hash_change() -> None:
    result = reconcile_graph_event_with_receipt(
        _graph_event(),
        _receipt(blockHash="0x" + "1" * 64),
    )

    assert result.status == ReconciliationStatus.MISMATCH
    assert any("possible reorg" in warning for warning in result.warnings)
