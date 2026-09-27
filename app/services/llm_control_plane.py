"""Risk, token, cache and request-coalescing controls for LLM calls."""

from __future__ import annotations

from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import hmac
import json
from math import ceil
import threading
from time import monotonic, sleep
from typing import Any, Callable, TypeVar

from app.core.config import settings
from app.core.observability import metrics
from app.models.chat import ChatIntent


Result = TypeVar("Result")


class RiskClass(str, Enum):
    SAFE_STATIC = "safe_static"
    SAFE_DYNAMIC = "safe_dynamic"
    PERSONALIZED = "personalized"
    CLINICAL_HIGH_RISK = "clinical_high_risk"


class CachePolicy(str, Enum):
    EXACT = "exact"
    NO_STORE = "no_store"


@dataclass(frozen=True)
class AgentRequestPolicy:
    risk_class: RiskClass
    cache_policy: CachePolicy
    verifier_required: bool
    single_flight: bool
    cache_ttl_seconds: int


@dataclass(frozen=True)
class GatewayRequestControls:
    role: str
    risk_class: str
    cache_policy: str
    max_input_tokens: int
    max_output_tokens: int
    estimated_input_tokens: int
    cache_ttl_seconds: int
    cache_namespace: str
    cache_scope: str
    end_user_scope: str
    session_scope: str
    prompt_version: str
    knowledge_version: str
    tool_result_version: str

    def cache_directives(self) -> dict[str, Any]:
        if self.cache_policy == CachePolicy.EXACT.value:
            return {
                "use-cache": True,
                "ttl": self.cache_ttl_seconds,
                "s-maxage": self.cache_ttl_seconds,
                "namespace": self.cache_namespace,
            }
        return {"no-cache": True, "no-store": True}

    def safe_metadata(self, request_id: str, stage: str) -> dict[str, str]:
        metadata = {
            "stage": stage[:64],
            "risk_class": self.risk_class,
            "cache_policy": self.cache_policy,
            "cache_scope": self.cache_scope,
            "prompt_version": self.prompt_version[:64],
            "knowledge_version_hash": _digest(self.knowledge_version),
            "tool_result_version": self.tool_result_version,
        }
        if self.cache_policy == CachePolicy.NO_STORE.value:
            metadata["request_id"] = request_id[:64]
        return metadata


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:24]


def _scope(value: str) -> str:
    return hmac.new(
        settings.secret_master_key.encode("utf-8"),
        value.encode("utf-8"),
        sha256,
    ).hexdigest()[:32]


def estimate_tokens(*values: Any) -> int:
    """Conservative tokenizer-independent estimate for the pre-call hard guard."""
    byte_count = sum(len(_canonical(value).encode("utf-8")) for value in values)
    return max(1, ceil(byte_count / 3))


def policy_for_intent(intent: ChatIntent) -> AgentRequestPolicy:
    if intent in {"triage", "safety", "monitoring", "general"}:
        return AgentRequestPolicy(
            risk_class=RiskClass.CLINICAL_HIGH_RISK,
            cache_policy=CachePolicy.NO_STORE,
            verifier_required=True,
            single_flight=False,
            cache_ttl_seconds=0,
        )
    if intent in {"followup", "pharmacy", "appointment_search"}:
        return AgentRequestPolicy(
            risk_class=RiskClass.PERSONALIZED,
            cache_policy=CachePolicy.NO_STORE,
            verifier_required=True,
            single_flight=False,
            cache_ttl_seconds=0,
        )
    if intent == "authenticity":
        return AgentRequestPolicy(
            risk_class=RiskClass.SAFE_DYNAMIC,
            cache_policy=CachePolicy.EXACT,
            verifier_required=True,
            single_flight=True,
            cache_ttl_seconds=settings.safe_cache_ttl_seconds,
        )
    return AgentRequestPolicy(
        risk_class=RiskClass.PERSONALIZED,
        cache_policy=CachePolicy.NO_STORE,
        verifier_required=True,
        single_flight=False,
        cache_ttl_seconds=0,
    )


def gateway_controls(
    *,
    role: str,
    policy: AgentRequestPolicy,
    tenant_id: str,
    conversation_id: str,
    locale: str,
    patient_context: dict[str, Any],
    prompt_version: str,
    knowledge_version: str,
    tool_result: Any,
    instructions: str,
    payload: dict[str, Any],
    max_input_tokens: int,
    max_output_tokens: int,
) -> GatewayRequestControls:
    context_hash = _scope(_canonical(patient_context))
    tool_hash = _scope(_canonical(tool_result))
    cache_material = _canonical(
        {
            "tenant": _scope(tenant_id),
            "conversation": _scope(conversation_id),
            "role": role,
            "locale": locale,
            "context": context_hash,
            "prompt": prompt_version,
            "knowledge": knowledge_version,
            "tool": tool_hash,
        }
    )
    return GatewayRequestControls(
        role=role,
        risk_class=policy.risk_class.value,
        cache_policy=policy.cache_policy.value,
        max_input_tokens=max_input_tokens,
        max_output_tokens=max_output_tokens,
        estimated_input_tokens=estimate_tokens(instructions, payload),
        cache_ttl_seconds=policy.cache_ttl_seconds,
        cache_namespace=f"medguard:{role}:{_digest(cache_material)}",
        cache_scope=_scope(cache_material),
        end_user_scope=_scope(f"tenant:{tenant_id}:conversation:{conversation_id}"),
        session_scope=_scope(f"tenant:{tenant_id}:session:{conversation_id}"),
        prompt_version=prompt_version,
        knowledge_version=knowledge_version,
        tool_result_version=tool_hash,
    )


def singleflight_key(
    *,
    tenant_id: str,
    conversation_id: str,
    locale: str,
    question: str,
    patient_context: dict[str, Any],
    tool_result: Any,
    prompt_version: str,
    knowledge_version: str,
) -> str:
    material = _canonical(
        {
            "tenant": _scope(tenant_id),
            "conversation": _scope(conversation_id),
            "locale": locale,
            "question": question,
            "context": patient_context,
            "tool": tool_result,
            "prompt": prompt_version,
            "knowledge": knowledge_version,
        }
    )
    return f"medguard:llm:flight:{_scope(material)}"


class SingleFlightCoordinator:
    """Coalesce exact-cache-safe calls locally and via a short Redis lock."""

    _RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""

    def __init__(self, redis_url: str | None, timeout_seconds: int, client: Any | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self._lock = threading.Lock()
        self._flights: dict[str, Future[Any]] = {}
        self._redis = client
        if redis_url and client is None:
            try:
                import redis

                candidate = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=1)
                candidate.ping()
                self._redis = candidate
            except Exception:
                self._redis = None

    def run(self, key: str, operation: Callable[[], Result]) -> Result:
        with self._lock:
            future = self._flights.get(key)
            if future is None:
                future = Future()
                self._flights[key] = future
                owner = True
            else:
                owner = False
        if not owner:
            metrics.inc_counter("medguard_llm_singleflight_total", labels={"outcome": "coalesced"})
            try:
                return future.result(timeout=self.timeout_seconds)
            except FutureTimeoutError:
                metrics.inc_counter("medguard_llm_singleflight_total", labels={"outcome": "timeout"})
                return operation()

        metrics.inc_counter("medguard_llm_singleflight_total", labels={"outcome": "owner"})
        try:
            result = self._run_distributed(key, operation)
            future.set_result(result)
            return result
        except BaseException as exc:
            future.set_exception(exc)
            raise
        finally:
            with self._lock:
                self._flights.pop(key, None)

    def _run_distributed(self, key: str, operation: Callable[[], Result]) -> Result:
        if self._redis is None:
            return operation()
        token = _scope(f"{threading.get_ident()}:{monotonic()}")
        deadline = monotonic() + self.timeout_seconds
        while monotonic() < deadline:
            try:
                acquired = self._redis.set(key, token, nx=True, ex=self.timeout_seconds)
            except Exception:
                metrics.inc_counter("medguard_llm_singleflight_total", labels={"outcome": "redis_unavailable"})
                self._redis = None
                return operation()
            if acquired:
                try:
                    return operation()
                finally:
                    try:
                        self._redis.eval(self._RELEASE_SCRIPT, 1, key, token)
                    except Exception:
                        metrics.inc_counter(
                            "medguard_llm_singleflight_total", labels={"outcome": "release_failed"}
                        )
            sleep(0.05)
        metrics.inc_counter("medguard_llm_singleflight_total", labels={"outcome": "timeout"})
        return operation()


singleflight = SingleFlightCoordinator(
    redis_url=settings.redis_url,
    timeout_seconds=settings.llm_singleflight_timeout_seconds,
)
