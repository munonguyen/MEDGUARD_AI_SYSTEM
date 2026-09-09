"""Benchmark Script: Clinical Triage & ESI Classification.

Evaluates against DS-TRIAGE (200 cases):
- Target Cohen's kappa (κ) >= 0.70
- Target Under-triage rate (downgraded >= 2 levels) <= 1.0%
- Emergency detection recall >= 98.0%
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.services.rules import triage_rules
DS_FILE = BASE_DIR / "datasets" / "DS-TRIAGE" / "dataset.json"


def compute_cohens_kappa(actual: list[int], predicted: list[int]) -> float:
    """Computes unweighted Cohen's kappa for multi-class agreement."""
    n = len(actual)
    if n == 0:
        return 1.0

    categories = sorted(list(set(actual + predicted)))
    k = len(categories)
    cat_to_idx = {cat: i for i, cat in enumerate(categories)}

    # Build confusion matrix
    matrix = [[0] * k for _ in range(k)]
    for a, p in zip(actual, predicted):
        matrix[cat_to_idx[a]][cat_to_idx[p]] += 1

    # Observed agreement
    p_o = sum(matrix[i][i] for i in range(k)) / n

    # Expected agreement by chance
    row_sums = [sum(matrix[i][j] for j in range(k)) for i in range(k)]
    col_sums = [sum(matrix[i][j] for i in range(k)) for j in range(k)]
    p_e = sum((row_sums[i] * col_sums[i]) for i in range(k)) / (n * n)

    if p_e == 1.0:
        return 1.0
    return (p_o - p_e) / (1.0 - p_e)


def run_triage_benchmark() -> dict[str, float]:
    data = json.loads(DS_FILE.read_text())
    cases = data["cases"]

    actual_esi = []
    predicted_esi = []
    severe_undertriage_count = 0
    emergency_actual_count = 0
    emergency_detected_count = 0

    for case in cases:
        gt_esi = case["ground_truth_esi"]
        actual_esi.append(gt_esi)

        rule_res = triage_rules(
            symptoms_text=case["symptoms_text"],
            vitals=None,
        )

        pred_esi = rule_res.esi_level or (2 if rule_res.urgency == "EMERGENCY" else 3 if rule_res.urgency == "URGENT" else 4)
        predicted_esi.append(pred_esi)

        # Severe under-triage check: evaluated >= 2 levels less urgent than ground truth
        # In ESI: 1 is most urgent, 5 is least. So pred - actual >= 2 means under-triaged
        if (pred_esi - gt_esi) >= 2:
            severe_undertriage_count += 1

        if gt_esi in (1, 2):
            emergency_actual_count += 1
            if rule_res.urgency == "EMERGENCY" or pred_esi in (1, 2):
                emergency_detected_count += 1

    kappa = compute_cohens_kappa(actual_esi, predicted_esi)
    undertriage_rate = severe_undertriage_count / len(cases)
    emergency_recall = emergency_detected_count / emergency_actual_count if emergency_actual_count > 0 else 1.0

    return {
        "total_cases": len(cases),
        "cohens_kappa": round(kappa, 4),
        "undertriage_rate": round(undertriage_rate, 4),
        "emergency_recall": round(emergency_recall, 4),
        "kappa_passed": kappa >= 0.70,
        "undertriage_passed": undertriage_rate <= 0.01,
        "emergency_recall_passed": emergency_recall >= 0.98,
    }


if __name__ == "__main__":
    results = run_triage_benchmark()
    print("=== DS-TRIAGE BENCHMARK RESULTS ===")
    print(f"Total Cases: {results['total_cases']}")
    print(f"Cohen's kappa (κ): {results['cohens_kappa']:.3f} (Target: >= 0.70) - {'PASS' if results['kappa_passed'] else 'FAIL'}")
    print(f"Under-triage Rate: {results['undertriage_rate'] * 100:.2f}% (Target: <= 1.0%) - {'PASS' if results['undertriage_passed'] else 'FAIL'}")
    print(f"Emergency Recall: {results['emergency_recall'] * 100:.2f}% (Target: >= 98.0%) - {'PASS' if results['emergency_recall_passed'] else 'FAIL'}")
