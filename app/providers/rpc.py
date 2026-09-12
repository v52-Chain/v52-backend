"""Uniform JSON-RPC providers for chain-primary evidence acquisition."""

from __future__ import annotations

import asyncio
import logging
import time
from abc import abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.evidence.provenance import utcnow
from app.models.evidence import ProviderStatus
from app.providers.base import BaseProvider, ProviderError, redact

logger = logging.getLogger(__name__)


class RpcErrorCode(StrEnum):
    """Provider-level errors surfaced through the public API envelope."""

    NOT_FOUND = "NOT_FOUND"
    CHAIN_MISMATCH = "CHAIN_MISMATCH"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_RATE_LIMIT = "PROVIDER_RATE_LIMIT"
    PROVIDER_INVALID_RESPONSE = "PROVIDER_INVALID_RESPONSE"
    RPC_UNAVAILABLE = "RPC_UNAVAILABLE"


READ_ONLY_METHODS = {
    "eth_chainId",
    "eth_getTransactionByHash",
    "eth_getTransactionReceipt",
    "eth_getBlockByNumber",
    "eth_getBlockByHash",
    "eth_getLogs",
    "eth_call",
}


@dataclass(frozen=True)
class RpcEndpointConfig:
    """Runtime configuration for one logical RPC endpoint."""

    rpc_url: str
    expected_chain_id: int
    network: str
    provider_label: str
    timeout_seconds: float
    max_retries: int


class RpcProvider(BaseProvider):
    """Uniform RPC provider interface required by FRANCO.md."""

    provider_label: str
    network: str
    expected_chain_id: int
    endpoint_id: str

    @abstractmethod
    async def chain_id(self) -> int:
        """Return the EIP-155 chain id reported by eth_chainId."""

    @abstractmethod
    async def validate_chain_id(self) -> int:
        """Ensure the endpoint belongs to the expected chain."""

    @abstractmethod
    async def get_block(
        self,
        number_or_hash: str | int,
        full_transactions: bool = False,
    ) -> dict[str, Any] | None:
        """Fetch a block by number or hash."""

    @abstractmethod
    async def get_transaction(self, tx_hash: str) -> dict[str, Any] | None:
        """Fetch a transaction by hash."""

    @abstractmethod
    async def get_transaction_receipt(self, tx_hash: str) -> dict[str, Any] | None:
        """Fetch a transaction receipt by hash."""

    @abstractmethod
    async def get_logs(self, filter_params: dict[str, Any]) -> list[dict[str, Any]]:
        """Fetch logs using eth_getLogs."""

    @abstractmethod
    async def eth_call(
        self,
        request: dict[str, Any],
        block_identifier: str = "latest",
    ) -> Any:
        """Execute a read-only eth_call."""


class JsonRpcProvider(RpcProvider):
    """Safe JSON-RPC client with retries, rate-limit handling and chain checks."""

    name = "json_rpc"
    version = "0.2.0"

    def __init__(self, config: RpcEndpointConfig) -> None:
        if not config.rpc_url:
            raise ProviderError(
                "RPC URL is not configured.",
                status=ProviderStatus.FAILED,
                code=RpcErrorCode.RPC_UNAVAILABLE,
                provider=config.provider_label,
            )
        super().__init__(timeout_seconds=config.timeout_seconds)
        self._rpc_url = config.rpc_url
        self.expected_chain_id = config.expected_chain_id
        self.network = config.network
        self.provider_label = config.provider_label
        self.max_retries = max(config.max_retries, 0)
        self.endpoint_id = _redacted_endpoint_id(config.rpc_url)
        self._request_id = 0
        self._failure_count = 0
        self._circuit_opened_at: float | None = None
        self._circuit_threshold = 3
        self._circuit_cooldown_seconds = 30.0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _make_error(
        self,
        message: str,
        *,
        code: RpcErrorCode,
        status: ProviderStatus = ProviderStatus.FAILED,
        retryable: bool = False,
    ) -> ProviderError:
        return ProviderError(
            message,
            status=status,
            code=code,
            retryable=retryable,
            provider=self.provider_label,
        )

    def _check_circuit(self) -> None:
        if self._circuit_opened_at is None:
            return
        elapsed = time.monotonic() - self._circuit_opened_at
        if elapsed >= self._circuit_cooldown_seconds:
            self._circuit_opened_at = None
            self._failure_count = 0
            return
        raise self._make_error(
            "RPC circuit breaker is open after repeated provider failures.",
            code=RpcErrorCode.RPC_UNAVAILABLE,
            retryable=True,
        )

    def _record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self._circuit_threshold:
            self._circuit_opened_at = time.monotonic()

    def _record_success(self) -> None:
        self._failure_count = 0
        self._circuit_opened_at = None

    async def _call(self, method: str, params: list[Any]) -> Any:
        retryable = method in READ_ONLY_METHODS
        return await self._call_json_rpc(method, params, retryable=retryable)

    async def _call_json_rpc(
        self,
        method: str,
        params: list[Any],
        *,
        retryable: bool,
    ) -> Any:
        self._check_circuit()
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params,
        }
        attempts = self.max_retries + 1 if retryable else 1
        last_error: ProviderError | None = None

        for attempt in range(attempts):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(
                        self._rpc_url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )
                if response.status_code == 429:
                    raise self._make_error(
                        f"RPC rate limit on method '{method}'.",
                        code=RpcErrorCode.PROVIDER_RATE_LIMIT,
                        status=ProviderStatus.DEGRADED,
                        retryable=True,
                    )
                response.raise_for_status()
                try:
                    data = response.json()
                except ValueError as exc:
                    raise self._make_error(
                        f"RPC returned malformed JSON on method '{method}'.",
                        code=RpcErrorCode.PROVIDER_INVALID_RESPONSE,
                    ) from exc
            except httpx.TimeoutException as exc:
                last_error = self._make_error(
                    f"RPC call to '{method}' timed out after {self.timeout_seconds}s.",
                    code=RpcErrorCode.PROVIDER_TIMEOUT,
                    status=ProviderStatus.TIMEOUT,
                    retryable=True,
                )
                self._set_timeout()
                if attempt < attempts - 1:
                    await _bounded_backoff(attempt)
                    continue
                self._record_failure()
                raise last_error from exc
            except httpx.HTTPStatusError as exc:
                last_error = self._make_error(
                    f"RPC HTTP error {exc.response.status_code} on method '{method}'.",
                    code=RpcErrorCode.RPC_UNAVAILABLE,
                    retryable=500 <= exc.response.status_code < 600,
                )
                self._set_failed()
                if last_error.retryable and attempt < attempts - 1:
                    await _bounded_backoff(attempt)
                    continue
                self._record_failure()
                raise last_error from exc
            except httpx.RequestError as exc:
                last_error = self._make_error(
                    f"RPC network error on method '{method}': {redact(str(exc))}",
                    code=RpcErrorCode.RPC_UNAVAILABLE,
                    retryable=True,
                )
                self._set_failed()
                if attempt < attempts - 1:
                    await _bounded_backoff(attempt)
                    continue
                self._record_failure()
                raise last_error from exc
            except ProviderError as exc:
                last_error = exc
                if exc.code == RpcErrorCode.PROVIDER_RATE_LIMIT:
                    self._set_degraded()
                else:
                    self._set_failed()
                if exc.retryable and attempt < attempts - 1:
                    await _bounded_backoff(attempt)
                    continue
                self._record_failure()
                raise

            if not isinstance(data, dict):
                self._set_failed()
                self._record_failure()
                raise self._make_error(
                    f"RPC returned a non-object JSON payload on method '{method}'.",
                    code=RpcErrorCode.PROVIDER_INVALID_RESPONSE,
                )

            if "error" in data:
                rpc_error = data["error"] if isinstance(data["error"], dict) else {}
                error_message = redact(str(rpc_error.get("message", "unknown error")))
                code = (
                    RpcErrorCode.PROVIDER_RATE_LIMIT
                    if _looks_rate_limited(rpc_error)
                    else RpcErrorCode.RPC_UNAVAILABLE
                )
                retry = code == RpcErrorCode.PROVIDER_RATE_LIMIT
                last_error = self._make_error(
                    f"RPC error {rpc_error.get('code', '?')}: {error_message}",
                    code=code,
                    status=ProviderStatus.DEGRADED if retry else ProviderStatus.FAILED,
                    retryable=retry,
                )
                if retry:
                    self._set_degraded()
                else:
                    self._set_failed()
                if retry and attempt < attempts - 1:
                    await _bounded_backoff(attempt)
                    continue
                self._record_failure()
                raise last_error

            self._set_ok()
            self._record_success()
            return data.get("result")

        if last_error is not None:
            raise last_error
        raise self._make_error(
            f"RPC call to '{method}' failed without a provider response.",
            code=RpcErrorCode.RPC_UNAVAILABLE,
            retryable=True,
        )

    async def chain_id(self) -> int:
        result = await self._call("eth_chainId", [])
        try:
            if isinstance(result, str):
                return int(result, 16)
            if isinstance(result, int):
                return result
        except ValueError as exc:
            raise self._make_error(
                f"RPC returned invalid eth_chainId value: {result!r}.",
                code=RpcErrorCode.PROVIDER_INVALID_RESPONSE,
            ) from exc
        raise self._make_error(
            f"RPC returned missing eth_chainId value: {result!r}.",
            code=RpcErrorCode.PROVIDER_INVALID_RESPONSE,
        )

    async def validate_chain_id(self) -> int:
        actual = await self.chain_id()
        if actual != self.expected_chain_id:
            self._set_failed()
            raise self._make_error(
                (
                    "RPC endpoint chain mismatch: expected "
                    f"{self.expected_chain_id}, got {actual}."
                ),
                code=RpcErrorCode.CHAIN_MISMATCH,
                retryable=False,
            )
        return actual

    async def get_transaction(self, tx_hash: str) -> dict[str, Any] | None:
        return await self._call("eth_getTransactionByHash", [tx_hash])

    async def get_transaction_receipt(self, tx_hash: str) -> dict[str, Any] | None:
        return await self._call("eth_getTransactionReceipt", [tx_hash])

    async def get_receipt(self, tx_hash: str) -> dict[str, Any] | None:
        """Backward-compatible alias used by the previous Ethereum provider."""
        return await self.get_transaction_receipt(tx_hash)

    async def get_block(
        self,
        number_or_hash: str | int,
        full_transactions: bool = False,
    ) -> dict[str, Any] | None:
        if isinstance(number_or_hash, int):
            number_or_hash = hex(number_or_hash)
        if isinstance(number_or_hash, str) and _is_hex_hash(number_or_hash):
            method = "eth_getBlockByHash"
        else:
            method = "eth_getBlockByNumber"
        return await self._call(method, [number_or_hash, full_transactions])

    async def get_logs(self, filter_params: dict[str, Any]) -> list[dict[str, Any]]:
        result = await self._call("eth_getLogs", [filter_params])
        return result if isinstance(result, list) else []

    async def eth_call(
        self,
        request: dict[str, Any],
        block_identifier: str = "latest",
    ) -> Any:
        return await self._call("eth_call", [request, block_identifier])

    async def acquire(self, **kwargs: Any) -> dict[str, Any]:
        tx_hash = str(kwargs["tx_hash"]).lower()
        actual_chain_id = await self.validate_chain_id()
        result: dict[str, Any] = {
            "provider": self.provider_label,
            "network": self.network,
            "endpoint_id": self.endpoint_id,
            "chain_id": actual_chain_id,
            "expected_chain_id": self.expected_chain_id,
            "request": {"method": "acquire", "tx_hash": tx_hash},
            "retrieved_at": utcnow().isoformat(),
            "transaction": None,
            "receipt": None,
            "block": None,
            "logs": [],
            "warnings": [],
        }

        tx = await self.get_transaction(tx_hash)
        if tx is None:
            raise self._make_error(
                f"Transaction {tx_hash} not found on {self.network}.",
                code=RpcErrorCode.NOT_FOUND,
                retryable=False,
            )
        result["transaction"] = tx

        receipt = await self.get_transaction_receipt(tx_hash)
        if receipt is None:
            self._set_degraded()
            result["warnings"].append(
                f"Receipt for {tx_hash} not found; transaction may not be mined yet."
            )
            return result
        result["receipt"] = receipt
        result["logs"] = receipt.get("logs", [])

        block_number = receipt.get("blockNumber")
        if block_number:
            result["block"] = await self.get_block(block_number)

        self._set_ok()
        return result

    def status_payload(self, actual_chain_id: int | None = None) -> dict[str, Any]:
        """Return a public, redacted provider status payload."""
        return {
            "status": self.status.value,
            "provider": self.provider_label,
            "network": self.network,
            "chain_id": actual_chain_id,
            "expected_chain_id": self.expected_chain_id,
            "endpoint_id": self.endpoint_id,
        }


class AlchemyRpcProvider(JsonRpcProvider):
    """Alchemy-backed EVM JSON-RPC provider."""

    name = "alchemy"

    def __init__(
        self,
        rpc_url: str,
        *,
        expected_chain_id: int,
        network: str,
        timeout_seconds: float,
        max_retries: int,
    ) -> None:
        super().__init__(
            RpcEndpointConfig(
                rpc_url=rpc_url,
                expected_chain_id=expected_chain_id,
                network=network,
                provider_label="alchemy",
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )
        )


class HskRpcProvider(JsonRpcProvider):
    """HSK JSON-RPC provider. It is deliberately not labeled as Alchemy."""

    name = "hsk_rpc"

    def __init__(
        self,
        rpc_url: str,
        *,
        expected_chain_id: int,
        timeout_seconds: float,
        max_retries: int,
    ) -> None:
        super().__init__(
            RpcEndpointConfig(
                rpc_url=rpc_url,
                expected_chain_id=expected_chain_id,
                network="hsk",
                provider_label="hsk_rpc",
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )
        )


async def _bounded_backoff(attempt: int) -> None:
    await asyncio.sleep(min(0.05 * (2**attempt), 0.5))


def _looks_rate_limited(error: dict[str, Any]) -> bool:
    code = error.get("code")
    message = str(error.get("message", "")).lower()
    return code in {429, -32005} or "rate" in message or "too many" in message


def _is_hex_hash(value: str) -> bool:
    return (
        len(value) == 66
        and value.startswith("0x")
        and all(char in "0123456789abcdefABCDEF" for char in value[2:])
    )


def _is_hex_quantity(value: str) -> bool:
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _redacted_endpoint_id(rpc_url: str) -> str:
    split = urlsplit(rpc_url)
    if not split.scheme or not split.netloc:
        return "[redacted-endpoint]"
    return f"{split.scheme}://{split.netloc}/[redacted]"
