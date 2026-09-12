"""Provider status endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.models.api import ApiEnvelope, ApiError, EnvelopeStatus, envelope
from app.providers.base import ProviderError
from app.providers.factory import configured_chains, get_rpc_provider_for_chain

router = APIRouter(prefix="/v1/providers", tags=["providers"])


@router.get(
    "/status",
    response_model=ApiEnvelope,
    summary="Return redacted provider health and chain checks",
)
async def provider_status(settings: Settings = Depends(get_settings)) -> ApiEnvelope:
    """Return provider status without exposing URLs, keys or tokens."""
    data: dict[str, object] = {
        "the_graph": {
            "status": "CONFIGURED" if settings.graph_configured else "UNCONFIGURED",
            "network": "ethereum-mainnet",
        },
        "rpc": {},
        "x402": {
            "status": "UNAVAILABLE",
            "network": "avalanche",
            "reason": "MCP/x402 settlement is owned by v52-mcp and not connected here yet.",
        },
    }
    warnings: list[str] = []
    errors: list[ApiError] = []

    rpc_status: dict[str, object] = {}
    for key, chain in configured_chains(settings).items():
        if not chain.configured:
            rpc_status[key] = {
                "status": "UNCONFIGURED",
                "provider": chain.provider_label,
                "network": chain.network,
                "expected_chain_id": chain.chain_id,
            }
            warnings.append(f"{key} RPC is not configured.")
            continue

        provider = get_rpc_provider_for_chain(settings, key)
        if provider is None:
            rpc_status[key] = {
                "status": "UNCONFIGURED",
                "provider": chain.provider_label,
                "network": chain.network,
                "expected_chain_id": chain.chain_id,
            }
            warnings.append(f"{key} RPC provider could not be built.")
            continue

        try:
            actual_chain_id = await provider.validate_chain_id()
            payload = provider.status_payload(actual_chain_id)
            payload["status"] = "UP"
            rpc_status[key] = payload
        except ProviderError as exc:
            rpc_status[key] = {
                "status": "DEGRADED" if exc.retryable else "DOWN",
                "provider": provider.provider_label,
                "network": provider.network,
                "expected_chain_id": provider.expected_chain_id,
                "endpoint_id": provider.endpoint_id,
            }
            errors.append(ApiError(**exc.to_api_error()))

    data["rpc"] = rpc_status
    status = EnvelopeStatus.COMPLETE if not warnings and not errors else EnvelopeStatus.PARTIAL
    configured_count = len(
        [chain for chain in configured_chains(settings).values() if chain.configured]
    )
    if errors and len(errors) == configured_count:
        status = EnvelopeStatus.FAILED
    return envelope(status, data=data, warnings=warnings, errors=errors)
