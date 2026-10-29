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


def test_routine_triage_preserves_candidates_but_displays_at_most_one_question():
    response = client.post(
        "/v1/chat",
        headers=_headers("dialogue-policy-routine-2"),
        json={
            "conversation_id": "dialogue-policy-routine-v2",
            "intent_hint": "triage",
            "messages": [
                {"role": "user", "content": "Tôi hơi đau lưng sau khi ngồi máy tính cả ngày"},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["urgency"] == "ROUTINE"
    # Full approved candidate set remains available for audit/evaluation.
    assert body["answer"]["questions"] == body["result"]["clarifying_questions"]
    # Patient surface receives the smaller information-gain set.
    assert len(body["answer"]["display_questions"]) <= 1
    assert set(body["answer"]["display_questions"]).issubset(set(body["answer"]["questions"]))
    policy = body["result"]["trace"]["details"]["question_policy"]
    assert policy["max_questions"] == 1
    assert len(policy["selected"]) <= 1


def test_urgent_gi_triage_displays_no_more_than_two_high_value_questions():
    response = client.post(
        "/v1/chat",
        headers=_headers("dialogue-policy-urgent-gi-2"),
        json={
            "conversation_id": "dialogue-policy-urgent-gi-v2",
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
    assert len(body["answer"]["display_questions"]) <= 2
    assert set(body["answer"]["display_questions"]).issubset(set(body["answer"]["questions"]))
    policy = body["result"]["trace"]["details"]["question_policy"]
    assert policy["max_questions"] in {1, 2}
    assert len(policy["selected"]) <= 2


def test_plain_abdominal_pain_prefers_severity_over_lower_value_timeline_question():
    response = client.post(
        "/v1/chat",
        headers=_headers("dialogue-policy-abdominal-severity-1"),
        json={
            "conversation_id": "dialogue-policy-abdominal-severity",
            "intent_hint": "triage",
            "messages": [{"role": "user", "content": "Tôi đang thấy đau bụng quá."}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["urgency"] == "ROUTINE"
    assert len(body["answer"]["display_questions"]) == 1
    assert "mức đau" in body["answer"]["display_questions"][0].lower()


def test_nausea_followup_prioritizes_vomiting_and_hydration_status():
    response = client.post(
        "/v1/chat",
        headers=_headers("dialogue-policy-nausea-hydration-1"),
        json={
            "conversation_id": "dialogue-policy-nausea-hydration",
            "intent_hint": "triage",
            "messages": [
                {"role": "user", "content": "Tôi thấy bụng cứ cồn cào, sốt ruột không rõ lắm."},
                {"role": "assistant", "content": "Bạn mô tả thêm cảm giác đang gặp nhé."},
                {"role": "user", "content": "Cảm giác nó cứ khó chịu, buồn nôn lắm."},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    selected = " ".join(body["answer"]["display_questions"]).lower()
    assert "nôn" in selected
    assert "nước" in selected


def test_urgent_leg_functional_impairment_keeps_safety_and_weight_bearing_questions():
    response = client.post(
        "/v1/chat",
        headers=_headers("dialogue-policy-leg-function-1"),
        json={
            "conversation_id": "dialogue-policy-leg-function",
            "intent_hint": "triage",
            "messages": [
                {
                    "role": "user",
                    "content": "tôi đang tính đi xem worldcup mà đang đau chân khó đi được vậy tôi có nên đi không",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["urgency"] == "URGENT"
    selected = body["answer"]["display_questions"]
    assert len(selected) <= 2
    assert any("chịu lực" in question.lower() for question in selected)


def test_emergency_action_is_not_delayed_by_clarifying_questions():
    response = client.post(
        "/v1/chat",
        headers=_headers("dialogue-policy-emergency-2"),
        json={
            "conversation_id": "dialogue-policy-emergency-v2",
            "intent_hint": "triage",
            "messages": [
                {"role": "user", "content": "Tôi đau ngực dữ dội, khó thở và vã mồ hôi"},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["urgency"] == "EMERGENCY"
    assert body["answer"]["display_questions"] == []
    policy = body["result"]["trace"]["details"]["question_policy"]
    assert policy["max_questions"] == 0

    narrative = body["answer"]["narrative"]
    early_text = " ".join(block["text"] for block in narrative[:2]).lower()
    assert "115" in early_text or "cấp cứu" in early_text


def test_known_gi_details_are_not_reasked_in_patient_question_set():
    response = client.post(
        "/v1/chat",
        headers=_headers("dialogue-policy-known-facts-2"),
        json={
            "conversation_id": "dialogue-policy-known-facts-v2",
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
    questions = " ".join(body["answer"]["display_questions"]).lower()
    assert "trên hay dưới bụng" not in questions
    assert "thay đổi thế nào khi đói" not in questions
    assert "nóng rát" not in questions
    assert "ợ chua" not in questions
