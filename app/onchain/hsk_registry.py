"""
HSK V52EvidenceRegistry client.

Thin wrapper around web3.py used to anchor and look up `.v52` manifest
commitments on HashKey Chain (HSK). Mirrors the contract at
`v52-onchain/contracts/hsk/V52EvidenceRegistry.sol`; the ABI vendored in
`app/onchain/abi/V52EvidenceRegistry.json` is a copy of
`v52-onchain/abi/V52EvidenceRegistry.json` and must be regenerated
(`forge inspect ... abi`) whenever the contract source changes.

Rules:
  - Never logs or raises the private key.
  - Every exception raised to callers is sanitized with redact() — RPC URLs
    and provider errors sometimes echo request details that could contain
    an API key or a raw signed transaction.
  - All web3 calls are synchronous (web3.py's HTTPProvider is sync); API
    handlers run them with `asyncio.to_thread()` so the event loop is never
    blocked on a JSON-RPC round trip to HSK.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from eth_account import Account
from web3 import Web3
from web3.exceptions import TimeExhausted, Web3Exception

from app.providers.base import redact

logger = logging.getLogger(__name__)

ZERO_BYTES32 = b"\x00" * 32
_ABI_PATH = Path(__file__).parent / "abi" / "V52EvidenceRegistry.json"


def _hex(value: bytes | str) -> str:
    """Normalize bytes or a hex string to a single 0x-prefixed lowercase string."""
    text = value.hex() if isinstance(value, bytes | bytearray) else str(value)
    if text.startswith(("0x", "0X")):
        text = text[2:]
    return "0x" + text.lower()


ZERO_BYTES32_HEX = _hex(ZERO_BYTES32)
_LOG_SCAN_FALLBACK_WINDOW = 90_000


class HskRegistryError(Exception):
    """Raised for any RPC, signing or contract-level failure. Message is safe to expose."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(redact(message))
        self.retryable = retryable


@lru_cache(maxsize=1)
def _load_abi() -> list[dict[str, Any]]:
    return json.loads(_ABI_PATH.read_text(encoding="utf-8"))


def _to_bytes32(value: bytes | str) -> bytes:
    """Accept raw bytes or a 0x-hex string and return exactly 32 bytes."""
    if isinstance(value, str):
        stripped = value[2:] if value.startswith(("0x", "0X")) else value
        try:
            value = bytes.fromhex(stripped)
        except ValueError as exc:
            raise HskRegistryError(f"Invalid hex value for bytes32 field: {exc}") from None
    if len(value) != 32:
        raise HskRegistryError(
            f"Expected exactly 32 bytes, got {len(value)}. "
            "manifest_root / methodology_hash / supersedes must be 32-byte hashes."
        )
    return value


@dataclass(frozen=True)
class AnchorRecord:
    """Mirrors the on-chain `Anchor` struct, hex-encoded for API responses."""

    manifest_root: str
    methodology_hash: str
    schema_version: str
    case_id: str
    issuer: str
    block_number: int
    timestamp: int
    supersedes: str
    exists: bool


@dataclass(frozen=True)
class AnchorTxResult:
    """Result of a submitted (and mined) `anchorCase` transaction."""

    tx_hash: str
    block_number: int
    gas_used: int
    status: int


class HskRegistryClient:
    """Read/write client for one V52EvidenceRegistry deployment."""

    def __init__(
        self,
        rpc_url: str,
        contract_address: str,
        *,
        private_key: str = "",
        chain_id: int | None = None,
        timeout_seconds: float = 20.0,
        confirmation_timeout_seconds: float = 90.0,
        gas_limit: int = 400_000,
    ) -> None:
        if not rpc_url:
            raise HskRegistryError("HSK_RPC_URL is not configured.")
        if not contract_address:
            raise HskRegistryError("HSK_EVIDENCE_REGISTRY_ADDRESS is not configured.")

        self._w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": timeout_seconds}))
        self._contract = self._w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=_load_abi(),
        )
        self._private_key = private_key
        self._expected_chain_id = chain_id
        self._confirmation_timeout_seconds = confirmation_timeout_seconds
        self._gas_limit = gas_limit

    # ── Read ─────────────────────────────────────────────────────────────

    def get_anchor(self, manifest_root: bytes | str) -> AnchorRecord | None:
        """Return the anchor for `manifest_root`, or None if never anchored."""
        root = _to_bytes32(manifest_root)
        try:
            result = self._contract.functions.getAnchor(root).call()
        except Web3Exception as exc:
            raise HskRegistryError(f"HSK RPC call failed: {exc}", retryable=True) from None
        except (ConnectionError, OSError, TimeoutError) as exc:
            raise HskRegistryError(f"HSK RPC unreachable: {exc}", retryable=True) from None

        exists = bool(result[8])
        if not exists:
            return None

        return AnchorRecord(
            manifest_root=_hex(result[0]),
            methodology_hash=_hex(result[1]),
            schema_version=result[2],
            case_id=result[3],
            issuer=result[4],
            block_number=int(result[5]),
            timestamp=int(result[6]),
            supersedes=_hex(result[7]),
            exists=exists,
        )

    def find_anchor_tx_hash(
        self, manifest_root: bytes | str, *, block_number: int | None = None
    ) -> str | None:
        """
        Best-effort lookup of the CaseAnchored transaction hash via logs.

        Public HSK RPC nodes cap `eth_getLogs` to a limited block range (seen
        in practice: 100_000 blocks), so scanning from genesis is not viable
        on a long-lived chain. `getAnchor()` already returns the exact
        `blockNumber` an anchor was mined in — pass it as `block_number` to
        query that single block directly (cheap, always within range limits).
        Without a hint, this falls back to scanning only the most recent
        block window, which will miss older anchors.
        """
        root = _to_bytes32(manifest_root)
        if block_number is not None:
            from_block, to_block = block_number, block_number
        else:
            try:
                latest = self._w3.eth.block_number
            except Web3Exception as exc:
                logger.warning("HSK log lookup failed (non-fatal): %s", redact(str(exc)))
                return None
            from_block, to_block = max(0, latest - _LOG_SCAN_FALLBACK_WINDOW), latest

        try:
            logs = self._contract.events.CaseAnchored().get_logs(
                from_block=from_block,
                to_block=to_block,
                argument_filters={"manifestRoot": root},
            )
        except Web3Exception as exc:
            logger.warning("HSK log lookup failed (non-fatal): %s", redact(str(exc)))
            return None
        if not logs:
            return None
        return _hex(logs[0]["transactionHash"])

    # ── Write ────────────────────────────────────────────────────────────

    def anchor(
        self,
        manifest_root: bytes | str,
        methodology_hash: bytes | str,
        schema_version: str,
        case_id: str,
        supersedes: bytes | str = ZERO_BYTES32,
    ) -> AnchorTxResult:
        """Sign and submit `anchorCase(...)`, waiting for a mined receipt."""
        if not self._private_key:
            raise HskRegistryError(
                "HSK_ANCHOR_PRIVATE_KEY is not configured; this client is read-only."
            )

        root = _to_bytes32(manifest_root)
        method_hash = _to_bytes32(methodology_hash)
        supersedes_bytes = _to_bytes32(supersedes)

        account = Account.from_key(self._private_key)

        try:
            chain_id = self._expected_chain_id or self._w3.eth.chain_id
            nonce = self._w3.eth.get_transaction_count(account.address, "pending")
            tx = self._contract.functions.anchorCase(
                root, method_hash, schema_version, case_id, supersedes_bytes
            ).build_transaction(
                {
                    "from": account.address,
                    "nonce": nonce,
                    "chainId": chain_id,
                    "gas": self._gas_limit,
                }
            )
            signed = account.sign_transaction(tx)
            tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self._w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=self._confirmation_timeout_seconds
            )
        except TimeExhausted as exc:
            raise HskRegistryError(
                f"HSK transaction was broadcast but not mined in time: {exc}", retryable=True
            ) from None
        except Web3Exception as exc:
            raise HskRegistryError(f"HSK anchor transaction failed: {exc}") from None
        except (ConnectionError, OSError, TimeoutError) as exc:
            raise HskRegistryError(f"HSK RPC unreachable: {exc}", retryable=True) from None

        if receipt.status != 1:
            raise HskRegistryError(
                f"HSK anchor transaction reverted (tx {_hex(receipt.transactionHash)})."
            )

        return AnchorTxResult(
            tx_hash=_hex(receipt.transactionHash),
            block_number=int(receipt.blockNumber),
            gas_used=int(receipt.gasUsed),
            status=int(receipt.status),
        )
