from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.context import RequestContext
from app.main import app
from app.services.jobs import job_store


client = TestClient(app)


def headers(key: str, *, alternate: bool = False, idempotent: bool = True) -> dict[str, str]:
    values = {
        "X-API-Key": "alt-key" if alternate else "demo-key",
        "X-Tenant-Id": "tenant-alt" if alternate else "tenant-demo",
    }
    if idempotent:
        values["Idempotency-Key"] = key
    return values


def post_chat(message: str, *, conversation_id: str, key: str):
    return client.post(
        "/v1/chat",
        headers=headers(key),
        json={
            "conversation_id": conversation_id,
            "messages": [{"role": "user", "content": message}],
        },
    )


def test_chat_creates_daily_medication_schedule_with_multiple_times():
    suffix = uuid4().hex[:8]
    patient_ref = f"BN-SCH-{suffix.upper()}"
    response = post_chat(
        f"#lichthuoc {patient_ref} uống amoxicillin lúc 8h và 20h mỗi ngày",
        conversation_id=f"schedule-{suffix}",
        key=f"schedule-{suffix}",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "schedule"
    assert body["status"] == "answered"
    assert len(body["result"]["schedules"]) == 2
    assert {item["recurrence"] for item in body["result"]["schedules"]} == {"daily"}

    schedule_response = client.get(
        "/v1/medication-schedules",
        params={"patient_ref": patient_ref},
        headers=headers("unused", idempotent=False),
    )
    assert schedule_response.status_code == 200
    schedules = schedule_response.json()["schedules"]
    assert len(schedules) == 2
    assert {item["medication_name"] for item in schedules} == {"amoxicillin"}


def test_natural_language_reminder_routes_to_schedule_without_a_tag():
    suffix = uuid4().hex[:8].upper()
    response = client.post(
        "/v1/chat",
        headers=headers(f"schedule-natural-{suffix}"),
        json={
            "conversation_id": f"schedule-natural-{suffix}",
            "messages": [
                {
                    "role": "user",
                    "content": "Nhắc tôi uống aspirin mỗi ngày lúc 8h và 20h.",
                }
            ],
            "context": {"patient_ref": f"BN-NATURAL-{suffix}"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "schedule"
    assert body["status"] == "answered"
    assert len(body["result"]["schedules"]) == 2


def test_schedule_chat_requests_missing_time_without_creating_schedule():
    suffix = uuid4().hex[:8]
    response = post_chat(
        f"#lichthuoc BN-NOTIME-{suffix} uống aspirin",
        conversation_id=f"schedule-missing-{suffix}",
        key=f"schedule-missing-{suffix}",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "needs_information"
    assert response.json()["required_fields"] == ["scheduled_at"]


def test_schedule_requires_a_real_profile_or_explicit_patient_reference():
    suffix = uuid4().hex[:8]
    response = post_chat(
        "#lichthuoc uống aspirin lúc 21h mỗi ngày",
        conversation_id=f"schedule-no-profile-{suffix}",
        key=f"schedule-no-profile-{suffix}",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "needs_information"
    assert response.json()["required_fields"] == ["patient_ref"]


def test_explicit_patient_in_latest_message_overrides_session_context():
    suffix = uuid4().hex[:8].upper()
    response = client.post(
        "/v1/chat",
        headers=headers(f"schedule-context-{suffix}"),
        json={
            "conversation_id": f"schedule-context-{suffix}",
            "messages": [
                {
                    "role": "user",
                    "content": f"#lichthuoc BN-NEW-{suffix} uống aspirin lúc 21h mỗi ngày",
                }
            ],
            "context": {"patient_ref": f"BN-OLD-{suffix}"},
        },
    )

    assert response.status_code == 200
    assert response.json()["extracted"]["patient_ref"] == f"BN-NEW-{suffix}"


def test_chat_history_is_durable_and_tenant_scoped():
    suffix = uuid4().hex[:8]
    conversation_id = f"history-{suffix}"
    response = post_chat(
        f"Phân luồng BN-HISTORY-{suffix}: đau đầu và chóng mặt",
        conversation_id=conversation_id,
        key=f"history-{suffix}",
    )
    assert response.status_code == 200

    conversations = client.get(
        "/v1/chat/conversations",
        headers=headers("unused", idempotent=False),
    )
    assert conversations.status_code == 200
    matching = [
        item for item in conversations.json()["conversations"]
        if item["conversation_id"] == conversation_id
    ]
    assert len(matching) == 1
    assert matching[0]["message_count"] == 2

    history = client.get(
        f"/v1/chat/conversations/{conversation_id}",
        headers=headers("unused", idempotent=False),
    )
    assert history.status_code == 200
    assert [item["role"] for item in history.json()["messages"]] == ["user", "assistant"]
    assert history.json()["messages"][1]["intent"] == "triage"
    assert history.json()["messages"][1]["answer"]["decision_basis"] == "versioned_rules"
    assert history.json()["messages"][1]["answer"]["rule_version"] == "triage-rules@pha0"

    isolated = client.get(
        f"/v1/chat/conversations/{conversation_id}",
        headers=headers("unused", alternate=True, idempotent=False),
    )
    assert isolated.status_code == 404


def test_idempotent_chat_does_not_duplicate_history_messages():
    suffix = uuid4().hex[:8]
    conversation_id = f"idem-history-{suffix}"
    message = f"Phân luồng BN-IDEM-HISTORY-{suffix}: đau bụng"
    first = post_chat(message, conversation_id=conversation_id, key=f"idem-history-{suffix}")
    second = post_chat(message, conversation_id=conversation_id, key=f"idem-history-{suffix}")
    assert first.status_code == second.status_code == 200

    history = client.get(
        f"/v1/chat/conversations/{conversation_id}",
        headers=headers("unused", idempotent=False),
    )
    assert len(history.json()["messages"]) == 2


def test_prescription_upload_is_recorded_in_chat_history():
    suffix = uuid4().hex[:8].upper()
    conversation_id = f"attachment-{suffix}"
    upload = client.post(
        "/v1/prescription/extract",
        headers=headers(f"attachment-{suffix}"),
        files={"image": ("prescription.png", b"\x89PNG\r\n\x1a\nfixture", "image/png")},
        data={
            "patient_ref": f"BN-ATTACH-{suffix}",
            "conversation_id": conversation_id,
            "message": "Đọc đơn thuốc trong ảnh này.",
        },
    )
    assert upload.status_code == 202

    history = client.get(
        f"/v1/chat/conversations/{conversation_id}",
        headers=headers("unused", idempotent=False),
    )
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert [item["role"] for item in messages] == ["user", "assistant"]
    assert messages[1]["intent"] == "ocr"
    assert messages[1]["result"]["status"] == "queued"


def verify(raw_code: str, suffix: str):
    return client.post(
        "/v1/product/verify",
        headers=headers(f"product-{suffix}"),
        json={"raw_code": raw_code},
    )


def test_product_verification_matches_complete_registry_identity():
    response = verify(
        "MEDGUARD|product=MG-AMOX-500|serial=VN24A001|lot=AMX2409",
        uuid4().hex,
    )
    assert response.status_code == 200
    assert response.json()["verification_status"] == "registry_match"
    assert response.json()["product"]["name"] == "Amoxicillin 500mg"


def test_product_verification_flags_serial_mismatch():
    response = verify(
        "MEDGUARD|product=MG-AMOX-500|serial=UNKNOWN|lot=AMX2409",
        uuid4().hex,
    )
    assert response.status_code == 200
    assert response.json()["verification_status"] == "suspected_counterfeit"


def test_product_verification_handles_unknown_and_recalled_codes():
    unknown = verify(
        "MEDGUARD|product=MG-NOT-REGISTERED|serial=X|lot=Y",
        uuid4().hex,
    )
    recalled = verify(
        "MEDGUARD|product=MG-RECALL-001|serial=VN23R001|lot=RCL2301",
        uuid4().hex,
    )
    assert unknown.status_code == recalled.status_code == 200
    assert unknown.json()["verification_status"] == "unknown"
    assert recalled.json()["verification_status"] == "recalled"


def test_confirmed_prescription_creates_daily_reminders_from_reviewed_directions():
    suffix = uuid4().hex[:8].upper()
    patient_ref = f"BN-RX-{suffix}"
    job = job_store.create(
        ctx=RequestContext(
            request_id=f"req-rx-{suffix}",
            tenant_id="tenant-demo",
            idempotency_key=f"create-rx-{suffix}",
        ),
        patient_ref=patient_ref,
        image_bytes=f"image-{suffix}".encode(),
        content_type="image/png",
        catalog_ref=None,
    )
    job_store.complete(
        job,
        {
            "extracted_medications": [
                {
                    "extracted_entity": {
                        "medicine_name": "Amoxicillin 500mg",
                        "strength": "500mg",
                        "frequency": "2 lần/ngày",
                        "instructions": "Uống sáng 1 viên, tối 1 viên sau ăn",
                    },
                    "confidence": 0.96,
                }
            ],
            "review_status": "PENDING_REVIEW",
        },
    )

    review = client.post(
        f"/v1/jobs/{job.job_id}/review?approved=true",
        headers=headers(f"review-rx-{suffix}"),
    )

    assert review.status_code == 200
    body = review.json()
    assert body["review_status"] == "CONFIRMED_BY_PHARMACIST"
    assert body["result"]["schedule_status"] == "created"
    assert len(body["result"]["medication_schedules"]) == 2
    assert {item["source"] for item in body["result"]["medication_schedules"]} == {"prescription_review"}

    listed = client.get(
        "/v1/medication-schedules",
        params={"patient_ref": patient_ref},
        headers=headers("unused", idempotent=False),
    )
    assert len(listed.json()["schedules"]) == 2
