from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from queue import Empty, Queue
import secrets
import ssl
from threading import RLock
import time
from typing import Any
from uuid import uuid4

import bcrypt
import pymysql

IDLE_TTL = 30 * 60
ABSOLUTE_TTL = 8 * 3600
SESSION_CACHE_TTL = 120  # Fast in-memory cache TTL in seconds
CLEANUP_INTERVAL = 600   # Expired session cleanup interval (10 min)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class TiDBConnectionPool:
    """Thread-safe connection pool with keep-alive ping for low-latency DB queries."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        max_size: int = 8,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.max_size = max_size
        self._pool: Queue[pymysql.Connection] = Queue(maxsize=max_size)
        self._ctx = ssl.create_default_context()
        self._ctx.check_hostname = False
        self._ctx.verify_mode = ssl.CERT_NONE

    def _create_connection(self) -> pymysql.Connection:
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            ssl=self._ctx,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
            read_timeout=10,
            write_timeout=10,
            autocommit=True,
        )

    @contextmanager
    def connection(self):
        conn: pymysql.Connection | None = None
        try:
            conn = self._pool.get_nowait()
            try:
                conn.ping()
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
                conn = self._create_connection()
        except Empty:
            conn = self._create_connection()

        try:
            yield conn
            try:
                self._pool.put_nowait(conn)
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            raise


class TiDBAccountBackend:
    """Low-latency persistent authentication backend using TiDB Cloud (MySQL compatible)
    with pooled connections and fast in-memory session acceleration.
    """

    def __init__(self) -> None:
        self.host = os.getenv("DB_HOST", "gateway01.ap-southeast-1.prod.aws.tidbcloud.com")
        self.port = int(os.getenv("DB_PORT", "4000"))
        self.user = os.getenv("DB_USERNAME", "2XDuhkZH7XUtxj1.root")
        self.password = os.getenv("DB_PASSWORD", "61Lz96QJ1KsCaMHR")
        self.database = os.getenv("DB_DATABASE", "bookingcare")
        self._pool = TiDBConnectionPool(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            max_size=8,
        )
        self._lock = RLock()
        self._session_cache: dict[str, dict[str, Any]] = {}
        self._user_cache: dict[str, dict[str, Any]] = {}
        self._email_cache: dict[str, dict[str, Any]] = {}
        self._last_cleanup = time.time()
        self._init_tables()

    @contextmanager
    def _get_connection(self):
        with self._pool.connection() as conn:
            yield conn

    def _init_tables(self) -> None:
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS medguard_sessions (
                            token VARCHAR(64) PRIMARY KEY,
                            user_id VARCHAR(64) NOT NULL,
                            csrf VARCHAR(64) NOT NULL,
                            csrf_secret VARCHAR(255),
                            created DOUBLE NOT NULL,
                            last_seen DOUBLE NOT NULL,
                            expires DOUBLE NOT NULL,
                            agent VARCHAR(255) NOT NULL,
                            INDEX idx_user (user_id)
                        );
                        """
                    )
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS medguard_users (
                            id VARCHAR(64) PRIMARY KEY,
                            email VARCHAR(255) UNIQUE NOT NULL,
                            password VARCHAR(255) NOT NULL,
                            role VARCHAR(32) NOT NULL DEFAULT 'patient',
                            verified INT NOT NULL DEFAULT 1,
                            consent INT NOT NULL DEFAULT 1,
                            created DOUBLE NOT NULL
                        );
                        """
                    )
        except Exception as exc:
            print(f"[TiDB] Init tables warning: {exc}")

    def verify_password(self, encoded_hash: str | None, raw_password: str) -> bool:
        if not encoded_hash or not raw_password:
            return False
        # 1. Check bcrypt ($2a$, $2b$, $2y$)
        if encoded_hash.startswith(("$2a$", "$2b$", "$2y$")):
            try:
                return bcrypt.checkpw(
                    raw_password.encode("utf-8"), encoded_hash.encode("utf-8")
                )
            except Exception:
                return False
        # 2. Check Argon2id
        try:
            from argon2 import PasswordHasher
            hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
            return hasher.verify(encoded_hash, raw_password)
        except Exception:
            pass
        return False

    def find_user_by_email(self, email: str) -> dict[str, Any] | None:
        email = email.strip().lower()
        now = time.time()
        with self._lock:
            cached = self._email_cache.get(email)
            if cached and (now - cached.get("_cached_at", 0) < 60):
                return {k: v for k, v in cached.items() if not k.startswith("_")}

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # 1. Check MedGuard users table first (fast path for MedGuard users)
                    cur.execute(
                        "SELECT id, email, password, role, verified, consent FROM medguard_users WHERE LOWER(email) = %s LIMIT 1",
                        (email,),
                    )
                    mg_row = cur.fetchone()
                    if mg_row:
                        res = {
                            "id": mg_row["id"],
                            "email": mg_row["email"],
                            "password": mg_row["password"],
                            "role": mg_row.get("role", "patient"),
                            "verified": mg_row.get("verified", 1),
                            "consent": mg_row.get("consent", 1),
                            "mfa": None,
                            "source": "medguard_users",
                        }
                        with self._lock:
                            self._email_cache[email] = {**res, "_cached_at": now}
                            self._user_cache[res["id"]] = {**res, "_cached_at": now}
                        return res

                    # 2. Check BookingCare Users table
                    cur.execute(
                        "SELECT id, email, password, roleId, status FROM Users WHERE LOWER(email) = %s LIMIT 1",
                        (email,),
                    )
                    row = cur.fetchone()
                    if row:
                        role_id = row.get("roleId", "R3")
                        role = "admin" if role_id == "R1" else ("doctor" if role_id == "R2" else "patient")
                        res = {
                            "id": f"bc_{row['id']}",
                            "email": row["email"],
                            "password": row["password"],
                            "role": role,
                            "verified": 1,
                            "consent": 1,
                            "mfa": None,
                            "source": "bookingcare_users",
                        }
                        with self._lock:
                            self._email_cache[email] = {**res, "_cached_at": now}
                            self._user_cache[res["id"]] = {**res, "_cached_at": now}
                        return res
        except Exception as exc:
            print(f"[TiDB] find_user_by_email error: {exc}")
        return None

    def find_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        now = time.time()
        with self._lock:
            cached = self._user_cache.get(user_id)
            if cached and (now - cached.get("_cached_at", 0) < SESSION_CACHE_TTL):
                return {k: v for k, v in cached.items() if not k.startswith("_")}

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    if user_id.startswith("bc_"):
                        bc_id = int(user_id[3:])
                        cur.execute(
                            "SELECT id, email, roleId, status FROM Users WHERE id = %s LIMIT 1",
                            (bc_id,),
                        )
                        row = cur.fetchone()
                        if row:
                            role_id = row.get("roleId", "R3")
                            role = "admin" if role_id == "R1" else ("doctor" if role_id == "R2" else "patient")
                            res = {
                                "id": user_id,
                                "email": row["email"],
                                "role": role,
                                "verified": 1,
                                "consent": 1,
                                "mfa": None,
                            }
                            with self._lock:
                                self._user_cache[user_id] = {**res, "_cached_at": now}
                            return res
                    else:
                        cur.execute(
                            "SELECT id, email, role, verified, consent FROM medguard_users WHERE id = %s LIMIT 1",
                            (user_id,),
                        )
                        row = cur.fetchone()
                        if row:
                            res = {
                                "id": row["id"],
                                "email": row["email"],
                                "role": row.get("role", "patient"),
                                "verified": row.get("verified", 1),
                                "consent": row.get("consent", 1),
                                "mfa": None,
                            }
                            with self._lock:
                                self._user_cache[user_id] = {**res, "_cached_at": now}
                            return res
        except Exception as exc:
            print(f"[TiDB] find_user_by_id error: {exc}")
        return None

    def create_user(self, email: str, raw_password: str, consent: bool) -> str:
        email = email.strip().lower()
        salt = bcrypt.gensalt(rounds=10)
        hashed = bcrypt.hashpw(raw_password.encode("utf-8"), salt).decode("utf-8")
        user_id = uuid4().hex
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO medguard_users (id, email, password, role, verified, consent, created)
                    VALUES (%s, %s, %s, 'patient', 1, %s, %s)
                    ON DUPLICATE KEY UPDATE password = VALUES(password)
                    """,
                    (user_id, email, hashed, 1 if consent else 0, time.time()),
                )
        with self._lock:
            self._email_cache.pop(email, None)
        return user_id

    def create_session(
        self,
        user_id: str,
        agent: str,
        csrf_secret: str | None = None,
        token: str | None = None,
        csrf: str | None = None,
        user_data: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        token = token or secrets.token_urlsafe(32)
        csrf = csrf or secrets.token_urlsafe(32)
        csrf_secret_val = csrf_secret if csrf_secret is not None else csrf
        now = time.time()
        token_digest = digest(token)
        csrf_digest = digest(csrf)

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Periodic non-blocking cleanup of expired sessions (every 10 minutes)
                if now - self._last_cleanup > CLEANUP_INTERVAL:
                    self._last_cleanup = now
                    try:
                        cur.execute(
                            "DELETE FROM medguard_sessions WHERE expires < %s OR last_seen < %s",
                            (now, now - IDLE_TTL),
                        )
                    except Exception:
                        pass

                cur.execute(
                    """
                    INSERT INTO medguard_sessions (token, user_id, csrf, csrf_secret, created, last_seen, expires, agent)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        token_digest,
                        user_id,
                        csrf_digest,
                        csrf_secret_val,
                        now,
                        now,
                        now + ABSOLUTE_TTL,
                        agent[:200],
                    ),
                )

        # Store in fast memory cache immediately for instant next lookup
        sess_obj = {
            "token": token_digest,
            "user_id": user_id,
            "csrf": csrf_digest,
            "csrf_secret": csrf_secret_val,
            "created": now,
            "last_seen": now,
            "expires": now + ABSOLUTE_TTL,
            "agent": agent[:200],
        }
        with self._lock:
            u_info = user_data or self._user_cache.get(user_id)
            if u_info:
                clean_u = {k: v for k, v in u_info.items() if not k.startswith("_")}
                self._session_cache[token_digest] = {
                    "session": sess_obj,
                    "user": clean_u,
                    "_cached_at": now,
                }

        return token, csrf

    def get_session_and_user(self, token: str) -> dict[str, Any] | None:
        now = time.time()
        token_digest = digest(token)

        # 1. Fast in-memory cache check (sub-millisecond latency)
        with self._lock:
            cached = self._session_cache.get(token_digest)
            if cached:
                session = cached["session"]
                if session["expires"] > now and session["last_seen"] > now - IDLE_TTL:
                    session["last_seen"] = now
                    return {
                        "session": session,
                        "user": cached["user"],
                    }
                else:
                    self._session_cache.pop(token_digest, None)

        # 2. Database lookup with single query on pooled connection
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Single joined query to fetch session and medguard_user in 1 roundtrip
                    cur.execute(
                        """
                        SELECT s.token, s.user_id, s.csrf, s.csrf_secret, s.created, s.last_seen, s.expires, s.agent,
                               u.email as u_email, u.role as u_role, u.verified as u_verified, u.consent as u_consent
                        FROM medguard_sessions s
                        LEFT JOIN medguard_users u ON s.user_id = u.id
                        WHERE s.token = %s LIMIT 1
                        """,
                        (token_digest,),
                    )
                    row = cur.fetchone()
                    if not row:
                        return None
                    if row["expires"] <= now or row["last_seen"] <= now - IDLE_TTL:
                        cur.execute("DELETE FROM medguard_sessions WHERE token = %s", (token_digest,))
                        with self._lock:
                            self._session_cache.pop(token_digest, None)
                        return None

                    # Update last seen lazily (only if last_seen > 60s ago to save writes)
                    if now - float(row["last_seen"]) > 60:
                        cur.execute(
                            "UPDATE medguard_sessions SET last_seen = %s WHERE token = %s",
                            (now, token_digest),
                        )

                    session = {
                        "token": row["token"],
                        "user_id": row["user_id"],
                        "csrf": row["csrf"],
                        "csrf_secret": row["csrf_secret"],
                        "created": float(row["created"]),
                        "last_seen": now,
                        "expires": float(row["expires"]),
                        "agent": row["agent"],
                    }

                    if row.get("u_email"):
                        user = {
                            "id": row["user_id"],
                            "email": row["u_email"],
                            "role": row.get("u_role", "patient"),
                            "verified": row.get("u_verified", 1),
                            "consent": row.get("u_consent", 1),
                            "mfa": None,
                        }
                    else:
                        user = self.find_user_by_id(row["user_id"])
                        if not user:
                            return None

                    with self._lock:
                        self._session_cache[token_digest] = {
                            "session": session,
                            "user": user,
                            "_cached_at": now,
                        }

                    return {
                        "session": session,
                        "user": user,
                    }
        except Exception as exc:
            print(f"[TiDB] get_session error: {exc}")
        return None

    def delete_session(self, token: str) -> None:
        self.delete_session_by_digest(digest(token))

    def delete_session_by_digest(self, token_digest: str) -> None:
        with self._lock:
            self._session_cache.pop(token_digest, None)
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM medguard_sessions WHERE token = %s", (token_digest,))
        except Exception as exc:
            print(f"[TiDB] delete_session error: {exc}")

    def delete_sessions_by_user(self, user_id: str) -> None:
        with self._lock:
            tokens_to_evict = [
                tok for tok, item in self._session_cache.items()
                if item.get("session", {}).get("user_id") == user_id
            ]
            for tok in tokens_to_evict:
                self._session_cache.pop(tok, None)
            self._user_cache.pop(user_id, None)

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM medguard_sessions WHERE user_id = %s", (user_id,))
        except Exception as exc:
            print(f"[TiDB] delete_sessions_by_user error: {exc}")

    def update_csrf(self, token_digest: str, csrf_digest: str, csrf_secret: str) -> None:
        with self._lock:
            if token_digest in self._session_cache:
                self._session_cache[token_digest]["session"]["csrf"] = csrf_digest
                self._session_cache[token_digest]["session"]["csrf_secret"] = csrf_secret

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE medguard_sessions SET csrf = %s, csrf_secret = %s WHERE token = %s",
                        (csrf_digest, csrf_secret, token_digest),
                    )
        except Exception as exc:
            print(f"[TiDB] update_csrf error: {exc}")
