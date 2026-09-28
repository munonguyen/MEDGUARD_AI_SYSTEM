"""Gate 3 (Jev) compact clinical-safety knowledge engine.

V14 authority model:
1. Jev does not diagnose, write patient prose, or own routine/urgent disposition.
2. It evaluates a PHI-free DecisionState and returns advisory clinical-safety
   signals to the resolver and selected response agent.
3. Only an already-established deterministic emergency floor is returned with
   ``authority='emergency_lock'``. All other Jev recommendations are advisory,
   even when Jev believes the case could be more acute.
4. Low fact coverage requests clarification instead of being treated as proof of
   urgent disease.
"""

from __future__ import annotations

from time import perf_counter

from app.models.jev import DecisionState, JevDecision

_CRITICAL_RISK_FEATURES: frozenset[str] = frozenset({
    "acute_functional_loss",
    "circulatory_compromise",
    "perfusion_threat",
    "toxic_exposure",
    "visceral_ischemia",
    "aerodigestive_rupture",
    "necrotizing_infection",
    "airway_compromise",
    "critical_vital_instability",
    "severe_toxic_ingestion",
    "intracranial_hemorrhage_risk",
})

_URGENT_RISK_FEATURES: frozenset[str] = frozenset({
    "moderate_dehydration",
    "localized_infection_spreading",
    "uncontrolled_moderate_pain",
    "persistent_vomiting",
    "concussion_signs_mild",
    "potential_fracture",
})


def evaluate_jev_decision(state: DecisionState) -> JevDecision:
    """Evaluate Jev safety knowledge without granting it normal disposition authority."""
    t0 = perf_counter()
    triggered_rules: list[str] = []

    # 1. Jev may carry forward an emergency lock that already exists in Gate 0.
    # It does not create this authority from its own probabilistic inference.
    if state.triage_floor == "EMERGENCY" or "emergency_floor_locked" in state.hard_safety_flags:
        triggered_rules.append("hard_emergency_floor_locked")
        latency = (perf_counter() - t0) * 1000.0
        return JevDecision(
            action="EMERGENCY_NOW",
            confidence=0.99,
            allow_home_monitoring=False,
            require_human_review=False,
            triage_recommendation="EMERGENCY",
            policy_rules_triggered=tuple(triggered_rules),
            clinical_insights=("deterministic_emergency_floor_present",),
            authority="emergency_lock",
            latency_ms=round(latency, 2),
            source="jev_engine",
        )

    has_critical_feature = any(feature in _CRITICAL_RISK_FEATURES for feature in state.risk_features)
    has_no_home_flag = "no_home_monitoring" in state.hard_safety_flags

    # 2. Critical feature detected by Jev: strong advisory challenge, not a new
    # emergency lock. Resolver/agent must surface it for clarification/review.
    if has_critical_feature:
        critical_features = tuple(
            feature for feature in state.risk_features if feature in _CRITICAL_RISK_FEATURES
        )
        triggered_rules.append("critical_syndromic_risk_feature")
        latency = (perf_counter() - t0) * 1000.0
        return JevDecision(
            action="EMERGENCY_NOW",
            confidence=max(state.confidence, 0.98),
            allow_home_monitoring=False,
            require_human_review=True,
            triage_recommendation="EMERGENCY",
            policy_rules_triggered=tuple(triggered_rules),
            clinical_insights=critical_features,
            advisory_red_flags=critical_features,
            suggested_clarifications=("confirm_critical_risk_feature_context",),
            latency_ms=round(latency, 2),
            source="jev_engine",
        )

    # 3. Reasoner emergency is echoed by Jev but remains reasoner-owned.
    if state.reasoner_triage == "EMERGENCY":
        triggered_rules.append("reasoner_emergency_entailed")
        latency = (perf_counter() - t0) * 1000.0
        return JevDecision(
            action="EMERGENCY_NOW",
            confidence=max(state.confidence, 0.95),
            allow_home_monitoring=False,
            require_human_review=False,
            triage_recommendation="EMERGENCY",
            policy_rules_triggered=tuple(triggered_rules),
            clinical_insights=("reasoner_emergency_entailed",),
            latency_ms=round(latency, 2),
            source="jev_engine",
        )

    # 4. Urgent reasoner/floor or urgent feature. Jev contributes evidence but
    # cannot upgrade a ROUTINE result by itself in the final resolver.
    urgent_features = tuple(feature for feature in state.risk_features if feature in _URGENT_RISK_FEATURES)
    if state.reasoner_triage == "URGENT" or state.triage_floor == "URGENT" or urgent_features:
        triggered_rules.append("urgent_evaluation_signal")
        latency = (perf_counter() - t0) * 1000.0
        return JevDecision(
            action="SAME_DAY_EVAL",
            confidence=max(state.confidence, 0.92),
            allow_home_monitoring=False,
            require_human_review=bool(
                urgent_features
                and state.reasoner_triage == "ROUTINE"
                and state.triage_floor == "ROUTINE"
            ),
            triage_recommendation="URGENT",
            policy_rules_triggered=tuple(triggered_rules),
            clinical_insights=urgent_features or ("urgent_disposition_already_present",),
            advisory_red_flags=urgent_features,
            suggested_clarifications=("confirm_urgent_risk_feature_context",) if urgent_features else (),
            latency_ms=round(latency, 2),
            source="jev_engine",
        )

    # 5. Low coverage is epistemic uncertainty, not evidence of disease severity.
    if state.fact_coverage < 0.35 and state.reasoner_triage == "ROUTINE":
        triggered_rules.append("epistemic_low_coverage_guard")
        latency = (perf_counter() - t0) * 1000.0
        return JevDecision(
            action="AMBIGUOUS_CLARIFY",
            confidence=0.60,
            allow_home_monitoring=False,
            require_human_review=True,
            triage_recommendation="ROUTINE",
            policy_rules_triggered=tuple(triggered_rules),
            clinical_insights=("insufficient_fact_coverage",),
            suggested_clarifications=("ask_one_high_information_clinical_question",),
            latency_ms=round(latency, 2),
            source="jev_engine",
        )

    # 6. Benign routine self-care advisory.
    triggered_rules.append("benign_routine_self_care")
    latency = (perf_counter() - t0) * 1000.0
    return JevDecision(
        action="SELF_CARE",
        confidence=min(max(state.confidence, 0.95), 0.99),
        allow_home_monitoring=not has_no_home_flag,
        require_human_review=False,
        triage_recommendation="ROUTINE",
        policy_rules_triggered=tuple(triggered_rules),
        clinical_insights=("no_jev_escalation_signal",),
        latency_ms=round(latency, 2),
        source="jev_engine",
    )
