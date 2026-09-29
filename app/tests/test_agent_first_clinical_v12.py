from __future__ import annotations

import json

from app.models.agents import AgentDraft, AgentVerification
from app.models.chat import GroundedAnswer
from app.services.agent_provider import ProviderResult
from app.services.answer_agents import AnswerAgentConfig, AnswerAgentPipeline
from app.services.circuit import CircuitBreaker
from app.services.clinical_agent_contract import build_clinical_agent_contract


TRUSTED = "https://www.nice.org.uk/guidance/ng100"


class FakeProvider:
    def __init__(self, name: str, data, *, citations=(), queries=()):
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
            latency_ms=1,
            citations=self.citations,
            search_queries=self.queries,
        )


def fallback_answer() -> GroundedAnswer:
    return GroundedAnswer(
        title="Thông tin hiện tại chưa cho thấy rõ dấu hiệu cấp cứu",
        summary="Cần thêm đánh giá lâm sàng toàn diện.",
        next_steps=["Theo dõi triệu chứng."],
        questions=["Có sốt hoặc đau tăng dần không?"],
        decision_basis="versioned_rules",
        evidence_state="bounded_result",
    )


def test_contract_uses_structured_state_not_legacy_prose_and_strips_identifiers():
    contract = build_clinical_agent_contract(
        intent="triage",
        question="Tôi đang cảm thấy đau các khớp tay",
        clinical_result={
            "urgency": "ROUTINE",
            "recommended_specialty": {"label": "Cơ xương khớp"},
            "red_flags": [],
            "clarifying_questions": ["Khớp có sưng nóng đỏ hoặc cứng buổi sáng không?"],
        },
        patient_context={
            "patient_ref": "BN-SECRET",
            "age": 31,
            "conditions": ["none"],
            "last_result": {"old": "answer"},
        },
    )

    encoded = json.dumps(contract.envelope, ensure_ascii=False)
    assert "BN-SECRET" not in encoded
    assert "patient_ref" not in contract.envelope["patient_context"]
    assert "last_result" not in contract.envelope["patient_context"]
    assert "Thông tin hiện tại chưa cho thấy rõ dấu hiệu cấp cứu" not in encoded
    assert contract.envelope["patient_context"]["age"] == 31
    assert contract.envelope["communication_contract"]["compose_original_response"] is True
    assert contract.envelope["communication_contract"]["question_budget"] == 1


def test_emergency_contract_locks_action_but_does_not_supply_full_template():
    contract = build_clinical_agent_contract(
        intent="triage",
        question="đau ngực khó thở",
        clinical_result={"urgency": "EMERGENCY", "emergency_flag": True, "red_flags": ["khó thở"]},
    )
    locked = [claim for claim in contract.claims if claim["locked"]]
    assert len(locked) == 1
    assert locked[0]["category"] == "action"
    assert "115" in locked[0]["text"]
    assert contract.envelope["communication_contract"]["question_budget"] == 0


def test_generate_response_sends_structured_clinical_context_not_fallback_prose_to_writer():
    # The agent graph owns a stable V14 transport envelope. Clinical reasoning
    # generations (V25+) travel inside that envelope rather than changing its
    # transport version on every reasoning upgrade.
    draft = AgentDraft.model_validate(
        {
            "question_analysis": {
                "interpreted_request": "Đau nhiều khớp tay, cần định hướng và câu hỏi phân biệt.",
                "key_questions": ["Có dấu hiệu viêm khớp không?"],
                "ambiguities": ["Chưa rõ sưng nóng đỏ/cứng buổi sáng"],
                "risk_level": "low",
            },
            "evidence_claims": [],
            "narrative": [
                {
                    "kind": "paragraph",
                    "text": "Đau nhiều khớp tay có nhiều nhóm nguyên nhân; hiện chưa đủ dữ kiện để kết luận một bệnh cụ thể.",
                    "emphasis": [],
                    "claim_ids": ["summary_1", "finding_2"],
                    "source_ids": ["src_nice"],
                }
            ],
            "sources": [
                {
                    "source_id": "src_nice",
                    "title": "Joint pain guidance",
                    "publisher": "NICE",
                    "url": TRUSTED,
                    "authority_tier": "guideline_or_regulator",
                    "supports_claim_ids": ["summary_1", "finding_2"],
                }
            ],
            "notes": "",
        }
    )
    report = AgentVerification.model_validate(
        {
            "approved": False,
            "scores": {
                "grounding": 0.9,
                "safety": 0.95,
                "completeness": 0.8,
                "clarity": 0.9,
                "citation_coverage": 0.9,
            },
            "issues": ["test rejection after writer payload capture"],
            "summary": "reject",
        }
    )
    research = FakeProvider("research", draft, citations=(TRUSTED,), queries=("joint pain NICE",))
    verifier = FakeProvider("verifier", report, citations=(TRUSTED,), queries=("verify joint pain",))
    pipeline = AnswerAgentPipeline(
        config=AnswerAgentConfig(
            mode="enforced",
            research_model="research-test",
            verifier_model="verifier-test",
            max_iterations=0,
        ),
        research_provider=research,
        verifier_provider=verifier,
        circuit=CircuitBreaker(error_threshold=1, min_requests=10),
    )
    fallback = fallback_answer()
    result = pipeline.generate_response(
        fallback_answer=fallback,
        clinical_payload={
            "urgency": "ROUTINE",
            "recommended_specialty": {"label": "Cơ xương khớp"},
            "clarifying_questions": ["Khớp có sưng nóng đỏ hoặc cứng buổi sáng không?"],
        },
        intent="triage",
        question="Tôi đang cảm thấy đau các khớp tay",
        request_id="req-v12",
        patient_context={"age": 31},
    )

    assert result.agent_trace.status == "rejected"
    payload = research.calls[0]["payload"]
    envelope = payload["clinical_envelope"]
    assert envelope["version"] == "v14-structured-agent-input"
    assert envelope["clinical_episode"]["version"] == "v25.1"
    assert envelope["reasoning_frame"]["version"] == "v25.2"
    assert envelope["communication_contract"]["legacy_template_prose_is_not_evidence"] is True
    dumped = json.dumps(payload, ensure_ascii=False)
    assert fallback.summary not in dumped
    assert fallback.title not in dumped
    assert "Cơ xương khớp" in dumped
