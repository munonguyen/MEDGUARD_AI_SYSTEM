"""Unit Tests for Tri-Gate Orchestrator and Deterministic Final Safety Resolver."""

import time
import pytest
from app.models.jev import DecisionState, JevDecision
from app.services.tri_gate_orchestrator import (
    TriGateResult,
    VerifierResult,
    run_tri_gate_pipeline,
)
from app.services.tri_gate_resolver import FinalResolution, resolve_tri_gate


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
    # Verify execution was concurrent: total time should be close to slow_verifier (~80ms), not 80ms + Jev
    assert elapsed < 0.20

    final = resolve_tri_gate(res)
    assert final.final_triage == "URGENT"
    assert final.final_action == "SAME_DAY_EVAL"
    assert final.allow_home_monitoring is False


def test_critical_path_hard_emergency():
    state = DecisionState(
        triage_floor="EMERGENCY",
        reasoner_triage="EMERGENCY",
        hard_safety_flags=("no_home_monitoring",),
    )
    res = run_tri_gate_pipeline(decision_state=state)
    assert res.selected_path == "CRITICAL_PATH"
    assert res.jev_invoked is True
    assert res.gate3_jev.action == "EMERGENCY_NOW"

    final = resolve_tri_gate(res)
    assert final.final_triage == "EMERGENCY"
    assert final.final_action == "EMERGENCY_NOW"
    assert final.allow_home_monitoring is False
    assert "enforce_zero_home_monitoring_for_emergency" in final.safety_invariants_enforced


def test_jev_veto_blocks_routine_home_care():
    state = DecisionState(
        triage_floor="ROUTINE",
        reasoner_triage="ROUTINE",
        risk_features=("acute_functional_loss",),  # Jev detects this!
    )
    res = run_tri_gate_pipeline(decision_state=state)
    assert res.selected_path == "REVIEW_PATH"
    assert res.gate3_jev.action == "EMERGENCY_NOW"

    final = resolve_tri_gate(res)
    assert final.final_triage == "EMERGENCY"
    assert final.final_action == "EMERGENCY_NOW"
    assert final.allow_home_monitoring is False
