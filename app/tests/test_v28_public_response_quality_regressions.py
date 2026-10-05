from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _headers(case_id: str) -> dict[str, str]:
    return {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "Idempotency-Key": f"v28-quality-{case_id}",
        "X-Consent-Token": "consent-v28-quality",
    }


def _chat(question: str, case_id: str) -> dict:
    response = client.post(
        "/v1/chat",
        headers=_headers(case_id),
        json={
            "conversation_id": f"v28-quality-{case_id}",
            "messages": [{"role": "user", "content": question}],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _visible_text(body: dict) -> str:
    answer = body.get("answer") or {}
    narrative = " ".join(block.get("text", "") for block in answer.get("narrative") or [])
    return " ".join(
        str(value)
        for value in (
            body.get("reply", ""),
            answer.get("title", ""),
            answer.get("summary", ""),
            narrative,
        )
    ).lower()


def test_therapeutic_paracetamol_plus_ibuprofen_question_is_not_fabricated_as_overdose():
    body = _chat(
        "Tôi uống paracetamol nhưng vẫn sốt. Tôi có thể uống thêm ibuprofen không?",
        "therapeutic-paracetamol",
    )
    text = _visible_text(body)

    assert body["intent"] == "safety"
    assert "báo cáo quá liều" not in text
    assert "uống nhầm thuốc chưa xác định" not in text
    result = body.get("result") or {}
    assert not (result.get("dose_assessment") or {}).get("risk_level")


def test_negated_exposure_list_does_not_create_toxic_inhalation_in_public_answer():
    body = _chat(
        "Tôi hơi khó thở nhưng không tiếp xúc hóa chất, chất tẩy rửa hay khí độc",
        "negated-exposure-list",
    )
    # The pre-existing dyspnea safety rule still independently escalates this
    # request. This regression only prevents fabricated chemical exposure;
    # it must not silently weaken that separate clinical safety policy.
    result = body.get("result") or {}
    assert "toxic_inhalation_dyspnea" not in (result.get("red_flags") or [])
    text = _visible_text(body)
    assert "phơi nhiễm hơi/khí hóa chất được xác nhận" not in text


def test_alt_question_gets_bounded_lab_explanation_not_generic_fallback():
    body = _chat(
        "Xét nghiệm máu của tôi có ALT cao. Điều đó có nghĩa là tôi bị bệnh gan không?",
        "alt-high",
    )
    text = _visible_text(body)
    result = body.get("result") or {}

    assert body["intent"] == "general"
    assert result.get("clinical_task") == "LAB_INTERPRETATION"
    assert result.get("confidence", 0) >= 0.60
    assert "alt" in text
    assert "không đồng nghĩa" in text or "không đủ" in text
    assert "bệnh gan" in text


def test_fasting_glucose_question_gets_confirmation_language_not_definitive_diagnosis():
    body = _chat(
        "Đường huyết lúc đói của tôi là 7,2 mmol/L. Có phải tôi bị tiểu đường không?",
        "fasting-glucose",
    )
    text = _visible_text(body)
    result = body.get("result") or {}

    assert body["intent"] == "general"
    assert result.get("clinical_task") == "LAB_INTERPRETATION"
    assert result.get("urgency") == "ROUTINE"
    assert result.get("confidence", 0) >= 0.80
    assert "7,0" in text
    assert "xác nhận" in text
    assert "không" in text and "chẩn đoán" in text
