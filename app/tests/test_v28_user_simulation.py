"""End-to-End User Simulation Tests for MedGuard V28.1 Roadmap.

Validates the 4 distinct user persona interaction scenarios:
- User 1: Headache after staying up late (sleep deprivation)
- User 2: Muscle pain after gym workout (DOMS, no drug push)
- User 3: Chest pain after push-ups (musculoskeletal, no panic)
- User 4: Chest pain + dyspnea + sweating (acute cardiac red flags)
"""

import pytest
from app.services.clinical_reasoning import ClinicalContextRouter, enrich_patient_context


@pytest.fixture
def router():
    return ClinicalContextRouter()


def test_user_1_headache_after_staying_up_late(router):
    """User 1: 'Tôi đau đầu sau thức khuya'.
    Checks:
    - No panic / no emergency (115) escalation
    - Correctly identifies sleep/lifestyle tension headache
    - Advises reasonable rest/sleep self-care
    """
    user_input = "Tôi đau đầu sau thức khuya"
    result = router.parse(user_input)

    assert result.positive_findings["headache"] is True
    assert "sleep_deprivation" in result.triggers
    assert "severe_headache_pattern" not in result.risk_features
    assert result.domain_assessment.risk_level == "ROUTINE"
    assert result.domain_assessment.subtype == "tension_or_lifestyle_headache"
    assert "Gọi 115" not in result.domain_assessment.suggested_action
    assert "Nghỉ ngơi" in result.domain_assessment.suggested_action


def test_user_2_muscle_soreness_after_gym_workout(router):
    """User 2: 'Tôi đau cơ sau tập gym'.
    Checks:
    - Recognizes exercise soreness (DOMS)
    - Recommends non-pharmacological self-care
    - Avoids immediate drug prescription
    """
    user_input = "Tôi đau cơ sau tập gym"
    result = router.parse(user_input)
    enriched = enrich_patient_context({}, user_input)

    assert result.positive_findings["muscle_pain"] is True
    assert result.positive_findings["exercise"] is True
    assert result.domain_assessment.risk_level == "ROUTINE"
    assert result.domain_assessment.subtype == "exercise_soreness_doms"
    action = result.domain_assessment.suggested_action.lower()
    assert "không cần tự động dùng thuốc giảm đau" in action
    assert "giảm cường độ tập" in action
    assert "đi khám nếu đau tăng" in action

    # Check medication safety pipeline
    med_safety = enriched["clinical_context"]["medication_safety"]
    assert "non_pharmacological_first_line" in med_safety["warning_notes"]
    assert "không tự động kê đơn" in med_safety["guidance"]


def test_user_3_chest_pain_after_pushups_musculoskeletal(router):
    """User 3: 'Tôi đau ngực sau chống đẩy'.
    Checks:
    - Differentiates musculoskeletal wall pain from cardiac ischemia
    - No false emergency 115 alert
    - Prompts follow-up red flags (difficulty breathing, radiation) without crying wolf
    """
    user_input = "Tôi đau ngực sau chống đẩy"
    result = router.parse(user_input)

    assert result.positive_findings["chest_pain"] is True
    assert result.positive_findings["exercise"] is True
    assert "cardiac_warning_pattern" not in result.risk_features
    assert result.domain_assessment.risk_level == "ROUTINE"
    assert result.domain_assessment.subtype == "musculoskeletal_chest_wall"
    assert "Gọi 115" not in result.domain_assessment.suggested_action
    assert "căng cơ thành ngực" in result.domain_assessment.rationale


def test_user_4_chest_pain_with_cardiac_red_flags_emergency(router):
    """User 4: 'Tôi đau ngực, khó thở, vã mồ hôi'.
    Checks:
    - Prioritizes acute cardiac emergency
    - Escalates to EMERGENCY (115) immediately
    - Actionable urgent guidance without delay
    """
    user_input = "Tôi đau ngực, khó thở, vã mồ hôi"
    result = router.parse(user_input)

    assert result.positive_findings["chest_pain"] is True
    assert result.positive_findings["shortness_of_breath"] is True
    assert result.positive_findings["sweating"] is True
    assert "cardiac_warning_pattern" in result.risk_features
    assert result.domain_assessment.risk_level == "EMERGENCY"
    assert result.domain_assessment.subtype == "cardiac_emergency_warning"
    assert "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức" in result.domain_assessment.suggested_action
