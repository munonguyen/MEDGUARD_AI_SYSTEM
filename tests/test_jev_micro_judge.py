"""Unit Tests for Jev Micro-Judge (Phase 3.4)."""

from app.models.synthesis import Claim, ReasoningDraft
from app.services.clinical_intake_compiler import ClinicalIntakeCompiler
from app.services.evidence_critic_agent import EvidenceCriticAgent
from app.services.jev_micro_judge import JevMicroJudge
from app.services.multi_domain_retriever import MultiDomainRetriever
from app.services.safety_kernel import SafetyKernel


def test_jev_micro_judge_atomic_scoring_without_global_dictatorship():
    intake = ClinicalIntakeCompiler.compile("Tôi bị mỏi bắp chân sau khi đi bộ")
    safety_kernel = SafetyKernel.evaluate(intake)
    evidence_packet = MultiDomainRetriever.retrieve_typed_packet(intake)

    draft = ReasoningDraft(
        draft_id="DRAFT-1",
        urgency="ROUTINE",
        specialty_code="ORTHOPEDICS",
        specialty_label="Cơ xương khớp",
        clinical_interpretation="Căng cơ nhẹ",
        draft_answer="Nghỉ ngơi và theo dõi tại nhà.",
        red_flags=["Sưng to nóng đỏ"],
        claims=[Claim(claim_id="C1", text="Căng cơ lành tính", evidence_ids=["E1"])],
    )
    critic = EvidenceCriticAgent.audit_draft(intake, evidence_packet, safety_kernel, draft)

    judgment = JevMicroJudge.judge(
        intake=intake,
        evidence_packet=evidence_packet,
        safety_kernel=safety_kernel,
        draft=draft,
        critic=critic,
    )

    # Invariant: Jev produces atomic calibrated probabilities
    assert 0.0 <= judgment.unsupported_claim_probability <= 1.0
    assert 0.0 <= judgment.overtriage_probability <= 1.0
    assert 0.0 <= judgment.undertriage_probability <= 1.0
    assert 0.0 <= judgment.context_alignment_score <= 1.0
    assert 0.0 <= judgment.redflag_coverage_score <= 1.0
    assert 0.0 <= judgment.evidence_grounding_score <= 1.0

    # Invariant: Jev does NOT possess global triage override fields
    assert not hasattr(judgment, "triage_recommendation")
    assert not hasattr(judgment, "allow_home_monitoring")


def test_jev_flags_overtriage_on_benign_case():
    intake = ClinicalIntakeCompiler.compile("Tôi bị mỏi bắp chân")
    safety_kernel = SafetyKernel.evaluate(intake)
    evidence_packet = MultiDomainRetriever.retrieve_typed_packet(intake)

    over_triaged_draft = ReasoningDraft(
        draft_id="DRAFT-OVER",
        urgency="EMERGENCY",  # Over-triage!
        specialty_code="ORTHOPEDICS",
        specialty_label="Cơ xương khớp",
        clinical_interpretation="Căng cơ",
        draft_answer="Bạn phải đi cấp cứu ngay lập tức!",
    )
    critic = EvidenceCriticAgent.audit_draft(intake, evidence_packet, safety_kernel, over_triaged_draft)

    judgment = JevMicroJudge.judge(
        intake=intake,
        evidence_packet=evidence_packet,
        safety_kernel=safety_kernel,
        draft=over_triaged_draft,
        critic=critic,
    )

    assert judgment.overtriage_probability >= 0.85
