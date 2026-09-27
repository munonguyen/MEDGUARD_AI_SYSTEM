"""Unit Tests for Gate 3 (Jev) Micro-Decision Engine."""

import pytest
from app.models.jev import DecisionState, JevDecision
from app.services.jev_engine import evaluate_jev_decision


def test_jev_state_hash_deterministic():
    s1 = DecisionState(
        triage_floor="ROUTINE",
        reasoner_triage="ROUTINE",
        risk_features=("acute_functional_loss",),
        hard_safety_flags=("no_home_monitoring",),
    )
    s2 = DecisionState(
        triage_floor="ROUTINE",
        reasoner_triage="ROUTINE",
        risk_features=("acute_functional_loss",),
        hard_safety_flags=("no_home_monitoring",),
    )
    assert s1.state_hash() == s2.state_hash()


def test_jev_hard_emergency_floor():
    state = DecisionState(
        triage_floor="EMERGENCY",
        reasoner_triage="ROUTINE",
    )
    decision = evaluate_jev_decision(state)
    assert decision.action == "EMERGENCY_NOW"
    assert decision.triage_recommendation == "EMERGENCY"
    assert decision.allow_home_monitoring is False
    assert decision.confidence >= 0.98


def test_jev_critical_risk_features():
    state = DecisionState(
        triage_floor="ROUTINE",
        reasoner_triage="ROUTINE",
        risk_features=("perfusion_threat", "circulatory_compromise"),
    )
    decision = evaluate_jev_decision(state)
    assert decision.action == "EMERGENCY_NOW"
    assert decision.triage_recommendation == "EMERGENCY"
    assert decision.allow_home_monitoring is False


def test_jev_reasoner_emergency():
    state = DecisionState(
        triage_floor="ROUTINE",
        reasoner_triage="EMERGENCY",
    )
    decision = evaluate_jev_decision(state)
    assert decision.action == "EMERGENCY_NOW"
    assert decision.triage_recommendation == "EMERGENCY"
    assert decision.allow_home_monitoring is False


def test_jev_urgent_boundary():
    state = DecisionState(
        triage_floor="ROUTINE",
        reasoner_triage="URGENT",
        risk_features=("moderate_dehydration",),
    )
    decision = evaluate_jev_decision(state)
    assert decision.action == "SAME_DAY_EVAL"
    assert decision.triage_recommendation == "URGENT"
    assert decision.allow_home_monitoring is False


def test_jev_benign_routine():
    state = DecisionState(
        triage_floor="ROUTINE",
        reasoner_triage="ROUTINE",
        risk_features=(),
        hard_safety_flags=(),
        confidence=0.98,
    )
    decision = evaluate_jev_decision(state)
    assert decision.action == "SELF_CARE"
    assert decision.triage_recommendation == "ROUTINE"
    assert decision.allow_home_monitoring is True


def test_jev_epistemic_low_coverage_invariant_v11_a():
    """Verify Invariant V11-A: Low coverage on benign consensus MUST NOT escalate to URGENT."""
    state = DecisionState(
        triage_floor="ROUTINE",
        reasoner_triage="ROUTINE",
        fact_coverage=0.20,
        risk_features=(),
        hard_safety_flags=(),
    )
    decision = evaluate_jev_decision(state)
    assert decision.action == "SELF_CARE"
    assert decision.triage_recommendation == "ROUTINE"
    assert decision.allow_home_monitoring is True
    assert "epistemic_benign_consensus_preserved" in decision.policy_rules_triggered


def test_jev_epistemic_low_coverage_with_risk_feature_escalates():
    """Verify that when real risk features ARE present with low coverage, Jev properly escalates."""
    state = DecisionState(
        triage_floor="ROUTINE",
        reasoner_triage="ROUTINE",
        fact_coverage=0.20,
        risk_features=("uncontrolled_moderate_pain",),
    )
    decision = evaluate_jev_decision(state)
    assert decision.triage_recommendation == "URGENT"
    assert decision.allow_home_monitoring is False
