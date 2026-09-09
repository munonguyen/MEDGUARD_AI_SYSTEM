from pathlib import Path

from scripts.benchmark_mimic_ed import run_mimic_ed_benchmark
from scripts.validate_external_datasets import DATASET_DIR, validate_mimic_demo


def test_mimic_demo_files_match_source_checksums_and_shape():
    result = validate_mimic_demo()

    assert result["valid"] is True
    assert result["checked_files"] == 7
    assert result["triage_rows"] == 222
    assert result["production_evaluable"] is False
    assert result["errors"] == []


def test_mimic_benchmark_is_explicitly_non_production():
    result = run_mimic_ed_benchmark()

    assert result["total_rows"] == 222
    assert result["labeled_rows"] == 207
    assert result["production_evaluable"] is False
    assert 0 <= result["emergency_recall"] <= 1


def test_external_validator_fails_closed_for_missing_dataset(tmp_path: Path):
    result = validate_mimic_demo(tmp_path / "missing")

    assert result["valid"] is False
    assert result["errors"]
    assert DATASET_DIR.name == "mimic-iv-ed-demo-2.2"
