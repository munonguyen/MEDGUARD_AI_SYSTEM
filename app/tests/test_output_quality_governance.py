"""Tests for MedGuard Post-Reasoning Output Quality Governance Architecture.

Covers:
1. CanonicalClinicalState unification.
2. ResponseObligationGraph contracts for all 4 risk tiers and dual crisis.
3. Dedicated OutputQualityVerifier and deterministic repair fallback.
4. ClinicalClarificationPlanner with Information-Gain ranking.
5. End-to-end preservation of dual-crisis obligations in chat/triage responses.
"""

from __future__ import annotations

import pytest

from app.services.canonical_clinical_state import (
    CanonicalClinicalState,
    build_canonical_clinical_state,
)
from app.services.clinical_clarification_planner import ClinicalClarificationPlanner
from app.services.output_quality_verifier import (
    OutputQualityCheckResult,
    get_deterministic_template_repair,
    verify_output_quality,
)
from app.services.response_obligation import (
    ResponseObligationGraph,
    build_response_obligations,
)
from app.services.answering import build_grounded_answer
from app.services.dual_crisis_policy import compose_dual_crisis_response


def test_canonical_clinical_state_construction():
    """Verify that clinical text is unified into a single CanonicalClinicalState."""
    text = "Bệnh nhân nam 58 tuổi đau tức ngực dữ dội, không sốt, không nôn, có tiền sử tăng huyết áp."
    state = build_canonical_clinical_state(
        text,
        demographics={"age": 58, "gender": "male"},
        vitals=[{"type": "bp_systolic", "value": 185, "unit": "mmHg"}],
        safety_floor="EMERGENCY",
    )
    assert state.demographics["age"] == 58
    assert state.safety_floor == "EMERGENCY"
    assert state.has_emergency_floor is True
    assert state.has_vital_crisis is True
    assert "hypertension" in state.risk_factors
    assert "no_fever" in state.negations or any("sot" in n for n in state.negations)
    assert len(state.symptoms) > 0


def test_response_obligation_graph_emergency():
    """Emergency obligations require immediate action and forbid delay/home monitoring."""
    obligations = build_response_obligations("EMERGENCY")
    assert obligations.triage == "EMERGENCY"
    assert obligations.policy_tier == "EMERGENCY"
    assert obligations.is_required("state_urgency")
    assert obligations.is_required("medical_emergency_action")
    assert obligations.is_required("do_not_delay")
    assert obligations.is_forbidden("home_monitoring")
    assert obligations.is_forbidden("wait_until_tomorrow")
    assert obligations.is_forbidden("false_reassurance")


def test_response_obligation_graph_dual_crisis():
    """Dual crisis must include both medical emergency and crisis support obligations."""
    obligations = build_response_obligations("EMERGENCY", is_dual_crisis=True)
    assert obligations.is_required("self_harm_support")
    assert obligations.is_required("crisis_hotline")
    assert obligations.is_required("do_not_stay_alone")
    assert obligations.is_forbidden("home_monitoring")


def test_response_obligation_graph_routine():
    """Routine obligations emphasize supportive care and forbid emergency hysteria."""
    obligations = build_response_obligations("ROUTINE")
    assert obligations.is_required("supportive_care")
    assert obligations.is_required("when_to_seek_care")
    assert obligations.is_forbidden("excessive_emergency_alarm")
    assert obligations.is_forbidden("unsupported_diagnosis")


def test_output_quality_verifier_compliant_emergency():
    """Compliant emergency text passes checklist validation."""
    obligations = build_response_obligations("EMERGENCY")
    text = (
        "CẢNH BÁO CẤP CỨU: Đây là tình trạng khẩn cấp cần được đánh giá y tế ngay lập tức. "
        "Hãy gọi ngay Cấp cứu 115 hoặc nhờ người nhà đưa đến bệnh viện gần nhất, tuyệt đối không được trì hoãn."
    )
    result = verify_output_quality(text, obligations)
    assert result.is_valid is True
    assert result.triage_consistent is True
    assert result.contains_contradiction is False
    assert result.contains_unsafe_reassurance is False
    assert result.action_is_clear is True


def test_output_quality_verifier_catches_unsafe_reassurance():
    """Verifier must catch forbidden reassurance ('không sao đâu') and trigger repair."""
    obligations = build_response_obligations("EMERGENCY")
    unsafe_text = "Tình trạng này không sao đâu, cứ ở nhà theo dõi đến mai xem sao."
    result = verify_output_quality(unsafe_text, obligations)
    assert result.is_valid is False
    assert result.contains_unsafe_reassurance is True
    assert "false_reassurance" in result.violated_forbidden
    assert result.repaired_text is None


def test_output_quality_verifier_catches_unsupported_diagnosis():
    """Verifier catches fabricated medical diagnosis."""
    obligations = build_response_obligations("ROUTINE")
    unsupported_text = "Bạn đã bị ung thư dạ dày giai đoạn cuối rồi."
    result = verify_output_quality(unsupported_text, obligations)
    assert result.is_valid is False
    assert result.contains_unsupported_diagnosis is True
    assert result.repaired_text is None


def test_deterministic_template_repair_dual_crisis():
    """Deterministic repair produces crisis hotline for dual crisis."""
    obligations = build_response_obligations("EMERGENCY", is_dual_crisis=True)
    template = get_deterministic_template_repair(obligations)
    assert "115" in template
    assert "Tổng đài Quốc gia 111" in template
    assert "Không ở một mình" in template or "ở cùng bạn" in template


def test_clinical_clarification_planner_information_gain():
    """Clarification planner selects highest information gain questions."""
    state = build_canonical_clinical_state("Tôi bị đau đầu từ sáng nay")
    questions = ClinicalClarificationPlanner.plan_clarifications(state, max_questions=2)
    assert len(questions) > 0
    # Must prioritize thunderclap headache screening for acute headache
    assert any("như sét đánh" in q or "dưới 1 phút" in q or "đột ngột" in q for q in questions)


def test_grounded_answer_preserves_dual_crisis_composition():
    """End-to-end check that build_grounded_answer preserves dual crisis composed advice."""
    crisis_text = "Bạn hãy chia sẻ với người thân và liên hệ Tổng đài Quốc gia 111."
    composed_reply = compose_dual_crisis_response(crisis_text)

    triage_result = {
        "urgency": "EMERGENCY",
        "emergency_flag": True,
        "crisis_support_flag": True,
        "red_flags": ["RF_CHEST_PAIN"],
        "advice": "Gọi 115 và đến cấp cứu ngay.",
    }

    answer = build_grounded_answer(
        intent="triage",
        status="answered",
        reply=composed_reply,
        required_fields=[],
        result=triage_result,
    )

    # Both medical emergency and crisis support must be preserved in summary and next steps
    assert "CẤP CỨU Y TẾ NGAY — GỌI 115" in answer.summary
    assert "khủng hoảng" in answer.summary.lower()
    assert any("111" in step for step in answer.next_steps)
    assert any("Không ở một mình" in note for note in answer.safety_notes)
