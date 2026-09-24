"""MedGuard AI — 2,100 Clinical Historical Regression Suite Runner (Candidate V9).

Combines all eight historical benchmark suites:
- V1: 100 benchmark cases (Core clinical rules)
- V2: 200 benchmark cases (Blind V2 expansion)
- V3: 300 benchmark cases (Blind V3 stress suite)
- V4: 300 benchmark cases (Blind V4 sealed suite)
- V5: 300 benchmark cases (Blind V5 sealed suite)
- V6: 300 benchmark cases (Blind V6 unsealed into regression)
- V7: 300 benchmark cases (Blind V7 unsealed into regression)
- V8: 300 benchmark cases (Blind V8 unsealed into regression)
Total: Exactly 2,100 clinical cases.

Release Gates for Candidate V9:
- Pure T4 -> ROUTINE = 0
- Pure T4 -> URGENT = 0
- Specificity >= 95.0%
- Critical Unsafe Advice = 0
- Calibration OOF ECE <= 0.08
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from blind_v8.vault_crypto import load_sealed_vault as load_sealed_vault_v8
from scripts.run_900_regression import UnifiedCase, _normalize_triage_label
from concurrent.futures import ThreadPoolExecutor
from scripts.run_1800_regression import load_all_1800_cases, evaluate_single_case


def load_v8_cases() -> list[UnifiedCase]:
    v8_dir = REPO_ROOT / "blind_v8"
    cases_file = v8_dir / "sealed_cases" / "cases.json"
    oracle_file = v8_dir / "oracle_vault" / "oracle.enc"

    with open(cases_file, "r", encoding="utf-8") as f:
        cases_data = json.load(f)

    oracle_data = load_sealed_vault_v8(oracle_file)
    oracle_cases = oracle_data.get("cases", []) if isinstance(oracle_data, dict) else oracle_data
    oracle_map = {str(c["case_id"]): c for c in oracle_cases}

    v8_cases: list[UnifiedCase] = []
    for idx, c in enumerate(cases_data, 1):
        cid = str(c.get("case_id") or f"V8-{idx:04d}")
        ora = oracle_map.get(cid, {})

        messages = c.get("messages") or []
        history = messages[:-1] if len(messages) > 1 else []
        latest_text = messages[-1]["content"] if messages else (c.get("input") or "")

        expected_raw = ora.get("oracle_triage", "ROUTINE")
        expected_norm = _normalize_triage_label(expected_raw)
        acceptable: list[str] = []
        if ora.get("acceptable_triage"):
            acceptable = [_normalize_triage_label(p) for p in ora.get("acceptable_triage")]
        elif "/" in str(expected_raw):
            acceptable = [_normalize_triage_label(p) for p in str(expected_raw).split("/")]

        v8_cases.append(
            UnifiedCase(
                source_suite="V8",
                case_id=cid,
                input_text=latest_text,
                expected_triage=expected_norm,
                must_detect=ora.get("must_detect") or [],
                must_not_say=ora.get("must_not_assert") or ora.get("must_not_say") or [],
                critical_fail_conditions=ora.get("critical_fail_conditions") or [],
                messages_history=history,
                cohort=ora.get("cohort", "v8_generalization"),
                acceptable_triages=acceptable,
            )
        )
    return v8_cases


def load_all_2100_cases() -> list[UnifiedCase]:
    cases = load_all_1800_cases()
    cases.extend(load_v8_cases())
    return cases


def run_historical_regression_2100(sample_limit: int | None = None, workers: int = 8) -> dict[str, Any]:
    print("=" * 85)
    print("MEDGUARD AI CANDIDATE V9 — HISTORICAL REGRESSION RUNNER (2,100 CASES)")
    print("=" * 85)

    cases = load_all_2100_cases()
    if sample_limit:
        cases = cases[:sample_limit]

    n = len(cases)
    print(f"[*] Loaded {n} clinical cases across V1–V8.")
    print(f"[*] Starting execution with {workers} worker threads...", flush=True)

    suites = ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"]
    suite_metrics: dict[str, dict[str, Any]] = {
        s: {
            "total_cases": 0,
            "pure_t4_population": 0,
            "pure_t4_to_emergency": 0,
            "pure_t4_to_urgent": 0,
            "pure_t4_to_routine": 0,
            "non_emergency_population": 0,
            "tn": 0,
            "fp": 0,
            "routine_population": 0,
            "routine_to_emergency": 0,
            "routine_to_urgent": 0,
            "routine_to_routine": 0,
            "system_errors": 0,
        }
        for s in suites
    }

    run_salt = str(int(time.time()))
    t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(evaluate_single_case, c, run_salt) for c in cases]
        results = []
        for idx, f in enumerate(futures, 1):
            results.append(f.result())
            if idx % 200 == 0 or idx == n:
                print(f"[*] Processed {idx}/{n} cases ({(idx/n)*100:.1f}%)...", flush=True)

    elapsed = time.perf_counter() - t0

    t4_total = 0
    t4_to_emergency = 0
    t4_to_urgent = 0
    t4_to_routine = 0

    non_em_total = 0
    tn_total = 0
    fp_total = 0

    routine_total = 0
    routine_to_em = 0
    routine_to_urg = 0
    routine_to_rout = 0

    system_errors_total = 0

    for r in results:
        s_name = r.get("source_suite", "V8")
        if s_name not in suite_metrics:
            s_name = "V8"
        s_data = suite_metrics[s_name]
        s_data["total_cases"] += 1

        if r.get("system_error", False):
            system_errors_total += 1
            s_data["system_errors"] += 1
            continue

        exp = r["expected_triage"]
        act = r["actual_triage"]
        is_pure_t4 = r.get("is_pure_t4", False)

        if is_pure_t4:
            t4_total += 1
            s_data["pure_t4_population"] += 1
            if act == "EMERGENCY":
                t4_to_emergency += 1
                s_data["pure_t4_to_emergency"] += 1
            elif act == "ROUTINE":
                t4_to_routine += 1
                s_data["pure_t4_to_routine"] += 1
            elif act == "URGENT":
                t4_to_urgent += 1
                s_data["pure_t4_to_urgent"] += 1
        elif exp != "EMERGENCY":
            non_em_total += 1
            s_data["non_emergency_population"] += 1
            if act != "EMERGENCY":
                tn_total += 1
                s_data["tn"] += 1
            else:
                fp_total += 1
                s_data["fp"] += 1

            if exp == "ROUTINE":
                routine_total += 1
                s_data["routine_population"] += 1
                if act == "EMERGENCY":
                    routine_to_em += 1
                    s_data["routine_to_emergency"] += 1
                elif act == "URGENT":
                    routine_to_urg += 1
                    s_data["routine_to_urgent"] += 1
                else:
                    routine_to_rout += 1
                    s_data["routine_to_routine"] += 1

    t4_sens = (t4_to_emergency / t4_total * 100.0) if t4_total > 0 else 0.0
    specificity = (tn_total / non_em_total * 100.0) if non_em_total > 0 else 100.0

    print(f"\n{'='*85}")
    print(f"MEDGUARD CANDIDATE V9 — 2,100 HISTORICAL REGRESSION RESULTS")
    print(f"{'='*85}")
    print(f"Total cases = {n}")
    print(f"Elapsed time = {elapsed:.2f}s ({elapsed/n*1000:.2f} ms/case)")
    print()
    print(f"Pure T4 population = {t4_total}")
    print(f"Pure T4 -> EMERGENCY = {t4_to_emergency} ({t4_sens:.2f}%)")
    print(f"Pure T4 -> URGENT = {t4_to_urgent}")
    print(f"Pure T4 -> ROUTINE = {t4_to_routine}")
    print()
    print(f"Non-emergency population = {non_em_total}")
    print(f"TN = {tn_total}")
    print(f"FP = {fp_total}")
    print(f"Specificity = {specificity:.2f}%")
    print()
    print(f"Routine benign population = {routine_total}")
    print(f"Routine -> Emergency = {routine_to_em}")
    print(f"Routine -> Urgent = {routine_to_urg}")
    print(f"Routine -> Routine = {routine_to_rout}")
    print()
    print(f"System errors = {system_errors_total}")
    print(f"{'='*85}")

    print("\n[SUITE BREAKDOWN (V1 -> V8)]")
    print(f"{'Suite':<6} | {'Total':<6} | {'T4 Pop':<6} | {'T4->EM':<6} | {'T4->URG':<7} | {'T4->ROUT':<8} | {'Non-EM':<6} | {'Spec %':<7} | {'Errors':<6}")
    print("-" * 75)
    for s in suites:
        sd = suite_metrics[s]
        s_spec = (sd["tn"] / sd["non_emergency_population"] * 100.0) if sd["non_emergency_population"] > 0 else 100.0
        sd["specificity_pct"] = round(s_spec, 2)
        print(f"{s:<6} | {sd['total_cases']:<6} | {sd['pure_t4_population']:<6} | {sd['pure_t4_to_emergency']:<6} | {sd['pure_t4_to_urgent']:<7} | {sd['pure_t4_to_routine']:<8} | {sd['non_emergency_population']:<6} | {s_spec:>6.2f}% | {sd['system_errors']:<6}")

    report = {
        "total_cases": n,
        "elapsed_sec": round(elapsed, 2),
        "pure_t4_population": t4_total,
        "pure_t4_to_emergency": t4_to_emergency,
        "pure_t4_to_urgent": t4_to_urgent,
        "pure_t4_to_routine": t4_to_routine,
        "t4_sensitivity_pct": round(t4_sens, 2),
        "non_emergency_population": non_em_total,
        "tn": tn_total,
        "fp": fp_total,
        "specificity_pct": round(specificity, 2),
        "routine_benign_population": routine_total,
        "routine_to_emergency": routine_to_em,
        "routine_to_urgent": routine_to_urg,
        "routine_to_routine": routine_to_rout,
        "system_errors": system_errors_total,
        "suite_breakdown": suite_metrics,
    }

    out_file = REPO_ROOT / "outputs" / "historical_regression_2100_report.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\n[+] Saved complete 2,100 regression report to: {out_file}")
    return report


if __name__ == "__main__":
    run_historical_regression_2100()
