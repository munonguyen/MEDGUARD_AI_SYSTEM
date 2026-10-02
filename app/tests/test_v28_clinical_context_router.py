from app.services.clinical_reasoning import ClinicalContextRouter


router = ClinicalContextRouter()


def test_headache_after_late_sleep_is_not_emergency_pattern():
    result = router.parse("Tôi đau đầu sau khi thức khuya")
    assert result.positive_findings["headache"] is True
    assert "severe_headache_pattern" not in result.risk_features


def test_exercise_chest_pain_without_red_flags():
    result = router.parse("Tôi đau ngực sau chống đẩy")
    assert result.positive_findings["chest_pain"] is True
    assert result.positive_findings["exercise"] is True
    assert result.risk_features == []


def test_negation_removes_leg_weakness_signal():
    result = router.parse("Tôi đau lưng nhưng không yếu chân")
    assert result.positive_findings["back_pain"] is True
    assert result.negative_findings["leg_weakness"] is True
    assert "spinal_neurological_warning" not in result.risk_features


def test_chest_pain_with_red_flags():
    result = router.parse("Tôi đau ngực, khó thở và vã mồ hôi")
    assert "cardiac_warning_pattern" in result.risk_features
