from scripts.prescription_benchmark import run_prescription_benchmark


def test_prescription_ocr_safety_invariant():
    report = run_prescription_benchmark()
    assert report["unsafe_auto_accept_count"] == 0, "CRITICAL: Found unsafe auto-accepted prescription!"
    assert report["safety_invariant_passed"] is True
    assert report["total_test_conditions"] == 10
