from __future__ import annotations

import inspect
from types import SimpleNamespace

from app.core.config import settings
from app.core.context import RequestContext
from app.models.agents import AnswerAgentTrace
from app.models.chat import ChatRequest
from app.services import chat
from app.services.agent_graph import _agent_inputs


def test_single_path_scope_cannot_be_bypassed_by_chat_branches():
    response_source = inspect.getsource(chat._response)
    orchestration_source = inspect.getsource(chat.orchestrate_chat)

    assert "effective_allow_agent" in response_source
    assert 'settings.agent_coverage_scope == "all"' in response_source
    assert "allow_agent=False" not in orchestration_source


def test_all_gateway_intents_are_runtime_agent_routed_when_scope_is_all(monkeypatch):
    """V27.4 runtime certification for the public single-path contract.

    Source inspection is useful but insufficient: a future refactor could retain
    the expected strings while accidentally bypassing the pipeline at runtime.
    This test executes the shared response boundary for every public intent under
    the production-style enforced/all/synchronous configuration and proves that
    each response reaches either the native clinical Writer path or the general
    Writer -> Reviewer path.
    """

    original_mode = settings.agent_mode
    original_scope = settings.agent_coverage_scope
    original_sync = settings.agent_sync_enabled
    original_background = settings.agent_background_enabled
    calls: list[tuple[str, str, str]] = []
    verified_trace = AnswerAgentTrace(mode="enforced", status="verified")

    def fake_generate_response(**values):
        calls.append(("generate_response", str(values["intent"]), "answered"))
        return values["fallback_answer"].model_copy(
            update={"agent_trace": verified_trace}
        )

    def fake_enhance(**values):
        answer = values["answer"]
        calls.append(("enhance", str(values["intent"]), answer.decision_basis))
        return answer.model_copy(update={"agent_trace": verified_trace})

    monkeypatch.setattr(chat.answer_agent_pipeline, "generate_response", fake_generate_response)
    monkeypatch.setattr(chat.answer_agent_pipeline, "enhance", fake_enhance)

    try:
        object.__setattr__(settings, "agent_mode", "enforced")
        object.__setattr__(settings, "agent_coverage_scope", "all")
        object.__setattr__(settings, "agent_sync_enabled", True)
        object.__setattr__(settings, "agent_background_enabled", False)

        for index, intent in enumerate(sorted(chat._ALL_GATEWAY_INTENTS)):
            payload = ChatRequest(
                conversation_id=f"v27-4-coverage-{intent}",
                messages=[
                    {
                        "role": "user",
                        "content": f"Runtime coverage certification for {intent}",
                    }
                ],
            )
            response = chat._response(
                payload,
                RequestContext(
                    request_id=f"req-v27-4-{index}",
                    tenant_id="tenant-demo",
                    idempotency_key=f"idem-v27-4-{index}",
                ),
                status="answered",
                intent=intent,
                reply=f"Bounded {intent} result.",
            )

            assert response.verification_status == "verified", intent
            assert response.answer_origin == "gateway_verified", intent
            assert response.orchestrator == "agent_verified", intent

        routed_intents = {intent for _path, intent, _basis in calls}
        assert routed_intents == set(chat._ALL_GATEWAY_INTENTS)

        clinical_generate_intents = {
            intent for path, intent, _basis in calls if path == "generate_response"
        }
        assert clinical_generate_intents == {"triage", "safety"}
    finally:
        object.__setattr__(settings, "agent_mode", original_mode)
        object.__setattr__(settings, "agent_coverage_scope", original_scope)
        object.__setattr__(settings, "agent_sync_enabled", original_sync)
        object.__setattr__(settings, "agent_background_enabled", original_background)


def test_non_answered_public_responses_still_reach_agent_gateway(monkeypatch):
    """Coverage=all includes clarification and unsupported responses as well."""

    original_mode = settings.agent_mode
    original_scope = settings.agent_coverage_scope
    original_sync = settings.agent_sync_enabled
    original_background = settings.agent_background_enabled
    calls: list[tuple[str, str]] = []
    verified_trace = AnswerAgentTrace(mode="enforced", status="verified")

    def fake_enhance(**values):
        calls.append((str(values["intent"]), values["answer"].decision_basis))
        return values["answer"].model_copy(update={"agent_trace": verified_trace})

    def unexpected_generate_response(**_values):
        raise AssertionError("non-answered responses should use the bounded enhance path")

    monkeypatch.setattr(chat.answer_agent_pipeline, "enhance", fake_enhance)
    monkeypatch.setattr(
        chat.answer_agent_pipeline,
        "generate_response",
        unexpected_generate_response,
    )

    try:
        object.__setattr__(settings, "agent_mode", "enforced")
        object.__setattr__(settings, "agent_coverage_scope", "all")
        object.__setattr__(settings, "agent_sync_enabled", True)
        object.__setattr__(settings, "agent_background_enabled", False)

        needs_payload = ChatRequest(
            conversation_id="v27-4-needs-info",
            messages=[{"role": "user", "content": "Tôi thấy không ổn."}],
        )
        needs_response = chat._response(
            needs_payload,
            RequestContext(
                request_id="req-v27-4-needs-info",
                tenant_id="tenant-demo",
                idempotency_key="idem-v27-4-needs-info",
            ),
            status="needs_information",
            intent="triage",
            reply="Cần thêm một dữ kiện để đánh giá.",
            required_fields=["request_detail"],
        )

        unsupported_payload = ChatRequest(
            conversation_id="v27-4-unsupported",
            messages=[{"role": "user", "content": "Yêu cầu ngoài phạm vi."}],
        )
        unsupported_response = chat._response(
            unsupported_payload,
            RequestContext(
                request_id="req-v27-4-unsupported",
                tenant_id="tenant-demo",
                idempotency_key="idem-v27-4-unsupported",
            ),
            status="unsupported",
            intent="general",
            reply="Yêu cầu này nằm ngoài phạm vi hỗ trợ hiện tại.",
        )

        assert needs_response.verification_status == "verified"
        assert needs_response.answer_origin == "gateway_verified"
        assert unsupported_response.verification_status == "verified"
        assert unsupported_response.answer_origin == "gateway_verified"
        assert {intent for intent, _basis in calls} == {"triage", "general"}
        assert any(
            intent == "triage" and basis == "insufficient_information"
            for intent, basis in calls
        )
    finally:
        object.__setattr__(settings, "agent_mode", original_mode)
        object.__setattr__(settings, "agent_coverage_scope", original_scope)
        object.__setattr__(settings, "agent_sync_enabled", original_sync)
        object.__setattr__(settings, "agent_background_enabled", original_background)


def test_legacy_presentation_prose_is_hidden_from_writer_and_reviewer():
    state = SimpleNamespace(
        intent="general",
        question="Tôi cần làm gì tiếp theo?",
        patient_context={"age": 30, "patient_ref": "PHI-MUST-NOT-PASS"},
        claims=[
            {"id": "title_1", "category": "title", "text": "Legacy title", "locked": False},
            {"id": "summary_2", "category": "summary", "text": "Legacy summary", "locked": False},
            {"id": "safety_3", "category": "safety", "text": "Safety constraint", "locked": True},
        ],
        tool_result={
            "title": "Legacy title",
            "summary": "Legacy summary",
            "narrative": [{"text": "Legacy patient-facing prose"}],
            "key_points": ["Structured finding"],
            "next_steps": ["Structured action"],
            "safety_notes": ["Safety constraint"],
            "questions": ["One clarification?"],
            "decision_basis": "versioned_rules",
            "evidence_state": "bounded_result",
            "requires_human_review": False,
        },
    )

    claims, envelope = _agent_inputs(state)  # type: ignore[arg-type]

    assert {claim["category"] for claim in claims} == {"safety"}
    assert "title" not in envelope
    assert "summary" not in envelope
    assert "narrative" not in envelope
    assert envelope["key_points"] == ["Structured finding"]
    assert envelope["next_steps"] == ["Structured action"]
    assert envelope["patient_context"] == {"age": 30}
    assert envelope["communication_contract"]["compose_original_response"] is True
    assert envelope["communication_contract"]["reviewer_is_non_authoring"] is True


def test_native_agent_first_envelope_is_not_reduced():
    native = {
        "version": "v12-agent-first",
        "intent": "triage",
        "clinical_result": {"urgency": "URGENT"},
    }
    expected_claims = [
        {"id": "summary_1", "category": "summary", "text": "URGENT", "locked": False}
    ]
    state = SimpleNamespace(
        intent="triage",
        question="Đau nhiều",
        patient_context={},
        claims=expected_claims,
        tool_result=native,
    )

    claims, envelope = _agent_inputs(state)  # type: ignore[arg-type]

    assert claims == expected_claims
    assert envelope is native
