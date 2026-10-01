from scripts import test_gemini_stability as stability


def test_provider_readiness_passes_only_when_every_attempt_succeeds(monkeypatch) -> None:
    attempts = iter(
        [
            stability.Attempt(True, 0.4, 0, "HTTP 200; nonempty=true"),
            stability.Attempt(True, 0.5, 0, "HTTP 200; nonempty=true"),
            stability.Attempt(True, 0.6, 0, "HTTP 200; nonempty=true"),
        ]
    )
    monkeypatch.setattr(stability, "_with_retry", lambda fn: next(attempts))

    result = stability._run_series("writer", lambda: "ok", iterations=3, max_p95_s=30.0)

    assert result.status == "pass"
    assert result.application_ok
    assert result.success_count == 3


def test_provider_quota_exhaustion_is_external_degradation_not_application_failure(monkeypatch) -> None:
    attempts = iter(
        [
            stability.Attempt(True, 0.5, 0, "HTTP 200; nonempty=true"),
            stability.Attempt(False, 4.0, 2, "HTTP 429", http_status=429),
            stability.Attempt(False, 4.0, 2, "HTTP 429", http_status=429),
        ]
    )
    monkeypatch.setattr(stability, "_with_retry", lambda fn: next(attempts))

    result = stability._run_series("reviewer", lambda: "ok", iterations=3, max_p95_s=30.0)

    assert result.status == "degraded_external"
    assert result.application_ok
    assert result.failure_http_statuses == (429, 429)


def test_protocol_or_client_error_remains_a_hard_application_failure(monkeypatch) -> None:
    attempts = iter(
        [
            stability.Attempt(True, 0.5, 0, "HTTP 200; nonempty=true"),
            stability.Attempt(False, 0.2, 0, "HTTP 400", http_status=400),
            stability.Attempt(True, 0.6, 0, "HTTP 200; nonempty=true"),
        ]
    )
    monkeypatch.setattr(stability, "_with_retry", lambda fn: next(attempts))

    result = stability._run_series("reviewer", lambda: "ok", iterations=3, max_p95_s=30.0)

    assert result.status == "fail_application"
    assert not result.application_ok
