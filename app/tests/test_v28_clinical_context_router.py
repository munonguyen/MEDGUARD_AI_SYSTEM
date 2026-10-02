import pytest
from app.services.clinical_reasoning import ClinicalContextRouter


@pytest.fixture
def router():
    return ClinicalContextRouter()


# --- Headache domain tests ---
def test_headache_after_late_sleep_is_not_emergency_pattern(router):
    result = router.parse("Tôi đau đầu sau khi thức khuya")
    assert result.positive_findings["headache"] is True
    assert "severe_headache_pattern" not in result.risk_features
    assert result.domain_assessment.risk_level == "ROUTINE"
    assert result.domain_assessment.subtype == "tension_or_lifestyle_headache"


def test_headache_thunderclap_is_emergency(router):
    result = router.parse("Đau đầu dữ dội đột ngột, trước giờ chưa từng bị")
    assert result.positive_findings["headache"] is True
    assert "severe_headache_pattern" in result.risk_features
    assert result.domain_assessment.risk_level == "EMERGENCY"


# --- Muscle pain domain tests ---
def test_muscle_pain_after_gym_is_routine_doms(router):
    result = router.parse("Tôi đau cơ sau khi tập gym")
    assert result.positive_findings["muscle_pain"] is True
    assert result.positive_findings["exercise"] is True
    assert result.domain_assessment.risk_level == "ROUTINE"
    assert result.domain_assessment.subtype == "exercise_soreness_doms"


def test_muscle_pain_with_dark_urine_triggers_rhabdomyolysis_warning(router):
    result = router.parse("Đau cơ nhiều sau tập, nước tiểu màu nâu")
    assert result.domain_assessment.risk_level == "URGENT"
    assert "dark_tea_colored_urine" in result.domain_assessment.red_flags
    assert result.domain_assessment.subtype == "rhabdomyolysis_warning"


# --- Chest pain domain tests ---
def test_exercise_chest_pain_without_red_flags(router):
    result = router.parse("Đau ngực khi ấn vào sau chống đẩy")
    assert result.positive_findings["chest_pain"] is True
    assert result.positive_findings["exercise"] is True
    assert result.domain_assessment.risk_level == "ROUTINE"
    assert result.domain_assessment.subtype == "musculoskeletal_chest_wall"
    assert result.risk_features == []


def test_chest_pain_with_red_flags(router):
    result = router.parse("Đau ngực, khó thở và vã mồ hôi")
    assert "cardiac_warning_pattern" in result.risk_features
    assert result.domain_assessment.risk_level == "EMERGENCY"
    assert result.domain_assessment.subtype == "cardiac_emergency_warning"


# --- Back pain domain tests ---
def test_back_pain_after_sitting_all_day_is_routine(router):
    result = router.parse("Đau lưng sau ngồi máy tính cả ngày")
    assert result.positive_findings["back_pain"] is True
    assert result.domain_assessment.risk_level == "ROUTINE"
    assert result.domain_assessment.subtype == "mechanical_postural_back_pain"


def test_negation_removes_leg_weakness_signal(router):
    result = router.parse("Tôi đau lưng nhưng không yếu chân")
    assert result.positive_findings["back_pain"] is True
    assert result.negative_findings["leg_weakness"] is True
    assert "spinal_neurological_warning" not in result.risk_features
    assert result.domain_assessment.risk_level == "ROUTINE"


def test_back_pain_with_leg_weakness_and_incontinence_is_emergency(router):
    result = router.parse("Đau lưng kèm yếu hai chân và mất kiểm soát tiểu tiện")
    assert "spinal_neurological_warning" in result.risk_features
    assert result.domain_assessment.risk_level == "EMERGENCY"
    assert result.domain_assessment.subtype == "spinal_neurological_emergency"


# --- Allergy & Anaphylaxis tests ---
def test_allergy_rash_with_lip_swelling_and_dyspnea_is_anaphylaxis_emergency(router):
    result = router.parse("Sau khi uống thuốc mới tôi nổi mề đay, môi bắt đầu sưng và thấy khó thở")
    assert result.domain_assessment.risk_level == "EMERGENCY"
    assert result.domain_assessment.subtype == "anaphylaxis_airway_emergency"
    assert "cardiac_warning_pattern" not in result.risk_features


# --- Metabolic / Glucose tests ---
def test_glucose_hypoglycemia_rule_of_15(router):
    result = router.parse("Đường huyết máy đo là 58 mg/dL, tôi hơi run tay và đói")
    assert result.domain_assessment.risk_level == "URGENT"
    assert result.domain_assessment.subtype == "acute_hypoglycemia_rule_of_15"


def test_glucose_severe_hypoglycemia_confusion_is_emergency(router):
    result = router.parse("Đường huyết 45 mg/dL và bắt đầu lú lẫn khó trả lời")
    assert result.domain_assessment.risk_level == "EMERGENCY"
    assert result.domain_assessment.subtype == "severe_hypoglycemia_emergency"


# --- Hypothetical query test ---
def test_hypothetical_query_flagged(router):
    result = router.parse("Nếu bắt đầu sưng môi hoặc khó thở thì tôi phải làm gì?")
    assert result.is_hypothetical is True
