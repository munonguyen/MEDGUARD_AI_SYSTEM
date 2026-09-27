"""Unit Tests for Deterministic Arbitration Policy (Phase 3.5)."""

from app.models.safety import SafetyKernelResult
from app.models.synthesis import (
    CriticReport,
    CriticViolation,
    JevMicroJudgment,
    ReasoningDraft,
)
from app.services.arbitration_policy import ArbitrationPolicy


def test_arbitration_accepts_clean_draft():
    safety_kernel = SafetyKernelResult(emergency_lock=False, minimum_triage="ROUTINE")
    critic = CriticReport(critic_pass=True, approved_claims=["C1", "C2"])
    jev = JevMicroJudgment(
        unsupported_claim_probability=0.05,
        overtriage_probability=0.05,
        undertriage_probability=0.02,
        context_alignment_score=0.95,
        redflag_coverage_score=0.95,
        evidence_grounding_score=0.90,
    )
    draft = ReasoningDraft(
        draft_id="D1", urgency="ROUTINE", specialty_code="ENT", specialty_label="Tai Mũi Họng",
        clinical_interpretation="Cảm lạnh", draft_answer="Nghỉ ngơi"
    )

    decision = ArbitrationPolicy.arbitrate(safety_kernel, critic, jev, draft)
    assert decision.action == "ACCEPT_A"


def test_arbitration_triggers_repair_on_high_violation():
    safety_kernel = SafetyKernelResult(emergency_lock=False, minimum_triage="ROUTINE")
    critic = CriticReport(
        critic_pass=False,
        violations=[
            CriticViolation(code="UNSUPPORTED_DIAGNOSIS", severity="HIGH", span="bạn bị DVT", reason="Chẩn đoán xác định từ xa")
        ],
        rejected_claims=["C1"],
    )
    jev = JevMicroJudgment(
        unsupported_claim_probability=0.75,
        overtriage_probability=0.10,
        undertriage_probability=0.02,
        context_alignment_score=0.85,
        redflag_coverage_score=0.90,
        evidence_grounding_score=0.60,
    )
    draft = ReasoningDraft(
        draft_id="D2", urgency="ROUTINE", specialty_code="ORTHOPEDICS", specialty_label="Cơ xương khớp",
        clinical_interpretation="Mỏi cơ", draft_answer="Mỏi cơ"
    )

    decision = ArbitrationPolicy.arbitrate(safety_kernel, critic, jev, draft)
    assert decision.action == "REPAIR_A"
    assert "C1" in decision.claims_to_repair


def test_arbitration_triggers_safe_fallback_on_multiple_critical_failures():
    safety_kernel = SafetyKernelResult(emergency_lock=True, minimum_triage="EMERGENCY")
    critic = CriticReport(
        critic_pass=False,
        violations=[
            CriticViolation(code="UNDER_TRIAGE", severity="CRITICAL", span="ROUTINE", reason="Ignored safety kernel emergency"),
            CriticViolation(code="RED_FLAG_OMISSION", severity="HIGH", span="none", reason="No warning signs"),
        ],
    )
    jev = JevMicroJudgment(
        unsupported_claim_probability=0.90,
        overtriage_probability=0.0,
        undertriage_probability=0.99,
        context_alignment_score=0.40,
        redflag_coverage_score=0.20,
        evidence_grounding_score=0.10,
    )
    draft = ReasoningDraft(
        draft_id="D3", urgency="ROUTINE", specialty_code="CARDIOLOGY", specialty_label="Tim mạch",
        clinical_interpretation="Khó chịu ngực", draft_answer="Uống nước đi ngủ"
    )

    decision = ArbitrationPolicy.arbitrate(safety_kernel, critic, jev, draft)
    assert decision.action == "SAFE_FALLBACK"
    assert decision.mandatory_emergency is True
    assert decision.fallback_policy == "SAFE_EMERGENCY"
