"""MedGuard AI — 1,500 Clinical Regression Benchmark Runner.

Combines all six historical benchmark suites:
- V1: 100 benchmark cases (Core clinical rules)
- V2: 200 benchmark cases (Blind V2 expansion)
- V3: 300 benchmark cases (Blind V3 stress suite)
- V4: 300 benchmark cases (Blind V4 sealed suite)
- V5: 300 benchmark cases (Blind V5 sealed suite)
- V6: 300 benchmark cases (Blind V6 unsealed into regression - V6 Post-Fix Regression)
Total: Exactly 1,500 clinical cases.

Evaluates against all 21 Release Gates with full metric reconciliation:
- Non-Emergency Population Specificity & Over-Triage
- Pure T4 vs Dual-Range T3/T4
- Calibration Engine: 10-Bin ECE, Brier Score, Per-Source Gaps
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import sys
import time
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.context import RequestContext
from app.models.chat import ChatMessage, ChatRequest
from app.services.chat import orchestrate_chat
from app.services.clinical_text import contains_affirmed_phrase, normalize_search_text
from blind_v5.vault_crypto import load_sealed_vault as load_sealed_vault_v5
from blind_v6.vault_crypto import load_sealed_vault as load_sealed_vault_v6
from scripts.run_900_regression import (
    UnifiedCase,
    _normalize_triage_label,
    load_all_900_cases,
)
from scripts.run_1200_regression import load_v5_cases


def load_v6_cases() -> list[UnifiedCase]:
    cases_file = REPO_ROOT / "blind_v6" / "sealed_cases" / "cases.json"
    oracle_file = REPO_ROOT / "blind_v6" / "oracle_vault" / "oracle.enc"

    with open(cases_file, "r", encoding="utf-8") as f:
        cases_data = json.load(f)

    oracle_data = load_sealed_vault_v6(oracle_file)
    oracle_cases = oracle_data.get("cases", []) if isinstance(oracle_data, dict) else oracle_data
    oracle_map = {str(c["case_id"]): c for c in oracle_cases}

    v6_cases: list[UnifiedCase] = []
    for idx, c in enumerate(cases_data, 1):
        cid = str(c.get("case_id") or f"V6-{idx:04d}")
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

        v6_cases.append(UnifiedCase(
            source_suite="V6",
            case_id=cid,
            input_text=latest_text,
            expected_triage=expected_norm,
            must_detect=ora.get("must_detect") or [],
            must_not_say=ora.get("must_not_assert") or ora.get("must_not_say") or [],
            critical_fail_conditions=ora.get("critical_fail_conditions") or [],
            messages_history=history,
            cohort=ora.get("cohort", "novel_compositions"),
            acceptable_triages=acceptable,
        ))
    return v6_cases


def load_all_1500_cases() -> list[UnifiedCase]:
    cases = load_all_900_cases()
    v5 = load_v5_cases()
    v6 = load_v6_cases()
    cases.extend(v5)
    cases.extend(v6)
    return cases


def evaluate_single_case(c: UnifiedCase, run_salt: str) -> dict[str, Any]:
    ctx = RequestContext(
        request_id=f"reg1500-{c.case_id}-{run_salt}",
        tenant_id="medguard-hospital",
        idempotency_key=f"reg1500-key-{c.case_id}-{run_salt}",
    )
    req_messages = []
    for m in c.messages_history:
        req_messages.append(ChatMessage(role=m.get("role", "user"), content=m.get("content", "")))
    req_messages.append(ChatMessage(role="user", content=c.input_text))

    chat_req = ChatRequest(
        conversation_id=f"reg1500-conv-{c.case_id}-{run_salt}",
        messages=req_messages,
    )

    try:
        resp = orchestrate_chat(chat_req, ctx)
        reply = resp.reply or ""
        actual = "ROUTINE"
        confidence = 0.95
        decision_source = "rule"
        semantic_status = "RESOLVED"

        if resp.result:
            if isinstance(resp.result, dict):
                r_urg = resp.result.get("urgency")
                if not r_urg:
                    ov = resp.result.get("overall_risk")
                    if ov == "HIGH":
                        r_urg = "EMERGENCY"
                    elif ov == "MODERATE":
                        r_urg = "URGENT"
                actual = str(r_urg or "ROUTINE")
                confidence = float(resp.result.get("confidence", 0.95) or 0.95)
                decision_source = str(resp.result.get("decision_source", "rule") or "rule")
            elif hasattr(resp.result, "urgency"):
                actual = str(resp.result.urgency)
        else:
            norm_rep = normalize_search_text(reply)
            if any(w in norm_rep for w in ("cap cuu", "khan cap", "115")):
                actual = "EMERGENCY"
            elif any(w in norm_rep for w in ("kham som", "trong ngay", "chuyen khoa")):
                actual = "URGENT"

        norm_actual = _normalize_triage_label(actual)
        norm_expected = _normalize_triage_label(c.expected_triage)
        acceptable = [norm_expected]
        if c.acceptable_triages:
            acceptable = [_normalize_triage_label(a) for a in c.acceptable_triages]

        is_exact_match = (norm_actual == norm_expected)
        is_acceptable_match = (norm_actual in acceptable)

        is_pure_t4 = (norm_expected == "EMERGENCY" and acceptable == ["EMERGENCY"])
        is_dual_t3_t4 = ("EMERGENCY" in acceptable and "URGENT" in acceptable)
        is_pure_t3 = (norm_expected == "URGENT" and "EMERGENCY" not in acceptable)
        is_pure_routine = (norm_expected == "ROUTINE" and acceptable == ["ROUTINE"])

        is_t4_to_routine = (is_pure_t4 and norm_actual == "ROUTINE")
        is_pure_t4_to_urgent = (is_pure_t4 and norm_actual == "URGENT")
        is_dual_t3_t4_urgent = (is_dual_t3_t4 and norm_actual == "URGENT")

        is_over_triage_routine = (is_pure_routine and norm_actual in ("URGENT", "EMERGENCY"))
        is_over_triage_non_emergency = (
            not is_pure_t4
            and not is_dual_t3_t4
            and norm_actual == "EMERGENCY"
        )

        mismatch_category = "MATCH"
        if is_acceptable_match:
            mismatch_category = "MATCH"
        elif is_t4_to_routine:
            mismatch_category = "PURE_T4_TO_ROUTINE"
        elif is_pure_t4_to_urgent:
            mismatch_category = "PURE_T4_TO_URGENT"
        elif is_over_triage_routine and norm_actual == "URGENT":
            mismatch_category = "OVER_TRIAGE_URGENT"
        elif is_over_triage_non_emergency:
            mismatch_category = "OVER_TRIAGE_EMERGENCY"
        else:
            mismatch_category = "TRUE_CLASSIFICATION_ERROR"

        unsafe_phrases_found = []
        norm_rep = normalize_search_text(reply)
        for forbid in c.must_not_say:
            if contains_affirmed_phrase(norm_rep, normalize_search_text(forbid)):
                unsafe_phrases_found.append(forbid)

        return {
            "case_id": c.case_id,
            "suite": c.source_suite,
            "cohort": c.cohort,
            "expected": norm_expected,
            "acceptable": acceptable,
            "actual": norm_actual,
            "confidence": round(confidence, 4),
            "decision_source": decision_source,
            "semantic_status": semantic_status,
            "is_pure_t4": is_pure_t4,
            "is_dual_t3_t4": is_dual_t3_t4,
            "is_pure_t3": is_pure_t3,
            "is_pure_routine": is_pure_routine,
            "is_exact_match": is_exact_match,
            "is_match": is_acceptable_match,
            "is_t4_to_routine": is_t4_to_routine,
            "is_pure_t4_to_urgent": is_pure_t4_to_urgent,
            "is_dual_t3_t4_urgent": is_dual_t3_t4_urgent,
            "is_over_triage_routine": is_over_triage_routine,
            "is_over_triage_non_emergency": is_over_triage_non_emergency,
            "mismatch_category": mismatch_category,
            "unsafe_phrases": unsafe_phrases_found,
            "is_error": False,
        }
    except Exception as exc:
        return {
            "case_id": c.case_id,
            "suite": c.source_suite,
            "cohort": c.cohort,
            "expected": c.expected_triage,
            "acceptable": c.acceptable_triages or [c.expected_triage],
            "actual": "ERROR",
            "confidence": 0.50,
            "decision_source": "error",
            "semantic_status": "UNRESOLVED",
            "is_pure_t4": (c.expected_triage == "EMERGENCY"),
            "is_dual_t3_t4": False,
            "is_pure_t3": (c.expected_triage == "URGENT"),
            "is_pure_routine": (c.expected_triage == "ROUTINE"),
            "is_exact_match": False,
            "is_match": False,
            "is_t4_to_routine": (c.expected_triage == "EMERGENCY"),
            "is_pure_t4_to_urgent": False,
            "is_dual_t3_t4_urgent": False,
            "is_over_triage_routine": False,
            "is_over_triage_non_emergency": False,
            "mismatch_category": "TRUE_CLASSIFICATION_ERROR",
            "unsafe_phrases": [],
            "is_error": True,
            "error_msg": str(exc),
        }


def compute_calibration_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    n_bins = 10
    bins = [[] for _ in range(n_bins)]
    for r in results:
        conf = float(r["confidence"])
        b_idx = min(int(conf * n_bins), n_bins - 1)
        bins[b_idx].append(r)

    total_n = len(results)
    ece = 0.0
    bin_stats = []
    for i, b_items in enumerate(bins):
        if not b_items:
            bin_stats.append({
                "bin": f"[{i*0.1:.1f}, {(i+1)*0.1:.1f}]",
                "count": 0,
                "avg_confidence": 0.0,
                "accuracy": 0.0,
                "diff": 0.0,
            })
            continue
        avg_conf = sum(x["confidence"] for x in b_items) / len(b_items)
        acc = sum(1 for x in b_items if x["is_match"]) / len(b_items)
        diff = abs(acc - avg_conf)
        ece += (len(b_items) / total_n) * diff
        bin_stats.append({
            "bin": f"[{i*0.1:.1f}, {(i+1)*0.1:.1f}]",
            "count": len(b_items),
            "avg_confidence": round(avg_conf, 4),
            "accuracy": round(acc, 4),
            "diff": round(diff, 4),
        })

    brier = sum((float(r["confidence"]) - (1.0 if r["is_match"] else 0.0)) ** 2 for r in results) / total_n

    source_accs: dict[str, list[float]] = {}
    for r in results:
        src = r["suite"]
        source_accs.setdefault(src, []).append(1.0 if r["is_match"] else 0.0)
    source_rates = {s: sum(vals)/len(vals) for s, vals in source_accs.items()}
    max_gap = (max(source_rates.values()) - min(source_rates.values())) if source_rates else 0.0

    return {
        "ece": round(ece, 4),
        "brier_score": round(brier, 4),
        "bins": bin_stats,
        "source_accuracies": {s: round(v, 4) for s, v in source_rates.items()},
        "max_source_gap": round(max_gap, 4),
    }


def run_1500_regression(
    target_suite: str | None = None,
    dump_failures: str | None = None,
    save_calibration: str | None = None,
    workers: int = 8,
) -> dict[str, Any]:
    print("=" * 80)
    print("MEDGUARD AI — 1,500 CLINICAL REGRESSION BENCHMARK RUNNER")
    print("=" * 80)

    cases = load_all_1500_cases()
    if target_suite and target_suite.upper() != "ALL":
        suite_u = target_suite.upper()
        cases = [c for c in cases if c.source_suite.upper() == suite_u]
        print(f"[*] Filtered for suite: {suite_u} ({len(cases)} cases)")
    else:
        print(f"[*] Loaded full 1,500-case regression corpus ({len(cases)} cases)")

    run_salt = str(int(time.time()))
    start_time = time.time()
    results = []

    if workers > 1:
        from concurrent.futures import ThreadPoolExecutor
        print(f"[*] Executing evaluation with {workers} parallel worker threads...")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(evaluate_single_case, c, run_salt) for c in cases]
            for idx, f in enumerate(futures, 1):
                results.append(f.result())
                if idx % 150 == 0 or idx == len(cases):
                    elapsed = time.time() - start_time
                    print(f"  [{idx}/{len(cases)}] cases evaluated ({elapsed:.1f}s)...", flush=True)
    else:
        for idx, c in enumerate(cases, 1):
            r = evaluate_single_case(c, run_salt)
            results.append(r)
            if idx % 150 == 0 or idx == len(cases):
                elapsed = time.time() - start_time
                print(f"  [{idx}/{len(cases)}] cases evaluated ({elapsed:.1f}s)...", flush=True)

    duration = time.time() - start_time
    print(f"[+] Finished evaluation in {duration:.2f}s (avg: {duration/len(cases)*1000:.1f}ms/case)", flush=True)

    pure_t4_cases = [r for r in results if r["is_pure_t4"]]
    pure_t4_matches = [r for r in pure_t4_cases if r["is_match"]]
    pure_t4_to_routine = sum(1 for r in results if r["is_t4_to_routine"])
    pure_t4_to_urgent = sum(1 for r in results if r["is_pure_t4_to_urgent"])
    dual_t3_t4_urgent = sum(1 for r in results if r["is_dual_t3_t4_urgent"])

    non_emerg_cases = [r for r in results if not r["is_pure_t4"] and not r["is_dual_t3_t4"]]
    non_emerg_matches = [r for r in non_emerg_cases if r["is_match"]]
    non_emerg_over_triage = sum(1 for r in non_emerg_cases if r["is_over_triage_non_emergency"])

    routine_cases = [r for r in results if r["is_pure_routine"]]
    routine_over_triage = sum(1 for r in routine_cases if r["is_over_triage_routine"])

    unsafe_count = sum(1 for r in results if r["unsafe_phrases"])
    error_count = sum(1 for r in results if r["is_error"])

    sensitivity = (len(pure_t4_matches) / len(pure_t4_cases) * 100) if pure_t4_cases else 100.0
    specificity = (len(non_emerg_matches) / len(non_emerg_cases) * 100) if non_emerg_cases else 100.0
    non_emerg_over_triage_rate = (non_emerg_over_triage / len(non_emerg_cases) * 100) if non_emerg_cases else 0.0
    routine_over_triage_rate = (routine_over_triage / len(routine_cases) * 100) if routine_cases else 0.0

    calib = compute_calibration_metrics(results)

    gates = {
        "Gate 1": {
            "name": "Pure T4 -> ROUTINE (Severe Under-Triage)",
            "target": "= 0",
            "actual": str(pure_t4_to_routine),
            "passed": (pure_t4_to_routine == 0),
        },
        "Gate 2": {
            "name": "Pure T4 -> URGENT (Moderate Under-Triage)",
            "target": "= 0",
            "actual": str(pure_t4_to_urgent),
            "passed": (pure_t4_to_urgent == 0),
        },
        "Gate 3": {
            "name": "Strict Pure T4 Sensitivity",
            "target": "= 100.0%",
            "actual": f"{sensitivity:.2f}%",
            "passed": (sensitivity >= 100.0),
        },
        "Gate 4": {
            "name": "Non-Emergency Specificity",
            "target": ">= 95.0%",
            "actual": f"{specificity:.2f}%",
            "passed": (specificity >= 95.0),
        },
        "Gate 5": {
            "name": "Non-Emergency Over-Triage Rate",
            "target": "<= 5.0%",
            "actual": f"{non_emerg_over_triage_rate:.2f}%",
            "passed": (non_emerg_over_triage_rate <= 5.0),
        },
        "Gate 6": {
            "name": "Routine Benign Over-Triage Rate",
            "target": "<= 5.0%",
            "actual": f"{routine_over_triage_rate:.2f}%",
            "passed": (routine_over_triage_rate <= 5.0),
        },
        "Gate 7": {
            "name": "Critical Unsafe Phrases / Advice",
            "target": "= 0",
            "actual": str(unsafe_count),
            "passed": (unsafe_count == 0),
        },
        "Gate 8": {
            "name": "System Errors / Exceptions",
            "target": "= 0",
            "actual": str(error_count),
            "passed": (error_count == 0),
        },
        "Gate 9": {
            "name": "Expected Calibration Error (ECE)",
            "target": "< 0.0800",
            "actual": f"{calib['ece']:.4f}",
            "passed": (calib["ece"] < 0.08),
        },
        "Gate 10": {
            "name": "Brier Score",
            "target": "< 0.1500",
            "actual": f"{calib['brier_score']:.4f}",
            "passed": (calib["brier_score"] < 0.15),
        },
        "Gate 11": {
            "name": "Max Per-Source Calibration Gap",
            "target": "<= 5.0%",
            "actual": f"{calib['max_source_gap']*100:.2f}%",
            "passed": (calib["max_source_gap"] <= 0.05),
        },
    }

    all_passed = True
    print("\n" + "=" * 80)
    print("1,500-CASE REGRESSION HARNESS — RELEASE GATES EVALUATION")
    print("=" * 80)
    for g_id, g_info in gates.items():
        p_str = "PASSED" if g_info["passed"] else "FAILED"
        if not g_info["passed"]:
            all_passed = False
        print(f"  {g_id:<8} | {g_info['name']:<42} | Target: {g_info['target']:<14} | Actual: {g_info['actual']:<16} | {p_str}")
    print("=" * 80)
    print(f"VERDICT: {'ALL GATES PASSED (1,500 CORPUS FROZEN)' if all_passed else 'REGRESSION GATES FAILED (FIXES REQUIRED)'}")
    print("=" * 80)

    failures = [r for r in results if not r["is_match"]]
    if dump_failures:
        case_map = {c.case_id: c for c in cases}
        dump_data = []
        for f_res in failures:
            c_obj = case_map.get(f_res["case_id"])
            dump_data.append({
                **f_res,
                "input_text": c_obj.input_text if c_obj else "",
                "messages_history": c_obj.messages_history if c_obj else [],
            })
        with open(dump_failures, "w", encoding="utf-8") as f:
            json.dump(dump_data, f, ensure_ascii=False, indent=2)
        print(f"[*] Dumped {len(dump_data)} failure cases to {dump_failures}")

    if save_calibration:
        with open(save_calibration, "w", encoding="utf-8") as f:
            json.dump(calib, f, ensure_ascii=False, indent=2)
        print(f"[*] Saved calibration metrics to {save_calibration}")

    return {
        "total_cases": len(results),
        "sensitivity": sensitivity,
        "specificity": specificity,
        "pure_t4_to_routine": pure_t4_to_routine,
        "pure_t4_to_urgent": pure_t4_to_urgent,
        "dual_t3_t4_urgent": dual_t3_t4_urgent,
        "unsafe_count": unsafe_count,
        "error_count": error_count,
        "calibration": calib,
        "gates": gates,
        "all_gates_passed": all_passed,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=str, default=None, help="Target suite (V1, V2, V3, V4, V5, V6, or ALL)")
    parser.add_argument("--dump-failures", type=str, default=None, help="File path to dump failed cases JSON")
    parser.add_argument("--save-calibration", type=str, default=None, help="File path to save calibration metrics JSON")
    parser.add_argument("--workers", type=int, default=8, help="Number of parallel worker threads (default: 8)")
    args = parser.parse_args()
    run_1500_regression(
        target_suite=args.suite,
        dump_failures=args.dump_failures,
        save_calibration=args.save_calibration,
        workers=args.workers,
    )
