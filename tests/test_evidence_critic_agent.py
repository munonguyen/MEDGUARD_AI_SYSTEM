"""Unit Tests for Agent B: Evidence & Safety Critic (Phase 3.3)."""

from app.models.synthesis import Claim, ReasoningDraft
from app.services.clinical_intake_compiler import ClinicalIntakeCompiler
from app.services.evidence_critic_agent import EvidenceCriticAgent
from app.services.multi_domain_retriever import MultiDomainRetriever
from app.services.safety_kernel import SafetyKernel


def test_critic_passes_on_sound_benign_draft():
    intake = ClinicalIntakeCompiler.compile("Tôi bị mỏi bắp chân sau khi đi bộ")
    safety_kernel = SafetyKernel.evaluate(intake)
    evidence_packet = MultiDomainRetriever.retrieve_typed_packet(intake)

    e1_id = evidence_packet.all_evidence[0].evidence_id if evidence_packet.all_evidence else "E1"

    sound_draft = ReasoningDraft(
        draft_id="DRAFT-1",
        urgency="ROUTINE",
        specialty_code="ORTHOPEDICS",
        specialty_label="Cơ xương khớp",
        clinical_interpretation="Mỏi cơ cơ học sau vận động",
        likely_explanations=["Căng cơ nhẹ"],
        self_care=["Nghỉ ngơi kê cao chân"],
        red_flags=["Bắp chân sưng to nóng đỏ"],
        follow_up_questions=["Có sưng không?"],
        claims=[
            Claim(claim_id="C1", text="Mỏi cơ sau vận động thường lành tính.", evidence_ids=[e1_id]),
        ],
        draft_answer="Chào bạn, tình trạng mỏi cơ sau vận động thường lành tính. Bạn nên nghỉ ngơi và theo dõi tại nhà.",
    )

    report = EvidenceCriticAgent.audit_draft(
        intake=intake,
        evidence_packet=evidence_packet,
        safety_kernel=safety_kernel,
        draft=sound_draft,
    )

    assert report.critic_pass is True
    assert len(report.rejected_claims) == 0
    assert "C1" in report.approved_claims


def test_critic_flags_unsupported_diagnosis_and_rejects_claim():
    intake = ClinicalIntakeCompiler.compile("Tôi bị mỏi bắp chân")
    safety_kernel = SafetyKernel.evaluate(intake)
    evidence_packet = MultiDomainRetriever.retrieve_typed_packet(intake)

    flawed_draft = ReasoningDraft(
        draft_id="DRAFT-2",
        urgency="ROUTINE",
        specialty_code="ORTHOPEDICS",
        specialty_label="Cơ xương khớp",
        clinical_interpretation="Chẩn đoán xác định DVT",
        likely_explanations=["DVT"],
        self_care=[],
        red_flags=["Đau dữ dội"],
        follow_up_questions=[],
        claims=[
            Claim(claim_id="C1", text="Chắc chắn bạn bị huyết khối tĩnh mạch sâu.", evidence_ids=["E1"]),
        ],
        draft_answer="Chào bạn, chắc chắn bạn bị huyết khối tĩnh mạch sâu cần điều trị.",
    )

    report = EvidenceCriticAgent.audit_draft(
        intake=intake,
        evidence_packet=evidence_packet,
        safety_kernel=safety_kernel,
        draft=flawed_draft,
    )

    assert report.critic_pass is False
    assert report.has_high_severity_violation is True
    assert any(v.code == "UNSUPPORTED_DIAGNOSIS" for v in report.violations)
    assert "C1" in report.rejected_claims


def test_critic_flags_under_triage_on_emergency_lock():
    intake = ClinicalIntakeCompiler.compile("Đau thắt ngực đè nặng lan tay trái khó thở")
    safety_kernel = SafetyKernel.evaluate(intake)
    evidence_packet = MultiDomainRetriever.retrieve_typed_packet(intake)

    downgraded_draft = ReasoningDraft(
        draft_id="DRAFT-3",
        urgency="ROUTINE",  # Failed to escalate!
        specialty_code="CARDIOLOGY",
        specialty_label="Tim mạch",
        clinical_interpretation="Khó chịu ngực",
        draft_answer="Bạn chỉ cần nghỉ ngơi uống nước.",
    )

    report = EvidenceCriticAgent.audit_draft(
        intake=intake,
        evidence_packet=evidence_packet,
        safety_kernel=safety_kernel,
        draft=downgraded_draft,
    )

    assert report.critic_pass is False
    assert any(v.code == "UNDER_TRIAGE" for v in report.violations)
    assert any(m.type == "emergency_transit" for m in report.missing_points)
