"""
POST /v1/cases/{case_id}/anchor — anchor a case's .v52 manifest hash on HSK.
GET  /v1/anchors/{manifest_root}  — look up an anchor by its manifest root.

The registry (V52EvidenceRegistry, v52-onchain/contracts/hsk) only ever
receives: sha256(manifest.json), a methodology hash, a schema version and a
non-sensitive case_id. It never receives the manifest itself, the subject
wallet, the claim text or any verdict. See v52-onchain/README.md and
docs/CONTRATO-INTEGRACION.md for the full contract.
"""

from __future__ import annotations

import asyncio
import json
import logging
import zipfile

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.evidence.preservation import sha256_of
from app.models.anchor import (
    BYTES32_RE,
    AnchorCaseRequest,
    AnchorCaseResponse,
    AnchorLookupResponse,
)
from app.onchain.hsk_registry import ZERO_BYTES32_HEX, HskRegistryClient, HskRegistryError
from app.storage.anchor_store import AnchorStore
from app.storage.case_repository import FileCaseRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["hsk-anchor"])


_POST_MINE_READ_RETRIES = 3
_POST_MINE_READ_DELAY_SECONDS = 2.0


async def _get_anchor_with_retry(client: HskRegistryClient, manifest_root_hex: str):
    """
    Re-read a just-mined anchor, tolerating brief read-after-write lag.

    HSK testnet's public RPC appears to load-balance across nodes; a read
    immediately after `wait_for_transaction_receipt` confirms a tx as mined
    can still hit a node that has not caught up yet. The transaction is
    already final at that point, so a short retry is safe and sufficient.
    """
    record = None
    for attempt in range(_POST_MINE_READ_RETRIES):
        record = await asyncio.to_thread(client.get_anchor, manifest_root_hex)
        if record is not None:
            return record
        if attempt < _POST_MINE_READ_RETRIES - 1:
            await asyncio.sleep(_POST_MINE_READ_DELAY_SECONDS)
    return record


def _explorer_urls(settings: Settings, tx_hash: str | None) -> tuple[str | None, str]:
    base = settings.v52_hsk_explorer_url.rstrip("/")
    address_url = f"{base}/address/{settings.v52_hsk_evidence_registry_address}"
    tx_url = f"{base}/tx/{tx_hash}" if tx_hash else None
    return tx_url, address_url


def _get_client(settings: Settings, *, require_signer: bool) -> HskRegistryClient:
    if require_signer and not settings.hsk_anchor_configured:
        raise HTTPException(
            status_code=503,
            detail=(
                "HSK anchoring is not configured. Set HSK_RPC_URL, "
                "HSK_EVIDENCE_REGISTRY_ADDRESS and HSK_ANCHOR_PRIVATE_KEY."
            ),
        )
    if not require_signer and not settings.hsk_registry_configured:
        raise HTTPException(
            status_code=503,
            detail=(
                "HSK registry lookup is not configured. Set HSK_RPC_URL "
                "and HSK_EVIDENCE_REGISTRY_ADDRESS."
            ),
        )
    return HskRegistryClient(
        rpc_url=settings.hsk_rpc_url,
        contract_address=settings.v52_hsk_evidence_registry_address,
        private_key=settings.v52_hsk_anchor_private_key if require_signer else "",
        chain_id=settings.hsk_chain_id,
        gas_limit=settings.v52_hsk_anchor_gas_limit,
    )


@router.post(
    "/cases/{case_id}/anchor",
    response_model=AnchorCaseResponse,
    summary="Anchor a case's .v52 manifest hash on HSK",
)
async def anchor_case(
    case_id: str,
    request: AnchorCaseRequest | None = None,
    settings: Settings = Depends(get_settings),
) -> AnchorCaseResponse:
    """
    Compute manifest_root = sha256(manifest.json bytes exactly as packaged in
    the case's .v52.zip) and anchor it on HSK via V52EvidenceRegistry. The
    same manifest bytes always produce the same manifest_root, so retrying
    this call after a package rebuild with unchanged content is idempotent.
    """
    request = request or AnchorCaseRequest()
    client = _get_client(settings, require_signer=True)

    repo = FileCaseRepository(settings.data_dir)
    case = await repo.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")

    package_path = settings.data_dir / "packages" / f"{case_id}.v52.zip"
    if not package_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Package for case '{case_id}' has not been built yet. "
                "Run a full audit to generate the .v52.zip before anchoring."
            ),
        )

    with zipfile.ZipFile(package_path) as zf:
        if "manifest.json" not in zf.namelist():
            raise HTTPException(
                status_code=400, detail="Package is missing manifest.json — cannot anchor."
            )
        manifest_bytes = zf.read("manifest.json")

    try:
        manifest = json.loads(manifest_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="manifest.json is not valid JSON.") from None

    schema_version = str(manifest.get("schema_version", "0.1.0"))
    manifest_root_hex = "0x" + sha256_of(manifest_bytes)
    methodology_hash_hex = "0x" + sha256_of(settings.v52_hsk_methodology_version.encode("utf-8"))
    supersedes_hex = request.supersedes or ZERO_BYTES32_HEX

    store = AnchorStore(settings.data_dir)

    try:
        existing = await asyncio.to_thread(client.get_anchor, manifest_root_hex)
    except HskRegistryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None

    already_anchored = existing is not None

    if already_anchored:
        record = existing
        cached = store.get(case_id) or {}
        tx_hash = cached.get("tx_hash") or await asyncio.to_thread(
            client.find_anchor_tx_hash, manifest_root_hex, block_number=record.block_number
        )
        gas_used = int(cached.get("gas_used", 0))
    else:
        try:
            tx_result = await asyncio.to_thread(
                client.anchor,
                manifest_root_hex,
                methodology_hash_hex,
                schema_version,
                case_id,
                supersedes_hex,
            )
        except HskRegistryError as exc:
            status_code = 502 if exc.retryable else 400
            raise HTTPException(status_code=status_code, detail=str(exc)) from None

        record = await _get_anchor_with_retry(client, manifest_root_hex)
        if record is None:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Anchor transaction {tx_result.tx_hash} was mined but the "
                    "record is not yet readable from HSK. Retry the lookup shortly."
                ),
            )
        tx_hash = tx_result.tx_hash
        gas_used = tx_result.gas_used
        store.save(
            case_id,
            {
                "case_id": case_id,
                "manifest_root": manifest_root_hex,
                "methodology_hash": methodology_hash_hex,
                "schema_version": schema_version,
                "supersedes": request.supersedes,
                "chain_id": settings.hsk_chain_id,
                "tx_hash": tx_hash,
                "block_number": tx_result.block_number,
                "gas_used": gas_used,
            },
        )

    tx_url, address_url = _explorer_urls(settings, tx_hash)

    return AnchorCaseResponse(
        case_id=case_id,
        manifest_root=record.manifest_root,
        methodology_hash=record.methodology_hash,
        schema_version=record.schema_version,
        issuer=record.issuer,
        supersedes=None if record.supersedes == ZERO_BYTES32_HEX else record.supersedes,
        chain_id=settings.hsk_chain_id,
        tx_hash=tx_hash or "",
        block_number=record.block_number,
        gas_used=gas_used,
        explorer_tx_url=tx_url or "",
        explorer_address_url=address_url,
        already_anchored=already_anchored,
    )


@router.get(
    "/anchors/{manifest_root}",
    response_model=AnchorLookupResponse,
    summary="Look up an HSK anchor by manifest root",
)
async def get_anchor(
    manifest_root: str,
    settings: Settings = Depends(get_settings),
) -> AnchorLookupResponse:
    """Public, unauthenticated lookup — anyone can verify a manifest_root exists on HSK."""
    if not BYTES32_RE.match(manifest_root):
        raise HTTPException(
            status_code=422,
            detail="manifest_root must be a 0x-prefixed 64-character hex string (32 bytes).",
        )
    manifest_root = manifest_root.lower()

    client = _get_client(settings, require_signer=False)

    try:
        record = await asyncio.to_thread(client.get_anchor, manifest_root)
    except HskRegistryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None

    if record is None:
        raise HTTPException(
            status_code=404, detail=f"No anchor found for manifest_root '{manifest_root}'."
        )

    tx_hash = await asyncio.to_thread(
        client.find_anchor_tx_hash, manifest_root, block_number=record.block_number
    )
    tx_url, address_url = _explorer_urls(settings, tx_hash)

    return AnchorLookupResponse(
        manifest_root=record.manifest_root,
        methodology_hash=record.methodology_hash,
        schema_version=record.schema_version,
        case_id=record.case_id,
        issuer=record.issuer,
        block_number=record.block_number,
        timestamp=record.timestamp,
        supersedes=None if record.supersedes == ZERO_BYTES32_HEX else record.supersedes,
        chain_id=settings.hsk_chain_id,
        tx_hash=tx_hash,
        explorer_tx_url=tx_url,
        explorer_address_url=address_url,
    )
