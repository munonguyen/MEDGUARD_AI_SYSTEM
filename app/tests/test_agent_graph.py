"""Tests for 3-Tier Agent Architecture: Harness ⊃ Graph ⊃ Loop with Gateway preservation."""

from __future__ import annotations

from typing import Any

import pytest

from app.core.observability import metrics
from app.models.agents import AgentDraft, AgentVerification
from app.models.chat import AnswerNarrativeBlock, GroundedAnswer
from app.services.agent_graph import MedicalAgentGraph, MedicalAgentState
from app.services.agent_provider import ProviderResult
from app.services.answer_agents import _claims, _gate_reason, _redact_question, _stage
from app.services.llm_control_plane import policy_for_intent

TRUSTED_URL = "https://www.nice.org.uk/guidance/cg150/chapter/recommendations"


class SequenceFakeProvider:
    """Mock provider that returns a sequence of predetermined responses for testing loops."""

    def __init__(self, name: str, responses: list[Any], citations=(), queries=()) -> None:
        self.provider_name = name
        self.responses = list(responses)
        self.citations = tuple(citations)
        self.queries = tuple(queries)
        self.calls: list[dict[str, Any]] = []

    @property
    def is_configured(self) -> bool:
        return True

    def complete(self, **values):
        self.calls.append(values)
        data = self.responses.pop(0) if self.responses else {}
        return ProviderResult(
            data=data,
            response_id=f"{self.provider_name}-resp-{len(self.calls)}",
            model=values["model"],
            latency_ms=10,
            citations=self.citations,
            search_queries=self.queries,
        )


def make_baseline() -> GroundedAnswer:
    return GroundedAnswer(
        title="Đánh giá hiện tại",
        summary="Chưa đủ dữ kiện để xác định nguyên nhân.",
        key_points=["Dấu hiệu được nhận diện: đau đầu"],
        next_steps=["Theo dõi triệu chứng và nghỉ ngơi."],
        safety_notes=["Đi cấp cứu ngay nếu đau đột ngột dữ dội."],
        questions=["Cơn đau bắt đầu từ lúc nào?"],
        decision_basis="versioned_rules",
        evidence_state="direct_rule_match",
        narrative=[AnswerNarrativeBlock(text="Bản deterministic.")],
    )


def make_draft(extra_claim: str | None = None) -> AgentDraft:
    narrative_text = "Đánh giá hiện tại. Chưa đủ dữ kiện để xác định nguyên nhân. Hướng dẫn chính thống khuyến nghị theo dõi."
    if extra_claim:
        narrative_text += f" {extra_claim}"

    return AgentDraft.model_validate(
        {
            "question_analysis": {
                "interpreted_request": "Đánh giá triệu chứng đau đầu.",
                "key_questions": ["Có nguy hiểm không?"],
                "ambiguities": [],
                "risk_level": "medium",
            },
            "evidence_claims": [
                {
                    "claim_id": "ext_headache_guidance",
                    "text": "Hướng dẫn chính thống khuyến nghị theo dõi.",
                    "source_ids": ["src_nice"],
                }
            ],
            "narrative": [
                {
                    "kind": "paragraph",
                    "text": narrative_text,
                    "emphasis": ["Đánh giá hiện tại"],
                    "claim_ids": ["title_1", "summary_2", "ext_headache_guidance"],
                    "source_ids": ["src_nice"],
                },
                {
                    "kind": "caution",
                    "text": "Dấu hiệu được nhận diện: đau đầu Theo dõi triệu chứng và nghỉ ngơi. Đi cấp cứu ngay nếu đau đột ngột dữ dội. Cơn đau bắt đầu từ lúc nào?",
                    "emphasis": ["Đi cấp cứu ngay nếu đau đột ngột dữ dội."],
                    "claim_ids": ["finding_3", "action_4", "safety_5", "question_6"],
                    "source_ids": ["src_nice"],
                },
            ],
            "sources": [
                {
                    "source_id": "src_nice",
                    "title": "Headaches in over 12s",
                    "publisher": "NICE",
                    "url": TRUSTED_URL,
                    "authority_tier": "guideline_or_regulator",
                    "supports_claim_ids": ["title_1", "summary_2", "finding_3", "action_4", "safety_5", "question_6", "ext_headache_guidance"],
                }
            ],
            "notes": "Draft kiểm thử",
        }
    )


def make_verification(*, approved: bool, unsupported: list[str] | None = None, grounding: float = 0.95) -> AgentVerification:
    return AgentVerification.model_validate(
        {
            "approved": approved,
            "scores": {
                "grounding": grounding,
                "safety": 0.98,
                "completeness": 0.92,
                "clarity": 0.95,
                "citation_coverage": 0.95,
            },
            "issues": [] if approved else ["Phát hiện nhận định chưa có căn cứ"],
            "missing_claim_ids": [],
            "unsupported_claims": unsupported or [],
            "source_issues": [],
            "summary": "Đạt" if approved else "Không đạt kiểm định",
        }
    )


def test_agent_graph_state_initialization():
    answer = make_baseline()
    policy = policy_for_intent("triage")
    claims = _claims(answer, "triage")

    state = MedicalAgentState(
        request_id="req-test-1",
        tenant_id="test-tenant",
        conversation_id="conv-test-1",
        locale="vi-VN",
        intent="triage",
        question="Tôi bị đau đầu dữ dội",
        patient_context={},
        policy=policy,
        claims=claims,
        tool_result=answer.model_dump(mode="json"),
        answer=answer,
    )

    assert state.iteration == 0
    assert state.status == "researching"
    assert len(state.feedback_history) == 0


def test_agent_graph_self_correction_loop_on_verifier_feedback():
    """Verifier rejects round 1 with unsupported claim, gives feedback, Writer fixes it on round 2, Verifier approves."""
    # Round 1: draft has an unsupported claim -> Verifier rejects
    # Round 2: draft is clean -> Verifier approves
    draft_v1 = make_draft(extra_claim="Thuốc này chữa khỏi hoàn toàn trong 1 giờ.")
    draft_v2 = make_draft()

    verification_v1 = make_verification(approved=False, unsupported=["Thuốc này chữa khỏi hoàn toàn trong 1 giờ."])
    verification_v2 = make_verification(approved=True)

    research_provider = SequenceFakeProvider("gemini-answer", [draft_v1, draft_v2], citations=(TRUSTED_URL,), queries=("headache",))
    verifier_provider = SequenceFakeProvider("gemini-verifier", [verification_v1, verification_v2], citations=(TRUSTED_URL,))

    graph = MedicalAgentGraph(
        research_provider=research_provider,
        verifier_provider=verifier_provider,
        research_model="gemini-3.8-flash",
        verifier_model="gemini-3.1-pro-preview",
        prompt_version="2026-09-09",
        max_input_tokens=12000,
        research_max_output_tokens=2400,
        verifier_max_output_tokens=1800,
        max_iterations=2,
    )

    answer = make_baseline()
    policy = policy_for_intent("triage")
    state = MedicalAgentState(
        request_id="req-loop-test",
        tenant_id="test-tenant",
        conversation_id="conv-loop",
        locale="vi-VN",
        intent="triage",
        question="Tôi bị đau đầu",
        patient_context={},
        policy=policy,
        claims=_claims(answer, "triage"),
        tool_result=answer.model_dump(mode="json"),
        answer=answer,
    )

    # 1. Researcher Node
    graph.node_researcher(state)
    assert len(state.retrieved_chunks) > 0

    # 2. Loop iteration 0: Writer -> Reviewer -> REVISE
    writer_ok = graph.node_writer(state, instructions="Research", redact_question_fn=_redact_question, stage_trace_fn=_stage)
    assert writer_ok is True
    graph.node_reviewer(state, instructions="Verify", stage_trace_fn=_stage, gate_reason_fn=_gate_reason)
    decision = graph.route_decision(state)
    assert decision == "REVISE"
    assert state.iteration == 1
    assert len(state.feedback_history) == 1
    assert "Loại bỏ hoặc bổ sung dẫn chứng" in state.feedback_history[0]

    # 3. Loop iteration 1: Writer receives feedback -> Reviewer approves -> COMPLETE
    writer_ok2 = graph.node_writer(state, instructions="Research", redact_question_fn=_redact_question, stage_trace_fn=_stage)
    assert writer_ok2 is True
    # Verify feedback was injected into research_payload for Writer
    assert "verifier_feedback" in research_provider.calls[-1]["payload"]

    graph.node_reviewer(state, instructions="Verify", stage_trace_fn=_stage, gate_reason_fn=_gate_reason)
    decision2 = graph.route_decision(state)
    assert decision2 == "COMPLETE"
    assert state.status == "verified"
    assert state.gate_reason is None


def test_agent_graph_halting_condition_after_max_iterations():
    """Verifier rejects persistently -> graph stops at max_iterations=2 and falls back."""
    draft_always_bad = make_draft(extra_claim="Claim không kiểm chứng được.")
    verification_always_reject = make_verification(approved=False, unsupported=["Claim không kiểm chứng được."])

    research_provider = SequenceFakeProvider("gemini-answer", [draft_always_bad, draft_always_bad, draft_always_bad], citations=(TRUSTED_URL,))
    verifier_provider = SequenceFakeProvider("gemini-verifier", [verification_always_reject, verification_always_reject, verification_always_reject], citations=(TRUSTED_URL,))

    graph = MedicalAgentGraph(
        research_provider=research_provider,
        verifier_provider=verifier_provider,
        research_model="gemini-3.8-flash",
        verifier_model="gemini-3.1-pro-preview",
        prompt_version="2026-09-09",
        max_input_tokens=12000,
        research_max_output_tokens=2400,
        verifier_max_output_tokens=1800,
        max_iterations=2,
    )

    answer = make_baseline()
    policy = policy_for_intent("triage")
    state = MedicalAgentState(
        request_id="req-halt-test",
        tenant_id="test-tenant",
        conversation_id="conv-halt",
        locale="vi-VN",
        intent="triage",
        question="Tôi bị đau đầu",
        patient_context={},
        policy=policy,
        claims=_claims(answer, "triage"),
        tool_result=answer.model_dump(mode="json"),
        answer=answer,
    )

    graph.node_researcher(state)

    # Iteration 0
    graph.node_writer(state, instructions="Research", redact_question_fn=_redact_question, stage_trace_fn=_stage)
    graph.node_reviewer(state, instructions="Verify", stage_trace_fn=_stage, gate_reason_fn=_gate_reason)
    d1 = graph.route_decision(state)
    assert d1 == "REVISE"
    assert state.iteration == 1

    # Iteration 1
    graph.node_writer(state, instructions="Research", redact_question_fn=_redact_question, stage_trace_fn=_stage)
    graph.node_reviewer(state, instructions="Verify", stage_trace_fn=_stage, gate_reason_fn=_gate_reason)
    d2 = graph.route_decision(state)
    assert d2 == "REVISE"
    assert state.iteration == 2

    # Iteration 2 (Reached max_iterations -> must FALLBACK)
    graph.node_writer(state, instructions="Research", redact_question_fn=_redact_question, stage_trace_fn=_stage)
    graph.node_reviewer(state, instructions="Verify", stage_trace_fn=_stage, gate_reason_fn=_gate_reason)
    d3 = graph.route_decision(state)
    assert d3 == "FALLBACK"
    assert state.status == "fallback"
