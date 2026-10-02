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


def test_anticoagulant_unauthorized_stopping_warned(pipeline):
    query = "Tôi đang dùng thuốc chống đông và bị chảy máu cam, có nên tự bỏ liều tối nay không?"
    result = pipeline.evaluate(query)
    assert result.allowed is False
    assert "unauthorized_anticoagulant_cessation" in result.contraindications_detected
    assert "không nên tự ý bỏ hoặc ngừng thuốc chống đông" in result.guidance


def test_routine_pain_prefers_non_pharmacological_first_line(pipeline):
    query = "Tôi bị đau mỏi cơ sau tập gym, nên uống thuốc gì?"
    result = pipeline.evaluate(query)
    assert result.allowed is True
    assert "non_pharmacological_first_line" in result.warning_notes
    assert "không tự động kê đơn hay chỉ định liều dùng thuốc cá nhân hóa" in result.guidance
