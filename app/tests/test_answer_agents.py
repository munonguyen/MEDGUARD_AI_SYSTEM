from __future__ import annotations

from copy import deepcopy
import json

from app.models.agents import AgentDraft, AgentVerification
from app.models.chat import AnswerNarrativeBlock, GroundedAnswer
from app.services.agent_provider import ProviderResult
from app.services.answer_agents import AnswerAgentConfig, AnswerAgentPipeline
from app.services.circuit import CircuitBreaker


TRUSTED_URL = "https://www.nice.org.uk/guidance/cg150/chapter/recommendations"


class FakeProvider:
    def __init__(self, name: str, data, *, citations=(), queries=()) -> None:
        self.provider_name = name
        self.data = data
        self.citations = tuple(citations)
        self.queries = tuple(queries)
        self.calls = []

    @property
    def is_configured(self) -> bool:
        return True

    def complete(self, **values):
        self.calls.append(values)
        return ProviderResult(
            data=self.data,
            response_id=f"{self.provider_name}-response",
            model=values["model"],
            latency_ms=7,
            citations=self.citations,
            search_queries=self.queries,
        )


def baseline_answer() -> GroundedAnswer:
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


def approved_draft(*, source_url: str = TRUSTED_URL, locked_action: str | None = None) -> AgentDraft:
    action = locked_action or "Theo dõi triệu chứng và nghỉ ngơi."
    return AgentDraft.model_validate(
        {
            "question_analysis": {
                "interpreted_request": "Đánh giá triệu chứng đau đầu và dấu hiệu cảnh báo.",
                "key_questions": ["Có dấu hiệu cấp cứu không?"],
                "ambiguities": ["Chưa rõ thời điểm khởi phát"],
                "risk_level": "medium",
            },
            "evidence_claims": [
                {
                    "claim_id": "ext_headache_guidance",
                    "text": "Hướng dẫn chính thống khuyến nghị đánh giá các dấu hiệu cảnh báo đi kèm đau đầu.",
                    "source_ids": ["src_nice"],
                }
            ],
            "narrative": [
                {
                    "kind": "paragraph",
                    "text": (
                        "Đánh giá hiện tại. Chưa đủ dữ kiện để xác định nguyên nhân. "
                        "Hướng dẫn chính thống khuyến nghị đánh giá các dấu hiệu cảnh báo đi kèm đau đầu."
                    ),
                    "emphasis": ["Đánh giá hiện tại"],
                    "claim_ids": ["title_1", "summary_2", "ext_headache_guidance"],
                    "source_ids": ["src_nice"],
                },
                {
                    "kind": "caution",
                    "text": (
                        f"Dấu hiệu được nhận diện: đau đầu {action} "
                        "Đi cấp cứu ngay nếu đau đột ngột dữ dội. Cơn đau bắt đầu từ lúc nào?"
                    ),
                    "emphasis": ["Đi cấp cứu ngay nếu đau đột ngột dữ dội."],
                    "claim_ids": ["finding_3", "action_4", "safety_5", "question_6"],
                    "source_ids": ["src_nice"],
                },
            ],
            "sources": [
                {
                    "source_id": "src_nice",
                    "title": "Headaches in over 12s: diagnosis and management",
                    "publisher": "NICE",
                    "url": source_url,
                    "authority_tier": "guideline_or_regulator",
                    "supports_claim_ids": [
                        "title_1",
                        "summary_2",
                        "finding_3",
                        "action_4",
                        "safety_5",
                        "question_6",
                        "ext_headache_guidance",
                    ],
                }
            ],
            "notes": "Chỉ sử dụng guideline.",
        }
    )


def verification(*, approved: bool = True) -> AgentVerification:
    return AgentVerification.model_validate(
        {
            "approved": approved,
            "scores": {
                "grounding": 0.98,
                "safety": 0.99,
                "completeness": 0.97,
                "clarity": 0.94,
                "citation_coverage": 0.98,
            },
            "issues": [] if approved else ["Nội dung chưa đủ căn cứ"],
            "missing_claim_ids": [],
            "unsupported_claims": [],
            "source_issues": [],
            "summary": "Đạt" if approved else "Không đạt",
        }
    )


def pipeline(
    draft: AgentDraft,
    report: AgentVerification,
    *,
    mode: str = "enforced",
    citations=(TRUSTED_URL,),
    verifier_citations=(TRUSTED_URL,),
):
    research = FakeProvider("gemini", draft, citations=citations, queries=("NICE headache red flags",))
    verifier = FakeProvider(
        "openai",
        report,
        citations=verifier_citations,
        queries=("verify headache guideline",),
    )
    instance = AnswerAgentPipeline(
        config=AnswerAgentConfig(
            mode=mode,
            research_model="gemini-test",
            verifier_model="gpt-test",
            min_grounding=0.90,
            min_safety=0.95,
            min_completeness=0.85,
            min_citation_coverage=0.90,
        ),
        research_provider=research,
        verifier_provider=verifier,
        circuit=CircuitBreaker(error_threshold=1, min_requests=10),
    )
    return instance, research, verifier


def test_verified_cross_provider_pipeline_releases_grounded_draft_and_redacts_identifiers():
    instance, research, verifier = pipeline(approved_draft(), verification())
    result = instance.enhance(
        answer=baseline_answer(),
        intent="triage",
        question="BN-SECRET-01 đau đầu, email an@example.com, số 0912345678",
        request_id="req-agent-approved",
    )

    assert result.agent_trace.status == "verified"
    assert result.agent_trace.generator.provider == "gemini"
    assert result.agent_trace.verifier.provider == "openai"
    assert result.agent_trace.search_queries == ["NICE headache red flags"]
    assert result.agent_trace.verifier_citation_urls == [TRUSTED_URL]
    assert result.researched_sources[0].publisher == "NICE"
    assert result.narrative[0].source_ids == ["src_nice"]
    sent_question = research.calls[0]["payload"]["user_question"]
    assert "BN-SECRET-01" not in sent_question
    assert "an@example.com" not in sent_question
    assert "0912345678" not in sent_question
    assert len(verifier.calls) == 1
    public_answer = result.model_dump(mode="json")
    assert "agent_trace" not in public_answer
    assert public_answer["answer_assurance"]["status"] == "verified"
    assert set(public_answer["answer_assurance"]) == {"status", "scores"}
    assert "gemini" not in json.dumps(public_answer).lower()
    assert "gpt" not in json.dumps(public_answer).lower()


def test_verifier_rejection_uses_deterministic_fallback():
    original = baseline_answer()
    instance, _, _ = pipeline(approved_draft(), verification(approved=False))
    result = instance.enhance(answer=original, intent="triage", question="đau đầu", request_id="req-reject")

    assert result.agent_trace.status == "rejected"
    assert result.agent_trace.fallback_reason == "verifier_rejected"
    assert result.narrative == original.narrative
    assert result.researched_sources == []


def test_source_url_not_returned_by_google_citation_metadata_is_rejected():
    original = baseline_answer()
    instance, _, _ = pipeline(approved_draft(), verification(), citations=("https://www.nhs.uk/conditions/headaches/",))
    result = instance.enhance(answer=original, intent="triage", question="đau đầu", request_id="req-fake-url")

    assert result.agent_trace.status == "rejected"
    assert result.agent_trace.fallback_reason == "source_not_in_provider_citations"
    assert result.researched_sources == []


def test_untrusted_commercial_source_is_rejected_even_when_verifier_approves():
    commercial_url = "https://health-blog.example/headache"
    instance, _, _ = pipeline(
        approved_draft(source_url=commercial_url),
        verification(),
        citations=(commercial_url,),
    )
    result = instance.enhance(answer=baseline_answer(), intent="triage", question="đau đầu", request_id="req-domain")

    assert result.agent_trace.status == "rejected"
    assert result.agent_trace.fallback_reason == "untrusted_source_domain"


def test_verifier_must_return_an_independently_trusted_source():
    instance, _, _ = pipeline(
        approved_draft(),
        verification(),
        verifier_citations=("https://health-blog.example/headache",),
    )
    result = instance.enhance(answer=baseline_answer(), intent="triage", question="đau đầu", request_id="req-crosscheck")

    assert result.agent_trace.status == "rejected"
    assert result.agent_trace.fallback_reason == "independent_trusted_source_missing"


def test_each_narrative_claim_must_be_supported_by_its_cited_source():
    draft = approved_draft().model_copy(deep=True)
    draft.sources[0].supports_claim_ids.remove("safety_5")
    instance, _, _ = pipeline(draft, verification())

    result = instance.enhance(answer=baseline_answer(), intent="triage", question="đau đầu", request_id="req-link")

    assert result.agent_trace.status == "rejected"
    assert result.agent_trace.fallback_reason == "narrative_claim_source_mismatch"


def test_locked_clinical_action_cannot_be_paraphrased_by_both_models():
    draft = approved_draft(locked_action="Bạn có thể tự dùng thuốc tùy ý.")
    instance, _, _ = pipeline(draft, verification())
    result = instance.enhance(answer=baseline_answer(), intent="triage", question="đau đầu", request_id="req-locked")

    assert result.agent_trace.status == "rejected"
    assert result.agent_trace.fallback_reason == "locked_claim_changed"


def test_shadow_mode_records_scores_but_never_replaces_user_answer():
    original = baseline_answer()
    instance, _, _ = pipeline(approved_draft(), verification(), mode="shadow")
    result = instance.enhance(answer=deepcopy(original), intent="triage", question="đau đầu", request_id="req-shadow")

    assert result.agent_trace.status == "shadow"
    assert result.agent_trace.verification.scores.citation_coverage == 0.98
    assert result.narrative == original.narrative
    assert result.researched_sources == []


def test_input_token_guard_fails_before_any_model_call():
    instance, research, verifier = pipeline(approved_draft(), verification())
    instance.config = AnswerAgentConfig(
        mode="enforced",
        research_model="research-test",
        verifier_model="verifier-test",
        min_grounding=0.90,
        min_safety=0.95,
        min_completeness=0.85,
        min_citation_coverage=0.90,
        max_input_tokens=1,
    )

    result = instance.enhance(
        answer=baseline_answer(),
        intent="triage",
        question="đau đầu",
        request_id="req-token-guard",
    )

    assert result.agent_trace.status == "rejected"
    assert result.agent_trace.fallback_reason == "input_token_limit_exceeded"
    assert research.calls == []
    assert verifier.calls == []
