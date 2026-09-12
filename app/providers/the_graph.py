"""
The Graph Provider — L1 INDEXED evidence acquisition.

Rules (architecture doc section 10):
  - The Graph must be load-bearing, not decorative.
  - Live data is consumed; fixtures are only for tests.
  - query, variables, raw response and timestamp are always preserved.
  - _meta, indexed block, deployment and hasIndexingErrors are captured when available.
  - If The Graph does not respond, the case is marked DEGRADED; evidence is never invented.
  - API key is never logged or surfaced in errors.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from app.models.evidence import ProviderStatus
from app.providers.base import BaseProvider, ProviderError, redact

logger = logging.getLogger(__name__)

# Default Uniswap V3 subgraph on The Graph's decentralized network.
# Override with V52_GRAPH_ENDPOINT in .env.
DEFAULT_GRAPH_ENDPOINT = (
    "https://gateway.thegraph.com/api/{api_key}/subgraphs/id/"
    "5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"
)

# Maximum response size to prevent memory exhaustion (5 MB).
_MAX_RESPONSE_BYTES = 5 * 1024 * 1024


class TheGraphProvider(BaseProvider):
    """
    Executes GraphQL queries against The Graph and preserves the full response.

    Captures:
      - query and variables (exact strings sent)
      - raw response body
      - _meta block and hasIndexingErrors when present
      - deployment ID when available
      - UTC timestamp of acquisition
    """

    name = "the_graph"
    version = "0.1.0"

    def __init__(
        self,
        endpoint: str,
        api_key: str = "",
        timeout_seconds: float = 30.0,
    ) -> None:
        super().__init__(timeout_seconds=timeout_seconds)
        if not endpoint:
            raise ProviderError(
                "V52_GRAPH_ENDPOINT is not configured. Set it in .env for live Graph queries.",
                status=ProviderStatus.FAILED,
            )
        if "{api_key}" in endpoint:
            if api_key:
                endpoint = endpoint.replace("{api_key}", api_key)
            else:
                endpoint = endpoint.replace("/{api_key}", "").replace("{api_key}", "")
        self._endpoint = endpoint
        self._api_key = api_key  # never logged

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def acquire(self, **kwargs: Any) -> dict[str, Any]:
        """
        Execute a GraphQL query and return preserved evidence payload.

        kwargs:
          query (str):     GraphQL query string.
          variables (dict): GraphQL variables.
          operation_name (str, optional): Named operation.

        Returns dict with: query, variables, response, meta, retrieved_at, warnings.
        """
        query: str = kwargs["query"]
        variables: dict = kwargs.get("variables", {})
        operation_name: str | None = kwargs.get("operation_name")

        payload: dict[str, Any] = {"query": query, "variables": variables}
        if operation_name:
            payload["operationName"] = operation_name

        retrieved_at = datetime.now(UTC).isoformat()
        warnings: list[str] = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    self._endpoint,
                    json=payload,
                    headers=self._build_headers(),
                )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            self._set_timeout()
            raise ProviderError(
                f"The Graph query timed out after {self.timeout_seconds}s.",
                status=ProviderStatus.TIMEOUT,
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._set_failed()
            raise ProviderError(
                f"The Graph HTTP error {exc.response.status_code}.",
                status=ProviderStatus.FAILED,
            ) from exc
        except httpx.RequestError as exc:
            self._set_failed()
            raise ProviderError(
                f"The Graph network error: {redact(str(exc))}",
                status=ProviderStatus.FAILED,
            ) from exc

        # Guard against unexpectedly large responses.
        content = response.content
        if len(content) > _MAX_RESPONSE_BYTES:
            self._set_degraded()
            warnings.append(
                f"Graph response truncated: {len(content)} bytes exceeds limit "
                f"of {_MAX_RESPONSE_BYTES} bytes."
            )

        data = response.json()

        # Extract GraphQL-level errors (partial response is still PARTIAL, not COMPLETE).
        gql_errors = data.get("errors")
        if gql_errors:
            self._set_degraded()
            for err in gql_errors:
                msg = redact(str(err.get("message", err)))
                warnings.append(f"Graph error: {msg}")

        # Extract _meta for indexing status.
        meta = self._extract_meta(data, warnings)

        if not gql_errors:
            self._set_ok()

        return {
            "query": query,
            "variables": variables,
            "response": data,
            "meta": meta,
            "retrieved_at": retrieved_at,
            "warnings": warnings,
            "has_errors": bool(gql_errors),
        }

    def _extract_meta(self, data: dict, warnings: list[str]) -> dict:
        """
        Extract _meta block from the GraphQL response data.
        Records hasIndexingErrors and indexed block number.
        """
        meta: dict[str, Any] = {}
        gql_data = data.get("data") or {}

        # _meta can be at the root of data or inside a named field.
        raw_meta = gql_data.get("_meta")
        if raw_meta is None:
            # Search one level deep.
            for v in gql_data.values():
                if isinstance(v, dict) and "_meta" in v:
                    raw_meta = v["_meta"]
                    break

        if raw_meta:
            block = raw_meta.get("block", {})
            meta["block_number"] = block.get("number")
            meta["block_hash"] = block.get("hash")
            meta["deployment"] = raw_meta.get("deployment")
            has_errors = raw_meta.get("hasIndexingErrors", False)
            meta["has_indexing_errors"] = has_errors
            if has_errors:
                warnings.append(
                    "The Graph reported hasIndexingErrors=true — "
                    "indexed data may be incomplete or stale."
                )
        else:
            warnings.append(
                "_meta not present in Graph response — "
                "indexing status and block number cannot be verified."
            )

        return meta

    async def query(
        self, query: str, variables: dict | None = None, operation_name: str | None = None
    ) -> dict[str, Any]:
        """Convenience wrapper around acquire()."""
        return await self.acquire(
            query=query,
            variables=variables or {},
            operation_name=operation_name,
        )
