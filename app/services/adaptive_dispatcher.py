from __future__ import annotations

from typing import Any

from app.models.adaptive_routing import AdaptiveRouteDecision, AgentTier, KevDecisionSignal, SeverityChoice
from app.models.jev import DecisionState
from app.services.jev_engine import evaluate_jev_decision


_RANK = {"ROUTINE": 0, "URGENT": 1, "EMERGENCY": 2}


def _severity_from_score(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 3.35:
        return "EMERGENCY"
    if score >= 1.75:
        return "URGENT"
    return "ROUTINE"


def _baseline_urgency(clinical_result: dict[str, Any]) -> str:
    urgency = str(clinical_result.get("urgency") or "ROUTINE").upper()
    return urgency if urgency in _RANK else "ROUTINE"


def _fact_coverage(clinical_result: dict[str, Any]) -> float:
    trace = clinical_result.get("trace") if isinstance(clinical_result.get("trace"), dict) else {}
    details = trace.get("details") if isinstance(trace, dict) else {}
    try:
        return max(0.0, min(1.0, float((details or {}).get("fact_coverage", 1.0))))
    except (TypeError, ValueError):
        return 1.0


def _tier_for(severity: str) -> AgentTier:
    return {
        "ROUTINE": AgentTier.ROUTINE,
        "URGENT": AgentTier.URGENT,
        "EMERGENCY": AgentTier.EMERGENCY,
    }[severity]


def resolve_adaptive_route(
    *,
    clinical_task: str,
    clinical_result: dict[str, Any],
    kev: KevDecisionSignal,
    kev_mode: str = "shadow",
    min_confidence: float = 0.72,
    min_margin: float = 0.15,
    low_coverage_threshold: float = 0.55,
) -> AdaptiveRouteDecision:
    """Resolve one and only one patient-facing severity agent.

    The already validated clinical result acts as a non-downgradable floor.
    Generic Kev checkpoints are advisory in shadow mode.  In enforced mode Kev
    may upgrade routing, or trigger clarification/Jev on uncertainty, but may
    never lower that floor.
    """
    baseline = _baseline_urgency(clinical_result)
    coverage = _fact_coverage(clinical_result)

    if bool(clinical_result.get("emergency_flag")) or baseline == "EMERGENCY":
        return AdaptiveRouteDecision(
            choice=SeverityChoice.EMERGENCY,
            agent_tier=AgentTier.EMERGENCY,
            clinical_task=clinical_task,
            effective_severity="EMERGENCY",
            confidence=1.0,
            margin=1.0,
            fact_coverage=coverage,
            reasons=["hard_or_resolved_emergency_floor"],
        )

    if kev_mode != "enforced" or kev.source == "clinical_fallback":
        return AdaptiveRouteDecision(
            choice=SeverityChoice(baseline),
            agent_tier=_tier_for(baseline),
            clinical_task=clinical_task,
            effective_severity=baseline,
            confidence=kev.choice_confidence,
            margin=kev.margin,
            fact_coverage=coverage,
            reasons=["validated_clinical_route", f"kev_mode_{kev_mode}"],
        )

    if kev.choice == SeverityChoice.OUT_OF_SCOPE:
        if clinical_task in {"general_medical", "administrative"} and kev.choice_confidence >= min_confidence:
            return AdaptiveRouteDecision(
                choice=kev.choice,
                agent_tier=AgentTier.NON_CLINICAL,
                clinical_task=clinical_task,
                confidence=kev.choice_confidence,
                margin=kev.margin,
                fact_coverage=coverage,
                reasons=["kev_out_of_scope_high_confidence"],
            )
        return AdaptiveRouteDecision(
            choice=SeverityChoice.UNKNOWN,
            agent_tier=AgentTier.DEEP,
            clinical_task=clinical_task,
            requires_jev=True,
            confidence=kev.choice_confidence,
            margin=kev.margin,
            fact_coverage=coverage,
            reasons=["out_of_scope_conflicts_with_clinical_task"],
        )

    if kev.choice == SeverityChoice.UNKNOWN:
        if coverage < low_coverage_threshold:
            return AdaptiveRouteDecision(
                choice=kev.choice,
                agent_tier=AgentTier.CLARIFICATION,
                clinical_task=clinical_task,
                requires_clarification=True,
                confidence=kev.choice_confidence,
                margin=kev.margin,
                fact_coverage=coverage,
                reasons=["kev_unknown_low_fact_coverage"],
            )
        return AdaptiveRouteDecision(
            choice=kev.choice,
            agent_tier=AgentTier.DEEP,
            clinical_task=clinical_task,
            requires_jev=True,
            confidence=kev.choice_confidence,
            margin=kev.margin,
            fact_coverage=coverage,
            reasons=["kev_unknown_despite_adequate_coverage"],
        )

    score_severity = _severity_from_score(kev.severity_score)
    disagreement = score_severity is not None and score_severity != kev.choice.value
    boundary = kev.choice_confidence < min_confidence or kev.margin < min_margin

    if boundary or disagreement:
        if coverage < low_coverage_threshold:
            return AdaptiveRouteDecision(
                choice=SeverityChoice.UNKNOWN,
                agent_tier=AgentTier.CLARIFICATION,
                clinical_task=clinical_task,
                requires_clarification=True,
                confidence=kev.choice_confidence,
                margin=kev.margin,
                fact_coverage=coverage,
                reasons=["kev_boundary", "missing_facts_prefer_clarification"],
            )
        return AdaptiveRouteDecision(
            choice=SeverityChoice.UNKNOWN,
            agent_tier=AgentTier.DEEP,
            clinical_task=clinical_task,
            requires_jev=True,
            confidence=kev.choice_confidence,
            margin=kev.margin,
            fact_coverage=coverage,
            reasons=["kev_boundary_or_choice_score_disagreement"],
        )

    kev_severity = kev.choice.value
    effective = kev_severity if _RANK[kev_severity] >= _RANK[baseline] else baseline
    reasons = ["kev_confident_single_path"]
    if effective != kev_severity:
        reasons.append("clinical_floor_prevented_downgrade")
    return AdaptiveRouteDecision(
        choice=SeverityChoice(effective),
        agent_tier=_tier_for(effective),
        clinical_task=clinical_task,
        effective_severity=effective,
        confidence=kev.choice_confidence,
        margin=kev.margin,
        fact_coverage=coverage,
        reasons=reasons,
    )


def adjudicate_uncertain_route(
    *,
    decision: AdaptiveRouteDecision,
    clinical_result: dict[str, Any],
) -> AdaptiveRouteDecision:
    """Use existing Jev only for an already-declared uncertain boundary.

    This keeps Jev out of the normal cheap path.  The result remains bounded by
    the current clinical floor and Jev's own hard-safety invariants.
    """
    if not decision.requires_jev:
        return decision
    baseline = _baseline_urgency(clinical_result)
    state = DecisionState(
        triage_floor=baseline,
        reasoner_triage=baseline,
        verifier_pending=True,
        risk_features=tuple(clinical_result.get("red_flags") or ()),
        hard_safety_flags=("emergency_floor_locked",) if baseline == "EMERGENCY" else (),
        candidate_actions=tuple(clinical_result.get("next_steps") or ()),
        confidence=decision.confidence,
        fact_coverage=decision.fact_coverage,
        symptoms_summary="",
    )
    jev = evaluate_jev_decision(state)
    severity = jev.triage_recommendation
    return AdaptiveRouteDecision(
        choice=SeverityChoice(severity),
        agent_tier=_tier_for(severity),
        clinical_task=decision.clinical_task,
        effective_severity=severity,
        requires_jev=True,
        confidence=jev.confidence,
        margin=decision.margin,
        fact_coverage=decision.fact_coverage,
        reasons=[*decision.reasons, "jev_boundary_adjudication", *jev.policy_rules_triggered],
    )
