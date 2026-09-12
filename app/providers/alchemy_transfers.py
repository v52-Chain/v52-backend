"""Alchemy Transfers API adapter for historical wallet flow acquisition."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

import httpx

from app.models.evidence import ProviderStatus
from app.models.wallet_flow import FlowTransfer
from app.providers.base import BaseProvider, ProviderError, redact


class AlchemyTransfersProvider(BaseProvider):
    name = "alchemy_transfers"
    version = "0.1.0"

    def __init__(self, rpc_url: str, timeout_seconds: float = 30.0) -> None:
        super().__init__(timeout_seconds=timeout_seconds)
        if not rpc_url:
            raise ProviderError(
                "Alchemy is not configured. Set V52_ALCHEMY_ETH_RPC_URL in the backend .env.",
                status=ProviderStatus.FAILED,
            )
        self._rpc_url = rpc_url
        self._request_id = 0

    async def _page(self, params: dict[str, Any]) -> dict[str, Any]:
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": "alchemy_getAssetTransfers",
            "params": [params],
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(self._rpc_url, json=payload)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            self._set_timeout()
            raise ProviderError(
                "Alchemy Transfers request timed out.", status=ProviderStatus.TIMEOUT
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._set_failed()
            raise ProviderError(
                f"Alchemy Transfers HTTP error {exc.response.status_code}.",
                status=ProviderStatus.FAILED,
            ) from exc
        except httpx.RequestError as exc:
            self._set_failed()
            raise ProviderError(
                f"Alchemy Transfers network error: {redact(str(exc))}",
                status=ProviderStatus.FAILED,
            ) from exc

        data = response.json()
        if "error" in data:
            self._set_failed()
            error = data["error"]
            raise ProviderError(
                f"Alchemy RPC error {error.get('code', '?')}: "
                f"{redact(str(error.get('message', 'unknown error')))}",
                status=ProviderStatus.FAILED,
            )
        self._set_ok()
        return data.get("result") or {}

    async def acquire(self, **kwargs: Any) -> list[FlowTransfer]:
        address = str(kwargs["address"]).lower()
        direction: Literal["IN", "OUT"] = kwargs["direction"]
        limit = int(kwargs.get("limit", 25))
        from_datetime: datetime | None = kwargs.get("from_datetime")
        to_datetime: datetime | None = kwargs.get("to_datetime")
        max_pages = max(1, int(kwargs.get("max_pages", 1)))
        field = "toAddress" if direction == "IN" else "fromAddress"
        params: dict[str, Any] = {
            "fromBlock": "0x0",
            "toBlock": "latest",
            field: address,
            "category": ["external", "erc20"],
            "excludeZeroValue": True,
            "withMetadata": True,
            "order": "desc",
            "maxCount": hex(1000 if from_datetime or to_datetime else min(limit, 1000)),
        }
        transfers: list[FlowTransfer] = []
        page_key: str | None = None
        for page_index in range(max_pages):
            page_params = {**params}
            if page_key:
                page_params["pageKey"] = page_key
            result = await self._page(page_params)
            reached_lower_bound = False
            for item_index, item in enumerate(result.get("transfers", [])):
                timestamp_value = (item.get("metadata") or {}).get("blockTimestamp")
                timestamp = (
                    datetime.fromisoformat(timestamp_value.replace("Z", "+00:00"))
                    if timestamp_value
                    else None
                )
                if to_datetime and (timestamp is None or timestamp > to_datetime):
                    continue
                if from_datetime and (timestamp is None or timestamp < from_datetime):
                    if timestamp is not None:
                        reached_lower_bound = True
                    continue
                counterparty = item.get("from") if direction == "IN" else item.get("to")
                if not counterparty:
                    counterparty = "0x0000000000000000000000000000000000000000"
                transfers.append(
                    FlowTransfer(
                        transfer_id=item.get("uniqueId")
                        or f"{item.get('hash', 'unknown')}:{page_index}:{item_index}",
                        direction=direction,
                        counterparty=str(counterparty).lower(),
                        tx_hash=item.get("hash") or "unknown",
                        block_number=int(item["blockNum"], 16) if item.get("blockNum") else None,
                        timestamp=timestamp,
                        asset=item.get("asset") or "UNKNOWN",
                        category=item.get("category") or "unknown",
                        value=str(item["value"]) if item.get("value") is not None else None,
                        contract_address=(item.get("rawContract") or {}).get("address"),
                        token_id=item.get("tokenId"),
                    )
                )
                if len(transfers) >= limit:
                    return transfers
            page_key = result.get("pageKey")
            if not page_key or reached_lower_bound:
                break
        return transfers
