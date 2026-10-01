from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.services.chat import _extract_monitoring


@pytest.mark.parametrize('message,expected', [('Đường huyết 45 mg/dL','EMERGENCY'),('Đường huyết 3,0 mmol/L','URGENT'),('Đường huyết 3 mmol/L','URGENT'),('Đường huyết 60 mg/dL','URGENT'),('Đường huyết 90 mg/dL','ROUTINE')])
def test_low_glucose_escalates_without_waiting_for_trend(message,expected):
    with TestClient(create_app()) as client:
        response=client.post('/v1/chat',headers={'X-Tenant-Id':'tenant-demo','X-API-Key':'demo-key','Idempotency-Key':uuid4().hex},json={'conversation_id':uuid4().hex,'messages':[{'role':'user','content':message}]})
    assert response.status_code==200
    body=response.json()
    assert body['result']['urgency']==expected
    if expected in {'EMERGENCY','URGENT'}:
        assert body['answer']['next_steps']
        assert not any('Cung cấp các giá trị đo lặp lại' in text for text in body['answer']['next_steps'])
        assert body['answer']['optional_advice']==[]


def test_glucose_units_are_not_guessed():
    assert _extract_monitoring('Đường huyết 45')==[]
    assert _extract_monitoring('Đường huyết 45 mg/dL')[0].value==45
    assert _extract_monitoring('Đường huyết 45 mmol/L')[0].value==810


def test_suicide_is_not_confirmed_workflow_and_hotline_hours_are_honest():
    with TestClient(create_app()) as client:
        response=client.post('/v1/chat',headers={'X-Tenant-Id':'tenant-demo','X-API-Key':'demo-key','Idempotency-Key':uuid4().hex},json={'conversation_id':uuid4().hex,'messages':[{'role':'user','content':'Tôi có ý định tự tử tối nay và đang ở một mình.'}]})
    body=response.json()
    assert body['intent']=='triage' and body['result']['urgency']=='EMERGENCY'
    assert '115' in body['answer']['next_steps'][0]
    assert 'không ở một mình' in body['answer']['next_steps'][0].lower()
    assert 'không phải' in body['answer']['safety_notes'][0]
    assert body['answer']['evidence_state']!='operation_confirmed'


def test_sprain_accent_folding_does_not_trigger_suicide():
    from app.services.ood_guard import evaluate
    for text in ['Tôi bị trẹo cổ chân nhẹ lúc đi bộ, vẫn đi lại được, không biến dạng.', 'Tôi trẹo cổ sau khi tập thể dục.', 'Toi bi treo co chan nhe']:
        result = evaluate(text)
        assert result is None or result.verdict != 'crisis_self_harm'
    assert evaluate('Tôi muốn treo cổ').verdict == 'crisis_self_harm'
    assert evaluate('Tôi trẹo cổ và muốn tự sát').verdict == 'crisis_self_harm'


def test_respiratory_support_is_grounded_and_never_down_triages():
    with TestClient(create_app()) as client:
        def ask(message):
            return client.post('/v1/chat',headers={'X-Tenant-Id':'tenant-demo','X-API-Key':'demo-key','Idempotency-Key':uuid4().hex},json={'conversation_id':uuid4().hex,'messages':[{'role':'user','content':message}]}).json()
        routine=ask('Tôi hắt hơi, sổ mũi, đau họng nhẹ, không sốt, không khó thở.')
        assert routine['result']['urgency']=='ROUTINE'
        assert routine['answer']['optional_advice']
        assert 'kháng sinh' in ' '.join(routine['answer']['next_steps'])
        emergency=ask('Tôi sổ mũi nhưng đang khó thở và SpO2 85%.')
        assert emergency['result']['urgency']=='EMERGENCY'
        assert emergency['answer']['optional_advice']==[]
