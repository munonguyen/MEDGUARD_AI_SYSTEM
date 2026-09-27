from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.main import app
from app.services.risk_memory import infer_episode_domain, should_start_new_episode

client = TestClient(app)
headers_base = {
    "X-API-Key": "demo-key",
    "X-Tenant-Id": "tenant-demo",
    "X-Consent-Token": "consent-chat-test",
}


def chat(
    messages: list[dict[str, str]],
    key: str,
    intent: str = "auto",
    context: dict | None = None,
) -> dict:
    headers = {**headers_base, "Idempotency-Key": key}
    response = client.post(
        "/v1/chat",
        headers=headers,
        json={
            "conversation_id": key,
            "intent_hint": intent,
            "messages": messages,
            "context": context or {},
        },
    )
    response.raise_for_status()
    return response.json()


print("DOMAIN chest:", infer_episode_domain("Tôi bị đau ngực và khó thở"))
print("DOMAIN GI:", infer_episode_domain("Tôi đang cảm thấy bụng cứ cồn cào, sốt ruột không rõ lắm."))
print(
    "SWITCH chest->GI:",
    should_start_new_episode(
        "Tôi đang cảm thấy bụng cứ cồn cào, sốt ruột không rõ lắm.",
        "Tôi bị đau ngực và khó thở",
    ),
)

chest_gi = chat(
    [
        {"role": "user", "content": "Tôi bị đau ngực và khó thở"},
        {"role": "assistant", "content": "Bạn cần được đánh giá cấp cứu ngay."},
        {"role": "user", "content": "Tôi đang cảm thấy bụng cứ cồn cào, sốt ruột không rõ lắm."},
    ],
    "diag-chest-gi-pretest",
)
print(
    "CHEST_TO_GI",
    json.dumps(
        {
            "intent": chest_gi.get("intent"),
            "urgency": (chest_gi.get("result") or {}).get("urgency"),
            "specialty": (chest_gi.get("result") or {}).get("recommended_specialty"),
            "trace": ((chest_gi.get("result") or {}).get("trace") or {}).get("details"),
            "extracted": chest_gi.get("extracted"),
            "summary": (chest_gi.get("answer") or {}).get("summary"),
        },
        ensure_ascii=False,
        indent=2,
    ),
)

gi = chat(
    [
        {"role": "user", "content": "tôi đang rất đau bụng và buồn nôn"},
        {"role": "assistant", "content": "Bạn đau ở vị trí nào?"},
        {"role": "user", "content": "Cơn đau của tôi tập trung ở vùng trên rốn."},
        {"role": "assistant", "content": "Đau có liên quan bữa ăn không?"},
        {"role": "user", "content": "Cơn đau thường xuất hiện hoặc tăng lên khi đói"},
        {"role": "assistant", "content": "Có nóng rát hay ợ chua không?"},
        {"role": "user", "content": "Cơn đau có kèm theo nóng rát và ợ chua"},
    ],
    "diag-gi-pretest",
    "triage",
)
print(
    "GI_DELTA",
    json.dumps(
        {
            "urgency": (gi.get("result") or {}).get("urgency"),
            "specialty": (gi.get("result") or {}).get("recommended_specialty"),
            "trace": ((gi.get("result") or {}).get("trace") or {}).get("details"),
            "summary": (gi.get("answer") or {}).get("summary"),
            "questions": (gi.get("answer") or {}).get("questions"),
            "safety_notes": (gi.get("answer") or {}).get("safety_notes"),
        },
        ensure_ascii=False,
        indent=2,
    ),
)

schedule = chat(
    [
        {"role": "user", "content": "Tôi bị đau ngực và khó thở"},
        {"role": "assistant", "content": "Bạn cần được đánh giá cấp cứu ngay."},
        {"role": "user", "content": "Tôi đang cảm thấy bụng cứ cồn cào, sốt ruột không rõ lắm."},
        {"role": "assistant", "content": chest_gi.get("reply", "")},
        {"role": "user", "content": "Cảm giác nó cứ khó chịu, buồn nôn lắm."},
        {"role": "assistant", "content": "Thông tin hiện tại chưa cho thấy rõ dấu hiệu cấp cứu."},
        {"role": "user", "content": "#lichthuoc uống amoxicillin lúc 8h và 20h mỗi ngày."},
    ],
    "diag-schedule-after-switch",
    "auto",
    {
        "patient_ref": "BN-UI-DIAG",
        "age": 36,
        "sex": "male",
        "current_medications": ["warfarin"],
        "allergies": [],
        "conditions": ["tăng huyết áp"],
        "last_result": None,
    },
)
print(
    "SCHEDULE_AFTER_SWITCH",
    json.dumps(
        {
            "intent": schedule.get("intent"),
            "status": schedule.get("status"),
            "reply": schedule.get("reply"),
            "required_fields": schedule.get("required_fields"),
            "answer_summary": (schedule.get("answer") or {}).get("summary"),
            "narrative": (schedule.get("answer") or {}).get("narrative"),
            "result": schedule.get("result"),
        },
        ensure_ascii=False,
        indent=2,
    ),
)
