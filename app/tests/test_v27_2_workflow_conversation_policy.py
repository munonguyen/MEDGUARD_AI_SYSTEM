from types import SimpleNamespace

from app.services.workflow_conversation_policy import _followup_reply, _schedule_reply


def _payload(text: str):
    return SimpleNamespace(messages=[SimpleNamespace(role="user", content=text)])


def test_schedule_confirmation_repeats_actual_created_time() -> None:
    result = {
        "action": "create",
        "schedules": [
            {
                "medication_name": "aspirin",
                "scheduled_at": "2026-10-02T08:00:00+07:00",
                "status": "active",
            }
        ],
    }
    reply = _schedule_reply(
        "Đã thêm 1 mốc uống aspirin vào card lịch thuốc; hiện có 1 mốc đang hoạt động.",
        result,
    )
    assert "08:00" in reply


def test_different_schedule_times_produce_different_patient_replies() -> None:
    base = "Đã thêm 1 mốc uống cetirizine vào card lịch thuốc; hiện có 1 mốc đang hoạt động."
    at_20 = _schedule_reply(
        base,
        {"action": "create", "schedules": [{"scheduled_at": "2026-10-02T20:00:00+07:00", "status": "active"}]},
    )
    at_21 = _schedule_reply(
        base,
        {"action": "create", "schedules": [{"scheduled_at": "2026-10-02T21:00:00+07:00", "status": "active"}]},
    )
    assert at_20 != at_21
    assert "20:00" in at_20
    assert "21:00" in at_21


def test_followup_without_rule_does_not_expose_rule_engine_message() -> None:
    reply = _followup_reply(
        _payload("Tôi muốn đặt lịch tái khám sau đợt ho này."),
        "Không có quy tắc phù hợp để sinh mốc tái khám.",
        {"plan_available": False, "suggestions": []},
    )
    assert "Không có quy tắc phù hợp để sinh mốc tái khám" not in reply
    assert "đợt ho" in reply
    assert "ngày/giờ" in reply
    assert "tự suy đoán" in reply


def test_unmatched_followup_replies_remain_turn_specific() -> None:
    cough = _followup_reply(
        _payload("Tôi muốn đặt lịch tái khám sau đợt ho này."),
        "legacy",
        {"plan_available": False},
    )
    back = _followup_reply(
        _payload("Cho tôi đặt lịch khám nếu đau lưng không giảm sau vài ngày."),
        "legacy",
        {"plan_available": False},
    )
    assert cough != back
    assert "đợt ho" in cough
    assert "đau lưng" in back


def test_followup_with_approved_plan_preserves_service_reply() -> None:
    original = "Tạo 1 mốc theo dõi."
    assert _followup_reply(
        _payload("Tôi muốn tái khám."),
        original,
        {"plan_available": True, "suggestions": [{"scheduled_for": "2026-10-05"}]},
    ) == original
