"""Real public-API controls for bounded chest calibration; no label edits."""
import pytest
from app.tests.test_v28_audit_defect_regressions import ask


@pytest.mark.parametrize('question,urgency', [
 ('Tôi đau ngực sau chống đẩy, không khó thở, không vã mồ hôi, không đau lan', 'ROUTINE'),
 ('Tôi nặng ngực khi leo cầu thang, không khó thở, không vã mồ hôi, không đau lan', 'URGENT'),
 ('Tôi nặng ngực khi leo cầu thang, không khó thở, không vã mồ hôi, không đau lan nhưng đau kéo dài không hết khi nghỉ', 'EMERGENCY'),
 ('Tôi có bệnh mạch vành, đau ngực sau chống đẩy, không khó thở, không vã mồ hôi, không đau lan', 'EMERGENCY'),
 ('Tôi đau ngực sau chống đẩy, không khó thở, không vã mồ hôi, không đau lan, SpO2 89%', 'EMERGENCY'),
 ('Tôi đau ngực dữ dội sau chống đẩy, không khó thở, không vã mồ hôi, không đau lan', 'EMERGENCY'),
 ('Tôi đau ngực sau chống đẩy; lúc đầu không khó thở, không vã mồ hôi, không đau lan nhưng giờ khó thở và vã mồ hôi', 'EMERGENCY'),
 ('Tôi đau ngực sau chống đẩy', 'EMERGENCY'),
 ('Tôi nặng ngực khi leo cầu thang', 'EMERGENCY'),
 ('Tôi đang mang thai và bị đau bụng kèm chảy máu. Tôi nên làm gì?', 'EMERGENCY'),
])
def test_context_reaches_public_api_without_weakening_emergency_controls(ask, question, urgency):
    body = ask(question)
    assert body['result']['urgency'] == urgency
    assert '115' in str(body['answer'])
    if urgency == 'URGENT':
        assert body['answer']['questions'], 'Urgent incomplete context must ask a management-changing question'
