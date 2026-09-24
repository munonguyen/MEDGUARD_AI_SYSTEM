"""Benchmark Script: Medication Safety Checks (Interactions & Allergies).

Evaluates against:
- DS-INTERACT (500 pairs): Target Interaction Recall >= 0.95, Precision >= 0.85
- DS-ALLERGY (200 pairs): Target Allergy Recall >= 0.98
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.models.safety import Allergy, MedicationItem, SafetyRequest
from app.services.rules import safety_rules
DS_INTERACT_FILE = BASE_DIR / "datasets" / "DS-INTERACT" / "dataset.json"
DS_ALLERGY_FILE = BASE_DIR / "datasets" / "DS-ALLERGY" / "dataset.json"


def run_interaction_benchmark() -> dict[str, float]:
    data = json.loads(DS_INTERACT_FILE.read_text())
    pairs = data["pairs"]

    tp = 0
    fp = 0
    fn = 0
    tn = 0

    for item in pairs:
        drug_a = item["drug_a"]
        drug_b = item["drug_b"]
        expected_interaction = item["has_interaction"]

        req = SafetyRequest(
            patient_ref="test-patient",
            current_medications=[MedicationItem(name=drug_a, active_ingredient=drug_a)],
            proposed_medications=[MedicationItem(name=drug_b, active_ingredient=drug_b)],
        )
        res = safety_rules(req)
        detected = any(w["type"] == "DRUG_DRUG_INTERACTION" for w in res.warnings)

        if expected_interaction and detected:
            tp += 1
        elif expected_interaction and not detected:
            fn += 1
        elif not expected_interaction and detected:
            fp += 1
        else:
            tn += 1

    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0

    return {
        "total_pairs": len(pairs),
        "true_positives": tp,
        "false_negatives": fn,
        "false_positives": fp,
        "true_negatives": tn,
        "interaction_recall": round(recall, 4),
        "interaction_precision": round(precision, 4),
        "recall_passed": recall >= 0.95,
        "precision_passed": precision >= 0.85,
    }


def run_allergy_benchmark() -> dict[str, float]:
    data = json.loads(DS_ALLERGY_FILE.read_text())
    cases = data["cases"]

    tp = 0
    fn = 0
    fp = 0
    tn = 0

    for case in cases:
        allergy = case["patient_allergy"]
        prescribed = case["prescribed_drug"]
        expected_conflict = case["has_allergy_conflict"]

        req = SafetyRequest(
            patient_ref="test-allergy",
            allergies=[Allergy(substance=allergy, severity="HIGH")],
            proposed_medications=[MedicationItem(name=prescribed, active_ingredient=prescribed)],
        )
        res = safety_rules(req)
        detected = any(w["type"] in ("ALLERGY_CROSS_REACTIVITY", "ALLERGY_PARTIAL_CROSS_REACTIVITY") for w in res.warnings)

        if expected_conflict and detected:
            tp += 1
        elif expected_conflict and not detected:
            fn += 1
        elif not expected_conflict and detected:
            fp += 1
        else:
            tn += 1

    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0

    return {
        "total_cases": len(cases),
        "true_positives": tp,
        "false_negatives": fn,
        "allergy_recall": round(recall, 4),
        "recall_passed": recall >= 0.98,
    }


if __name__ == "__main__":
    int_res = run_interaction_benchmark()
    all_res = run_allergy_benchmark()

    print("=== DS-INTERACT BENCHMARK RESULTS ===")
    print(f"Total Pairs: {int_res['total_pairs']}")
    print(f"Recall: {int_res['interaction_recall'] * 100:.2f}% (Target: >= 95.0%) - {'PASS' if int_res['recall_passed'] else 'FAIL'}")
    print(f"Precision: {int_res['interaction_precision'] * 100:.2f}% (Target: >= 85.0%) - {'PASS' if int_res['precision_passed'] else 'FAIL'}")

    print("\n=== DS-ALLERGY BENCHMARK RESULTS ===")
    print(f"Total Cases: {all_res['total_cases']}")
    print(f"Allergy Recall: {all_res['allergy_recall'] * 100:.2f}% (Target: >= 98.0%) - {'PASS' if all_res['recall_passed'] else 'FAIL'}")
