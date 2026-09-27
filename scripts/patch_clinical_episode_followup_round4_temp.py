from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one target, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(path: str, marker: str, block: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if marker in text:
        return
    target.write_text(text.rstrip() + "\n\n\n" + block.strip() + "\n", encoding="utf-8")


# Explicit control commands must outrank stale clinical history.  Previously
# #lichthuoc received +20 while an old emergency could contribute +30/+60 to
# triage, causing a deterministic medication-schedule command to be hijacked by
# historical risk scoring.
replace_once(
    "app/services/chat.py",
    '''def _detect_intent(payload: ChatRequest, normalized_text: str) -> ChatIntent:
    if payload.intent_hint != "auto":
        return payload.intent_hint

    def contains(keyword: str) -> bool:
''',
    '''def _detect_intent(payload: ChatRequest, normalized_text: str) -> ChatIntent:
    if payload.intent_hint != "auto":
        return payload.intent_hint

    # Explicit product/control syntax has deterministic user intent and must
    # never be overridden by historical clinical-risk scores from another turn.
    if "#lichthuoc" in normalized_text:
        return "schedule"

    def contains(keyword: str) -> bool:
''',
)

append_once(
    "app/tests/test_clinical_episode_orchestration.py",
    "test_explicit_schedule_command_after_clinical_history_is_not_hijacked_by_triage",
    '''
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
''',
)

print("Round-4 explicit schedule routing patch staged successfully")
