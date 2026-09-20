"""Unit Tests for Single-Pass Response Generator."""

import pytest
from app.services.single_response_writer import render_single_clinical_response
from app.services.tri_gate_resolver import FinalResolution


def test_emergency_response_policy_compliance():
    res = FinalResolution(
        final_triage="EMERGENCY",
        final_action="EMERGENCY_NOW",
        allow_home_monitoring=False,
        require_human_review=False,
        confidence=0.99,
        governing_source="gate3_jev",
        safety_invariants_enforced=("enforce_zero_home_monitoring_for_emergency",),
        response_policy={
            "forbid_phrases": ["theo dõi tại nhà", "chờ thêm"],
            "mandate_phrases": ["cấp cứu ngay", "115"],
        },
    )
    resp = render_single_clinical_response(res, "Đau ngực dữ dội vã mồ hôi")
    assert resp.policy_compliant is True
    assert "115" in resp.reply_text
    assert "cấp cứu" in resp.reply_text.lower()
    assert "TUYỆT ĐỐI KHÔNG ở nhà tự xử trí" in resp.reply_text
    assert len(resp.narrative_blocks) == 2


def test_urgent_response():
    res = FinalResolution(
        final_triage="URGENT",
        final_action="SAME_DAY_EVAL",
        allow_home_monitoring=False,
        require_human_review=False,
        confidence=0.92,
        governing_source="gate1_reasoner",
        safety_invariants_enforced=("mandate_same_day_physician_evaluation",),
        response_policy={"forbid_phrases": ["không sao đâu"]},
    )
    resp = render_single_clinical_response(res, "Đau bụng âm ỉ hố chậu phải")
    assert resp.policy_compliant is True
    assert "trong ngày" in resp.reply_text
    assert "thăm khám" in resp.reply_text


def test_routine_response():
    res = FinalResolution(
        final_triage="ROUTINE",
        final_action="SELF_CARE",
        allow_home_monitoring=True,
        require_human_review=False,
        confidence=0.95,
        governing_source="gate1_reasoner",
        safety_invariants_enforced=("benign_routine_self_care_permitted",),
        response_policy={},
    )
    resp = render_single_clinical_response(res, "Mỏi cổ gáy sau khi ngủ dậy")
    assert resp.policy_compliant is True
    assert "nghỉ ngơi" in resp.reply_text
    assert "theo dõi tại nhà" in resp.reply_text
