from __future__ import annotations

from typing import Any

from app.models.adaptive_routing import (
    AdaptiveRouteDecision,
    KevDecisionSignal,
    ModelTier,
    SeverityAgent,
    SeverityChoice,
)


_SEVERITY_RANK = {"ROUTINE": 0, "URGENT": 1, "EMERGENCY": 2}


def _resolved_severity(clinical_result: dict[str, Any]) -> str | None:
    urgency = str(clinical_result.get("urgency") or "").upper()
    return urgency if urgency in _SEVERITY_RANK else None


def _fact_coverage(clinical_result: dict[str, Any]) -> float:
    trace = clinical_result.get("trace") if isinstance(clinical_result.get("trace"), dict) else {}
    details = trace.get("details") if isinstance(trace, dict) else {}
    try:
        return max(0.0, min(1.0, float((details or {}).get("fact_coverage", 1.0))))
    except (TypeError, ValueError):
        return 1.0


def _agent_for(severity: str) -> SeverityAgent:
    return {
        "ROUTINE": SeverityAgent.ROUTINE,
        "URGENT": SeverityAgent.URGENT,
        "EMERGENCY": SeverityAgent.EMERGENCY,
    }[severity]


def _score_band(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 3.35:
        return "EMERGENCY"
    if score >= 1.75:
        return "URGENT"
    return "ROUTINE"


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
    """Choose exactly one response agent without transferring clinical authority.

    Authority contract:
    - explicit emergency lock always selects the emergency path;
    - a validated ROUTINE/URGENT/EMERGENCY result remains the clinical truth;
    - Kev may identify uncertainty, disagreement, or workload difficulty;
    - Kev never upgrades or downgrades the clinical disposition by itself;
    - Jev/Reviewer remains downstream and non-authoring.
    """
    severity = _resolved_severity(clinical_result)
    coverage = _fact_coverage(clinical_result)
    emergency_lock = bool(clinical_result.get("emergency_flag")) or severity == "EMERGENCY"

    if emergency_lock:
        return AdaptiveRouteDecision(
            clinical_task=clinical_task,
            resolved_severity="EMERGENCY",
            agent=SeverityAgent.EMERGENCY,
            model_tier=ModelTier.DEEP,
            emergency_lock=True,
            kev_choice=kev.choice,
            confidence=1.0,
            margin=kev.margin,
            fact_coverage=coverage,
            reasons=["explicit_emergency_lock"],
        )

    # A non-clinical task may be routed away from the severity writer only when
    # both the task router and Kev indicate that shape. Kev alone cannot turn a
    # clinical task into OUT_OF_SCOPE.
    non_clinical_task = clinical_task in {"administrative", "general_non_clinical"}
    if non_clinical_task and kev.choice == SeverityChoice.OUT_OF_SCOPE and kev.choice_confidence >= min_confidence:
        return AdaptiveRouteDecision(
            clinical_task=clinical_task,
            resolved_severity=severity,
            agent=SeverityAgent.NON_CLINICAL,
            model_tier=ModelTier.FAST,
            kev_choice=kev.choice,
            confidence=kev.choice_confidence,
            margin=kev.margin,
            fact_coverage=coverage,
            reasons=["task_and_kev_non_clinical_agreement"],
        )

    if severity is None:
        return AdaptiveRouteDecision(
            clinical_task=clinical_task,
            resolved_severity=None,
            agent=SeverityAgent.UNCERTAIN,
            model_tier=ModelTier.DEEP,
            requires_clarification=coverage < low_coverage_threshold,
            requires_review=True,
            kev_choice=kev.choice,
            confidence=kev.choice_confidence,
            margin=kev.margin,
            fact_coverage=coverage,
            reasons=["clinical_disposition_unresolved"],
        )

    # Disabled/shadow Kev never changes the selected severity agent. It can be
    # observed and calibrated without affecting the patient-facing path.
    if kev_mode != "enforced" or kev.source == "clinical_fallback":
        return AdaptiveRouteDecision(
            clinical_task=clinical_task,
            resolved_severity=severity,
            agent=_agent_for(severity),
            model_tier=ModelTier.STANDARD,
            kev_choice=kev.choice,
            confidence=kev.choice_confidence,
            margin=kev.margin,
            fact_coverage=coverage,
            reasons=["validated_clinical_route", f"kev_mode_{kev_mode}"],
        )

    score_band = _score_band(kev.severity_score)
    choice_disagrees = kev.choice in {
        SeverityChoice.ROUTINE,
        SeverityChoice.URGENT,
        SeverityChoice.EMERGENCY,
    } and kev.choice.value != severity
    score_disagrees = score_band is not None and score_band != severity
    boundary = kev.choice_confidence < min_confidence or kev.margin < min_margin
    unknown = kev.choice == SeverityChoice.UNKNOWN
    scope_conflict = kev.choice == SeverityChoice.OUT_OF_SCOPE and not non_clinical_task

    if unknown or boundary or choice_disagrees or score_disagrees or scope_conflict:
        reasons = ["kev_requires_uncertainty_path"]
        if unknown:
            reasons.append("kev_unknown")
        if boundary:
            reasons.append("kev_low_confidence_or_margin")
        if choice_disagrees:
            reasons.append("kev_choice_disagrees_with_clinical_result")
        if score_disagrees:
            reasons.append("kev_score_disagrees_with_clinical_result")
        if scope_conflict:
            reasons.append("kev_scope_conflicts_with_clinical_task")
        return AdaptiveRouteDecision(
            clinical_task=clinical_task,
            resolved_severity=severity,
            agent=SeverityAgent.UNCERTAIN,
            model_tier=ModelTier.DEEP,
            requires_clarification=coverage < low_coverage_threshold,
            requires_review=True,
            kev_choice=kev.choice,
            confidence=kev.choice_confidence,
            margin=kev.margin,
            fact_coverage=coverage,
            reasons=reasons,
        )

    # Agreement allows token/latency optimization. Severity is still inherited
    # from the validated clinical result; Kev controls only the execution tier.
    model_tier = ModelTier.FAST if severity == "ROUTINE" and coverage >= 0.85 else ModelTier.STANDARD
    return AdaptiveRouteDecision(
        clinical_task=clinical_task,
        resolved_severity=severity,
        agent=_agent_for(severity),
        model_tier=model_tier,
        kev_choice=kev.choice,
        confidence=kev.choice_confidence,
        margin=kev.margin,
        fact_coverage=coverage,
        reasons=["clinical_and_kev_agree", "kev_used_for_execution_tier_only"],
    )
