"""ERC-20 decoder tests, including a verified Ethereum mainnet fixture."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.protocols.erc20 import (
    ERC20_TRANSFER_TOPIC,
    ERC20DecodeError,
    decode_transfer_log,
    decode_transfer_logs,
    format_token_amount,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "known_case"


def _fixture() -> dict:
    return json.loads((FIXTURE_DIR / "ethereum_rpc.json").read_text(encoding="utf-8"))


def _metadata() -> dict:
    items = json.loads((FIXTURE_DIR / "token_metadata.json").read_text(encoding="utf-8"))
    return {item["address"]: item for item in items["tokens"]}


def _expected() -> dict:
    return json.loads((FIXTURE_DIR / "expected_result.json").read_text(encoding="utf-8"))


def _transfer_logs() -> list[dict]:
    return [
        log
        for log in _fixture()["logs"]
        if log["topics"][0].lower() == ERC20_TRANSFER_TOPIC
    ]


def test_decodes_real_transfers_in_log_order() -> None:
    fixture = _fixture()
    expected = _expected()["transfers"]
    transfers = decode_transfer_logs(
        reversed(fixture["logs"]),
        evidence_id=fixture["evidence_id"],
        metadata_by_address=_metadata(),
    )

    assert [transfer.log_index for transfer in transfers] == [
        item["log_index"] for item in expected
    ]

    usdc, weth = transfers
    assert usdc.model_dump(include=set(expected[0])) == expected[0]
    assert weth.model_dump(include=set(expected[1])) == expected[1]
    assert usdc.to_address == fixture["transaction"]["from"]
    assert weth.evidence_ids == [fixture["evidence_id"]]


def test_missing_metadata_preserves_raw_and_warns() -> None:
    transfer = decode_transfer_log(_transfer_logs()[0], evidence_id="ev_l0_test")

    assert transfer.amount_raw == "17112191"
    assert transfer.amount_formatted is None
    assert transfer.token_decimals is None
    assert "decimals unavailable" in transfer.warnings[0]


def test_rejects_malformed_topic_count() -> None:
    log = deepcopy(_transfer_logs()[0])
    log["topics"] = log["topics"][:2]

    with pytest.raises(ERC20DecodeError, match="exactly three topics"):
        decode_transfer_log(log, evidence_id="ev_l0_test")


def test_rejects_malformed_data() -> None:
    log = deepcopy(_transfer_logs()[0])
    log["data"] = "0x01"

    with pytest.raises(ERC20DecodeError, match="uint256"):
        decode_transfer_log(log, evidence_id="ev_l0_test")


def test_rejects_non_zero_address_padding() -> None:
    log = deepcopy(_transfer_logs()[0])
    log["topics"][1] = "0x01" + log["topics"][1][4:]

    with pytest.raises(ERC20DecodeError, match="non-zero address padding"):
        decode_transfer_log(log, evidence_id="ev_l0_test")


def test_unrelated_events_are_ignored() -> None:
    fixture = _fixture()
    unrelated = [
        log for log in fixture["logs"] if log["topics"][0].lower() != ERC20_TRANSFER_TOPIC
    ]

    assert decode_transfer_logs(unrelated, evidence_id=fixture["evidence_id"]) == []


def test_uint256_max_is_preserved_without_float() -> None:
    log = deepcopy(_transfer_logs()[0])
    maximum = (1 << 256) - 1
    log["data"] = f"0x{maximum:064x}"

    transfer = decode_transfer_log(log, evidence_id="ev_l0_test")

    assert transfer.amount_raw == str(maximum)
    assert isinstance(transfer.amount_raw, str)


@pytest.mark.parametrize(
    ("amount", "decimals", "expected"),
    [
        (0, 18, "0"),
        (1, 6, "0.000001"),
        (17_112_191, 6, "17.112191"),
        (10**16, 18, "0.01"),
        (42, 0, "42"),
    ],
)
def test_exact_amount_formatting(amount: int, decimals: int, expected: str) -> None:
    assert format_token_amount(amount, decimals) == expected
