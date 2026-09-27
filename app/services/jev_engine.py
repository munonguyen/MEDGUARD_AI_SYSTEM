"""Gate 3 (Jev) High-Performance Micro-Decision Engine.

Design Principles:
1. Micro-Scope Only:
   - Does NOT diagnose illnesses or reason from scratch.
   - Does NOT generate conversational prose or user-facing explanations.
   - Purely resolves boundary acuity, action safety, and clinical constraints.
2. Ultra-Fast Execution:
   - In-memory deterministic policy matrix + feature constraints.
   - Execution latency target: < 5 ms in pure local mode; < 150 ms if model-assisted.
3. Strict Safety Invariants:
   - If any perfusion, functional, or toxic threat is present -> action = EMERGENCY_NOW,
     allow_home_monitoring = False.
   - Never allows home monitoring for EMERGENCY or unresolved acute complaints.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any

from app.models.jev import DecisionState, JevAction, JevDecision, TriageAcuity

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
    """Execute Gate 3 (Jev) micro-decision over a compact DecisionState."""
    t0 = perf_counter()
    triggered_rules: list[str] = []

    # 1. Hard safety triggers & locked emergency floor
    has_critical_feature = any(f in _CRITICAL_RISK_FEATURES for f in state.risk_features)
    has_no_home_flag = "no_home_monitoring" in state.hard_safety_flags

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
            latency_ms=round(latency, 2),
            source="jev_engine",
        )

    # 2. Critical syndromic risk features
    if has_critical_feature:
        triggered_rules.append("critical_syndromic_risk_feature")
        latency = (perf_counter() - t0) * 1000.0
        return JevDecision(
            action="EMERGENCY_NOW",
            confidence=max(state.confidence, 0.98),
            allow_home_monitoring=False,
            require_human_review=False,
            triage_recommendation="EMERGENCY",
            policy_rules_triggered=tuple(triggered_rules),
            latency_ms=round(latency, 2),
            source="jev_engine",
        )

    # 3. Reasoner Emergency entailment
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
            latency_ms=round(latency, 2),
            source="jev_engine",
        )

    # 4. Urgent floor or Urgent Reasoner
    has_urgent_feature = any(f in _URGENT_RISK_FEATURES for f in state.risk_features)
    if state.reasoner_triage == "URGENT" or state.triage_floor == "URGENT" or has_urgent_feature:
        triggered_rules.append("urgent_evaluation_required")
        latency = (perf_counter() - t0) * 1000.0
        return JevDecision(
            action="SAME_DAY_EVAL",
            confidence=max(state.confidence, 0.92),
            allow_home_monitoring=False,
            require_human_review=False,
            triage_recommendation="URGENT",
            policy_rules_triggered=tuple(triggered_rules),
            latency_ms=round(latency, 2),
            source="jev_engine",
        )

    # 5. Epistemic check on low coverage (Invariant V11-A Compliant)
    has_any_risk_indicator = bool(
        has_critical_feature
        or has_urgent_feature
        or state.risk_features
        or state.hard_safety_flags
    )

    if state.fact_coverage < 0.35 and state.reasoner_triage == "ROUTINE":
        # INVARIANT V11-A: If Gate 0 & Gate 1 agreed on ROUTINE and there are ZERO risk features,
        # Jev MUST NOT escalate to URGENT. Preserve ROUTINE self-care and advise clarification.
        if state.triage_floor == "ROUTINE" and not has_any_risk_indicator:
            triggered_rules.append("epistemic_benign_consensus_preserved")
            latency = (perf_counter() - t0) * 1000.0
            return JevDecision(
                action="SELF_CARE",
                confidence=min(max(state.confidence, 0.90), 0.95),
                allow_home_monitoring=not has_no_home_flag,
                require_human_review=False,
                triage_recommendation="ROUTINE",
                policy_rules_triggered=tuple(triggered_rules),
                latency_ms=round(latency, 2),
                source="jev_engine",
            )

        triggered_rules.append("epistemic_low_coverage_guard")
        latency = (perf_counter() - t0) * 1000.0
        return JevDecision(
            action="AMBIGUOUS_CLARIFY",
            confidence=0.60,
            allow_home_monitoring=False,
            require_human_review=False,
            triage_recommendation="URGENT",
            policy_rules_triggered=tuple(triggered_rules),
            latency_ms=round(latency, 2),
            source="jev_engine",
        )

    # 6. Benign Routine Self-Care
    triggered_rules.append("benign_routine_self_care")
    latency = (perf_counter() - t0) * 1000.0
    return JevDecision(
        action="SELF_CARE",
        confidence=min(max(state.confidence, 0.95), 0.99),
        allow_home_monitoring=not has_no_home_flag,
        require_human_review=False,
        triage_recommendation="ROUTINE",
        policy_rules_triggered=tuple(triggered_rules),
        latency_ms=round(latency, 2),
        source="jev_engine",
    )
