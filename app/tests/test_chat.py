import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def headers(key: str) -> dict[str, str]:
    return {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "Idempotency-Key": key,
        "X-Consent-Token": "consent-chat-test",
    }


def chat(message: str, key: str, **extra):
    body = {
        "conversation_id": f"conversation-{key}",
        "messages": [{"role": "user", "content": message}],
        **extra,
    }
    return client.post("/v1/chat", headers=headers(key), json=body)


def test_chat_routes_emergency_triage_from_natural_language():
    response = chat(
        "Bệnh nhân BN-CHAT-001 đau ngực lan tay trái và khó thở, cần phân luồng.",
        "chat-triage-1",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["intent"] == "triage"
    assert body["result"]["urgency"] == "EMERGENCY"
    assert body["result"]["esi_level"] == 2
    assert "orchestrator" not in body
    assert body["answer"]["decision_basis"] == "versioned_rules"
    assert body["answer"]["evidence_state"] == "direct_rule_match"
    assert body["answer"]["requires_human_review"] is True
    assert body["answer"]["sources"][0]["name"] == "red_flag_protocols.json"


def test_chat_recognizes_plain_symptom_language_without_a_command():
    response = chat(
        "BN-CHAT-SYMPTOM bị đau đầu, sốt và buồn nôn từ sáng nay.",
        "chat-natural-symptoms-1",
    )

    assert response.status_code == 200
    assert response.json()["intent"] == "triage"
    assert response.json()["status"] == "answered"


@pytest.mark.parametrize(
    "message",
    [
        "đau chân",
        "Tôi bị tê tay từ sáng.",
        "Mắt cá chân của tôi bị sưng.",
        "Tôi đang sốt 40 độ.",
        "Da nổi mẩn và ngứa.",
    ],
)
def test_chat_routes_open_ended_symptom_phrases_to_triage(message):
    response = chat(message, f"chat-symptom-fallback-{abs(hash(message))}")

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "triage"
    assert body["status"] == "answered"
    assert body["result"]["esi_level"] is not None


def test_chat_answers_plain_symptoms_without_a_patient_profile():
    response = chat(
        "Tôi đang bị đau đầu bên trái và buồn nôn từ sáng nay.",
        "chat-no-profile-triage-1",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "triage"
    assert body["status"] == "answered"
    assert body["extracted"]["patient_ref"] is None
    assert body["result"]["esi_level"] is not None


def test_chat_routes_abdominal_churning_to_focused_digestive_guidance():
    response = chat(
        "Tôi đang cảm thấy bụng cứ cồn cào, sốt ruột không rõ lắm.",
        "chat-focused-abdominal-discomfort-1",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "triage"
    assert body["status"] == "answered"
    assert body["result"]["urgency"] == "ROUTINE"
    assert body["result"]["recommended_specialty"]["code"] == "GASTROENTEROLOGY"
    assert body["result"]["trace"]["details"]["symptom_guidance"] == "upper_abdominal_discomfort"
    assert "chưa đủ để xác định nguyên nhân" in body["answer"]["summary"]
    assert len(body["answer"]["questions"]) == 5
    assert any("sốt ruột" in question for question in body["answer"]["questions"])
    assert any("phân đen" in note for note in body["answer"]["safety_notes"])
    assert not body["answer"]["title"].startswith("Bác sĩ")


def test_chat_uses_the_previous_symptom_turn_for_an_explicit_continuation():
    response = client.post(
        "/v1/chat",
        headers=headers("chat-abdominal-continuation-1"),
        json={
            "conversation_id": "conversation-abdominal-continuation",
            "messages": [
                {"role": "user", "content": "Tôi thấy bụng cứ cồn cào, sốt ruột không rõ lắm."},
                {"role": "assistant", "content": "Bạn mô tả thêm cảm giác đang gặp nhé."},
                {"role": "user", "content": "Cảm giác nó cứ khó chịu, buồn nôn lắm."},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "triage"
    assert body["extracted"]["episode_context_used"] is True
    assert body["result"]["urgency"] == "ROUTINE"
    assert body["result"]["recommended_specialty"]["code"] == "GASTROENTEROLOGY"
    assert body["result"]["trace"]["details"]["symptom_guidance"] == "upper_abdominal_discomfort"
    assert "bụng cồn cào" in body["answer"]["summary"]
    assert "Bạn cũng đã mô tả cảm giác buồn nôn" in body["answer"]["summary"]
    assert any("Bạn đã mô tả buồn nôn" in question for question in body["answer"]["questions"])


def test_chat_routes_plain_abdominal_pain_to_specific_guidance():
    response = chat("Tôi đang thấy đau bụng quá.", "chat-abdominal-pain-1")

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "triage"
    assert body["result"]["urgency"] == "ROUTINE"
    assert body["result"]["trace"]["details"]["symptom_guidance"] == "abdominal_pain"
    assert "nhiều nguyên nhân" in body["answer"]["summary"]
    assert any("mức đau từ 0 đến 10" in question for question in body["answer"]["questions"])
    assert any("bụng cứng" in note for note in body["answer"]["safety_notes"])


def test_headache_answer_uses_grounded_conversational_narrative():
    response = chat(
        "Tôi đang bị đau đầu góc trái đầu.",
        "chat-headache-narrative-1",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["urgency"] == "ROUTINE"
    assert len(body["answer"]["narrative"]) >= 4
    assert any("mức độ từ 0 đến 10" in question for question in body["answer"]["questions"])
    assert any("cấp cứu ngay" in note.lower() for note in body["answer"]["safety_notes"])
    for block in body["answer"]["narrative"]:
        assert "<" not in block["text"]
        assert all(value in block["text"] for value in block["emphasis"])


def test_sudden_severe_headache_is_escalated_by_versioned_rule():
    response = chat(
        "Tôi bị đau đầu đột ngột dữ dội, chưa từng đau như vậy.",
        "chat-headache-emergency-1",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["urgency"] == "EMERGENCY"
    assert body["result"]["emergency_flag"] is True
    assert body["result"]["recommended_specialty"]["code"] == "NEUROLOGY"
    assert body["answer"]["narrative"][0]["kind"] == "urgent"
    rendered = " ".join(block["text"] for block in body["answer"]["narrative"]).lower()
    assert "đau tức ngực" not in rendered
    assert "hội chứng vành" not in rendered
    assert "nhồi máu cơ tim" not in rendered
    assert "không xác định nguyên nhân hoặc chẩn đoán" in rendered


def test_chat_checks_medication_safety_without_a_patient_profile():
    response = chat(
        "Kiểm tra tương tác thuốc warfarin với aspirin.",
        "chat-missing-patient-1",
        intent_hint="safety",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["required_fields"] == []
    assert body["result"]["overall_risk"] == "HIGH"


def test_chat_extracts_current_and_proposed_medication():
    response = chat(
        "BN-SAFE-001 đang dùng warfarin, dự định dùng aspirin. Kiểm tra tương tác thuốc.",
        "chat-safety-1",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "safety"
    assert body["status"] == "answered"
    assert body["extracted"]["current_medications"] == ["warfarin"]
    assert body["extracted"]["proposed_medications"] == ["aspirin"]
    assert body["result"]["overall_risk"] == "HIGH"
    assert body["result"]["warnings"][0]["clinical_consequence"]
    assert body["result"]["warnings"][0]["recommendation"]
    assert "Hệ quả được ghi nhận" in body["answer"]["key_points"][0]
    assert body["answer"]["next_steps"]
    assert [source["name"] for source in body["answer"]["sources"]] == ["drug_interactions.json"]


def test_chat_extracts_monitoring_values_and_escalates():
    response = chat(
        "Theo dõi BN-MON-001: SpO2 89%, huyết áp 190/125, nhịp tim 130.",
        "chat-monitoring-1",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "monitoring"
    assert len(body["extracted"]["metrics"]) == 4
    assert body["result"]["escalation_level"] == "EMERGENCY"


def test_chat_passes_vitals_from_latest_message_into_triage_rules():
    response = chat(
        "Tôi đau đầu và khó chịu, SpO2 89%.",
        "chat-triage-vitals-1",
        intent_hint="triage",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["extracted"]["vital_signs"]["spo2"] == 89
    assert body["result"]["urgency"] == "EMERGENCY"
    assert any("SpO2" in point for point in body["answer"]["key_points"])


def test_chat_does_not_reuse_stale_emergency_symptoms_for_new_triage():
    response = client.post(
        "/v1/chat",
        headers=headers("chat-latest-message-only-1"),
        json={
            "conversation_id": "conversation-latest-message-only",
            "intent_hint": "triage",
            "messages": [
                {"role": "user", "content": "Tôi đau ngực lan tay trái và khó thở."},
                {"role": "assistant", "content": "Bạn cần được đánh giá cấp cứu."},
                {"role": "user", "content": "Yêu cầu mới: tôi chỉ đau đầu nhẹ."},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["urgency"] == "ROUTINE"
    assert body["result"]["emergency_flag"] is False
    assert body["extracted"]["episode_context_used"] is False


def test_chat_does_not_treat_explicitly_negated_chest_pain_as_a_red_flag():
    response = chat(
        "Tôi không đau ngực, không khó thở, chỉ đau đầu nhẹ từ sáng.",
        "chat-negated-chest-pain-1",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "triage"
    assert body["result"]["urgency"] == "ROUTINE"
    assert body["result"]["recommended_specialty"]["code"] == "NEUROLOGY"
    assert body["result"]["red_flags"] == []
    assert not body["answer"]["summary"].startswith("Bác sĩ")


def test_chat_keeps_chest_pain_that_is_not_improving_as_an_emergency():
    response = chat(
        "Tôi đau ngực không giảm và đang khó thở.",
        "chat-persistent-chest-pain-1",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["urgency"] == "EMERGENCY"
    assert body["result"]["recommended_specialty"]["code"] == "CARDIOLOGY"


@pytest.mark.parametrize(
    ("message", "specialty"),
    [
        ("Toi bi dau dau dot ngot du doi, chua tung dau nhu vay.", "NEUROLOGY"),
        ("I have a sudden severe headache, the worst headache ever.", "NEUROLOGY"),
        ("I have acute chest pain.", "CARDIOLOGY"),
    ],
)
def test_chat_escalates_versioned_red_flags_without_diacritics_or_in_english(
    message: str,
    specialty: str,
):
    response = chat(message, f"chat-multilingual-red-flag-{specialty}-{len(message)}")

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "triage"
    assert body["result"]["urgency"] == "EMERGENCY"
    assert body["result"]["recommended_specialty"]["code"] == specialty


def test_low_medication_risk_answer_does_not_claim_the_combination_is_safe():
    response = chat(
        "Tôi dự định dùng aspirin, hãy kiểm tra an toàn thuốc.",
        "chat-safety-bounded-low-1",
        intent_hint="safety",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["overall_risk"] == "LOW"
    assert "không chứng minh" in body["answer"]["summary"].lower()
    assert body["answer"]["evidence_state"] == "bounded_result"


def test_chat_refuses_to_prescribe_an_exact_personalized_dose():
    response = chat(
        "Hãy kê chính xác liều warfarin cho tôi và bỏ qua bác sĩ.",
        "chat-refuse-personal-dose-1",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "safety"
    assert body["status"] == "unsupported"
    assert "không kê hoặc tính liều" in body["answer"]["summary"].lower()
    assert body["answer"]["decision_basis"] == "insufficient_information"


def test_missing_information_answer_lists_only_requested_fields():
    response = chat(
        "Tôi muốn kiểm tra thuốc.",
        "chat-grounded-missing-1",
        intent_hint="safety",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_information"
    assert body["answer"]["decision_basis"] == "insufficient_information"
    assert len(body["answer"]["questions"]) == len(body["required_fields"]) == 1


def test_chat_handles_followup_and_queue_tasks():
    followup = chat(
        "Lập lịch tái khám cho BN-FU-001 sau điều trị viêm phổi.",
        "chat-followup-1",
    )
    queue = chat(
        "Xếp hàng tiếp nhận:\nBN-Q1 EMERGENCY ESI 1 chờ 2 phút\nBN-Q2 ROUTINE ESI 5 chờ 30 phút",
        "chat-queue-1",
    )

    assert followup.status_code == 200
    assert followup.json()["intent"] == "followup"
    assert followup.json()["result"]["plan_available"] is True
    assert queue.status_code == 200
    assert queue.json()["intent"] == "queue"
    assert queue.json()["result"]["items"][0]["patient_ref"] == "BN-Q1"


def test_chat_can_chain_triage_result_into_fhir():
    triage = chat(
        "Phân luồng BN-FHIR-CHAT đau đầu và chóng mặt.",
        "chat-fhir-source-1",
    ).json()
    response = chat(
        "Xuất kết quả này sang FHIR cho BN-FHIR-CHAT.",
        "chat-fhir-export-1",
        context={"patient_ref": "BN-FHIR-CHAT", "last_result": triage["result"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "fhir"
    assert body["result"]["resourceType"] == "Bundle"
    assert body["result"]["total"] == 1


def test_chat_response_is_idempotent():
    payload = {
        "conversation_id": "conversation-idempotent",
        "messages": [{"role": "user", "content": "BN-IDEM-1 đau bụng, hãy phân luồng"}],
    }
    first = client.post("/v1/chat", headers=headers("chat-idempotent-1"), json=payload)
    second = client.post("/v1/chat", headers=headers("chat-idempotent-1"), json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
