import pytest
from app.services.clinical_reasoning.medication_safety import MedicationSafetyPipeline


@pytest.fixture
def pipeline():
    return MedicationSafetyPipeline()


def test_alcohol_with_sedatives_is_contraindicated(pipeline):
    query = "Tối nay tôi có uống rượu, có thể dùng thêm thuốc gây buồn ngủ được không?"
    result = pipeline.evaluate(query)
    assert result.allowed is False
    assert "alcohol_sedative_coadministration" in result.contraindications_detected
    assert "Không được uống thuốc ngủ sau khi đã uống rượu bia" in result.guidance


def test_penicillin_allergy_contraindicates_amoxicillin(pipeline):
    query = "Tôi từng dị ứng penicillin, giờ có đơn amoxicillin có nên thử nửa viên không?"
    result = pipeline.evaluate(query)
    assert result.allowed is False
    assert "penicillin_amoxicillin_cross_reactivity" in result.contraindications_detected
    assert "tuyệt đối không được tự ý dùng thử hay uống nửa viên" in result.guidance


def test_penicillin_allergy_from_patient_context_is_enforced(pipeline):
    result = pipeline.evaluate(
        "Tôi có thể uống amoxicillin theo đơn này không?",
        {"allergies": ["Penicillin"]},
    )
    assert result.allowed is False
    assert "penicillin_amoxicillin_cross_reactivity" in result.contraindications_detected


def test_anticoagulant_unauthorized_stopping_warned(pipeline):
    query = "Tôi đang dùng thuốc chống đông và bị chảy máu cam, có nên tự bỏ liều tối nay không?"
    result = pipeline.evaluate(query)
    assert result.allowed is False
    assert "unauthorized_anticoagulant_cessation" in result.contraindications_detected
    assert "không nên tự ý bỏ hoặc ngừng thuốc chống đông" in result.guidance


def test_anticoagulant_from_context_blocks_nsaid_self_use(pipeline):
    result = pipeline.evaluate(
        "Tôi đau lưng, dùng ibuprofen được không?",
        {"current_medications": ["apixaban"]},
    )
    assert result.allowed is False
    assert "anticoagulant_nsaid_combination_requires_review" in result.contraindications_detected


def test_kidney_disease_blocks_nsaid_self_use(pipeline):
    result = pipeline.evaluate(
        "Đau đầu thì uống ibuprofen được không?",
        {"conditions": ["bệnh thận mạn"]},
    )
    assert result.allowed is False
    assert "nsaid_requires_clinician_review" in result.contraindications_detected


def test_pediatric_personalized_dose_requires_more_context(pipeline):
    result = pipeline.evaluate(
        "Paracetamol uống bao nhiêu mg?",
        {"age": 8},
    )
    assert result.allowed is False
    assert "insufficient_pediatric_dosing_context" in result.contraindications_detected


def test_routine_pain_prefers_non_pharmacological_first_line(pipeline):
    query = "Tôi bị đau mỏi cơ sau tập gym, nên uống thuốc gì?"
    result = pipeline.evaluate(query)
    assert result.allowed is True
    assert "non_pharmacological_first_line" in result.warning_notes
    assert "không tự động kê đơn hay chỉ định liều dùng thuốc cá nhân hóa" in result.guidance
