"""Deterministic safety resolver for MedGuard's multi-signal triage layer.

V14 authority model:
1. The deterministic hard safety floor is the fail-closed authority.
2. Clinical reasoner + approved verifier determine normal ROUTINE/URGENT/EMERGENCY
   disposition. Their output is never downgraded by Jev.
3. Jev is advisory outside an explicit ``emergency_lock`` decision. A Jev-only
   disagreement requests clarification/human review instead of silently forcing
   benign cases into URGENT/EMERGENCY.
4. The resolver emits constraints, not patient-facing prose. Response writing
   belongs to the selected agent; the downstream output gate only releases or
   rejects that answer.
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


def _is_explicit_jev_emergency_lock(tri_result: TriGateResult) -> bool:
    jev = tri_result.gate3_jev
    if jev is None:
        return False
    return (
        getattr(jev, "authority", "advisory") == "emergency_lock"
        and jev.triage_recommendation == "EMERGENCY"
        and jev.action in {"EMERGENCY_NOW", "CALL_115"}
    )


def _primary_candidates(tri_result: TriGateResult) -> list[tuple[str, TriageAcuity, float]]:
    """Return authoritative non-Jev disposition candidates.

    The hard safety floor participates as a monotonic lower bound. Jev is kept
    out of this list deliberately: it can enrich or challenge a decision, but
    it cannot become the normal governing source by merely choosing a higher
    acuity.
    """
    candidates: list[tuple[str, TriageAcuity, float]] = [
        ("hard_safety_floor", tri_result.hard_safety_floor, 0.99),
        ("gate1_reasoner", tri_result.gate1_reasoner_triage, tri_result.gate1_confidence),
    ]
    if tri_result.gate2_verifier and tri_result.gate2_verifier.approved:
        candidates.append(
            (
                "gate2_verifier",
                tri_result.gate2_verifier.verifier_urgency,
                tri_result.gate2_verifier.confidence,
            )
        )
    return candidates


def resolve_tri_gate(tri_result: TriGateResult) -> FinalResolution:
    """Resolve safety constraints without letting Jev author the disposition."""
    invariants: list[str] = ["jev_non_emergency_authority_is_advisory"]

    # Gate 0 remains an unconditional fail-closed emergency authority.
    hard_emergency = tri_result.hard_safety_floor == "EMERGENCY"
    jev_emergency_lock = _is_explicit_jev_emergency_lock(tri_result)

    candidates = _primary_candidates(tri_result)
    governing_source, primary_triage, base_conf = max(
        candidates,
        key=lambda candidate: (_ACUITY_RANK.get(candidate[1], 1), candidate[2]),
    )

    if hard_emergency or jev_emergency_lock:
        final_triage: TriageAcuity = "EMERGENCY"
        final_action: JevAction = "EMERGENCY_NOW"
        allow_home_monitoring = False
        require_review = False
        final_conf = max(base_conf, 0.98)
        governing_source = "hard_safety_floor" if hard_emergency else "jev_emergency_lock"
        invariants.extend(
            (
                "enforce_zero_home_monitoring_for_emergency",
                "mandate_emergency_transit_or_115",
            )
        )
        response_policy = {
            "locked_disposition": "EMERGENCY",
            "required_actions": ["emergency_now", "call_115_or_nearest_emergency_service"],
            "forbidden_advice": ["delay_for_monitoring", "routine_home_care"],
            "output_gate_may_reject_but_not_rewrite": True,
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

    # Normal disposition is owned by the hard floor + reasoner + approved
    # verifier. Jev can challenge the result but cannot silently replace it.
    jev = tri_result.gate3_jev
    jev_upward_disagreement = bool(
        jev
        and _ACUITY_RANK.get(jev.triage_recommendation, 1)
        > _ACUITY_RANK.get(primary_triage, 1)
    )
    jev_blocks_home = bool(jev and not jev.allow_home_monitoring)
    jev_requests_review = bool(jev and jev.require_human_review)

    if primary_triage == "EMERGENCY":
        final_triage = "EMERGENCY"
        final_action = "EMERGENCY_NOW"
        allow_home_monitoring = False
        require_review = False
        final_conf = max(base_conf, 0.96)
        invariants.extend(
            (
                "reasoner_or_verifier_emergency_preserved",
                "enforce_zero_home_monitoring_for_emergency",
            )
        )
        response_policy = {
            "locked_disposition": "EMERGENCY",
            "required_actions": ["emergency_now"],
            "forbidden_advice": ["delay_for_monitoring", "routine_home_care"],
            "output_gate_may_reject_but_not_rewrite": True,
        }

    elif primary_triage == "URGENT":
        final_triage = "URGENT"
        final_action = "SAME_DAY_EVAL"
        allow_home_monitoring = False
        require_review = base_conf < 0.80 or jev_requests_review
        final_conf = max(base_conf, 0.88)
        invariants.append("preserve_reasoner_verifier_urgent_disposition")
        response_policy = {
            "locked_disposition": "URGENT",
            "required_actions": ["same_day_clinical_evaluation"],
            "forbidden_advice": ["routine_home_care_only"],
            "output_gate_may_reject_but_not_rewrite": True,
        }

    else:  # ROUTINE
        final_triage = "ROUTINE"
        if jev_upward_disagreement or jev_blocks_home or jev_requests_review:
            # Do not mislabel the patient as URGENT solely because Jev disagrees.
            # Preserve the advisory signal by requiring clarification/review and
            # withholding a casual home-care endorsement until that conflict is
            # resolved.
            final_action = "AMBIGUOUS_CLARIFY"
            allow_home_monitoring = False
            require_review = True
            final_conf = min(base_conf, 0.79)
            invariants.extend(
                (
                    "jev_disagreement_requests_clarification_not_escalation",
                    "routine_label_not_overridden_by_jev_alone",
                )
            )
            response_policy = {
                "locked_disposition": "ROUTINE",
                "clarification_required": True,
                "advisory_red_flags": list(getattr(jev, "advisory_red_flags", ())) if jev else [],
                "suggested_clarifications": list(getattr(jev, "suggested_clarifications", ())) if jev else [],
                "output_gate_may_reject_but_not_rewrite": True,
            }
        else:
            final_action = "SELF_CARE"
            allow_home_monitoring = True
            require_review = False
            final_conf = min(base_conf, 0.96)
            invariants.append("benign_routine_self_care_permitted")
            response_policy = {
                "locked_disposition": "ROUTINE",
                "required_actions": ["context_specific_self_care", "state_relevant_red_flags"],
                "output_gate_may_reject_but_not_rewrite": True,
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
