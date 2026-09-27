"""Unit Tests for Evidence & Citation Guard / Verifier (Phase 3.8)."""

from app.models.synthesis import FinalSynthesisResult
from app.services.clinical_intake_compiler import ClinicalIntakeCompiler
from app.services.evidence_verifier import EvidenceVerifier
from app.services.multi_domain_retriever import MultiDomainRetriever


def test_evidence_verifier_approves_valid_registered_citations():
    intake = ClinicalIntakeCompiler.compile("Tôi bị mỏi bắp chân sau khi đi bộ")
    evidence_packet = MultiDomainRetriever.retrieve_typed_packet(intake)

    valid_eid = evidence_packet.all_evidence[0].evidence_id if evidence_packet.all_evidence else "E1"
    valid_source = evidence_packet.all_evidence[0].source_ref.source_id if evidence_packet.all_evidence else "src_1"

    valid_synth = FinalSynthesisResult(
        final_answer="Mỏi cơ lành tính sau vận động.",
        title="Tư vấn",
        summary="Mỏi cơ",
        urgency="ROUTINE",
        specialty_code="ORTHOPEDICS",
        specialty_label="Cơ xương khớp",
        claims_used=["C1"],
        evidence_used=[valid_eid],
        sources=[{"source_id": valid_source}],
    )

    result = EvidenceVerifier.verify(evidence_packet, valid_synth)
    assert result.verified is True
    assert len(result.invalid_citations) == 0


def test_evidence_verifier_catches_fabricated_evidence_id():
    intake = ClinicalIntakeCompiler.compile("Tôi bị mỏi bắp chân")
    evidence_packet = MultiDomainRetriever.retrieve_typed_packet(intake)

    fabricated_synth = FinalSynthesisResult(
        final_answer="Mỏi cơ.",
        title="Tư vấn",
        summary="Mỏi cơ",
        urgency="ROUTINE",
        specialty_code="ORTHOPEDICS",
        specialty_label="Cơ xương khớp",
        claims_used=["C1"],
        evidence_used=["E999_FABRICATED"],  # Hallucinated evidence ID!
        sources=[],
    )

    result = EvidenceVerifier.verify(evidence_packet, fabricated_synth)
    assert result.verified is False
    assert "E999_FABRICATED" in result.invalid_citations
