from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _headers(key: str) -> dict[str, str]:
    return {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "Idempotency-Key": key,
        "X-Consent-Token": "consent-dialogue-policy-test",
    }


def test_routine_triage_exposes_at_most_one_policy_selected_question():
    response = client.post(
        "/v1/chat",
        headers=_headers("dialogue-policy-routine-1"),
        json={
            "conversation_id": "dialogue-policy-routine",
            "intent_hint": "triage",
            "messages": [
                {"role": "user", "content": "Tôi hơi đau lưng sau khi ngồi máy tính cả ngày"},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["urgency"] == "ROUTINE"
    assert len(body["result"]["clarifying_questions"]) <= 1
    assert len(body["answer"]["questions"]) <= 1
    policy = body["result"]["trace"]["details"]["question_policy"]
    assert policy["max_questions"] == 1
    assert len(policy["selected"]) <= 1


def test_urgent_gi_triage_asks_no_more_than_two_high_value_questions():
    response = client.post(
        "/v1/chat",
        headers=_headers("dialogue-policy-urgent-gi-1"),
        json={
            "conversation_id": "dialogue-policy-urgent-gi",
            "intent_hint": "triage",
            "messages": [
                {"role": "user", "content": "Tôi đang rất đau bụng và buồn nôn"},
                {"role": "assistant", "content": "Bạn đau ở vị trí nào?"},
                {"role": "user", "content": "Đau tập trung ở vùng trên rốn"},
                {"role": "assistant", "content": "Đau liên quan bữa ăn thế nào?"},
                {"role": "user", "content": "Đau tăng khi đói và có nóng rát, ợ chua"},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["result"]["clarifying_questions"]) <= 2
    assert len(body["answer"]["questions"]) <= 2
    policy = body["result"]["trace"]["details"]["question_policy"]
    assert policy["max_questions"] in {1, 2}
    assert len(policy["selected"]) <= 2


def test_emergency_action_is_not_delayed_by_clarifying_questions():
    response = client.post(
        "/v1/chat",
        headers=_headers("dialogue-policy-emergency-1"),
        json={
            "conversation_id": "dialogue-policy-emergency",
            "intent_hint": "triage",
            "messages": [
                {"role": "user", "content": "Tôi đau ngực dữ dội, khó thở và vã mồ hôi"},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["urgency"] == "EMERGENCY"
    assert body["result"]["clarifying_questions"] == []
    assert body["answer"]["questions"] == []
    policy = body["result"]["trace"]["details"]["question_policy"]
    assert policy["max_questions"] == 0

    narrative = body["answer"]["narrative"]
    early_text = " ".join(block["text"] for block in narrative[:2]).lower()
    assert "115" in early_text or "cấp cứu" in early_text


def test_known_gi_details_are_not_reasked_after_policy_selection():
    response = client.post(
        "/v1/chat",
        headers=_headers("dialogue-policy-known-facts-1"),
        json={
            "conversation_id": "dialogue-policy-known-facts",
            "intent_hint": "triage",
            "messages": [
                {"role": "user", "content": "Tôi đau bụng vùng trên rốn và buồn nôn"},
                {"role": "assistant", "content": "Đau liên quan bữa ăn thế nào?"},
                {"role": "user", "content": "Đau tăng khi đói"},
                {"role": "assistant", "content": "Có nóng rát hoặc ợ chua không?"},
                {"role": "user", "content": "Có nóng rát và ợ chua"},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    questions = " ".join(body["answer"]["questions"]).lower()
    assert "trên hay dưới bụng" not in questions
    assert "thay đổi thế nào khi đói" not in questions
    assert "nóng rát" not in questions
    assert "ợ chua" not in questions
