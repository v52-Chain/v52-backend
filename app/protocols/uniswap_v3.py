"""
Uniswap V3 Resolver — stub interface (OWNER: Jhamil).

This module defines the resolver interface that Jhamil must implement.
Saúl provides:
  - The types (ProtocolAction, SwapEvent, TokenInfo) in app/models/protocol.py
  - The raw evidence via EvidenceRecord IDs that point to vault files.

Jhamil implements:
  - resolve() — reads from evidence records, decodes events, returns ProtocolAction.

The resolver NEVER calls providers directly.  It consumes preserved evidence only.

Rule from architecture doc section 11:
  PROTOCOL VOLUME != SUBJECT CONTRIBUTION
"""

from __future__ import annotations

import logging
from typing import Any

from app.models.evidence import EvidenceRecord
from app.models.protocol import ProtocolAction

logger = logging.getLogger(__name__)


class UniswapV3Resolver:
    """
    Resolves Uniswap V3 swap semantics from preserved L0/L1 evidence.

    STUB — pending Jhamil's implementation with real fixtures.

    Expected inputs:
      - l0_record: L0 EvidenceRecord (RPC tx, receipt, logs)
      - l0_raw: Raw dict from the vault (tx, receipt, block, logs)
      - l1_record: L1 EvidenceRecord (The Graph response)
      - l1_raw: Raw dict from the vault (GraphQL response with swaps)
      - subject: subject address to evaluate contribution for

    Expected output:
      ProtocolAction with SwapEvent, token metadata and contribution flag.
    """

    def resolve(
        self,
        l0_record: EvidenceRecord | None,
        l0_raw: dict[str, Any] | None,
        l1_record: EvidenceRecord | None,
        l1_raw: dict[str, Any] | None,
        subject: str,
    ) -> ProtocolAction:
        """
        Decode Uniswap V3 swap events from evidence.

        STUB: Returns a ProtocolAction with a WARNING until Jhamil implements this.
        The stub ensures the pipeline doesn't crash and the warning is visible.
        """
        warnings = [
            "UniswapV3Resolver is not yet implemented. "
            "Protocol decoding pending Jhamil's fixtures and implementation."
        ]
        logger.warning("UniswapV3Resolver.resolve() called — stub returning UNKNOWN action.")
        return ProtocolAction(
            protocol="uniswap_v3",
            action="swap",
            subject_address=subject,
            warnings=warnings,
            subject_contribution_proven=False,
        )
