"""Response Obligation Graph for MedGuard AI System.

Constructs explicit contractual obligations (required vs. forbidden content) for
the Grounded Answer Writer based on resolved triage level, clinical safety floor,
and specific conditions like dual crisis, severe burn, toxidrome, or stroke.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.canonical_clinical_state import CanonicalClinicalState


@dataclass(frozen=True)
class ResponseObligationGraph:
    """Explicit content contract governing patient-facing text generation."""
    triage: str
    policy_tier: str
    required_content: tuple[str, ...] = field(default_factory=tuple)
    forbidden_content: tuple[str, ...] = field(default_factory=tuple)
    crisis_support_required: bool = False
    evidence_claims_required: tuple[str, ...] = field(default_factory=tuple)

    def is_required(self, obligation: str) -> bool:
        return obligation in self.required_content

    def is_forbidden(self, obligation: str) -> bool:
        return obligation in self.forbidden_content


def build_response_obligations(
    triage_level: str,
    clinical_state: CanonicalClinicalState | None = None,
    *,
    is_dual_crisis: bool = False,
    is_toxidrome: bool = False,
    topic: str = "",
) -> ResponseObligationGraph:
    """Build the formal response obligation graph for a given clinical encounter."""
    level = triage_level.upper()
    req: list[str] = []
    forb: list[str] = []
    claims: list[str] = []

    if level == "EMERGENCY":
        tier = "EMERGENCY"
        req.extend([
            "state_urgency",
            "medical_emergency_action",
            "do_not_delay",
            "immediate_hospital_evaluation",
        ])
        forb.extend([
            "home_monitoring",
            "wait_until_tomorrow",
            "false_reassurance",
            "self_treatment_only",
            "delay_action",
        ])
        if is_dual_crisis or (clinical_state and any("suicid" in s for s in clinical_state.negations + clinical_state.active_symptom_names)):
            req.extend([
                "self_harm_support",
                "crisis_hotline",
                "do_not_stay_alone",
            ])
        if is_toxidrome:
            req.extend([
                "poison_center_guidance",
                "bring_substance_container",
            ])
            forb.append("induce_vomiting")

    elif level == "URGENT":
        tier = "URGENT"
        req.extend([
            "prompt_evaluation_timeframe",
            "red_flag_warning",
            "specialty_consultation",
            "seek_care_within_12_24h",
        ])
        forb.extend([
            "false_reassurance",
            "dismissive_language",
        ])

    elif level == "ROUTINE":
        tier = "ROUTINE"
        req.extend([
            "supportive_care",
            "when_to_seek_care",
            "progression_monitoring",
        ])
        forb.extend([
            "excessive_emergency_alarm",
            "unsupported_diagnosis",
            "panic_inducing_language",
        ])

    else:
        tier = "UNRESOLVED"
        req.extend([
            "state_insufficient_data",
            "targeted_clarification",
            "safety_net",
        ])
        forb.extend([
            "false_certainty",
            "unsupported_diagnosis",
            "unfounded_reassurance",
        ])

    # Add specific claims based on clinical state symptoms
    if clinical_state:
        for s in clinical_state.symptoms:
            concept = s.get("concept") or s.get("name")
            if concept and concept not in claims:
                claims.append(concept)

    return ResponseObligationGraph(
        triage=level,
        policy_tier=tier,
        required_content=tuple(req),
        forbidden_content=tuple(forb),
        crisis_support_required=is_dual_crisis,
        evidence_claims_required=tuple(claims),
    )
