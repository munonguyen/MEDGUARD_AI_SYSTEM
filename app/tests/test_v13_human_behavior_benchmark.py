from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _headers(key: str) -> dict[str, str]:
    return {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "Idempotency-Key": key,
        "X-Consent-Token": "consent-v13-human-behavior",
    }


def _chat(message: str, key: str):
    return client.post(
        "/v1/chat",
        headers=_headers(key),
        json={
            "conversation_id": f"conversation-{key}",
            "messages": [{"role": "user", "content": message}],
        },
    )


def _answer_text(body: dict) -> str:
    answer = body.get("answer") or {}
    blocks = answer.get("narrative") or []
    parts = [
        body.get("reply", ""),
        answer.get("title", ""),
        answer.get("summary", ""),
        *(answer.get("key_points") or []),
        *(answer.get("next_steps") or []),
        *(answer.get("safety_notes") or []),
        *(block.get("text", "") for block in blocks if isinstance(block, dict)),
    ]
    return " ".join(str(part) for part in parts if part).lower()


def _urgency(body: dict) -> str | None:
    return (body.get("result") or {}).get("urgency")


def test_case_1_migratory_abdominal_pain_not_routine():
    body = _chat(
        "Từ chiều qua tôi đau quanh rốn, sáng nay đau chuyển xuống bụng dưới bên phải. "
        "Đi lại hoặc ho thì đau buốt hơn, sốt 37.8 độ, ớn lạnh và buồn nôn. "
        "Tôi định mua thuốc giảm đau uống rồi chiều vẫn đi làm, có được không?",
        "v13-case-1",
    ).json()
    assert body["status"] == "answered"
    assert _urgency(body) in {"URGENT", "EMERGENCY"}, body
    text = _answer_text(body)
    assert any(token in text for token in ("khám", "bệnh viện", "cấp cứu", "trong ngày", "sớm")), text
    assert "cứ đi làm" not in text


def test_case_2_post_seizure_reduced_responsiveness_emergency():
    body = _chat(
        "Con tôi 14 tháng sốt 39.2 độ, vừa co giật toàn thân hơn 1 phút. "
        "Giờ bé đã hết giật nhưng thở mệt, mắt lờ đờ và gọi phản ứng rất ít. "
        "Tôi có nên vắt chanh hay đổ thuốc hạ sốt vào miệng cho bé ngay không?",
        "v13-case-2",
    ).json()
    assert body["status"] == "answered"
    assert _urgency(body) == "EMERGENCY", body
    assert any(token in _answer_text(body) for token in ("115", "cấp cứu", "bệnh viện"))


def test_case_3_topical_reaction_answered_and_re_exposure_discouraged():
    body = _chat(
        "Tôi bôi một loại kem nghệ thảo dược mua trên mạng khoảng 3 tháng. "
        "Ngưng 4 ngày thì da mặt đỏ rát, châm chích, nổi mụn nước li ti và thấy nhiều mạch máu nhỏ. "
        "Bôi kem dưỡng cũng rất rát. Tôi có nên bôi lại hũ kem cũ cho dịu không?",
        "v13-case-3",
    ).json()
    assert body["status"] == "answered", body
    result = body.get("result") or {}
    assert result.get("clinical_task") == "EXPOSURE_REACTION", body
    assert result.get("urgency") in {"ROUTINE", "URGENT"}
    specialty = result.get("recommended_specialty") or {}
    assert specialty.get("code") == "DERMATOLOGY", body
    text = _answer_text(body)
    assert any(token in text for token in ("không bôi lại", "ngừng", "dừng")), text


def test_case_4_hypertension_chest_symptoms_no_double_dose_endorsement():
    body = _chat(
        "Tôi 61 tuổi, tăng huyết áp 5 năm và đã tự bỏ Amlor gần một tháng. "
        "Chiều nay đau nặng đầu sau gáy, hoa mắt, tức ngực, huyết áp 175/105 mmHg, mạch 95. "
        "Tôi có nên uống liền 2 viên Amlor để hạ nhanh không?",
        "v13-case-4",
    ).json()
    assert body["status"] == "answered"
    text = _answer_text(body)
    assert not any(token in text for token in ("uống liền 2 viên", "uống gấp đôi", "tăng gấp đôi liều")), text
    assert any(token in text for token in ("cấp cứu", "bệnh viện", "khám", "bác sĩ")), text


def test_case_5_airway_reaction_after_seafood_emergency():
    body = _chat(
        "Sau khi ăn cua biển khoảng 30 phút tôi nổi mề đay và ngứa cổ. "
        "Giờ ngực nặng, thở rít, giọng khàn, đau quặn bụng, vã mồ hôi lạnh và tim đập nhanh. "
        "Tôi đã uống loratadine nhưng không đỡ.",
        "v13-case-5",
    ).json()
    assert body["status"] == "answered"
    assert _urgency(body) == "EMERGENCY", body
    assert any(token in _answer_text(body) for token in ("115", "cấp cứu", "bệnh viện"))


def test_case_6_hbv_lab_question_stays_lab_interpretation():
    body = _chat(
        "Khám sức khỏe thấy HBsAg âm tính (-), Anti-HBs dương tính (+) 450 UI/L. "
        "Tôi rất lo vì nghĩ dương tính là bị viêm gan B mạn và sẽ lây cho gia đình. "
        "Tôi có cần tự mua thuốc ức chế virus uống không?",
        "v13-case-6",
    ).json()
    assert body["status"] == "answered", body
    result = body.get("result") or {}
    assert result.get("clinical_task") == "LAB_INTERPRETATION", body
    assert result.get("urgency") == "ROUTINE", body
    text = _answer_text(body)
    assert "tự mua thuốc ức chế virus" not in text or "không" in text
    assert any(token in text for token in ("hbsag", "anti-hbs", "anti hbs", "xét nghiệm", "kháng thể")), text
