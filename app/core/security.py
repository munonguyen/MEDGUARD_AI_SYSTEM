from __future__ import annotations

from hashlib import sha256
import re

from fastapi import Header, HTTPException, Request, status

from app.core.config import settings
from app.core.context import RequestContext
from app.core.secrets import secret_manager


def _hash_key(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def make_request_id(seed: str) -> str:
    digest = sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"req_{digest}"


def verify_tenant_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RequestContext:
    context = verify_tenant_credentials(request, x_api_key, x_tenant_id)
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "missing_auth_headers", "message": "Missing Idempotency-Key."},
        )
    normalized_key = idempotency_key.strip()
    if len(normalized_key) > 128 or not re.fullmatch(r"[A-Za-z0-9._:-]+", normalized_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "invalid_idempotency_key",
                "message": "Idempotency-Key must be 1-128 characters using letters, numbers, '.', '_', ':' or '-'.",
            },
        )
    return RequestContext(
        request_id=context.request_id,
        tenant_id=context.tenant_id,
        idempotency_key=normalized_key,
        role=context.role,
    )


def verify_tenant_credentials(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
) -> RequestContext:
    from app.services.browser_auth import COOKIE, authenticate, fail
    if COOKIE in request.cookies:
        account = authenticate(request)
        # Patient accounts cannot reach privileged operational tools, even by injecting headers.
        path = request.url.path
        if path.startswith(("/v1/audit", "/v1/queue", "/v1/pharmacy", "/v1/result-delivery", "/v1/fhir")) or re.fullmatch(r"/v1/jobs/[^/]+/(process|review)", path):
            fail("patient_role_required", 403)
        return RequestContext(request_id=getattr(request.state, "request_id", "") or make_request_id(account["account_id"]),
                              tenant_id=account["tenant_id"], idempotency_key="", role="patient")
    if not x_api_key or not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "missing_auth_headers", "message": "Missing tenant credentials."},
        )
    if x_tenant_id not in settings.allowed_tenants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "tenant_not_enabled", "message": "Tenant is not enabled."},
        )
    if not secret_manager.verify_key(tenant_id=x_tenant_id, raw_key=x_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "invalid_api_key", "message": "Invalid API key."},
        )
    request_id = getattr(request.state, "request_id", None) or make_request_id(
        f"{x_tenant_id}:{_hash_key(x_api_key)}"
    )
    return RequestContext(
        request_id=request_id,
        tenant_id=x_tenant_id,
        idempotency_key="",
    )
