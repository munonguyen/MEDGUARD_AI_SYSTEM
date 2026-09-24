from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.models.agents import (
    AgentDraft,
    AgentEvidenceClaim,
    AgentEvidenceSource,
    AgentNarrativeBlock,
    AgentQuestionAnalysis,
    AgentVerification,
    VerificationScores,
)
from app.models.chat import AnswerAssurance, AnswerNarrativeBlock, ChatIntent, GroundedAnswer
from app.services.agent_graph import MedicalAgentGraph, MedicalAgentState
from app.services.answer_agents import (
    _CLINICAL_RESEARCH_INSTRUCTIONS,
    _CLINICAL_VERIFIER_INSTRUCTIONS,
    _PHARMA_RESEARCH_INSTRUCTIONS,
    _PHARMA_VERIFIER_INSTRUCTIONS,
    AnswerAgentConfig,
    AnswerAgentPipeline,
)
from app.services.circuit import CircuitBreaker
from app.services.knowledge_retriever import (
    _CLINICAL_DOCS,
    _PHARMA_DOCS,
    knowledge_retriever,
    resolve_domain,
)
from app.services.llm_control_plane import policy_for_intent


def test_resolve_domain_classification() -> None:
    """Test accurate classification into clinical vs pharmacology branches."""
    # Intent-driven resolution
    assert resolve_domain("triage", "Tôi bị sốt cao") == "clinical"
    assert resolve_domain("monitoring", "Huyết áp của tôi là 140/90") == "clinical"
    assert resolve_domain("followup", "Hôm nay tôi đã bớt mệt hơn") == "clinical"
    assert resolve_domain("safety", "Uống thuốc này có an toàn không?") == "pharmacology"
    assert resolve_domain("pharmacy", "Tìm hiệu thuốc bán Amoxicillin") == "pharmacology"
    assert resolve_domain("authenticity", "Quét mã vạch thuốc Aspirin") == "pharmacology"

    # Context & keyword-driven resolution when intent is ambiguous
    assert resolve_domain(None, "Tôi bị đau đầu sau khi thức dậy") == "clinical"
    assert resolve_domain(None, "Đau thắt ngực lan ra cánh tay trái") == "clinical"
    assert resolve_domain(None, "Tôi có thể uống Paracetamol kèm Decolgen không?") == "pharmacology"
    assert resolve_domain(None, "Tương tác giữa Aspirin và Warfarin là gì?") == "pharmacology"
    assert resolve_domain(None, "Liều dùng tối đa của Ibuprofen trong ngày?") == "pharmacology"


def test_knowledge_retriever_domain_routing() -> None:
    """Test that domain filtering prioritizes domain-relevant documents."""
    clinical_chunks = knowledge_retriever.retrieve("đau đầu", domain="clinical", top_k=5)
    assert len(clinical_chunks) > 0
    assert any(c.doc_name in _CLINICAL_DOCS for c in clinical_chunks)

    pharma_chunks = knowledge_retriever.retrieve("paracetamol", domain="pharmacology", top_k=5)
    assert len(pharma_chunks) > 0
    assert any(c.doc_name in _PHARMA_DOCS for c in pharma_chunks)


def test_agent_graph_domain_model_and_prompt_routing() -> None:
    """Test that MedicalAgentGraph routes to specialized models and prompts per domain."""
    mock_research_provider = MagicMock()
    mock_verifier_provider = MagicMock()

    graph = MedicalAgentGraph(
        research_provider=mock_research_provider,
        verifier_provider=mock_verifier_provider,
        research_model="medguard-answer",
        verifier_model="medguard-verifier",
        clinical_research_model="medguard-clinical-answer",
        clinical_verifier_model="medguard-clinical-verifier",
        pharma_research_model="medguard-pharma-answer",
        pharma_verifier_model="medguard-pharma-verifier",
        prompt_version="2026-09-09",
        max_input_tokens=10000,
        research_max_output_tokens=2000,
        verifier_max_output_tokens=1500,
    )

    # 1. Clinical State
    clinical_state = MedicalAgentState(
        request_id="req-1",
        tenant_id="test",
        conversation_id="c-1",
        locale="vi-VN",
        intent="triage",
        question="Tôi bị nhức đầu sáng nay",
        patient_context={},
        policy=policy_for_intent("triage"),
        claims=[{"id": "finding_1", "category": "finding", "text": "Đau đầu nhẹ", "required": True, "locked": True}],
        tool_result={},
        answer=GroundedAnswer(
            title="Đau đầu",
            summary="Theo dõi nghỉ ngơi",
            key_points=["Đau đầu nhẹ"],
            next_steps=["Nghỉ ngơi"],
            safety_notes=["Đi khám nếu đau dữ dội"],
            questions=["Đau từ lúc nào?"],
            decision_basis="versioned_rules",
            evidence_state="direct_rule_match",
            narrative=[AnswerNarrativeBlock(text="Bản deterministic.")],
        ),
        domain="clinical",
    )

    # Mock provider response for writer
    draft_obj = AgentDraft(
        question_analysis=AgentQuestionAnalysis(
            interpreted_request="Đau đầu sáng nay",
            key_questions=["Đau bao lâu?"],
            ambiguities=[],
            risk_level="low",
        ),
        evidence_claims=[],
        narrative=[
            AgentNarrativeBlock(
                kind="paragraph",
                text="Bạn đang có triệu chứng Đau đầu nhẹ.",
                emphasis=["Đau đầu nhẹ"],
                claim_ids=["finding_1"],
                source_ids=["src_1"],
            )
        ],
        sources=[
            AgentEvidenceSource(
                source_id="src_1",
                title="Hướng dẫn đau đầu",
                publisher="WHO",
                url="https://who.int/guideline",
                authority_tier="guideline_or_regulator",
                supports_claim_ids=["finding_1"],
            )
        ],
        notes="Non-diagnostic",
    )
    mock_gen = MagicMock()
    mock_gen.data = draft_obj.model_dump()
    mock_gen.citations = ("https://who.int/guideline",)
    mock_gen.search_queries = ("who headache",)
    mock_gen.latency_ms = 100
    mock_gen.input_tokens = 200
    mock_gen.output_tokens = 100
    mock_gen.cached_input_tokens = 0
    mock_gen.cache_hit = False
    mock_gen.model = "medguard-clinical-answer"
    mock_research_provider.complete.return_value = mock_gen

    def stage_trace_fn(role: str, prov: Any, mod: str, res: Any, est: int) -> Any:
        return MagicMock(role=role, model=mod)

    graph.node_writer(
        clinical_state,
        instructions=_CLINICAL_RESEARCH_INSTRUCTIONS,
        redact_question_fn=lambda q: q,
        stage_trace_fn=stage_trace_fn,
    )

    # Verify writer was called with clinical model
    mock_research_provider.complete.assert_called_once()
    assert mock_research_provider.complete.call_args.kwargs["model"] == "medguard-clinical-answer"
    assert mock_research_provider.complete.call_args.kwargs["instructions"] == _CLINICAL_RESEARCH_INSTRUCTIONS

    # 2. Pharma State
    pharma_state = MedicalAgentState(
        request_id="req-2",
        tenant_id="test",
        conversation_id="c-2",
        locale="vi-VN",
        intent="safety",
        question="Uống Paracetamol và Ibuprofen cùng lúc được không?",
        patient_context={},
        policy=policy_for_intent("safety"),
        claims=[{"id": "finding_1", "category": "finding", "text": "Tương tác thuốc", "required": True, "locked": True}],
        tool_result={},
        answer=GroundedAnswer(
            title="Tương tác thuốc",
            summary="Cần thận trọng",
            key_points=["Tương tác thuốc"],
            next_steps=["Hỏi ý kiến dược sĩ"],
            safety_notes=["Không tự ý tăng liều"],
            questions=[],
            decision_basis="versioned_rules",
            evidence_state="direct_rule_match",
            narrative=[AnswerNarrativeBlock(text="Bản deterministic.")],
        ),
        domain="pharmacology",
    )

    mock_research_provider.complete.reset_mock()
    mock_gen.model = "medguard-pharma-answer"
    graph.node_writer(
        pharma_state,
        instructions=_PHARMA_RESEARCH_INSTRUCTIONS,
        redact_question_fn=lambda q: q,
        stage_trace_fn=stage_trace_fn,
    )

    # Verify writer was called with pharma model
    mock_research_provider.complete.assert_called_once()
    assert mock_research_provider.complete.call_args.kwargs["model"] == "medguard-pharma-answer"
    assert mock_research_provider.complete.call_args.kwargs["instructions"] == _PHARMA_RESEARCH_INSTRUCTIONS


def test_end_to_end_pipeline_domain_tagging() -> None:
    """Test that AnswerAgentPipeline records domain in the resulting trace."""
    mock_research_provider = MagicMock()
    mock_research_provider.provider_name = "mock_research"
    mock_verifier_provider = MagicMock()
    mock_verifier_provider.provider_name = "mock_verifier"
    circuit = CircuitBreaker()

    pipeline = AnswerAgentPipeline(
        config=AnswerAgentConfig(
            mode="shadow",
            research_model="medguard-answer",
            verifier_model="medguard-verifier",
            clinical_research_model="medguard-clinical-answer",
            clinical_verifier_model="medguard-clinical-verifier",
            pharma_research_model="medguard-pharma-answer",
            pharma_verifier_model="medguard-pharma-verifier",
            min_grounding=0.8,
            min_safety=0.8,
            min_completeness=0.8,
            min_citation_coverage=0.8,
        ),
        research_provider=mock_research_provider,
        verifier_provider=mock_verifier_provider,
        circuit=circuit,
    )

    mock_gen = MagicMock()
    mock_gen.data = {
        "question_analysis": {
            "interpreted_request": "Uống thuốc an toàn",
            "key_questions": ["Uống như thế nào?"],
            "ambiguities": [],
            "risk_level": "low",
        },
        "evidence_claims": [],
        "narrative": [
            {
                "kind": "paragraph",
                "text": "Thông tin an toàn thuốc Dược lý",
                "emphasis": [],
                "claim_ids": ["title_1"],
                "source_ids": ["src_1"],
            }
        ],
        "sources": [
            {
                "source_id": "src_1",
                "title": "Dược thư Quốc gia",
                "publisher": "BYT",
                "url": "https://moh.gov.vn/duocthu",
                "authority_tier": "guideline_or_regulator",
                "supports_claim_ids": ["title_1"],
            }
        ],
        "notes": "",
    }
    mock_gen.citations = ("https://moh.gov.vn/duocthu",)
    mock_gen.search_queries = ("duoc thu",)
    mock_gen.latency_ms = 50
    mock_gen.response_id = "resp-1"
    mock_gen.input_tokens = 100
    mock_gen.output_tokens = 50
    mock_gen.cached_input_tokens = 0
    mock_gen.cache_hit = False
    mock_gen.model = "medguard-pharma-answer"
    mock_research_provider.complete.return_value = mock_gen

    mock_ver = MagicMock()
    mock_ver.data = {
        "approved": True,
        "scores": {
            "grounding": 1.0,
            "safety": 1.0,
            "completeness": 1.0,
            "clarity": 1.0,
            "citation_coverage": 1.0,
        },
        "issues": [],
        "missing_claim_ids": [],
        "unsupported_claims": [],
        "source_issues": [],
        "summary": "OK",
    }
    mock_ver.citations = ("https://moh.gov.vn/duocthu",)
    mock_ver.response_id = "resp-2"
    mock_ver.latency_ms = 40
    mock_ver.input_tokens = 80
    mock_ver.output_tokens = 30
    mock_ver.cached_input_tokens = 0
    mock_ver.cache_hit = False
    mock_ver.model = "medguard-pharma-verifier"
    mock_verifier_provider.complete.return_value = mock_ver

    input_answer = GroundedAnswer(
        title="Dược lý",
        summary="Cần kiểm tra kỹ",
        key_points=[],
        next_steps=[],
        safety_notes=[],
        questions=[],
        decision_basis="versioned_rules",
        evidence_state="direct_rule_match",
        narrative=[AnswerNarrativeBlock(text="Bản deterministic.")],
    )

    enhanced = pipeline.enhance(
        answer=input_answer,
        intent="safety",
        question="Uống thuốc này có an toàn không?",
        request_id="req-trace-test",
    )

    assert enhanced.agent_trace is not None
    assert enhanced.agent_trace.domain == "pharmacology"
