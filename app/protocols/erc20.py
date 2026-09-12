"""Strict, deterministic decoder for ERC-20 ``Transfer`` event logs.

The decoder consumes preserved L0 log dictionaries and never calls a provider.
Malformed logs that claim to be ``Transfer`` events are rejected. Unrelated
events are ignored by :func:`decode_transfer_logs`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from app.models.transfer import DecodedTransfer, TokenMetadata

ERC20_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

_HEX_32_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


class ERC20DecodeError(ValueError):
    """A log matched the Transfer signature but was not valid ABI data."""


def _quantity(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ERC20DecodeError(f"{field} must be an integer or 0x quantity")
    if isinstance(value, int):
        if value < 0:
            raise ERC20DecodeError(f"{field} cannot be negative")
        return value
    if isinstance(value, str) and value.startswith("0x"):
        try:
            parsed = int(value, 16)
        except ValueError as exc:
            raise ERC20DecodeError(f"{field} is not a valid 0x quantity") from exc
        return parsed
    raise ERC20DecodeError(f"{field} must be an integer or 0x quantity")


def _address(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _ADDRESS_RE.fullmatch(value):
        raise ERC20DecodeError(f"{field} must be a 0x-prefixed 20-byte address")
    return value.lower()


def _topic_address(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _HEX_32_RE.fullmatch(value):
        raise ERC20DecodeError(f"{field} must be a 32-byte ABI topic")
    encoded = value[2:]
    if encoded[:24] != "0" * 24:
        raise ERC20DecodeError(f"{field} has non-zero address padding")
    return f"0x{encoded[-40:]}".lower()


def _transaction_hash(value: Any) -> str:
    if not isinstance(value, str) or not _HEX_32_RE.fullmatch(value):
        raise ERC20DecodeError("transactionHash must be a 0x-prefixed 32-byte hash")
    return value.lower()


def format_token_amount(amount_raw: int, decimals: int) -> str:
    """Format a uint exactly with integer/string operations, never binary float."""
    if amount_raw < 0:
        raise ValueError("amount_raw cannot be negative")
    if not 0 <= decimals <= 255:
        raise ValueError("decimals must be between 0 and 255")
    if decimals == 0:
        return str(amount_raw)

    digits = str(amount_raw).rjust(decimals + 1, "0")
    whole = digits[:-decimals]
    fraction = digits[-decimals:].rstrip("0")
    return whole if not fraction else f"{whole}.{fraction}"


def _metadata_for(
    token_address: str,
    metadata_by_address: Mapping[str, TokenMetadata | Mapping[str, Any]] | None,
) -> TokenMetadata | None:
    if metadata_by_address is None:
        return None

    raw_metadata = next(
        (
            metadata
            for address, metadata in metadata_by_address.items()
            if address.lower() == token_address
        ),
        None,
    )
    if raw_metadata is None:
        return None

    metadata = (
        raw_metadata
        if isinstance(raw_metadata, TokenMetadata)
        else TokenMetadata.model_validate(raw_metadata)
    )
    if metadata.address != token_address:
        raise ERC20DecodeError("token metadata address does not match the log address")
    return metadata


def decode_transfer_log(
    log: Mapping[str, Any],
    *,
    evidence_id: str,
    metadata_by_address: Mapping[str, TokenMetadata | Mapping[str, Any]] | None = None,
) -> DecodedTransfer:
    """Decode one standard ERC-20 Transfer log and preserve its L0 lineage."""
    if not evidence_id.strip():
        raise ERC20DecodeError("evidence_id cannot be empty")

    topics = log.get("topics")
    if not isinstance(topics, list) or len(topics) != 3:
        raise ERC20DecodeError("Transfer log must contain exactly three topics")
    if not isinstance(topics[0], str) or topics[0].lower() != ERC20_TRANSFER_TOPIC:
        raise ERC20DecodeError("log does not have the ERC-20 Transfer topic")

    data = log.get("data")
    if not isinstance(data, str) or not _HEX_32_RE.fullmatch(data):
        raise ERC20DecodeError("Transfer data must be one ABI-encoded uint256 word")

    token_address = _address(log.get("address"), "address")
    amount = int(data, 16)
    metadata = _metadata_for(token_address, metadata_by_address)
    warnings: list[str] = []
    amount_formatted: str | None = None

    if metadata is None or metadata.decimals is None:
        warnings.append(
            f"Token decimals unavailable for {token_address}; "
            "amount_raw was preserved and amount_formatted was omitted."
        )
    else:
        amount_formatted = format_token_amount(amount, metadata.decimals)

    return DecodedTransfer(
        token_address=token_address,
        from_address=_topic_address(topics[1], "topics[1]"),
        to_address=_topic_address(topics[2], "topics[2]"),
        amount_raw=str(amount),
        transaction_hash=_transaction_hash(log.get("transactionHash")),
        block_number=_quantity(log.get("blockNumber"), "blockNumber"),
        log_index=_quantity(log.get("logIndex"), "logIndex"),
        evidence_ids=[evidence_id],
        token_symbol=metadata.symbol if metadata else None,
        token_decimals=metadata.decimals if metadata else None,
        amount_formatted=amount_formatted,
        warnings=warnings,
    )


def decode_transfer_logs(
    logs: Iterable[Mapping[str, Any]],
    *,
    evidence_id: str,
    metadata_by_address: Mapping[str, TokenMetadata | Mapping[str, Any]] | None = None,
) -> list[DecodedTransfer]:
    """Decode all Transfer events and return them ordered by ``logIndex``."""
    transfers: list[DecodedTransfer] = []
    for log in logs:
        topics = log.get("topics")
        if not isinstance(topics, list) or not topics:
            continue
        topic0 = topics[0]
        if not isinstance(topic0, str) or topic0.lower() != ERC20_TRANSFER_TOPIC:
            continue
        transfers.append(
            decode_transfer_log(
                log,
                evidence_id=evidence_id,
                metadata_by_address=metadata_by_address,
            )
        )

    return sorted(transfers, key=lambda transfer: transfer.log_index)

