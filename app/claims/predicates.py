"""
Claim predicates stub (OWNER: Jhamil).

Verifiable predicates for Ethereum/Uniswap V3 claims.
"""

from __future__ import annotations

from app.models.claim import ContributionSummary, Predicate
from app.models.protocol import ProtocolAction


def evaluate_predicates(
    predicates: list[Predicate],
    protocol_action: ProtocolAction,
    contribution: ContributionSummary,
) -> list[Predicate]:
    """
    Evaluate a list of predicates against evidence.

    STUB — Jhamil implements the full predicate engine.
    Returns predicates unchanged with a stub note.
    """
    return [
        p.model_copy(
            update={
                "reasoning": (
                    "Predicate evaluation pending Jhamil's implementation. "
                    + (p.reasoning or "")
                )
            }
        )
        for p in predicates
    ]
