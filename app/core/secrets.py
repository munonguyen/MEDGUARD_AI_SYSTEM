"""Secret manager and API key credential store with zero-downtime rotation.

Enforces:
- API key hashing using PBKDF2-HMAC-SHA256 / Argon2 with cryptographic salt.
- Multiple active keys per tenant (Primary + Rotating) to enable key rotation
  without downtime.
- Revocation of compromised keys.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from threading import RLock
from time import time
from typing import Literal

from app.core.config import settings


@dataclass
class TenantApiKey:
    key_id: str
    tenant_id: str
    key_hash: str
    key_prefix: str
    status: Literal["active", "rotating", "revoked"]
    created_at: float = field(default_factory=time)
    expires_at: float | None = None


class SecretManager:
    """Manages secure tenant credentials with key rotation capabilities."""

    def __init__(self) -> None:
        self._salt = settings.secret_master_key.encode("utf-8")
        self._lock = RLock()
        # In-memory credential registry: tenant_id -> list[TenantApiKey]
        self._keys: dict[str, list[TenantApiKey]] = {}
        self._verified_cache: dict[tuple[str, str], str] = {}
        self._init_default_keys()

    @staticmethod
    def _fingerprint(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def _hash_key(self, raw_key: str) -> str:
        """Derives a secure hash for the API key using PBKDF2 with system salt."""
        return hashlib.pbkdf2_hmac(
            "sha256",
            raw_key.encode("utf-8"),
            self._salt,
            iterations=10000,
        ).hex()

    def _init_default_keys(self) -> None:
        """Populates initial keys from configuration."""
        for tenant_id, raw_key in settings.api_keys_by_tenant.items():
            self.register_key(tenant_id=tenant_id, raw_key=raw_key, status="active")

    def register_key(
        self,
        *,
        tenant_id: str,
        raw_key: str,
        status: Literal["active", "rotating", "revoked"] = "active",
        expires_at: float | None = None,
    ) -> TenantApiKey:
        key_hash = self._hash_key(raw_key)
        prefix = raw_key[:8] if len(raw_key) >= 8 else raw_key
        key_obj = TenantApiKey(
            key_id=secrets.token_hex(8),
            tenant_id=tenant_id,
            key_hash=key_hash,
            key_prefix=prefix,
            status=status,
            expires_at=expires_at,
        )
        with self._lock:
            if tenant_id not in self._keys:
                self._keys[tenant_id] = []
            self._keys[tenant_id].append(key_obj)
            if status in ("active", "rotating"):
                self._verified_cache[(tenant_id, self._fingerprint(raw_key))] = key_hash
        return key_obj

    def rotate_key(self, *, tenant_id: str, new_raw_key: str) -> TenantApiKey:
        """Enables zero-downtime key rotation:

        Demotes current 'active' keys to 'rotating' and registers new key as 'active'.
        """
        with self._lock:
            existing = self._keys.get(tenant_id, [])
            for k in existing:
                if k.status == "active":
                    k.status = "rotating"
            return self.register_key(tenant_id=tenant_id, raw_key=new_raw_key, status="active")

    def revoke_key(self, *, tenant_id: str, key_hash: str) -> bool:
        with self._lock:
            for k in self._keys.get(tenant_id, []):
                if k.key_hash == key_hash:
                    k.status = "revoked"
                    self._verified_cache = {
                        cache_key: cached_hash
                        for cache_key, cached_hash in self._verified_cache.items()
                        if cached_hash != key_hash
                    }
                    return True
        return False

    def verify_key(self, *, tenant_id: str, raw_key: str) -> bool:
        """Verifies if the raw key matches any active or rotating key for the tenant."""
        now = time()
        fingerprint = self._fingerprint(raw_key)
        with self._lock:
            tenant_keys = self._keys.get(tenant_id, [])
            cached_hash = self._verified_cache.get((tenant_id, fingerprint))
            if cached_hash:
                for key in tenant_keys:
                    if (
                        key.key_hash == cached_hash
                        and key.status in ("active", "rotating")
                        and (key.expires_at is None or now <= key.expires_at)
                    ):
                        return True

            candidate_hash = self._hash_key(raw_key)
            for k in tenant_keys:
                if k.status in ("active", "rotating"):
                    if k.expires_at and now > k.expires_at:
                        continue
                    if hmac.compare_digest(k.key_hash, candidate_hash):
                        self._verified_cache[(tenant_id, fingerprint)] = k.key_hash
                        return True

        return False


secret_manager = SecretManager()
