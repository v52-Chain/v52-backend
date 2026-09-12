"""
Claim Auditor stub (OWNER: Jhamil + Omar).

Combines predicates, evidence and contribution to produce a Verdict.
"""

from __future__ import annotations

from app.models.claim import ContributionSummary, Predicate
from app.models.evidence import EvidenceRecord
from app.models.protocol import ProtocolAction
from app.models.verdict import Verdict


def audit(
    predicates: list[Predicate],
    evidence_for: list[EvidenceRecord],
    evidence_against: list[EvidenceRecord],
    protocol_action: ProtocolAction,
    contribution: ContributionSummary,
) -> tuple[Verdict, str, list[str]]:
    """
    Produce a Verdict from evaluated predicates and evidence.

    Returns (verdict, summary, gaps).

    STUB — returns UNKNOWN until Jhamil + Omar implement the auditor.
    Gaps are surfaced explicitly so the frontend displays limits correctly.
    """
    gaps = [
        "Protocol decoding not complete.",
        "Contribution analysis not complete.",
        "Predicate evaluation not complete.",
    ]
    return (
        Verdict.UNKNOWN,
        "Full auditor pending implementation by Jhamil and Omar.",
        gaps,
    )
