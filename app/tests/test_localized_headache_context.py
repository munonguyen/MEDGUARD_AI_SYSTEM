from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.services.clinical_text import normalize_search_text,contains_affirmed_phrase
from app.services.risk_memory import should_start_new_episode
from scripts.audit_v28_output_quality import display_projection


@pytest.mark.parametrize('query',['Tôi đang đau góc trái đầu','Tôi đau bên phải đầu','Tôi nhức ở vùng sau đầu','Tôi đau phía trái đầu'])
def test_anatomical_relation_is_understood(query):
    assert contains_affirmed_phrase(normalize_search_text(query),'dau dau')


@pytest.mark.parametrize('query',['Tôi không đau góc trái đầu','Tôi đau góc trái đầu gối','Tôi đau tay trái, đầu ngón tay tê'])
def test_negations_and_non_head_anatomy_do_not_create_headache(query):
    assert not contains_affirmed_phrase(normalize_search_text(query),'dau dau')


def test_new_head_complaint_does_not_inherit_arm_guidance(monkeypatch):
    from app.services import chat
    monkeypatch.setattr(chat.active_learning_store,'capture_case',lambda **kw:None)
    with TestClient(create_app()) as client:
        key=uuid4().hex
        response=client.post('/v1/chat',headers={'X-API-Key':'demo-key','X-Tenant-Id':'tenant-demo','X-Consent-Token':'consent-test','Idempotency-Key':key},json={'conversation_id':key,'messages':[{'role':'user','content':'Tôi đang căng cơ tay trái và cần phải làm gì'},{'role':'user','content':'Tôi đang đau góc trái đầu'}]})
        assert response.status_code==200
        body=response.json();shown=display_projection(body)['text']
        assert body['intent']=='triage'
        assert body['extracted']['episode_switched']
        assert 'đầu' in shown and '115' in str(body['answer'])
        assert 'RICE' not in shown and 'căng cơ tay' not in shown
        assert body['result']['recommended_specialty']['code']!='MUSCULOSKELETAL'


def test_explicit_continuation_keeps_related_risk():
    assert not should_start_new_episode('Ngoài ra tôi đau góc trái đầu','Tôi đau ngực và khó thở')


def test_unknown_complaint_still_reaches_writer_and_records_knowledge_gap(tmp_path,monkeypatch):
    from app.services import chat
    from app.services.knowledge_pool import get_knowledge_pool
    monkeypatch.setenv('MEDGUARD_KNOWLEDGE_POOL_DATABASE',str(tmp_path/'pool.sqlite3'))
    monkeypatch.setattr(chat.active_learning_store,'capture_case',lambda **kw:None)
    from dataclasses import replace
    monkeypatch.setattr(chat,'settings',replace(chat.settings,agent_mode='enforced',agent_sync_enabled=True,agent_coverage_scope='all'))
    calls=[]
    original=chat.answer_agent_pipeline.generate_response
    def observed(**kwargs):
        calls.append(kwargs['question'])
        return original(**kwargs)
    monkeypatch.setattr(chat.answer_agent_pipeline,'generate_response',observed)
    with TestClient(create_app()) as client:
        key=uuid4().hex;query='Tôi đang khó chịu ở vùng zyxnovel, cần làm gì?'
        response=client.post('/v1/chat',headers={'X-API-Key':'demo-key','X-Tenant-Id':'tenant-demo','X-Consent-Token':'consent-test','Idempotency-Key':key},json={'conversation_id':key,'intent_hint':'triage','messages':[{'role':'user','content':query}]})
        assert response.status_code==200
        assert calls==[query]
        assert response.json()['verification_status']=='unavailable'
        assert response.json()['answer_origin']=='deterministic_fallback'
        assert response.json()['answer']['questions']
        gaps=get_knowledge_pool().inventory()['gaps']
        assert any(g['reason']=='no_matching_guidance' for g in gaps)
        assert 'zyxnovel' not in str(gaps)
