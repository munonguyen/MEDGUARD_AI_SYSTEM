import pytest
from app.tests.test_v28_audit_defect_regressions import ask
from scripts.audit_v28_output_quality import display_projection


@pytest.mark.parametrize('question', ['Có nên ngủ sớm không?', 'Tôi có nên ngủ sớm không?', 'Ngủ sớm có lợi ích gì?'])
def test_simple_sleep_question_is_direct_and_brief(ask, question):
    body = ask(question)
    shown = display_projection(body)
    assert body['answer']['presentation'] == 'brief'
    assert body['answer']['summary'].startswith('Có,')
    assert 'tập trung' in shown['text'] and 'tâm trạng' in shown['text']
    assert len(shown['text'].split()) <= 80
    assert not shown['questions']
    assert not body['answer']['clinical_hypotheses']


def test_explicit_explanation_has_more_relevant_detail(ask):
    body = ask('Giải thích chi tiết lợi ích của ngủ sớm')
    assert body['answer']['presentation'] == 'detailed'
    assert body['answer']['next_steps']
    assert len(display_projection(body)['text'].split()) > 80


@pytest.mark.parametrize('question', [
    'Tôi đang đau ngực dữ dội và khó thở. Có nên ngủ sớm không?',
    'Trả lời ngắn thôi: tôi đau ngực lan tay trái và vã mồ hôi, có nên ngủ sớm không?',
])
def test_brevity_never_replaces_emergency_action_with_sleep_advice(ask, question):
    body = ask(question)
    assert body['result']['urgency'] == 'EMERGENCY'
    assert body['answer']['presentation'] != 'brief'
    assert '115' in display_projection(body)['text']
    assert not body['answer']['questions']


def test_focused_answer_keeps_actions_and_safety_visible(ask):
    body = ask('Tôi đau đầu nhẹ sau khi nhìn màn hình cả ngày.')
    shown = display_projection(body)
    assert body['answer']['presentation'] == 'focused'
    assert body['answer']['clinical_hypotheses']
    assert not shown['sections']['Khả năng cần cân nhắc']
    assert shown['sections']['Bạn nên làm gì lúc này']
    assert shown['sections']['Khi nào cần đi khám / cấp cứu']
    assert len(shown['text'].split()) <= 350
    assert body['answer']['display_next_steps'][-1] == body['answer']['next_steps'][-1]
    assert body['answer']['safety_notes'] == shown['sections']['Khi nào cần đi khám / cấp cứu']


def test_detailed_clinical_question_keeps_full_explanation(ask):
    body = ask('Giải thích chi tiết: tôi đau đầu nhẹ sau khi nhìn màn hình cả ngày.')
    assert body['answer']['presentation'] == 'detailed'
    assert body['answer']['display_next_steps'] is None


def test_drug_risk_remains_in_primary_content(ask):
    body = ask('Tôi đang uống warfarin. Tôi có thể uống ibuprofen khi đau đầu không?')
    assert display_projection(body)['sections']['Dữ kiện chính'] == body['answer']['key_points']
