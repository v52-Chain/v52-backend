"""
Evidence acquisition — orchestrates RPC + The Graph, handles partial/failed states.

Rules:
  - Providers are only called from this module.  Protocol modules (uniswap_v3.py)
    read from preserved evidence; they never call providers directly.
  - A timeout or partial response never becomes COMPLETE.
  - Secrets are never included in EvidenceRecord fields or warnings.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.evidence.provenance import make_evidence_id, make_request_fingerprint, utcnow
from app.models.evidence import AuthorityLevel, EvidenceRecord, EvidenceStatus, ProviderStatus
from app.providers.base import ProviderError
from app.providers.ethereum_rpc import EthereumRpcProvider
from app.providers.the_graph import TheGraphProvider
from app.storage.evidence_vault import EvidenceVault

logger = logging.getLogger(__name__)

# Default Uniswap V3 subgraph query — captures Swap events for a tx hash.
_UNISWAP_V3_SWAP_QUERY = """
query UniswapV3Swaps($txHash: String!) {
  _meta {
    block { number hash }
    deployment
    hasIndexingErrors
  }
  swaps(where: { transaction: $txHash }) {
    id
    timestamp
    transaction { id blockNumber }
    pool { id token0 { id symbol decimals } token1 { id symbol decimals } liquidity }
    sender
    recipient
    origin
    amount0
    amount1
    amountUSD
    sqrtPriceX96
    tick
    logIndex
  }
}
"""


class AcquisitionError(Exception):
    """Raised when acquisition cannot produce usable evidence."""


class EvidenceAcquisition:
    """
    Orchestrates evidence acquisition from RPC (L0) and The Graph (L1).

    Responsibilities:
      - Acquire raw payloads from providers.
      - Preserve them in the Evidence Vault (append-only).
      - Build EvidenceRecord objects with proper status, warnings and provenance.
      - Return a structured result; never raise to the pipeline on partial failures.
    """

    def __init__(
        self,
        vault: EvidenceVault,
        rpc_provider: EthereumRpcProvider | None,
        graph_provider: TheGraphProvider | None,
    ) -> None:
        self.vault = vault
        self.rpc = rpc_provider
        self.graph = graph_provider

    async def acquire_l0(
        self,
        case_id: str,
        tx_hash: str,
    ) -> tuple[EvidenceRecord, dict[str, Any] | None]:
        """
        Acquire L0 (RPC) evidence: tx, receipt, block, logs.

        Returns (EvidenceRecord, raw_payload_or_None).
        EvidenceRecord.status reflects the provider outcome faithfully.
        """
        if self.rpc is None:
            record = EvidenceRecord(
                evidence_id=make_evidence_id("ethereum_rpc", "acquire", {"tx_hash": tx_hash}),
                authority_level=AuthorityLevel.L0_CHAIN_PRIMARY,
                chain_id=1,
                source="ethereum_rpc",
                method="acquire",
                request_fingerprint=make_request_fingerprint({"tx_hash": tx_hash}),
                retrieved_at=utcnow(),
                raw_path="",
                raw_sha256="",
                status=EvidenceStatus.FAILED,
                warnings=["RPC provider is not configured (V52_RPC_URL not set)."],
            )
            return record, None

        evidence_id = make_evidence_id("ethereum_rpc", "acquire", {"tx_hash": tx_hash})
        request_payload = {"method": "acquire", "tx_hash": tx_hash}
        fingerprint = make_request_fingerprint(request_payload)
        warnings: list[str] = []
        status = EvidenceStatus.COMPLETE

        t0 = time.monotonic()
        raw_payload: dict | None = None
        try:
            raw_payload = await self.rpc.acquire(tx_hash=tx_hash)
            warnings.extend(raw_payload.get("warnings", []))
            if self.rpc.status in (ProviderStatus.DEGRADED, ProviderStatus.TIMEOUT):
                status = EvidenceStatus.PARTIAL
        except ProviderError as exc:
            status = (
                EvidenceStatus.UNKNOWN
                if exc.status == ProviderStatus.FAILED and "not found" in str(exc)
                else EvidenceStatus.FAILED
            )
            warnings.append(str(exc))

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        retrieved_at = utcnow()

        raw_path = ""
        raw_sha256 = ""
        if raw_payload is not None:
            try:
                raw_path, raw_sha256 = self.vault.preserve_raw(
                    case_id=case_id,
                    evidence_id=evidence_id,
                    payload=raw_payload,
                )
            except Exception as exc:
                warnings.append(f"Vault preservation failed: {exc}")
                status = EvidenceStatus.PARTIAL

        record = EvidenceRecord(
            evidence_id=evidence_id,
            authority_level=AuthorityLevel.L0_CHAIN_PRIMARY,
            chain_id=1,
            source="ethereum_rpc",
            method="acquire",
            request_fingerprint=fingerprint,
            retrieved_at=retrieved_at,
            raw_path=raw_path,
            raw_sha256=raw_sha256,
            status=status,
            warnings=warnings,
        )
        logger.info(
            "L0 evidence acquired: id=%s status=%s elapsed_ms=%d",
            evidence_id,
            status,
            elapsed_ms,
        )
        return record, raw_payload

    async def acquire_l1(
        self,
        case_id: str,
        tx_hash: str,
        query: str | None = None,
        variables: dict | None = None,
    ) -> tuple[EvidenceRecord, dict[str, Any] | None]:
        """
        Acquire L1 (The Graph) evidence for a transaction.

        Returns (EvidenceRecord, raw_graph_payload_or_None).
        Missing _meta or indexing errors are reflected as WARNING status, not FAILED.
        """
        gql_query = query or _UNISWAP_V3_SWAP_QUERY
        gql_vars = variables or {"txHash": tx_hash}

        if self.graph is None:
            evidence_id = make_evidence_id("the_graph", "query", gql_vars)
            record = EvidenceRecord(
                evidence_id=evidence_id,
                authority_level=AuthorityLevel.L1_INDEXED,
                chain_id=1,
                source="the_graph",
                method="query",
                request_fingerprint=make_request_fingerprint(
                    {"query": gql_query, "variables": gql_vars}
                ),
                retrieved_at=utcnow(),
                raw_path="",
                raw_sha256="",
                status=EvidenceStatus.FAILED,
                warnings=["The Graph provider is not configured (V52_GRAPH_ENDPOINT not set)."],
            )
            return record, None

        evidence_id = make_evidence_id(
            "the_graph", "query", {"query": gql_query, "variables": gql_vars}
        )
        fingerprint = make_request_fingerprint({"query": gql_query, "variables": gql_vars})
        warnings: list[str] = []
        status = EvidenceStatus.COMPLETE

        t0 = time.monotonic()
        raw_payload: dict | None = None
        meta: dict = {}

        try:
            raw_payload = await self.graph.query(query=gql_query, variables=gql_vars)
            warnings.extend(raw_payload.get("warnings", []))
            meta = raw_payload.get("meta", {})

            if raw_payload.get("has_errors"):
                status = EvidenceStatus.PARTIAL
            elif meta.get("has_indexing_errors"):
                status = EvidenceStatus.WARNING
        except ProviderError as exc:
            status = (
                EvidenceStatus.FAILED
                if exc.status == ProviderStatus.FAILED
                else EvidenceStatus.PARTIAL
            )
            warnings.append(str(exc))

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        retrieved_at = utcnow()

        raw_path = ""
        raw_sha256 = ""
        if raw_payload is not None:
            try:
                raw_path, raw_sha256 = self.vault.preserve_raw(
                    case_id=case_id,
                    evidence_id=evidence_id,
                    payload=raw_payload,
                )
            except Exception as exc:
                warnings.append(f"Vault preservation failed: {exc}")
                status = EvidenceStatus.PARTIAL

        record = EvidenceRecord(
            evidence_id=evidence_id,
            authority_level=AuthorityLevel.L1_INDEXED,
            chain_id=1,
            source="the_graph",
            method="query",
            request_fingerprint=fingerprint,
            retrieved_at=retrieved_at,
            raw_path=raw_path,
            raw_sha256=raw_sha256,
            status=status,
            warnings=warnings,
            block_number=meta.get("block_number"),
            indexing_errors=meta.get("has_indexing_errors"),
            graph_deployment=meta.get("deployment"),
        )
        logger.info(
            "L1 evidence acquired: id=%s status=%s elapsed_ms=%d block=%s",
            evidence_id,
            status,
            elapsed_ms,
            meta.get("block_number"),
        )
        return record, raw_payload
