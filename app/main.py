from pathlib import Path
import re
from uuid import uuid4
from time import perf_counter

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from starlette.concurrency import run_in_threadpool
from starlette.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings
from app.core.observability import metrics
from app.core.rate_limit import RateLimitDecision, rate_limiter

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_RATE_LIMIT_EXEMPT_PATHS = {
    "/v1/health",
    "/v1/health/readiness",
}
_RATE_LIMIT_STATIC_BUCKETS = {
    "/v1/audit/events",
    "/v1/chat",
    "/v1/chat/conversations",
    "/v1/fhir/export",
    "/v1/followup/plan",
    "/v1/health/circuit-status",
    "/v1/medication/safety-check",
    "/v1/medication-schedules",
    "/v1/models",
    "/v1/monitoring/ingest",
    "/v1/pharmacy/fulfillment",
    "/v1/prescription/extract",
    "/v1/product/verify",
    "/v1/queue/prioritize",
    "/v1/result-delivery/prepare",
    "/v1/triage",
}


def _request_id(request: Request) -> str:
    supplied = request.headers.get("X-Request-Id", "").strip()
    if supplied and _REQUEST_ID_PATTERN.fullmatch(supplied):
        return supplied
    return f"req_{uuid4().hex[:16]}"


def _rate_limit_bucket(path: str) -> str:
    if re.fullmatch(r"/v1/chat/conversations/[^/]+", path):
        return "/v1/chat/conversations/{conversation_id}"
    match = re.fullmatch(r"(/v1/jobs)/[^/]+(?P<action>/(?:process|review))?", path)
    if match:
        return f"{match.group(1)}/{{job_id}}{match.group('action') or ''}"
    return path if path in _RATE_LIMIT_STATIC_BUCKETS else "/v1/{unknown}"


def _should_rate_limit(path: str) -> bool:
    return path.startswith("/v1/") and path not in _RATE_LIMIT_EXEMPT_PATHS


def _rate_limit_headers(response, decision: RateLimitDecision) -> None:
    response.headers["RateLimit-Limit"] = str(decision.limit)
    response.headers["RateLimit-Remaining"] = str(decision.remaining)
    response.headers["RateLimit-Reset"] = str(decision.reset_after_seconds)


def _security_headers(response, *, path: str) -> None:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = (
        "camera=(self), microphone=(self), geolocation=(), payment=(), usb=()"
    )
    if path in {"/", "/dashboard"} or path.startswith("/static/"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'self'; connect-src 'self' blob:; "
            "font-src 'self'; frame-ancestors 'none'; img-src 'self' data: blob:; "
            "media-src 'self' blob:; object-src 'none'; script-src 'self'; style-src 'self'"
        )
    if path.startswith("/v1/"):
        response.headers["Cache-Control"] = "no-store"
    if settings.environment.lower() == "production":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )


def create_app() -> FastAPI:
    app = FastAPI(title="MedGuard AI", version="0.1.0")
    app.state.rate_limiter = rate_limiter
    from app.core.accounts import AccountStore
    from app.api.accounts import router as accounts_router

    app.state.accounts = AccountStore()
    app.include_router(accounts_router, prefix="/v1")
    from app.api.knowledge_pool import router as knowledge_pool_router
    app.include_router(knowledge_pool_router)
    import os

    if os.getenv("MEDGUARD_ENVIRONMENT") == "production":
        from urllib.parse import urlsplit
        from starlette.middleware.trustedhost import TrustedHostMiddleware

        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=[urlsplit(os.environ["MEDGUARD_PUBLIC_ORIGIN"]).hostname],
        )

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        models_dir = static_dir / "models"
        if models_dir.exists():
            app.mount("/models", StaticFiles(directory=str(models_dir)), name="models")

    @app.get("/", include_in_schema=False)
    @app.get("/dashboard", include_in_schema=False)
    def dashboard() -> FileResponse:
        index_path = static_dir / "index.html"
        return FileResponse(str(index_path))

    app.include_router(router, prefix=f"/{settings.api_version}")

    @app.get("/metrics")
    def prometheus_metrics(request: Request) -> PlainTextResponse:
        if os.getenv("MEDGUARD_ENVIRONMENT") == "production":
            from app.core.accounts import reject

            user = request.app.state.accounts.authenticate(request)
            if user["role"] != "admin":
                reject("permission_denied", 403)
        return PlainTextResponse(metrics.render(), media_type="text/plain")

    @app.middleware("http")
    async def telemetry_middleware(request: Request, call_next):
        req_id = _request_id(request)
        request.state.request_id = req_id
        start = perf_counter()

        tenant_id = request.headers.get("X-Tenant-Id", "anonymous")
        path = request.url.path
        bucket = _rate_limit_bucket(path)
        decision: RateLimitDecision | None = None

        if settings.rate_limit_enabled and _should_rate_limit(path):
            client_host = request.client.host if request.client else "unknown"
            identity = (
                tenant_id
                if tenant_id in settings.allowed_tenants
                else f"client:{client_host}"
            )
            decision = await run_in_threadpool(
                request.app.state.rate_limiter.check,
                identity,
                bucket,
            )
            if not decision.available or not decision.allowed:
                status_code = 503 if not decision.available else 429
                error_code = (
                    "rate_limiter_unavailable"
                    if not decision.available
                    else "rate_limit_exceeded"
                )
                response = JSONResponse(
                    status_code=status_code,
                    content={
                        "error_code": error_code,
                        "message": (
                            "Request rate limiter is unavailable."
                            if not decision.available
                            else "Too many requests. Retry after the current window."
                        ),
                        "request_id": req_id,
                        "details": {
                            "retry_after_seconds": decision.reset_after_seconds
                        },
                    },
                )
                response.headers["X-Request-Id"] = req_id
                response.headers["Retry-After"] = str(decision.reset_after_seconds)
                _rate_limit_headers(response, decision)
                _security_headers(response, path=path)
                if settings.metrics_enabled:
                    metrics.inc_counter(
                        "medguard_rate_limit_rejections_total",
                        labels={"endpoint": bucket, "reason": error_code},
                    )
                    metrics.inc_counter(
                        "medguard_requests_total",
                        labels={
                            "tenant_id": tenant_id,
                            "endpoint": bucket,
                            "status": str(status_code),
                        },
                    )
                    metrics.observe_histogram(
                        "medguard_request_duration_seconds",
                        value=perf_counter() - start,
                        labels={"tenant_id": tenant_id, "endpoint": bucket},
                    )
                return response

        try:
            response = await call_next(request)
            duration = perf_counter() - start
            response.headers["X-Request-Id"] = req_id
            if decision is not None:
                _rate_limit_headers(response, decision)
            _security_headers(response, path=path)

            route = request.scope.get("route")
            endpoint = getattr(route, "path", bucket)

            if settings.metrics_enabled and path != "/metrics":
                metrics.inc_counter(
                    "medguard_requests_total",
                    labels={
                        "tenant_id": tenant_id,
                        "endpoint": endpoint,
                        "status": str(response.status_code),
                    },
                )
                metrics.observe_histogram(
                    "medguard_request_duration_seconds",
                    value=duration,
                    labels={"tenant_id": tenant_id, "endpoint": endpoint},
                )
            return response
        except Exception:
            if settings.metrics_enabled and path != "/metrics":
                metrics.inc_counter(
                    "medguard_requests_total",
                    labels={
                        "tenant_id": tenant_id,
                        "endpoint": bucket,
                        "status": "500",
                    },
                )
            raise

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content={
                "error_code": "invalid_payload",
                "message": "Request payload does not match the API schema.",
                "request_id": request.state.request_id,
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            error_code = detail.get("error_code", "http_error")
            details = {
                key: value for key, value in detail.items() if key != "error_code"
            }
            message = detail.get("message", error_code)
        else:
            error_code = str(detail)
            details = {}
            message = str(detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": error_code,
                "message": message,
                "request_id": request.state.request_id,
                "details": details,
            },
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def catch_all(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "internal_error",
                "message": "Internal server error.",
                "request_id": getattr(request.state, "request_id", "req_unknown"),
                "details": {"exception": exc.__class__.__name__},
            },
        )

    return app


app = create_app()
