from __future__ import annotations

from app.models.clinical_task import ClinicalTask
from app.services.clinical_task_router import resolve_clinical_task
from app.services.exposure_reasoner import evaluate_exposure_reaction
from app.services.lab_interpreter import interpret_laboratory_text
from app.services.temporal_syndrome import evaluate_temporal_syndrome


def test_hbv_results_route_to_lab_interpretation_not_acute_symptom():
    decision = resolve_clinical_task("HBsAg âm tính (-), Anti-HBs dương tính (+) 450 UI/L")
    assert decision.task == ClinicalTask.LAB_INTERPRETATION


def test_hbv_interpreter_does_not_invent_current_infection():
    result = interpret_laboratory_text("HBsAg âm tính (-), Anti-HBs dương tính (+) 450 UI/L")
    assert result.urgency == "ROUTINE"
    assert any("không ủng hộ" in value.lower() for value in result.interpretation_points)
    assert "total anti-HBc" in result.missing_information
    assert any("không tự" in value.lower() for value in result.prohibited_actions)


def test_topical_reaction_routes_to_exposure_reasoner():
    decision = resolve_clinical_task(
        "Bôi kem nghệ mua trên mạng, da mặt đỏ rát, châm chích và nổi mụn nước li ti."
    )
    assert decision.task == ClinicalTask.EXPOSURE_REACTION
    result = evaluate_exposure_reaction(
        "Bôi kem nghệ mua trên mạng, da mặt đỏ rát, châm chích và nổi mụn nước li ti."
    )
    assert result.urgency == "URGENT"
    assert result.recommended_specialty and result.recommended_specialty["code"] == "DERMATOLOGY"
    assert any("không bôi lại" in value.lower() for value in result.prohibited_actions)


def test_exposure_airway_features_are_emergency():
    result = evaluate_exposure_reaction(
        "Sau kem bôi tôi nổi mẩn, sưng môi, khàn giọng và khó thở."
    )
    assert result.urgency == "EMERGENCY"


def test_migratory_rlq_pattern_requires_relational_support():
    result = evaluate_temporal_syndrome(
        "Chiều qua đau quanh rốn, sáng nay đau chuyển xuống bụng dưới bên phải. "
        "Đi lại và ho đau tăng, kèm buồn nôn và sốt nhẹ."
    )
    assert result.urgency == "URGENT"
    assert result.syndrome_id == "MIGRATORY_RLQ_ABDOMINAL_PATTERN"


def test_rlq_keyword_alone_does_not_trigger_temporal_syndrome():
    result = evaluate_temporal_syndrome("Tôi hơi đau bụng dưới bên phải sau khi tập, không sốt, không buồn nôn.")
    assert result.urgency == "ROUTINE"
    assert result.syndrome_id is None


def test_reading_about_migratory_pain_is_not_patient_syndrome():
    result = evaluate_temporal_syndrome(
        "Tôi đọc trên mạng rằng đau quanh rốn chuyển xuống bụng dưới bên phải có thể là ruột thừa."
    )
    # No supportive movement/cough/systemic features, so the relation alone is insufficient.
    assert result.urgency == "ROUTINE"
