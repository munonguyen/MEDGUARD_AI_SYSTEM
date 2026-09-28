from __future__ import annotations

from app.models.adaptive_routing import KevDecisionSignal, ModelTier, SeverityAgent, SeverityChoice
from app.services.adaptive_dispatcher import resolve_adaptive_route


def _kev(
    choice: SeverityChoice,
    *,
    score: float,
    confidence: float = 0.94,
    probabilities: dict[str, float] | None = None,
) -> KevDecisionSignal:
    return KevDecisionSignal(
        choice=choice,
        severity_score=score,
        choice_confidence=confidence,
        score_confidence=confidence,
        probabilities=probabilities
        or {
            choice.value: 0.94,
            "ROUTINE": 0.02 if choice != SeverityChoice.ROUTINE else 0.94,
            "URGENT": 0.02 if choice != SeverityChoice.URGENT else 0.94,
            "EMERGENCY": 0.02 if choice != SeverityChoice.EMERGENCY else 0.94,
        },
        source="test",
    )


def test_emergency_lock_cannot_be_downgraded_by_kev() -> None:
    decision = resolve_adaptive_route(
        clinical_task="acute_symptom",
        clinical_result={"urgency": "EMERGENCY", "emergency_flag": True},
        kev=_kev(SeverityChoice.ROUTINE, score=0.4),
        kev_mode="enforced",
    )

    assert decision.agent == SeverityAgent.EMERGENCY
    assert decision.resolved_severity == "EMERGENCY"
    assert decision.emergency_lock is True
    assert decision.model_tier == ModelTier.DEEP


def test_kev_disagreement_routes_to_uncertain_not_new_severity() -> None:
    decision = resolve_adaptive_route(
        clinical_task="acute_symptom",
        clinical_result={"urgency": "ROUTINE", "trace": {"details": {"fact_coverage": 0.9}}},
        kev=_kev(SeverityChoice.URGENT, score=2.8),
        kev_mode="enforced",
    )

    assert decision.resolved_severity == "ROUTINE"
    assert decision.agent == SeverityAgent.UNCERTAIN
    assert decision.requires_review is True
    assert "kev_choice_disagrees_with_clinical_result" in decision.reasons


def test_choice_score_disagreement_routes_to_uncertain() -> None:
    decision = resolve_adaptive_route(
        clinical_task="acute_symptom",
        clinical_result={"urgency": "URGENT", "trace": {"details": {"fact_coverage": 0.9}}},
        kev=_kev(SeverityChoice.URGENT, score=0.5),
        kev_mode="enforced",
    )

    assert decision.resolved_severity == "URGENT"
    assert decision.agent == SeverityAgent.UNCERTAIN
    assert "kev_score_disagrees_with_clinical_result" in decision.reasons


def test_low_coverage_uncertainty_requests_clarification() -> None:
    decision = resolve_adaptive_route(
        clinical_task="acute_symptom",
        clinical_result={"urgency": "ROUTINE", "trace": {"details": {"fact_coverage": 0.4}}},
        kev=_kev(SeverityChoice.UNKNOWN, score=2.0),
        kev_mode="enforced",
    )

    assert decision.agent == SeverityAgent.UNCERTAIN
    assert decision.requires_clarification is True
    assert decision.requires_review is True


def test_high_confidence_agreement_can_use_fast_tier_for_routine() -> None:
    decision = resolve_adaptive_route(
        clinical_task="self_care",
        clinical_result={"urgency": "ROUTINE", "trace": {"details": {"fact_coverage": 0.95}}},
        kev=_kev(SeverityChoice.ROUTINE, score=0.8),
        kev_mode="enforced",
    )

    assert decision.agent == SeverityAgent.ROUTINE
    assert decision.resolved_severity == "ROUTINE"
    assert decision.model_tier == ModelTier.FAST
    assert decision.requires_review is False


def test_shadow_mode_never_changes_clinical_agent() -> None:
    decision = resolve_adaptive_route(
        clinical_task="acute_symptom",
        clinical_result={"urgency": "URGENT"},
        kev=_kev(SeverityChoice.ROUTINE, score=0.4),
        kev_mode="shadow",
    )

    assert decision.agent == SeverityAgent.URGENT
    assert decision.resolved_severity == "URGENT"
    assert decision.model_tier == ModelTier.STANDARD


def test_out_of_scope_needs_task_router_agreement() -> None:
    clinical = resolve_adaptive_route(
        clinical_task="acute_symptom",
        clinical_result={"urgency": "ROUTINE"},
        kev=_kev(SeverityChoice.OUT_OF_SCOPE, score=0.0),
        kev_mode="enforced",
    )
    administrative = resolve_adaptive_route(
        clinical_task="administrative",
        clinical_result={"urgency": "ROUTINE"},
        kev=_kev(SeverityChoice.OUT_OF_SCOPE, score=0.0),
        kev_mode="enforced",
    )

    assert clinical.agent == SeverityAgent.UNCERTAIN
    assert administrative.agent == SeverityAgent.NON_CLINICAL
    assert administrative.model_tier == ModelTier.FAST


def test_unresolved_clinical_disposition_uses_uncertain_agent() -> None:
    decision = resolve_adaptive_route(
        clinical_task="general_medical",
        clinical_result={"trace": {"details": {"fact_coverage": 0.8}}},
        kev=_kev(SeverityChoice.UNKNOWN, score=2.0),
        kev_mode="enforced",
    )

    assert decision.resolved_severity is None
    assert decision.agent == SeverityAgent.UNCERTAIN
    assert decision.model_tier == ModelTier.DEEP
