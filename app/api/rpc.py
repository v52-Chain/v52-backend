"""Direct RPC acquisition endpoints."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.evidence.provenance import make_evidence_id, make_request_fingerprint, utcnow
from app.models.api import ApiEnvelope, ApiError, EnvelopeStatus, envelope
from app.models.evidence import AuthorityLevel, EvidenceRecord, EvidenceStatus
from app.providers.base import ProviderError
from app.providers.factory import get_rpc_provider_for_chain, normalize_chain
from app.providers.rpc import RpcErrorCode
from app.storage.evidence_vault import EvidenceVault

router = APIRouter(prefix="/v1/rpc", tags=["rpc"])

_TX_HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")


@router.get(
    "/transactions/{chain}/{tx_hash}",
    response_model=ApiEnvelope,
    summary="Acquire a transaction through the configured RPC provider",
)
async def get_transaction(
    chain: str,
    tx_hash: str,
    settings: Settings = Depends(get_settings),
) -> ApiEnvelope:
    return await _acquire_rpc_object(
        chain=chain,
        tx_hash=tx_hash,
        method="eth_getTransactionByHash",
        settings=settings,
    )


@router.get(
    "/receipts/{chain}/{tx_hash}",
    response_model=ApiEnvelope,
    summary="Acquire a transaction receipt through the configured RPC provider",
)
async def get_receipt(
    chain: str,
    tx_hash: str,
    settings: Settings = Depends(get_settings),
) -> ApiEnvelope:
    return await _acquire_rpc_object(
        chain=chain,
        tx_hash=tx_hash,
        method="eth_getTransactionReceipt",
        settings=settings,
    )


async def _acquire_rpc_object(
    *,
    chain: str,
    tx_hash: str,
    method: str,
    settings: Settings,
) -> ApiEnvelope:
    if not _TX_HASH_RE.fullmatch(tx_hash):
        raise HTTPException(
            status_code=422,
            detail="transaction hash must be 0x followed by 64 hexadecimal characters.",
        )

    chain_config = normalize_chain(chain, settings)
    if chain_config is None:
        return envelope(
            EnvelopeStatus.FAILED,
            errors=[
                ApiError(
                    code="INVALID_CHAIN",
                    message=f"Unsupported chain alias or id: {chain}.",
                    retryable=False,
                )
            ],
        )

    provider = get_rpc_provider_for_chain(settings, chain_config.key)
    if provider is None:
        return envelope(
            EnvelopeStatus.FAILED,
            data={
                "chain": chain_config.key,
                "chain_id": chain_config.chain_id,
                "network": chain_config.network,
            },
            errors=[
                ApiError(
                    code="RPC_UNAVAILABLE",
                    message=f"{chain_config.key} RPC provider is not configured.",
                    retryable=False,
                    provider=chain_config.provider_label,
                )
            ],
        )

    try:
        actual_chain_id = await provider.validate_chain_id()
        response = (
            await provider.get_transaction(tx_hash.lower())
            if method == "eth_getTransactionByHash"
            else await provider.get_transaction_receipt(tx_hash.lower())
        )
    except ProviderError as exc:
        return envelope(
            EnvelopeStatus.FAILED,
            data={
                "chain": chain_config.key,
                "network": provider.network,
                "expected_chain_id": provider.expected_chain_id,
            },
            errors=[ApiError(**exc.to_api_error())],
        )

    if response is None:
        return envelope(
            EnvelopeStatus.UNKNOWN,
            data={
                "chain": chain_config.key,
                "chain_id": actual_chain_id,
                "network": provider.network,
                "result": None,
            },
            errors=[
                ApiError(
                    code=RpcErrorCode.NOT_FOUND,
                    message=f"Transaction {tx_hash.lower()} was not found.",
                    retryable=False,
                    provider=provider.provider_label,
                )
            ],
        )

    evidence_record, raw_payload = _preserve_rpc_response(
        settings=settings,
        provider=provider,
        chain_key=chain_config.key,
        chain_id=actual_chain_id,
        tx_hash=tx_hash.lower(),
        method=method,
        response=response,
    )

    return envelope(
        EnvelopeStatus.COMPLETE,
        data={
            "chain": chain_config.key,
            "chain_id": actual_chain_id,
            "network": provider.network,
            "provider": provider.provider_label,
            "method": method,
            "result": response,
            "evidence": evidence_record.model_dump(mode="json"),
            "raw_sha256": evidence_record.raw_sha256,
            "raw": raw_payload,
        },
    )


def _preserve_rpc_response(
    *,
    settings: Settings,
    provider: Any,
    chain_key: str,
    chain_id: int,
    tx_hash: str,
    method: str,
    response: dict[str, Any],
) -> tuple[EvidenceRecord, dict[str, Any]]:
    request_payload = {
        "chain": chain_key,
        "chain_id": chain_id,
        "method": method,
        "params": [tx_hash],
        "provider": provider.provider_label,
    }
    evidence_id = make_evidence_id(provider.provider_label, method, request_payload)
    raw_payload = {
        "provider": provider.provider_label,
        "network": provider.network,
        "endpoint_id": provider.endpoint_id,
        "chain_id": chain_id,
        "request": request_payload,
        "response": response,
        "retrieved_at": utcnow().isoformat(),
    }
    vault = EvidenceVault(settings.data_dir)
    case_id = f"rpc_{chain_id}_{tx_hash[2:10]}"
    raw_path, raw_sha256 = vault.preserve_raw(
        case_id=case_id,
        evidence_id=evidence_id,
        payload=raw_payload,
    )
    record = EvidenceRecord(
        evidence_id=evidence_id,
        authority_level=AuthorityLevel.L0_CHAIN_PRIMARY,
        chain_id=chain_id,
        source=provider.provider_label,
        source_type="RPC_PROVIDER",
        provider=provider.provider_label,
        network=provider.network,
        endpoint_id=provider.endpoint_id,
        method=method,
        request_fingerprint=make_request_fingerprint(request_payload),
        retrieved_at=utcnow(),
        raw_path=raw_path,
        raw_sha256=raw_sha256,
        adapter_version=provider.version,
        status=EvidenceStatus.COMPLETE,
        block_number=_to_int(response.get("blockNumber")),
        block_hash=response.get("blockHash"),
    )
    records_dir = settings.data_dir / "records" / case_id
    records_dir.mkdir(parents=True, exist_ok=True)
    (records_dir / f"{evidence_id}.json").write_text(
        record.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return record, raw_payload


def _to_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 16) if value.startswith("0x") else int(value)
        except ValueError:
            return None
    return None
