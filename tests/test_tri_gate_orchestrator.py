"""Unit tests for Tri-Gate orchestration and V14 safety-authority resolution."""

import time

from app.models.jev import DecisionState, JevDecision
from app.services.tri_gate_orchestrator import (
    TriGateResult,
    VerifierResult,
    run_tri_gate_pipeline,
)
from app.services.tri_gate_resolver import resolve_tri_gate


def test_fast_path_skips_jev():
    state = DecisionState(
        triage_floor="ROUTINE",
        reasoner_triage="ROUTINE",
        confidence=0.96,
        risk_features=(),
        hard_safety_flags=(),
    )
    res = run_tri_gate_pipeline(decision_state=state)
    assert res.selected_path == "FAST_PATH"
    assert res.jev_invoked is False
    assert res.gate3_jev is None

    final = resolve_tri_gate(res)
    assert final.final_triage == "ROUTINE"
    assert final.final_action == "SELF_CARE"
    assert final.allow_home_monitoring is True


def test_review_path_parallel_execution():
    state = DecisionState(
        triage_floor="ROUTINE",
        reasoner_triage="URGENT",
        confidence=0.88,
        risk_features=("uncontrolled_moderate_pain",),
    )

    def slow_verifier():
        time.sleep(0.08)
        return VerifierResult(
            approved=True,
            verifier_urgency="URGENT",
            confidence=0.92,
            latency_ms=80.0,
        )

    t0 = time.perf_counter()
    res = run_tri_gate_pipeline(decision_state=state, verifier_fn=slow_verifier)
    elapsed = time.perf_counter() - t0

    assert res.selected_path == "REVIEW_PATH"
    assert res.jev_invoked is True
    assert res.gate3_jev is not None
    assert res.gate3_jev.action == "SAME_DAY_EVAL"
    assert elapsed < 0.20

    final = resolve_tri_gate(res)
    assert final.final_triage == "URGENT"
    assert final.final_action == "SAME_DAY_EVAL"
    assert final.allow_home_monitoring is False


def test_critical_path_hard_emergency_remains_locked():
    state = DecisionState(
        triage_floor="EMERGENCY",
        reasoner_triage="EMERGENCY",
        hard_safety_flags=("no_home_monitoring",),
    )
    res = run_tri_gate_pipeline(decision_state=state)
    assert res.selected_path == "CRITICAL_PATH"
    assert res.jev_invoked is True
    assert res.gate3_jev is not None
    assert res.gate3_jev.action == "EMERGENCY_NOW"
    assert res.gate3_jev.authority == "emergency_lock"

    final = resolve_tri_gate(res)
    assert final.final_triage == "EMERGENCY"
    assert final.final_action == "EMERGENCY_NOW"
    assert final.allow_home_monitoring is False
    assert "enforce_zero_home_monitoring_for_emergency" in final.safety_invariants_enforced


def test_jev_critical_disagreement_requests_review_without_overriding_routine():
    state = DecisionState(
        triage_floor="ROUTINE",
        reasoner_triage="ROUTINE",
        confidence=0.92,
        fact_coverage=1.0,
        risk_features=("acute_functional_loss",),
    )
    res = run_tri_gate_pipeline(decision_state=state)
    assert res.selected_path == "REVIEW_PATH"
    assert res.gate3_jev is not None
    assert res.gate3_jev.action == "EMERGENCY_NOW"
    assert res.gate3_jev.authority == "advisory"
    assert res.gate3_jev.require_human_review is True

    final = resolve_tri_gate(res)
    assert final.final_triage == "ROUTINE"
    assert final.final_action == "AMBIGUOUS_CLARIFY"
    assert final.allow_home_monitoring is False
    assert final.require_human_review is True
    assert "routine_label_not_overridden_by_jev_alone" in final.safety_invariants_enforced


def test_low_fact_coverage_is_clarification_not_urgent_evidence():
    state = DecisionState(
        triage_floor="ROUTINE",
        reasoner_triage="ROUTINE",
        confidence=0.90,
        fact_coverage=0.1,
    )
    res = run_tri_gate_pipeline(decision_state=state)
    assert res.gate3_jev is not None
    assert res.gate3_jev.action == "AMBIGUOUS_CLARIFY"
    assert res.gate3_jev.triage_recommendation == "ROUTINE"

    final = resolve_tri_gate(res)
    assert final.final_triage == "ROUTINE"
    assert final.final_action == "AMBIGUOUS_CLARIFY"
    assert final.require_human_review is True


def test_explicit_jev_emergency_lock_is_honored_only_when_marked():
    state = DecisionState(
        triage_floor="ROUTINE",
        reasoner_triage="ROUTINE",
        confidence=0.91,
    )
    explicit_lock = JevDecision(
        action="EMERGENCY_NOW",
        confidence=0.99,
        allow_home_monitoring=False,
        require_human_review=False,
        triage_recommendation="EMERGENCY",
        authority="emergency_lock",
        policy_rules_triggered=("explicit_emergency_lock_test",),
    )
    tri = TriGateResult(
        selected_path="REVIEW_PATH",
        hard_safety_floor="ROUTINE",
        gate1_reasoner_triage="ROUTINE",
        gate1_confidence=0.91,
        gate2_verifier=VerifierResult(
            approved=True,
            verifier_urgency="ROUTINE",
            confidence=0.93,
        ),
        gate3_jev=explicit_lock,
        jev_invoked=True,
        parallel_latency_ms=0.0,
        total_orchestration_ms=0.0,
        decision_state=state,
    )

    final = resolve_tri_gate(tri)
    assert final.final_triage == "EMERGENCY"
    assert final.final_action == "EMERGENCY_NOW"
    assert final.governing_source == "jev_emergency_lock"
