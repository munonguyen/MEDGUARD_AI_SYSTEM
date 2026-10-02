"""V28.2 challenge regressions for context, negation and calibrated uncertainty.

These cases target failure modes that ordinary keyword benchmarks often miss:
- negated red flags embedded next to current symptoms,
- unknown findings accidentally presented as negative,
- symptom words mistaken for causal/exercise context,
- Vietnamese urinary-retention wording where "không" is part of the symptom,
- distinction between severe and thunderclap headache,
- current findings versus hypothetical contingency language.
"""

import pytest

from app.services.clinical_reasoning import ClinicalContextRouter


@pytest.fixture
def router():
    return ClinicalContextRouter()


def test_chest_pain_with_negated_cardiac_companions_is_not_emergency(router):
    result = router.parse(
        "Tôi đau ngực nhưng không khó thở, không vã mồ hôi và không đau lan tay"
    )
    assert result.positive_findings["chest_pain"] is True
    assert result.negative_findings["shortness_of_breath"] is True
    assert result.negative_findings["sweating"] is True
    assert result.negative_findings["radiation"] is True
    assert result.domain_assessment.risk_level != "EMERGENCY"
    assert "cardiac_warning_pattern" not in result.risk_features


def test_chest_pain_after_pushups_with_negated_red_flags_stays_chest_wall_pattern(router):
    result = router.parse(
        "Tôi đau ngực sau chống đẩy, không khó thở, không vã mồ hôi, không đau lan"
    )
    assert result.domain_assessment.risk_level == "ROUTINE"
    assert result.domain_assessment.subtype == "musculoskeletal_chest_wall"


def test_exertional_chest_pressure_remains_urgent_even_without_classic_companions(router):
    result = router.parse(
        "Tôi nặng ngực khi leo cầu thang, không khó thở, không vã mồ hôi, không đau lan"
    )
    assert result.domain_assessment.risk_level == "URGENT"
    assert result.domain_assessment.subtype == "exertional_chest_pain_needs_prompt_assessment"


def test_headache_negated_focal_neuro_words_do_not_create_emergency(router):
    result = router.parse(
        "Tôi đau đầu nhưng không yếu tay, không yếu chân, không nói ngọng và không co giật"
    )
    assert result.domain_assessment.risk_level != "EMERGENCY"
    assert "focal_neurological_deficit" not in result.domain_assessment.red_flags


def test_severe_non_thunderclap_headache_is_urgent_not_emergency(router):
    result = router.parse("Tôi đau đầu dữ dội nhưng khởi phát từ từ, không yếu liệt")
    assert result.domain_assessment.risk_level == "URGENT"
    assert result.domain_assessment.subtype == "headache_needs_prompt_assessment"
    assert "thunderclap_headache" not in result.domain_assessment.red_flags


def test_thunderclap_headache_stays_emergency_despite_negative_focal_findings(router):
    result = router.parse(
        "Tôi đau đầu đột ngột như sét đánh nhưng không yếu tay và không nói ngọng"
    )
    assert result.domain_assessment.risk_level == "EMERGENCY"
    assert "thunderclap_headache" in result.domain_assessment.red_flags


def test_myalgia_without_exercise_is_not_labeled_doms(router):
    result = router.parse(
        "Tôi đau cơ toàn thân, không tập gym và không vận động nặng mấy ngày nay"
    )
    assert result.positive_findings["muscle_pain"] is True
    assert result.domain_assessment.risk_level == "ROUTINE"
    assert result.domain_assessment.subtype == "general_myalgia"


def test_post_exercise_myalgia_with_negated_dark_urine_stays_routine(router):
    result = router.parse(
        "Tôi đau cơ sau tập gym nhưng không có nước tiểu sẫm màu và vẫn tiểu bình thường"
    )
    assert result.domain_assessment.risk_level == "ROUTINE"
    assert result.domain_assessment.subtype == "exercise_soreness_doms"
    assert "dark_tea_colored_urine" not in result.domain_assessment.red_flags


def test_post_exercise_myalgia_with_dark_urine_is_urgent(router):
    result = router.parse("Tôi đau cơ nhiều sau tập nặng và nước tiểu sẫm màu như nước trà")
    assert result.domain_assessment.risk_level == "URGENT"
    assert result.domain_assessment.subtype == "rhabdomyolysis_warning"
    assert "dark_tea_colored_urine" in result.domain_assessment.red_flags


def test_back_pain_with_inability_to_void_is_emergency(router):
    result = router.parse("Tôi đau lưng và từ sáng đến giờ buồn tiểu nhưng không tiểu được")
    assert result.domain_assessment.risk_level == "EMERGENCY"
    assert result.domain_assessment.subtype == "spinal_neurological_emergency"
    assert "new_bladder_bowel_dysfunction" in result.domain_assessment.red_flags


def test_back_pain_with_negated_retention_does_not_create_emergency(router):
    result = router.parse("Tôi đau lưng nhưng không bí tiểu và không yếu chân")
    assert result.domain_assessment.risk_level == "ROUTINE"
    assert "new_bladder_bowel_dysfunction" not in result.domain_assessment.red_flags
    assert "new_leg_weakness" not in result.domain_assessment.red_flags


def test_postural_back_pain_wording_preserves_unknown_not_false(router):
    result = router.parse("Tôi đau lưng sau khi ngồi máy tính cả ngày")
    assert result.domain_assessment.risk_level == "ROUTINE"
    rationale = result.domain_assessment.rationale.lower()
    assert "chưa ghi nhận" in rationale
    assert "chưa biết" in rationale
    assert "không kèm" not in rationale


def test_current_rash_with_hypothetical_airway_red_flags_is_not_false_emergency(router):
    result = router.parse(
        "Tôi đang nổi mề đay nhẹ. Nếu sau đó sưng môi hoặc khó thở thì phải làm gì?"
    )
    assert result.positive_findings["rash"] is True
    assert result.hypothetical_findings["angioedema"] is True
    assert result.hypothetical_findings["shortness_of_breath"] is True
    assert result.domain_assessment.risk_level == "ROUTINE"


def test_current_allergy_airway_compromise_remains_emergency(router):
    result = router.parse(
        "Sau khi uống thuốc tôi nổi mề đay, sưng môi và đang khó thở"
    )
    assert result.domain_assessment.risk_level == "EMERGENCY"
    assert result.domain_assessment.subtype == "anaphylaxis_airway_emergency"


def test_isolated_chest_discomfort_preserves_uncertainty(router):
    result = router.parse("Tôi hơi đau ngực từ sáng")
    assert result.domain_assessment.risk_level == "ROUTINE"
    assert result.domain_assessment.subtype == "unspecified_chest_discomfort"
    assert "chưa đủ dữ kiện" in result.domain_assessment.rationale.lower()
