from __future__ import annotations

from typing import Any

from app.models.agents import AnswerAgentTrace
from app.models.chat import GroundedAnswer
from app.services.answer_agents import AnswerAgentConfig, AnswerAgentPipeline
from app.services.circuit import CircuitBreaker


class _ConfiguredProvider:
    provider_name = "v27-test-provider"

    @property
    def is_configured(self) -> bool:
        return True

    def complete(self, **_values: Any):  # pragma: no cover - _execute is intercepted
        raise AssertionError("provider should not be called in contract-routing test")


def _pipeline() -> AnswerAgentPipeline:
    return AnswerAgentPipeline(
        config=AnswerAgentConfig(
            mode="enforced",
            research_model="writer-test",
            verifier_model="reviewer-test",
            web_search_required=False,
            verifier_search_required=False,
            total_timeout_seconds=2.0,
        ),
        research_provider=_ConfiguredProvider(),
        verifier_provider=_ConfiguredProvider(),
        circuit=CircuitBreaker(error_threshold=1, min_requests=10),
    )


def _needs_information_answer() -> GroundedAnswer:
    return GroundedAnswer(
        title="Cần thêm thông tin để hỗ trợ bạn",
        summary="Mình chưa có đủ dữ kiện để đưa ra hướng dẫn an toàn.",
        questions=["Bạn mô tả rõ hơn triệu chứng được không?"],
        decision_basis="insufficient_information",
        evidence_state="partial_input",
        requires_human_review=True,
    )


def test_triage_needs_information_uses_same_structured_clinical_contract(monkeypatch) -> None:
    instance = _pipeline()
    captured: dict[str, Any] = {}

    def fake_execute(**kwargs: Any) -> GroundedAnswer:
        captured.update(kwargs)
        return kwargs["answer"].model_copy(
            update={
                "agent_trace": AnswerAgentTrace(
                    mode="enforced",
                    status="verified",
                )
            }
        )

    monkeypatch.setattr(instance, "_execute", fake_execute)

    result = instance.enhance(
        answer=_needs_information_answer(),
        intent="triage",
        question="Tôi đau các khớp tay mấy hôm nay.",
        request_id="req-v27-needs-info",
        tenant_id="tenant-test",
        conversation_id="conv-test",
    )

    assert result.agent_trace is not None
    assert result.agent_trace.status == "verified"
    envelope = captured["tool_result_override"]
    claims = captured["claims_override"]

    assert envelope["version"] == "v27-semantic-authority"
    assert envelope["assessment_state"] == "INSUFFICIENT_CONTEXT"
    assert envelope["clinical_episode"]["chief_domain"] == "peripheral_joint"
    assert envelope["reasoning_frame"]["next_question_key"] == "joint_inflammation_pattern"
    assert envelope["communication_contract"]["response_must_remain_relevant_to_active_episode"] is True

    claim_text = " ".join(item["text"] for item in claims)
    assert "Mình chưa có đủ dữ kiện để đưa ra hướng dẫn an toàn." not in claim_text
    assert "Bạn mô tả rõ hơn triệu chứng được không?" not in claim_text
    assert "sưng/nóng/đỏ" in claim_text


def test_nonclinical_needs_information_keeps_legacy_enhance_contract(monkeypatch) -> None:
    instance = _pipeline()
    captured: dict[str, Any] = {}

    def fake_execute(**kwargs: Any) -> GroundedAnswer:
        captured.update(kwargs)
        return kwargs["answer"].model_copy(
            update={
                "agent_trace": AnswerAgentTrace(
                    mode="enforced",
                    status="verified",
                )
            }
        )

    monkeypatch.setattr(instance, "_execute", fake_execute)
    answer = _needs_information_answer()

    instance.enhance(
        answer=answer,
        intent="general",
        question="Tôi muốn hỏi một việc nhưng chưa nói rõ.",
        request_id="req-v27-general",
        tenant_id="tenant-test",
        conversation_id="conv-general",
    )

    assert captured["claims_override"] is None
    assert captured["tool_result_override"] is None
