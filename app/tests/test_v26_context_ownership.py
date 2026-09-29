from __future__ import annotations

from app.services.conversation_continuation import resolve_conversation_continuation


def _resolve(*user_turns: str):
    messages: list[tuple[str, str]] = []
    for index, text in enumerate(user_turns):
        messages.append(("user", text))
        if index < len(user_turns) - 1:
            messages.append(("assistant", "Đã ghi nhận."))
    return resolve_conversation_continuation(messages)


def test_direct_glucose_measurement_owns_turn_over_prior_dizziness() -> None:
    resolution = _resolve(
        "Tôi hơi chóng mặt khi đứng lên nhanh.",
        "Đường huyết máy đo là 74 mg/dL.",
    )
    assert resolution is not None
    assert resolution.intent == "monitoring"
    assert resolution.reason == "explicit_glucose_measurement"


def test_direct_glucose_measurement_starts_monitoring_without_history() -> None:
    resolution = _resolve("Đường huyết máy đo là 72 mg/dL.")
    assert resolution is not None
    assert resolution.intent == "monitoring"
    assert "Đường huyết" in (resolution.augmented_latest or "")


def test_cross_intent_warfarin_ibuprofen_question_routes_to_safety() -> None:
    resolution = _resolve(
        "Tôi hơi đau đầu sau khi làm việc máy tính.",
        "Chuyển việc khác: tôi đang dùng warfarin, có dùng ibuprofen được không?",
    )
    assert resolution is not None
    assert resolution.intent == "safety"


def test_half_tablet_self_trial_routes_to_safety() -> None:
    resolution = _resolve(
        "Tôi từng dị ứng penicillin.",
        "Tôi chưa uống viên amoxicillin nào, có nên thử nửa viên xem sao không?",
    )
    assert resolution is not None
    assert resolution.intent == "safety"


def test_inducing_vomiting_after_medication_ingestion_routes_to_safety() -> None:
    resolution = _resolve(
        "Tôi lỡ uống nhầm gấp đôi thuốc của mình.",
        "Tôi có nên tự gây nôn để đẩy thuốc ra không?",
    )
    assert resolution is not None
    assert resolution.intent == "safety"


def test_schedule_command_still_has_precedence_over_medication_words() -> None:
    resolution = _resolve(
        "Tôi đang dùng aspirin.",
        "Tạo card nhắc tôi uống aspirin mỗi ngày lúc 20:00.",
    )
    assert resolution is None
