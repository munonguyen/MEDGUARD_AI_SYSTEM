"""Server-side account/session store. Secrets and opaque tokens never enter logs."""

from __future__ import annotations
import base64, hashlib, hmac, os, secrets, sqlite3, struct, tempfile, time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from cryptography.fernet import Fernet
from fastapi import HTTPException, Request

HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = HASHER.hash(secrets.token_urlsafe(24))
COOKIE = "medguard_session"
ABSOLUTE_TTL = 8 * 3600
IDLE_TTL = 30 * 60


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def reject(code, status=401):
    raise HTTPException(status, detail={"error_code": code, "message": code})


def check_password(value):
    if len(value) < 12 or len(value.encode()) > 256:
        reject("password_requires_12_to_256_bytes", 422)


def verify_password(encoded, raw):
    try:
        return HASHER.verify(encoded, raw)
    except (VerificationError, InvalidHashError):
        return False


def check_origin(request):
    origin = request.headers.get("origin")
    expected = os.getenv("MEDGUARD_PUBLIC_ORIGIN") or str(request.base_url).rstrip("/")
    if origin and not hmac.compare_digest(origin.rstrip("/"), expected.rstrip("/")):
        reject("cross_origin_request", 403)
    if request.headers.get("sec-fetch-site") == "cross-site":
        reject("cross_origin_request", 403)


class AccountStore:
    def __init__(self, path=None):
        self.path = str(
            path or os.getenv("MEDGUARD_AUTH_DATABASE", ".runtime/accounts.sqlite3")
        )
        if os.getenv("MEDGUARD_ENVIRONMENT") == "production":
            from urllib.parse import urlsplit

            origin = urlsplit(os.getenv("MEDGUARD_PUBLIC_ORIGIN", ""))
            if (
                origin.scheme != "https"
                or not origin.hostname
                or not os.getenv("MEDGUARD_AUTH_ENCRYPTION_KEY")
                or not os.getenv("MEDGUARD_AUTH_DATABASE")
            ):
                raise RuntimeError(
                    "Production authentication requires HTTPS public origin, an encryption key and a persistent account database path"
                )
            Fernet(os.environ["MEDGUARD_AUTH_ENCRYPTION_KEY"].encode())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT, 0o600)
        os.close(fd)
        os.chmod(self.path, 0o600)
        with self.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'patient', verified INTEGER NOT NULL DEFAULT 0,consent INTEGER NOT NULL DEFAULT 0,mfa TEXT,last_totp INTEGER NOT NULL DEFAULT -1,created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),csrf TEXT NOT NULL,created REAL NOT NULL,last_seen REAL NOT NULL,expires REAL NOT NULL,agent TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS session_user ON sessions(user_id);
            CREATE TABLE IF NOT EXISTS tokens(token TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),purpose TEXT NOT NULL,expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS throttle(key TEXT PRIMARY KEY,attempts INTEGER NOT NULL,window REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS account_events(id INTEGER PRIMARY KEY, user_id TEXT,event TEXT NOT NULL,created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS recovery_codes(user_id TEXT NOT NULL REFERENCES users(id),code TEXT NOT NULL,PRIMARY KEY(user_id,code));
            """)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(sessions)")}
            if "csrf_secret" not in columns:
                db.execute("ALTER TABLE sessions ADD COLUMN csrf_secret TEXT")
        with self.db() as db:
            if "profile" not in {
                row["name"] for row in db.execute("PRAGMA table_info(users)")
            }:
                db.execute("ALTER TABLE users ADD COLUMN profile TEXT")
        os.chmod(self.path, 0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def event(self, db, user, event):
        db.execute(
            "INSERT INTO account_events(user_id,event,created) VALUES(?,?,?)",
            (user, event, time.time()),
        )

    def throttle(self, key, limit=10):
        now = time.time()
        with self.db() as db:
            db.execute("DELETE FROM throttle WHERE window<?", (now - 3600,))
            row = db.execute(
                "SELECT * FROM throttle WHERE key=?", (digest(key),)
            ).fetchone()
            count = row["attempts"] + 1 if row and row["window"] > now - 60 else 1
            db.execute(
                "INSERT OR REPLACE INTO throttle VALUES(?,?,?)",
                (
                    digest(key),
                    count,
                    row["window"] if row and row["window"] > now - 60 else now,
                ),
            )
        if count > limit:
            reject("authentication_rate_limited", 429)

    def create(self, email, password, consent):
        check_password(password)
        if not consent:
            reject("consent_required", 422)
        user = uuid4().hex
        encoded = HASHER.hash(password)
        try:
            with self.db() as db:
                db.execute(
                    "INSERT INTO users(id,email,password,consent,created) VALUES(?,?,?,?,?)",
                    (user, email, encoded, 1, time.time()),
                )
                self.event(db, user, "registered")
        except sqlite3.IntegrityError:
            reject("account_not_created", 409)
        return user

    def key(self):
        configured = os.getenv("MEDGUARD_AUTH_ENCRYPTION_KEY")
        if configured:
            return Fernet(configured.encode())
        if os.getenv("MEDGUARD_ENVIRONMENT") == "production":
            reject("mfa_encryption_not_configured", 503)
        path = Path(self.path).with_suffix(".key")
        # Publish only a fully written key, including with concurrent workers.
        if not path.exists():
            fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".auth-key-")
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(Fernet.generate_key())
                    f.flush()
                    os.fsync(f.fileno())
                try:
                    os.link(temporary, path)
                except FileExistsError:
                    pass
            finally:
                os.unlink(temporary)
        return Fernet(path.read_bytes())

    def totp(self, secret, step):
        key = base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8))
        raw = hmac.new(key, struct.pack(">Q", step), "sha1").digest()
        offset = raw[-1] & 15
        return str(
            (struct.unpack(">I", raw[offset : offset + 4])[0] & 0x7FFFFFFF) % 1000000
        ).zfill(6)

    def verify_totp(self, secret, code, last=-1):
        step = int(time.time() // 30)
        for n in (step - 1, step, step + 1):
            if n > last and hmac.compare_digest(self.totp(secret, n), str(code or "")):
                return n
        reject("invalid_credentials")

    def verify_mfa(self, db, user, code):
        """Consume one MFA proof atomically for login or sensitive reauthentication."""
        backup = db.execute(
            "DELETE FROM recovery_codes WHERE user_id=? AND code=?",
            (user["id"], digest(str(code or ""))),
        )
        if backup.rowcount == 1:
            self.event(db, user["id"], "mfa_recovery_used")
            return
        secret = self.key().decrypt(user["mfa"].encode()).decode()
        step = self.verify_totp(secret, code, user["last_totp"])
        db.execute("UPDATE users SET last_totp=? WHERE id=?", (step, user["id"]))

    def login(self, email, password, otp, agent):
        with self.db() as db:
            row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        valid = verify_password(row["password"] if row else DUMMY_HASH, password)
        if not row or not valid:
            reject("invalid_credentials")
        with self.db() as db:
            row = db.execute("SELECT * FROM users WHERE id=?", (row["id"],)).fetchone()
            # Recheck against races with password reset/change.
            if not verify_password(row["password"], password):
                reject("invalid_credentials")
            if row["mfa"]:
                self.verify_mfa(db, row, otp)
            if (
                os.getenv(
                    "MEDGUARD_REQUIRE_VERIFIED_EMAIL",
                    (
                        "true"
                        if os.getenv("MEDGUARD_ENVIRONMENT") == "production"
                        else "false"
                    ),
                ).lower()
                == "true"
                and not row["verified"]
            ):
                reject("email_verification_required", 403)
            token = secrets.token_urlsafe(32)
            csrf = secrets.token_urlsafe(32)
            now = time.time()
            db.execute(
                "DELETE FROM sessions WHERE expires<? OR last_seen<?",
                (now, now - IDLE_TTL),
            )
            encrypted_csrf = self.key().encrypt(csrf.encode()).decode()
            db.execute(
                "INSERT INTO sessions(token,user_id,csrf,created,last_seen,expires,agent,csrf_secret) VALUES(?,?,?,?,?,?,?,?)",
                (
                    digest(token),
                    row["id"],
                    digest(csrf),
                    now,
                    now,
                    now + ABSOLUTE_TTL,
                    agent[:200],
                    encrypted_csrf,
                ),
            )
            self.event(db, row["id"], "login")
        return token, csrf

    def authenticate(self, request, csrf=True):
        token = request.cookies.get(COOKIE)
        if not token:
            reject("login_required")
        now = time.time()
        with self.db() as db:
            row = db.execute(
                "SELECT s.*,u.email,u.role,u.verified,u.consent,u.mfa FROM sessions s JOIN users u ON u.id=s.user_id WHERE token=?",
                (digest(token),),
            ).fetchone()
            if not row or row["expires"] <= now or row["last_seen"] <= now - IDLE_TTL:
                reject("session_expired")
            if csrf and request.method not in {"GET", "HEAD", "OPTIONS"}:
                check_origin(request)
                if not hmac.compare_digest(
                    digest(request.headers.get("X-CSRF-Token", "")), row["csrf"]
                ):
                    reject("csrf_invalid", 403)
            db.execute(
                "UPDATE sessions SET last_seen=? WHERE token=?", (now, digest(token))
            )
        return dict(row)

    def token(self, user, purpose):
        raw = secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute(
                "DELETE FROM tokens WHERE expires<? OR (user_id=? AND purpose=?)",
                (time.time(), user, purpose),
            )
            db.execute(
                "INSERT INTO tokens VALUES(?,?,?,?)",
                (digest(raw), user, purpose, time.time() + 1800),
            )
        return raw

    def consume(self, raw, purpose, password=None):
        if password is not None:
            check_password(password)
            encoded = HASHER.hash(password)
        with self.db() as db:
            row = db.execute(
                "SELECT * FROM tokens WHERE token=? AND purpose=? AND expires>?",
                (digest(raw), purpose, time.time()),
            ).fetchone()
            if not row:
                reject("invalid_or_expired_token", 400)
            user = row["user_id"]
            db.execute(
                "DELETE FROM tokens WHERE user_id=? AND purpose=?", (user, purpose)
            )
            if purpose == "reset":
                db.execute("UPDATE users SET password=? WHERE id=?", (encoded, user))
                db.execute("DELETE FROM sessions WHERE user_id=?", (user,))
                db.execute("DELETE FROM tokens WHERE user_id=?", (user,))
                self.event(db, user, "password_reset")
            else:
                db.execute("UPDATE users SET verified=1 WHERE id=?", (user,))
                self.event(db, user, "email_verified")
