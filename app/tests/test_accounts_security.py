"""Real HTTP authentication/security regressions; email delivery is stubbed explicitly."""

import time
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.core.accounts import AccountStore, COOKIE, digest

PASSWORD = "a strong unique password 27!"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDGUARD_AUTH_DATABASE", str(tmp_path / "accounts.sqlite3"))
    monkeypatch.delenv("MEDGUARD_REQUIRE_VERIFIED_EMAIL", raising=False)
    monkeypatch.delenv("MEDGUARD_ENVIRONMENT", raising=False)
    return create_app()


def signup(c, email="patient@example.com"):
    r = c.post(
        "/v1/auth/register",
        json={"email": email, "password": PASSWORD, "consent": True},
    )
    assert r.status_code == 201, r.text
    r = c.post("/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["csrf_token"]


def h(csrf):
    return {"X-CSRF-Token": csrf, "Idempotency-Key": uuid4().hex}


def test_hash_cookie_and_session_metadata(app):
    c = TestClient(app)
    csrf = signup(c)
    raw = c.cookies.get(COOKIE)
    assert raw and len(raw) >= 40
    with app.state.accounts.db() as db:
        user = db.execute("SELECT * FROM users").fetchone()
        session = db.execute("SELECT * FROM sessions").fetchone()
    assert (
        user["password"].startswith("$argon2id$") and PASSWORD not in user["password"]
    )
    assert session["token"] == digest(raw) and session["csrf"] == digest(csrf)
    assert raw not in c.get("/v1/auth/sessions").text
    assert c.get("/v1/auth/me").json()["user"]["role"] == "patient"


def test_http_only_and_strict_cookie(app):
    c = TestClient(app)
    signup(c)
    r = c.post(
        "/v1/auth/login", json={"email": "patient@example.com", "password": PASSWORD}
    )
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie


@pytest.mark.parametrize(
    "extra", [{"role": "admin"}, {"consent": False}, {"password": "short"}]
)
def test_registration_rejects_escalation_missing_consent_and_weak_password(app, extra):
    c = TestClient(app)
    data = {
        "email": "patient@example.com",
        "password": PASSWORD,
        "consent": True,
        **extra,
    }
    assert c.post("/v1/auth/register", json=data).status_code in (400, 422)
    with app.state.accounts.db() as db:
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_logout_requires_csrf_and_rejects_cross_origin(app):
    c = TestClient(app)
    csrf = signup(c)
    assert c.post("/v1/auth/logout").status_code == 403
    assert (
        c.post(
            "/v1/auth/logout", headers={**h(csrf), "Origin": "https://attacker.invalid"}
        ).status_code
        == 403
    )
    assert c.post("/v1/auth/logout", headers=h(csrf)).status_code == 200
    assert c.get("/v1/auth/me").status_code == 401


def test_expired_or_forged_session_cannot_downgrade_to_demo_key(app):
    c = TestClient(app)
    signup(c)
    raw = c.cookies.get(COOKIE)
    with app.state.accounts.db() as db:
        db.execute("UPDATE sessions SET expires=?", (time.time() - 1,))
    r = c.get(
        "/v1/chat/conversations",
        headers={"X-Tenant-Id": "tenant-demo", "X-API-Key": "demo-key"},
    )
    assert r.status_code == 401
    c.cookies.set(COOKIE, "forged", domain="testserver.local", path="/")
    assert c.get("/v1/auth/me").status_code == 401


def test_idle_expiry(app):
    c = TestClient(app)
    signup(c)
    with app.state.accounts.db() as db:
        db.execute("UPDATE sessions SET last_seen=?", (time.time() - 1801,))
    assert c.get("/v1/auth/me").status_code == 401


def test_logout_all_revokes_other_devices(app):
    a, b = TestClient(app), TestClient(app)
    csrf = signup(a)
    b.post(
        "/v1/auth/login", json={"email": "patient@example.com", "password": PASSWORD}
    )
    assert a.post("/v1/auth/logout-all", headers=h(csrf)).status_code == 200
    assert b.get("/v1/auth/me").status_code == 401


def test_change_password_invalidates_sessions(app):
    c = TestClient(app)
    csrf = signup(c)
    assert (
        c.post(
            "/v1/auth/password",
            headers=h(csrf),
            json={
                "current_password": PASSWORD,
                "new_password": "another strong unique pass 28!",
            },
        ).status_code
        == 200
    )
    assert c.get("/v1/auth/me").status_code == 401
    assert (
        c.post(
            "/v1/auth/login",
            json={"email": "patient@example.com", "password": PASSWORD},
        ).status_code
        == 401
    )


def test_brute_force_throttled(app):
    c = TestClient(app)
    for _ in range(10):
        assert (
            c.post(
                "/v1/auth/login",
                json={"email": "unknown@example.com", "password": "incorrect"},
            ).status_code
            == 401
        )
    assert (
        c.post(
            "/v1/auth/login",
            json={"email": "unknown@example.com", "password": "incorrect"},
        ).status_code
        == 429
    )


def test_cross_account_history_and_admin_denial(app):
    a, b = TestClient(app), TestClient(app)
    ca = signup(a)
    cb = signup(b, "other@example.com")
    conversation = uuid4().hex
    r = a.post(
        "/v1/chat",
        headers=h(ca),
        json={
            "conversation_id": conversation,
            "messages": [{"role": "user", "content": "Có nên ngủ sớm không?"}],
        },
    )
    assert r.status_code == 200, r.text
    assert conversation in a.get("/v1/chat/conversations").text
    assert (
        conversation
        not in b.get(
            "/v1/chat/conversations",
            headers={"X-Tenant-Id": "tenant-demo", "X-API-Key": "demo-key"},
        ).text
    )
    assert b.get("/v1/chat/conversations/" + conversation).status_code in (403, 404)
    assert a.get("/v1/audit/events").status_code == 403


def test_other_account_cannot_revoke_session(app):
    a, b = TestClient(app), TestClient(app)
    ca = signup(a)
    cb = signup(b, "other@example.com")
    sid = a.get("/v1/auth/sessions").json()["sessions"][0]["id"]
    assert b.delete("/v1/auth/sessions/" + sid, headers=h(cb)).status_code == 200
    assert a.get("/v1/auth/me").status_code == 200


def test_reset_single_use_and_expired_tokens(app):
    c = TestClient(app)
    signup(c)
    uid = c.get("/v1/auth/me").json()["user"]["id"]
    token = app.state.accounts.token(uid, "reset")
    assert (
        c.post(
            "/v1/auth/reset-password",
            json={"token": token, "password": "brand new strong password 29!"},
        ).status_code
        == 200
    )
    assert c.get("/v1/auth/me").status_code == 401
    assert (
        c.post(
            "/v1/auth/reset-password", json={"token": token, "password": PASSWORD}
        ).status_code
        == 400
    )
    token = app.state.accounts.token(uid, "reset")
    with app.state.accounts.db() as db:
        db.execute("UPDATE tokens SET expires=?", (time.time() - 1,))
    assert (
        c.post(
            "/v1/auth/reset-password", json={"token": token, "password": PASSWORD}
        ).status_code
        == 400
    )


def test_email_recovery_has_generic_response_and_no_returned_token(app, monkeypatch):
    monkeypatch.setenv("MEDGUARD_SMTP_HOST", "configured.example")
    monkeypatch.setenv("MEDGUARD_PUBLIC_ORIGIN", "http://testserver")
    deliveries = []
    monkeypatch.setattr(
        "app.api.accounts.send_email", lambda *args: deliveries.append(args)
    )
    c = TestClient(app)
    signup(c)
    a = c.post("/v1/auth/forgot-password", json={"email": "patient@example.com"})
    b = c.post("/v1/auth/forgot-password", json={"email": "unknown@example.com"})
    assert a.json() == b.json() and len(deliveries) == 2
    assert deliveries[-1][1] not in a.text


def test_mfa_enrollment_reauth_and_replay_guard(app):
    c = TestClient(app)
    csrf = signup(c)
    assert (
        c.post(
            "/v1/auth/mfa/setup", headers=h(csrf), json={"current_password": "wrong"}
        ).status_code
        == 401
    )
    r = c.post(
        "/v1/auth/mfa/setup", headers=h(csrf), json={"current_password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    setup = r.json()
    step = int(time.time() // 30)
    code = app.state.accounts.totp(setup["secret"], step)
    assert (
        c.post(
            "/v1/auth/mfa/enable",
            headers=h(csrf),
            json={"token": setup["setup_token"], "code": code},
        ).status_code
        == 200
    )
    assert c.get("/v1/auth/me").status_code == 401
    assert (
        c.post(
            "/v1/auth/login",
            json={"email": "patient@example.com", "password": PASSWORD},
        ).status_code
        == 401
    )
    assert (
        c.post(
            "/v1/auth/login",
            json={"email": "patient@example.com", "password": PASSWORD, "otp": code},
        ).status_code
        == 401
    )
    with app.state.accounts.db() as db:
        row = db.execute("SELECT * FROM users").fetchone()
        assert setup["secret"] not in row["mfa"]
    # Deterministic clock in test, not a real 30-second wait.
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "app.core.accounts.time.time", return_value=(step + 1) * 30 + 1
    ):
        next_code = app.state.accounts.totp(setup["secret"], step + 1)
        assert (
            c.post(
                "/v1/auth/login",
                json={
                    "email": "patient@example.com",
                    "password": PASSWORD,
                    "otp": next_code,
                },
            ).status_code
            == 200
        )


def test_csrf_stable_across_tabs(app):
    c = TestClient(app)
    csrf = signup(c)
    assert c.get("/v1/auth/csrf").json()["csrf_token"] == csrf
    assert c.get("/v1/auth/csrf").json()["csrf_token"] == csrf
    assert c.post("/v1/auth/logout", headers=h(csrf)).status_code == 200


def test_mfa_recovery_single_use_and_sensitive_reauthentication(app):
    c = TestClient(app)
    csrf = signup(c)
    setup = c.post(
        "/v1/auth/mfa/setup", headers=h(csrf), json={"current_password": PASSWORD}
    ).json()
    code = app.state.accounts.totp(setup["secret"], int(time.time() // 30))
    result = c.post(
        "/v1/auth/mfa/enable",
        headers=h(csrf),
        json={"token": setup["setup_token"], "code": code},
    )
    assert result.status_code == 200
    backups = result.json()["recovery_codes"]
    assert len(set(backups)) == 10
    with app.state.accounts.db() as db:
        codes = [r["code"] for r in db.execute("SELECT * FROM recovery_codes")]
        assert backups[0] not in codes
    payload = {"email": "patient@example.com", "password": PASSWORD, "otp": backups[0]}
    result = c.post("/v1/auth/login", json=payload)
    assert result.status_code == 200
    csrf = result.json()["csrf_token"]
    assert c.post("/v1/auth/login", json=payload).status_code == 401
    assert (
        c.post(
            "/v1/auth/mfa/disable",
            headers=h(csrf),
            json={"current_password": PASSWORD, "otp": backups[0]},
        ).status_code
        == 401
    )
    assert (
        c.post(
            "/v1/auth/mfa/disable",
            headers=h(csrf),
            json={"current_password": PASSWORD, "otp": backups[1]},
        ).status_code
        == 200
    )
    assert c.get("/v1/auth/me").status_code == 401
    with app.state.accounts.db() as db:
        assert db.execute("SELECT COUNT(*) FROM recovery_codes").fetchone()[0] == 0
        assert (
            db.execute(
                "SELECT COUNT(*) FROM account_events WHERE event='mfa_recovery_used'"
            ).fetchone()[0]
            == 2
        )
    assert (
        c.post(
            "/v1/auth/login",
            json={"email": "patient@example.com", "password": PASSWORD},
        ).status_code
        == 200
    )


def test_token_purpose_and_verified_email_gate(app, monkeypatch):
    c = TestClient(app)
    signup(c)
    uid = c.get("/v1/auth/me").json()["user"]["id"]
    verify = app.state.accounts.token(uid, "verify")
    reset = app.state.accounts.token(uid, "reset")
    assert (
        c.post(
            "/v1/auth/reset-password", json={"token": verify, "password": PASSWORD}
        ).status_code
        == 400
    )
    assert c.post("/v1/auth/verify-email", json={"token": reset}).status_code == 400
    monkeypatch.setenv("MEDGUARD_REQUIRE_VERIFIED_EMAIL", "true")
    assert (
        c.post(
            "/v1/auth/login",
            json={"email": "patient@example.com", "password": PASSWORD},
        ).status_code
        == 403
    )
    assert c.post("/v1/auth/verify-email", json={"token": verify}).status_code == 200
    assert c.post("/v1/auth/verify-email", json={"token": verify}).status_code == 400
    assert (
        c.post(
            "/v1/auth/login",
            json={"email": "patient@example.com", "password": PASSWORD},
        ).status_code
        == 200
    )


def test_profile_private_encrypted_and_csrf_protected(app):
    a, b = TestClient(app), TestClient(app)
    csrf = signup(a)
    signup(b, "other@example.com")
    profile = {"display_name": "Private Person", "conditions": ["Private condition"]}
    assert a.put("/v1/auth/profile", json=profile).status_code == 403
    assert a.put("/v1/auth/profile", headers=h(csrf), json=profile).status_code == 200
    assert (
        a.get("/v1/auth/profile").json()["profile"]["display_name"] == "Private Person"
    )
    assert b.get("/v1/auth/profile").json()["profile"]["display_name"] == ""
    with app.state.accounts.db() as db:
        raw = db.execute(
            "SELECT profile FROM users WHERE email=?", ("patient@example.com",)
        ).fetchone()["profile"]
        assert "Private Person" not in raw and "Private condition" not in raw
    assert a.post("/v1/jobs/missing/review", headers=h(csrf)).status_code == 403
    assert a.post("/v1/jobs/missing/process", headers=h(csrf)).status_code == 403


def test_production_requires_config_and_secure_cookie(app, monkeypatch, tmp_path):
    from cryptography.fernet import Fernet

    monkeypatch.setenv("MEDGUARD_ENVIRONMENT", "production")
    monkeypatch.delenv("MEDGUARD_AUTH_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("MEDGUARD_PUBLIC_ORIGIN", raising=False)
    with pytest.raises(RuntimeError):
        AccountStore(tmp_path / "production.sqlite3")
    monkeypatch.setenv("MEDGUARD_AUTH_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("MEDGUARD_PUBLIC_ORIGIN", "https://medguard.example")
    monkeypatch.setenv("MEDGUARD_REQUIRE_VERIFIED_EMAIL", "false")
    production = create_app()
    c = TestClient(production, base_url="https://medguard.example")
    assert c.get("/", headers={"host": "attacker.invalid"}).status_code == 400
    csrf = signup(c)
    response = c.post(
        "/v1/auth/login", json={"email": "patient@example.com", "password": PASSWORD},
        headers={"Origin": "https://medguard.example"},
    )
    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"]
    # Development addresses and forged forwarding headers cannot override the
    # explicit production public origin, even with otherwise valid credentials.
    assert c.post(
        "/v1/auth/login",
        json={"email": "patient@example.com", "password": PASSWORD},
        headers={"Origin": "http://localhost:5173", "X-Forwarded-Host": "localhost:5173"},
    ).status_code == 403
    assert c.get("/metrics").status_code == 403
    assert (
        TestClient(production, base_url="https://medguard.example")
        .get("/metrics")
        .status_code
        == 401
    )


def test_email_token_is_url_fragment(monkeypatch):
    from app.api.accounts import send_email

    messages = []

    class SMTP:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def starttls(self, **k):
            assert k["context"].verify_mode == 2

        def login(self, *a):
            pass

        def send_message(self, message):
            messages.append(message)

    monkeypatch.setattr("app.api.accounts.smtplib.SMTP", SMTP)
    monkeypatch.setenv("MEDGUARD_SMTP_HOST", "stub.example")
    monkeypatch.setenv("MEDGUARD_PUBLIC_ORIGIN", "https://medguard.example")
    send_email("patient@example.com", "a-private-token", "reset")
    assert "/#reset_token=a-private-token" in messages[0].get_content()
    assert "/?reset_token=" not in messages[0].get_content()


@pytest.mark.parametrize("origin", ["https://attacker.invalid", "http://localhost:9999", "null"])
def test_login_does_not_trust_client_forwarded_origin(app, origin):
    c = TestClient(app, base_url="http://localhost:5173")
    response = c.post(
        "/v1/auth/login",
        json={"email": "synthetic@example.com", "password": PASSWORD},
        headers={
            "Origin": origin,
            "X-Forwarded-Host": origin.removeprefix("https://").removeprefix("http://"),
            "X-Forwarded-Proto": "https",
            "Forwarded": 'host="attacker.invalid";proto=https',
        },
    )
    assert response.status_code == 403
    assert "cross_origin_request" in response.text
