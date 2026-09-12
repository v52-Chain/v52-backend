"""Evidence acquisition from RPC and The Graph."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.evidence.provenance import make_evidence_id, make_request_fingerprint, utcnow
from app.models.evidence import AuthorityLevel, EvidenceRecord, EvidenceStatus, ProviderStatus
from app.providers.base import ProviderError
from app.providers.rpc import RpcProvider
from app.providers.the_graph import TheGraphProvider
from app.storage.evidence_vault import EvidenceVault

logger = logging.getLogger(__name__)

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
    """Acquire, preserve and describe raw evidence."""

    def __init__(
        self,
        vault: EvidenceVault,
        rpc_provider: RpcProvider | None,
        graph_provider: TheGraphProvider | None,
        *,
        chain_id: int = 1,
    ) -> None:
        self.vault = vault
        self.rpc = rpc_provider
        self.graph = graph_provider
        self.chain_id = chain_id

    async def acquire_l0(
        self,
        case_id: str,
        tx_hash: str,
    ) -> tuple[EvidenceRecord, dict[str, Any] | None]:
        """Acquire L0 chain-primary evidence: tx, receipt, block and logs."""
        source = _rpc_source(self.rpc)
        network = getattr(self.rpc, "network", None)
        endpoint_id = getattr(self.rpc, "endpoint_id", None)
        request_payload = {
            "method": "acquire",
            "tx_hash": tx_hash.lower(),
            "chain_id": self.chain_id,
            "provider": source,
        }
        evidence_id = make_evidence_id(source, "acquire", request_payload)
        fingerprint = make_request_fingerprint(request_payload)

        if self.rpc is None:
            record = EvidenceRecord(
                evidence_id=evidence_id,
                authority_level=AuthorityLevel.L0_CHAIN_PRIMARY,
                chain_id=self.chain_id,
                source=source,
                source_type="RPC_PROVIDER",
                provider=source,
                network=network,
                endpoint_id=endpoint_id,
                method="acquire",
                request_fingerprint=fingerprint,
                retrieved_at=utcnow(),
                raw_path="",
                raw_sha256="",
                status=EvidenceStatus.FAILED,
                warnings=[f"RPC provider is not configured for chain_id {self.chain_id}."],
            )
            self._preserve_record(case_id, record)
            return record, None

        warnings: list[str] = []
        status = EvidenceStatus.COMPLETE
        raw_payload: dict[str, Any] | None = None
        t0 = time.monotonic()

        try:
            raw_payload = await self.rpc.acquire(tx_hash=tx_hash)
            warnings.extend(raw_payload.get("warnings", []))
            if self.rpc.status in (ProviderStatus.DEGRADED, ProviderStatus.TIMEOUT):
                status = EvidenceStatus.PARTIAL
        except ProviderError as exc:
            status = EvidenceStatus.UNKNOWN if exc.code == "NOT_FOUND" else EvidenceStatus.FAILED
            warnings.append(str(exc))

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        raw_path = ""
        raw_sha256 = ""
        block_number: int | None = None
        block_hash: str | None = None

        if raw_payload is not None:
            block_number = _hex_to_int((raw_payload.get("receipt") or {}).get("blockNumber"))
            block_hash = (raw_payload.get("receipt") or {}).get("blockHash")
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
            chain_id=self.chain_id,
            source=source,
            source_type="RPC_PROVIDER",
            provider=source,
            network=network,
            endpoint_id=endpoint_id,
            method="acquire",
            request_fingerprint=fingerprint,
            retrieved_at=utcnow(),
            raw_path=raw_path,
            raw_sha256=raw_sha256,
            adapter_version=getattr(self.rpc, "version", "0.1.0"),
            status=status,
            warnings=warnings,
            block_number=block_number,
            block_hash=block_hash,
        )
        self._preserve_record(case_id, record)
        logger.info(
            "L0 evidence acquired: id=%s status=%s chain=%s elapsed_ms=%d",
            evidence_id,
            status,
            self.chain_id,
            elapsed_ms,
        )
        return record, raw_payload

    async def acquire_l1(
        self,
        case_id: str,
        tx_hash: str,
        query: str | None = None,
        variables: dict[str, Any] | None = None,
    ) -> tuple[EvidenceRecord, dict[str, Any] | None]:
        """Acquire L1 indexed evidence from The Graph."""
        gql_query = query or _UNISWAP_V3_SWAP_QUERY
        gql_vars = variables or {"txHash": tx_hash.lower()}
        request_payload = {"query": gql_query, "variables": gql_vars, "chain_id": self.chain_id}
        evidence_id = make_evidence_id("the_graph", "query", request_payload)
        fingerprint = make_request_fingerprint(request_payload)

        if self.graph is None:
            record = EvidenceRecord(
                evidence_id=evidence_id,
                authority_level=AuthorityLevel.L1_INDEXED,
                chain_id=self.chain_id,
                source="the_graph",
                source_type="INDEXED_PROVIDER",
                provider="the_graph",
                network="ethereum-mainnet" if self.chain_id == 1 else None,
                method="query",
                request_fingerprint=fingerprint,
                retrieved_at=utcnow(),
                raw_path="",
                raw_sha256="",
                status=EvidenceStatus.FAILED,
                warnings=["The Graph provider is not configured for this chain."],
            )
            self._preserve_record(case_id, record)
            return record, None

        warnings: list[str] = []
        status = EvidenceStatus.COMPLETE
        raw_payload: dict[str, Any] | None = None
        meta: dict[str, Any] = {}
        t0 = time.monotonic()

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
            chain_id=self.chain_id,
            source="the_graph",
            source_type="INDEXED_PROVIDER",
            provider="the_graph",
            network="ethereum-mainnet" if self.chain_id == 1 else None,
            method="query",
            request_fingerprint=fingerprint,
            retrieved_at=utcnow(),
            raw_path=raw_path,
            raw_sha256=raw_sha256,
            adapter_version=getattr(self.graph, "version", "0.1.0"),
            status=status,
            warnings=warnings,
            block_number=meta.get("block_number"),
            block_hash=meta.get("block_hash"),
            indexing_errors=meta.get("has_indexing_errors"),
            graph_deployment=meta.get("deployment"),
        )
        self._preserve_record(case_id, record)
        logger.info(
            "L1 evidence acquired: id=%s status=%s elapsed_ms=%d block=%s",
            evidence_id,
            status,
            elapsed_ms,
            meta.get("block_number"),
        )
        return record, raw_payload

    def _preserve_record(self, case_id: str, record: EvidenceRecord) -> None:
        records_dir = self.vault.data_dir / "records" / case_id
        records_dir.mkdir(parents=True, exist_ok=True)
        path = records_dir / f"{record.evidence_id}.json"
        path.write_text(record.model_dump_json(indent=2), encoding="utf-8")


def _rpc_source(rpc: RpcProvider | None) -> str:
    return getattr(rpc, "provider_label", "rpc")


def _hex_to_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 16)
        except ValueError:
            return None
    return None
