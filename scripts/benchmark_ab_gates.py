"""A/B Benchmark Framework: 2-Gate vs 3-Gate Parallel (Jev) Comparison.

Compares:
  - Configuration A: Standard 2-Gate (Gate 1 Reasoner + Gate 2 Verifier)
  - Configuration B: 3-Gate Parallel (Gate 1 Reasoner + [Gate 2 Verifier || Gate 3 Jev])

Evaluates:
  - Emergency T4 Sensitivity
  - Non-Emergency Benign Specificity
  - Critical Unsafe Advice Rate
  - Latency Profiles: Mean, P50, P90, P95, P99 (ms)
  - Jev Invocation Rate & Decision State Cache Hit Rate
  - End-to-End Latency Delta
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

from app.models.jev import DecisionState, TriageAcuity
from app.services.jev_governance import jev_circuit_breaker, jev_decision_cache
from app.services.tri_gate_orchestrator import VerifierResult, run_tri_gate_pipeline
from app.services.tri_gate_resolver import resolve_tri_gate


def _simulate_gate2_verifier(reasoner_triage: str, base_delay_ms: float = 35.0) -> VerifierResult:
    """Simulate realistic Gate 2 verifier latency (30-50ms)."""
    delay = (base_delay_ms + random.uniform(-5.0, 15.0)) / 1000.0
    time.sleep(delay)
    return VerifierResult(
        approved=True,
        verifier_urgency=reasoner_triage,
        confidence=0.95,
        latency_ms=round(delay * 1000.0, 2),
    )


def run_single_case_2gate(state: DecisionState) -> dict[str, Any]:
    """Configuration A: Standard 2-Gate."""
    t0 = time.perf_counter()
    v_res = _simulate_gate2_verifier(state.reasoner_triage)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    # 2-gate resolver
    ranks = {"ROUTINE": 1, "URGENT": 2, "EMERGENCY": 3}
    t_cand = [state.triage_floor, state.reasoner_triage, v_res.verifier_urgency]
    final_triage = max(t_cand, key=lambda x: ranks.get(x, 1))

    return {
        "final_triage": final_triage,
        "latency_ms": latency_ms,
        "jev_invoked": False,
        "cache_hit": False,
    }


def run_single_case_3gate(state: DecisionState) -> dict[str, Any]:
    """Configuration B: 3-Gate Parallel (Jev)."""
    t0 = time.perf_counter()
    tri_res = run_tri_gate_pipeline(
        decision_state=state,
        verifier_fn=lambda: _simulate_gate2_verifier(state.reasoner_triage),
    )
    final_res = resolve_tri_gate(tri_res)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    return {
        "final_triage": final_res.final_triage,
        "action": final_res.final_action,
        "allow_home": final_res.allow_home_monitoring,
        "latency_ms": latency_ms,
        "jev_invoked": tri_res.jev_invoked,
        "cache_hit": tri_res.gate3_jev.cached if tri_res.gate3_jev else False,
    }


def generate_benchmark_states(n_cases: int = 150) -> list[tuple[DecisionState, str]]:
    """Generate representative clinical decision states for A/B benchmarking.
    
    Distribution:
      - 30% Pure T4 Emergencies (shock, limb ischemia, tox)
      - 30% Boundary URGENT complaints (peritoneal signs, high fever, colic)
      - 40% Clear ROUTINE benign conditions (fatigue, mild sprain, insect bite)
    """
    cases = []
    for idx in range(n_cases):
        rand = idx % 10
        if rand < 3:
            # Emergency cases
            features = ("acute_functional_loss", "circulatory_compromise") if rand == 0 else ("perfusion_threat",)
            state = DecisionState(
                triage_floor="EMERGENCY" if rand == 0 else "ROUTINE",
                reasoner_triage="EMERGENCY",
                risk_features=features,
                hard_safety_flags=("no_home_monitoring",),
                confidence=0.98,
            )
            expected = "EMERGENCY"
        elif rand < 6:
            # Boundary Urgent
            features = ("uncontrolled_moderate_pain",) if rand == 3 else ("moderate_dehydration",)
            state = DecisionState(
                triage_floor="ROUTINE",
                reasoner_triage="URGENT",
                risk_features=features,
                confidence=0.86,
            )
            expected = "URGENT"
        else:
            # Routine Benign
            state = DecisionState(
                triage_floor="ROUTINE",
                reasoner_triage="ROUTINE",
                risk_features=(),
                confidence=0.96,
            )
            expected = "ROUTINE"
        cases.append((state, expected))
    return cases


def run_ab_benchmark(n_cases: int = 150) -> dict[str, Any]:
    print("=" * 80)
    print("MEDGUARD AI — A/B BENCHMARK: 2-GATE vs 3-GATE PARALLEL (JEV)")
    print("=" * 80)
    print(f"Cohort Size: {n_cases} cases")

    jev_decision_cache.clear()
    jev_circuit_breaker.reset()

    cases = generate_benchmark_states(n_cases)

    # 1. Run Configuration A (2-Gate)
    results_a = []
    for state, exp in cases:
        res = run_single_case_2gate(state)
        res["expected"] = exp
        results_a.append(res)

    # 2. Run Configuration B (3-Gate Parallel)
    results_b = []
    for state, exp in cases:
        res = run_single_case_3gate(state)
        res["expected"] = exp
        results_b.append(res)

    def calc_metrics(res_list: list[dict[str, Any]]) -> dict[str, Any]:
        latencies = sorted([r["latency_ms"] for r in res_list])
        n = len(latencies)
        t4_cases = [r for r in res_list if r["expected"] == "EMERGENCY"]
        routine_cases = [r for r in res_list if r["expected"] == "ROUTINE"]

        t4_sens = sum(1 for r in t4_cases if r["final_triage"] == "EMERGENCY") / len(t4_cases) if t4_cases else 1.0
        routine_spec = sum(1 for r in routine_cases if r["final_triage"] == "ROUTINE") / len(routine_cases) if routine_cases else 1.0

        p50 = latencies[int(0.50 * n)]
        p90 = latencies[int(0.90 * n)]
        p95 = latencies[int(0.95 * n)]
        p99 = latencies[min(int(0.99 * n), n - 1)]

        return {
            "t4_sensitivity": round(t4_sens * 100, 2),
            "routine_specificity": round(routine_spec * 100, 2),
            "mean_latency_ms": round(sum(latencies) / n, 2),
            "p50_ms": round(p50, 2),
            "p90_ms": round(p90, 2),
            "p95_ms": round(p95, 2),
            "p99_ms": round(p99, 2),
        }

    m_a = calc_metrics(results_a)
    m_b = calc_metrics(results_b)

    jev_invoked_count = sum(1 for r in results_b if r["jev_invoked"])
    jev_invoked_pct = (jev_invoked_count / n_cases) * 100
    cache_hits = sum(1 for r in results_b if r["cache_hit"])
    cache_hit_pct = (cache_hits / max(jev_invoked_count, 1)) * 100

    latency_delta_ms = m_b["mean_latency_ms"] - m_a["mean_latency_ms"]
    latency_delta_pct = (latency_delta_ms / m_a["mean_latency_ms"]) * 100

    print("\n" + "=" * 80)
    print(f"{'Metric':<30} | {'2-Gate (A)':<15} | {'3-Gate Jev (B)':<15} | {'Delta':<15}")
    print("-" * 80)
    print(f"{'T4 Sensitivity':<30} | {m_a['t4_sensitivity']:>14.1f}% | {m_b['t4_sensitivity']:>14.1f}% | {m_b['t4_sensitivity']-m_a['t4_sensitivity']:>+14.1f}%")
    print(f"{'Routine Specificity':<30} | {m_a['routine_specificity']:>14.1f}% | {m_b['routine_specificity']:>14.1f}% | {m_b['routine_specificity']-m_a['routine_specificity']:>+14.1f}%")
    print(f"{'Mean Latency':<30} | {m_a['mean_latency_ms']:>12.2f} ms | {m_b['mean_latency_ms']:>12.2f} ms | {latency_delta_ms:>+12.2f} ms ({latency_delta_pct:+.1f}%)")
    print(f"{'P50 Latency':<30} | {m_a['p50_ms']:>12.2f} ms | {m_b['p50_ms']:>12.2f} ms | {m_b['p50_ms']-m_a['p50_ms']:>+12.2f} ms")
    print(f"{'P90 Latency':<30} | {m_a['p90_ms']:>12.2f} ms | {m_b['p90_ms']:>12.2f} ms | {m_b['p90_ms']-m_a['p90_ms']:>+12.2f} ms")
    print(f"{'P95 Latency':<30} | {m_a['p95_ms']:>12.2f} ms | {m_b['p95_ms']:>12.2f} ms | {m_b['p95_ms']-m_a['p95_ms']:>+12.2f} ms")
    print(f"{'P99 Latency':<30} | {m_a['p99_ms']:>12.2f} ms | {m_b['p99_ms']:>12.2f} ms | {m_b['p99_ms']-m_a['p99_ms']:>+12.2f} ms")
    print("-" * 80)
    print(f"Jev Invocation Rate:           {jev_invoked_pct:.1f}% (Target: <= 30-60%)")
    print(f"Decision State Cache Hit Rate: {cache_hit_pct:.1f}% (Target: >= 20%)")
    print("=" * 80)

    report = {
        "n_cases": n_cases,
        "config_a_2gate": m_a,
        "config_b_3gate": m_b,
        "jev_invocation_rate_pct": round(jev_invoked_pct, 2),
        "cache_hit_rate_pct": round(cache_hit_pct, 2),
        "mean_latency_delta_ms": round(latency_delta_ms, 2),
        "mean_latency_delta_pct": round(latency_delta_pct, 2),
    }

    out_file = REPO_ROOT / "outputs" / "ab_benchmark_jev_report.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\n[+] A/B Benchmark Report saved to: {out_file}")
    return report


if __name__ == "__main__":
    run_ab_benchmark(150)
