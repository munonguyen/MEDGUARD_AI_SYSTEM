from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from time import time

import pytest

from app.core.context import RequestContext
from app.core.database import DatabaseManager, DatabaseUnavailableError
from app.core.queue import InMemoryJobQueue, RedisJobQueue
from app.core.secrets import SecretManager
from app.services.audit import AuditEvent, AuditStore
from app.services.idempotency import IdempotencyStore
from app.services.jobs import JobStore
from app.workers import ocr_worker


class _FakePipeline:
    def __init__(self, client: "_FakeRedis") -> None:
        self.client = client
        self.operations: list[tuple[str, tuple]] = []

    def lrem(self, *args):
        self.operations.append(("lrem", args))
        return self

    def lpush(self, *args):
        self.operations.append(("lpush", args))
        return self

    def execute(self):
        return [getattr(self.client, name)(*args) for name, args in self.operations]


class _FakeRedis:
    def __init__(self) -> None:
        self.lists: dict[str, list[str]] = {}
        self.commands: list[tuple] = []

    def ping(self):
        return True

    def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)
        return len(self.lists[key])

    def execute_command(self, *args):
        self.commands.append(args)
        _, source, destination, _, _, _ = args
        if not self.lists.get(source):
            return None
        value = self.lists[source].pop()
        self.lists.setdefault(destination, []).insert(0, value)
        return value

    def lrem(self, key, count, value):
        removed = 0
        retained = []
        for item in self.lists.get(key, []):
            if item == value and (count == 0 or removed < count):
                removed += 1
            else:
                retained.append(item)
        self.lists[key] = retained
        return removed

    def lrange(self, key, start, end):
        del start, end
        return list(self.lists.get(key, []))

    def llen(self, key):
        return len(self.lists.get(key, []))

    def pipeline(self, transaction=True):
        assert transaction is True
        return _FakePipeline(self)

    def eval(self, script, number_of_keys, source, destination, old_value, new_value):
        del script
        assert number_of_keys == 2
        removed = self.lrem(source, 1, old_value)
        if removed == 1:
            self.lpush(destination, new_value)
        return removed


def _context(tenant_id: str = "tenant-a") -> RequestContext:
    return RequestContext(request_id="req-persist", tenant_id=tenant_id, idempotency_key="idem")


def test_sqlite_repositories_survive_manager_restart(tmp_path):
    path = str(tmp_path / "medguard.sqlite3")
    first_database = DatabaseManager(sqlite_path=path, environment="development")
    jobs = JobStore(first_database)
    idempotency = IdempotencyStore(first_database)
    audit = AuditStore(first_database)
    job = jobs.create(
        ctx=_context(), patient_ref="patient-1", image_bytes=b"image",
        content_type="image/png", catalog_ref=None,
    )
    jobs.mark_processing(job)
    jobs.complete(job, {"medications": [{"name": "verified"}]})
    idempotency.put(
        ("tenant-a", "triage.evaluate", "idem"),
        payload_hash="a" * 64,
        response={"urgency": "ROUTINE"},
    )
    audit.append(AuditEvent("req-persist", "tenant-a", "restart.test", "Test", {"ok": True}))
    first_database.close()

    second_database = DatabaseManager(sqlite_path=path, environment="development")
    loaded_job = JobStore(second_database).get(ctx=_context(), job_id=job.job_id)
    loaded_entry = IdempotencyStore(second_database).get(
        ("tenant-a", "triage.evaluate", "idem")
    )
    loaded_audit = AuditStore(second_database).query("tenant-a", "req-persist")
    assert loaded_job.status == "completed"
    assert loaded_job.result == {"medications": [{"name": "verified"}]}
    assert loaded_entry and loaded_entry.response["urgency"] == "ROUTINE"
    assert loaded_audit[0].metadata == {"ok": True}
    second_database.close()


def test_production_database_fails_closed_without_postgres():
    database = DatabaseManager(database_url=None, environment="production")
    assert database.backend_name == "unavailable"
    with pytest.raises(DatabaseUnavailableError):
        with database.tenant_context("tenant-a"):
            pass


def test_sqlite_migrates_legacy_idempotency_table(tmp_path):
    path = str(tmp_path / "legacy.sqlite3")
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE idempotency_records (
            record_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
            idempotency_key TEXT NOT NULL, endpoint TEXT NOT NULL,
            response_code INTEGER NOT NULL, response_body TEXT NOT NULL,
            created_at REAL NOT NULL, expires_at REAL NOT NULL,
            UNIQUE(tenant_id, idempotency_key)
        )
        """
    )
    connection.commit()
    connection.close()
    database = DatabaseManager(sqlite_path=path, environment="development")
    with database.tenant_context("tenant-a") as session:
        columns = session.execute("PRAGMA table_info(idempotency_records)")
    assert "payload_hash" in {row["name"] for row in columns}
    store = IdempotencyStore(database)
    store.put(
        ("tenant-a", "triage.evaluate", "shared-key"),
        payload_hash="a" * 64,
        response={"action": "triage"},
    )
    store.put(
        ("tenant-a", "fhir.export", "shared-key"),
        payload_hash="b" * 64,
        response={"action": "fhir"},
    )
    with database.tenant_context("tenant-a") as session:
        rows = session.execute(
            "SELECT COUNT(*) AS count FROM idempotency_records WHERE idempotency_key = ?",
            ("shared-key",),
        )
    assert rows[0]["count"] == 2
    database.close()


def test_concurrent_idempotency_writes_preserve_one_record(tmp_path):
    database = DatabaseManager(
        sqlite_path=str(tmp_path / "concurrent.sqlite3"), environment="development"
    )
    store = IdempotencyStore(database)

    def write_response(index: int) -> None:
        store.put(
            ("tenant-a", "triage.evaluate", "same-key"),
            payload_hash="b" * 64,
            response={"writer": index},
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(write_response, range(40)))
    with database.tenant_context("tenant-a") as session:
        rows = session.execute(
            """
            SELECT COUNT(*) AS count FROM idempotency_records
            WHERE tenant_id = ? AND endpoint = ? AND idempotency_key = ?
            """,
            ("tenant-a", "triage.evaluate", "same-key"),
        )
    assert rows[0]["count"] == 1
    database.close()


def test_idempotency_reservation_blocks_duplicate_in_flight_request(tmp_path):
    database = DatabaseManager(
        sqlite_path=str(tmp_path / "reservation.sqlite3"), environment="development"
    )
    first = IdempotencyStore(database)
    second = IdempotencyStore(database)
    key = ("tenant-a", "prescription.extract", "same-key")
    assert first.acquire(key, "a" * 64)[0] == "acquired"
    assert second.acquire(key, "a" * 64)[0] == "in_progress"
    assert second.acquire(key, "b" * 64)[0] == "conflict"
    first.put(key, payload_hash="a" * 64, response={"job_id": "job-1"})
    outcome, entry = second.acquire(key, "a" * 64)
    assert outcome == "replay"
    assert entry and entry.response == {"job_id": "job-1"}
    database.close()


def test_database_compare_and_set_allows_only_one_job_claim(tmp_path):
    database = DatabaseManager(
        sqlite_path=str(tmp_path / "job-claim.sqlite3"), environment="development"
    )
    first = JobStore(database)
    second = JobStore(database)
    job = first.create(
        ctx=_context(), patient_ref="patient-1", image_bytes=b"image",
        content_type="image/png", catalog_ref=None,
    )
    stale_copy = second.get(ctx=_context(), job_id=job.job_id)
    assert first.mark_processing(job) is True
    assert second.mark_processing(stale_copy) is False
    assert second.get(ctx=_context(), job_id=job.job_id).status == "processing"
    database.close()


def test_memory_queue_retries_then_dead_letters():
    queue = InMemoryJobQueue(max_attempts=2)
    queue.enqueue("tenant-a", "job-1", {"action": "ocr"})
    assert queue.dequeue().attempts == 1  # type: ignore[union-attr]
    queue.fail("job-1", "temporary", requeue=True)
    assert queue.dequeue().attempts == 2  # type: ignore[union-attr]
    queue.fail("job-1", "temporary", requeue=True)
    assert queue.queue_depth() == 0
    assert queue.processing_depth() == 0
    assert queue.dead_letter_depth() == 1


def test_memory_queue_reclaims_stale_claim():
    queue = InMemoryJobQueue(max_attempts=3)
    queue.enqueue("tenant-a", "job-1", {})
    message = queue.dequeue()
    assert message is not None
    message.claimed_at = time() - 30
    assert queue.reclaim_stale(10) == 1
    assert queue.queue_depth() == 1
    assert queue.processing_depth() == 0


def test_redis_queue_uses_atomic_pending_to_processing_claim():
    client = _FakeRedis()
    queue = RedisJobQueue("redis://unused", client=client)
    queue.enqueue("tenant-a", "job-1", {"action": "ocr"})
    message = queue.dequeue(timeout_seconds=1)
    assert message and message.attempts == 1
    assert client.commands[0][0] == "BLMOVE"
    assert queue.processing_depth() == 1
    queue.ack("job-1")
    assert queue.processing_depth() == 0


def test_redis_stale_reclaim_does_not_duplicate_raced_message():
    client = _FakeRedis()
    queue = RedisJobQueue("redis://unused", client=client)
    queue.enqueue("tenant-a", "job-1", {})
    message = queue.dequeue(timeout_seconds=0)
    assert message is not None and message.receipt is not None
    stale = message.receipt
    replacement = stale.replace(str(message.claimed_at), str(time() - 30))
    client.lrem(queue.processing_key, 1, stale)
    client.lpush(queue.processing_key, replacement)
    original_eval = client.eval

    def raced_eval(*args):
        client.lrem(queue.processing_key, 1, replacement)
        return original_eval(*args)

    client.eval = raced_eval  # type: ignore[method-assign]
    assert queue.reclaim_stale(10) == 0
    assert queue.queue_depth() == 0


def test_reclaimed_processing_job_is_completed_by_new_worker(tmp_path, monkeypatch):
    database = DatabaseManager(
        sqlite_path=str(tmp_path / "worker-recovery.sqlite3"), environment="development"
    )
    jobs = JobStore(database)
    queue = InMemoryJobQueue(max_attempts=3)
    job = jobs.create(
        ctx=_context(), patient_ref="patient-1", image_bytes=b"image",
        content_type="image/png", catalog_ref=None,
    )
    queue.enqueue("tenant-a", job.job_id, {"action": "ocr"})
    first_claim = queue.dequeue()
    assert first_claim is not None
    jobs.mark_processing(job)
    first_claim.claimed_at = time() - 30
    assert queue.reclaim_stale(10) == 1

    class _Storage:
        @staticmethod
        def retrieve(**kwargs):
            del kwargs
            return b"image", "image/png"

    class _Audit:
        @staticmethod
        def append(event):
            del event

    monkeypatch.setattr(ocr_worker, "job_queue", queue)
    monkeypatch.setattr(ocr_worker, "job_store", jobs)
    monkeypatch.setattr(ocr_worker, "storage_manager", _Storage())
    monkeypatch.setattr(ocr_worker, "audit_store", _Audit())
    monkeypatch.setattr(
        ocr_worker,
        "run_vision_pipeline",
        lambda image: {"extracted_medications": [], "has_unmatched_items": False},
    )
    assert ocr_worker.process_next_ocr_job(timeout_seconds=0) == job.job_id
    recovered = jobs.get(ctx=_context(), job_id=job.job_id)
    assert recovered.status == "completed"
    assert queue.processing_depth() == 0
    database.close()


def test_revoked_configured_key_cannot_use_settings_fallback():
    manager = SecretManager()
    key = next(item for item in manager._keys["tenant-demo"] if item.status == "active")
    assert manager.revoke_key(tenant_id="tenant-demo", key_hash=key.key_hash)
    assert manager.verify_key(tenant_id="tenant-demo", raw_key="demo-key") is False


def test_verified_key_cache_still_enforces_expiration():
    manager = SecretManager()
    cached = manager.register_key(
        tenant_id="tenant-cache",
        raw_key="cache-key",
        expires_at=time() - 1,
    )
    assert ("tenant-cache", manager._fingerprint("cache-key")) in manager._verified_cache
    assert manager.verify_key(tenant_id="tenant-cache", raw_key="cache-key") is False
    assert cached.status == "active"
