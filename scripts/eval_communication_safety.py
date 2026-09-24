"""Evaluate deterministic safety gates and Vietnamese communication labels.

This regression runner intentionally reports whether its dataset is production
evaluable. Project-authored examples can validate code behavior but cannot be
used to claim superiority over external models.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.jury_evaluator import (  # noqa: E402
    CommunicationQualityEvaluator,
    MedicalSafetyGate,
    QAGEvaluator,
)


def evaluate_dataset(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases", [])
    results: list[dict[str, Any]] = []
    labels: Counter[str] = Counter()
    passed = 0

    for case in cases:
        grounding = QAGEvaluator.evaluate_groundedness(case["answer"], case.get("contexts", []))
        gate = MedicalSafetyGate.evaluate(
            answer_text=case["answer"],
            locked_claims=case.get("locked_claims", []),
            abstains_from_diagnosis=case.get("abstains_from_diagnosis", True),
            red_flags_present=case.get("red_flags_present", False),
            triage_urgency=case.get("triage_urgency", "ROUTINE"),
            grounding=grounding,
        )
        communication = CommunicationQualityEvaluator.evaluate(
            question=case["question"],
            answer_text=case["answer"],
            high_risk=case.get("red_flags_present", False)
            or case.get("triage_urgency", "ROUTINE") in {"EMERGENCY", "CRITICAL"},
            safety_gate=gate,
            groundedness=grounding["groundedness_ratio"],
        )
        labels[communication.impact_label] += 1
        case_passed = (
            gate.passed == case["expected_gate_pass"]
            and communication.impact_label == case["expected_impact_label"]
        )
        passed += int(case_passed)
        results.append(
            {
                "case_id": case["case_id"],
                "passed": case_passed,
                "expected_gate_pass": case["expected_gate_pass"],
                "actual_gate_pass": gate.passed,
                "expected_impact_label": case["expected_impact_label"],
                "actual_impact_label": communication.impact_label,
                "safety_gate": gate.to_dict(),
                "communication_quality": communication.to_dict(),
                "grounding": grounding,
            }
        )

    total = len(cases)
    return {
        "dataset": str(path),
        "dataset_version": payload.get("_meta", {}).get("version"),
        "production_evaluable": bool(payload.get("_meta", {}).get("production_evaluable", False)),
        "total_cases": total,
        "passed_cases": passed,
        "pass_rate": round(passed / total, 3) if total else 0.0,
        "impact_labels": dict(labels),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("datasets/DS-COMMUNICATION-SAFETY/dataset.json"),
    )
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    report = evaluate_dataset(args.dataset)
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False, indent=2))
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    raise SystemExit(0 if report["passed_cases"] == report["total_cases"] else 1)


if __name__ == "__main__":
    main()
