"""Triage Risk Resolver for MedGuard AI (V6 Architecture).

Implements conservative severity resolution across deterministic rules,
compositional threat reasoning, semantic clinical evaluation, and multi-turn ledger.

Design Invariants:
  - Fail-safe: NO SIGNAL or UNRESOLVED with acute cues -> URGENT / EMERGENCY.
  - Conservative Max: Final = MAX(Rule, Compositional Threat, Semantic, Ledger History).
  - Epistemic Uncertainty Calibration: Distinguishes LOW_RISK from UNRESOLVED.
    Never outputs ROUTINE with high confidence (0.94) on unparsed text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

URGENCY_RANK: dict[str, int] = {
    "ROUTINE": 1,
    "URGENT": 2,
    "EMERGENCY": 3,
}

TriageDisposition = Literal["ROUTINE", "URGENT", "EMERGENCY"]


class SemanticStatus(str, Enum):
    UNDERSTOOD = "UNDERSTOOD"
    PARTIALLY_UNDERSTOOD = "PARTIALLY_UNDERSTOOD"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class ResolvedTriage:
    urgency: TriageDisposition
    source: str
    confidence: float = 1.0
    reasons: list[str] = field(default_factory=list)
    semantic_status: SemanticStatus = SemanticStatus.UNDERSTOOD
    epistemic_warning: bool = False


def highest_urgency(*values: str | None) -> str:
    """Return the highest clinical urgency among valid candidates."""
    valid = [v for v in values if v in URGENCY_RANK]
    if not valid:
        return "URGENT"
    return max(valid, key=lambda x: URGENCY_RANK[x])


def resolve_triage(
    *,
    rule_urgency: str | None,
    semantic_urgency: str | None,
    compositional_urgency: str | None = None,
    historical_urgency: str | None = None,
    rule_confidence: float = 1.0,
    semantic_confidence: float = 1.0,
    compositional_confidence: float = 0.98,
    semantic_status: SemanticStatus | str = SemanticStatus.UNDERSTOOD,
    fact_coverage: float = 1.0,
    has_acute_functional_loss: bool = False,
) -> ResolvedTriage:
    """Conservatively resolve triage urgency across all clinical reasoning layers.
    
    Invariants:
      1. If any signal indicates EMERGENCY, the resolved urgency is EMERGENCY.
      2. If no valid signal is provided, fails closed to URGENT (never ROUTINE).
      3. Epistemic Guard: UNRESOLVED complaint with acute functional cues escalates to URGENT.
      4. Calibration: Confidence is scaled by semantic coverage and epistemic certainty.
    """
    candidates: dict[str, str | None] = {
        "rule": rule_urgency if rule_urgency != "UNRESOLVED" else None,
        "compositional": compositional_urgency,
        "semantic": semantic_urgency,
        "history": historical_urgency,
    }

    valid_candidates = {
        k: v for k, v in candidates.items() if v in URGENCY_RANK
    }

    if not valid_candidates:
        # Epistemic Fail-Safe
        return ResolvedTriage(
            urgency="URGENT",
            source="fail_safe",
            confidence=0.50,
            reasons=["no_reliable_triage_signal"],
            semantic_status=SemanticStatus.UNRESOLVED,
            epistemic_warning=True,
        )

    # Pick the source with the highest severity
    source, urgency = max(
        valid_candidates.items(),
        key=lambda item: URGENCY_RANK[item[1]],
    )

    reasons = []
    for k, v in valid_candidates.items():
        if v == urgency:
            reasons.append(f"{k}_{v.lower()}")

    # Determine base confidence by source
    if source == "compositional":
        confidence = min(max(compositional_confidence + 0.04, 0.70), 0.98)
    elif source == "rule":
        confidence = min(max(rule_confidence, 0.50), 0.96)
    elif source == "semantic":
        confidence = min(max(semantic_confidence, 0.50), 0.95)
    elif source == "history":
        confidence = 0.95
    else:
        confidence = 0.50

    # Epistemic Uncertainty Adjustment (Gate 12 & Gate 13 calibration)
    sem_stat_enum = SemanticStatus(semantic_status) if isinstance(semantic_status, str) else semantic_status
    epistemic_warning = False

    if sem_stat_enum == SemanticStatus.UNRESOLVED:
        if has_acute_functional_loss and urgency == "ROUTINE":
            # Conservative escalation: Unresolved text with acute loss must not be Routine
            urgency = "URGENT"
            source = "epistemic_escalation"
            reasons.append("unresolved_with_acute_functional_loss")
            confidence = 0.55
            epistemic_warning = True
        elif urgency == "ROUTINE":
            # Cap confidence on unparsed low-signal input
            confidence = min(confidence, 0.55)
            epistemic_warning = True
        else:
            confidence = min(confidence, 0.55)
            epistemic_warning = True
    elif sem_stat_enum == SemanticStatus.PARTIALLY_UNDERSTOOD:
        # Scale confidence by fact coverage only when understanding is incomplete
        if urgency != "EMERGENCY" and fact_coverage < 0.50:
            confidence = max(0.50, confidence * (0.60 + 0.40 * fact_coverage))

    return ResolvedTriage(
        urgency=urgency,  # type: ignore[arg-type]
        source=source,
        confidence=round(confidence, 4),
        reasons=reasons,
        semantic_status=sem_stat_enum,
        epistemic_warning=epistemic_warning,
    )
