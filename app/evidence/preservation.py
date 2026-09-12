"""
Evidence preservation — canonical JSON serialization and SHA-256 hashing.

Rules:
  - Raw content is hashed BEFORE any transformation.
  - The hash is stable: same content always produces the same digest.
  - Canonical JSON uses sorted keys and no extra whitespace.
  - No secrets are written to disk as part of the raw payload.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonicalize(data: Any) -> bytes:
    """
    Serialize data to canonical JSON (sorted keys, no trailing whitespace, UTF-8).
    This is the stable wire format used before computing SHA-256.
    """
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_default_serializer,
    ).encode("utf-8")


def sha256_of(data: bytes) -> str:
    """Return lowercase hex SHA-256 digest of the given bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_of_canonical(obj: Any) -> str:
    """
    Compute a stable SHA-256 over the canonical JSON representation of obj.
    Use this to fingerprint requests and raw responses.
    """
    return sha256_of(canonicalize(obj))


def _default_serializer(obj: Any) -> Any:
    """JSON serializer for types not handled by the standard library."""
    # datetime → ISO 8601 string
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    # bytes → hex string
    if isinstance(obj, (bytes, bytearray)):
        return obj.hex()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
