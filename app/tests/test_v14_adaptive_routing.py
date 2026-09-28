from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from app.models.adaptive_routing import AgentTier, KevDecisionSignal, SeverityChoice
from app.services.adaptive_dispatcher import adjudicate_uncertain_route, resolve_adaptive_route
from app.services.severity_agent_policy import profile_for_tier


def kev(
    choice: str,
    *,
    probs: dict[str, float] | None = None,
    score: float | None = None,
    confidence: float = 0.9,
    source: str = "kev",
) -> KevDecisionSignal:
    return KevDecisionSignal(
        choice=SeverityChoice(choice),
        probabilities=probs or {choice: 1.0},
        severity_score=score,
        choice_confidence=confidence,
        score_confidence=confidence,
        source=source,
    )


def result(urgency: str = "ROUTINE", *, emergency: bool = False, coverage: float = 1.0):
    return {
        "urgency": urgency,
        "emergency_flag": emergency,
        "red_flags": [],
        "trace": {"details": {"fact_coverage": coverage}},
    }


def test_hard_emergency_floor_bypasses_kev():
    route = resolve_adaptive_route(
        clinical_task="acute_symptom",
        clinical_result=result("EMERGENCY", emergency=True),
        kev=kev("ROUTINE", score=0.2),
        kev_mode="enforced",
    )
    assert route.agent_tier == AgentTier.EMERGENCY
    assert route.effective_severity == "EMERGENCY"
    assert route.requires_jev is False


def test_shadow_mode_never_changes_validated_route():
    route = resolve_adaptive_route(
        clinical_task="acute_symptom",
        clinical_result=result("URGENT"),
        kev=kev("ROUTINE", score=0.2),
        kev_mode="shadow",
    )
    assert route.agent_tier == AgentTier.URGENT


def test_enforced_kev_can_upgrade_but_not_downgrade_clinical_floor():
    upgrade = resolve_adaptive_route(
        clinical_task="acute_symptom",
        clinical_result=result("ROUTINE"),
        kev=kev(
            "URGENT",
            probs={"ROUTINE": 0.05, "URGENT": 0.9, "EMERGENCY": 0.05},
            score=2.6,
        ),
        kev_mode="enforced",
    )
    assert upgrade.agent_tier == AgentTier.URGENT

    downgrade = resolve_adaptive_route(
        clinical_task="acute_symptom",
        clinical_result=result("URGENT"),
        kev=kev(
            "ROUTINE",
            probs={"ROUTINE": 0.94, "URGENT": 0.04, "EMERGENCY": 0.02},
            score=0.7,
        ),
        kev_mode="enforced",
    )
    assert downgrade.agent_tier == AgentTier.URGENT
    assert "clinical_floor_prevented_downgrade" in downgrade.reasons


def test_low_coverage_boundary_prefers_one_clarification_turn():
    route = resolve_adaptive_route(
        clinical_task="acute_symptom",
        clinical_result=result("ROUTINE", coverage=0.3),
        kev=kev(
            "URGENT",
            probs={"ROUTINE": 0.41, "URGENT": 0.43, "EMERGENCY": 0.16},
            score=2.3,
            confidence=0.45,
        ),
        kev_mode="enforced",
    )
    assert route.agent_tier == AgentTier.CLARIFICATION
    assert route.requires_clarification is True
    assert route.requires_jev is False


def test_adequate_coverage_boundary_uses_jev_not_other_severity_agents():
    route = resolve_adaptive_route(
        clinical_task="acute_symptom",
        clinical_result=result("ROUTINE", coverage=0.9),
        kev=kev(
            "URGENT",
            probs={"ROUTINE": 0.4, "URGENT": 0.45, "EMERGENCY": 0.15},
            score=2.4,
            confidence=0.5,
        ),
        kev_mode="enforced",
    )
    assert route.agent_tier == AgentTier.DEEP
    assert route.requires_jev is True


def test_choice_score_disagreement_is_not_silently_dispatched():
    route = resolve_adaptive_route(
        clinical_task="acute_symptom",
        clinical_result=result("ROUTINE", coverage=0.9),
        kev=kev(
            "ROUTINE",
            probs={"ROUTINE": 0.9, "URGENT": 0.06, "EMERGENCY": 0.04},
            score=3.7,
            confidence=0.9,
        ),
        kev_mode="enforced",
    )
    assert route.requires_jev is True
    assert route.agent_tier == AgentTier.DEEP


def test_unknown_low_coverage_clarifies_unknown_high_coverage_adjudicates():
    low = resolve_adaptive_route(
        clinical_task="acute_symptom",
        clinical_result=result("ROUTINE", coverage=0.2),
        kev=kev("UNKNOWN", confidence=0.8),
        kev_mode="enforced",
    )
    assert low.agent_tier == AgentTier.CLARIFICATION

    high = resolve_adaptive_route(
        clinical_task="acute_symptom",
        clinical_result=result("ROUTINE", coverage=0.9),
        kev=kev("UNKNOWN", confidence=0.8),
        kev_mode="enforced",
    )
    assert high.agent_tier == AgentTier.DEEP
    assert high.requires_jev is True


def test_out_of_scope_only_wins_when_task_is_not_specific_clinical_work():
    allowed = resolve_adaptive_route(
        clinical_task="general_medical",
        clinical_result=result("ROUTINE"),
        kev=kev("OUT_OF_SCOPE", confidence=0.95),
        kev_mode="enforced",
    )
    assert allowed.agent_tier == AgentTier.NON_CLINICAL

    conflict = resolve_adaptive_route(
        clinical_task="lab_interpretation",
        clinical_result=result("ROUTINE"),
        kev=kev("OUT_OF_SCOPE", confidence=0.95),
        kev_mode="enforced",
    )
    assert conflict.agent_tier == AgentTier.DEEP
    assert conflict.requires_jev is True


def test_jev_adjudication_returns_exactly_one_severity_agent():
    pending = resolve_adaptive_route(
        clinical_task="acute_symptom",
        clinical_result=result("URGENT", coverage=0.9),
        kev=kev("UNKNOWN", confidence=0.55),
        kev_mode="enforced",
    )
    resolved = adjudicate_uncertain_route(decision=pending, clinical_result=result("URGENT", coverage=0.9))
    assert resolved.agent_tier == AgentTier.URGENT
    assert resolved.effective_severity == "URGENT"
    assert resolved.requires_jev is True


@pytest.mark.parametrize(
    ("tier", "expected_model", "max_output", "reviewer"),
    [
        (AgentTier.ROUTINE, "free-routine", 410, False),
        (AgentTier.URGENT, "free-urgent", 620, False),
        (AgentTier.EMERGENCY, "free-emergency", 320, False),
        (AgentTier.DEEP, "deep-clinical", 700, True),
    ],
)
def test_severity_profiles_use_one_model_alias_per_tier(tier, expected_model, max_output, reviewer):
    settings = SimpleNamespace(
        routine_agent_model="free-routine",
        urgent_agent_model="free-urgent",
        emergency_agent_model="free-emergency",
        clinical_research_model="deep-clinical",
        routine_agent_max_input_tokens=3500,
        urgent_agent_max_input_tokens=5500,
        emergency_agent_max_input_tokens=2500,
        routine_agent_max_output_tokens=410,
        urgent_agent_max_output_tokens=620,
        emergency_agent_max_output_tokens=320,
        agent_max_input_tokens=12000,
        research_max_output_tokens=700,
    )
    profile = profile_for_tier(tier, settings)
    assert profile.model == expected_model
    assert profile.max_output_tokens == max_output
    assert profile.reviewer_required is reviewer


def test_kev_signal_normalizes_probabilities_and_reports_margin():
    signal = kev(
        "URGENT",
        probs={"ROUTINE": 1, "URGENT": 7, "EMERGENCY": 2},
        score=2.3,
        confidence=0.7,
    )
    assert math.isclose(sum(signal.probabilities.values()), 1.0)
    assert math.isclose(signal.margin, 0.5)
