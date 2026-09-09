from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.database import db_manager
from app.core.queue import job_queue
from app.core.rate_limit import rate_limiter
from app.core.storage import storage_manager
from app.knowledge.loader import knowledge
from app.models.health import ReadinessCheck, ReadinessResponse
from app.services.ocr.detector import text_detector
from app.services.ocr.recognizer import line_recognizer


_DEVELOPMENT_SECRETS = {
    "dev-delivery-secret",
    "dev-master-key-32-chars-long!",
}


def _knowledge_is_approved() -> bool:
    if not knowledge.files:
        return False
    for knowledge_file in knowledge.files.values():
        approved_by = str(knowledge_file.data.get("_meta", {}).get("approved_by", "")).strip()
        if not approved_by or "PENDING" in approved_by.upper():
            return False
    return True


def _llm_gateway_healthcheck() -> tuple[bool, str]:
    if not settings.llm_gateway_url or not settings.llm_gateway_api_key:
        return False, "gateway URL or virtual key is not configured"
    gateway_root = settings.llm_gateway_url.removesuffix("/v1")
    try:
        response = httpx.get(
            f"{gateway_root}/health/liveliness",
            headers={"Authorization": f"Bearer {settings.llm_gateway_api_key}"},
            timeout=settings.llm_gateway_health_timeout_seconds,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return False, "gateway liveliness check failed"
    return True, "gateway is reachable through the configured virtual key"


def build_readiness() -> ReadinessResponse:
    knowledge_approved = _knowledge_is_approved()
    probe_tenant = settings.allowed_tenants[0] if settings.allowed_tenants else "readiness"
    database_healthy, database_detail = db_manager.healthcheck(probe_tenant)
    tenant_configuration_valid = set(settings.allowed_tenants) == set(
        settings.api_keys_by_tenant
    )
    development_credentials = any(
        key in {"demo-key", "alt-key"} for key in settings.api_keys_by_tenant.values()
    )
    agents_configured = bool(
        settings.llm_gateway_url
        and settings.llm_gateway_api_key
        and settings.research_agent_model
        and settings.verifier_agent_model
    )
    agents_active = settings.agent_mode in {"shadow", "enforced"}
    gateway_healthy, gateway_detail = (
        _llm_gateway_healthcheck() if agents_active and agents_configured else (False, "gateway not probed")
    )
    if (
        agents_active
        and agents_configured
        and gateway_healthy
        and (settings.agent_mode == "enforced" or not settings.agent_required_for_production)
    ):
        agent_status = "pass"
        agent_detail = f"mode={settings.agent_mode}; gateway=healthy; both roles are configured"
    elif agents_active and agents_configured and gateway_healthy and settings.agent_mode == "shadow":
        agent_status = "fail" if settings.agent_required_for_production else "warn"
        agent_detail = "gateway is healthy but shadow mode cannot satisfy the production release gate"
    elif agents_active and agents_configured:
        agent_status = "fail"
        agent_detail = gateway_detail
    elif settings.agent_required_for_production or agents_active:
        agent_status = "fail"
        agent_detail = f"mode={settings.agent_mode}; gateway virtual key or model aliases are incomplete"
    else:
        agent_status = "warn"
        agent_detail = "answer research and independent verification are disabled; deterministic presenter remains active"
    checks = [
        ReadinessCheck(
            name="database",
            status="pass" if db_manager.is_postgres and database_healthy else "fail",
            detail=database_detail,
        ),
        ReadinessCheck(
            name="queue",
            status="pass" if job_queue.is_durable and job_queue.is_healthy else "fail",
            detail=(
                f"active backend: {job_queue.backend_name}; "
                f"pending={job_queue.queue_depth()} processing={job_queue.processing_depth()} "
                f"dead_letter={job_queue.dead_letter_depth()}"
            ),
        ),
        ReadinessCheck(
            name="object_storage",
            status="pass" if storage_manager.is_durable and storage_manager.is_healthy else "fail",
            detail=f"active backend: {storage_manager.backend_name}",
        ),
        ReadinessCheck(
            name="ocr_engines",
            status=(
                "pass"
                if text_detector.is_real_engine_available and line_recognizer.is_real_engine_available
                else "fail"
            ),
            detail=(
                "detector and recognizer are available"
                if text_detector.is_real_engine_available and line_recognizer.is_real_engine_available
                else "detector or recognizer is unavailable; OCR fails closed"
            ),
        ),
        ReadinessCheck(
            name="clinical_knowledge_approval",
            status="pass" if knowledge_approved else "fail",
            detail="all knowledge snapshots approved" if knowledge_approved else "one or more snapshots are pending approval",
        ),
        ReadinessCheck(
            name="production_secrets",
            status=(
                "fail"
                if settings.delivery_hmac_secret in _DEVELOPMENT_SECRETS
                or settings.secret_master_key in _DEVELOPMENT_SECRETS
                else "pass"
            ),
            detail=(
                "development defaults are active"
                if settings.delivery_hmac_secret in _DEVELOPMENT_SECRETS
                or settings.secret_master_key in _DEVELOPMENT_SECRETS
                else "external secrets are configured"
            ),
        ),
        ReadinessCheck(
            name="tenant_credentials",
            status="fail" if development_credentials or not tenant_configuration_valid else "pass",
            detail=(
                "allowed tenants and API key tenants do not match"
                if not tenant_configuration_valid
                else "development API keys are active"
                if development_credentials
                else "external tenant credentials are configured"
            ),
        ),
        ReadinessCheck(
            name="consent_enforcement",
            status="pass" if settings.enforce_consent else "fail",
            detail="consent evidence is required" if settings.enforce_consent else "consent bypass is active in development",
        ),
        ReadinessCheck(
            name="rate_limiting",
            status=(
                "pass"
                if rate_limiter.is_distributed and rate_limiter.is_healthy
                else "fail"
            ),
            detail=(
                f"active backend: {rate_limiter.backend_name}; "
                f"limit={settings.rate_limit_requests}/{settings.rate_limit_window_seconds}s"
            ),
        ),
        ReadinessCheck(
            name="answer_agents",
            status=agent_status,
            detail=agent_detail,
            required_for_production=settings.agent_required_for_production,
        ),
    ]
    production_ready = all(
        check.status == "pass" for check in checks if check.required_for_production
    )
    return ReadinessResponse(
        status="ready" if production_ready else "degraded",
        service=settings.service_name,
        environment=settings.environment,
        production_ready=production_ready,
        checks=checks,
    )
