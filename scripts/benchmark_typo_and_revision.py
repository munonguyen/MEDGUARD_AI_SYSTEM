#!/usr/bin/env python3
"""Benchmark evaluation script for Typo-Resilience and Natural Language Revision.

Evaluates all 40 cases in datasets/DS-TYPO-AND-REVISION/dataset.json:
  1. TYPO_RESILIENCE (20 cases)
  2. VERIFIER_CRITIQUE_REVISION (10 cases)
  3. NATURAL_PERSUASIVE_TRIAGE (10 cases)

Usage:
    .venv/bin/python scripts/benchmark_typo_and_revision.py
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.context import RequestContext
from app.models.chat import ChatMessage, ChatRequest
from app.services.chat import _detect_intent, orchestrate_chat
from app.services.clinical_text import normalize_search_text

DATASET_PATH = PROJECT_ROOT / "datasets" / "DS-TYPO-AND-REVISION" / "dataset.json"
REPORT_PATH = PROJECT_ROOT / "datasets" / "DS-TYPO-AND-REVISION" / "eval_report.json"


def main() -> int:
    with open(DATASET_PATH, encoding="utf-8") as f:
        data = json.load(f)

    cases = data["cases"]
    total = len(cases)
    print(f"\n🚀 Running Benchmark on {total} Typo-Resilience & Revision cases...")
    print("=" * 76)

    group_stats: dict[str, dict[str, int]] = {}
    passed_total = 0
    failures: list[dict] = []
    start_time = time.perf_counter()

    for idx, case in enumerate(cases, 1):
        case_id = case["case_id"]
        group = case["group"]
        query = case["input"]
        expected_intent = case["expected_intent"]
        expected_urgency = case.get("expected_urgency")

        if group not in group_stats:
            group_stats[group] = {"total": 0, "pass": 0, "fail": 0}
        group_stats[group]["total"] += 1

        t0 = time.perf_counter()
        normalized = normalize_search_text(query)

        ctx = RequestContext(
            request_id=f"req-bench-{idx}",
            tenant_id="tenant-demo",
            idempotency_key=f"ik-bench-{idx}",
        )
        req = ChatRequest(
            conversation_id=f"conv-bench-{idx}",
            messages=[ChatMessage(role="user", content=query)],
        )

        resp = orchestrate_chat(req, ctx)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Verification criteria
        is_pass = True
        reasons = []

        if resp.intent != expected_intent:
            is_pass = False
            reasons.append(f"Intent mismatch: expected {expected_intent}, got {resp.intent}")

        if expected_urgency and resp.result and hasattr(resp.result, "urgency"):
            if resp.result.urgency != expected_urgency:
                is_pass = False
                reasons.append(f"Urgency mismatch: expected {expected_urgency}, got {resp.result.urgency}")

        # Ensure answer is not empty or robotic
        if resp.status == "answered":
            summary = resp.answer.summary.lower()
            if len(summary) < 30:
                is_pass = False
                reasons.append(f"Summary too short/uninformative: {resp.answer.summary}")

        if is_pass:
            group_stats[group]["pass"] += 1
            passed_total += 1
            print(f"  [{idx:2d}/{total}] ✅ {case_id} ({group:<26}) {elapsed_ms:6.1f}ms")
        else:
            group_stats[group]["fail"] += 1
            print(f"  [{idx:2d}/{total}] ❌ {case_id} ({group:<26}) {elapsed_ms:6.1f}ms -> {', '.join(reasons)}")
            failures.append({
                "case_id": case_id,
                "input": query,
                "reasons": reasons,
            })

    total_time = time.perf_counter() - start_time
    print("=" * 76)
    print(f"  🎯 RESULT: {passed_total}/{total} Passed ({(passed_total/total)*100:.1f}%) in {total_time:.2f}s")

    for g, s in group_stats.items():
        rate = (s["pass"] / s["total"]) * 100 if s["total"] else 0
        print(f"  • {g:<26}: {s['pass']:2d}/{s['total']:2d} ({rate:.1f}%)")

    report = {
        "dataset_version": data.get("_meta", {}).get("version", "1.0.0"),
        "total": total,
        "passed": passed_total,
        "accuracy": round(passed_total / total, 4),
        "execution_time_seconds": round(total_time, 2),
        "group_breakdown": group_stats,
        "failures": failures,
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  Saved report to: {REPORT_PATH}\n")

    return 0 if passed_total == total else 1


if __name__ == "__main__":
    sys.exit(main())
