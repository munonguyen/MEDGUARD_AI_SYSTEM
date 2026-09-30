from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def _text(body: dict) -> str:
    answer = body.get("answer") or {}
    values: list[str] = []
    for key in (
        "title",
        "summary",
        "clinical_hypotheses",
        "key_points",
        "next_steps",
        "safety_notes",
        "questions",
        "limitations",
    ):
        value = answer.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif value:
            values.append(str(value))
    return " ".join(values).lower()


def test_emergency_chest_dyspnea_api_fallback_keeps_critical_action() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/chat",
        headers={
            "X-API-Key": "demo-key",
            "X-Tenant-Id": "tenant-demo",
            "X-Consent-Token": "consent-v27-critical-fallback",
            "Idempotency-Key": "v27-critical-fallback-chest-dyspnea",
        },
        json={
            "conversation_id": "v27-critical-fallback-chest-dyspnea",
            "messages": [
                {
                    "role": "user",
                    "content": "Tôi đau ngực và cảm giác khó thở, có cần đi viện không?",
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    text = _text(body)
    assert ("115" in text or "cấp cứu" in text), body
    assert (body.get("result") or {}).get("urgency") == "EMERGENCY", body
