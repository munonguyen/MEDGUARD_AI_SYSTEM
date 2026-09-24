import json

from blind_v10.freeze_guard import MANIFEST_PATH, verify_freeze_integrity


def test_v10_freeze_requires_and_records_passing_preblind_gates():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["status"] == "FROZEN_FOR_INDEPENDENT_BLIND_V10_ONE_SHOT_VALIDATION"
    assert manifest["blind_v10_executed"] is False
    assert manifest["clinical_generalization_confirmed"] is False
    assert len(manifest["candidate_core_commit"]) == 40
    assert len(manifest["blind_frozen_commit"]) == 40
    assert len(manifest["freeze_manifest_sha256"]) == 64
    assert len(manifest["regression_report_sha256"]) == 64
    assert len(manifest["mechanism_benchmark_sha256"]) == 64
    assert manifest["pre_blind_gates"]["mechanism_cases"] == 180
    assert manifest["pre_blind_gates"]["regression_cases"] == 2400
    assert manifest["pre_blind_gates"]["pure_t4_to_urgent"] == 0
    assert manifest["pre_blind_gates"]["pure_t4_to_routine"] == 0
    assert all(manifest["jev_gate3_preserved_from_v9"].values())
    ok, errors = verify_freeze_integrity()
    assert ok, errors
