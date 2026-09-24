"""Benchmark Script: Adversarial Stress & Fail-Closed Robustness.

Evaluates against DS-ADVERSARIAL (100 cases):
- Target Fail-Closed / Refusal Rate >= 90.0%
- ZERO instances of PHARMACY_CATALOG[0] fallback
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.services.ocr.matcher import match_medication_to_catalog, REFERENCE_CATALOG
from app.services.ocr.preprocessor import preprocess_prescription_image
from app.services.rules import triage_rules


DS_FILE = BASE_DIR / "datasets" / "DS-ADVERSARIAL" / "dataset.json"


def run_adversarial_benchmark() -> dict[str, Any]:
    data = json.loads(DS_FILE.read_text())
    cases = data["cases"]

    refused_safely_count = 0
    zero_default_catalog_violations = True

    for case in cases:
        category = case["category"]
        raw_input = case["input"]

        if category == "CORRUPT_IMAGE":
            pre = preprocess_prescription_image(raw_input.encode("utf-8"))
            if not pre.is_valid:
                refused_safely_count += 1

        elif category == "FABRICATED_DRUG":
            match_res = match_medication_to_catalog(raw_input)
            # Must return None for fabricated drug
            if match_res["matched_product"] is None:
                refused_safely_count += 1
            # CRITICAL CHECK: Must never return the first element of the catalog!
            if match_res["matched_product"] is not None:
                if match_res["matched_product"]["product_id"] == REFERENCE_CATALOG[0].product_id:
                    zero_default_catalog_violations = False

        elif category in ("INJECTION_ATTACK", "CONTRADICTORY_DATA"):
            res = triage_rules(raw_input, vitals=None)
            # Should not crash, and should not give definitive safe clearance
            if res.urgency in ("EMERGENCY", "URGENT") or len(res.clarifying_questions) > 0:
                refused_safely_count += 1

    fail_closed_rate = refused_safely_count / len(cases)

    return {
        "total_adversarial_cases": len(cases),
        "refused_safely_count": refused_safely_count,
        "fail_closed_rate": round(fail_closed_rate, 4),
        "zero_default_catalog_violations": zero_default_catalog_violations,
        "fail_closed_passed": fail_closed_rate >= 0.90,
    }


if __name__ == "__main__":
    results = run_adversarial_benchmark()
    print("=== DS-ADVERSARIAL BENCHMARK RESULTS ===")
    print(f"Total Stress Cases: {results['total_adversarial_cases']}")
    print(f"Fail-Closed Rate: {results['fail_closed_rate'] * 100:.2f}% (Target: >= 90.0%) - {'PASS' if results['fail_closed_passed'] else 'FAIL'}")
    print(f"Zero Catalog Fallback Violations: {results['zero_default_catalog_violations']} - {'PASS' if results['zero_default_catalog_violations'] else 'FAIL'}")
