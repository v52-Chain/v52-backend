"""Reconcile indexed Graph events against chain-primary RPC logs."""

from __future__ import annotations

from typing import Any

from app.models.reconciliation import ReconciliationResult, ReconciliationStatus


def reconcile_graph_swaps_with_rpc(
    graph_payload: dict[str, Any] | None,
    rpc_payload: dict[str, Any] | None,
    *,
    evidence_ids: list[str] | None = None,
) -> list[ReconciliationResult]:
    """Compare Uniswap swap entities from The Graph with RPC receipt logs."""
    if rpc_payload is None:
        return [
            ReconciliationResult(
                status=ReconciliationStatus.RPC_UNAVAILABLE,
                evidence_ids=evidence_ids or [],
                warnings=["RPC evidence is unavailable; indexed events cannot be corroborated."],
            )
        ]

    swaps = _extract_swaps(graph_payload)
    if not swaps:
        return [
            ReconciliationResult(
                status=ReconciliationStatus.INSUFFICIENT_DATA,
                evidence_ids=evidence_ids or [],
                warnings=["No Graph swap events were available for reconciliation."],
            )
        ]

    receipt = rpc_payload.get("receipt") or {}
    logs = receipt.get("logs") or []
    if not receipt or not logs:
        return [
            ReconciliationResult(
                status=ReconciliationStatus.RPC_UNAVAILABLE,
                evidence_ids=evidence_ids or [],
                transaction_hash=_lower(receipt.get("transactionHash")),
                warnings=[
                    "RPC receipt/logs are unavailable; indexed events cannot be corroborated."
                ],
            )
        ]

    return [
        reconcile_graph_event_with_receipt(swap, receipt, evidence_ids=evidence_ids or [])
        for swap in swaps
    ]


def reconcile_graph_event_with_receipt(
    graph_event: dict[str, Any],
    receipt: dict[str, Any],
    *,
    evidence_ids: list[str] | None = None,
) -> ReconciliationResult:
    """Compare one indexed event against the matching receipt log."""
    warnings: list[str] = []
    compared: dict[str, Any] = {}
    tx_hash = _graph_tx_hash(graph_event)
    log_index = _to_int(graph_event.get("logIndex"))
    contract_address = _graph_contract_address(graph_event)
    graph_block = _graph_block_number(graph_event)
    graph_block_hash = _lower(graph_event.get("blockHash"))

    if not tx_hash or log_index is None or not contract_address:
        return ReconciliationResult(
            status=ReconciliationStatus.INSUFFICIENT_DATA,
            evidence_ids=evidence_ids or [],
            transaction_hash=tx_hash,
            log_index=log_index,
            contract_address=contract_address,
            warnings=["Graph event is missing transaction hash, log index or contract address."],
        )

    receipt_tx = _lower(receipt.get("transactionHash"))
    receipt_logs = receipt.get("logs") or []
    matching_log = None
    for log in receipt_logs:
        if _to_int(log.get("logIndex")) == log_index:
            matching_log = log
            break

    if matching_log is None:
        return ReconciliationResult(
            status=ReconciliationStatus.MISMATCH,
            evidence_ids=evidence_ids or [],
            transaction_hash=tx_hash,
            log_index=log_index,
            contract_address=contract_address,
            block_number=graph_block,
            block_hash=graph_block_hash,
            warnings=[f"No RPC log with logIndex {log_index} was found in the receipt."],
        )

    compared["transactionHash"] = {"graph": tx_hash, "rpc": receipt_tx}
    compared["logIndex"] = {"graph": log_index, "rpc": _to_int(matching_log.get("logIndex"))}
    compared["contract"] = {
        "graph": contract_address,
        "rpc": _lower(matching_log.get("address")),
    }
    compared["blockNumber"] = {
        "graph": graph_block,
        "rpc": _to_int(matching_log.get("blockNumber") or receipt.get("blockNumber")),
    }
    compared["blockHash"] = {
        "graph": graph_block_hash,
        "rpc": _lower(matching_log.get("blockHash") or receipt.get("blockHash")),
    }

    graph_topics = [_lower(topic) for topic in graph_event.get("topics", [])]
    rpc_topics = [_lower(topic) for topic in matching_log.get("topics", [])]
    if graph_topics:
        compared["topics"] = {"graph": graph_topics, "rpc": rpc_topics}

    graph_data = _lower(graph_event.get("data"))
    rpc_data = _lower(matching_log.get("data"))
    if graph_data:
        compared["data"] = {"graph": graph_data, "rpc": rpc_data}

    mismatches = [
        field
        for field, pair in compared.items()
        if pair["graph"] not in (None, [], "") and pair["graph"] != pair["rpc"]
    ]

    block_hash_pair = compared["blockHash"]
    if block_hash_pair["graph"] and block_hash_pair["graph"] != block_hash_pair["rpc"]:
        warnings.append("Block hash differs between Graph and RPC; possible reorg or stale index.")

    if mismatches:
        warnings.append("Graph/RPC mismatch in fields: " + ", ".join(mismatches))
        return ReconciliationResult(
            status=ReconciliationStatus.MISMATCH,
            evidence_ids=evidence_ids or [],
            transaction_hash=tx_hash,
            log_index=log_index,
            contract_address=contract_address,
            block_number=graph_block,
            block_hash=graph_block_hash,
            compared_fields=compared,
            warnings=warnings,
        )

    return ReconciliationResult(
        status=ReconciliationStatus.CORROBORATED,
        evidence_ids=evidence_ids or [],
        transaction_hash=tx_hash,
        log_index=log_index,
        contract_address=contract_address,
        block_number=compared["blockNumber"]["rpc"],
        block_hash=compared["blockHash"]["rpc"],
        compared_fields=compared,
        warnings=warnings,
    )


def _extract_swaps(graph_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not graph_payload:
        return []
    response = graph_payload.get("response") if "response" in graph_payload else graph_payload
    data = (response or {}).get("data") or {}
    swaps = data.get("swaps") or []
    return [swap for swap in swaps if isinstance(swap, dict)]


def _graph_tx_hash(event: dict[str, Any]) -> str | None:
    value = event.get("transactionHash")
    if value is None:
        transaction = event.get("transaction")
        if isinstance(transaction, dict):
            value = transaction.get("id")
        elif isinstance(transaction, str):
            value = transaction
    return _lower(value)


def _graph_contract_address(event: dict[str, Any]) -> str | None:
    value = event.get("address") or event.get("contractAddress")
    if value is None:
        pool = event.get("pool")
        if isinstance(pool, dict):
            value = pool.get("id")
        elif isinstance(pool, str):
            value = pool
    return _lower(value)


def _graph_block_number(event: dict[str, Any]) -> int | None:
    value = event.get("blockNumber")
    if value is None:
        transaction = event.get("transaction")
        if isinstance(transaction, dict):
            value = transaction.get("blockNumber")
    return _to_int(value)


def _lower(value: Any) -> str | None:
    if isinstance(value, str):
        return value.lower()
    return None


def _to_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 16) if value.startswith("0x") else int(value)
        except ValueError:
            return None
    return None
