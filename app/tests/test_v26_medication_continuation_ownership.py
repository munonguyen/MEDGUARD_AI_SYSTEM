from __future__ import annotations

import pytest

from app.services.conversation_continuation import resolve_conversation_continuation


@pytest.mark.parametrize(
    ("messages", "reason"),
    [
        (
            [
                ("user", "Tôi bị nổi mề đay sau khi dùng penicillin trước đây."),
                ("assistant", "Bạn nên tránh tự dùng lại thuốc gây dị ứng."),
                ("user", "Tôi chưa uống viên amoxicillin nào, có nên thử nửa viên xem sao không?"),
            ],
            "explicit_medication_self_management",
        ),
        (
            [
                ("user", "Tôi đã uống nhầm thuốc và đang lo có quá liều."),
                ("assistant", "Không tự dùng thêm thuốc trong lúc chờ đánh giá."),
                ("user", "Tôi có nên tự gây nôn để đẩy thuốc ra không?"),
            ],
            "explicit_medication_self_management",
        ),
        (
            [
                ("user", "Tôi đau đầu nhẹ sau khi nhìn màn hình lâu."),
                ("assistant", "Có thể theo dõi thêm nếu triệu chứng vẫn nhẹ."),
                ("user", "Chuyển việc khác: tôi đang dùng warfarin, có dùng ibuprofen được không?"),
            ],
            "explicit_medication_self_management",
        ),
    ],
)
def test_current_turn_medication_safety_owns_domain_despite_history(
    messages: list[tuple[str, str]],
    reason: str,
) -> None:
    resolution = resolve_conversation_continuation(messages)

    assert resolution is not None
    assert resolution.intent == "safety"
    assert resolution.reason == reason
    assert resolution.confidence >= 0.99


def test_schedule_command_keeps_workflow_ownership_over_medication_name() -> None:
    resolution = resolve_conversation_continuation(
        [
            ("user", "Tôi đang dùng aspirin."),
            ("assistant", "Đã ghi nhận thông tin thuốc."),
            ("user", "Tạo card lịch uống aspirin lúc 19:00 mỗi ngày."),
        ]
    )

    assert resolution is None
