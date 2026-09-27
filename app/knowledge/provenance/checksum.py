"""Cryptographic and data integrity utility for Knowledge Provenance.

Computes and verifies SHA-256 digests for knowledge sources, evidence chunks,
and clinical state snapshots to ensure deterministic auditability.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def compute_sha256(data: str | bytes | dict[str, Any] | list[Any]) -> str:
    """Computes a deterministic SHA-256 hex digest."""
    if isinstance(data, (dict, list)):
        payload = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    elif isinstance(data, str):
        payload = data.encode("utf-8")
    elif isinstance(data, bytes):
        payload = data
    else:
        payload = str(data).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_checksum(data: str | bytes | dict[str, Any] | list[Any], expected_hash: str) -> bool:
    """Verifies that the data matches the expected SHA-256 hash."""
    return compute_sha256(data).lower() == expected_hash.strip().lower()
