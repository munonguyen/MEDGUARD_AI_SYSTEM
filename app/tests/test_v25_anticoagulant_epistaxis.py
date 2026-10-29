from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services.clinical_safety_floor import evaluate_clinical_safety_floor


client = TestClient(app)


def _headers(key: str) -> dict[str, str]:
    return {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "Idempotency-Key": key,
        "X-Consent-Token": "consent-v25-anticoagulant-epistaxis",
    }


def test_anticoagulant_epistaxis_without_major_loss_is_urgent_not_emergency() -> None:
    floor = evaluate_clinical_safety_floor(
        "Tôi đang dùng thuốc chống đông và hôm nay bị chảy máu cam."
    )

    assert floor.disposition == "URGENT"
    assert floor.is_emergency is False
    assert "clinical_threat_graph" in floor.sources


def test_persistent_anticoagulant_epistaxis_stays_urgent_without_shock_or_major_loss() -> None:
    floor = evaluate_clinical_safety_floor(
        "Tôi đang uống warfarin và chảy máu cam đã 30 phút vẫn chưa cầm, nhưng không choáng hay ngất."
    )

    assert floor.disposition == "URGENT"
    assert floor.is_emergency is False


def test_anticoagulant_major_hemorrhage_still_has_emergency_floor() -> None:
    floor = evaluate_clinical_safety_floor(
        "Tôi dùng warfarin quá liều, chảy máu ồ ạt, nôn ra máu và choáng gần ngất."
    )

    assert floor.disposition == "EMERGENCY"
    assert floor.is_emergency is True


def test_chat_keeps_anticoagulant_nosebleed_in_safety_workflow() -> None:
    suffix = uuid4().hex[:10]
    response = client.post(
        "/v1/chat",
        headers=_headers(f"v25-anticoag-epistaxis-{suffix}"),
        json={
            "conversation_id": f"v25-anticoag-epistaxis-{suffix}",
            "messages": [
                {
                    "role": "user",
                    "content": "Tôi đang dùng thuốc chống đông và hôm nay bị chảy máu cam.",
                }
            ],
            "locale": "vi-VN",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "safety"

    result = body.get("result") or {}
    urgency = str(result.get("urgency") or result.get("escalation_level") or "").upper()
    assert urgency != "EMERGENCY"

    rendered = " ".join(
        [
            body.get("reply", ""),
            (body.get("answer") or {}).get("summary", ""),
            *[
                block.get("text", "")
                for block in (body.get("answer") or {}).get("narrative", [])
            ],
        ]
    ).lower()
    assert "xuất huyết tự phát lớn" not in rendered
    assert "sốc tuần hoàn" not in rendered


def test_chat_major_anticoagulant_bleeding_can_still_enter_emergency_path() -> None:
    suffix = uuid4().hex[:10]
    response = client.post(
        "/v1/chat",
        headers=_headers(f"v25-anticoag-major-bleed-{suffix}"),
        json={
            "conversation_id": f"v25-anticoag-major-bleed-{suffix}",
            "messages": [
                {
                    "role": "user",
                    "content": "Tôi dùng warfarin quá liều, chảy máu ồ ạt, nôn ra máu và choáng gần ngất.",
                }
            ],
            "locale": "vi-VN",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "triage"
    assert (body.get("result") or {}).get("urgency") == "EMERGENCY"
    assert (body.get("answer") or {}).get("display_questions") == []
