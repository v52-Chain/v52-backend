"""Verdict enum — five possible outcomes of the Claim Auditor."""

from enum import StrEnum


class Verdict(StrEnum):
    """
    Deterministic verdict produced by the Claim Auditor.
    Each verdict MUST cite evidence records.  IA (L5) only explains, never decides.
    """

    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    MISLEADING = "MISLEADING"
    REFUTED = "REFUTED"
    UNKNOWN = "UNKNOWN"
