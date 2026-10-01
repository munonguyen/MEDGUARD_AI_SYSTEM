"""Tenant-scoped database adapters for local SQLite and production PostgreSQL."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Generator, Protocol

from app.core.config import settings


class DatabaseUnavailableError(RuntimeError):
    pass


class TenantSession(Protocol):
    dialect: str

    def execute(
        self, query: str, params: tuple[Any, ...] | dict[str, Any] = ()
    ) -> list[dict[str, Any]]: ...


class DatabaseEngine(Protocol):
    backend_name: str
    is_durable: bool
    is_postgres: bool

    @contextmanager
    def session(self, tenant_id: str) -> Generator[TenantSession, None, None]: ...

    def close(self) -> None: ...


_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    action TEXT NOT NULL,
    payload_type TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_tenant_req
    ON audit_events(tenant_id, request_id);
CREATE INDEX IF NOT EXISTS idx_audit_tenant_created
    ON audit_events(tenant_id, created_at);

CREATE TABLE IF NOT EXISTS prescription_jobs (
    job_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    patient_ref TEXT NOT NULL,
    image_sha256 TEXT NOT NULL,
    image_size_bytes INTEGER NOT NULL,
    content_type TEXT NOT NULL,
    catalog_ref TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    review_status TEXT NOT NULL DEFAULT 'PENDING_REVIEW',
    result TEXT,
    error_code TEXT,
    created_at REAL NOT NULL,
    completed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_prescription_jobs_lookup
    ON prescription_jobs(tenant_id, job_id);
CREATE INDEX IF NOT EXISTS idx_prescription_jobs_tenant_status
    ON prescription_jobs(tenant_id, status, created_at);

CREATE TABLE IF NOT EXISTS idempotency_records (
    record_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    response_code INTEGER NOT NULL,
    response_body TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    UNIQUE(tenant_id, endpoint, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_idempotency_expiry
    ON idempotency_records(expires_at);

CREATE TABLE IF NOT EXISTS chat_conversations (
    tenant_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    title TEXT NOT NULL,
    patient_ref TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, conversation_id)
);
CREATE INDEX IF NOT EXISTS idx_chat_conversations_updated
    ON chat_conversations(tenant_id, updated_at);

CREATE TABLE IF NOT EXISTS chat_messages (
    message_id TEXT PRIMARY KEY,
    request_id TEXT,
    tenant_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    intent TEXT,
    status TEXT,
    result_json TEXT,
    answer_json TEXT,
    answer_origin TEXT,
    verification_status TEXT,
    knowledge_approval TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id, conversation_id)
        REFERENCES chat_conversations(tenant_id, conversation_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation
    ON chat_messages(tenant_id, conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_tenant_created
    ON chat_messages(tenant_id, created_at);

CREATE TABLE IF NOT EXISTS medication_schedules (
    schedule_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    patient_ref TEXT NOT NULL,
    medication_name TEXT NOT NULL,
    dosage_text TEXT,
    scheduled_at TEXT NOT NULL,
    recurrence TEXT NOT NULL DEFAULT 'once',
    source TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_medication_schedules_patient
    ON medication_schedules(tenant_id, patient_ref, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_medication_schedules_patient_status
    ON medication_schedules(tenant_id, patient_ref, status);
"""


class SqliteTenantSession:
    dialect = "sqlite"

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def execute(
        self, query: str, params: tuple[Any, ...] | dict[str, Any] = ()
    ) -> list[dict[str, Any]]:
        cursor = self._connection.execute(query, params)
        if cursor.description is None:
            return []
        return [dict(row) for row in cursor.fetchall()]


class SqliteTenantEngine:
    is_postgres = False

    def __init__(self, path: str = ":memory:") -> None:
        self.path = path
        self.is_durable = path != ":memory:"
        self.backend_name = "sqlite-file" if self.is_durable else "sqlite-memory"
        if self.is_durable:
            resolved = Path(path).expanduser().resolve()
            resolved.parent.mkdir(parents=True, exist_ok=True)
            self.path = str(resolved)
        self._lock = RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA busy_timeout = 5000")
        self._connection.execute("PRAGMA cache_size = -64000")
        self._connection.execute("PRAGMA temp_store = MEMORY")
        if self.is_durable:
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = NORMAL")
            self._connection.execute("PRAGMA mmap_size = 268435456")
        self._connection.executescript(_SQLITE_SCHEMA)
        self._connection.executescript((Path(__file__).parent / "browser_schema.sql").read_text())
        idempotency_columns = {
            row[1]
            for row in self._connection.execute("PRAGMA table_info(idempotency_records)")
        }
        if "payload_hash" not in idempotency_columns:
            self._connection.execute(
                "ALTER TABLE idempotency_records "
                "ADD COLUMN payload_hash TEXT NOT NULL DEFAULT ''"
            )
        chat_message_columns = {
            row[1]
            for row in self._connection.execute("PRAGMA table_info(chat_messages)")
        }
        if "answer_json" not in chat_message_columns:
            self._connection.execute("ALTER TABLE chat_messages ADD COLUMN answer_json TEXT")
        for column_name in ("request_id", "answer_origin", "verification_status", "knowledge_approval"):
            if column_name not in chat_message_columns:
                self._connection.execute(
                    f"ALTER TABLE chat_messages ADD COLUMN {column_name} TEXT"
                )
        table_sql_row = self._connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'idempotency_records'"
        ).fetchone()
        normalized_table_sql = "".join(str(table_sql_row[0]).lower().split())
        if "unique(tenant_id,idempotency_key)" in normalized_table_sql:
            self._connection.executescript(
                """
                DROP INDEX IF EXISTS idx_idempotency_expiry;
                ALTER TABLE idempotency_records RENAME TO idempotency_records_legacy;
                CREATE TABLE idempotency_records (
                    record_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    response_code INTEGER NOT NULL,
                    response_body TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    UNIQUE(tenant_id, endpoint, idempotency_key)
                );
                INSERT INTO idempotency_records (
                    record_id, tenant_id, idempotency_key, endpoint, response_code,
                    response_body, payload_hash, created_at, expires_at
                )
                SELECT record_id, tenant_id, idempotency_key, endpoint, response_code,
                       response_body, payload_hash, created_at, expires_at
                FROM idempotency_records_legacy;
                DROP TABLE idempotency_records_legacy;
                CREATE INDEX idx_idempotency_expiry ON idempotency_records(expires_at);
                """
            )
        self._connection.commit()

    @contextmanager
    def session(self, tenant_id: str) -> Generator[SqliteTenantSession, None, None]:
        del tenant_id
        with self._lock:
            session = SqliteTenantSession(self._connection)
            try:
                yield session
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class PostgresTenantSession:
    dialect = "postgresql"

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def execute(
        self, query: str, params: tuple[Any, ...] | dict[str, Any] = ()
    ) -> list[dict[str, Any]]:
        postgres_query = query.replace("?", "%s") if not isinstance(params, dict) else query
        cursor = self._connection.execute(postgres_query, params)
        if cursor.description is None:
            return []
        return [dict(row) for row in cursor.fetchall()]


class PostgresTenantEngine:
    backend_name = "postgresql"
    is_durable = True
    is_postgres = True

    def __init__(
        self,
        database_url: str,
        *,
        pool_size: int,
        max_overflow: int,
        connect_timeout_seconds: int,
    ) -> None:
        try:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
        except ImportError as exc:
            raise DatabaseUnavailableError(
                "PostgreSQL is configured but psycopg[pool] is not installed"
            ) from exc

        self._pool = ConnectionPool(
            conninfo=database_url,
            min_size=1,
            max_size=max(pool_size, pool_size + max_overflow),
            kwargs={"row_factory": dict_row},
            timeout=connect_timeout_seconds,
            open=True,
        )
        try:
            self._pool.wait(timeout=connect_timeout_seconds)
        except Exception as exc:
            self._pool.close()
            raise DatabaseUnavailableError("PostgreSQL connection pool is unavailable") from exc

    @contextmanager
    def session(self, tenant_id: str) -> Generator[PostgresTenantSession, None, None]:
        with self._pool.connection() as connection:
            connection.execute(
                "SELECT set_config('app.current_tenant_id', %s, true)",
                (tenant_id,),
            )
            yield PostgresTenantSession(connection)

    def close(self) -> None:
        self._pool.close()


class DatabaseManager:
    def __init__(
        self,
        *,
        database_url: str | None = settings.database_url,
        sqlite_path: str = settings.sqlite_path,
        environment: str = settings.environment,
        pool_size: int = settings.db_pool_size,
        max_overflow: int = settings.db_max_overflow,
        connect_timeout_seconds: int = settings.db_connect_timeout_seconds,
    ) -> None:
        self.postgres_configured = bool(
            database_url and database_url.startswith(("postgres://", "postgresql://"))
        )
        self.initialization_error: str | None = None
        self._engine: DatabaseEngine | None = None

        if self.postgres_configured:
            try:
                self._engine = PostgresTenantEngine(
                    database_url or "",
                    pool_size=pool_size,
                    max_overflow=max_overflow,
                    connect_timeout_seconds=connect_timeout_seconds,
                )
            except DatabaseUnavailableError as exc:
                self.initialization_error = str(exc)
                if environment.lower() != "production":
                    self._engine = SqliteTenantEngine(sqlite_path)
        elif environment.lower() == "production":
            self.initialization_error = "MEDGUARD_DATABASE_URL is required in production"
        else:
            self._engine = SqliteTenantEngine(sqlite_path)

    @property
    def backend_name(self) -> str:
        return self._engine.backend_name if self._engine else "unavailable"

    @property
    def is_durable(self) -> bool:
        return bool(self._engine and self._engine.is_durable)

    @property
    def is_postgres(self) -> bool:
        return bool(self._engine and self._engine.is_postgres)

    @contextmanager
    def tenant_context(self, tenant_id: str) -> Generator[TenantSession, None, None]:
        if self._engine is None:
            raise DatabaseUnavailableError(self.initialization_error or "Database is unavailable")
        with self._engine.session(tenant_id) as session:
            yield session

    def healthcheck(self, tenant_id: str) -> tuple[bool, str]:
        if self._engine is None:
            return False, self.initialization_error or "database is unavailable"
        try:
            with self._engine.session(tenant_id) as session:
                session.execute(
                    """
                    SELECT job_id FROM prescription_jobs
                    WHERE tenant_id = ? LIMIT 1
                    """,
                    (tenant_id,),
                )
            return True, f"active backend: {self.backend_name}"
        except Exception as exc:
            return False, f"{self.backend_name} health check failed: {exc.__class__.__name__}"

    def close(self) -> None:
        if self._engine:
            self._engine.close()


db_manager = DatabaseManager()


def encode_timestamp(session: TenantSession, epoch_seconds: float) -> float | datetime:
    if session.dialect == "postgresql":
        return datetime.fromtimestamp(epoch_seconds, timezone.utc)
    return epoch_seconds


def decode_timestamp(value: Any) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    return float(value)
