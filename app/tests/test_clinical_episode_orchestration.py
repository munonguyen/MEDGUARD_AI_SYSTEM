from fastapi.testclient import TestClient

from app.main import app
from app.services.episode_context import select_active_episode_text


client = TestClient(app)


def _headers(key: str) -> dict[str, str]:
    return {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "Idempotency-Key": key,
        "X-Consent-Token": "consent-chat-test",
    }


def test_episode_selector_drops_unrelated_back_pain_when_abdominal_complaint_starts():
    selection = select_active_episode_text(
        "Tôi hơi đau lưng sau khi ngồi máy tính cả ngày\n"
        "Tôi chỉ đau ở vùng thắt lưng, không có đau lan hay tê chân.\n"
        "Lượt hiện tại: tôi đang rất đau bụng và buồn nôn"
    )

    assert selection.switched_episode is True
    assert selection.used_history is False
    assert selection.text == "tôi đang rất đau bụng và buồn nôn"
    assert "đau lưng" not in selection.text.lower()


def test_episode_selector_keeps_same_gi_episode_for_short_followup_details():
    selection = select_active_episode_text(
        "tôi đang rất đau bụng và buồn nôn\n"
        "Cơn đau của tôi tập trung ở vùng trên rốn.\n"
        "Cơn đau thường xuất hiện hoặc tăng lên khi đói\n"
        "Lượt hiện tại: Cơn đau có kèm theo nóng rát và ợ chua"
    )

    assert selection.switched_episode is False
    assert selection.used_history is True
    assert "đau bụng" in selection.text.lower()
    assert "trên rốn" in selection.text.lower()
    assert "ợ chua" in selection.text.lower()


def test_chat_natural_episode_switch_recomputes_specialty_from_current_complaint():
    response = client.post(
        "/v1/chat",
        headers=_headers("episode-natural-switch-1"),
        json={
            "conversation_id": "conversation-natural-episode-switch",
            "intent_hint": "triage",
            "messages": [
                {"role": "user", "content": "Tôi hơi đau lưng sau khi ngồi máy tính cả ngày"},
                {"role": "assistant", "content": "Bạn có đau lan xuống chân không?"},
                {"role": "user", "content": "Tôi chỉ đau ở vùng thắt lưng, không có đau lan hay tê chân."},
                {"role": "assistant", "content": "Bạn theo dõi thêm nhé."},
                {"role": "user", "content": "tôi đang rất đau bụng và buồn nôn"},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "triage"
    assert body["result"]["recommended_specialty"]["code"] == "GASTROENTEROLOGY"
    assert body["result"]["trace"]["details"]["episode_switched"] is True
    assert body["result"]["trace"]["details"]["episode_context_used"] is False
    assert "Cơ xương khớp" not in body["answer"]["summary"]


def test_chat_gi_followup_remains_gi_after_natural_episode_switch():
    response = client.post(
        "/v1/chat",
        headers=_headers("episode-gi-continuation-1"),
        json={
            "conversation_id": "conversation-natural-episode-switch-gi",
            "intent_hint": "triage",
            "messages": [
                {"role": "user", "content": "Tôi hơi đau lưng sau khi ngồi máy tính cả ngày"},
                {"role": "assistant", "content": "Bạn có đau lan xuống chân không?"},
                {"role": "user", "content": "tôi đang rất đau bụng và buồn nôn"},
                {"role": "assistant", "content": "Bạn đau ở vị trí nào?"},
                {"role": "user", "content": "Cơn đau của tôi tập trung ở vùng trên rốn."},
                {"role": "assistant", "content": "Đau có liên quan bữa ăn không?"},
                {"role": "user", "content": "Cơn đau thường xuất hiện hoặc tăng lên khi đói"},
                {"role": "assistant", "content": "Có nóng rát hay ợ chua không?"},
                {"role": "user", "content": "Cơn đau có kèm theo nóng rát và ợ chua"},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "triage"
    assert body["result"]["recommended_specialty"]["code"] == "GASTROENTEROLOGY"
    assert body["result"]["trace"]["details"]["episode_context_used"] is True
    assert body["result"]["trace"]["details"]["episode_switched"] is True
    assert body["answer"]["next_steps"]
