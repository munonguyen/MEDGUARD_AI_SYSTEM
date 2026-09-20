"""Evaluator for DS-ADVANCED-TOXICOLOGY Benchmark (160 cases).

Evaluates the Advanced Toxicology Reasoner against the two mandatory hard gates:
1. Critical toxicology under-triage == 0
2. Advanced Toxicology Accuracy >= 98.0%
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.toxicology_reasoner import evaluate_toxicology, ToxicologyUrgency
from scripts.run_900_regression import _normalize_triage_label

DATASET_PATH = REPO_ROOT / "datasets" / "DS-ADVANCED-TOXICOLOGY" / "dataset.json"


def evaluate_advanced_toxicology() -> dict[str, Any]:
    print("=" * 80)
    print("MEDGUARD AI — ADVANCED TOXICOLOGY BENCHMARK EVALUATOR")
    print("=" * 80)

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases = data["cases"]
    print(f"[*] Loaded {len(cases)} toxicology cases from {DATASET_PATH}")

    correct = 0
    critical_under_triage = 0
    over_triage = 0
    failures = []

    for c in cases:
        prompt = c["prompt"]
        expected = c["expected_triage"]
        assessment = evaluate_toxicology(prompt)
        actual = assessment.urgency.value

        norm_exp = _normalize_triage_label(expected)
        norm_act = _normalize_triage_label(actual)

        is_match = (norm_act == norm_exp)
        if is_match:
            correct += 1
        else:
            if norm_exp == "EMERGENCY" and norm_act == "ROUTINE":
                critical_under_triage += 1
            elif norm_exp == "ROUTINE" and norm_act in ("URGENT", "EMERGENCY"):
                over_triage += 1
            failures.append({
                "case_id": c["case_id"],
                "cohort": c["cohort"],
                "prompt": prompt,
                "expected": norm_exp,
                "actual": norm_act,
                "reasons": assessment.reasons,
            })

    accuracy = (correct / len(cases)) * 100.0
    gate1_passed = (critical_under_triage == 0)
    gate2_passed = (accuracy >= 98.0)
    all_passed = gate1_passed and gate2_passed

    print("\n" + "=" * 80)
    print("ADVANCED TOXICOLOGY BENCHMARK — GATE RESULTS")
    print("=" * 80)
    print(f"  Gate 1 | Critical Toxicology Under-Triage | Target: = 0    | Actual: {critical_under_triage:<6} | {'PASSED' if gate1_passed else 'FAILED'}")
    print(f"  Gate 2 | Advanced Toxicology Accuracy     | Target: >= 98% | Actual: {accuracy:.2f}% | {'PASSED' if gate2_passed else 'FAILED'}")
    print("=" * 80)
    print(f"OVERALL VERDICT: {'PASSED (FREEZE READY)' if all_passed else 'FAILED (REFINEMENT REQUIRED)'}")
    print("=" * 80)

    report = {
        "total_cases": len(cases),
        "accuracy": round(accuracy, 2),
        "critical_under_triage": critical_under_triage,
        "over_triage": over_triage,
        "gate1_passed": gate1_passed,
        "gate2_passed": gate2_passed,
        "all_passed": all_passed,
        "failures_count": len(failures),
        "failures": failures,
    }

    report_path = REPO_ROOT / "datasets" / "DS-ADVANCED-TOXICOLOGY" / "eval_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"[+] Saved evaluation report to: {report_path}")

    return report


if __name__ == "__main__":
    evaluate_advanced_toxicology()
