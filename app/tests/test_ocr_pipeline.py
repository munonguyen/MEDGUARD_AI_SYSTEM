"""Safety and orchestration tests for the prescription OCR boundary."""

import base64

import pytest

from app.services.ocr.detector import TextBox, text_detector
from app.services.ocr.errors import OcrPipelineError
from app.services.ocr.extractor import entity_extractor
from app.services.ocr.matcher import REFERENCE_CATALOG, match_medication_to_catalog
from app.services.ocr.preprocessor import preprocess_prescription_image
from app.services.ocr.recognizer import RecognizedLine, line_recognizer
from app.workers.ocr_worker import run_vision_pipeline


VALID_PNG = (
    base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==")
)


def test_stage_1_preprocessor_rejects_invalid_content():
    preprocessed = preprocess_prescription_image(VALID_PNG)
    assert preprocessed.is_valid is True
    assert preprocessed.format == "image/png"
    assert (preprocessed.width, preprocessed.height) == (1, 1)

    corrupt = preprocess_prescription_image(b"invalid_data_here")
    assert corrupt.is_valid is False
    assert corrupt.error_message == "invalid_image"


def test_detector_and_recognizer_fail_closed_without_engines(monkeypatch):
    monkeypatch.setattr(text_detector, "_paddle_ocr", None)
    with pytest.raises(OcrPipelineError, match="ocr_detector_unavailable"):
        text_detector.detect_boxes(VALID_PNG)

    monkeypatch.setattr(line_recognizer, "_predictor", None)
    boxes = [TextBox(box_id=0, bbox=[0, 0, 1, 1], confidence=0.9, line_index=0)]
    with pytest.raises(OcrPipelineError, match="ocr_recognizer_unavailable"):
        line_recognizer.recognize_lines(VALID_PNG, boxes)


def test_entity_extractor_keeps_unknown_fields_null():
    lines = [
        RecognizedLine(0, "1. Augmentin 1g", 0.94, [0, 0, 1, 1]),
        RecognizedLine(1, "Theo huong dan cua bac si", 0.92, [0, 0, 1, 1]),
    ]
    medications = entity_extractor.extract_medications(VALID_PNG, lines)
    assert len(medications) == 1
    medication = medications[0]
    assert medication.medicine_name == "Augmentin"
    assert medication.active_ingredient is None
    assert medication.route is None
    assert medication.frequency is None
    assert medication.duration_days is None


def test_catalog_matcher_exact_fuzzy_and_fail_closed():
    exact = match_medication_to_catalog("Augmentin 1g")
    assert exact["matched_product"]["product_id"] == "PROD-001"
    assert exact["match_type"] == "EXACT"

    fuzzy = match_medication_to_catalog("Augmentin 1 g")
    assert fuzzy["matched_product"]["product_id"] == "PROD-001"
    assert fuzzy["similarity_score"] >= 0.85

    no_match = match_medication_to_catalog("Thuoc Bia Dat XYZ123")
    assert no_match["matched_product"] is None
    assert no_match["match_type"] == "NO_MATCH_FAIL_CLOSED"
    assert no_match["requires_manual_confirmation"] is True
    assert no_match["matched_product"] != REFERENCE_CATALOG[0]


def test_pipeline_orchestration_with_explicit_test_doubles(monkeypatch):
    boxes = [
        TextBox(0, [0, 0, 1, 1], 0.95, 0),
        TextBox(1, [0, 0, 1, 1], 0.95, 1),
    ]
    lines = [
        RecognizedLine(0, "1. Augmentin 1g", 0.94, [0, 0, 1, 1]),
        RecognizedLine(1, "Uong 1 vien x 2 lan/ngay trong 7 ngay", 0.92, [0, 0, 1, 1]),
    ]
    monkeypatch.setattr(text_detector, "_paddle_ocr", object())
    monkeypatch.setattr(line_recognizer, "_predictor", object())
    monkeypatch.setattr(text_detector, "detect_boxes", lambda _: boxes)
    monkeypatch.setattr(line_recognizer, "recognize_lines", lambda _image, _boxes: lines)

    result = run_vision_pipeline(VALID_PNG)
    assert result["review_status"] == "PENDING_REVIEW"
    assert len(result["stages_executed"]) == 4
    assert len(result["extracted_medications"]) == 1
    assert result["requires_human_pharmacist_review"] is True


def test_full_pipeline_fails_when_engines_are_unavailable(monkeypatch):
    monkeypatch.setattr(text_detector, "_paddle_ocr", None)
    monkeypatch.setattr(line_recognizer, "_predictor", None)
    with pytest.raises(OcrPipelineError, match="ocr_worker_unavailable"):
        run_vision_pipeline(VALID_PNG)


def test_pipeline_fails_when_no_medication_is_detected(monkeypatch):
    boxes = [TextBox(0, [0, 0, 1, 1], 0.95, 0)]
    lines = [RecognizedLine(0, "Phong kham da khoa", 0.94, [0, 0, 1, 1])]
    monkeypatch.setattr(text_detector, "_paddle_ocr", object())
    monkeypatch.setattr(line_recognizer, "_predictor", object())
    monkeypatch.setattr(text_detector, "detect_boxes", lambda _: boxes)
    monkeypatch.setattr(line_recognizer, "recognize_lines", lambda _image, _boxes: lines)

    with pytest.raises(OcrPipelineError, match="ocr_no_medications_detected"):
        run_vision_pipeline(VALID_PNG)
