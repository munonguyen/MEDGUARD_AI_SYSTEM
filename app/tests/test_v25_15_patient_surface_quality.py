from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _headers(key: str) -> dict[str, str]:
    return {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "X-Consent-Token": "consent-v25-15-quality",
        "Idempotency-Key": key,
    }


def _chat(
    question: str,
    key: str,
    *,
    patient_ref: str | None = None,
    intent_hint: str = "auto",
):
    context = {"patient_ref": patient_ref} if patient_ref else {}
    return client.post(
        "/v1/chat",
        headers=_headers(key),
        json={
            "conversation_id": f"conversation-{key}",
            "messages": [{"role": "user", "content": question}],
            "context": context,
            "intent_hint": intent_hint,
            "locale": "vi-VN",
        },
    )


def _chat_messages(messages: list[dict[str, str]], key: str):
    return client.post(
        "/v1/chat",
        headers=_headers(key),
        json={
            "conversation_id": f"conversation-{key}",
            "messages": messages,
            "locale": "vi-VN",
        },
    )


def test_natural_spo2_sentence_is_parsed_without_needs_information() -> None:
    response = _chat("SpO2 của tôi lúc nghỉ là 95%.", "v25-15-spo2")
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "monitoring"
    assert body["status"] == "answered"
    assert body["extracted"]["metrics"][0]["metric"] == "spo2"
    assert body["extracted"]["metrics"][0]["value"] == 95.0
    assert body["answer"]["next_steps"]
    assert "đo lại" in " ".join(body["answer"]["next_steps"]).lower()


def test_natural_temperature_sentence_is_parsed() -> None:
    response = _chat("Nhiệt độ của tôi là 38.1 độ C.", "v25-15-temp")
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "monitoring"
    assert body["status"] == "answered"
    metrics = body["extracted"]["metrics"]
    assert any(item["metric"] == "temperature_c" and item["value"] == 38.1 for item in metrics)


def test_fever_symptom_remains_owned_by_triage() -> None:
    response = _chat("Tôi đang sốt 40 độ.", "v25-15-fever-triage")
    assert response.status_code == 200
    assert response.json()["intent"] == "triage"


def test_natural_resting_heart_rate_sentence_is_parsed() -> None:
    response = _chat("Nhịp tim nghỉ của tôi khoảng 104 lần/phút.", "v25-15-hr")
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "monitoring"
    assert body["status"] == "answered"
    metrics = body["extracted"]["metrics"]
    assert any(item["metric"] == "heart_rate" and item["value"] == 104.0 for item in metrics)


def test_monitoring_enrichment_does_not_change_authoritative_urgency() -> None:
    response = _chat("SpO2 của tôi lúc nghỉ là 88%.", "v25-15-spo2-emergency")
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["urgency"] == "EMERGENCY"
    assert body["answer"]["display_questions"] == []
    text = " ".join([body["answer"]["summary"], *body["answer"]["next_steps"]]).lower()
    assert "115" in text or "cấp cứu" in text


def test_schedule_answer_exposes_actionable_next_steps_after_real_mutation() -> None:
    response = _chat(
        "Tạo cho tôi một card lịch uống thuốc aspirin mỗi ngày lúc 08:00.",
        "v25-15-card",
        patient_ref="V25-15-CARD-PT",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "schedule"
    assert body["status"] == "answered"
    steps = " ".join(body["answer"]["next_steps"]).lower()
    assert "kiểm tra" in steps
    assert "theo dõi" in steps


def test_safety_needs_information_has_safe_next_action() -> None:
    response = _chat(
        "Tôi muốn kiểm tra một thuốc mới có dùng chung được không.",
        "v25-15-safety-needs-info",
        intent_hint="safety",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "safety"
    assert body["status"] == "needs_information"
    steps = " ".join(body["answer"]["next_steps"]).lower()
    assert "kiểm tra" in steps
    assert "không tự" in steps


def test_amoxicillin_half_tablet_followup_stays_medication_safety() -> None:
    response = _chat_messages(
        [
            {"role": "user", "content": "Tôi từng dị ứng penicillin và bác sĩ vừa kê amoxicillin."},
            {"role": "assistant", "content": "Cần kiểm tra an toàn thuốc trước khi dùng."},
            {"role": "user", "content": "Tôi chưa uống viên amoxicillin nào, có nên thử nửa viên xem sao không?"},
        ],
        "v25-15-amoxicillin-half",
    )
    assert response.status_code == 200
    assert response.json()["intent"] == "safety"


def test_self_induced_vomiting_after_medication_error_stays_safety() -> None:
    response = _chat_messages(
        [
            {"role": "user", "content": "Tôi uống nhầm gấp đôi thuốc của mình và giờ thấy buồn ngủ, hơi chóng mặt."},
            {"role": "assistant", "content": "Không tự dùng thêm thuốc và cần đánh giá nguy cơ dùng nhầm liều."},
            {"role": "user", "content": "Tôi có nên tự gây nôn để đẩy thuốc ra không?"},
        ],
        "v25-15-self-vomit",
    )
    assert response.status_code == 200
    assert response.json()["intent"] == "safety"


def test_explicit_topic_switch_to_warfarin_ibuprofen_does_not_inherit_prior_triage() -> None:
    response = _chat_messages(
        [
            {"role": "user", "content": "Tôi đau đầu nhẹ sau khi nhìn màn hình cả ngày."},
            {"role": "assistant", "content": "Bạn có thể nghỉ màn hình và theo dõi diễn biến."},
            {"role": "user", "content": "Chuyển việc khác: tôi đang dùng warfarin, có dùng ibuprofen được không?"},
        ],
        "v25-15-context-switch-safety",
    )
    assert response.status_code == 200
    assert response.json()["intent"] == "safety"
