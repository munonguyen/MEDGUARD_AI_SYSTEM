"""Cold-Cache, Warm-Cache & Mixed-Cache Stress Benchmark for Gate 3 (Jev).

Evaluates latency distributions under 3 distinct caching conditions:
  1. Cold Cache: Cache cleared before every single request (100% cache miss).
  2. Warm Cache: High repeat state distribution (typical steady-state traffic).
  3. Mixed Cache: 70% unique novel states, 30% repeated states (realistic production mix).

Measures: P50, P90, P95, P99 latency (ms) and validates against G23 (Cold-cache latency delta <= 10%).
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

from app.models.jev import DecisionState, JevDecision
from app.services.jev_governance import (
    execute_jev_governed,
    jev_circuit_breaker,
    jev_decision_cache,
)
from app.services.tri_gate_orchestrator import run_tri_gate_pipeline
from app.services.tri_gate_resolver import resolve_tri_gate


def _simulate_gate2_verifier(reasoner_triage: str) -> Any:
    delay = (35.0 + random.uniform(-5.0, 10.0)) / 1000.0
    time.sleep(delay)
    from app.services.tri_gate_orchestrator import VerifierResult
    return VerifierResult(
        approved=True,
        verifier_urgency=reasoner_triage,
        confidence=0.95,
        latency_ms=round(delay * 1000.0, 2),
    )


def generate_unique_decision_state(case_idx: int) -> DecisionState:
    """Generate a guaranteed unique clinical decision state."""
    features_pool = [
        "acute_functional_loss",
        "perfusion_threat",
        "circulatory_compromise",
        "toxic_exposure",
        "visceral_ischemia",
        "uncontrolled_moderate_pain",
        "moderate_dehydration",
        "localized_infection_spreading",
    ]
    # Pick a unique combination or salt
    r = case_idx % 3
    if r == 0:
        floor = "EMERGENCY"
        reasoner = "EMERGENCY"
        feat = (random.choice(features_pool[:4]), f"unique_token_{case_idx}")
        flags = ("no_home_monitoring",)
    elif r == 1:
        floor = "ROUTINE"
        reasoner = "URGENT"
        feat = (random.choice(features_pool[4:]), f"unique_token_{case_idx}")
        flags = ()
    else:
        floor = "ROUTINE"
        reasoner = "ROUTINE"
        feat = ()
        flags = ()

    return DecisionState(
        triage_floor=floor,
        reasoner_triage=reasoner,
        risk_features=feat,
        hard_safety_flags=flags,
        confidence=round(0.80 + random.random() * 0.18, 4),
        fact_coverage=round(0.40 + random.random() * 0.60, 2),
        symptoms_summary=f"Case description variant {case_idx}",
    )


def benchmark_cache_mode(mode: str, n_cases: int = 150) -> dict[str, Any]:
    jev_circuit_breaker.reset()
    latencies: list[float] = []
    cache_hits = 0

    if mode == "warm":
        # Pre-populate cache with a small set of representative states
        fixed_states = [generate_unique_decision_state(i) for i in range(10)]
        for s in fixed_states:
            execute_jev_governed(s)

        for i in range(n_cases):
            st = fixed_states[i % len(fixed_states)]
            t0 = time.perf_counter()
            tri = run_tri_gate_pipeline(
                decision_state=st,
                verifier_fn=lambda: _simulate_gate2_verifier(st.reasoner_triage),
            )
            resolve_tri_gate(tri)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(elapsed_ms)
            if tri.gate3_jev and tri.gate3_jev.cached:
                cache_hits += 1

    elif mode == "cold":
        # Clear cache before EVERY single call
        for i in range(n_cases):
            jev_decision_cache.clear()
            st = generate_unique_decision_state(i)
            t0 = time.perf_counter()
            tri = run_tri_gate_pipeline(
                decision_state=st,
                verifier_fn=lambda: _simulate_gate2_verifier(st.reasoner_triage),
            )
            resolve_tri_gate(tri)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(elapsed_ms)
            if tri.gate3_jev and tri.gate3_jev.cached:
                cache_hits += 1

    else:  # mixed (70% novel cold, 30% warm)
        jev_decision_cache.clear()
        repeated_pool = [generate_unique_decision_state(1000 + i) for i in range(5)]
        for s in repeated_pool:
            execute_jev_governed(s)

        for i in range(n_cases):
            if random.random() < 0.30:
                st = random.choice(repeated_pool)
            else:
                st = generate_unique_decision_state(2000 + i)

            t0 = time.perf_counter()
            tri = run_tri_gate_pipeline(
                decision_state=st,
                verifier_fn=lambda: _simulate_gate2_verifier(st.reasoner_triage),
            )
            resolve_tri_gate(tri)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(elapsed_ms)
            if tri.gate3_jev and tri.gate3_jev.cached:
                cache_hits += 1

    sorted_lat = sorted(latencies)
    n = len(sorted_lat)
    p50 = sorted_lat[int(0.50 * n)]
    p90 = sorted_lat[int(0.90 * n)]
    p95 = sorted_lat[int(0.95 * n)]
    p99 = sorted_lat[min(int(0.99 * n), n - 1)]

    return {
        "mode": mode,
        "n_cases": n_cases,
        "cache_hit_rate": round((cache_hits / n_cases) * 100, 1),
        "mean_ms": round(sum(latencies) / n, 2),
        "p50_ms": round(p50, 2),
        "p90_ms": round(p90, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
    }


def main():
    print("=" * 80)
    print("MEDGUARD AI — JEV CACHE PROFILE STRESS TEST (WARM vs COLD vs MIXED)")
    print("=" * 80)

    res_warm = benchmark_cache_mode("warm", 150)
    res_cold = benchmark_cache_mode("cold", 150)
    res_mixed = benchmark_cache_mode("mixed", 150)

    print(f"{'Cache Mode':<15} | {'Cache Hit %':<12} | {'Mean (ms)':<10} | {'P50 (ms)':<10} | {'P90 (ms)':<10} | {'P95 (ms)':<10} | {'P99 (ms)':<10}")
    print("-" * 80)
    for r in [res_warm, res_mixed, res_cold]:
        print(f"{r['mode'].capitalize():<15} | {r['cache_hit_rate']:>10.1f}% | {r['mean_ms']:>9.2f} | {r['p50_ms']:>9.2f} | {r['p90_ms']:>9.2f} | {r['p95_ms']:>9.2f} | {r['p99_ms']:>9.2f}")
    print("-" * 80)

    cold_delta_pct = ((res_cold["p95_ms"] - res_warm["p95_ms"]) / res_warm["p95_ms"]) * 100
    print(f"Cold vs Warm P95 Latency Delta: {cold_delta_pct:+.1f}% (Gate G23: <= 10%)")
    status = "PASS" if cold_delta_pct <= 10.0 else "INVESTIGATE"
    print(f"Release Gate G23 Status:        {status}")
    print("=" * 80)

    out_file = REPO_ROOT / "outputs" / "jev_cold_cache_report.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "warm": res_warm,
            "mixed": res_mixed,
            "cold": res_cold,
            "cold_p95_delta_pct": round(cold_delta_pct, 2),
            "gate_g23_pass": (cold_delta_pct <= 10.0),
        }, f, indent=2)
    print(f"\n[+] Cold Cache Report saved to: {out_file}")


if __name__ == "__main__":
    main()
