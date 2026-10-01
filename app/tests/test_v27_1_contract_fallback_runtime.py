from __future__ import annotations

from app.models.chat import GroundedAnswer
from app.services.answer_agents import AnswerAgentConfig, AnswerAgentPipeline
from app.services.circuit import CircuitBreaker
from app.services.patient_visible_response import select_patient_visible_surface


class UnconfiguredProvider:
    provider_name = "unconfigured-test"

    @property
    def is_configured(self) -> bool:
        return False

    def complete(self, **_values):  # pragma: no cover - must never be called
        raise AssertionError("provider must not be called in unavailable-path regression")


def _legacy_fallback() -> GroundedAnswer:
    return GroundedAnswer(
        title="Đánh giá ban đầu: mức theo dõi thường quy",
        summary=(
            "Với các dữ kiện hiện có, bệnh cảnh đang ở mức theo dõi thường quy. "
            "Chưa thể xác định nguyên nhân chỉ từ tin nhắn."
        ),
        next_steps=["Theo dõi triệu chứng."],
        questions=["Có triệu chứng nào khác không?"],
        decision_basis="versioned_rules",
        evidence_state="bounded_result",
    )


def _pipeline() -> AnswerAgentPipeline:
    provider = UnconfiguredProvider()
    return AnswerAgentPipeline(
        config=AnswerAgentConfig(
            mode="enforced",
            research_model="medguard-clinical-answer",
            verifier_model="medguard-clinical-verifier",
        ),
        research_provider=provider,
        verifier_provider=provider,
        circuit=CircuitBreaker(error_threshold=1, min_requests=10),
    )


def test_unavailable_writer_uses_mechanical_chest_contract_not_legacy_routine_template() -> None:
    result = _pipeline().generate_response(
        fallback_answer=_legacy_fallback(),
        clinical_payload={
            "urgency": "ROUTINE",
            "emergency_flag": False,
            "red_flags": [],
            "self_care": ["Tạm nghỉ các bài tập ngực nặng và theo dõi diễn biến."],
        },
        intent="triage",
        question="Tôi hơi tức cơ ngực sau buổi tập gym tối qua, ấn vào thì đau hơn.",
        request_id="v27-fallback-chest",
    )

    assert result.agent_trace is not None
    assert result.agent_trace.status == "unavailable"
    visible = select_patient_visible_surface({
        "answer": result.model_dump(mode="json"),
        "verification_status": "unavailable",
        "result": {"urgency": "ROUTINE"},
    }).text
    lowered = visible.lower()
    assert "đánh giá ban đầu: mức theo dõi thường quy" not in lowered
    assert "với các dữ kiện hiện có, bệnh cảnh đang ở mức theo dõi thường quy" not in lowered
    assert "thành ngực" in lowered or "cơ" in lowered
    assert "ấn" in lowered or "vận động" in lowered or "sau vận động" in lowered
    assert len(result.questions) <= 1


def test_unavailable_writer_emergency_fallback_keeps_115_action_and_zero_questions() -> None:
    result = _pipeline().generate_response(
        fallback_answer=_legacy_fallback(),
        clinical_payload={
            "urgency": "EMERGENCY",
            "emergency_flag": True,
            "red_flags": ["đau ngực lan tay trái", "vã mồ hôi", "buồn nôn"],
        },
        intent="triage",
        question="Đau ngực lan xuống tay trái, vã mồ hôi và buồn nôn.",
        request_id="v27-fallback-emergency",
    )

    assert result.agent_trace is not None
    assert result.agent_trace.status == "unavailable"
    visible = select_patient_visible_surface({
        "answer": result.model_dump(mode="json"),
        "verification_status": "unavailable",
        "result": {"urgency": "EMERGENCY"},
    }).text
    assert "115" in visible
    assert result.questions == []
    assert result.display_questions == []
