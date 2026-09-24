from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading
from time import sleep

from app.services.llm_control_plane import (
    CachePolicy,
    SingleFlightCoordinator,
    gateway_controls,
    policy_for_intent,
    singleflight_key,
)


def _controls(**updates):
    values = {
        "role": "answer",
        "policy": policy_for_intent("authenticity"),
        "tenant_id": "hospital-secret",
        "conversation_id": "conversation-secret",
        "locale": "vi-VN",
        "patient_context": {"patient_ref": "patient-secret", "allergies": ["penicillin"]},
        "prompt_version": "prompt-v1",
        "knowledge_version": "knowledge-v1",
        "tool_result": {"status": "registry_match"},
        "instructions": "Use only approved claims.",
        "payload": {"question": "verify QR"},
        "max_input_tokens": 12000,
        "max_output_tokens": 2400,
    }
    values.update(updates)
    return gateway_controls(**values)


def test_clinical_policy_is_no_store_and_requires_verifier():
    for intent in ("triage", "safety", "monitoring", "followup", "pharmacy"):
        policy = policy_for_intent(intent)  # type: ignore[arg-type]
        assert policy.cache_policy is CachePolicy.NO_STORE
        assert policy.verifier_required is True
        assert policy.single_flight is False


def test_registry_policy_uses_bounded_exact_cache_and_singleflight():
    policy = policy_for_intent("authenticity")
    controls = _controls(policy=policy)

    assert policy.cache_policy is CachePolicy.EXACT
    assert policy.verifier_required is True
    assert policy.single_flight is True
    assert controls.cache_directives() == {
        "use-cache": True,
        "ttl": policy.cache_ttl_seconds,
        "s-maxage": policy.cache_ttl_seconds,
        "namespace": controls.cache_namespace,
    }


def test_unlisted_business_intent_fails_closed_instead_of_inheriting_faq_cache():
    policy = policy_for_intent("delivery")

    assert policy.cache_policy is CachePolicy.NO_STORE
    assert policy.verifier_required is True
    assert policy.single_flight is False


def test_cache_scope_isolated_by_context_versions_and_contains_no_identity():
    baseline = _controls()
    variants = (
        _controls(tenant_id="other-hospital"),
        _controls(patient_context={"patient_ref": "other-patient"}),
        _controls(prompt_version="prompt-v2"),
        _controls(knowledge_version="knowledge-v2"),
        _controls(tool_result={"status": "recalled"}),
    )

    assert all(item.cache_scope != baseline.cache_scope for item in variants)
    serialized = " ".join(
        (baseline.cache_namespace, baseline.cache_scope, baseline.end_user_scope, baseline.session_scope)
    )
    for secret in ("hospital-secret", "conversation-secret", "patient-secret", "penicillin"):
        assert secret not in serialized


def test_singleflight_key_changes_with_knowledge_and_never_contains_question():
    values = {
        "tenant_id": "tenant-sensitive",
        "conversation_id": "conversation-sensitive",
        "locale": "vi-VN",
        "question": "nội dung riêng tư",
        "patient_context": {"patient_ref": "patient-sensitive"},
        "tool_result": {"state": "unknown"},
        "prompt_version": "prompt-v1",
        "knowledge_version": "knowledge-v1",
    }
    first = singleflight_key(**values)
    second = singleflight_key(**{**values, "knowledge_version": "knowledge-v2"})

    assert first != second
    assert "nội dung riêng tư" not in first
    assert "tenant-sensitive" not in first
    assert "patient-sensitive" not in first


def test_process_singleflight_executes_one_operation_for_concurrent_callers():
    coordinator = SingleFlightCoordinator(redis_url=None, timeout_seconds=2)
    barrier = threading.Barrier(8)
    lock = threading.Lock()
    call_count = 0

    def operation():
        nonlocal call_count
        with lock:
            call_count += 1
        sleep(0.05)
        return {"answer": "verified"}

    def call():
        barrier.wait()
        return coordinator.run("same-safe-key", operation)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _index: call(), range(8)))

    assert call_count == 1
    assert results == [{"answer": "verified"}] * 8


def test_singleflight_redis_failure_degrades_to_direct_operation():
    class FailingRedis:
        def set(self, *_args, **_kwargs):
            raise ConnectionError("redis unavailable")

    coordinator = SingleFlightCoordinator(
        redis_url="redis://unused",
        timeout_seconds=2,
        client=FailingRedis(),
    )
    calls = 0

    def operation():
        nonlocal calls
        calls += 1
        return "deterministic-result"

    assert coordinator.run("safe-key", operation) == "deterministic-result"
    assert calls == 1
