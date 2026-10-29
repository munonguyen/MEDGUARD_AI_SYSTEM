"""Durable tenant-scoped prescription job repository."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from threading import RLock
from time import time
from uuid import uuid4

from fastapi import HTTPException, status

from app.core.context import RequestContext
from app.core.database import DatabaseManager, db_manager, decode_timestamp, encode_timestamp
from app.core.repository import PrescriptionJobRepository, job_repository
from app.models.prescription import JobStatusResponse


@dataclass
class PrescriptionJob:
    job_id: str
    request_id: str
    tenant_id: str
    patient_ref: str
    image_sha256: str
    image_size_bytes: int
    content_type: str
    catalog_ref: str | None
    created_at: float
    status: str = "queued"
    review_status: str = "PENDING_REVIEW"
    result: dict | None = None
    error_code: str | None = None
    completed_at: float | None = None


class JobStore:
    def __init__(
        self,
        database: DatabaseManager = db_manager,
        repository: PrescriptionJobRepository | None = None,
    ) -> None:
        self.database = database
        self.repository = repository or PrescriptionJobRepository(database)
        self._lock = RLock()
        self.jobs: dict[tuple[str, str], PrescriptionJob] = {}

    @staticmethod
    def _from_row(row: dict) -> PrescriptionJob:
        raw_result = row.get("result")
        result = raw_result if isinstance(raw_result, dict) else json.loads(raw_result) if raw_result else None
        return PrescriptionJob(
            job_id=str(row["job_id"]),
            request_id=str(row["request_id"]),
            tenant_id=str(row["tenant_id"]),
            patient_ref=str(row["patient_ref"]),
            image_sha256=str(row["image_sha256"]),
            image_size_bytes=int(row["image_size_bytes"]),
            content_type=str(row["content_type"]),
            catalog_ref=row.get("catalog_ref"),
            created_at=decode_timestamp(row["created_at"]),
            status=str(row["status"]),
            review_status=str(row["review_status"]),
            result=result,
            error_code=row.get("error_code"),
            completed_at=decode_timestamp(row["completed_at"]) if row.get("completed_at") else None,
        )

    def create(
        self,
        *,
        ctx: RequestContext,
        patient_ref: str,
        image_bytes: bytes,
        content_type: str,
        catalog_ref: str | None,
    ) -> PrescriptionJob:
        job = PrescriptionJob(
            job_id=f"job_{uuid4().hex[:16]}",
            request_id=ctx.request_id,
            tenant_id=ctx.tenant_id,
            patient_ref=patient_ref,
            image_sha256=sha256(image_bytes).hexdigest(),
            image_size_bytes=len(image_bytes),
            content_type=content_type,
            catalog_ref=catalog_ref,
            created_at=time(),
        )
        with self._lock:
            self.repository.insert({
                "job_id": job.job_id,
                "tenant_id": job.tenant_id,
                "request_id": job.request_id,
                "patient_ref": job.patient_ref,
                "image_sha256": job.image_sha256,
                "image_size_bytes": job.image_size_bytes,
                "content_type": job.content_type,
                "catalog_ref": job.catalog_ref,
                "status": job.status,
                "review_status": job.review_status,
                "created_at": job.created_at,
            })
            self.jobs[(ctx.tenant_id, job.job_id)] = job
        return job

    def _load(self, tenant_id: str, job_id: str) -> PrescriptionJob | None:
        row = self.repository.find_by_id(tenant_id, job_id)
        if not row:
            return None
        job = self._from_row(row)
        self.jobs[(tenant_id, job_id)] = job
        return job

    def get(self, *, ctx: RequestContext, job_id: str) -> PrescriptionJob:
        with self._lock:
            job = self._load(ctx.tenant_id, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "job_not_found", "message": "Job was not found."},
            )
        return job

    def get_for_worker(self, tenant_id: str, job_id: str) -> PrescriptionJob | None:
        with self._lock:
            return self._load(tenant_id, job_id)

    def _update(self, job: PrescriptionJob) -> None:
        self.repository.update_status_and_result(
            tenant_id=job.tenant_id,
            job_id=job.job_id,
            status=job.status,
            review_status=job.review_status,
            result=job.result,
            error_code=job.error_code,
            completed_at=job.completed_at,
        )

    def mark_processing(self, job: PrescriptionJob) -> bool:
        with self._lock:
            claimed = self.repository.claim_processing(job.tenant_id, job.job_id)
            if claimed:
                job.status = "processing"
                self.jobs[(job.tenant_id, job.job_id)] = job
                return True
            return False

    def claim_next(self) -> PrescriptionJob | None:
        with self._lock:
            for job in self.jobs.values():
                if job.status == "queued":
                    return job if self.mark_processing(job) else None
        return None

    def fail(self, job: PrescriptionJob, error_code: str) -> None:
        with self._lock:
            job.status = "failed"
            job.review_status = "FAILED"
            job.error_code = error_code
            job.completed_at = time()
            self._update(job)

    def complete(self, job: PrescriptionJob, result: dict) -> None:
        with self._lock:
            job.status = "completed"
            job.review_status = "PENDING_REVIEW"
            job.result = result
            job.error_code = None
            job.completed_at = time()
            self._update(job)

    def set_review_status(self, job: PrescriptionJob, review_status: str) -> None:
        with self._lock:
            job.review_status = review_status
            self._update(job)

    def clear(self) -> None:
        with self._lock:
            self.jobs.clear()
            if self.database.is_postgres:
                return
            with self.database.tenant_context("local-test") as session:
                session.execute("DELETE FROM prescription_jobs")


job_store = JobStore()


def to_job_response(job: PrescriptionJob, ctx: RequestContext) -> JobStatusResponse:
    return JobStatusResponse(
        request_id=ctx.request_id,
        job_id=job.job_id,
        status=job.status,  # type: ignore[arg-type]
        review_status=job.review_status,  # type: ignore[arg-type]
        result=job.result,
        error_code=job.error_code,
    )
