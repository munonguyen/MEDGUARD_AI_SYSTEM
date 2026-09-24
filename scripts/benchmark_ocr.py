"""Evaluate OCR from real image inputs and independently test catalog matching."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.services.ocr.detector import text_detector
from app.services.ocr.extractor import entity_extractor
from app.services.ocr.matcher import match_medication_to_catalog
from app.services.ocr.preprocessor import preprocess_prescription_image
from app.services.ocr.recognizer import line_recognizer


DS_FILE = BASE_DIR / "datasets" / "DS-OCR" / "dataset.json"


def _edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for row, reference_item in enumerate(reference, start=1):
        current = [row]
        for column, hypothesis_item in enumerate(hypothesis, start=1):
            current.append(
                min(
                    current[column - 1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (reference_item != hypothesis_item),
                )
            )
        previous = current
    return previous[-1]


def calculate_cer(reference: str, hypothesis: str) -> float:
    return _edit_distance(list(reference), list(hypothesis)) / max(1, len(reference))


def calculate_wer(reference: str, hypothesis: str) -> float:
    reference_words = reference.split()
    return _edit_distance(reference_words, hypothesis.split()) / max(1, len(reference_words))


def run_ocr_benchmark() -> dict[str, Any]:
    data = json.loads(DS_FILE.read_text(encoding="utf-8"))
    cases = data["cases"]
    cer_scores: list[float] = []
    wer_scores: list[float] = []
    missing_images = 0
    pipeline_failures = 0
    catalog_matches = 0
    catalog_correct = 0

    for case in cases:
        for medication in case["ground_truth_medications"]:
            match = match_medication_to_catalog(medication["name"], medication.get("strength"))
            product = match["matched_product"]
            if product is not None:
                catalog_matches += 1
                expected_name = medication["name"].lower().replace(" ", "")
                expected_ingredient = medication.get("active_ingredient", "").lower().replace(" ", "")
                product_name = product["product_name"].lower().replace(" ", "")
                product_ingredient = product["active_ingredient"].lower().replace(" ", "")
                if expected_name in product_name or (
                    expected_ingredient and expected_ingredient in product_ingredient
                ):
                    catalog_correct += 1

        image_path = BASE_DIR / case["mock_image_path"]
        if not image_path.is_file():
            missing_images += 1
            continue

        try:
            image_bytes = image_path.read_bytes()
            preprocessed = preprocess_prescription_image(image_bytes)
            if not preprocessed.is_valid:
                pipeline_failures += 1
                continue
            boxes = text_detector.detect_boxes(image_bytes)
            lines = line_recognizer.recognize_lines(image_bytes, boxes)
        except Exception:
            pipeline_failures += 1
            continue

        reference = " ".join(case["ground_truth_lines"])
        hypothesis = " ".join(line.text for line in lines)
        cer_scores.append(calculate_cer(reference, hypothesis))

        reference_names = " ".join(item["name"] for item in case["ground_truth_medications"])
        recognized_names = " ".join(
            medication.medicine_name
            for medication in entity_extractor.extract_medications(image_bytes, lines)
        )
        wer_scores.append(calculate_wer(reference_names, recognized_names))

    evaluable_cases = len(cer_scores)
    average_cer = sum(cer_scores) / evaluable_cases if evaluable_cases else None
    average_wer = sum(wer_scores) / len(wer_scores) if wer_scores else None
    catalog_precision = catalog_correct / catalog_matches if catalog_matches else None
    ocr_evaluable = evaluable_cases > 0

    return {
        "total_cases": len(cases),
        "evaluable_cases": evaluable_cases,
        "missing_images": missing_images,
        "pipeline_failures": pipeline_failures,
        "ocr_status": "evaluated" if ocr_evaluable else "not_evaluable",
        "average_cer": round(average_cer, 4) if average_cer is not None else None,
        "average_wer": round(average_wer, 4) if average_wer is not None else None,
        "catalog_matches": catalog_matches,
        "catalog_precision": round(catalog_precision, 4) if catalog_precision is not None else None,
        "cer_passed": bool(ocr_evaluable and average_cer is not None and average_cer <= 0.10),
        "wer_passed": bool(ocr_evaluable and average_wer is not None and average_wer <= 0.15),
        "precision_passed": bool(catalog_precision is not None and catalog_precision >= 0.98),
    }


def _percent(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:.2f}%"


if __name__ == "__main__":
    results = run_ocr_benchmark()
    print("=== DS-OCR BENCHMARK RESULTS ===")
    print(f"Dataset cases: {results['total_cases']}")
    print(f"Evaluable image cases: {results['evaluable_cases']}")
    print(f"Missing images: {results['missing_images']}")
    print(f"Pipeline failures: {results['pipeline_failures']}")
    print(f"OCR status: {results['ocr_status'].upper()}")
    print(f"Average CER: {_percent(results['average_cer'])}")
    print(f"Average WER: {_percent(results['average_wer'])}")
    print(f"Catalog matcher precision: {_percent(results['catalog_precision'])}")
