"""Contribution Analysis for direct, evidence-backed flow."""

from __future__ import annotations

import logging
from decimal import Decimal

from app.models.claim import ContributionSummary, TokenAmountValue
from app.models.protocol import ProtocolAction

logger = logging.getLogger(__name__)


class DirectFlowAnalysis:
    """Compute the MVP contribution buckets required by FRANCO.md."""

    def analyze(
        self,
        protocol_action: ProtocolAction,
        subject: str,
    ) -> ContributionSummary:
        """
        Separate observed protocol volume from amount attributable to the subject.

        This MVP is intentionally conservative:
        - no decoded swap means UNKNOWN buckets;
        - a decoded swap without a proven subject contribution keeps attribution at 0;
        - all values remain integer strings with token decimals metadata when available.
        """
        if protocol_action.swap is None:
            warning = (
                "Contribution analysis has insufficient decoded protocol data. "
                "No value was attributed to the subject."
            )
            logger.warning("DirectFlowAnalysis lacks decoded swap evidence.")
            return ContributionSummary(
                subject=subject,
                unknown_or_unattributable=TokenAmountValue(raw="0"),
                limits={"max_hops": 1},
                warnings=[warning],
            )

        swap = protocol_action.swap
        volume = _amount(
            raw=swap.amount_in_raw,
            decimals=swap.token_in.decimals,
            symbol=swap.token_in.symbol,
        )
        evidence_ids = list(
            dict.fromkeys(swap.evidence_ids + protocol_action.contribution_evidence_ids)
        )

        attributable_raw = (
            swap.amount_in_raw if protocol_action.subject_contribution_proven else "0"
        )
        unknown_raw = "0"
        if not protocol_action.subject_contribution_proven:
            unknown_raw = swap.amount_in_raw

        warnings = list(protocol_action.warnings) + list(swap.warnings)
        if not protocol_action.subject_contribution_proven:
            warnings.append(
                "The subject is connected to the case, but direct value attribution was not proven."
            )

        return ContributionSummary(
            subject=subject,
            amount_in_raw=swap.amount_in_raw,
            amount_out_raw=swap.amount_out_raw,
            token_in_symbol=swap.token_in.symbol,
            token_out_symbol=swap.token_out.symbol,
            percentage_of_pool_volume=_percentage(attributable_raw, swap.amount_in_raw),
            counterparty_volume=volume,
            case_flow=volume,
            attributable_value=_amount(
                raw=attributable_raw,
                decimals=swap.token_in.decimals,
                symbol=swap.token_in.symbol,
            ),
            unknown_or_unattributable=_amount(
                raw=unknown_raw,
                decimals=swap.token_in.decimals,
                symbol=swap.token_in.symbol,
            ),
            evidence_ids=evidence_ids,
            limits={"max_hops": 1},
            warnings=warnings,
        )


def _amount(raw: str, decimals: int | None = None, symbol: str | None = None) -> TokenAmountValue:
    return TokenAmountValue(raw=str(raw), decimals=decimals, symbol=symbol)


def _percentage(part: str, whole: str) -> str | None:
    try:
        denominator = Decimal(whole)
        if denominator == 0:
            return None
        return str((Decimal(part) / denominator) * Decimal(100))
    except Exception:
        return None
