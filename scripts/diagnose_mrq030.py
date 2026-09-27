from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from scripts.evaluate_medical_response_quality import _score_case


root = Path(__file__).resolve().parents[1]
dataset = json.loads((root / "datasets/DS-MEDICAL-RESPONSE-QUALITY/dataset.json").read_text(encoding="utf-8"))
case = next(item for item in dataset["cases"] if item["case_id"] == "MRQ-030")
client = TestClient(app)
with patch("app.services.chat.background_agent_runner.submit", return_value=False), patch(
    "app.services.chat.active_learning_store.capture_case", return_value=None
):
    response = client.post(
        "/v1/chat",
        headers={
            "X-API-Key": "demo-key",
            "X-Tenant-Id": "tenant-demo",
            "X-Consent-Token": "consent-mrq030-diagnostic",
            "Idempotency-Key": "mrq030-diagnostic",
        },
        json={
            "conversation_id": "mrq030-diagnostic",
            "messages": [{"role": "user", "content": case["prompt"]}],
        },
    )
body = response.json()
score = _score_case(case, body, 0.0)
print("MRQ030_SCORE", json.dumps(score, ensure_ascii=False, indent=2))
print("MRQ030_ANSWER", json.dumps(body.get("answer"), ensure_ascii=False, indent=2))
