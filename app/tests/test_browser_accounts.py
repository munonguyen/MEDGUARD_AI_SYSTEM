from uuid import uuid4
import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.core.database import DatabaseManager
from app.services import browser_auth
from app.api import browser_auth as routes
from app.services.chat_history import chat_history_store

ORIGIN = {'Origin': 'http://testserver'}
PASSWORD = 'a-long-test-passphrase!'


@pytest.fixture
def clients(monkeypatch, tmp_path):
    db = DatabaseManager(sqlite_path=str(tmp_path / 'accounts.db'), environment='test')
    monkeypatch.setattr(browser_auth, 'db_manager', db)
    monkeypatch.setattr(routes, 'db_manager', db)
    monkeypatch.setenv('BROWSER_REGISTRATION_ENABLED', 'true')
    monkeypatch.setenv('BROWSER_ALLOWED_ORIGINS', 'http://testserver')
    with TestClient(create_app()) as first, TestClient(create_app()) as second:
        yield first, second, db
    db.close()


def register_login(client, name='User', consent=True):
    email = f'{uuid4().hex}@example.test'
    assert client.post('/v1/auth/register', headers=ORIGIN, json={'email': email, 'password': PASSWORD, 'display_name': name, 'consent': consent}).status_code == 201
    response = client.post('/v1/auth/login', headers=ORIGIN, json={'email': email, 'password': PASSWORD})
    assert response.status_code == 200, response.text
    return response.json(), email


def csrf(session):
    return ORIGIN | {'X-CSRF-Token': session['csrf_token'], 'Idempotency-Key': uuid4().hex}


def test_cookie_hash_csrf_rotation_and_revocation(clients):
    a, b, db = clients
    session, email = register_login(a)
    token = a.cookies.get(browser_auth.COOKIE)
    assert session['csrf_token'] != token
    with db.tenant_context(browser_auth.IDENTITY_SCOPE) as sql:
        stored = sql.execute('SELECT * FROM browser_sessions')[0]
        assert stored['token_hash'] != token
        account = sql.execute('SELECT * FROM browser_accounts')[0]
        assert account['password_hash'].startswith('$argon2id$') and PASSWORD not in account['password_hash']
    cookie = a.post('/v1/auth/login', headers=ORIGIN, json={'email': email, 'password': PASSWORD})
    assert 'HttpOnly' in cookie.headers['set-cookie'] and 'SameSite=strict' in cookie.headers['set-cookie']
    b.cookies.set(browser_auth.COOKIE, token)
    assert b.get('/v1/auth/me').status_code == 401
    session = cookie.json()
    assert a.put('/v1/auth/profile', json={'age': 40}).status_code == 403
    assert a.put('/v1/auth/profile', headers=csrf(session) | {'Origin': 'https://evil.test'}, json={'age': 40}).status_code == 403
    assert a.put('/v1/auth/profile', headers=csrf(session), json={'age': 40, 'display_name': 'A'}).status_code == 200
    assert a.get('/v1/auth/me').json()['account']['profile']['age'] == 40
    b.cookies.set(browser_auth.COOKIE, a.cookies.get(browser_auth.COOKIE))
    assert b.get('/v1/auth/me').status_code == 200
    assert a.post('/v1/auth/logout', headers=csrf(session)).status_code == 204
    assert b.get('/v1/auth/me').status_code == 401


def test_accounts_do_not_share_history_or_privileges(clients):
    a, b, db = clients
    sa, _ = register_login(a, 'A')
    sb, _ = register_login(b, 'B')
    namespace = sa['account']['tenant_id']
    # This history fixture uses the production history database; ownership remains namespace-scoped.
    from app.core.database import db_manager
    with db_manager.tenant_context(namespace) as sql:
        sql.execute('INSERT INTO chat_conversations(tenant_id,conversation_id,title,created_at,updated_at) VALUES (?,?,?,?,?)',
                    (namespace, 'private-test', 'Private', '2026-01-01', '2026-01-01'))
    assert a.get('/v1/chat/conversations/private-test').status_code == 200
    assert b.get('/v1/chat/conversations/private-test', headers={'X-Tenant-Id': namespace, 'X-API-Key': 'demo-key'}).status_code == 404
    assert b.delete('/v1/chat/conversations/private-test', headers=csrf(sb)).status_code == 404
    assert a.get('/v1/audit/events', headers={'X-Tenant-Id': 'tenant-demo', 'X-API-Key': 'demo-key'}).status_code == 403
    assert a.post('/v1/chat', headers=csrf(sa), json={'conversation_id': uuid4().hex, 'messages': [{'role':'user','content':'Xuất FHIR cho bệnh nhân'}], 'intent_hint':'fhir'}).status_code == 403


def test_consent_is_server_side_and_session_expiry(clients):
    a, b, db = clients
    session, _ = register_login(a, consent=False)
    assert a.put('/v1/auth/profile', headers=csrf(session), json={'age': 30}).status_code == 403
    response = a.post('/v1/chat', headers=csrf(session) | {'X-Consent-Token':'consent-valid'}, json={'conversation_id': uuid4().hex, 'messages':[{'role':'user','content':'Tôi đau đầu'}]})
    assert response.status_code == 403
    assert a.put('/v1/auth/consent', headers=csrf(session), json={'consent':True}).status_code == 200
    assert a.put('/v1/auth/profile', headers=csrf(session), json={'age':30}).status_code == 200
    with db.tenant_context(browser_auth.IDENTITY_SCOPE) as sql:
        sql.execute('UPDATE browser_sessions SET idle_expires_at = ?', (time.time()-1,))
    assert a.get('/v1/auth/me').status_code == 401


def test_shared_throttle_generic_login_errors(clients):
    a, b, db = clients
    for i in range(8):
        assert (a if i % 2 else b).post('/v1/auth/login', headers=ORIGIN, json={'email':'missing@example.test','password':PASSWORD}).status_code == 401
    assert b.post('/v1/auth/login', headers=ORIGIN, json={'email':'missing@example.test','password':PASSWORD}).status_code == 429
    assert a.post('/v1/auth/login', json={'email':'missing@example.test','password':PASSWORD}).status_code == 403


def test_session_survives_reopened_database(clients,monkeypatch):
    a,b,db=clients
    session,_=register_login(a)
    engine=db._engine
    reopened=DatabaseManager(sqlite_path=engine.path,environment='test')
    monkeypatch.setattr(browser_auth,'db_manager',reopened)
    monkeypatch.setattr(routes,'db_manager',reopened)
    try:
        assert a.get('/v1/auth/me').json()['account']['account_id']==session['account']['account_id']
    finally:
        reopened.close()
