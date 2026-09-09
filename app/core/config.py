import json
from dataclasses import dataclass, field
from os import getenv


def _env_bool(name: str, default: bool = False) -> bool:
    value = getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"true", "1", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = getenv(name)
    return default if value is None else int(value)


def _env_float(name: str, default: float) -> float:
    value = getenv(name)
    return default if value is None else float(value)


def _allowed_tenants() -> tuple[str, ...]:
    value = getenv("MEDGUARD_ALLOWED_TENANTS")
    if not value:
        return ("tenant-demo", "tenant-alt")
    tenants = tuple(item.strip() for item in value.split(",") if item.strip())
    if not tenants:
        raise ValueError("MEDGUARD_ALLOWED_TENANTS must contain at least one tenant")
    return tenants


def _api_keys_by_tenant() -> dict[str, str]:
    value = getenv("MEDGUARD_API_KEYS_JSON")
    if not value:
        return {"tenant-demo": "demo-key", "tenant-alt": "alt-key"}
    parsed = json.loads(value)
    if not isinstance(parsed, dict) or not parsed:
        raise ValueError("MEDGUARD_API_KEYS_JSON must be a non-empty JSON object")
    result = {str(tenant): str(key) for tenant, key in parsed.items() if str(tenant) and str(key)}
    if len(result) != len(parsed):
        raise ValueError("MEDGUARD_API_KEYS_JSON contains an empty tenant or key")
    return result


@dataclass(frozen=True)
class Settings:
    service_name: str = "medguard-ai"
    environment: str = field(default_factory=lambda: getenv("MEDGUARD_ENVIRONMENT", "development"))
    api_version: str = "v1"
    request_timeout_seconds: int = 10
    idempotency_ttl_seconds: int = 24 * 60 * 60
    triage_low_confidence_threshold: float = 0.60
    prescription_match_threshold: float = 0.85
    prescription_line_review_threshold: float = 0.75
    circuit_error_threshold: float = 0.05
    circuit_min_requests: int = 5
    circuit_timeout_ms: int = 500
    prescription_max_image_bytes: int = 10 * 1024 * 1024

    # Security & multi-tenancy
    delivery_hmac_secret: str = field(
        default_factory=lambda: getenv("MEDGUARD_DELIVERY_HMAC_SECRET", "dev-delivery-secret")
    )
    allowed_tenants: tuple[str, ...] = field(default_factory=_allowed_tenants)
    api_keys_by_tenant: dict[str, str] = field(default_factory=_api_keys_by_tenant)
    secret_master_key: str = field(
        default_factory=lambda: getenv("MEDGUARD_SECRET_MASTER_KEY", "dev-master-key-32-chars-long!")
    )
    rate_limit_enabled: bool = field(
        default_factory=lambda: _env_bool("MEDGUARD_RATE_LIMIT_ENABLED", True)
    )
    rate_limit_requests: int = field(
        default_factory=lambda: _env_int("MEDGUARD_RATE_LIMIT_REQUESTS", 300)
    )
    rate_limit_window_seconds: int = field(
        default_factory=lambda: _env_int("MEDGUARD_RATE_LIMIT_WINDOW_SECONDS", 60)
    )

    # Database & RLS
    database_url: str | None = field(
        default_factory=lambda: getenv("MEDGUARD_DATABASE_URL")
    )
    sqlite_path: str = field(default_factory=lambda: getenv("MEDGUARD_SQLITE_PATH", ":memory:"))
    db_pool_size: int = field(default_factory=lambda: _env_int("MEDGUARD_DB_POOL_SIZE", 10))
    db_max_overflow: int = field(default_factory=lambda: _env_int("MEDGUARD_DB_MAX_OVERFLOW", 20))
    db_connect_timeout_seconds: int = field(
        default_factory=lambda: _env_int("MEDGUARD_DB_CONNECT_TIMEOUT_SECONDS", 5)
    )

    # Distributed Queue
    redis_url: str | None = field(
        default_factory=lambda: getenv("MEDGUARD_REDIS_URL")
    )
    queue_name: str = "medguard_jobs"
    queue_max_attempts: int = field(default_factory=lambda: _env_int("MEDGUARD_QUEUE_MAX_ATTEMPTS", 3))

    # Object Storage
    s3_endpoint_url: str | None = field(
        default_factory=lambda: getenv("MEDGUARD_S3_ENDPOINT")
    )
    s3_bucket_name: str = field(
        default_factory=lambda: getenv("MEDGUARD_S3_BUCKET", "medguard-prescriptions")
    )
    s3_access_key_id: str | None = field(
        default_factory=lambda: getenv("MEDGUARD_S3_ACCESS_KEY")
    )
    s3_secret_access_key: str | None = field(
        default_factory=lambda: getenv("MEDGUARD_S3_SECRET_KEY")
    )
    storage_retention_ttl_seconds: int = 3600  # Default 1h TTL ephemeral storage

    # Observability & Metrics
    metrics_enabled: bool = True
    log_level: str = field(
        default_factory=lambda: getenv("MEDGUARD_LOG_LEVEL", "INFO")
    )
    mask_clinical_data_in_logs: bool = True

    # Consent enforcement
    enforce_consent: bool = field(default_factory=lambda: _env_bool("MEDGUARD_ENFORCE_CONSENT"))

    # Optional two-agent answer presentation and verification
    agent_mode: str = field(default_factory=lambda: getenv("MEDGUARD_AGENT_MODE", "disabled").lower())
    research_agent_provider: str = field(
        default_factory=lambda: getenv("MEDGUARD_RESEARCH_AGENT_PROVIDER", "litellm").lower()
    )
    verifier_agent_provider: str = field(
        default_factory=lambda: getenv("MEDGUARD_VERIFIER_AGENT_PROVIDER", "litellm").lower()
    )
    agent_required_for_production: bool = field(
        default_factory=lambda: _env_bool("MEDGUARD_AGENT_REQUIRED_FOR_PRODUCTION")
    )
    llm_gateway_url: str | None = field(
        default_factory=lambda: (
            getenv("MEDGUARD_LLM_GATEWAY_URL", "").rstrip("/") or None
        )
    )
    llm_gateway_api_key: str | None = field(
        default_factory=lambda: getenv("MEDGUARD_LLM_GATEWAY_API_KEY")
    )
    llm_gateway_health_timeout_seconds: int = field(
        default_factory=lambda: _env_int("MEDGUARD_LLM_GATEWAY_HEALTH_TIMEOUT_SECONDS", 2)
    )
    research_agent_model: str | None = field(
        default_factory=lambda: getenv("MEDGUARD_RESEARCH_AGENT_MODEL", "medguard-answer")
    )
    verifier_agent_model: str | None = field(
        default_factory=lambda: getenv("MEDGUARD_VERIFIER_AGENT_MODEL", "medguard-verifier")
    )
    research_reasoning_effort: str = field(
        default_factory=lambda: getenv("MEDGUARD_RESEARCH_REASONING_EFFORT", "high").lower()
    )
    verifier_reasoning_effort: str = field(
        default_factory=lambda: getenv("MEDGUARD_VERIFIER_REASONING_EFFORT", "high").lower()
    )
    agent_timeout_seconds: int = field(
        default_factory=lambda: _env_int("MEDGUARD_AGENT_TIMEOUT_SECONDS", 15)
    )
    agent_max_input_tokens: int = field(
        default_factory=lambda: _env_int("MEDGUARD_AGENT_MAX_INPUT_TOKENS", 12_000)
    )
    research_max_output_tokens: int = field(
        default_factory=lambda: _env_int("MEDGUARD_RESEARCH_MAX_OUTPUT_TOKENS", 2_400)
    )
    verifier_max_output_tokens: int = field(
        default_factory=lambda: _env_int("MEDGUARD_VERIFIER_MAX_OUTPUT_TOKENS", 1_800)
    )
    agent_prompt_version: str = field(
        default_factory=lambda: getenv("MEDGUARD_AGENT_PROMPT_VERSION", "2026-09-09")
    )
    safe_cache_ttl_seconds: int = field(
        default_factory=lambda: _env_int("MEDGUARD_SAFE_CACHE_TTL_SECONDS", 300)
    )
    llm_singleflight_timeout_seconds: int = field(
        default_factory=lambda: _env_int("MEDGUARD_LLM_SINGLEFLIGHT_TIMEOUT_SECONDS", 50)
    )
    verifier_min_grounding: float = field(
        default_factory=lambda: _env_float("MEDGUARD_VERIFIER_MIN_GROUNDING", 0.90)
    )
    verifier_min_safety: float = field(
        default_factory=lambda: _env_float("MEDGUARD_VERIFIER_MIN_SAFETY", 0.95)
    )
    verifier_min_completeness: float = field(
        default_factory=lambda: _env_float("MEDGUARD_VERIFIER_MIN_COMPLETENESS", 0.85)
    )
    verifier_min_citation_coverage: float = field(
        default_factory=lambda: _env_float("MEDGUARD_VERIFIER_MIN_CITATION_COVERAGE", 0.90)
    )

    def __post_init__(self) -> None:
        if self.environment.lower() not in {"development", "test", "production"}:
            raise ValueError("MEDGUARD_ENVIRONMENT must be development, test, or production")
        if self.db_pool_size < 1:
            raise ValueError("MEDGUARD_DB_POOL_SIZE must be at least 1")
        if self.db_max_overflow < 0:
            raise ValueError("MEDGUARD_DB_MAX_OVERFLOW cannot be negative")
        if self.db_connect_timeout_seconds < 1:
            raise ValueError("MEDGUARD_DB_CONNECT_TIMEOUT_SECONDS must be at least 1")
        if self.queue_max_attempts < 1:
            raise ValueError("MEDGUARD_QUEUE_MAX_ATTEMPTS must be at least 1")
        if self.rate_limit_requests < 1:
            raise ValueError("MEDGUARD_RATE_LIMIT_REQUESTS must be at least 1")
        if self.rate_limit_window_seconds < 1:
            raise ValueError("MEDGUARD_RATE_LIMIT_WINDOW_SECONDS must be at least 1")
        if self.agent_mode not in {"disabled", "shadow", "enforced"}:
            raise ValueError("MEDGUARD_AGENT_MODE must be disabled, shadow, or enforced")
        if self.research_agent_provider != "litellm":
            raise ValueError("MEDGUARD_RESEARCH_AGENT_PROVIDER must be litellm")
        if self.verifier_agent_provider != "litellm":
            raise ValueError("MEDGUARD_VERIFIER_AGENT_PROVIDER must be litellm")
        if self.agent_timeout_seconds < 1:
            raise ValueError("MEDGUARD_AGENT_TIMEOUT_SECONDS must be at least 1")
        for name, value in {
            "MEDGUARD_AGENT_MAX_INPUT_TOKENS": self.agent_max_input_tokens,
            "MEDGUARD_RESEARCH_MAX_OUTPUT_TOKENS": self.research_max_output_tokens,
            "MEDGUARD_VERIFIER_MAX_OUTPUT_TOKENS": self.verifier_max_output_tokens,
            "MEDGUARD_SAFE_CACHE_TTL_SECONDS": self.safe_cache_ttl_seconds,
            "MEDGUARD_LLM_SINGLEFLIGHT_TIMEOUT_SECONDS": self.llm_singleflight_timeout_seconds,
        }.items():
            if value < 1:
                raise ValueError(f"{name} must be at least 1")
        if self.llm_gateway_health_timeout_seconds < 1:
            raise ValueError("MEDGUARD_LLM_GATEWAY_HEALTH_TIMEOUT_SECONDS must be at least 1")
        for name, value in {
            "MEDGUARD_RESEARCH_REASONING_EFFORT": self.research_reasoning_effort,
            "MEDGUARD_VERIFIER_REASONING_EFFORT": self.verifier_reasoning_effort,
        }.items():
            if value not in {"low", "medium", "high", "xhigh", "max"}:
                raise ValueError(f"{name} must be low, medium, high, xhigh, or max")
        for name, value in {
            "MEDGUARD_VERIFIER_MIN_GROUNDING": self.verifier_min_grounding,
            "MEDGUARD_VERIFIER_MIN_SAFETY": self.verifier_min_safety,
            "MEDGUARD_VERIFIER_MIN_COMPLETENESS": self.verifier_min_completeness,
            "MEDGUARD_VERIFIER_MIN_CITATION_COVERAGE": self.verifier_min_citation_coverage,
        }.items():
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")


settings = Settings()
