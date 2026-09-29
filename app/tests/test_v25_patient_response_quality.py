from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _headers(key: str) -> dict[str, str]:
    return {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "X-Consent-Token": "consent-v25-response-quality",
        "Idempotency-Key": key,
    }


def test_q5_screen_headache_response_explains_mechanism_and_asks_one_high_value_question():
    response = client.post(
        "/v1/chat",
        headers=_headers("v25-q5-screen-headache"),
        json={
            "conversation_id": "v25-q5-screen-headache",
            "messages": [
                {
                    "role": "user",
                    "content": "Tôi đau đầu nhẹ sau khi nhìn màn hình cả ngày.",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "triage"
    assert body["status"] == "answered"
    answer = body["answer"]
    summary = answer["summary"].lower()
    assert "mỏi thị giác" in summary or "điều tiết" in summary
    assert "không phải chẩn đoán" in summary
    assert "chưa biết" in summary
    assert answer["clinical_hypotheses"]
    display_questions = answer.get("display_questions")
    assert display_questions is not None
    assert len(display_questions) == 1
    assert "đột ngột" in display_questions[0].lower()


def test_q6_followup_response_updates_reasoning_instead_of_repeating_q5():
    response = client.post(
        "/v1/chat",
        headers=_headers("v25-q6-delta-reasoning"),
        json={
            "conversation_id": "v25-q6-delta-reasoning",
            "messages": [
                {
                    "role": "user",
                    "content": "Tôi đau đầu nhẹ sau khi nhìn màn hình cả ngày.",
                },
                {
                    "role": "user",
                    "content": "Đau chủ yếu vùng trán, không sốt, nghỉ một lúc thì giảm.",
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "triage"
    answer = body["answer"]
    assert "dữ kiện mới" in answer["summary"].lower()
    display_questions = answer.get("display_questions")
    assert display_questions is not None
    assert len(display_questions) <= 1
    if display_questions:
        assert "sốt" not in display_questions[0].lower()

    trace = (body.get("result") or {}).get("trace") or {}
    v25 = (trace.get("details") or {}).get("v25_contextual_reasoning") or {}
    assert v25.get("applied") is True
    assert v25.get("user_turns") == 2
    assert "fever_neck_stiffness" not in v25.get("unknown_decision_relevant", [])


def test_emergency_headache_remains_action_first_with_zero_display_questions():
    response = client.post(
        "/v1/chat",
        headers=_headers("v25-emergency-action-first"),
        json={
            "conversation_id": "v25-emergency-action-first",
            "messages": [
                {
                    "role": "user",
                    "content": "Vừa rồi tôi đột ngột đau đầu dữ dội nhất từ trước tới giờ.",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert (body.get("result") or {}).get("urgency") == "EMERGENCY"
    answer = body["answer"]
    assert answer.get("display_questions") == []
    full_text = " ".join(
        [answer.get("summary") or ""]
        + list(answer.get("next_steps") or [])
        + list(answer.get("safety_notes") or [])
    ).lower()
    assert "115" in full_text or "cấp cứu" in full_text
