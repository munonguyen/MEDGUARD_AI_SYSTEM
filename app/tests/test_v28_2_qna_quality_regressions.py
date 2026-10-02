"""Regression tests derived from human review of the 40-case Q&A audit.

These tests intentionally protect patient-facing quality defects that can pass a
coarse aggregate score: task misrouting and cross-template contamination.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.knowledge.loader import knowledge
from app.main import app
from app.models.clinical_task import ClinicalTask
from app.services.clinical_task_router import resolve_clinical_task


def _chat(prompt: str, key: str) -> dict:
    client = TestClient(app)
    with patch("app.services.chat.background_agent_runner.submit", return_value=False), patch(
        "app.services.chat.active_learning_store.capture_case", return_value=None
    ):
        response = client.post(
            "/v1/chat",
            headers={
                "X-API-Key": "demo-key",
                "X-Tenant-Id": "tenant-demo",
                "X-Consent-Token": "consent-v28-qna-regression",
                "Idempotency-Key": key,
            },
            json={
                "conversation_id": key,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
    assert response.status_code == 200
    return response.json()


def _answer_text(body: dict) -> str:
    answer = body.get("answer") or {}
    values: list[str] = []
    for key in (
        "title", "summary", "clinical_hypotheses", "key_points", "next_steps",
        "safety_notes", "questions", "limitations",
    ):
        value = answer.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif value:
            values.append(str(value))
    return " ".join(values).lower()


def test_testing_advice_without_results_is_not_lab_interpretation() -> None:
    decision = resolve_clinical_task(
        "Tôi thường xuyên mệt mỏi dù ngủ đủ. Tôi có nên đi xét nghiệm không?"
    )
    assert decision.task == ClinicalTask.ACUTE_SYMPTOM


def test_actual_alt_result_stays_lab_interpretation() -> None:
    decision = resolve_clinical_task(
        "Xét nghiệm máu của tôi có ALT cao. Điều đó có nghĩa là gì?"
    )
    assert decision.task == ClinicalTask.LAB_INTERPRETATION


def test_sleep_medication_question_is_classified_as_medication_safety_work() -> None:
    decision = resolve_clinical_task(
        "Tôi mất ngủ gần một tuần rồi. Tôi có nên dùng thuốc ngủ không?"
    )
    assert decision.task == ClinicalTask.MEDICATION_SAFETY


def test_persistent_fatigue_chat_no_longer_asks_for_lab_result_fields() -> None:
    body = _chat(
        "Tôi thường xuyên mệt mỏi dù ngủ đủ. Tôi có nên đi xét nghiệm không?",
        "v28-qna-fatigue-routing",
    )
    text = _answer_text(body)
    assert body["intent"] in {"triage", "followup"}
    assert "diễn giải xét nghiệm" not in text
    assert "tên xét nghiệm, giá trị" not in text
    assert any(marker in text for marker in ("đánh giá", "đi khám", "bác sĩ", "nguyên nhân"))


def test_animal_bite_bypasses_generic_symptom_templates() -> None:
    guidance = knowledge.find_symptom_guidance(
        "Tôi vừa bị chó cắn vào chân và có chảy máu. Tôi có cần tiêm phòng không?"
    )
    assert guidance is None or guidance.get("topic") in {"animal_bite", "rabies_exposure"}


def test_dog_bite_answer_has_no_foreign_injury_template_leakage() -> None:
    body = _chat(
        "Tôi vừa bị chó cắn và có chảy máu. Tôi có cần tiêm phòng không?",
        "v28-qna-rabies-context-isolation",
    )
    text = _answer_text(body)
    leaked_templates = (
        "dao rọc giấy",
        "mép giấy",
        "mảnh kính",
        "kéo",
        "nước sôi",
        "bọng nước",
        "kem đánh răng",
        "mỡ trăn",
        "tác nhân gây bỏng",
        "vùng da bị bỏng",
        "sơ cứu bỏng",
    )
    for leaked in leaked_templates:
        assert leaked not in text
    assert any(marker in text for marker in ("bệnh dại", "tiêm", "vắc xin", "vaccine"))


def test_bp_145_95_is_explained_as_high_without_emergency_overtriage() -> None:
    body = _chat(
        "Huyết áp của tôi là 145/95 mmHg. Con số này có ý nghĩa gì?",
        "v28-qna-bp-145-95",
    )
    text = _answer_text(body)
    assert body["intent"] == "monitoring"
    assert (body.get("result") or {}).get("urgency") == "ROUTINE"
    assert (body.get("result") or {}).get("escalation_level") == "CLINIC"
    assert "stage 2" in text
    assert "một lần đo chưa đủ" in text
    assert any(marker in text for marker in ("đo lại", "nhân viên y tế", "cơ sở y tế"))


def test_orthostatic_dizziness_answer_preserves_uncertainty_and_no_default_sugar() -> None:
    body = _chat(
        "Tôi bị chóng mặt mỗi khi đứng dậy. Nguyên nhân có thể là gì?",
        "v28-qna-orthostatic-dizziness",
    )
    text = _answer_text(body)
    assert body["intent"] == "triage"
    assert any(marker in text for marker in ("nhiều nguyên nhân", "chưa đủ", "có thể liên quan"))
    assert "uống một cốc nước ấm có chút đường" not in text
    assert "không mặc định uống đường" in text
    assert any(marker in text for marker in ("ngồi", "nằm", "tránh té", "đứng dậy từ từ"))


def test_sleep_medication_answer_directly_discourages_unsupervised_hypnotics() -> None:
    body = _chat(
        "Tôi mất ngủ gần một tuần rồi. Tôi có nên dùng thuốc ngủ không?",
        "v28-qna-sleep-medication",
    )
    text = _answer_text(body)
    assert "không nên tự bắt đầu thuốc ngủ" in text or "không tự bắt đầu thuốc ngủ" in text
    assert any(marker in text for marker in ("bác sĩ", "dược sĩ", "tương tác"))
    assert any(marker in text for marker in ("giờ ngủ", "caffeine", "màn hình"))


def test_hypertension_education_answers_control_question_not_generic_triage() -> None:
    body = _chat(
        "Bác sĩ bảo tôi bị tăng huyết áp. Bệnh này có chữa khỏi hoàn toàn được không?",
        "v28-qna-hypertension-education",
    )
    text = _answer_text(body)
    assert "kiểm soát lâu dài" in text
    assert any(marker in text for marker in ("không tự ngừng thuốc", "trước khi giảm liều", "trước khi ngừng thuốc"))
    assert any(marker in text for marker in ("theo dõi huyết áp", "nhật ký đo", "lối sống"))
