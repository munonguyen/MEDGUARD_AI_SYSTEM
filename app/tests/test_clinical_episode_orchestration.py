from fastapi.testclient import TestClient

from app.main import app
from app.models.triage import TriageRequest
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


def test_triage_request_boundary_removes_stale_episode_before_frozen_engine():
    request = TriageRequest(
        patient_ref="TEST-EPISODE",
        symptoms_text=(
            "Tôi hơi đau lưng sau khi ngồi máy tính cả ngày\n"
            "Tôi chỉ đau ở vùng thắt lưng, không có đau lan hay tê chân.\n"
            "Lượt hiện tại: tôi đang rất đau bụng và buồn nôn"
        ),
    )

    assert request.symptoms_text == "tôi đang rất đau bụng và buồn nôn"
    assert "đau lưng" not in request.symptoms_text.lower()


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
    assert "Cơ xương khớp" not in body["answer"]["summary"]
    assert body["answer"]["next_steps"]


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
    assert "Cơ xương khớp" not in body["answer"]["summary"]
    assert body["answer"]["next_steps"]


def test_negated_leg_findings_do_not_select_lower_limb_guidance():
    from app.knowledge.loader import knowledge

    guidance = knowledge.find_symptom_guidance(
        "Tôi chỉ đau ở vùng thắt lưng, không có đau lan hay tê chân."
    )

    assert guidance is not None
    assert guidance["topic"] == "back_pain"


def test_episode_domain_ignores_negated_chest_symptom():
    from app.services.risk_memory import infer_episode_domain

    assert infer_episode_domain("Không đau ngực, tôi chỉ đau bụng vùng trên rốn") == "gastrointestinal"


def test_chat_emergency_chest_episode_does_not_lock_new_abdominal_episode():
    response = client.post(
        "/v1/chat",
        headers=_headers("episode-emergency-to-gi-1"),
        json={
            "conversation_id": "conversation-emergency-to-gi",
            "intent_hint": "auto",
            "messages": [
                {"role": "user", "content": "Tôi bị đau ngực và khó thở"},
                {"role": "assistant", "content": "Bạn cần được đánh giá cấp cứu ngay."},
                {"role": "user", "content": "Tôi đang cảm thấy bụng cứ cồn cào, sốt ruột không rõ lắm."},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "triage"
    assert body["result"]["urgency"] == "ROUTINE"
    assert body["result"]["recommended_specialty"]["code"] == "GASTROENTEROLOGY"
    assert body["extracted"]["episode_switched"] is True
    summary = body["answer"]["summary"].lower()
    current_red_flags = " ".join(body["result"].get("red_flags", [])).lower()
    trace = body["result"]["trace"]["details"]
    assert "đau ngực" not in summary
    assert "khó thở" not in summary
    assert "đau ngực" not in current_red_flags
    assert "tức ngực" not in current_red_flags
    assert trace["conversation_risk"] is None
    assert trace["rule_urgency"] != "EMERGENCY"


def test_negated_leg_followup_stays_back_pain_and_routes_musculoskeletal():
    response = client.post(
        "/v1/chat",
        headers=_headers("episode-back-negation-1"),
        json={
            "conversation_id": "conversation-back-negation",
            "intent_hint": "triage",
            "messages": [
                {"role": "user", "content": "Tôi hơi đau lưng sau khi ngồi máy tính cả ngày"},
                {"role": "assistant", "content": "Bạn có đau lan xuống chân không?"},
                {"role": "user", "content": "Tôi chỉ đau ở vùng thắt lưng, không có đau lan hay tê chân."},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["trace"]["details"]["symptom_guidance"] == "back_pain"
    assert body["result"]["recommended_specialty"]["code"] == "MUSCULOSKELETAL"
    assert not body["answer"]["summary"].startswith("Đau chân cần được đánh giá")


def test_gi_followups_consume_location_meal_relation_and_reflux_details():
    response = client.post(
        "/v1/chat",
        headers=_headers("episode-gi-state-delta-1"),
        json={
            "conversation_id": "conversation-gi-state-delta",
            "intent_hint": "triage",
            "messages": [
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
    summary = body["answer"]["summary"].lower()
    questions = " ".join(body["answer"]["questions"]).lower()
    assert "trên rốn" in summary
    assert "tăng khi đói" in summary
    assert "ợ chua" in summary
    assert "đau ở vùng trên hay dưới bụng" not in questions
    assert "thay đổi thế nào khi đói" not in questions
    assert body["result"]["trace"]["details"]["resolution_reasons"]


def test_explicit_schedule_command_after_clinical_history_is_not_hijacked_by_triage():
    response = client.post(
        "/v1/chat",
        headers=_headers("episode-schedule-after-history-1"),
        json={
            "conversation_id": "conversation-schedule-after-history",
            "intent_hint": "auto",
            "context": {
                "patient_ref": "BN-SCHEDULE-HISTORY",
                "age": 36,
                "sex": "male",
                "current_medications": ["warfarin"],
                "conditions": ["tăng huyết áp"],
            },
            "messages": [
                {"role": "user", "content": "Tôi bị đau ngực và khó thở"},
                {"role": "assistant", "content": "Bạn cần được đánh giá cấp cứu ngay."},
                {"role": "user", "content": "Tôi đang cảm thấy bụng cứ cồn cào, sốt ruột không rõ lắm."},
                {"role": "assistant", "content": "Thông tin hiện tại chưa cho thấy rõ dấu hiệu cấp cứu."},
                {"role": "user", "content": "Cảm giác nó cứ khó chịu, buồn nôn lắm."},
                {"role": "assistant", "content": "Bạn đã mô tả buồn nôn."},
                {"role": "user", "content": "#lichthuoc uống amoxicillin lúc 8h và 20h mỗi ngày."},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "schedule"
    assert body["status"] == "answered"
    assert "Đã thêm 2 mốc uống amoxicillin" in body["reply"]
    assert len((body.get("result") or {}).get("schedules", [])) == 2
