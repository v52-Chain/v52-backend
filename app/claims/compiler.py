"""
Claim compiler stub (OWNER: Omar).

Transforms raw claim text into structured predicates.
For P0, uses controlled templates; LLM is not required.
"""

from __future__ import annotations

from app.models.claim import ClaimAuditRequest, Predicate


def compile_claim(request: ClaimAuditRequest) -> list[Predicate]:
    """
    Parse a claim string into verifiable predicates.

    STUB — Omar implements the full compiler.
    Returns a single unresolved predicate for the raw claim.
    """
    return [
        Predicate(
            id="p_raw_claim",
            statement=request.claim,
            result=None,
            reasoning="Predicate compilation pending Omar's implementation.",
        )
    ]
