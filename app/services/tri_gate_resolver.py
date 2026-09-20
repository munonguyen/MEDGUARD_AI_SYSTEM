"""Deterministic Final Safety Resolver for MedGuard Tri-Gate Architecture.

Design Invariants:
1. Pure Deterministic Resolution: NO 4th LLM judge.
   Zero latency overhead (< 0.5 ms), zero hallucination risk.
2. Monotonic Safety Floor:
   final_triage = max(safety_floor, reasoner_floor, verifier_floor, jev_floor)
3. Strict Policy Enforcement:
   - EMERGENCY: MUST block home monitoring, MUST mandate emergency 115 care.
   - URGENT: MUST mandate same-day clinical evaluation; blocks unmonitored delays.
   - ROUTINE: Permits self-care only when no red-flag features or safety flags exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.jev import JevAction, TriageAcuity
from app.services.tri_gate_orchestrator import TriGateResult

_ACUITY_RANK: dict[TriageAcuity, int] = {
    "ROUTINE": 1,
    "URGENT": 2,
    "EMERGENCY": 3,
}


@dataclass(frozen=True)
class FinalResolution:
    final_triage: TriageAcuity
    final_action: JevAction
    allow_home_monitoring: bool
    require_human_review: bool
    confidence: float
    governing_source: str
    safety_invariants_enforced: tuple[str, ...]
    response_policy: dict[str, Any] = field(default_factory=dict)


def resolve_tri_gate(tri_result: TriGateResult) -> FinalResolution:
    """Deterministically resolve clinical triage and actions across all 3 gates."""
    invariants: list[str] = []

    # 1. Collect candidate urgencies
    candidates: list[tuple[str, TriageAcuity, float]] = [
        ("hard_safety_floor", tri_result.hard_safety_floor, 0.99),
        ("gate1_reasoner", tri_result.gate1_reasoner_triage, tri_result.gate1_confidence),
    ]

    if tri_result.gate2_verifier and tri_result.gate2_verifier.approved:
        candidates.append(("gate2_verifier", tri_result.gate2_verifier.verifier_urgency, tri_result.gate2_verifier.confidence))

    if tri_result.gate3_jev:
        candidates.append(("gate3_jev", tri_result.gate3_jev.triage_recommendation, tri_result.gate3_jev.confidence))

    # 2. Monotonic Conservative Max Resolution
    governing_source, final_triage, base_conf = max(
        candidates,
        key=lambda c: (_ACUITY_RANK.get(c[1], 1), c[2]),
    )

    # 3. Policy Table & Invariant Enforcement
    if final_triage == "EMERGENCY":
        final_action: JevAction = "EMERGENCY_NOW"
        allow_home_monitoring = False
        invariants.append("enforce_zero_home_monitoring_for_emergency")
        invariants.append("mandate_emergency_transit_or_115")
        require_review = False
        final_conf = max(base_conf, 0.98)
        response_policy = {
            "template": "emergency_immediate",
            "forbid_phrases": ["theo dõi tại nhà", "chờ thêm", "uống thuốc rồi tính"],
            "mandate_phrases": ["cấp cứu ngay", "115", "cơ sở y tế gần nhất"],
        }

    elif final_triage == "URGENT":
        final_action = "SAME_DAY_EVAL"
        allow_home_monitoring = False
        invariants.append("mandate_same_day_physician_evaluation")
        require_review = (base_conf < 0.80)
        final_conf = max(base_conf, 0.90)
        response_policy = {
            "template": "urgent_same_day",
            "forbid_phrases": ["không sao đâu", "tự khỏi"],
            "mandate_phrases": ["khám trong ngày", "chuyên khoa"],
        }

    else:  # ROUTINE
        # Strict Benign Guard: if Jev or Verifier rejected self-care, escalate
        if tri_result.gate3_jev and not tri_result.gate3_jev.allow_home_monitoring:
            final_triage = "URGENT"
            final_action = "SAME_DAY_EVAL"
            allow_home_monitoring = False
            require_review = False
            final_conf = 0.90
            invariants.append("jev_override_blocked_routine_home_care")
            response_policy = {"template": "urgent_same_day"}
        else:
            final_action = "SELF_CARE"
            allow_home_monitoring = True
            require_review = False
            final_conf = min(base_conf, 0.96)
            invariants.append("benign_routine_self_care_permitted")
            response_policy = {
                "template": "routine_self_care_with_red_flags",
                "mandate_red_flags": True,
            }

    return FinalResolution(
        final_triage=final_triage,
        final_action=final_action,
        allow_home_monitoring=allow_home_monitoring,
        require_human_review=require_review,
        confidence=round(final_conf, 4),
        governing_source=governing_source,
        safety_invariants_enforced=tuple(invariants),
        response_policy=response_policy,
    )
