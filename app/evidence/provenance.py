"""
Evidence provenance — deterministic ID generation and lineage tracking.

IDs are stable for the same logical inputs so that repeated acquisitions
of identical content produce identical evidence_ids.  A UUID4 suffix is added
only when content-based uniqueness is insufficient (e.g., two calls with the
same params at different times should still be distinct).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.evidence.preservation import sha256_of_canonical


def make_evidence_id(
    source: str,
    method: str,
    request_payload: object,
    retrieved_at: datetime | None = None,
) -> str:
    """
    Generate a stable evidence ID.

    Format: ev_<source>_<sha256-8chars>_<uuid4-8chars>

    The SHA-256 prefix is derived from the request payload (what was asked),
    not from the response (what was received), so the ID can be computed
    before the response arrives.

    The UUID4 suffix ensures uniqueness across repeated acquisitions with the
    same parameters (e.g., two calls to the same RPC endpoint at different times).
    """
    fingerprint = sha256_of_canonical(
        {
            "source": source,
            "method": method,
            "payload": request_payload,
        }
    )
    short_fp = fingerprint[:8]
    short_uuid = uuid.uuid4().hex[:8]
    safe_source = source.replace("_", "").replace("-", "")[:12]
    return f"ev_{safe_source}_{short_fp}_{short_uuid}"


def make_case_id(
    chain_id: int,
    tx_hash: str,
    subject: str,
) -> str:
    """
    Generate a stable case ID from the audit inputs.

    Format: case_<chain_id>_<tx-prefix-8>_<subj-prefix-6>_<uuid4-8>

    The deterministic prefix lets teammates refer to the same logical case
    even before a full audit completes.  The UUID4 suffix disambiguates
    re-audits of the same transaction.
    """
    tx_clean = tx_hash.lower().lstrip("0x")[:8]
    subj_clean = subject.lower().lstrip("0x")[:6]
    short_uuid = uuid.uuid4().hex[:8]
    return f"case_{chain_id}_{tx_clean}_{subj_clean}_{short_uuid}"


def make_request_fingerprint(request_payload: object) -> str:
    """
    Compute a SHA-256 fingerprint of a canonicalized request payload.
    Used in EvidenceRecord.request_fingerprint.

    Returns string in format: sha256:<hex>
    """
    digest = sha256_of_canonical(request_payload)
    return f"sha256:{digest}"


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(UTC)
