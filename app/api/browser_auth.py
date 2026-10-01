from __future__ import annotations

import json
import re
import time
from uuid import uuid4

from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.core.database import db_manager
from app.models.chat import ChatContext
from app.services.browser_auth import (
    COOKIE, IDENTITY_SCOPE, HASHER, DUMMY_HASH, authenticate, check_origin,
    csrf_token, fail, new_session, public_account, registration_enabled, set_cookie, throttle,
)

router = APIRouter(prefix='/auth', tags=['Account'])


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator('email')
    @classmethod
    def email_format(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('Email không hợp lệ')
        return value


class Registration(Credentials):
    display_name: str = Field(min_length=1, max_length=80)
    consent: bool = False

    @field_validator('display_name')
    @classmethod
    def display_name_not_blank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Tên hiển thị không được để trống')
        return value


class ProfileUpdate(ChatContext):
    display_name: str | None = Field(default=None, max_length=80)


class ConsentUpdate(BaseModel):
    consent: bool


@router.get('/config')
def config():
    return {'registration_enabled': registration_enabled()}


@router.post('/register', status_code=201)
def register(body: Registration, request: Request):
    check_origin(request)
    if not registration_enabled():
        fail('registration_disabled', 403)
    throttle(request, body.email)
    account_id = uuid4().hex
    namespace = f'{settings.allowed_tenants[0][:24]}.u{account_id}'
    password_hash = HASHER.hash(body.password)
    now = time.time()
    with db_manager.tenant_context(IDENTITY_SCOPE) as db:
        rows = db.execute('''INSERT INTO browser_accounts(account_id,email,password_hash,display_name,tenant_id,consent_at,created_at)
            VALUES(?,?,?,?,?,?,?) ON CONFLICT(email) DO NOTHING RETURNING account_id''',
            (account_id, body.email, password_hash, body.display_name.strip(), namespace, now if body.consent else None, now))
        if not rows:
            fail('account_unavailable', 400)
        if db.dialect == 'postgresql':
            db.execute('INSERT INTO tenants(tenant_id, name) VALUES (?, ?)', (namespace, 'Patient account'))
    # Registration does not silently establish a session; explicit login rotates tokens.
    return {'created': True}


@router.post('/login')
def login(body: Credentials, request: Request, response: Response):
    check_origin(request)
    throttle(request, body.email)
    with db_manager.tenant_context(IDENTITY_SCOPE) as db:
        rows = db.execute('SELECT * FROM browser_accounts WHERE email = ?', (body.email,))
    account = rows[0] if rows else None
    try:
        valid = HASHER.verify(account['password_hash'] if account else DUMMY_HASH, body.password)
    except (VerificationError, InvalidHashError):
        valid = False
    if not account or not valid:
        fail('invalid_credentials')
    # Re-login revokes the current session (session fixation protection).
    previous = request.cookies.get(COOKIE)
    if previous:
        from app.services.browser_auth import token_hash
        with db_manager.tenant_context(IDENTITY_SCOPE) as db:
            db.execute('DELETE FROM browser_sessions WHERE token_hash = ?', (token_hash(previous),))
    token = new_session(account['account_id'])
    set_cookie(response, token)
    return {'account': public_account(account), 'csrf_token': csrf_token(token)}


@router.get('/me')
def me(request: Request):
    account = authenticate(request)
    return {'account': public_account(account), 'csrf_token': csrf_token(request.cookies[COOKIE])}


@router.post('/logout', status_code=204)
def logout(request: Request, response: Response):
    authenticate(request)
    from app.services.browser_auth import token_hash
    with db_manager.tenant_context(IDENTITY_SCOPE) as db:
        db.execute('DELETE FROM browser_sessions WHERE token_hash = ?', (token_hash(request.cookies[COOKIE]),))
    response.delete_cookie(COOKIE, path='/', secure=settings.environment == 'production', httponly=True, samesite='strict')


@router.post('/logout-all', status_code=204)
def logout_all(request: Request, response: Response):
    account = authenticate(request)
    with db_manager.tenant_context(IDENTITY_SCOPE) as db:
        db.execute('DELETE FROM browser_sessions WHERE account_id = ?', (account['account_id'],))
    response.delete_cookie(COOKIE, path='/')


@router.put('/profile')
def profile(body: ProfileUpdate, request: Request):
    account = authenticate(request)
    if not account['consent_at']:
        fail('consent_required', 403)
    # Do not persist previous inference results or arbitrary client keys.
    value = body.model_dump(exclude={'last_result'}, exclude_none=True)
    serialized = json.dumps(value, ensure_ascii=False)
    if len(serialized.encode()) > 16384:
        fail('profile_too_large', 413)
    with db_manager.tenant_context(IDENTITY_SCOPE) as db:
        db.execute('UPDATE browser_accounts SET profile_json = ? WHERE account_id = ?', (serialized, account['account_id']))
    return {'profile': value}


@router.put('/consent')
def consent(body: ConsentUpdate, request: Request):
    account = authenticate(request)
    with db_manager.tenant_context(IDENTITY_SCOPE) as db:
        db.execute('UPDATE browser_accounts SET consent_at = ? WHERE account_id = ?',
                   (time.time() if body.consent else None, account['account_id']))
    return {'consent': body.consent}
