"""Clean Architecture Repository Layer for Loose Coupling between Services and DB Engines.

Implements Interface Adapters layer (Clean Architecture):
- Encapsulates queries and mutations inside domain-driven repositories.
- Decouples Application Use Cases (Services) from raw SQL dialect nuances.
- Supports Dependency Injection (Loose Coupling) with default singleton DatabaseManager.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from time import time
from typing import Any, Generic, TypeVar
from uuid import uuid4

from app.core.database import DatabaseManager, TenantSession, db_manager, decode_timestamp, encode_timestamp

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Generic base repository managing tenant sessions and query execution."""

    def __init__(self, database: DatabaseManager = db_manager) -> None:
        self.database = database

    def _execute(
        self, tenant_id: str, query: str, params: tuple[Any, ...] | dict[str, Any] = ()
    ) -> list[dict[str, Any]]:
        with self.database.tenant_context(tenant_id) as session:
            return session.execute(query, params)

    def _execute_scalar(
        self, tenant_id: str, query: str, params: tuple[Any, ...] | dict[str, Any] = ()
    ) -> Any:
        with self.database.tenant_context(tenant_id) as session:
            return session.execute_scalar(query, params)


class PrescriptionJobRepository(BaseRepository[dict[str, Any]]):
    """Encapsulates prescription job persistence and concurrency-safe claiming."""

    def insert(self, job_data: dict[str, Any]) -> None:
        tenant_id = str(job_data["tenant_id"])
        with self.database.tenant_context(tenant_id) as session:
            created_at_encoded = encode_timestamp(session, job_data["created_at"])
            session.execute(
                """
                INSERT INTO prescription_jobs (
                    job_id, tenant_id, request_id, patient_ref, image_sha256,
                    image_size_bytes, content_type, catalog_ref, status,
                    review_status, result, error_code, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_data["job_id"],
                    job_data["tenant_id"],
                    job_data["request_id"],
                    job_data["patient_ref"],
                    job_data["image_sha256"],
                    job_data["image_size_bytes"],
                    job_data["content_type"],
                    job_data.get("catalog_ref"),
                    job_data.get("status", "queued"),
                    job_data.get("review_status", "PENDING_REVIEW"),
                    None,
                    None,
                    created_at_encoded,
                    None,
                ),
            )

    def find_by_id(self, tenant_id: str, job_id: str) -> dict[str, Any] | None:
        rows = self._execute(
            tenant_id,
            """
            SELECT job_id, tenant_id, request_id, patient_ref, image_sha256,
                   image_size_bytes, content_type, catalog_ref, status,
                   review_status, result, error_code, created_at, completed_at
            FROM prescription_jobs
            WHERE tenant_id = ? AND job_id = ?
            """,
            (tenant_id, job_id),
        )
        return rows[0] if rows else None

    def update_status_and_result(
        self,
        tenant_id: str,
        job_id: str,
        status: str,
        review_status: str,
        result: dict[str, Any] | None,
        error_code: str | None,
        completed_at: float | None,
    ) -> None:
        with self.database.tenant_context(tenant_id) as session:
            completed_encoded = (
                encode_timestamp(session, completed_at) if completed_at else None
            )
            result_json = (
                json.dumps(result, separators=(",", ":"), sort_keys=True)
                if result is not None
                else None
            )
            session.execute(
                """
                UPDATE prescription_jobs
                SET status = ?, review_status = ?, result = ?, error_code = ?, completed_at = ?
                WHERE tenant_id = ? AND job_id = ?
                """,
                (
                    status,
                    review_status,
                    result_json,
                    error_code,
                    completed_encoded,
                    tenant_id,
                    job_id,
                ),
            )

    def claim_processing(self, tenant_id: str, job_id: str) -> bool:
        """Atomically claim a queued job for processing."""
        with self.database.tenant_context(tenant_id) as session:
            claimed = session.execute(
                """
                UPDATE prescription_jobs SET status = 'processing'
                WHERE tenant_id = ? AND job_id = ? AND status = 'queued'
                RETURNING status
                """,
                (tenant_id, job_id),
            )
            return bool(claimed)


class AuditEventRepository(BaseRepository[dict[str, Any]]):
    """Encapsulates immutable security and clinical audit logs."""

    def record_event(
        self,
        tenant_id: str,
        event_id: str,
        request_id: str,
        action: str,
        payload_type: str,
        metadata_json: str,
        created_at: str,
    ) -> None:
        self._execute(
            tenant_id,
            """
            INSERT INTO audit_events (
                event_id, tenant_id, request_id, action, payload_type,
                metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                tenant_id,
                request_id,
                action,
                payload_type,
                metadata_json,
                created_at,
            ),
        )

    def query_events(
        self, tenant_id: str, request_id: str | None = None
    ) -> list[dict[str, Any]]:
        query = """
            SELECT event_id, tenant_id, request_id, action, payload_type,
                   metadata_json, created_at
            FROM audit_events
            WHERE tenant_id = ?
        """
        params: tuple[Any, ...] = (tenant_id,)
        if request_id:
            query += " AND request_id = ?"
            params += (request_id,)
        query += " ORDER BY created_at ASC"
        return self._execute(tenant_id, query, params)

    def clear(self, tenant_id: str = "local-test") -> None:
        if self.database.is_postgres:
            return
        self._execute(tenant_id, "DELETE FROM audit_events")


class UserSpendingRepository(BaseRepository[dict[str, Any]]):
    """Encapsulates personal health spending transactions and budget targets."""

    def get_user_transactions(
        self, tenant_id: str, user_id: str
    ) -> list[dict[str, Any]]:
        return self._execute(
            tenant_id,
            """
            SELECT id, user_id, title, amount_vnd, category, provider, doctor,
                   bhyt_covered_vnd, is_gpp, raw_date, created_at
            FROM user_spending
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        )

    def add_transaction(
        self,
        tenant_id: str,
        user_id: str,
        title: str,
        amount_vnd: int,
        category: str = "medication",
        provider: str = "",
        doctor: str = "",
        bhyt_covered_vnd: int = 0,
        is_gpp: bool = True,
        raw_date: str = "",
    ) -> dict[str, Any]:
        tx_id = f"tx_{uuid4().hex[:12]}"
        now = time()
        date_str = raw_date or datetime.now().strftime("%Y-%m-%d")
        self._execute(
            tenant_id,
            """
            INSERT INTO user_spending (
                id, user_id, title, amount_vnd, category, provider, doctor,
                bhyt_covered_vnd, is_gpp, raw_date, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tx_id,
                user_id,
                title,
                amount_vnd,
                category,
                provider,
                doctor,
                bhyt_covered_vnd,
                1 if is_gpp else 0,
                date_str,
                now,
            ),
        )
        return {
            "id": tx_id,
            "user_id": user_id,
            "title": title,
            "amount_vnd": amount_vnd,
            "category": category,
            "provider": provider,
            "doctor": doctor,
            "bhyt_covered_vnd": bhyt_covered_vnd,
            "is_gpp": bool(is_gpp),
            "raw_date": date_str,
            "created_at": now,
        }


class HealthTwinRepository(BaseRepository[dict[str, Any]]):
    """Encapsulates 3D anatomical health twin state and timeline recovery."""

    def load_twin(self, tenant_id: str, user_id: str) -> dict[str, Any] | None:
        rows = self._execute(
            tenant_id,
            """
            SELECT user_id, overall_health_score, health_trend, active_diagnosis,
                   sleep_score, recovery_score, stress_score, energy_battery_pct,
                   hydration_pct, vitals_json, organs_json, active_medications_json,
                   discontinued_medications_json, contraindicated_regimens_json,
                   clinical_directives_json, safe_guardrail_alert_json, timeline_json,
                   updated_at
            FROM medguard_health_twins
            WHERE user_id = ?
            """,
            (user_id,),
        )
        return rows[0] if rows else None

    def upsert_twin(self, tenant_id: str, user_id: str, fields: dict[str, Any]) -> None:
        now = time()
        with self.database.tenant_context(tenant_id) as session:
            existing = session.execute(
                "SELECT user_id FROM medguard_health_twins WHERE user_id = ?",
                (user_id,),
            )
            if existing:
                set_clauses = [f"{col} = ?" for col in fields.keys()]
                set_clauses.append("updated_at = ?")
                sql = f"UPDATE medguard_health_twins SET {', '.join(set_clauses)} WHERE user_id = ?"
                params = tuple(fields.values()) + (now, user_id)
                session.execute(sql, params)
            else:
                cols = ["user_id"] + list(fields.keys()) + ["updated_at"]
                placeholders = ["?"] * len(cols)
                sql = f"INSERT INTO medguard_health_twins ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
                params = (user_id,) + tuple(fields.values()) + (now,)
                session.execute(sql, params)


class IdempotencyRepository(BaseRepository[dict[str, Any]]):
    """Encapsulates durable multi-tenant idempotency reservations and cached responses."""

    def find_record(
        self, tenant_id: str, endpoint: str, idempotency_key: str
    ) -> dict[str, Any] | None:
        rows = self._execute(
            tenant_id,
            """
            SELECT record_id, tenant_id, idempotency_key, endpoint,
                   response_code, response_body, payload_hash, created_at, expires_at
            FROM idempotency_records
            WHERE tenant_id = ? AND endpoint = ? AND idempotency_key = ?
            """,
            (tenant_id, endpoint, idempotency_key),
        )
        return rows[0] if rows else None

    def delete_record(
        self, tenant_id: str, endpoint: str, idempotency_key: str
    ) -> None:
        self._execute(
            tenant_id,
            """
            DELETE FROM idempotency_records
            WHERE tenant_id = ? AND endpoint = ? AND idempotency_key = ?
            """,
            (tenant_id, endpoint, idempotency_key),
        )

    def save_response(
        self,
        tenant_id: str,
        endpoint: str,
        idempotency_key: str,
        response_code: int,
        response_body: str,
        payload_hash: str,
        created_at: float,
        expires_at: float,
    ) -> None:
        with self.database.tenant_context(tenant_id) as session:
            created_enc = encode_timestamp(session, created_at)
            expires_enc = encode_timestamp(session, expires_at)
            if session.dialect in ("mysql", "tidb"):
                session.execute(
                    """
                    INSERT INTO idempotency_records (
                        record_id, tenant_id, idempotency_key, endpoint,
                        response_code, response_body, payload_hash, created_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON DUPLICATE KEY UPDATE
                        response_code = VALUES(response_code),
                        response_body = VALUES(response_body),
                        payload_hash = VALUES(payload_hash),
                        created_at = VALUES(created_at),
                        expires_at = VALUES(expires_at)
                    """,
                    (
                        str(uuid4()),
                        tenant_id,
                        idempotency_key,
                        endpoint,
                        response_code,
                        response_body,
                        payload_hash,
                        created_enc,
                        expires_enc,
                    ),
                )
            else:
                session.execute(
                    """
                    INSERT INTO idempotency_records (
                        record_id, tenant_id, idempotency_key, endpoint,
                        response_code, response_body, payload_hash, created_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(tenant_id, endpoint, idempotency_key) DO UPDATE SET
                        response_code = excluded.response_code,
                        response_body = excluded.response_body,
                        payload_hash = excluded.payload_hash,
                        created_at = excluded.created_at,
                        expires_at = excluded.expires_at
                    """,
                    (
                        str(uuid4()),
                        tenant_id,
                        idempotency_key,
                        endpoint,
                        response_code,
                        response_body,
                        payload_hash,
                        created_enc,
                        expires_enc,
                    ),
                )

    def try_reserve_lease(
        self,
        tenant_id: str,
        endpoint: str,
        idempotency_key: str,
        payload_hash: str,
        now: float,
        lease_expires_at: float,
    ) -> bool:
        """Attempt to atomically acquire a lease for in-flight request execution."""
        with self.database.tenant_context(tenant_id) as session:
            now_enc = encode_timestamp(session, now)
            lease_enc = encode_timestamp(session, lease_expires_at)
            if session.dialect in ("mysql", "tidb"):
                existing = session.execute(
                    """
                    SELECT payload_hash FROM idempotency_records
                    WHERE tenant_id = ? AND endpoint = ? AND idempotency_key = ?
                    """,
                    (tenant_id, endpoint, idempotency_key),
                )
                if not existing:
                    try:
                        session.execute(
                            """
                            INSERT INTO idempotency_records (
                                record_id, tenant_id, idempotency_key, endpoint,
                                response_code, response_body, payload_hash, created_at, expires_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                str(uuid4()),
                                tenant_id,
                                idempotency_key,
                                endpoint,
                                102,
                                "{}",
                                payload_hash,
                                now_enc,
                                lease_enc,
                            ),
                        )
                        return True
                    except Exception:
                        return False
                return False
            else:
                inserted = session.execute(
                    """
                    INSERT INTO idempotency_records (
                        record_id, tenant_id, idempotency_key, endpoint,
                        response_code, response_body, payload_hash, created_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(tenant_id, endpoint, idempotency_key) DO NOTHING
                    RETURNING payload_hash
                    """,
                    (
                        str(uuid4()),
                        tenant_id,
                        idempotency_key,
                        endpoint,
                        102,
                        "{}",
                        payload_hash,
                        now_enc,
                        lease_enc,
                    ),
                )
                return bool(inserted)

    def clear(self) -> None:
        if self.database.is_postgres:
            return
        self._execute("local-test", "DELETE FROM idempotency_records")


# Pre-instantiated default repositories
job_repository = PrescriptionJobRepository()
audit_repository = AuditEventRepository()
spending_repository = UserSpendingRepository()
health_twin_repository = HealthTwinRepository()
idempotency_repository = IdempotencyRepository()
