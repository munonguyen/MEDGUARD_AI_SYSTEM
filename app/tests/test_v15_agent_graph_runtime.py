from __future__ import annotations

from typing import Any

import pytest

from app.models.agents import AgentDraft, AgentVerification
from app.models.chat import GroundedAnswer
from app.services import agent_graph as agent_graph_module
from app.services.adaptive_agent_runtime import AdaptiveAgentRuntime, AdaptiveAgentRuntimeConfig
from app.services.agent_graph import MedicalAgentGraph, MedicalAgentState
from app.services.agent_provider import ModelProviderError, ProviderResult
from app.services.llm_control_plane import policy_for_intent


class ModelAwareProvider:
    def __init__(self, name: str, data: Any, *, fail_models: set[str] | None = None) -> None:
        self.provider_name = name
        self.data = data
        self.fail_models = fail_models or set()
        self.calls: list[dict[str, Any]] = []

    @property
    def is_configured(self) -> bool:
        return True

    def complete(self, **values: Any) -> ProviderResult:
        self.calls.append(values)
        model = values["model"]
        if model in self.fail_models:
            raise ModelProviderError(f"simulated outage for {model}")
        return ProviderResult(
            data=self.data,
            response_id=f"{self.provider_name}-{len(self.calls)}",
            model=model,
            latency_ms=5,
        )


def _draft() -> AgentDraft:
    return AgentDraft.model_validate(
        {
            "question_analysis": {
                "interpreted_request": "Đánh giá triệu chứng.",
                "key_questions": [],
                "ambiguities": [],
                "risk_level": "low",
            },
            "evidence_claims": [],
            "narrative": [
                {
                    "kind": "paragraph",
                    "text": "Theo dõi triệu chứng và thực hiện hướng dẫn đã được xác nhận.",
                    "emphasis": [],
                    "claim_ids": [],
                    "source_ids": [],
                }
            ],
            "sources": [],
            "notes": "runtime test",
        }
    )


def _verification() -> AgentVerification:
    return AgentVerification.model_validate(
        {
            "approved": True,
            "scores": {
                "grounding": 0.98,
                "safety": 0.99,
                "completeness": 0.95,
                "clarity": 0.95,
                "citation_coverage": 0.98,
            },
            "issues": [],
            "missing_claim_ids": [],
            "unsupported_claims": [],
            "source_issues": [],
            "summary": "Đạt",
        }
    )


def _state() -> MedicalAgentState:
    answer = GroundedAnswer(
        title="Theo dõi tại nhà",
        summary="Bệnh cảnh hiện tại ở mức theo dõi.",
        key_points=[],
        next_steps=[],
        safety_notes=[],
        questions=[],
        decision_basis="versioned_rules",
        evidence_state="direct_rule_match",
    )
    return MedicalAgentState(
        request_id="req-v15-runtime",
        tenant_id="tenant-test",
        conversation_id="conv-test",
        locale="vi-VN",
        intent="triage",
        question="Tôi hơi đau lưng sau khi ngồi máy tính cả ngày",
        patient_context={"age": 24},
        policy=policy_for_intent("triage"),
        claims=[],
        tool_result={
            "version": "v12-agent-first",
            "intent": "triage",
            "clinical_result": {
                "urgency": "ROUTINE",
                "clinical_task": "acute_symptom",
                "trace": {"details": {"fact_coverage": 0.95}},
            },
        },
        answer=answer,
    )


def _graph(writer: ModelAwareProvider, reviewer: ModelAwareProvider) -> MedicalAgentGraph:
    return MedicalAgentGraph(
        research_provider=writer,
        verifier_provider=reviewer,
        research_model="writer-primary",
        verifier_model="judge-primary",
        clinical_research_model="writer-primary",
        clinical_verifier_model="judge-primary",
        prompt_version="v15-test",
        max_input_tokens=12000,
        research_max_output_tokens=1200,
        verifier_max_output_tokens=800,
        web_search_required=False,
        verifier_search_required=False,
    )


def test_writer_and_reviewer_fallback_keep_same_clinical_route(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = AdaptiveAgentRuntime(
        AdaptiveAgentRuntimeConfig(
            mode="shadow",
            standard_writer_model="writer-primary",
            writer_fallback_models=("writer-backup",),
            verifier_fallback_models=("judge-backup",),
            standard_max_input_tokens=4000,
            standard_max_output_tokens=500,
            verifier_standard_max_output_tokens=300,
        )
    )
    monkeypatch.setattr(agent_graph_module, "adaptive_agent_runtime", runtime)

    writer = ModelAwareProvider("writer", _draft(), fail_models={"writer-primary"})
    reviewer = ModelAwareProvider("reviewer", _verification(), fail_models={"judge-primary"})
    graph = _graph(writer, reviewer)
    state = _state()

    assert graph.node_writer(
        state,
        instructions="write",
        redact_question_fn=lambda value: value,
        stage_trace_fn=lambda role, provider, model, result, estimated: None,
    ) is True

    assert [call["model"] for call in writer.calls] == ["writer-primary", "writer-backup"]
    assert writer.calls[-1]["controls"].max_input_tokens == 4000
    assert writer.calls[-1]["controls"].max_output_tokens == 500
    assert state.selected_writer_model == "writer-backup"
    assert state.adaptive_route is not None
    assert state.adaptive_route.resolved_severity == "ROUTINE"

    graph.node_reviewer(
        state,
        instructions="review",
        stage_trace_fn=lambda role, provider, model, result, estimated: None,
        gate_reason_fn=lambda **kwargs: None,
    )

    assert [call["model"] for call in reviewer.calls] == ["judge-primary", "judge-backup"]
    assert reviewer.calls[-1]["controls"].max_input_tokens == 4000
    assert reviewer.calls[-1]["controls"].max_output_tokens == 300
    assert state.selected_verifier_model == "judge-backup"
    assert state.verification is not None and state.verification.approved is True
    assert state.gate_reason is None
    assert state.adaptive_route.resolved_severity == "ROUTINE"


def test_reviewer_ladder_exhaustion_fails_instead_of_bypassing_review(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = AdaptiveAgentRuntime(
        AdaptiveAgentRuntimeConfig(
            mode="shadow",
            standard_writer_model="writer-primary",
            verifier_fallback_models=("judge-backup",),
        )
    )
    monkeypatch.setattr(agent_graph_module, "adaptive_agent_runtime", runtime)

    writer = ModelAwareProvider("writer", _draft())
    reviewer = ModelAwareProvider(
        "reviewer",
        _verification(),
        fail_models={"judge-primary", "judge-backup"},
    )
    graph = _graph(writer, reviewer)
    state = _state()

    assert graph.node_writer(
        state,
        instructions="write",
        redact_question_fn=lambda value: value,
        stage_trace_fn=lambda role, provider, model, result, estimated: None,
    ) is True

    with pytest.raises(ModelProviderError):
        graph.node_reviewer(
            state,
            instructions="review",
            stage_trace_fn=lambda role, provider, model, result, estimated: None,
            gate_reason_fn=lambda **kwargs: None,
        )

    assert [call["model"] for call in reviewer.calls] == ["judge-primary", "judge-backup"]
    assert state.verification is None
