"""V27 patient-visible Jev benchmark.

Invariant under test:

    Jev evaluated surface == patient-visible surface == benchmark surface

This runner never concatenates hidden deterministic title/summary/key-points
onto a verified Writer narrative.  It accepts captured ChatResponse JSON records
so the evaluated candidate is the exact runtime object sent to the frontend.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.services.jury_evaluator import jury_panel
from app.services.knowledge_retriever import KnowledgeRetriever
from app.services.patient_visible_response import (
    assert_benchmark_surface_is_patient_visible,
    select_patient_visible_surface,
)


def _records(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("records", "cases", "responses", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError("input must be a list or object containing records/cases/responses/results")


def _runtime_response(item: dict[str, Any]) -> dict[str, Any]:
    response = item.get("response")
    if isinstance(response, dict):
        return response
    # A captured response itself may be the record.
    if "answer" in item and "verification_status" in item:
        return item
    raise ValueError("record is missing captured runtime response")


def evaluate_patient_visible_records(
    input_path: Path,
    output_path: Path | None = None,
) -> dict[str, Any]:
    retriever = KnowledgeRetriever()
    rows = _records(json.loads(input_path.read_text(encoding="utf-8")))

    results: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    passed = 0
    score_total = 0.0

    for index, item in enumerate(rows, 1):
        response = _runtime_response(item)
        surface = select_patient_visible_surface(response)

        case_id = str(item.get("id") or response.get("request_id") or f"v27-visible-{index:04d}")
        question = str(item.get("question") or item.get("prompt") or "").strip()
        intent = str(response.get("intent") or item.get("intent") or "triage")
        result = response.get("result") if isinstance(response.get("result"), dict) else {}

        # Optional capture-side text is accepted only as a cross-check; it may
        # never redefine what the benchmark scores.
        recorded_visible_text = item.get("patient_visible_text")
        if recorded_visible_text is not None:
            assert_benchmark_surface_is_patient_visible(response, str(recorded_visible_text))

        if not surface.text:
            raise ValueError(f"{case_id}: patient-visible surface is empty")

        retrieved = retriever.retrieve(question or surface.text, intent=intent, top_k=3)
        contexts = [entry.content for entry in retrieved]

        red_flags = result.get("red_flags") or []
        urgency = str(result.get("urgency") or result.get("escalation_level") or "ROUTINE")
        scorecard = jury_panel.evaluate(
            evaluation_id=case_id,
            question=question,
            user_intent=intent,
            answer_text=surface.text,
            contexts=contexts,
            locked_claims=[],
            abstains_from_diagnosis=True,
            red_flags_present=bool(red_flags),
            triage_urgency=urgency,
        )

        if scorecard.overall_passed:
            passed += 1
        score_total += scorecard.consensus_score
        source_counts[surface.source] += 1

        results.append(
            {
                "id": case_id,
                "surface_source": surface.source,
                "verification_status": surface.verification_status,
                "safety_urgency": surface.safety_urgency,
                "patient_visible_text": surface.text,
                "scorecard": scorecard.to_dict(),
            }
        )

    total = len(results)
    report = {
        "benchmark": "PATIENT_VISIBLE_RESPONSE_BENCHMARK",
        "invariant": "jev_surface == patient_visible_surface == benchmark_surface",
        "total_cases": total,
        "passed_cases": passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "average_consensus_score": round(score_total / total, 4) if total else 0.0,
        "surface_sources": dict(source_counts),
        "verified_canonical_cases": source_counts.get("canonical_verified_narrative", 0),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score exactly the V27 patient-visible response surface with Jev."
    )
    parser.add_argument("input", type=Path, help="Captured ChatResponse JSON dataset")
    parser.add_argument("--output-json", type=Path, default=None)
    args = parser.parse_args()

    report = evaluate_patient_visible_records(args.input, args.output_json)
    print(
        f"V27 patient-visible benchmark: {report['passed_cases']}/{report['total_cases']} "
        f"passed ({report['pass_rate'] * 100:.1f}%), "
        f"avg={report['average_consensus_score']:.3f}"
    )


if __name__ == "__main__":
    main()
