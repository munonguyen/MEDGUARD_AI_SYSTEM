"""Ephemeral development storage and optional S3 storage for prescription images.

Enforces Principle P2:
- Ephemeral storage with configurable TTL (default 1 hour)
- Data isolation by tenant_id
- SHA-256 integrity metadata and tenant-scoped keys
- Pluggable S3/MinIO backend with an in-memory masked development fallback
"""

from __future__ import annotations

import hashlib
import hmac
import threading
from dataclasses import dataclass
from time import time
from typing import Any

from app.core.config import settings


@dataclass
class StoredObject:
    object_id: str
    tenant_id: str
    content_type: str
    data: bytes
    sha256_hash: str
    created_at: float
    expires_at: float


class InMemoryObjectStorage:
    """Thread-safe masked development storage with TTL cleanup."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: dict[tuple[str, str], StoredObject] = {}

    def _encrypt_decrypt(self, data: bytes) -> bytes:
        # Reversible masking prevents accidental plain-text inspection. It is
        # not a production encryption primitive; readiness rejects this backend.
        key = settings.secret_master_key.encode("utf-8")
        mask = hashlib.sha256(key).digest()
        masked = bytearray(data)
        for i in range(len(masked)):
            masked[i] ^= mask[i % len(mask)]
        return bytes(masked)

    def store(
        self,
        *,
        tenant_id: str,
        object_id: str,
        data: bytes,
        content_type: str,
        ttl_seconds: int | None = None,
    ) -> str:
        ttl = ttl_seconds or settings.storage_retention_ttl_seconds
        now = time()
        digest = hashlib.sha256(data).hexdigest()
        encrypted = self._encrypt_decrypt(data)

        obj = StoredObject(
            object_id=object_id,
            tenant_id=tenant_id,
            content_type=content_type,
            data=encrypted,
            sha256_hash=digest,
            created_at=now,
            expires_at=now + ttl,
        )
        with self._lock:
            self._store[(tenant_id, object_id)] = obj
        return object_id

    def retrieve(self, *, tenant_id: str, object_id: str) -> tuple[bytes, str] | None:
        with self._lock:
            obj = self._store.get((tenant_id, object_id))
            if not obj:
                return None
            if time() > obj.expires_at:
                del self._store[(tenant_id, object_id)]
                return None
            decrypted = self._encrypt_decrypt(obj.data)
            return decrypted, obj.content_type

    def delete(self, *, tenant_id: str, object_id: str) -> bool:
        with self._lock:
            return self._store.pop((tenant_id, object_id), None) is not None

    def purge_expired(self) -> int:
        now = time()
        with self._lock:
            expired = [k for k, v in self._store.items() if now > v.expires_at]
            for k in expired:
                del self._store[k]
            return len(expired)


class S3ObjectStorage:
    """S3/MinIO compatible object store implementation."""

    def __init__(self) -> None:
        self.endpoint_url = settings.s3_endpoint_url
        self.bucket = settings.s3_bucket_name
        self._s3_client: Any = None
        self._init_client()

    def _init_client(self) -> None:
        if not self.endpoint_url:
            return
        try:
            import boto3
            from botocore.config import Config

            self._s3_client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=settings.s3_access_key_id,
                aws_secret_access_key=settings.s3_secret_access_key,
                config=Config(
                    connect_timeout=2,
                    read_timeout=2,
                    retries={"max_attempts": 1, "mode": "standard"},
                ),
            )
        except Exception:
            self._s3_client = None

    @property
    def is_available(self) -> bool:
        return self._s3_client is not None

    def healthcheck(self) -> bool:
        if not self._s3_client:
            self._init_client()
            if not self._s3_client:
                return False
        try:
            self._s3_client.head_bucket(Bucket=self.bucket)
            return True
        except Exception:
            self._s3_client = None
            return False

    def store(
        self,
        *,
        tenant_id: str,
        object_id: str,
        data: bytes,
        content_type: str,
        ttl_seconds: int | None = None,
    ) -> str:
        if not self._s3_client:
            raise RuntimeError("S3 client is not available")
        key = f"tenants/{tenant_id}/prescriptions/{object_id}"
        self._s3_client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            ServerSideEncryption="AES256",
            Metadata={"tenant_id": tenant_id, "ttl": str(ttl_seconds or settings.storage_retention_ttl_seconds)},
        )
        return object_id

    def retrieve(self, *, tenant_id: str, object_id: str) -> tuple[bytes, str] | None:
        if not self._s3_client:
            return None
        key = f"tenants/{tenant_id}/prescriptions/{object_id}"
        try:
            res = self._s3_client.get_object(Bucket=self.bucket, Key=key)
            data = res["Body"].read()
            content_type = res.get("ContentType", "application/octet-stream")
            return data, content_type
        except Exception:
            return None

    def delete(self, *, tenant_id: str, object_id: str) -> bool:
        if not self._s3_client:
            return False
        key = f"tenants/{tenant_id}/prescriptions/{object_id}"
        try:
            self._s3_client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def purge_expired(self) -> int:
        # S3 lifecycle policies handle expiration natively
        return 0


class StorageManager:
    def __init__(self) -> None:
        self._in_memory = InMemoryObjectStorage()
        self._s3 = S3ObjectStorage()

    @property
    def backend(self) -> InMemoryObjectStorage | S3ObjectStorage:
        if self._s3.is_available:
            return self._s3
        return self._in_memory

    @property
    def backend_name(self) -> str:
        return "s3" if isinstance(self.backend, S3ObjectStorage) else "memory"

    @property
    def is_durable(self) -> bool:
        return isinstance(self.backend, S3ObjectStorage)

    @property
    def is_healthy(self) -> bool:
        return self._s3.healthcheck()

    def _backend_for_work(self) -> InMemoryObjectStorage | S3ObjectStorage:
        if settings.environment.lower() == "production" and not self.is_healthy:
            raise RuntimeError("A healthy S3 object store is required in production")
        return self.backend

    def store(
        self,
        *,
        tenant_id: str,
        object_id: str,
        data: bytes,
        content_type: str,
        ttl_seconds: int | None = None,
    ) -> str:
        return self._backend_for_work().store(
            tenant_id=tenant_id,
            object_id=object_id,
            data=data,
            content_type=content_type,
            ttl_seconds=ttl_seconds,
        )

    def retrieve(self, *, tenant_id: str, object_id: str) -> tuple[bytes, str] | None:
        return self._backend_for_work().retrieve(tenant_id=tenant_id, object_id=object_id)

    def delete(self, *, tenant_id: str, object_id: str) -> bool:
        return self._backend_for_work().delete(tenant_id=tenant_id, object_id=object_id)

    def purge_expired(self) -> int:
        return self._backend_for_work().purge_expired()


storage_manager = StorageManager()
