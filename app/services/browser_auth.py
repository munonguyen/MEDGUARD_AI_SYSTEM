"""Revocable shared-database sessions; browser identity never accepts tenant headers."""
from __future__ import annotations

from hashlib import sha256
import hmac
import json
import os
import secrets
import time
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import HTTPException, Request

from app.core.config import settings
from app.core.database import db_manager

COOKIE = 'medguard_session'
IDENTITY_SCOPE = '__browser_identity__'
SESSION_SECONDS = 7 * 24 * 3600
IDLE_SECONDS = 30 * 60
HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = HASHER.hash(secrets.token_urlsafe(32))


def fail(code: str, status: int = 401):
    raise HTTPException(status_code=status, detail={'error_code': code, 'message': {
        'authentication_required': 'Vui lòng đăng nhập lại.',
        'invalid_credentials': 'Email hoặc mật khẩu không đúng.',
        'csrf_rejected': 'Phiên xác thực không hợp lệ. Vui lòng tải lại trang.',
        'auth_rate_limited': 'Quá nhiều lần thử. Vui lòng thử lại sau 15 phút.',
        'account_unavailable': 'Không thể tạo tài khoản với thông tin này.',
        'registration_disabled': 'Hệ thống chưa mở đăng ký tài khoản.',
        'patient_role_required': 'Tài khoản này không có quyền thực hiện thao tác vận hành.',
    }.get(code, code)})


def registration_enabled() -> bool:
    return os.getenv('BROWSER_REGISTRATION_ENABLED', 'false' if settings.environment == 'production' else 'true').lower() == 'true'


def token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def csrf_token(token: str) -> str:
    return token_hash('csrf:' + token)


def check_origin(request: Request):
    configured = os.getenv('BROWSER_ALLOWED_ORIGINS', '')
    allowed = {value.strip().rstrip('/') for value in configured.split(',') if value.strip()}
    if not allowed and settings.environment != 'production':
        allowed = {str(request.base_url).rstrip('/')}
    origin = request.headers.get('origin')
    if not origin or origin.rstrip('/') not in allowed:
        fail('csrf_rejected', 403)


def throttle(request: Request, email: str):
    # Fixed windows are persisted and atomically incremented across all API replicas.
    now = time.time()
    client = request.client.host if request.client else 'unknown'
    buckets = [('email:' + email, 8), ('ip:' + client, 30)]
    limited = False
    with db_manager.tenant_context(IDENTITY_SCOPE) as db:
        for identity, limit in buckets:
            bucket = token_hash(identity)
            rows = db.execute('''INSERT INTO browser_auth_attempts(bucket, attempts, window_start)
                VALUES (?, 1, ?) ON CONFLICT(bucket) DO UPDATE SET
                attempts = CASE WHEN browser_auth_attempts.window_start <= ? THEN 1 ELSE browser_auth_attempts.attempts + 1 END,
                window_start = CASE WHEN browser_auth_attempts.window_start <= ? THEN ? ELSE browser_auth_attempts.window_start END
                RETURNING attempts''', (bucket, now, now - 900, now - 900, now))
            limited = limited or rows[0]['attempts'] > limit
        db.execute('DELETE FROM browser_auth_attempts WHERE window_start < ?', (now - 86400,))
    if limited:
        fail('auth_rate_limited', 429)


def authenticate(request: Request, *, mutation: bool = True) -> dict:
    token = request.cookies.get(COOKIE, '')
    if not token or len(token) > 128:
        fail('authentication_required')
    if mutation and request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        check_origin(request)
        if not hmac.compare_digest(request.headers.get('x-csrf-token', ''), csrf_token(token)):
            fail('csrf_rejected', 403)
    now = time.time()
    with db_manager.tenant_context(IDENTITY_SCOPE) as db:
        rows = db.execute('''SELECT a.*, s.expires_at FROM browser_sessions s
            JOIN browser_accounts a ON a.account_id = s.account_id
            WHERE s.token_hash = ? AND s.expires_at > ? AND s.idle_expires_at > ?''', (token_hash(token), now, now))
        if not rows:
            fail('authentication_required')
        db.execute('UPDATE browser_sessions SET idle_expires_at = ? WHERE token_hash = ?',
                   (min(now + IDLE_SECONDS, rows[0]['expires_at']), token_hash(token)))
    account = dict(rows[0])
    request.state.browser_account = account
    return account


def public_account(account: dict) -> dict:
    return {key: account[key] for key in ('account_id', 'display_name', 'email', 'tenant_id')} | {
        'role': 'patient', 'consent': bool(account['consent_at']),
        'profile': json.loads(account['profile_json']),
    }


def new_session(account_id: str) -> str:
    token = secrets.token_urlsafe(32)
    now = time.time()
    with db_manager.tenant_context(IDENTITY_SCOPE) as db:
        db.execute('DELETE FROM browser_sessions WHERE expires_at <= ? OR idle_expires_at <= ?', (now, now))
        db.execute('INSERT INTO browser_sessions(token_hash, account_id, expires_at, idle_expires_at) VALUES (?, ?, ?, ?)',
                   (token_hash(token), account_id, now + SESSION_SECONDS, now + IDLE_SECONDS))
    return token


def set_cookie(response, token: str):
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=settings.environment == 'production', samesite='strict', path='/')
