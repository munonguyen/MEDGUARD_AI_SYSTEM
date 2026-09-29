from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services.conversation_continuation import resolve_conversation_continuation
from app.services.end_organ_coupling import evaluate_end_organ_coupling


client = TestClient(app)


def _headers(key: str) -> dict[str, str]:
    return {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "Idempotency-Key": key,
        "X-Consent-Token": "consent-v25-symptomatic-tachycardia",
    }


def test_heart_rate_continuation_with_presyncope_routes_to_triage() -> None:
    resolution = resolve_conversation_continuation(
        [
            ("user", "Nhịp tim nghỉ của tôi khoảng 104 lần/phút."),
            ("assistant", "Hãy theo dõi thêm."),
            ("user", "Sau 15 phút vẫn 112 lần/phút."),
            ("assistant", "Tiếp tục theo dõi."),
            ("user", "Nhịp tim 145 lần/phút và tôi gần ngất."),
        ]
    )

    assert resolution is not None
    assert resolution.intent == "triage"
    assert resolution.reason == "heart_rate_with_presyncope"


def test_mid_140s_tachycardia_plus_affirmed_presyncope_is_emergency_coupling() -> None:
    result = evaluate_end_organ_coupling(
        "Nhịp tim 145 lần/phút và tôi gần ngất."
    )

    assert result.disposition == "EMERGENCY"
    assert "symptomatic_tachyarrhythmia_hypoperfusion" in result.coupling_ids


def test_mid_140s_tachycardia_without_presyncope_is_not_promoted_by_coupling() -> None:
    result = evaluate_end_organ_coupling(
        "Nhịp tim 145 lần/phút nhưng tôi không choáng và không gần ngất."
    )

    assert result.disposition != "EMERGENCY"
    assert "symptomatic_tachyarrhythmia_hypoperfusion" not in result.coupling_ids


def test_chat_promotes_heart_rate_145_with_near_syncope_to_emergency() -> None:
    suffix = uuid4().hex[:10]
    response = client.post(
        "/v1/chat",
        headers=_headers(f"v25-tachy-presyncope-{suffix}"),
        json={
            "conversation_id": f"v25-tachy-presyncope-{suffix}",
            "messages": [
                {"role": "user", "content": "Nhịp tim nghỉ của tôi khoảng 104 lần/phút."},
                {"role": "assistant", "content": "Hãy theo dõi thêm."},
                {"role": "user", "content": "Sau 15 phút vẫn 112 lần/phút."},
                {"role": "assistant", "content": "Tiếp tục theo dõi."},
                {"role": "user", "content": "Tôi thấy hồi hộp và choáng."},
                {"role": "assistant", "content": "Nếu nặng lên hãy báo ngay."},
                {"role": "user", "content": "Nhịp tim 145 lần/phút và tôi gần ngất."},
            ],
            "locale": "vi-VN",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "triage"
    assert body["result"]["urgency"] == "EMERGENCY"
    assert body["answer"]["display_questions"] == []
    first = body["answer"]["narrative"][0]["text"].lower()
    assert "115" in first or "cấp cứu" in first
