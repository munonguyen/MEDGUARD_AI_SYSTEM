import os
from dataclasses import replace
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from scripts.configure_doctor_chat import profile, write_profile


def test_profile_is_private_and_preserves_review_gates(tmp_path):
    values = profile('http://localhost:4000/v1', 'synthetic-local-key', 'chat_completions')
    assert values['MEDGUARD_AGENT_MODE'] == 'enforced'
    assert values['MEDGUARD_VERIFIER_WEB_SEARCH_REQUIRED'] == 'true'
    assert values['MEDGUARD_AGENT_SYNC_ENABLED'] == 'true'
    path = tmp_path / '.env.doctor'
    write_profile(path, values)
    if os.name != 'nt': assert path.stat().st_mode & 0o777 == 0o600
    from dotenv import dotenv_values
    assert dotenv_values(path) == values
    assert not list(tmp_path.glob('.doctor-config-*'))


def test_remote_key_requires_https():
    import pytest
    for url in ['http://remote.example/v1', 'https://user:password@example.com/v1', 'https://example.com/v1?key=secret']:
        with pytest.raises(ValueError): profile(url, 'synthetic-key', 'responses')


def test_status_explains_missing_gateway_and_never_exposes_key(monkeypatch):
    import app.services.companion_status as status
    monkeypatch.setattr(status, 'settings', replace(settings, llm_gateway_url=None, llm_gateway_api_key=None))
    with TestClient(app) as client:
        result = client.get('/v1/companion/status').json()
        assert result['configured'] is False
        assert 'configure_doctor_chat.py' in result['message']
    monkeypatch.setattr(status, 'settings', replace(settings, llm_gateway_url='https://example.com/v1', llm_gateway_api_key='private-gateway-secret'))
    with TestClient(app) as client:
        result = client.get('/v1/companion/status')
        assert result.json()['configured'] is True
        assert 'private-gateway-secret' not in result.text
        assert 'example.com' not in result.text


def test_wizard_probes_all_aliases_and_does_not_write_on_failure(tmp_path, monkeypatch, capsys):
    import json
    import urllib.request
    import scripts.configure_doctor_chat as wizard
    aliases = ['medguard-answer','medguard-verifier','medguard-clinical-answer',
               'medguard-clinical-verifier','medguard-pharma-answer','medguard-pharma-verifier']
    requests = []
    class Result:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit):
            return json.dumps({'data':[{'id':a} for a in aliases]} if len(requests)==1 else {'choices':[{'message':{'content':'OK'}}]}).encode()
    class Opener:
        def open(self, request, **kwargs):
            requests.append(request)
            return Result()
    monkeypatch.setattr(urllib.request,'build_opener',lambda *args:Opener())
    wizard.check_models('http://localhost:4000/v1','private-synthetic-key')
    assert len(requests)==7
    assert {json.loads(r.data)['model'] for r in requests[1:]} == set(aliases)
    monkeypatch.setattr(wizard.getpass,'getpass',lambda *args:'private-synthetic-key')
    def fail(*args): raise RuntimeError('private-synthetic-key')
    monkeypatch.setattr(wizard,'check_models',fail)
    path=tmp_path/'.env.doctor'
    assert wizard.main(['--output',str(path)])==1
    assert not path.exists()
    assert 'private-synthetic-key' not in capsys.readouterr().out
