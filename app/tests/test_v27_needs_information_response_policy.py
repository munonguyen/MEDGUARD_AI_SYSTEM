from __future__ import annotations

from types import SimpleNamespace

from app.core.context import RequestContext
from app.models.agents import AnswerAgentTrace
from app.models.chat import ChatContext, ChatMessage, ChatRequest, GroundedAnswer
from app.services import chat


class _FakePipeline:
    def __init__(self) -> None:
        self.generate_calls: list[dict] = []
        self.enhance_calls: list[dict] = []

    def generate_response(self, **kwargs):
        self.generate_calls.append(kwargs)
        answer: GroundedAnswer = kwargs["fallback_answer"]
        return answer.model_copy(
            update={
                "agent_trace": AnswerAgentTrace(
                    mode="enforced",
                    status="verified",
                )
            }
        )

    def enhance(self, **kwargs):
        self.enhance_calls.append(kwargs)
        raise AssertionError("clinical needs_information must not use legacy enhance()")


def _payload(text: str) -> ChatRequest:
    return ChatRequest(
        conversation_id="v27-needs-info",
        messages=[ChatMessage(role="user", content=text)],
        context=ChatContext(),
    )


def _ctx() -> RequestContext:
    return RequestContext(
        request_id="req-v27-needs-info",
        tenant_id="tenant-v27",
        idempotency_key="idem-v27-needs-info",
    )


def test_safety_needs_information_uses_agent_first_clinical_contract(monkeypatch) -> None:
    pipeline = _FakePipeline()
    monkeypatch.setattr(chat, "answer_agent_pipeline", pipeline)
    monkeypatch.setattr(chat.settings, "agent_mode", "enforced")
    monkeypatch.setattr(chat.settings, "agent_coverage_scope", "all")
    monkeypatch.setattr(chat.settings, "agent_sync_enabled", True)
    monkeypatch.setattr(chat.settings, "agent_background_enabled", False)

    response = chat._response(
        _payload("Tôi muốn kiểm tra thuốc này có dùng cùng thuốc đang uống được không"),
        _ctx(),
        status="needs_information",
        intent="safety",
        reply="Tôi cần tên thuốc đang cân nhắc để kiểm tra.",
        required_fields=["proposed_medications"],
        extracted={"current_medications": ["warfarin"]},
        result=None,
        allow_agent=True,
    )

    assert len(pipeline.generate_calls) == 1
    assert pipeline.enhance_calls == []
    call = pipeline.generate_calls[0]
    assert call["clinical_payload"]["_response_status"] == "needs_information"
    assert call["clinical_payload"]["required_fields"] == ["proposed_medications"]
    assert response.status == "needs_information"
    assert response.verification_status == "verified"
    assert response.answer_origin == "gateway_verified"


def test_low_confidence_clinical_task_needs_information_uses_same_path(monkeypatch) -> None:
    pipeline = _FakePipeline()
    monkeypatch.setattr(chat, "answer_agent_pipeline", pipeline)
    monkeypatch.setattr(chat.settings, "agent_mode", "enforced")
    monkeypatch.setattr(chat.settings, "agent_coverage_scope", "all")
    monkeypatch.setattr(chat.settings, "agent_sync_enabled", True)
    monkeypatch.setattr(chat.settings, "agent_background_enabled", False)

    response = chat._response(
        _payload("Giúp tôi đọc xét nghiệm này"),
        _ctx(),
        status="needs_information",
        intent="general",
        reply="Cần thêm giá trị xét nghiệm và đơn vị.",
        required_fields=["request_detail"],
        extracted={"clinical_task": "LAB_INTERPRETATION"},
        result={
            "clinical_task": "LAB_INTERPRETATION",
            "confidence": 0.4,
        },
        allow_agent=True,
    )

    assert len(pipeline.generate_calls) == 1
    assert pipeline.enhance_calls == []
    assert response.status == "needs_information"


def test_nonclinical_needs_information_keeps_normal_gateway_policy(monkeypatch) -> None:
    pipeline = _FakePipeline()

    # Non-clinical coverage still belongs to the normal V14 policy. For this
    # focused test disable coverage so no gateway call is expected at all.
    monkeypatch.setattr(chat, "answer_agent_pipeline", pipeline)
    monkeypatch.setattr(chat.settings, "agent_mode", "disabled")
    monkeypatch.setattr(chat.settings, "agent_coverage_scope", "all")
    monkeypatch.setattr(chat.settings, "agent_sync_enabled", False)
    monkeypatch.setattr(chat.settings, "agent_background_enabled", False)

    response = chat._response(
        _payload("Xuất FHIR"),
        _ctx(),
        status="needs_information",
        intent="fhir",
        reply="Cần kết quả trước đó và mã hồ sơ.",
        required_fields=["last_result", "patient_ref"],
    )

    assert pipeline.generate_calls == []
    assert pipeline.enhance_calls == []
    assert response.status == "needs_information"
