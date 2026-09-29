from __future__ import annotations

from fastapi.testclient import TestClient

from app.knowledge.loader import knowledge
from app.main import app


client = TestClient(app)


def _headers(request_id: str) -> dict[str, str]:
    return {
        "X-API-Key": "demo-key",
        "X-Tenant-Id": "tenant-demo",
        "X-Consent-Token": "consent-v26-route-isolation",
        "Idempotency-Key": request_id,
    }


def test_chemical_inhalation_does_not_select_skin_burn_guidance() -> None:
    guidance = knowledge.find_symptom_guidance(
        "Tôi vừa hít phải mùi hóa chất tẩy rửa trong phòng kín."
    )

    assert guidance is None or guidance.get("topic") != "acute_burn"


def test_explicit_skin_burn_still_allows_burn_guidance() -> None:
    guidance = knowledge.find_symptom_guidance(
        "Hóa chất đổ lên da làm tôi bị bỏng đỏ rát ở bàn tay."
    )

    assert guidance is not None
    assert guidance.get("topic") == "acute_burn"


def test_chat_chemical_inhalation_has_no_thermal_burn_contamination() -> None:
    response = client.post(
        "/v1/chat",
        headers=_headers("v26-chemical-inhalation-route"),
        json={
            "conversation_id": "v26-chemical-inhalation-route",
            "messages": [
                {
                    "role": "user",
                    "content": "Tôi vừa hít phải mùi hóa chất tẩy rửa trong phòng kín.",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "triage"
    assert body["result"]["urgency"] == "URGENT"

    answer = body["answer"]
    rendered = " ".join(
        [answer.get("summary", "")]
        + list(answer.get("next_steps") or [])
        + list(answer.get("safety_notes") or [])
        + list(answer.get("questions") or [])
    ).lower()
    assert "bỏng nhiệt" not in rendered
    assert "vùng da bị bỏng" not in rendered
    assert "làm mát vết bỏng" not in rendered
    assert "hóa chất" in rendered or "phơi nhiễm" in rendered
