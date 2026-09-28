from __future__ import annotations

from scripts.benchmark_professional_response import run_professional_response_benchmark


def test_professional_response_release_benchmark_has_zero_classification_errors() -> None:
    report = run_professional_response_benchmark()

    assert report["total"] >= 10
    assert report["accuracy"] == 1.0
    assert report["false_accepts"] == []
    assert report["false_rejects"] == []
    assert report["critical_failures"] == []
    assert report["average_good_score"] >= 0.95
    assert report["gate_passed"] is True
