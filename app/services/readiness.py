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
from app.services.circuit import CircuitState, model_circuit


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
    if not agents_active or not agents_configured:
        gateway_status = "fail" if settings.agent_required_for_production else "warn"
        gateway_detail = "gateway not required by the active deterministic execution policy"
    else:
        gateway_status = "pass" if gateway_healthy else "fail"

    circuit = model_circuit.snapshot()
    if circuit.total_requests == 0:
        contract_status = "fail" if settings.agent_required_for_production else "warn"
        contract_detail = "gateway transport may be live, but no writer+verifier contract has completed in this process"
    elif circuit.state != CircuitState.CLOSED or circuit.failure_count:
        contract_status = "fail"
        contract_detail = (
            f"writer+verifier contract is unhealthy: state={circuit.state}; "
            f"failures={circuit.failure_count}/{circuit.total_requests}"
        )
    else:
        contract_status = "pass"
        contract_detail = f"writer+verifier contract completed successfully; runs={circuit.total_requests}"

    execution_enabled = settings.agent_sync_enabled or settings.agent_background_enabled
    if not agents_active or not execution_enabled:
        agent_status = "fail" if settings.agent_required_for_production else "warn"
        agent_detail = (
            f"mode={settings.agent_mode}; synchronous and background model execution are disabled; "
            "patient answers use the deterministic clinical path"
        )
    elif settings.agent_sync_enabled:
        agent_status = "pass" if settings.agent_mode == "enforced" and contract_status == "pass" else "fail"
        agent_detail = (
            f"mode={settings.agent_mode}; execution=synchronous; release requires a proven writer+verifier contract"
        )
    else:
        agent_status = "fail" if settings.agent_required_for_production else "pass"
        agent_detail = (
            f"mode={settings.agent_mode}; execution=queued-background; patient responses do not wait for Ollama; "
            f"verified_promotion={str(settings.agent_background_promote_verified).lower()}"
        )

    coverage_configured = (
        settings.agent_coverage_scope == "all"
        and agents_active
        and execution_enabled
    )
    synchronous_release = (
        coverage_configured
        and settings.agent_mode == "enforced"
        and settings.agent_sync_enabled
    )
    background_admission = coverage_configured and settings.agent_background_enabled
    if settings.agent_required_for_production:
        coverage_status = "pass" if synchronous_release else "fail"
    else:
        coverage_status = "pass" if synchronous_release or background_admission else "warn"
    if synchronous_release:
        coverage_detail = (
            "scope=all; enforced synchronous execution attempts the gateway before every public response; "
            "per-response verification_status still reports timeout, rejection, or provider failure"
        )
    elif coverage_configured and settings.agent_background_enabled:
        promotion_detail = (
            "verified results may update durable history"
            if settings.agent_background_promote_verified
            else "results are observability-only"
        )
        coverage_detail = (
            "scope=all; every admitted response is queued for background gateway review; "
            f"{promotion_detail}; queued work is not durable across process restarts"
        )
    else:
        coverage_detail = (
            f"scope={settings.agent_coverage_scope}; mode={settings.agent_mode}; "
            "not every public response is submitted to the gateway"
        )
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
            name="llm_gateway_transport",
            status=gateway_status,
            detail=gateway_detail,
            required_for_production=settings.agent_required_for_production,
        ),
        ReadinessCheck(
            name="llm_model_contract",
            status=contract_status,
            detail=contract_detail,
            required_for_production=settings.agent_required_for_production,
        ),
        ReadinessCheck(
            name="answer_agents",
            status=agent_status,
            detail=agent_detail,
            required_for_production=settings.agent_required_for_production,
        ),
        ReadinessCheck(
            name="gateway_response_coverage",
            status=coverage_status,
            detail=coverage_detail,
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
