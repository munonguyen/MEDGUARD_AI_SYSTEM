"""User-reported toothache and muscle/neck accent-collision regressions."""
import pytest
from app.tests.test_v28_audit_defect_regressions import ask
from app.knowledge.loader import knowledge
from app.services.clinical_text import normalize_search_text


def test_request_language_is_not_changed_to_muscle_strain():
    assert 'can co cach' in normalize_search_text('cần có cách')
    assert 'cang co' not in normalize_search_text('cần có cách giảm đau')


@pytest.mark.parametrize('question', [
    'Tôi đang đau răng,cần có cách nào để hết đau răng',
    'Tôi nhức răng, cần có cách giảm đau',
    'toi dau rang, can co cach nao de het dau rang',
])
def test_toothache_stays_dental_and_gives_bounded_relief(ask, question):
    body = ask(question)
    answer = body['answer']
    text = str(answer).lower()
    assert 'nha sĩ' in text and 'ăn mềm' in text
    assert 'sưng' in text and 'khó nuốt' in text
    assert 'căng cơ' not in text and 'rice' not in text
    assert not answer['clinical_hypotheses']
    assert answer['questions']
    assert any('https://www.nhs.uk/symptoms/toothache/' in s['references'] for s in answer['sources'])


@pytest.mark.parametrize('question', ['tôi đang đâu cơ', 'tôi đang đau cơ', 'toi dau co'])
def test_unlocalized_pain_asks_location_without_inventing_neck_disease(ask, question):
    answer = ask(question)['answer']
    text = str(answer).lower()
    assert 'vùng' in ' '.join(answer['questions']).lower()
    assert 'thoái hóa' not in text and 'gối' not in text and 'rice' not in text
    assert not answer['clinical_hypotheses']


def test_actual_neck_pain_still_has_neck_guidance():
    assert knowledge.find_symptom_guidance('Tôi đau cổ vai gáy sau ngồi lâu')['topic'] == 'neck_shoulder_pain'


def test_negated_dental_complaint_does_not_select_dental_template():
    guidance = knowledge.find_symptom_guidance('Tôi không đau răng, tôi đau lưng sau khi ngồi lâu')
    assert guidance['topic'] == 'back_pain'


def test_pain_with_associated_findings_is_not_muscle_pain():
    guidance = knowledge.find_symptom_guidance('Tôi đau bụng trên rốn. Cơn đau có kèm nóng rát và ợ chua')
    assert guidance and guidance['topic'] not in {'unlocalized_muscle_pain', 'neck_shoulder_pain'}


def test_dental_airway_danger_still_escalates(ask):
    body = ask('Tôi đau răng, sưng cổ và khó thở')
    assert body['result']['urgency'] == 'EMERGENCY'
    assert '115' in str(body['answer'])
