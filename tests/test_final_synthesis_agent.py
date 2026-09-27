"""Unit Tests for Final Synthesis Agent (Phase 3.6)."""

from app.models.synthesis import (
    ArbitrationDecision,
    Claim,
    CriticMissingPoint,
    CriticReport,
    JevMicroJudgment,
    ReasoningDraft,
)
from app.services.clinical_intake_compiler import ClinicalIntakeCompiler
from app.services.final_synthesis_agent import FinalSynthesisAgent
from app.services.multi_domain_retriever import MultiDomainRetriever
from app.services.safety_kernel import SafetyKernel


def test_final_synthesis_merges_approved_and_filters_rejected_claims():
    intake = ClinicalIntakeCompiler.compile("Tôi bị mỏi bắp chân sau khi đi bộ")
    safety_kernel = SafetyKernel.evaluate(intake)
    evidence_packet = MultiDomainRetriever.retrieve_typed_packet(intake)

    draft = ReasoningDraft(
        draft_id="DRAFT-1",
        urgency="ROUTINE",
        specialty_code="ORTHOPEDICS",
        specialty_label="Cơ xương khớp",
        clinical_interpretation="Căng cơ cơ học lành tính",
        draft_answer="Bạn bị mỏi cơ, chắc chắn bị DVT. Nghỉ ngơi kê cao chân.",
        self_care=["Nghỉ ngơi kê cao chân"],
        red_flags=["Sưng nóng đỏ"],
        claims=[
            Claim(claim_id="C1", text="Căng cơ lành tính sau vận động.", evidence_ids=["E1"]),
            Claim(claim_id="C2", text="Chắc chắn bị DVT.", evidence_ids=["E2"]),
        ],
        sources=[{"source_id": "SRC-1", "title": "HD BYT", "publisher": "Bộ Y Tế"}],
    )

    critic = CriticReport(
        critic_pass=False,
        approved_claims=["C1"],
        rejected_claims=["C2"],  # C2 rejected!
        missing_points=[
            CriticMissingPoint(type="red_flag", concept="unilateral_swelling", remedy_instruction="Sưng to một bên bắp chân")
        ],
    )
    jev = JevMicroJudgment(
        unsupported_claim_probability=0.2, overtriage_probability=0.1, undertriage_probability=0.01,
        context_alignment_score=0.9, redflag_coverage_score=0.8, evidence_grounding_score=0.85
    )
    arbitration = ArbitrationDecision(action="ACCEPT_A", claims_to_repair=[])

    synthesis = FinalSynthesisAgent.synthesize(
        intake=intake,
        evidence_packet=evidence_packet,
        safety_kernel=safety_kernel,
        draft=draft,
        critic=critic,
        jev=jev,
        arbitration=arbitration,
    )

    assert "C1" in synthesis.claims_used
    assert "C2" not in synthesis.claims_used  # Invariant: C2 filtered out!
    assert "Chắc chắn bị DVT" not in synthesis.final_answer
    assert any("Sưng to một bên" in rf for rf in synthesis.red_flags)
    assert len(synthesis.narrative_blocks) >= 2
