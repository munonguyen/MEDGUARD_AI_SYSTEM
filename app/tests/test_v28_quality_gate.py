import pytest
from app.services.clinical_reasoning.quality_gate import ResponseQualityReviewer


@pytest.fixture
def reviewer():
    return ResponseQualityReviewer()


def test_rejects_cardiopulmonary_leakage_in_allergy_case(reviewer):
    query = "Sau khi uống thuốc mới tôi nổi vài mảng mề đay ở cánh tay"
    leaked_response = (
        "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức. "
        "Việc bạn thấy đỡ sau khi nghỉ không xóa các dấu hiệu cảnh báo tim–phổi đã xuất hiện trước đó."
    )
    result = reviewer.review(query, leaked_response)
    assert result.passed is False
    assert "context_leakage_cardiopulmonary_in_allergy" in result.violations


def test_rejects_eye_strain_leakage_in_thunderclap_headache(reviewer):
    query = "Vừa rồi đột ngột xuất hiện cơn đau đầu dữ dội nhất từ trước tới giờ"
    leaked_response = (
        "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức. "
        "Nhìn gần và tập trung vào màn hình trong thời gian dài làm hệ điều tiết và hội tụ của mắt hoạt động liên tục."
    )
    result = reviewer.review(query, leaked_response)
    assert result.passed is False
    assert "context_leakage_eye_strain_in_severe_case" in result.violations


def test_rejects_hypothetical_question_treated_as_active_emergency(reviewer):
    query = "Nếu bắt đầu sưng môi hoặc khó thở thì tôi phải làm gì?"
    panic_response = (
        "Gọi 115 hoặc đến khoa Cấp cứu gần nhất ngay lập tức. "
        "Các dấu hiệu hiện tại nằm trong nhóm cảnh báo cần xử trí cấp cứu."
    )
    result = reviewer.review(query, panic_response)
    assert result.passed is False
    assert "hypothetical_treated_as_current_emergency" in result.violations


def test_rejects_unconditional_immediate_action_for_hypothetical_question(reviewer):
    query = "Nếu bắt đầu sưng môi hoặc khó thở thì tôi phải làm gì?"
    panic_response = "Gọi 115 ngay lập tức và đến khoa Cấp cứu ngay bây giờ."
    result = reviewer.review(query, panic_response)
    assert result.passed is False
    assert "hypothetical_treated_as_current_emergency" in result.violations


def test_allows_conditional_emergency_safety_net_for_hypothetical_question(reviewer):
    query = "Nếu bắt đầu sưng môi hoặc khó thở thì tôi phải làm gì?"
    good_response = (
        "Nếu sưng môi, nghẹn họng hoặc khó thở thực sự xuất hiện, hãy gọi 115 ngay lập tức. "
        "Hiện câu hỏi của bạn đang ở dạng dự phòng."
    )
    result = reviewer.review(query, good_response)
    assert result.passed is True


def test_rejects_negated_leg_weakness_triggering_cauda_equina(reviewer):
    query = "Tôi đau lưng sau ngồi lâu, không có yếu chân hay sốt"
    bad_response = (
        "Gọi 115 hoặc đến khoa Cấp cứu gần nhất. "
        "Dấu hiệu cảnh báo chèn ép hoặc tổn thương thần kinh vùng yên ngựa và chùm đuôi ngựa."
    )
    result = reviewer.review(query, bad_response)
    assert result.passed is False
    assert "negation_false_positive_cauda_equina" in result.violations


def test_rejects_plain_khong_yeu_chan_false_positive(reviewer):
    query = "Tôi đau lưng nhưng không yếu chân"
    bad_response = (
        "Bạn có dấu hiệu chèn ép hoặc tổn thương thần kinh và hội chứng chùm đuôi ngựa."
    )
    result = reviewer.review(query, bad_response)
    assert result.passed is False
    assert "negation_false_positive_cauda_equina" in result.violations


def test_passes_well_aligned_clinical_response(reviewer):
    query = "Tôi đau cơ sau khi tập gym hôm qua"
    good_response = (
        "Cảm giác đau mỏi cơ sau tập luyện thường phù hợp với đau cơ khởi phát muộn (DOMS). "
        "Bạn nên nghỉ ngơi, uống đủ nước và chườm ấm thư giãn cơ. Theo dõi và đi khám nếu đau kéo dài trên 7 ngày."
    )
    result = reviewer.review(query, good_response)
    assert result.passed is True
    assert result.violations == []
