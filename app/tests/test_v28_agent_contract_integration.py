from __future__ import annotations

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


def _fallback() -> GroundedAnswer:
    return GroundedAnswer(
        title="Theo dõi triệu chứng",
        summary="Theo dõi diễn tiến và đi khám nếu tình trạng tăng nặng.",
        next_steps=["Theo dõi triệu chứng."],
        decision_basis="versioned_rules",
        evidence_state="bounded_result",
    )


def test_contract_exposes_v28_negation_context_without_identifiers():
    contract = build_clinical_agent_contract(
        intent="triage",
        question="Tôi đau lưng nhưng không yếu chân",
        clinical_result={"urgency": "ROUTINE", "red_flags": []},
        patient_context={"age": 31, "patient_ref": "BN-SECRET"},
    )

    patient = contract.envelope["patient_context"]
    assert "patient_ref" not in patient
    assert patient["age"] == 31
    clinical = patient["clinical_context"]
    assert clinical["positive_findings"]["back_pain"] is True
    assert clinical["negative_findings"]["leg_weakness"] is True
    assert clinical["domain_assessment"]["risk_level"] == "ROUTINE"
    assert contract.envelope["communication_contract"]["never_promote_negated_findings_to_present"] is True


def test_contract_exposes_hypothetical_findings_as_non_current():
    contract = build_clinical_agent_contract(
        intent="triage",
        question="Nếu bắt đầu sưng môi hoặc khó thở thì tôi phải làm gì?",
        clinical_result={"urgency": "ROUTINE", "red_flags": []},
    )

    clinical = contract.envelope["patient_context"]["clinical_context"]
    assert clinical["positive_findings"] == {}
    assert clinical["hypothetical_findings"]["angioedema"] is True
    assert clinical["hypothetical_findings"]["shortness_of_breath"] is True
    assert clinical["domain_assessment"]["subtype"] == "contingency_safety_guidance"


def test_hard_medication_block_becomes_locked_agent_claim():
    contract = build_clinical_agent_contract(
        intent="triage",
        question="Tôi đau lưng, dùng ibuprofen được không?",
        clinical_result={"urgency": "ROUTINE", "red_flags": []},
        patient_context={"current_medications": ["apixaban"]},
    )

    medication = contract.envelope["patient_context"]["clinical_context"]["medication_safety"]
    assert medication["allowed"] is False
    assert "anticoagulant_nsaid_combination_requires_review" in medication["contraindications"]
    locked_safety = [
        claim
        for claim in contract.claims
        if claim["category"] == "safety" and claim["locked"]
    ]
    assert locked_safety
    assert any("ibuprofen" in claim["text"].lower() for claim in locked_safety)


def test_release_gate_rejects_context_leakage_after_model_approval():
    # Keep the fake model output fully valid against the real AgentDraft schema;
    # the test must reach the post-model V28 release gate rather than fail during
    # fixture validation.
    draft = AgentDraft.model_validate(
        {
            "question_analysis": {
                "interpreted_request": "Mề đay sau thuốc mới.",
                "key_questions": ["Ban có lan nhanh hoặc xuất hiện khó thở không?"],
                "ambiguities": [],
                "risk_level": "low",
            },
            "evidence_claims": [],
            "narrative": [
                {
                    "kind": "paragraph",
                    "text": (
                        "Bạn đang mô tả mề đay ở cánh tay sau thuốc mới; hãy ngừng dùng thêm thuốc nghi ngờ và theo dõi. "
                        "Việc đỡ sau nghỉ không xóa các dấu hiệu tim-phổi hay đau ngực theo gắng sức đã xuất hiện trước đó."
                    ),
                    "emphasis": [],
                    "claim_ids": ["summary_1"],
                    "source_ids": ["src_nice"],
                }
            ],
            "sources": [
                {
                    "source_id": "src_nice",
                    "title": "Drug allergy guidance",
                    "publisher": "NICE",
                    "url": TRUSTED,
                    "authority_tier": "guideline_or_regulator",
                    "supports_claim_ids": ["summary_1"],
                }
            ],
            "notes": "",
        }
    )
    verification = AgentVerification.model_validate(
        {
            "approved": True,
            "scores": {
                "grounding": 1.0,
                "safety": 1.0,
                "completeness": 1.0,
                "clarity": 1.0,
                "citation_coverage": 1.0,
            },
            "issues": [],
            "unsupported_claims": [],
            "source_issues": [],
            "missing_claim_ids": [],
            "summary": "approved by model verifier",
        }
    )
    research = FakeProvider(
        "research",
        draft,
        citations=(TRUSTED,),
        queries=("urticaria drug reaction NICE",),
    )
    verifier = FakeProvider(
        "verifier",
        verification,
        citations=(TRUSTED,),
        queries=("verify urticaria",),
    )
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

    result = pipeline.generate_response(
        fallback_answer=_fallback(),
        clinical_payload={"urgency": "ROUTINE", "red_flags": []},
        intent="triage",
        question="Sau khi uống thuốc mới tôi nổi mề đay ở cánh tay",
        request_id="req-v28-release-gate",
    )

    writer_envelope = research.calls[0]["payload"]["clinical_envelope"]
    assert writer_envelope["version"] == "v14-structured-agent-input"
    assert writer_envelope["patient_context"]["clinical_context"]["positive_findings"]["rash"] is True
    assert writer_envelope["communication_contract"]["respect_v28_positive_negative_findings"] is True
    assert writer_envelope["communication_contract"]["never_promote_negated_findings_to_present"] is True

    assert result.agent_trace is not None
    assert result.agent_trace.status == "rejected"
    assert result.agent_trace.fallback_reason == (
        "v28_response_quality:context_leakage_cardiopulmonary_in_allergy"
    )
