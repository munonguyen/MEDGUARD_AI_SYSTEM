"""Unit Tests for Agent A: Clinical Reasoner (Phase 3.2)."""

from app.services.clinical_intake_compiler import ClinicalIntakeCompiler
from app.services.clinical_reasoner_agent import ClinicalReasonerAgent
from app.services.multi_domain_retriever import MultiDomainRetriever
from app.services.safety_kernel import SafetyKernel


def test_reasoner_agent_generates_structured_claims_with_evidence():
    intake = ClinicalIntakeCompiler.compile("Tôi bị mỏi bắp chân sau khi đi bộ nhiều, không sưng không đỏ")
    safety_kernel = SafetyKernel.evaluate(intake)
    evidence_packet = MultiDomainRetriever.retrieve_typed_packet(intake)

    draft = ClinicalReasonerAgent.generate_draft(
        intake=intake,
        evidence_packet=evidence_packet,
        safety_kernel=safety_kernel,
    )

    assert draft.urgency == "ROUTINE"
    assert draft.specialty_code == "ORTHOPEDICS"
    assert len(draft.claims) >= 2
    assert all(c.claim_id.startswith("C") for c in draft.claims)
    assert any(len(c.evidence_ids) > 0 for c in draft.claims)
    assert len(draft.self_care) > 0
    assert len(draft.red_flags) > 0
    assert "chăm sóc" in draft.draft_answer.lower() or "nghỉ ngơi" in draft.draft_answer.lower()


def test_reasoner_agent_handles_emergency_lock():
    intake = ClinicalIntakeCompiler.compile("Đau thắt ngực đè nặng lan tay trái khó thở")
    safety_kernel = SafetyKernel.evaluate(intake)
    evidence_packet = MultiDomainRetriever.retrieve_typed_packet(intake)

    draft = ClinicalReasonerAgent.generate_draft(
        intake=intake,
        evidence_packet=evidence_packet,
        safety_kernel=safety_kernel,
    )

    assert draft.urgency == "EMERGENCY"
    assert any("cấp cứu" in c.text.lower() for c in draft.claims)
    assert any("115" in c.text for c in draft.claims)
