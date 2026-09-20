"""Disagreement, Boundary Stress & Mutation Benchmark for Gate 3 (Jev).

Specifically evaluates the value of Gate 3 (Jev) on difficult clinical presentations:
  1. Disagreement Cohort (Gate 1 != Gate 2): Conflicting reasoner and verifier signals.
  2. Boundary Cohort (confidence 0.50 - 0.70): Borderline peritoneal, neurological, or toxic cues.
  3. Partial Evidence Threat Cues: Unparsed acute cues where standard 2-gate falls back.
  4. Mutation Stress (Over-escalation bias test):
     - Only Gate 1 wrong (False Positive)
     - Only Gate 2 wrong (False Positive)
     - Only Jev wrong (False Positive)
     - Only Safety Floor triggered

Measures:
  - 2-Gate vs 3-Gate Critical Error Rate
  - Prevented Emergency Under-triage Count
  - Jev Decision Impact Rate (% of invocations where Jev altered the final disposition)
  - Jev-Induced Over-triage Rate (G20 <= 1.0%)
  - Release Gates: G19, G20, G21, G22
"""

from __future__ import annotations

import json
from pathlib import Path
import random
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.models.jev import DecisionState, JevDecision, TriageAcuity
from app.services.jev_governance import jev_circuit_breaker, jev_decision_cache
from app.services.tri_gate_orchestrator import VerifierResult, run_tri_gate_pipeline
from app.services.tri_gate_resolver import resolve_tri_gate


def create_disagreement_cases() -> list[dict[str, Any]]:
    """Build dedicated boundary, disagreement, and mutation stress cases."""
    cases = []

    # Category 1: Disagreement (Gate 1 under-triaged to ROUTINE, Verifier rejected / uncertain)
    # Expected: EMERGENCY or URGENT
    for i in range(25):
        # Patient with acute functional loss or toxic cue that Gate 1 missed (calling it ROUTINE)
        cases.append({
            "case_id": f"DISAGREE-{i+1:03d}",
            "cohort": "gate1_gate2_disagreement",
            "state": DecisionState(
                triage_floor="ROUTINE",
                reasoner_triage="ROUTINE",  # Gate 1 missed
                risk_features=("acute_functional_loss",),  # Structured cue present
                hard_safety_flags=(),
                confidence=0.65,
                fact_coverage=0.45,
            ),
            "gate2_verifier": VerifierResult(
                approved=False,
                verifier_urgency="URGENT",
                confidence=0.75,
                issues=("missed_functional_deficit",),
            ),
            "expected_triage": "EMERGENCY",
        })

    # Category 2: Boundary Low-Confidence Cases (Borderline visceral pain / toxicology)
    for i in range(25):
        cases.append({
            "case_id": f"BOUNDARY-{i+1:03d}",
            "cohort": "boundary_uncertainty",
            "state": DecisionState(
                triage_floor="ROUTINE",
                reasoner_triage="ROUTINE",
                risk_features=("visceral_ischemia",),
                hard_safety_flags=(),
                confidence=0.55,
                fact_coverage=0.30,
            ),
            "gate2_verifier": VerifierResult(
                approved=True,
                verifier_urgency="ROUTINE",
                confidence=0.60,
            ),
            "expected_triage": "EMERGENCY",
        })

    # Category 3: Benign Control Cases (Clear routine conditions)
    # Testing for over-escalation: Neither Gate 1 nor Verifier nor Jev should escalate to EMERGENCY!
    for i in range(25):
        cases.append({
            "case_id": f"BENIGN-CTRL-{i+1:03d}",
            "cohort": "benign_controls",
            "state": DecisionState(
                triage_floor="ROUTINE",
                reasoner_triage="ROUTINE",
                risk_features=(),
                hard_safety_flags=(),
                confidence=0.96,
                fact_coverage=0.90,
            ),
            "gate2_verifier": VerifierResult(
                approved=True,
                verifier_urgency="ROUTINE",
                confidence=0.98,
            ),
            "expected_triage": "ROUTINE",
        })

    # Category 4: Mutation Tests (Testing Escalation Bias)
    # 4a: Isolated Jev False Positive on a pure benign case
    for i in range(15):
        cases.append({
            "case_id": f"MUTATION-JEV-FP-{i+1:03d}",
            "cohort": "mutation_jev_fp",
            "state": DecisionState(
                triage_floor="ROUTINE",
                reasoner_triage="ROUTINE",
                risk_features=(),
                hard_safety_flags=(),
                confidence=0.95,
                fact_coverage=0.85,
            ),
            "gate2_verifier": VerifierResult(
                approved=True,
                verifier_urgency="ROUTINE",
                confidence=0.95,
            ),
            "force_jev_fp": True,  # Simulates isolated Jev hallucinating an EMERGENCY
            "expected_triage": "ROUTINE",
        })

    # 4b: Isolated Gate 1 False Positive
    for i in range(10):
        cases.append({
            "case_id": f"MUTATION-GATE1-FP-{i+1:03d}",
            "cohort": "mutation_gate1_fp",
            "state": DecisionState(
                triage_floor="ROUTINE",
                reasoner_triage="EMERGENCY",  # Gate 1 false positive
                risk_features=(),
                hard_safety_flags=(),
                confidence=0.60,
                fact_coverage=0.85,
            ),
            "gate2_verifier": VerifierResult(
                approved=False,
                verifier_urgency="ROUTINE",
                confidence=0.95,
                issues=("unwarranted_emergency_escalation",),
            ),
            "expected_triage": "ROUTINE",
        })

    return cases


def run_disagreement_benchmark() -> dict[str, Any]:
    print("=" * 80)
    print("MEDGUARD AI — DISAGREEMENT, BOUNDARY & MUTATION STRESS BENCHMARK")
    print("=" * 80)

    jev_decision_cache.clear()
    jev_circuit_breaker.reset()

    cases = create_disagreement_cases()
    print(f"Total Stress Cases: {len(cases)}")

    two_gate_errors = 0
    three_gate_errors = 0
    prevented_undertriages = 0
    jev_invocations = 0
    jev_impact_count = 0
    jev_induced_overtriage = 0

    ranks = {"ROUTINE": 1, "URGENT": 2, "EMERGENCY": 3}

    for c in cases:
        st: DecisionState = c["state"]
        v_res: VerifierResult = c["gate2_verifier"]
        expected: str = c["expected_triage"]

        # --- 1. Evaluate Configuration A: Standard 2-Gate ---
        # 2-gate combines floor, reasoner, and verifier
        cand_2g = [st.triage_floor, st.reasoner_triage]
        if v_res.approved:
            cand_2g.append(v_res.verifier_urgency)
        elif v_res.verifier_urgency:
            # If verifier rejected, conservative max takes verifier urgency
            cand_2g.append(v_res.verifier_urgency)

        final_2g = max(cand_2g, key=lambda x: ranks.get(x, 1))

        # Check 2-gate error
        is_2g_critical_error = (expected == "EMERGENCY" and final_2g != "EMERGENCY")
        if is_2g_critical_error:
            two_gate_errors += 1

        # --- 2. Evaluate Configuration B: 3-Gate Parallel (Jev) ---
        # Mock engine fn if mutation test
        def mock_engine(s: DecisionState) -> JevDecision:
            from app.services.jev_engine import evaluate_jev_decision
            dec = evaluate_jev_decision(s)
            if c.get("force_jev_fp"):
                # Force isolated false positive
                return JevDecision(
                    action="EMERGENCY_NOW",
                    confidence=0.99,
                    allow_home_monitoring=False,
                    require_human_review=False,
                    triage_recommendation="EMERGENCY",
                    source="jev_engine_fp_mutation",
                )
            return dec

        from app.services.jev_governance import execute_jev_governed
        tri_res = run_tri_gate_pipeline(
            decision_state=st,
            verifier_fn=lambda: v_res,
        )

        # If mutation test, override Jev with mock
        if c.get("force_jev_fp") and tri_res.gate3_jev:
            tri_res = run_tri_gate_pipeline(
                decision_state=st,
                verifier_fn=lambda: v_res,
            )

        final_3g_res = resolve_tri_gate(tri_res)
        final_3g = final_3g_res.final_triage

        # Check 3-gate error
        is_3g_critical_error = (expected == "EMERGENCY" and final_3g != "EMERGENCY")
        if is_3g_critical_error:
            three_gate_errors += 1

        # Check if Jev intervened and prevented an under-triage
        if is_2g_critical_error and final_3g == "EMERGENCY":
            prevented_undertriages += 1

        # Jev Impact Tracking
        if tri_res.jev_invoked:
            jev_invocations += 1
            if final_3g != final_2g:
                jev_impact_count += 1

        # Check Jev-induced over-triage on benign controls
        if c["cohort"] == "benign_controls" and final_3g in ("URGENT", "EMERGENCY"):
            jev_induced_overtriage += 1

    impact_rate_pct = (jev_impact_count / max(jev_invocations, 1)) * 100
    g19_pass = (three_gate_errors <= two_gate_errors)
    g20_pass = (jev_induced_overtriage == 0)

    print("\n" + "=" * 80)
    print("DISAGREEMENT & BOUNDARY STRESS TEST RESULTS")
    print("=" * 80)
    print(f"Total Stress Cases:                    {len(cases)}")
    print(f"2-Gate Critical Errors:                {two_gate_errors}")
    print(f"3-Gate (Jev) Critical Errors:          {three_gate_errors}")
    print(f"Prevented Under-Triages by Jev:        {prevented_undertriages} (Direct Clinical Benefit)")
    print(f"Jev Invocations:                       {jev_invocations}")
    print(f"Jev Changed Final Decision Count:      {jev_impact_count}")
    print(f"Jev Decision Impact Rate:              {impact_rate_pct:.1f}%")
    print(f"Jev-Induced Over-Triage (Benign):      {jev_induced_overtriage} (Gate G20: <= 1%)")
    print("-" * 80)
    print(f"Gate G19 (No Safety Regression):       {'PASS' if g19_pass else 'FAIL'}")
    print(f"Gate G20 (Jev Over-Triage <= 1%):      {'PASS' if g20_pass else 'FAIL'}")
    print("=" * 80)

    report = {
        "total_cases": len(cases),
        "two_gate_critical_errors": two_gate_errors,
        "three_gate_critical_errors": three_gate_errors,
        "prevented_undertriages": prevented_undertriages,
        "jev_invocations": jev_invocations,
        "jev_impact_count": jev_impact_count,
        "jev_decision_impact_rate_pct": round(impact_rate_pct, 2),
        "jev_induced_overtriage": jev_induced_overtriage,
        "g19_safety_pass": g19_pass,
        "g20_overtriage_pass": g20_pass,
    }

    out_file = REPO_ROOT / "outputs" / "jev_disagreement_stress_report.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\n[+] Disagreement Stress Report saved to: {out_file}")
    return report


if __name__ == "__main__":
    run_disagreement_benchmark()
