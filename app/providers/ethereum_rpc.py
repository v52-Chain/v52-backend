"""
Ethereum RPC Provider — L0 CHAIN_PRIMARY evidence acquisition.

Implements:
  - eth_getTransactionByHash
  - eth_getTransactionReceipt
  - eth_getBlockByNumber
  - eth_getLogs

Rules:
  - RPC URL is never logged or surfaced in errors.
  - Timeouts produce ProviderStatus.TIMEOUT, not exceptions to the caller.
  - Missing receipt (unmined tx) produces UNKNOWN, not COMPLETE.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.models.evidence import ProviderStatus
from app.providers.base import BaseProvider, ProviderError, redact

logger = logging.getLogger(__name__)


class EthereumRpcProvider(BaseProvider):
    """
    Sends JSON-RPC 2.0 requests to the configured Ethereum endpoint.

    The RPC URL (which may contain an API key in the path) is never logged.
    Error messages from the remote are redacted before being raised or logged.
    """

    name = "ethereum_rpc"
    version = "0.1.0"

    def __init__(self, rpc_url: str, timeout_seconds: float = 30.0) -> None:
        super().__init__(timeout_seconds=timeout_seconds)
        if not rpc_url:
            raise ProviderError(
                "V52_RPC_URL is not configured.  Set it in .env to enable live RPC acquisition.",
                status=ProviderStatus.FAILED,
            )
        self._rpc_url = rpc_url
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _call(self, method: str, params: list[Any]) -> Any:
        """
        Execute a single JSON-RPC call.  Returns the 'result' field.
        Raises ProviderError on timeout, HTTP error, or RPC error.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    self._rpc_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            self._set_timeout()
            raise ProviderError(
                f"RPC call to '{method}' timed out after {self.timeout_seconds}s.",
                status=ProviderStatus.TIMEOUT,
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._set_failed()
            raise ProviderError(
                f"RPC HTTP error {exc.response.status_code} on method '{method}'.",
                status=ProviderStatus.FAILED,
            ) from exc
        except httpx.RequestError as exc:
            self._set_failed()
            raise ProviderError(
                f"RPC network error on method '{method}': {redact(str(exc))}",
                status=ProviderStatus.FAILED,
            ) from exc

        data = response.json()
        if "error" in data:
            self._set_failed()
            err = data["error"]
            raise ProviderError(
                f"RPC error {err.get('code', '?')}: {redact(str(err.get('message', '')))}",
                status=ProviderStatus.FAILED,
            )

        self._set_ok()
        return data.get("result")

    async def acquire(self, **kwargs: Any) -> dict[str, Any]:
        """
        Acquire full L0 evidence for a transaction:
          tx, receipt, block and raw logs.

        kwargs:
          tx_hash (str): 0x-prefixed transaction hash.

        Returns a dict with keys: transaction, receipt, block, logs.
        Missing receipt sets status to UNKNOWN (tx not yet mined).
        """
        tx_hash: str = kwargs["tx_hash"]
        result: dict[str, Any] = {
            "transaction": None,
            "receipt": None,
            "block": None,
            "logs": [],
            "warnings": [],
        }

        # 1. Transaction
        result["transaction"] = await self.get_transaction(tx_hash)
        if result["transaction"] is None:
            self._set_failed()
            raise ProviderError(
                f"Transaction {tx_hash} not found on chain.",
                status=ProviderStatus.FAILED,
            )

        # 2. Receipt (may be None if not mined)
        receipt = await self.get_receipt(tx_hash)
        if receipt is None:
            self._set_degraded()
            result["warnings"].append(
                f"Receipt for {tx_hash} not found — transaction may not be mined yet."
            )
            self._status = ProviderStatus.DEGRADED
            return result

        result["receipt"] = receipt

        # 3. Block
        block_number = receipt.get("blockNumber")
        if block_number:
            result["block"] = await self.get_block(block_number)

        # 4. Logs (from the receipt to avoid extra call)
        result["logs"] = receipt.get("logs", [])

        self._set_ok()
        return result

    async def get_transaction(self, tx_hash: str) -> dict | None:
        """eth_getTransactionByHash."""
        return await self._call("eth_getTransactionByHash", [tx_hash])

    async def get_receipt(self, tx_hash: str) -> dict | None:
        """eth_getTransactionReceipt.  Returns None if not yet mined."""
        return await self._call("eth_getTransactionReceipt", [tx_hash])

    async def get_block(
        self, block_number: str | int, full_transactions: bool = False
    ) -> dict | None:
        """eth_getBlockByNumber.  block_number may be hex string or int."""
        if isinstance(block_number, int):
            block_number = hex(block_number)
        return await self._call("eth_getBlockByNumber", [block_number, full_transactions])

    async def get_logs(self, filter_params: dict) -> list[dict]:
        """eth_getLogs with provided filter params."""
        result = await self._call("eth_getLogs", [filter_params])
        return result if result is not None else []
