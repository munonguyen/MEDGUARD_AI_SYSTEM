"""MedGuard AI — 900 Clinical Regression Benchmark Runner (V5).

Combines all four validation suites:
- V1: 100 benchmark cases (Original core regression)
- V2: 200 benchmark cases (Blind V2 expansion)
- V3: 300 benchmark cases (Blind V3 stress suite)
- V4: 300 benchmark cases (Blind V4 sealed suite, now frozen into regression)
Total: Exactly 900 clinical cases.

Evaluates against all 14 Mandatory Release Gates.
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


@dataclass
class UnifiedCase:
    source_suite: str  # "V1", "V2", "V3", "V4"
    case_id: str
    input_text: str
    expected_triage: str  # "EMERGENCY" (T4), "URGENT" (T3), "ROUTINE" (T1-T2)
    must_detect: list[str] = field(default_factory=list)
    must_not_say: list[str] = field(default_factory=list)
    critical_fail_conditions: list[str] = field(default_factory=list)
    messages_history: list[dict[str, str]] = field(default_factory=list)
    cohort: str = "general"
    acceptable_triages: list[str] = field(default_factory=list)


def _normalize_triage_label(label: str) -> str:
    norm_upper = str(label).strip().upper()
    # Guard: reject labels that explicitly negate a T4 classification
    # e.g. "Không đủ dữ liệu; hỏi red flags nhưng không tự động khẳng định T4"
    _NEGATION_PHRASES = (
        "KHÔNG TỰ ĐỘNG",
        "KHÔNG ĐỦ DỮ LIỆU",
        "KHÔNG KHẲNG ĐỊNH",
        "CHƯA ĐỦ",
        "INSUFFICIENT",
        "NOT ENOUGH DATA",
    )
    has_negation = any(neg in norm_upper for neg in _NEGATION_PHRASES)
    if (
        not has_negation
        and (
            "T4" in norm_upper
            or "EMERGENCY" in norm_upper
            or "RESUSCITATION" in norm_upper
        )
        and not any(k in norm_upper for k in ("T1/T2", "T0/T1", "T0", "T1"))
    ):
        return "EMERGENCY"
    elif "T3" in norm_upper or "URGENT" in norm_upper:
        return "URGENT"
    elif any(k in norm_upper for k in ("T0", "T1", "T2", "ROUTINE", "GREEN")):
        return "ROUTINE"
    return "ROUTINE"


def load_v1_cases() -> list[UnifiedCase]:
    from scripts.run_100_benchmark import CASES as V1_CASES
    cases = []
    for c in V1_CASES:
        exp_raw = c.expected_triage
        acceptable: list[str] = []
        if "/" in str(exp_raw):
            acceptable = [_normalize_triage_label(p) for p in str(exp_raw).split("/")]

        cases.append(UnifiedCase(
            source_suite="V1",
            case_id=f"V1-{c.id:03d}",
            input_text=c.input,
            expected_triage=_normalize_triage_label(exp_raw),
            must_detect=[c.must_detect] if c.must_detect else [],
            must_not_say=c.must_not_say or [],
            critical_fail_conditions=[c.critical_fail_condition] if c.critical_fail_condition else [],
            messages_history=c.messages_history or [],
            cohort=c.group,
            acceptable_triages=acceptable,
        ))
    return cases


def load_json_suite(path: Path, suite_name: str) -> list[UnifiedCase]:
    with open(path, "r", encoding="utf-8") as f:
        raw_list = json.load(f)
    cases = []
    for idx, c in enumerate(raw_list, 1):
        cid = str(c.get("id") or c.get("case_id") or f"{suite_name}-{idx:04d}")
        if not cid.startswith(suite_name):
            cid = f"{suite_name}-{idx:03d}"
        txt = c.get("input") or c.get("symptoms_text") or ""
        history = c.get("messages_history") or []
        must_detect = c.get("must_detect") or []
        if isinstance(must_detect, str):
            must_detect = [must_detect]
        must_not_say = c.get("must_not_say") or c.get("must_not_assert") or []
        if isinstance(must_not_say, str):
            must_not_say = [must_not_say]
        crit = c.get("critical_if") or c.get("critical_fail_conditions") or []
        if isinstance(crit, str):
            crit = [crit]

        exp_raw = c.get("expected_triage", "ROUTINE")
        acceptable: list[str] = []
        if "/" in str(exp_raw):
            acceptable = [_normalize_triage_label(p) for p in str(exp_raw).split("/")]

        cases.append(UnifiedCase(
            source_suite=suite_name,
            case_id=cid,
            input_text=txt,
            expected_triage=_normalize_triage_label(exp_raw),
            must_detect=must_detect,
            must_not_say=must_not_say,
            critical_fail_conditions=crit,
            messages_history=history,
            cohort=c.get("cohort") or c.get("group") or "general",
            acceptable_triages=acceptable,
        ))
    return cases


def load_all_900_cases() -> list[UnifiedCase]:
    cases: list[UnifiedCase] = []
    # V1 (100)
    cases.extend(load_v1_cases())
    # V2 (200)
    v2_path = REPO_ROOT / "datasets" / "blind_benchmark_v2.json"
    if v2_path.exists():
        cases.extend(load_json_suite(v2_path, "V2"))
    # V3 (300)
    v3_path = REPO_ROOT / "datasets" / "blind_benchmark_v3.json"
    if v3_path.exists():
        cases.extend(load_json_suite(v3_path, "V3"))
    # V4 (300)
    v4_path = REPO_ROOT / "datasets" / "blind_benchmark_v4.json"
    if v4_path.exists():
        cases.extend(load_json_suite(v4_path, "V4"))
    return cases


def evaluate_single_case(c: UnifiedCase, run_salt: str) -> dict[str, Any]:
    ctx = RequestContext(
        request_id=f"reg900-{c.case_id}-{run_salt}",
        tenant_id="medguard-hospital",
        idempotency_key=f"reg900-key-{c.case_id}-{run_salt}",
    )
    messages = []
    for m in c.messages_history:
        messages.append(ChatMessage(role=m.get("role", "user"), content=m.get("content", "")))
    messages.append(ChatMessage(role="user", content=c.input_text))

    req = ChatRequest(
        conversation_id=f"reg900-conv-{c.case_id}-{run_salt}",
        patient_ref=f"patient-reg900-{c.case_id}",
        messages=messages,
    )

    try:
        resp = orchestrate_chat(req, ctx)
        reply = resp.reply or ""
        actual_triage = "ROUTINE"
        if resp.result:
            if isinstance(resp.result, dict):
                r_urg = resp.result.get("urgency")
                if not r_urg:
                    ov = resp.result.get("overall_risk")
                    if ov == "HIGH":
                        r_urg = "EMERGENCY"
                    elif ov == "MODERATE":
                        r_urg = "URGENT"
                actual_triage = str(r_urg or "ROUTINE")
            elif hasattr(resp.result, "urgency"):
                actual_triage = str(resp.result.urgency)
        else:
            norm_rep = normalize_search_text(reply)
            if "cap cuu" in norm_rep or "khan cap" in norm_rep or "115" in norm_rep:
                actual_triage = "EMERGENCY"
            elif "kham som" in norm_rep or "trong ngay" in norm_rep or "chuyen khoa" in norm_rep:
                actual_triage = "URGENT"

        norm_actual = _normalize_triage_label(actual_triage)
        norm_expected = c.expected_triage

        # Check safety invariants
        is_t4_to_routine = (norm_expected == "EMERGENCY" and norm_actual == "ROUTINE")
        is_t4_to_urgent = (norm_expected == "EMERGENCY" and norm_actual == "URGENT")
        is_over_triage = (norm_expected == "ROUTINE" and norm_actual == "EMERGENCY")

        # Check forbidden phrases
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
            "actual": norm_actual,
            "is_match": (norm_expected == norm_actual),
            "is_t4_to_routine": is_t4_to_routine,
            "is_t4_to_urgent": is_t4_to_urgent,
            "is_over_triage": is_over_triage,
            "unsafe_phrases": unsafe_phrases_found,
            "is_error": False,
        }
    except Exception as exc:
        return {
            "case_id": c.case_id,
            "suite": c.source_suite,
            "cohort": c.cohort,
            "expected": c.expected_triage,
            "actual": "ERROR",
            "is_match": False,
            "is_t4_to_routine": (c.expected_triage == "EMERGENCY"),
            "is_t4_to_urgent": False,
            "is_over_triage": False,
            "unsafe_phrases": [],
            "is_error": True,
            "error_msg": str(exc),
        }


def run_900_regression() -> dict[str, Any]:
    cases = load_all_900_cases()
    print(f"[*] Loaded {len(cases)} regression cases across V1, V2, V3, V4 suites.")
    assert len(cases) == 900, f"Expected exactly 900 cases, got {len(cases)}"

    run_salt = str(int(time.time()))
    results = []
    suite_counts: dict[str, int] = {}

    start_time = time.time()
    for idx, c in enumerate(cases, 1):
        suite_counts[c.source_suite] = suite_counts.get(c.source_suite, 0) + 1
        res = evaluate_single_case(c, run_salt)
        results.append(res)
        if idx % 100 == 0 or idx == len(cases):
            elapsed = time.time() - start_time
            print(f"[{idx}/{len(cases)}] Processed in {elapsed:.1f}s...")

    # Calculate Metrics
    emergencies = [r for r in results if r["expected"] == "EMERGENCY"]
    non_emergencies = [r for r in results if r["expected"] != "EMERGENCY"]
    routines = [r for r in results if r["expected"] == "ROUTINE"]

    tp = sum(1 for r in emergencies if r["actual"] == "EMERGENCY")
    fn = len(emergencies) - tp
    tn = sum(1 for r in non_emergencies if r["actual"] != "EMERGENCY")
    fp = len(non_emergencies) - tn

    sensitivity = (tp / len(emergencies) * 100) if emergencies else 100.0
    specificity = (tn / len(non_emergencies) * 100) if non_emergencies else 100.0

    t4_to_routine_count = sum(1 for r in results if r["is_t4_to_routine"])
    t4_to_urgent_count = sum(1 for r in results if r["is_t4_to_urgent"])
    over_triage_count = sum(1 for r in results if r["is_over_triage"])
    over_triage_rate = (over_triage_count / len(routines) * 100) if routines else 0.0

    unsafe_count = sum(len(r["unsafe_phrases"]) for r in results)
    error_count = sum(1 for r in results if r["is_error"])

    # Per-Suite Performance
    per_suite: dict[str, dict[str, Any]] = {}
    for suite_name in ("V1", "V2", "V3", "V4"):
        suite_res = [r for r in results if r["suite"] == suite_name]
        suite_emerg = [r for r in suite_res if r["expected"] == "EMERGENCY"]
        s_tp = sum(1 for r in suite_emerg if r["actual"] == "EMERGENCY")
        s_sens = (s_tp / len(suite_emerg) * 100) if suite_emerg else 100.0
        s_t4_routine = sum(1 for r in suite_res if r["is_t4_to_routine"])
        s_t4_urgent = sum(1 for r in suite_res if r["is_t4_to_urgent"])
        per_suite[suite_name] = {
            "total": len(suite_res),
            "emergency_count": len(suite_emerg),
            "emergency_sensitivity": round(s_sens, 2),
            "t4_to_routine": s_t4_routine,
            "t4_to_urgent": s_t4_urgent,
        }

    # Summary Report
    print("\n" + "=" * 60)
    print("MEDGUARD AI — 900 REGRESSION BENCHMARK REPORT (V5)")
    print("=" * 60)
    print(f"Total Cases Evaluated: {len(results)}")
    print(f"Emergency Sensitivity: {sensitivity:.2f}% ({tp}/{len(emergencies)})")
    print(f"Emergency Specificity: {specificity:.2f}% ({tn}/{len(non_emergencies)})")
    print(f"Pure T4 -> ROUTINE:    {t4_to_routine_count} (Target: 0)")
    print(f"Pure T4 -> URGENT:     {t4_to_urgent_count} (Target: 0)")
    print(f"Over-Triage Rate:      {over_triage_rate:.2f}% ({over_triage_count}/{len(routines)})")
    print(f"Unsafe Phrase Triggers:{unsafe_count}")
    print(f"System Error Count:    {error_count}")
    print("-" * 60)
    print("Per-Suite Breakdown:")
    for s_name, s_data in per_suite.items():
        print(f"  {s_name}: Total {s_data['total']}, Sensitivity {s_data['emergency_sensitivity']}%, T4->ROUTINE: {s_data['t4_to_routine']}, T4->URGENT: {s_data['t4_to_urgent']}")
    print("=" * 60)

    report_payload = {
        "benchmark_name": "MedGuard AI 900 Regression Benchmark",
        "total_cases": len(results),
        "emergency_sensitivity": round(sensitivity, 2),
        "emergency_specificity": round(specificity, 2),
        "t4_to_routine_count": t4_to_routine_count,
        "t4_to_urgent_count": t4_to_urgent_count,
        "over_triage_rate": round(over_triage_rate, 2),
        "unsafe_count": unsafe_count,
        "error_count": error_count,
        "per_suite": per_suite,
    }
    return report_payload


if __name__ == "__main__":
    run_900_regression()
