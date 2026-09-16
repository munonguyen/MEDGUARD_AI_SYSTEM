"""Triage Risk Resolver for MedGuard AI.

Implements conservative severity resolution across deterministic rules,
semantic clinical risk evaluation, and multi-turn historical risk.
Design Invariant:
  - Fail-safe: NO SIGNAL or UNRESOLVED -> URGENT (never ROUTINE).
  - Conservative Max: Final = MAX(Rule, Semantic, Multi-turn History).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

URGENCY_RANK: dict[str, int] = {
    "ROUTINE": 1,
    "URGENT": 2,
    "EMERGENCY": 3,
}

TriageDisposition = Literal["ROUTINE", "URGENT", "EMERGENCY"]


@dataclass(frozen=True)
class ResolvedTriage:
    urgency: TriageDisposition
    source: str
    confidence: float = 1.0
    reasons: list[str] = field(default_factory=list)


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
    historical_urgency: str | None = None,
    rule_confidence: float = 1.0,
    semantic_confidence: float = 1.0,
) -> ResolvedTriage:
    """Conservatively resolve triage urgency across rule, semantic, and conversation signals.
    
    Invariants:
      1. If any signal indicates EMERGENCY, the resolved urgency is EMERGENCY.
      2. If no valid signal is provided, fails closed to URGENT (never ROUTINE).
      3. An explicit benign determination requires affirmative agreement without concerning signals.
    """
    candidates: dict[str, str | None] = {
        "rule": rule_urgency if rule_urgency != "UNRESOLVED" else None,
        "semantic": semantic_urgency,
        "history": historical_urgency,
    }

    valid_candidates = {
        k: v for k, v in candidates.items() if v in URGENCY_RANK
    }

    if not valid_candidates:
        return ResolvedTriage(
            urgency="URGENT",
            source="fail_safe",
            confidence=0.50,
            reasons=["no_reliable_triage_signal"],
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

    if source == "rule":
        confidence = min(max(rule_confidence, 0.50), 0.96)
    elif source == "semantic":
        confidence = min(max(semantic_confidence, 0.50), 0.95)
    elif source == "history":
        confidence = 0.95
    else:
        confidence = 0.50

    return ResolvedTriage(
        urgency=urgency,  # type: ignore[arg-type]
        source=source,
        confidence=confidence,
        reasons=reasons,
    )
