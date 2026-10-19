from __future__ import annotations
import base64, os, re, secrets, smtplib, ssl, time
from email.message import EmailMessage
from urllib.parse import quote
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.core.accounts import (
    COOKIE,
    ABSOLUTE_TTL,
    check_origin,
    check_password,
    digest,
    reject,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Accounts"])


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)
    otp: str | None = Field(default=None, max_length=32)

    @field_validator("email")
    @classmethod
    def email_valid(cls, v):
        v = v.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", v):
            raise ValueError("Invalid email")
        return v


class Registration(Credentials):
    consent: bool = False


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(max_length=256)
    new_password: str = Field(max_length=256)
    otp: str | None = Field(default=None, max_length=32)


class Reauthentication(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(max_length=256)
    otp: str | None = Field(default=None, max_length=32)


class EmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=254)
    _normalize_email = field_validator("email")(Credentials.email_valid.__func__)


class TokenInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=128)


class ResetInput(TokenInput):
    password: str = Field(max_length=256)


def public(row):
    return {
        "id": row["user_id"],
        "email": row["email"],
        "role": row["role"],
        "email_verified": bool(row["verified"]),
        "mfa_enabled": bool(row["mfa"]),
        "scope": "user-" + row["user_id"],
    }


def store(r):
    return r.app.state.accounts


def send_email(email, token, purpose):
    host = os.getenv("MEDGUARD_SMTP_HOST")
    origin = os.getenv("MEDGUARD_PUBLIC_ORIGIN")
    if not host or not origin:
        reject("email_delivery_not_configured", 503)
    msg = EmailMessage()
    msg["From"] = os.getenv("MEDGUARD_SMTP_FROM", "")
    msg["To"] = email
    msg["Subject"] = "MedGuard: " + (
        "Đặt lại mật khẩu" if purpose == "reset" else "Xác thực email"
    )
    msg.set_content(
        f"Mở liên kết để tiếp tục (hết hạn sau 30 phút):\n{origin}/#{purpose}_token={quote(token)}\nNếu không phải bạn yêu cầu, hãy bỏ qua email này."
    )
    try:
        with smtplib.SMTP(
            host, int(os.getenv("MEDGUARD_SMTP_PORT", "587")), timeout=10
        ) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(
                os.getenv("MEDGUARD_SMTP_USER", ""),
                os.getenv("MEDGUARD_SMTP_PASSWORD", ""),
            )
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError, ValueError):
        reject("email_delivery_failed", 503)


def throttled(r, purpose):
    check_origin(r)
    store(r).throttle(purpose + ":" + (r.client.host if r.client else "unknown"))


@router.post("/register", status_code=201)
def register(data: Registration, request: Request):
    throttled(request, "register")
    user = store(request).create(data.email, data.password, data.consent)
    if os.getenv("MEDGUARD_SMTP_HOST") and os.getenv("MEDGUARD_PUBLIC_ORIGIN"):
        send_email(data.email, store(request).token(user, "verify"), "verify")
    return {"message": "Tài khoản đã tạo. Bạn có thể đăng nhập."}


@router.post("/login")
def login(data: Credentials, request: Request, response: Response):
    throttled(request, "login")
    store(request).throttle("account:" + data.email)
    token, csrf = store(request).login(
        data.email, data.password, data.otp, request.headers.get("user-agent", "")
    )
    response.set_cookie(
        COOKIE,
        token,
        max_age=ABSOLUTE_TTL,
        httponly=True,
        secure=os.getenv("MEDGUARD_ENVIRONMENT") == "production",
        samesite="strict",
        path="/",
    )
    return {
        "csrf_token": csrf,
        "user": public(
            store(request).authenticate(_cookie_request(request, token), csrf=False)
        ),
    }


def _cookie_request(request, token):
    # Login response metadata only; do not mutate the original request/cookies.
    scope = dict(request.scope)
    scope["headers"] = [
        (k, v) for k, v in scope["headers"] if k.lower() != b"cookie"
    ] + [(b"cookie", f"{COOKIE}={token}".encode())]
    return Request(scope)


@router.get("/me")
def me(request: Request):
    return {"user": public(store(request).authenticate(request))}


@router.get("/csrf")
def csrf(request: Request):
    row = store(request).authenticate(request)
    if row.get("csrf_secret"):
        token = store(request).key().decrypt(row["csrf_secret"].encode()).decode()
    else:
        token = secrets.token_urlsafe(32)
        encrypted = store(request).key().encrypt(token.encode()).decode()
        with store(request).db() as db:
            db.execute(
                "UPDATE sessions SET csrf=?,csrf_secret=? WHERE token=?",
                (digest(token), encrypted, row["token"]),
            )
    return {"csrf_token": token}


@router.post("/logout")
def logout(request: Request, response: Response):
    row = store(request).authenticate(request)
    with store(request).db() as db:
        db.execute("DELETE FROM sessions WHERE token=?", (row["token"],))
        store(request).event(db, row["user_id"], "logout")
    response.delete_cookie(COOKIE, path="/")
    return {"message": "Đã đăng xuất"}


@router.post("/logout-all")
def logout_all(request: Request, response: Response):
    row = store(request).authenticate(request)
    with store(request).db() as db:
        db.execute("DELETE FROM sessions WHERE user_id=?", (row["user_id"],))
        store(request).event(db, row["user_id"], "sessions_revoked")
    response.delete_cookie(COOKIE, path="/")
    return {"message": "Đã thu hồi toàn bộ phiên"}


@router.get("/sessions")
def sessions(request: Request):
    row = store(request).authenticate(request)
    with store(request).db() as db:
        rows = db.execute(
            "SELECT token,created,last_seen,agent FROM sessions WHERE user_id=? AND expires>? AND last_seen>?",
            (row["user_id"], time.time(), time.time() - 1800),
        ).fetchall()
    return {
        "sessions": [
            {
                "id": r["token"],
                "created": r["created"],
                "last_seen": r["last_seen"],
                "agent": r["agent"],
                "current": r["token"] == row["token"],
            }
            for r in rows
        ]
    }


@router.delete("/sessions/{session_id}")
def revoke(session_id: str, request: Request):
    row = store(request).authenticate(request)
    with store(request).db() as db:
        db.execute(
            "DELETE FROM sessions WHERE token=? AND user_id=?",
            (session_id, row["user_id"]),
        )
    return {"message": "Đã thu hồi phiên"}


@router.post("/password")
def change_password(data: PasswordChange, request: Request, response: Response):
    row = store(request).authenticate(request)
    check_password(data.new_password)
    store(request).throttle("reauth:" + row["user_id"])
    from app.core.accounts import HASHER

    encoded = HASHER.hash(data.new_password)
    with store(request).db() as db:
        u = db.execute("SELECT * FROM users WHERE id=?", (row["user_id"],)).fetchone()
        if not verify_password(u["password"], data.current_password):
            reject("invalid_credentials")
        if u["mfa"]:
            store(request).verify_mfa(db, u, data.otp)
        db.execute("UPDATE users SET password=? WHERE id=?", (encoded, u["id"]))
        db.execute("DELETE FROM sessions WHERE user_id=?", (u["id"],))
        store(request).event(db, u["id"], "password_changed")
        db.execute("DELETE FROM tokens WHERE user_id=?", (u["id"],))
    response.delete_cookie(COOKIE, path="/")
    return {"message": "Mật khẩu đã đổi. Hãy đăng nhập lại."}


@router.post("/forgot-password")
def forgot(data: EmailInput, request: Request):
    throttled(request, "recovery")
    if not os.getenv("MEDGUARD_SMTP_HOST") or not os.getenv("MEDGUARD_PUBLIC_ORIGIN"):
        reject("email_delivery_not_configured", 503)
    with store(request).db() as db:
        row = db.execute(
            "SELECT id FROM users WHERE email=?", (data.email.strip().lower(),)
        ).fetchone()
    if row:
        send_email(data.email, store(request).token(row["id"], "reset"), "reset")
    return {"message": "Nếu tài khoản tồn tại, hướng dẫn sẽ được gửi qua email."}


@router.post("/reset-password")
def reset(data: ResetInput, request: Request):
    throttled(request, "reset")
    store(request).consume(data.token, "reset", data.password)
    return {"message": "Đã đặt lại mật khẩu. Hãy đăng nhập lại."}


@router.post("/verification-email")
def verification_email(request: Request, data: EmailInput | None = None):
    throttled(request, "verification")
    if not os.getenv("MEDGUARD_SMTP_HOST") or not os.getenv("MEDGUARD_PUBLIC_ORIGIN"):
        reject("email_delivery_not_configured", 503)
    if request.cookies.get(COOKIE):
        row = store(request).authenticate(request)
        user, email = row["user_id"], row["email"]
    else:
        if data is None:
            reject("email_required", 400)
        email = data.email.strip().lower()
        with store(request).db() as db:
            row = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        user = row["id"] if row else None
    if user:
        send_email(email, store(request).token(user, "verify"), "verify")
    return {"message": "Nếu tài khoản tồn tại, email xác thực sẽ được gửi."}


@router.post("/verify-email")
def verify_email(data: TokenInput, request: Request):
    throttled(request, "verify")
    store(request).consume(data.token, "verify")
    return {"message": "Đã xác thực email"}


@router.post("/mfa/setup")
def mfa_setup(data: Reauthentication, request: Request):
    row = store(request).authenticate(request)
    store(request).throttle("reauth:" + row["user_id"])
    with store(request).db() as db:
        u = db.execute("SELECT * FROM users WHERE id=?", (row["user_id"],)).fetchone()
    if not verify_password(u["password"], data.current_password) or u["mfa"]:
        reject("invalid_credentials")
    secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
    encrypted = store(request).key().encrypt(secret.encode()).decode()
    raw = store(request).token(row["user_id"], "mfa:" + encrypted)
    return {
        "setup_token": raw,
        "secret": secret,
        "uri": f'otpauth://totp/MedGuard:{quote(row["email"])}?secret={secret}&issuer=MedGuard&algorithm=SHA1&digits=6&period=30',
    }


class MFAConfirm(TokenInput):
    code: str = Field(pattern=r"^\d{6}$")


@router.post("/mfa/enable")
def enable_mfa(data: MFAConfirm, request: Request):
    row = store(request).authenticate(request)
    store(request).throttle("reauth:" + row["user_id"])
    backups = [secrets.token_hex(10) for _ in range(10)]
    with store(request).db() as db:
        t = db.execute(
            "SELECT * FROM tokens WHERE token=? AND user_id=? AND expires>?",
            (digest(data.token), row["user_id"], time.time()),
        ).fetchone()
        if not t or not t["purpose"].startswith("mfa:"):
            reject("invalid_or_expired_token", 400)
        if not db.execute(
            "SELECT 1 FROM sessions WHERE token=?", (row["token"],)
        ).fetchone():
            reject("session_expired")
        encrypted = t["purpose"][4:]
        n = store(request).verify_totp(
            store(request).key().decrypt(encrypted.encode()).decode(), data.code
        )
        db.execute(
            "UPDATE users SET mfa=?,last_totp=? WHERE id=?",
            (encrypted, n, row["user_id"]),
        )
        db.execute(
            "DELETE FROM tokens WHERE user_id=? AND purpose LIKE ?",
            (row["user_id"], "mfa:%"),
        )
        db.execute("DELETE FROM sessions WHERE user_id=?", (row["user_id"],))
        store(request).event(db, row["user_id"], "mfa_enabled")
        db.execute("DELETE FROM recovery_codes WHERE user_id=?", (row["user_id"],))
        db.executemany(
            "INSERT INTO recovery_codes VALUES(?,?)",
            [(row["user_id"], digest(code)) for code in backups],
        )
    return {
        "message": "MFA đã bật. Lưu các mã khôi phục riêng tư; mỗi mã chỉ dùng một lần.",
        "recovery_codes": backups,
    }


@router.post("/mfa/disable")
def disable_mfa(data: Reauthentication, request: Request):
    row = store(request).authenticate(request)
    store(request).throttle("reauth:" + row["user_id"])
    with store(request).db() as db:
        u = db.execute("SELECT * FROM users WHERE id=?", (row["user_id"],)).fetchone()
        if not u["mfa"] or not verify_password(u["password"], data.current_password):
            reject("invalid_credentials")
        store(request).verify_mfa(db, u, data.otp)
        db.execute("UPDATE users SET mfa=NULL,last_totp=-1 WHERE id=?", (u["id"],))
        db.execute("DELETE FROM sessions WHERE user_id=?", (u["id"],))
        store(request).event(db, u["id"], "mfa_disabled")
        db.execute("DELETE FROM recovery_codes WHERE user_id=?", (u["id"],))
    return {"message": "MFA đã tắt. Hãy đăng nhập lại."}


class AccountProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(default="", max_length=100)
    patient_ref: str = Field(default="", max_length=100)
    age: int | None = Field(default=None, ge=0, le=130)
    sex: str | None = Field(default=None, pattern=r"^(male|female|other)$")
    current_medications: list[str] = Field(default_factory=list, max_length=100)
    allergies: list[str] = Field(default_factory=list, max_length=100)
    conditions: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("current_medications", "allergies", "conditions")
    @classmethod
    def bounded_items(cls, items):
        if any(len(item) > 200 for item in items):
            raise ValueError("Profile entries are too long")
        return items


@router.get("/profile")
def get_profile(request: Request):
    import json

    row = store(request).authenticate(request)
    with store(request).db() as db:
        profile = db.execute(
            "SELECT profile FROM users WHERE id=?", (row["user_id"],)
        ).fetchone()["profile"]
    return {
        "profile": (
            json.loads(store(request).key().decrypt(profile.encode()))
            if profile
            else AccountProfile().model_dump()
        )
    }


@router.put("/profile")
def put_profile(data: AccountProfile, request: Request):
    row = store(request).authenticate(request)
    encrypted = store(request).key().encrypt(data.model_dump_json().encode()).decode()
    with store(request).db() as db:
        db.execute("UPDATE users SET profile=? WHERE id=?", (encrypted, row["user_id"]))
    return {"message": "Đã lưu Profile"}
