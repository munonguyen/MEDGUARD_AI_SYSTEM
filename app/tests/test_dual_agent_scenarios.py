from __future__ import annotations

from copy import deepcopy
import json
from typing import Any
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
from app.models.chat import AnswerNarrativeBlock, GroundedAnswer
from app.services.agent_provider import ProviderResult
from app.services.answer_agents import (
    AnswerAgentConfig,
    AnswerAgentPipeline,
    _claims,
    _gate_reason,
)
from app.services.circuit import CircuitBreaker
from app.services.knowledge_retriever import resolve_domain
from app.services.ood_guard import evaluate


TRUSTED_NICE_URL = "https://www.nice.org.uk/guidance/cg150/chapter/recommendations"
TRUSTED_WHO_URL = "https://www.who.int/news-room/fact-sheets/detail/headache-disorders"
TRUSTED_NHS_URL = "https://www.nhs.uk/conditions/headaches/"
TRUSTED_FDA_URL = "https://www.fda.gov/drugs/drug-safety-and-availability"
TRUSTED_EMA_URL = "https://www.ema.europa.eu/en/medicines"
TRUSTED_MOH_URL = "https://moh.gov.vn/huong-dan-dieu-tri"
TRUSTED_KCB_URL = "https://kcb.vn/tai-lieu-chuyen-mon"
TRUSTED_CDC_URL = "https://www.cdc.gov/headache"
TRUSTED_NCBI_URL = "https://ncbi.nlm.nih.gov/pmc/articles/PMC12345"


class FakeProvider:
    def __init__(self, name: str, data: Any, *, citations=(), queries=()) -> None:
        self.provider_name = name
        self.data = data
        self.citations = tuple(citations)
        self.queries = tuple(queries)
        self.calls: list[dict[str, Any]] = []

    @property
    def is_configured(self) -> bool:
        return True

    def complete(self, **values: Any) -> ProviderResult:
        self.calls.append(values)
        return ProviderResult(
            data=self.data,
            response_id=f"{self.provider_name}-resp-123",
            model=values.get("model", "test-model"),
            latency_ms=12,
            citations=self.citations,
            search_queries=self.queries,
        )


def baseline_clinical_answer() -> GroundedAnswer:
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


def baseline_pharma_answer() -> GroundedAnswer:
    return GroundedAnswer(
        title="Tư vấn sử dụng thuốc",
        summary="Cần lưu ý tương tác thuốc và liều lượng khuyến cáo.",
        key_points=["Dấu hiệu được nhận diện: sử dụng đồng thời paracetamol và thuốc cảm"],
        next_steps=["Kiểm tra tổng liều Paracetamol không vượt quá 4g/ngày."],
        safety_notes=["Ngưng thuốc ngay và đi viện nếu có dấu hiệu ngộ độc gan."],
        questions=["Bạn đã uống thuốc được mấy ngày?"],
        decision_basis="versioned_rules",
        evidence_state="direct_rule_match",
        narrative=[AnswerNarrativeBlock(text="Bản deterministic pharma.")],
    )


def build_valid_draft(
    *,
    source_url: str = TRUSTED_NICE_URL,
    publisher: str = "NICE",
    source_title: str = "Headaches guideline",
    title_text: str = "Đánh giá hiện tại",
    summary_text: str = "Chưa đủ dữ kiện để xác định nguyên nhân.",
    locked_action: str = "Theo dõi triệu chứng và nghỉ ngơi.",
    locked_safety: str = "Đi cấp cứu ngay nếu đau đột ngột dữ dội.",
    finding_text: str = "Dấu hiệu được nhận diện: đau đầu",
    question_text: str = "Cơn đau bắt đầu từ lúc nào?",
    risk_level: str = "medium",
    evidence_text: str = "Hướng dẫn chính thống khuyến nghị đánh giá các dấu hiệu cảnh báo đi kèm đau đầu.",
) -> AgentDraft:
    return AgentDraft.model_validate(
        {
            "question_analysis": {
                "interpreted_request": "Đánh giá triệu chứng và dấu hiệu cảnh báo.",
                "key_questions": ["Có dấu hiệu cấp cứu không?"],
                "ambiguities": ["Chưa rõ thời điểm khởi phát"],
                "risk_level": risk_level,
            },
            "evidence_claims": [
                {
                    "claim_id": "ext_guideline_claim",
                    "text": evidence_text,
                    "source_ids": ["src_primary"],
                }
            ],
            "narrative": [
                {
                    "kind": "paragraph",
                    "text": (
                        f"{title_text}. {summary_text} {evidence_text}"
                    ),
                    "emphasis": [title_text],
                    "claim_ids": ["title_1", "summary_2", "ext_guideline_claim"],
                    "source_ids": ["src_primary"],
                },
                {
                    "kind": "caution",
                    "text": (
                        f"{finding_text} {locked_action} {locked_safety} {question_text}"
                    ),
                    "emphasis": [locked_safety],
                    "claim_ids": ["finding_3", "action_4", "safety_5", "question_6"],
                    "source_ids": ["src_primary"],
                },
            ],
            "sources": [
                {
                    "source_id": "src_primary",
                    "title": source_title,
                    "publisher": publisher,
                    "url": source_url,
                    "authority_tier": "guideline_or_regulator",
                    "supports_claim_ids": [
                        "title_1",
                        "summary_2",
                        "finding_3",
                        "action_4",
                        "safety_5",
                        "question_6",
                        "ext_guideline_claim",
                    ],
                }
            ],
            "notes": "Chỉ sử dụng guideline chính thống.",
        }
    )


def build_verification(
    *,
    approved: bool = True,
    grounding: float = 0.98,
    safety: float = 0.99,
    completeness: float = 0.97,
    clarity: float = 0.95,
    citation_coverage: float = 0.98,
    issues: list[str] | None = None,
    missing_claim_ids: list[str] | None = None,
    unsupported_claims: list[str] | None = None,
    source_issues: list[str] | None = None,
    summary: str = "Đạt tiêu chuẩn an toàn y khoa",
) -> AgentVerification:
    return AgentVerification.model_validate(
        {
            "approved": approved,
            "scores": {
                "grounding": grounding,
                "safety": safety,
                "completeness": completeness,
                "clarity": clarity,
                "citation_coverage": citation_coverage,
            },
            "issues": issues or ([] if approved else ["Nội dung không đạt tiêu chuẩn"]),
            "missing_claim_ids": missing_claim_ids or [],
            "unsupported_claims": unsupported_claims or [],
            "source_issues": source_issues or [],
            "summary": summary,
        }
    )


def create_pipeline(
    draft: AgentDraft,
    report: AgentVerification,
    *,
    mode: str = "enforced",
    citations: tuple[str, ...] = (TRUSTED_NICE_URL,),
    verifier_citations: tuple[str, ...] = (TRUSTED_NICE_URL,),
    config_overrides: dict[str, Any] | None = None,
) -> tuple[AnswerAgentPipeline, FakeProvider, FakeProvider]:
    research = FakeProvider("gemini-clinical", draft, citations=citations, queries=("clinical red flags",))
    verifier = FakeProvider("openai-verifier", report, citations=verifier_citations, queries=("verify clinical red flags",))
    cfg_args = {
        "mode": mode,
        "research_model": "medguard-research-v1",
        "verifier_model": "medguard-verifier-v1",
        "min_grounding": 0.90,
        "min_safety": 0.95,
        "min_completeness": 0.85,
        "min_citation_coverage": 0.90,
    }
    if config_overrides:
        cfg_args.update(config_overrides)
    cfg = AnswerAgentConfig(**cfg_args)
    pipeline = AnswerAgentPipeline(
        config=cfg,
        research_provider=research,
        verifier_provider=verifier,
        circuit=CircuitBreaker(error_threshold=2, min_requests=10),
    )
    return pipeline, research, verifier


# ==============================================================================
# Group 1: Writer Draft Diversity (12 tests)
# ==============================================================================

class TestWriterDraftDiversity:
    def test_writer_draft_with_all_narrative_block_types(self):
        """Draft with all supported narrative block types: paragraph, caution, and urgent."""
        draft = build_valid_draft()
        # Add urgent block
        draft.narrative.append(
            AgentNarrativeBlock(
                kind="urgent",
                text="Cảnh báo cấp cứu: Đến cơ sở y tế gần nhất nếu có dấu hiệu nguy kịch.",
                emphasis=["Cảnh báo cấp cứu"],
                claim_ids=["safety_5"],
                source_ids=["src_primary"],
            )
        )
        pipe, _, _ = create_pipeline(draft, build_verification())
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="đau đầu", request_id="req-blocks")
        assert result.agent_trace.status == "verified"
        assert len(result.narrative) == 3
        kinds = [b.kind for b in result.narrative]
        assert kinds == ["paragraph", "caution", "urgent"]

    def test_writer_draft_multi_authority_nice_and_who(self):
        """Draft citing both NICE and WHO guidelines with distinct source entries."""
        draft = build_valid_draft(source_url=TRUSTED_NICE_URL, publisher="NICE")
        who_source = AgentEvidenceSource(
            source_id="src_who",
            title="WHO Headache Disorders",
            publisher="WHO",
            url=TRUSTED_WHO_URL,
            authority_tier="guideline_or_regulator",
            supports_claim_ids=["summary_2", "ext_who_claim"],
        )
        who_claim = AgentEvidenceClaim(
            claim_id="ext_who_claim",
            text="WHO ghi nhận đau đầu là một trong những rối loạn thần kinh phổ biến nhất.",
            source_ids=["src_who"],
        )
        draft.sources.append(who_source)
        draft.evidence_claims.append(who_claim)
        draft.narrative[0].text += " WHO ghi nhận đau đầu là một trong những rối loạn thần kinh phổ biến nhất."
        draft.narrative[0].claim_ids.append("ext_who_claim")
        draft.narrative[0].source_ids.append("src_who")

        pipe, _, _ = create_pipeline(
            draft,
            build_verification(),
            citations=(TRUSTED_NICE_URL, TRUSTED_WHO_URL),
            verifier_citations=(TRUSTED_WHO_URL,),
        )
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="đau đầu", request_id="req-multi-nice-who")
        assert result.agent_trace.status == "verified"
        assert len(result.researched_sources) == 2
        publishers = {s.publisher for s in result.researched_sources}
        assert "NICE" in publishers and "WHO" in publishers

    def test_writer_draft_multi_authority_fda_and_ema(self):
        """Draft citing regulatory authorities FDA and EMA for drug safety."""
        draft = build_valid_draft(source_url=TRUSTED_FDA_URL, publisher="FDA")
        ema_source = AgentEvidenceSource(
            source_id="src_ema",
            title="EMA Drug Safety",
            publisher="EMA",
            url=TRUSTED_EMA_URL,
            authority_tier="guideline_or_regulator",
            supports_claim_ids=["ext_ema_claim"],
        )
        ema_claim = AgentEvidenceClaim(
            claim_id="ext_ema_claim",
            text="EMA khuyến cáo kiểm soát nồng độ dược chất chặt chẽ.",
            source_ids=["src_ema"],
        )
        draft.sources.append(ema_source)
        draft.evidence_claims.append(ema_claim)
        draft.narrative[0].text += " EMA khuyến cáo kiểm soát nồng độ dược chất chặt chẽ."
        draft.narrative[0].claim_ids.append("ext_ema_claim")
        draft.narrative[0].source_ids.append("src_ema")

        pipe, _, _ = create_pipeline(
            draft,
            build_verification(),
            citations=(TRUSTED_FDA_URL, TRUSTED_EMA_URL),
            verifier_citations=(TRUSTED_EMA_URL,),
        )
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="an toàn thuốc", request_id="req-fda-ema")
        assert result.agent_trace.status == "verified"
        assert any(s.publisher == "EMA" for s in result.researched_sources)
        assert any(s.publisher == "FDA" for s in result.researched_sources)

    def test_writer_draft_multi_authority_moh_vietnam(self):
        """Draft citing Vietnam Ministry of Health (moh.gov.vn) and KCB (kcb.vn)."""
        draft = build_valid_draft(source_url=TRUSTED_MOH_URL, publisher="Bộ Y Tế Việt Nam")
        kcb_source = AgentEvidenceSource(
            source_id="src_kcb",
            title="KCB Phác đồ điều trị",
            publisher="Cục Quản lý Khám chữa bệnh",
            url=TRUSTED_KCB_URL,
            authority_tier="guideline_or_regulator",
            supports_claim_ids=["ext_kcb_claim"],
        )
        kcb_claim = AgentEvidenceClaim(
            claim_id="ext_kcb_claim",
            text="KCB ban hành phác đồ chẩn đoán và xử trí đau đầu tại tuyến cơ sở.",
            source_ids=["src_kcb"],
        )
        draft.sources.append(kcb_source)
        draft.evidence_claims.append(kcb_claim)
        draft.narrative[0].text += " KCB ban hành phác đồ chẩn đoán và xử trí đau đầu tại tuyến cơ sở."
        draft.narrative[0].claim_ids.append("ext_kcb_claim")
        draft.narrative[0].source_ids.append("src_kcb")

        pipe, _, _ = create_pipeline(
            draft,
            build_verification(),
            citations=(TRUSTED_MOH_URL, TRUSTED_KCB_URL),
            verifier_citations=(TRUSTED_MOH_URL,),
        )
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="phác đồ đau đầu", request_id="req-moh")
        assert result.agent_trace.status == "verified"
        assert any(s.url == TRUSTED_MOH_URL for s in result.researched_sources)
        assert any(s.url == TRUSTED_KCB_URL for s in result.researched_sources)

    def test_writer_draft_multi_authority_cdc_and_ncbi(self):
        """Draft citing CDC and NCBI PubMed as authoritative sources."""
        draft = build_valid_draft(source_url=TRUSTED_CDC_URL, publisher="CDC")
        ncbi_source = AgentEvidenceSource(
            source_id="src_ncbi",
            title="NCBI PMC Evidence Review",
            publisher="NCBI PubMed",
            url=TRUSTED_NCBI_URL,
            authority_tier="peer_reviewed_journal",
            supports_claim_ids=["ext_ncbi_claim"],
        )
        ncbi_claim = AgentEvidenceClaim(
            claim_id="ext_ncbi_claim",
            text="Nghiên cứu trên PubMed xác nhận tỷ lệ đau đầu căng thẳng chiếm đa số.",
            source_ids=["src_ncbi"],
        )
        draft.sources.append(ncbi_source)
        draft.evidence_claims.append(ncbi_claim)
        draft.narrative[0].text += " Nghiên cứu trên PubMed xác nhận tỷ lệ đau đầu căng thẳng chiếm đa số."
        draft.narrative[0].claim_ids.append("ext_ncbi_claim")
        draft.narrative[0].source_ids.append("src_ncbi")

        pipe, _, _ = create_pipeline(
            draft,
            build_verification(),
            citations=(TRUSTED_CDC_URL, TRUSTED_NCBI_URL),
            verifier_citations=(TRUSTED_CDC_URL,),
        )
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="dịch tễ đau đầu", request_id="req-cdc-ncbi")
        assert result.agent_trace.status == "verified"
        assert any(s.publisher == "NCBI PubMed" for s in result.researched_sources)

    def test_writer_draft_clinical_triage_low_risk(self):
        """Question analysis evaluates low risk level correctly."""
        draft = build_valid_draft(risk_level="low")
        pipe, _, _ = create_pipeline(draft, build_verification())
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="đau đầu nhẹ sau khi ngủ dậy", request_id="req-low-risk")
        assert result.agent_trace.status == "verified"

    def test_writer_draft_clinical_triage_high_risk_red_flags(self):
        """Question analysis identifies high risk level and emergency red flags."""
        draft = build_valid_draft(risk_level="high")
        draft.question_analysis.key_questions = [
            "Có sốt cao kèm cứng cổ không?",
            "Cơn đau có dữ dội như sét đánh không?",
        ]
        pipe, _, _ = create_pipeline(draft, build_verification())
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="đau đầu dữ dội đột ngột", request_id="req-high-risk")
        assert result.agent_trace.status == "verified"

    def test_writer_draft_clinical_ambiguities_captured(self):
        """Question analysis documents multiple clinical ambiguities."""
        draft = build_valid_draft()
        draft.question_analysis.ambiguities = [
            "Chưa rõ tiền sử bệnh lý tim mạch",
            "Chưa rõ thời gian đau kéo dài bao lâu",
            "Chưa rõ có nôn ói hay mờ mắt không",
        ]
        pipe, _, _ = create_pipeline(draft, build_verification())
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="đau đầu mông lung", request_id="req-ambiguities")
        assert result.agent_trace.status == "verified"

    def test_writer_draft_pharma_interaction_domain(self):
        """Pharmacology scenario evaluating Paracetamol and multi-symptom cold medicine."""
        ans = baseline_pharma_answer()
        evidence = "Hướng dẫn dược lâm sàng cảnh báo nguy cơ quá liều Paracetamol khi dùng chung các chế phẩm cảm sốt."
        draft = build_valid_draft(
            source_url=TRUSTED_FDA_URL,
            publisher="FDA",
            locked_action="Kiểm tra tổng liều Paracetamol không vượt quá 4g/ngày.",
            locked_safety="Ngưng thuốc ngay và đi viện nếu có dấu hiệu ngộ độc gan.",
            finding_text="Dấu hiệu được nhận diện: sử dụng đồng thời paracetamol và thuốc cảm",
            evidence_text=evidence,
        )
        pipe, _, _ = create_pipeline(
            draft,
            build_verification(),
            citations=(TRUSTED_FDA_URL,),
            verifier_citations=(TRUSTED_FDA_URL,),
        )
        result = pipe.enhance(answer=ans, intent="safety", question="uống paracetamol cùng decolgen", request_id="req-pharma")
        assert result.agent_trace.status == "verified"
        assert "tổng liều Paracetamol không vượt quá 4g/ngày" in result.narrative[1].text

    def test_writer_draft_pediatric_fever_scenario(self):
        """Pediatric fever scenario with weight-based considerations."""
        ans = GroundedAnswer(
            title="Xử trí sốt ở trẻ em",
            summary="Đánh giá sốt và liều hạ sốt theo cân nặng.",
            key_points=["Dấu hiệu được nhận diện: sốt 38.5 độ ở trẻ em"],
            next_steps=["Dùng Paracetamol liều 10-15mg/kg mỗi 4-6 giờ."],
            safety_notes=["Đưa trẻ đi viện ngay nếu co giật hoặc li bì."],
            questions=["Bé nặng bao nhiêu kg?"],
            decision_basis="versioned_rules",
            evidence_state="direct_rule_match",
            narrative=[AnswerNarrativeBlock(text="Bản deterministic nhi khoa.")],
        )
        evidence = "Hướng dẫn Nhi khoa khuyến cáo dùng paracetamol theo cân nặng và bù dịch điện giải đầy đủ."
        draft = build_valid_draft(
            source_url=TRUSTED_WHO_URL,
            publisher="WHO",
            locked_action="Dùng Paracetamol liều 10-15mg/kg mỗi 4-6 giờ.",
            locked_safety="Đưa trẻ đi viện ngay nếu co giật hoặc li bì.",
            finding_text="Dấu hiệu được nhận diện: sốt 38.5 độ ở trẻ em",
            evidence_text=evidence,
        )
        pipe, _, _ = create_pipeline(
            draft,
            build_verification(),
            citations=(TRUSTED_WHO_URL,),
            verifier_citations=(TRUSTED_WHO_URL,),
        )
        result = pipe.enhance(answer=ans, intent="triage", question="bé 2 tuổi sốt 38.5 độ", request_id="req-pediatric")
        assert result.agent_trace.status == "verified"
        assert "10-15mg/kg" in result.narrative[1].text

    def test_writer_draft_geriatric_polypharmacy_scenario(self):
        """Geriatric polypharmacy scenario with NSAID and hypertension risk."""
        ans = GroundedAnswer(
            title="Cảnh báo sử dụng NSAID ở người cao tuổi",
            summary="Nguy cơ tăng huyết áp và xuất huyết tiêu hóa.",
            key_points=["Dấu hiệu được nhận diện: người cao tuổi tăng huyết áp muốn dùng ibuprofen"],
            next_steps=["Tham vấn bác sĩ tim mạch trước khi dùng thuốc giảm đau kháng viêm."],
            safety_notes=["Theo dõi huyết áp thường xuyên và ngưng ngay nếu đi cầu phân đen."],
            questions=["Bác đang dùng thuốc huyết áp loại nào?"],
            decision_basis="versioned_rules",
            evidence_state="direct_rule_match",
            narrative=[AnswerNarrativeBlock(text="Bản deterministic người cao tuổi.")],
        )
        evidence = "Khuyến cáo tim mạch chỉ ra NSAID có thể làm giảm hiệu quả thuốc hạ áp và tăng nguy cơ suy tim."
        draft = build_valid_draft(
            source_url=TRUSTED_NICE_URL,
            publisher="NICE",
            locked_action="Tham vấn bác sĩ tim mạch trước khi dùng thuốc giảm đau kháng viêm.",
            locked_safety="Theo dõi huyết áp thường xuyên và ngưng ngay nếu đi cầu phân đen.",
            finding_text="Dấu hiệu được nhận diện: người cao tuổi tăng huyết áp muốn dùng ibuprofen",
            evidence_text=evidence,
        )
        pipe, _, _ = create_pipeline(
            draft,
            build_verification(),
            citations=(TRUSTED_NICE_URL,),
            verifier_citations=(TRUSTED_NICE_URL,),
        )
        result = pipe.enhance(answer=ans, intent="safety", question="ông 70 tuổi bị cao huyết áp có uống ibuprofen được không", request_id="req-geriatric")
        assert result.agent_trace.status == "verified"
        assert "Tham vấn bác sĩ tim mạch" in result.narrative[1].text

    def test_writer_draft_chronic_disease_hba1c_monitoring(self):
        """Chronic diabetes management scenario checking glycemic targets."""
        ans = GroundedAnswer(
            title="Mục tiêu đường huyết và HbA1c",
            summary="Đánh giá kết quả xét nghiệm HbA1c định kỳ.",
            key_points=["Dấu hiệu được nhận diện: chỉ số HbA1c 8.2%"],
            next_steps=["Tái khám chuyên khoa Nội tiết để điều chỉnh phác đồ thuốc."],
            safety_notes=["Xử trí ngay nếu xuất hiện triệu chứng hạ đường huyết như run tay, vã mồ hôi."],
            questions=["Lần gần nhất bạn thay đổi liều thuốc là khi nào?"],
            decision_basis="versioned_rules",
            evidence_state="direct_rule_match",
            narrative=[AnswerNarrativeBlock(text="Bản deterministic đái tháo đường.")],
        )
        evidence = "Hiệp hội Đái tháo đường khuyến cáo mục tiêu HbA1c thông thường dưới 7.0% cho hầu hết người trưởng thành."
        draft = build_valid_draft(
            source_url=TRUSTED_CDC_URL,
            publisher="CDC",
            title_text="Mục tiêu đường huyết và HbA1c",
            summary_text="Đánh giá kết quả xét nghiệm HbA1c định kỳ.",
            locked_action="Tái khám chuyên khoa Nội tiết để điều chỉnh phác đồ thuốc.",
            locked_safety="Xử trí ngay nếu xuất hiện triệu chứng hạ đường huyết như run tay, vã mồ hôi.",
            finding_text="Dấu hiệu được nhận diện: chỉ số HbA1c 8.2%",
            question_text="Lần gần nhất bạn thay đổi liều thuốc là khi nào?",
            evidence_text=evidence,
        )
        pipe, _, _ = create_pipeline(
            draft,
            build_verification(),
            citations=(TRUSTED_CDC_URL,),
            verifier_citations=(TRUSTED_CDC_URL,),
        )
        result = pipe.enhance(answer=ans, intent="triage", question="hba1c 8.2% có nguy hiểm không", request_id="req-chronic")
        assert result.agent_trace.status == "verified"


# ==============================================================================
# Group 2: Verifier Approval Calibration (8 tests)
# ==============================================================================

class TestVerifierApprovalCalibration:
    def test_verifier_approval_at_exact_threshold_boundaries(self):
        """Scores exactly at the configured minimums (0.90, 0.95, 0.85, 0.90) must pass."""
        report = build_verification(
            approved=True,
            grounding=0.90,
            safety=0.95,
            completeness=0.85,
            citation_coverage=0.90,
        )
        pipe, _, _ = create_pipeline(build_valid_draft(), report)
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="đau đầu", request_id="req-exact-boundary")
        assert result.agent_trace.status == "verified"
        assert result.agent_trace.verification.scores.grounding == 0.90
        assert result.agent_trace.verification.scores.safety == 0.95

    def test_verifier_approval_just_above_thresholds(self):
        """Scores marginally above thresholds (0.91, 0.96, 0.86, 0.91) pass cleanly."""
        report = build_verification(
            approved=True,
            grounding=0.91,
            safety=0.96,
            completeness=0.86,
            citation_coverage=0.91,
        )
        pipe, _, _ = create_pipeline(build_valid_draft(), report)
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="đau đầu", request_id="req-above-boundary")
        assert result.agent_trace.status == "verified"

    def test_verifier_approval_perfect_scores(self):
        """Scores of 1.0 across all dimensions pass with top assurance."""
        report = build_verification(
            approved=True,
            grounding=1.0,
            safety=1.0,
            completeness=1.0,
            clarity=1.0,
            citation_coverage=1.0,
        )
        pipe, _, _ = create_pipeline(build_valid_draft(), report)
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="đau đầu", request_id="req-perfect")
        assert result.agent_trace.status == "verified"
        assert result.agent_trace.verification.scores.safety == 1.0

    def test_verifier_approval_independent_crosscheck_urls(self):
        """Writer cites NICE and Verifier independently cross-checks with WHO."""
        pipe, _, _ = create_pipeline(
            build_valid_draft(source_url=TRUSTED_NICE_URL),
            build_verification(),
            citations=(TRUSTED_NICE_URL,),
            verifier_citations=(TRUSTED_WHO_URL,),
        )
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="đau đầu", request_id="req-crosscheck-urls")
        assert result.agent_trace.status == "verified"
        assert result.agent_trace.verifier_citation_urls == [TRUSTED_WHO_URL]

    def test_verifier_approval_multiple_independent_verifier_citations(self):
        """Verifier returns 3 independent trusted citation URLs."""
        verifier_urls = (TRUSTED_WHO_URL, TRUSTED_NHS_URL, TRUSTED_CDC_URL)
        pipe, _, _ = create_pipeline(
            build_valid_draft(),
            build_verification(),
            citations=(TRUSTED_NICE_URL,),
            verifier_citations=verifier_urls,
        )
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="đau đầu", request_id="req-multi-verifier-urls")
        assert result.agent_trace.status == "verified"
        assert len(result.agent_trace.verifier_citation_urls) == 3

    def test_verifier_approval_with_clarity_score_variation(self):
        """Clarity score is informational; low clarity (0.60) does not block approval when other 4 scores pass."""
        report = build_verification(
            approved=True,
            grounding=0.95,
            safety=0.98,
            completeness=0.90,
            clarity=0.60,
            citation_coverage=0.95,
        )
        pipe, _, _ = create_pipeline(build_valid_draft(), report)
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="đau đầu", request_id="req-clarity")
        assert result.agent_trace.status == "verified"
        assert result.agent_trace.verification.scores.clarity == 0.60

    def test_verifier_approval_preserves_verifier_model_trace(self):
        """Trace correctly logs verifier metadata, provider, latency, and status."""
        pipe, _, _ = create_pipeline(build_valid_draft(), build_verification())
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="đau đầu", request_id="req-trace")
        assert result.agent_trace.verifier.provider == "openai-verifier"
        assert result.agent_trace.verifier.latency_ms == 12
        assert result.agent_trace.verifier.status == "success"

    def test_verifier_approval_populates_public_assurance_dict(self):
        """Public model dump exposes answer_assurance without internal agent_trace details."""
        pipe, _, _ = create_pipeline(build_valid_draft(), build_verification())
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="đau đầu", request_id="req-assurance")
        dump = result.model_dump(mode="json")
        assert "agent_trace" not in dump
        assert dump["answer_assurance"]["status"] == "verified"
        assert "scores" in dump["answer_assurance"]
        assert dump["answer_assurance"]["scores"]["grounding"] == 0.98


# ==============================================================================
# Group 3: Verifier Rejection Accuracy (6 tests)
# ==============================================================================

class TestVerifierRejectionAccuracy:
    def test_verifier_rejection_unsupported_claims_precedence(self):
        """When approved=False and unsupported_claims is populated, gate reason is unsupported_claims."""
        report = build_verification(
            approved=False,
            unsupported_claims=["ext_guideline_claim"],
            summary="Khẳng định không có bằng chứng hỗ trợ",
        )
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2")
        reason = _gate_reason(
            draft=build_valid_draft(),
            verification=report,
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("headache",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "unsupported_claims"

    def test_verifier_rejection_source_issues_precedence(self):
        """When approved=False, unsupported_claims empty, and source_issues populated -> verifier_reported_source_issues."""
        report = build_verification(
            approved=False,
            unsupported_claims=[],
            source_issues=["Nguồn dẫn không còn truy cập được"],
            summary="Lỗi nguồn dẫn",
        )
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2")
        reason = _gate_reason(
            draft=build_valid_draft(),
            verification=report,
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("headache",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "verifier_reported_source_issues"

    def test_verifier_rejection_missing_claims_precedence(self):
        """When approved=False, unsupported & source issues empty, and missing_claim_ids populated -> verifier_reported_missing_claims."""
        report = build_verification(
            approved=False,
            unsupported_claims=[],
            source_issues=[],
            missing_claim_ids=["safety_5"],
            summary="Thiếu thông báo an toàn bắt buộc",
        )
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2")
        reason = _gate_reason(
            draft=build_valid_draft(),
            verification=report,
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("headache",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "verifier_reported_missing_claims"

    def test_verifier_rejection_generic_without_issue_lists(self):
        """When approved=False and all specific issue lists are empty -> verifier_rejected."""
        report = build_verification(
            approved=False,
            unsupported_claims=[],
            source_issues=[],
            missing_claim_ids=[],
            issues=["Bản thảo không đạt yêu cầu lâm sàng"],
            summary="Từ chối chung",
        )
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2")
        reason = _gate_reason(
            draft=build_valid_draft(),
            verification=report,
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("headache",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "verifier_rejected"

    def test_verifier_rejection_priority_order_unsupported_over_source(self):
        """If both unsupported_claims and source_issues exist, unsupported_claims takes precedence."""
        report = build_verification(
            approved=False,
            unsupported_claims=["claim_123"],
            source_issues=["source_456"],
            summary="Nhiều lỗi",
        )
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2")
        reason = _gate_reason(
            draft=build_valid_draft(),
            verification=report,
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("headache",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "unsupported_claims"

    def test_verifier_rejection_priority_order_source_over_missing(self):
        """If both source_issues and missing_claim_ids exist, source_issues takes precedence."""
        report = build_verification(
            approved=False,
            unsupported_claims=[],
            source_issues=["source_456"],
            missing_claim_ids=["claim_789"],
            summary="Lỗi nguồn và thiếu claim",
        )
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2")
        reason = _gate_reason(
            draft=build_valid_draft(),
            verification=report,
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("headache",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "verifier_reported_source_issues"


# ==============================================================================
# Group 4: Gate Reason Coverage (15 tests)
# ==============================================================================

class TestGateReasonCoverage:
    def test_gate_reason_grounding_below_threshold(self):
        """Grounding score below min_grounding triggers grounding_below_threshold."""
        report = build_verification(approved=True, grounding=0.89)
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2", min_grounding=0.90)
        reason = _gate_reason(
            draft=build_valid_draft(),
            verification=report,
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("q",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "grounding_below_threshold"

    def test_gate_reason_safety_below_threshold(self):
        """Safety score below min_safety triggers safety_below_threshold."""
        report = build_verification(approved=True, safety=0.94)
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2", min_safety=0.95)
        reason = _gate_reason(
            draft=build_valid_draft(),
            verification=report,
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("q",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "safety_below_threshold"

    def test_gate_reason_completeness_below_threshold(self):
        """Completeness score below min_completeness triggers completeness_below_threshold."""
        report = build_verification(approved=True, completeness=0.84)
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2", min_completeness=0.85)
        reason = _gate_reason(
            draft=build_valid_draft(),
            verification=report,
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("q",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "completeness_below_threshold"

    def test_gate_reason_citation_coverage_below_threshold(self):
        """Citation coverage score below min_citation_coverage triggers citation_coverage_below_threshold."""
        report = build_verification(approved=True, citation_coverage=0.89)
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2", min_citation_coverage=0.90)
        reason = _gate_reason(
            draft=build_valid_draft(),
            verification=report,
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("q",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "citation_coverage_below_threshold"

    def test_gate_reason_search_grounding_missing_when_no_citations(self):
        """Empty provider citations triggers search_grounding_missing."""
        report = build_verification(approved=True)
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2")
        reason = _gate_reason(
            draft=build_valid_draft(),
            verification=report,
            claims=claims,
            provider_citations=(),
            provider_queries=("q",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "search_grounding_missing"

    def test_gate_reason_search_grounding_missing_when_no_queries(self):
        """Empty provider queries triggers search_grounding_missing."""
        report = build_verification(approved=True)
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2")
        reason = _gate_reason(
            draft=build_valid_draft(),
            verification=report,
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=(),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "search_grounding_missing"

    def test_gate_reason_independent_verification_missing(self):
        """Empty verifier citations triggers independent_verification_missing."""
        report = build_verification(approved=True)
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2")
        reason = _gate_reason(
            draft=build_valid_draft(),
            verification=report,
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("q",),
            verifier_citations=(),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "independent_verification_missing"

    def test_gate_reason_independent_trusted_source_missing(self):
        """Verifier citations with untrusted domain triggers independent_trusted_source_missing."""
        report = build_verification(approved=True)
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2")
        reason = _gate_reason(
            draft=build_valid_draft(),
            verification=report,
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("q",),
            verifier_citations=("https://untrusted-blog.com/health",),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "independent_trusted_source_missing"

    def test_gate_reason_duplicate_evidence_claim_id(self):
        """Draft with duplicate evidence claim IDs triggers duplicate_evidence_claim_id."""
        draft = build_valid_draft()
        dup_claim = deepcopy(draft.evidence_claims[0])
        draft.evidence_claims.append(dup_claim)
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2")
        reason = _gate_reason(
            draft=draft,
            verification=build_verification(approved=True),
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("q",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "duplicate_evidence_claim_id"

    def test_gate_reason_unknown_claim_reference(self):
        """Narrative referencing an unknown claim ID triggers unknown_claim_reference."""
        draft = build_valid_draft()
        draft.narrative[0].claim_ids.append("totally_unknown_claim_999")
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2")
        reason = _gate_reason(
            draft=draft,
            verification=build_verification(approved=True),
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("q",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "unknown_claim_reference"

    def test_gate_reason_required_claim_not_cited(self):
        """Omitting a required/locked claim ID from narrative blocks triggers required_claim_not_cited."""
        draft = build_valid_draft()
        # safety_5 is locked & required; remove from narrative
        draft.narrative[1].claim_ids.remove("safety_5")
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2")
        reason = _gate_reason(
            draft=draft,
            verification=build_verification(approved=True),
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("q",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "required_claim_not_cited"

    def test_gate_reason_duplicate_source_id(self):
        """Draft with duplicate source IDs triggers duplicate_source_id."""
        draft = build_valid_draft()
        dup_source = deepcopy(draft.sources[0])
        draft.sources.append(dup_source)
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2")
        reason = _gate_reason(
            draft=draft,
            verification=build_verification(approved=True),
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("q",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "duplicate_source_id"

    def test_gate_reason_unknown_source_reference(self):
        """Narrative referencing a source_id not in draft.sources triggers unknown_source_reference."""
        draft = build_valid_draft()
        draft.narrative[0].source_ids.append("src_ghost")
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2")
        reason = _gate_reason(
            draft=draft,
            verification=build_verification(approved=True),
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("q",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "unknown_source_reference"

    def test_gate_reason_unused_evidence_claim(self):
        """Evidence claim defined in draft but never cited in narrative triggers unused_evidence_claim."""
        draft = build_valid_draft()
        extra_claim = AgentEvidenceClaim(
            claim_id="ext_orphan_claim",
            text="Một khẳng định mồ côi không được trích dẫn.",
            source_ids=["src_primary"],
        )
        draft.evidence_claims.append(extra_claim)
        draft.sources[0].supports_claim_ids.append("ext_orphan_claim")
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2")
        reason = _gate_reason(
            draft=draft,
            verification=build_verification(approved=True),
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("q",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "unused_evidence_claim"

    def test_gate_reason_offline_source_evidence_missing(self):
        """When web_search_required=False and retrieved_source_urls is empty -> offline_source_evidence_missing."""
        draft = build_valid_draft()
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2", web_search_required=False)
        reason = _gate_reason(
            draft=draft,
            verification=build_verification(approved=True),
            claims=claims,
            provider_citations=(),
            provider_queries=(),
            verifier_citations=(),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "offline_source_evidence_missing"


# ==============================================================================
# Group 5: Emphasis & Markup Sanitization (5 tests)
# ==============================================================================

class TestEmphasisAndMarkupSanitization:
    def test_markup_rejection_html_tags(self):
        """Block containing HTML tags like <div> or <script> triggers markup_not_allowed."""
        draft = build_valid_draft()
        draft.narrative[0].text += " <div>Thông tin độc hại</div>"
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2")
        reason = _gate_reason(
            draft=draft,
            verification=build_verification(approved=True),
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("q",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "markup_not_allowed"

    def test_markup_rejection_xml_brackets(self):
        """Block containing XML-like brackets <b> or <clinical_action> triggers markup_not_allowed."""
        draft = build_valid_draft()
        draft.narrative[1].text += " <action>Uống nhiều nước</action>"
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2")
        reason = _gate_reason(
            draft=draft,
            verification=build_verification(approved=True),
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("q",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason == "markup_not_allowed"

    def test_emphasis_sanitization_filters_unmatched_phrases(self):
        """Emphasis items not present in block text are pruned without failing the gate."""
        draft = build_valid_draft()
        draft.narrative[0].emphasis = ["Đánh giá hiện tại", "Cụm từ hoàn toàn không có trong đoạn văn"]
        claims = _claims(baseline_clinical_answer(), "triage")
        cfg = AnswerAgentConfig(mode="enforced", research_model="m1", verifier_model="m2")
        reason = _gate_reason(
            draft=draft,
            verification=build_verification(approved=True),
            claims=claims,
            provider_citations=(TRUSTED_NICE_URL,),
            provider_queries=("q",),
            verifier_citations=(TRUSTED_NICE_URL,),
            retrieved_source_urls=(),
            config=cfg,
        )
        assert reason is None
        assert draft.narrative[0].emphasis == ["Đánh giá hiện tại"]

    def test_emphasis_sanitization_preserves_valid_substrings(self):
        """Emphasis items exactly matching substrings are preserved."""
        draft = build_valid_draft()
        draft.narrative[1].emphasis = ["Đi cấp cứu ngay nếu đau đột ngột dữ dội."]
        pipe, _, _ = create_pipeline(draft, build_verification())
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="đau đầu", request_id="req-emphasis-valid")
        assert result.agent_trace.status == "verified"
        assert result.narrative[1].emphasis == ["Đi cấp cứu ngay nếu đau đột ngột dữ dội."]

    def test_emphasis_empty_list_accepted(self):
        """Empty emphasis lists in blocks are handled cleanly without error."""
        draft = build_valid_draft()
        draft.narrative[0].emphasis = []
        draft.narrative[1].emphasis = []
        pipe, _, _ = create_pipeline(draft, build_verification())
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="đau đầu", request_id="req-emphasis-empty")
        assert result.agent_trace.status == "verified"
        assert result.narrative[0].emphasis == []


# ==============================================================================
# Group 6: Cross-Domain Routing (5 tests)
# ==============================================================================

class TestCrossDomainRouting:
    def test_domain_classification_clinical_queries(self):
        """Clinical symptom queries resolve to 'clinical' domain."""
        queries = [
            ("triage", "Tôi bị sốt cao kèm rét run"),
            ("triage", "Đau ngực trái lan ra sau lưng"),
            (None, "Bé bị nôn trớ liên tục sau khi bú"),
            (None, "Đau đầu dữ dội vùng thái dương kèm hoa mắt"),
        ]
        for intent, query in queries:
            assert resolve_domain(intent, query) == "clinical"

    def test_domain_classification_pharmacology_queries(self):
        """Medication and pharmacy queries resolve to 'pharmacology' domain."""
        queries = [
            ("safety", "Uống thuốc Panadol chung với kháng sinh được không?"),
            ("pharmacy", "Tìm tiệm thuốc gần nhất có bán Klacid"),
            (None, "Tương tác giữa Warfarin và NSAID nguy hiểm như thế nào?"),
            (None, "Liều dùng tối đa của Paracetamol trong một lần uống là bao nhiêu?"),
        ]
        for intent, query in queries:
            assert resolve_domain(intent, query) == "pharmacology"

    def test_ood_guard_catches_non_medical_boundary_queries(self):
        """Completely out-of-domain queries are rejected by OOD guard."""
        ood_queries = [
            "Thời tiết ngày mai ở Hà Nội thế nào?",
            "Công thức nấu món phở bò truyền thống ngon nhất?",
            "Viết code python merge sort thuật toán sắp xếp",
        ]
        for query in ood_queries:
            result = evaluate(query)
            assert result is not None
            assert result.verdict == "ood_off_topic"

    def test_ood_guard_catches_crisis_queries(self):
        """Self-harm and crisis prompts are caught with emergency hotlines."""
        crisis_queries = [
            "Tôi muốn tự tử, uống bao nhiêu viên thuốc ngủ thì đi luôn?",
            "Chán đời quá không muốn sống nữa, làm sao chết không đau?",
        ]
        for query in crisis_queries:
            result = evaluate(query)
            assert result is not None
            assert result.verdict == "crisis_self_harm"
            assert result.hotline is not None
            assert "115" in result.hotline

    def test_ood_guard_catches_veterinary_queries(self):
        """Animal and pet health queries are redirected to veterinary services."""
        vet_queries = [
            "Con chó cưng của tôi bị nôn mửa và bỏ ăn 2 ngày nay rồi.",
            "Mèo nhà tôi bị tiêu chảy và sốt, cho uống thuốc gì?",
        ]
        for query in vet_queries:
            result = evaluate(query)
            assert result is not None
            assert result.verdict == "ood_veterinary"
            assert "thú y" in result.reply.lower()


# ==============================================================================
# Group 7: Locked Claim Integrity (4 tests)
# ==============================================================================

class TestLockedClaimIntegrity:
    def test_locked_claim_partial_phrase_missing_triggers_fallback(self):
        """Omitting even a partial phrase of a locked claim triggers locked_claim_changed."""
        draft = build_valid_draft(locked_action="Theo dõi triệu chứng.")
        pipe, _, _ = create_pipeline(draft, build_verification())
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="đau đầu", request_id="req-locked-partial")
        assert result.agent_trace.status == "rejected"
        assert result.agent_trace.fallback_reason == "locked_claim_changed"
        assert result.narrative == baseline_clinical_answer().narrative

    def test_locked_claim_typo_or_paraphrase_triggers_fallback(self):
        """Synonym replacement (e.g. 'nghỉ ngơi tĩnh dưỡng' instead of 'nghỉ ngơi') triggers locked_claim_changed."""
        draft = build_valid_draft(locked_action="Theo dõi triệu chứng và nghỉ ngơi tĩnh dưỡng.")
        pipe, _, _ = create_pipeline(draft, build_verification())
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="đau đầu", request_id="req-locked-typo")
        assert result.agent_trace.status == "rejected"
        assert result.agent_trace.fallback_reason == "locked_claim_changed"

    def test_locked_claim_exact_verbatim_across_multiple_blocks(self):
        """Verbatim inclusion of multiple locked claims succeeds without rejection."""
        draft = build_valid_draft(
            locked_action="Theo dõi triệu chứng và nghỉ ngơi.",
            locked_safety="Đi cấp cứu ngay nếu đau đột ngột dữ dội.",
        )
        pipe, _, _ = create_pipeline(draft, build_verification())
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="đau đầu", request_id="req-locked-verbatim")
        assert result.agent_trace.status == "verified"
        full_text = "\n".join(b.text for b in result.narrative)
        assert "Theo dõi triệu chứng và nghỉ ngơi." in full_text
        assert "Đi cấp cứu ngay nếu đau đột ngột dữ dội." in full_text

    def test_locked_claim_in_different_sentence_order_succeeds(self):
        """Locked claims embedded in varied sentence positions succeed as long as verbatim text exists."""
        draft = build_valid_draft()
        finding = "Dấu hiệu được nhận diện: đau đầu"
        action = "Theo dõi triệu chứng và nghỉ ngơi."
        safety = "Đi cấp cứu ngay nếu đau đột ngột dữ dội."
        draft.narrative[1].text = f"Lưu ý quan trọng: {safety} Ngoài ra: {action} {finding} Cơn đau bắt đầu từ lúc nào?"
        pipe, _, _ = create_pipeline(draft, build_verification())
        result = pipe.enhance(answer=baseline_clinical_answer(), intent="triage", question="đau đầu", request_id="req-locked-reorder")
        assert result.agent_trace.status == "verified"
