from __future__ import annotations

import json
from pathlib import Path

from scripts.evaluate_medical_response_quality import run_benchmark


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "datasets" / "DS-MEDICAL-RESPONSE-QUALITY" / "dataset.json"


def test_medical_response_quality_dataset_is_isolated_and_complete():
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    metadata = dataset["_meta"]
    cases = dataset["cases"]

    assert metadata["total"] == 40 == len(cases)
    assert metadata["production_evaluable"] is False
    assert metadata["training_allowed"] is False
    assert metadata["expert_review_status"] == "pending"
    assert len({case["case_id"] for case in cases}) == 40
    assert sum(case["critical"] for case in cases) >= 10
    assert sum(dimension["max"] for dimension in metadata["rubric"].values()) == 14
    assert metadata["release_gate"]["maximum_critical_failures"] == 0


def test_original_four_quality_cases_pass_without_a_critical_failure():
    report = run_benchmark({"MRQ-001", "MRQ-002", "MRQ-003", "MRQ-004"})

    assert report["total"] == 4
    assert report["critical_failures"] == 0
    assert report["subthreshold_cases"] == 0
    assert report["average_score"] >= 12
    assert report["p95_latency_ms"] < 10_000
    assert report["gate_passed"] is True

