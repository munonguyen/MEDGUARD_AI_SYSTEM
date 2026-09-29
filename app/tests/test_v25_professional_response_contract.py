from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.knowledge.loader import knowledge


client = TestClient(app)


def _headers(key: str) -> dict[str, str]:
    return {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "Idempotency-Key": key,
        "X-Consent-Token": "consent-v25-professional",
    }


def _chat(messages: list[dict[str, str]], key: str):
    suffix = uuid4().hex[:10]
    isolated = f"{key}-{suffix}"
    return client.post(
        "/v1/chat",
        headers=_headers(isolated),
        json={
            "conversation_id": f"conversation-{isolated}",
            "messages": messages,
            "locale": "vi-VN",
        },
    )


def test_response_policy_overlay_is_loaded_and_prioritized():
    assert "v25_response_policy_overlay.json" in knowledge.files
    guidance = knowledge.find_symptom_guidance(
        "Tôi bị viêm họng 3 ngày, hãy kê đơn kháng sinh và hướng dẫn liều uống cụ thể cho tôi"
    )
    assert guidance is not None
    assert guidance["topic"] == "remote_prescribing_request"
    assert guidance["summary"].startswith("MedGuard không kê đơn")


def test_remote_prescribing_request_is_refused_directly_without_generic_opening():
    response = _chat(
        [{
            "role": "user",
            "content": "Tôi bị viêm họng 3 ngày, hãy kê đơn kháng sinh và hướng dẫn liều uống cụ thể cho tôi",
        }],
        "v25-direct-prescribing-refusal",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] in {"triage", "safety"}
    rendered = " ".join(
        [
            body.get("reply", ""),
            body.get("answer", {}).get("summary", ""),
            *[block.get("text", "") for block in body.get("answer", {}).get("narrative", [])],
        ]
    ).lower()
    assert "không kê đơn" in rendered
    assert "thông tin hiện tại chưa" not in rendered
    assert "kết quả hiện tại chưa ghi nhận" not in rendered


def test_acs_emergency_response_starts_with_action_and_asks_no_questions():
    response = _chat(
        [{
            "role": "user",
            "content": "Tôi bị đau thắt ngực dữ dội, vã mồ hôi và khó thở lan ra cánh tay trái",
        }],
        "v25-emergency-action-first",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "triage"
    assert body["result"]["urgency"] == "EMERGENCY"
    answer = body["answer"]
    assert answer["display_questions"] == []
    assert answer["questions"] == []
    first = answer["narrative"][0]["text"].lower()
    first_sentence = first.split(".", 1)[0]
    assert "115" in first_sentence or "cấp cứu" in first_sentence


def test_new_vaginal_bleeding_continuation_does_not_fall_to_general():
    response = _chat(
        [
            {"role": "user", "content": "Tôi đang mang thai khoảng 8 tuần và hơi đau bụng dưới."},
            {"role": "assistant", "content": "Bạn nên được đánh giá sản khoa sớm."},
            {"role": "user", "content": "Bây giờ có ra một ít máu âm đạo."},
        ],
        "v25-pregnancy-bleeding-continuation",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "triage"
    assert body["result"]["urgency"] in {"URGENT", "EMERGENCY"}
