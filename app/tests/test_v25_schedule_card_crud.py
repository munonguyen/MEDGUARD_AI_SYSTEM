from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _headers(key: str, *, idempotent: bool = True) -> dict[str, str]:
    headers = {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "X-Consent-Token": "consent-v25-schedule-card",
    }
    if idempotent:
        headers["Idempotency-Key"] = key
    return headers


def _chat(patient_ref: str, conversation_id: str, key: str, messages: list[dict[str, str]]):
    return client.post(
        "/v1/chat",
        headers=_headers(key),
        json={
            "conversation_id": conversation_id,
            "messages": messages,
            "context": {"patient_ref": patient_ref},
        },
    )


def _active(patient_ref: str) -> list[dict]:
    response = client.get(
        "/v1/medication-schedules",
        params={"patient_ref": patient_ref},
        headers=_headers("unused", idempotent=False),
    )
    assert response.status_code == 200
    return [item for item in response.json()["schedules"] if item["status"] == "active"]


def test_card_create_view_update_delete_is_stateful_and_never_routes_to_triage():
    suffix = uuid4().hex[:8]
    patient_ref = f"V25-CARD-{suffix}"
    conversation_id = f"v25-card-{suffix}"
    messages: list[dict[str, str]] = []

    create_q = "Tạo cho tôi một card lịch uống thuốc aspirin mỗi ngày lúc 08:00."
    messages.append({"role": "user", "content": create_q})
    created = _chat(patient_ref, conversation_id, f"{suffix}-1", messages)
    assert created.status_code == 200
    assert created.json()["intent"] == "schedule"
    assert created.json()["status"] == "answered"
    active = _active(patient_ref)
    assert len(active) == 1
    assert active[0]["scheduled_at"][11:16] == "08:00"
    original_id = active[0]["schedule_id"]
    messages.append({"role": "assistant", "content": created.json()["reply"]})

    view_q = "Cho tôi xem lại card lịch uống aspirin vừa tạo, đừng tạo thêm card mới."
    messages.append({"role": "user", "content": view_q})
    viewed = _chat(patient_ref, conversation_id, f"{suffix}-2", messages)
    assert viewed.status_code == 200
    assert viewed.json()["intent"] == "schedule"
    active = _active(patient_ref)
    assert len(active) == 1
    assert active[0]["schedule_id"] == original_id
    messages.append({"role": "assistant", "content": viewed.json()["reply"]})

    update_q = "Đổi giờ trên card aspirin đó từ 08:00 sang 09:00, giữ nguyên một card thôi."
    messages.append({"role": "user", "content": update_q})
    updated = _chat(patient_ref, conversation_id, f"{suffix}-3", messages)
    assert updated.status_code == 200
    assert updated.json()["intent"] == "schedule"
    active = _active(patient_ref)
    assert len(active) == 1
    assert active[0]["schedule_id"] == original_id
    assert active[0]["scheduled_at"][11:16] == "09:00"
    messages.append({"role": "assistant", "content": updated.json()["reply"]})

    delete_q = "Xóa card lịch uống aspirin này giúp tôi."
    messages.append({"role": "user", "content": delete_q})
    deleted = _chat(patient_ref, conversation_id, f"{suffix}-4", messages)
    assert deleted.status_code == 200
    assert deleted.json()["intent"] == "schedule"
    assert _active(patient_ref) == []


def test_cancel_card_marks_it_inactive_without_creating_a_duplicate():
    suffix = uuid4().hex[:8]
    patient_ref = f"V25-CANCEL-{suffix}"
    conversation_id = f"v25-cancel-{suffix}"

    created = _chat(
        patient_ref,
        conversation_id,
        f"{suffix}-create",
        [{"role": "user", "content": "Tạo cho tôi một card lịch uống thuốc amoxicillin mỗi ngày lúc 07:00."}],
    )
    assert created.status_code == 200
    assert created.json()["intent"] == "schedule"
    assert len(_active(patient_ref)) == 1

    cancelled = _chat(
        patient_ref,
        conversation_id,
        f"{suffix}-cancel",
        [
            {"role": "user", "content": "Tạo cho tôi một card lịch uống thuốc amoxicillin mỗi ngày lúc 07:00."},
            {"role": "assistant", "content": created.json()["reply"]},
            {"role": "user", "content": "Hủy card nhắc amoxicillin này."},
        ],
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["intent"] == "schedule"
    assert _active(patient_ref) == []
