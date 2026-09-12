"""
Contribution Analysis — Direct Flow (OWNER: Jhamil).

Determines what fraction of the observed protocol volume is directly
attributable to the subject.

Rule (architecture doc section 11):
  PROTOCOL VOLUME != SUBJECT CONTRIBUTION

STUB — pending Jhamil's implementation.
"""

from __future__ import annotations

import logging

from app.models.claim import ContributionSummary
from app.models.protocol import ProtocolAction

logger = logging.getLogger(__name__)


class DirectFlowAnalysis:
    """
    Computes subject contribution from a resolved ProtocolAction.

    STUB: Returns a ContributionSummary with a WARNING until Jhamil implements this.
    """

    def analyze(
        self,
        protocol_action: ProtocolAction,
        subject: str,
    ) -> ContributionSummary:
        """
        Compute the subject's direct contribution.

        STUB: Returns unresolved summary with explicit WARNING.
        """
        warnings = [
            "DirectFlowAnalysis is not yet implemented. "
            "Contribution computation pending Jhamil's implementation."
        ]
        logger.warning("DirectFlowAnalysis.analyze() called — stub.")
        return ContributionSummary(
            subject=subject,
            warnings=warnings,
        )
