from __future__ import annotations

import pytest

from app.services.patient_visible_response import (
    assert_benchmark_surface_is_patient_visible,
    select_patient_visible_surface,
)


def _response(*, verification_status: str, narrative: list[dict] | None = None) -> dict:
    return {
        "verification_status": verification_status,
        "intent": "triage",
        "result": {"urgency": "ROUTINE", "esi_level": 4},
        "answer": {
            "title": "Deterministic title must not win",
            "summary": "Cần thêm đánh giá lâm sàng toàn diện.",
            "key_points": ["hidden deterministic key point"],
            "next_steps": ["hidden deterministic next step"],
            "questions": ["hidden deterministic question"],
            "limitations": ["hidden deterministic limitation"],
            "narrative": narrative or [],
        },
    }


def test_verified_narrative_is_the_only_benchmark_surface() -> None:
    response = _response(
        verification_status="verified",
        narrative=[
            {"kind": "paragraph", "text": "Đây là câu trả lời Writer đã được Reviewer và Jev duyệt."},
            {"kind": "paragraph", "text": "Thông tin thứ hai vẫn thuộc canonical narrative."},
        ],
    )

    surface = select_patient_visible_surface(response)

    assert surface.source == "canonical_verified_narrative"
    assert surface.safety_urgency == "ROUTINE"
    assert surface.text == (
        "Đây là câu trả lời Writer đã được Reviewer và Jev duyệt.\n"
        "Thông tin thứ hai vẫn thuộc canonical narrative."
    )
    assert "Deterministic title" not in surface.text
    assert "Cần thêm đánh giá lâm sàng toàn diện" not in surface.text
    assert "hidden deterministic" not in surface.text


def test_legacy_question_narrative_block_is_filtered_like_frontend() -> None:
    response = _response(
        verification_status="verified",
        narrative=[
            {"kind": "paragraph", "text": "Nội dung chính đã kiểm chứng."},
            {"kind": "paragraph", "text": "Bạn cho mình biết thêm: câu hỏi legacy"},
            {
                "kind": "paragraph",
                "text": "Thông tin cần báo nhân viên y tế nếu có thể: legacy block",
            },
        ],
    )

    surface = select_patient_visible_surface(response)
    assert surface.text == "Nội dung chính đã kiểm chứng."


def test_non_verified_response_uses_deterministic_fallback_surface() -> None:
    response = _response(
        verification_status="rejected",
        narrative=[{"kind": "paragraph", "text": "Draft bị reject không được hiển thị."}],
    )

    surface = select_patient_visible_surface(response)
    assert surface.source == "deterministic_fallback"
    assert "Deterministic title must not win" in surface.text
    assert "Draft bị reject" not in surface.text


def test_benchmark_must_equal_patient_visible_surface_byte_for_byte() -> None:
    response = _response(
        verification_status="verified",
        narrative=[{"kind": "paragraph", "text": "Canonical patient response"}],
    )

    surface = assert_benchmark_surface_is_patient_visible(
        response,
        "Canonical patient response",
    )
    assert surface.is_verified_canonical is True

    with pytest.raises(ValueError, match="benchmark_surface_mismatch"):
        assert_benchmark_surface_is_patient_visible(
            response,
            "Canonical patient response\nCần thêm đánh giá lâm sàng toàn diện.",
        )


def test_verified_without_visible_narrative_fails_back_deterministically() -> None:
    response = _response(
        verification_status="verified",
        narrative=[{"kind": "paragraph", "text": "Bạn cho mình biết thêm: legacy only"}],
    )

    surface = select_patient_visible_surface(response)
    assert surface.source == "deterministic_fallback"
    assert surface.text
