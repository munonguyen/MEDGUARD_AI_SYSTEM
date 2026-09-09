from fastapi.testclient import TestClient

from app.core.rate_limit import InMemoryRateLimiter, RateLimitManager, RedisRateLimiter
from app.main import create_app


class MutableClock:
    def __init__(self, value: float = 1_000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


class FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.keys: list[str] = []

    def ping(self) -> bool:
        return True

    def eval(self, _script, _key_count, key, window_seconds):
        self.keys.append(key)
        self.counts[key] = self.counts.get(key, 0) + 1
        return [self.counts[key], int(window_seconds)]


def test_in_memory_rate_limit_resets_and_isolates_buckets():
    clock = MutableClock()
    limiter = InMemoryRateLimiter(limit=2, window_seconds=10, clock=clock)

    first = limiter.check("tenant-a", "/v1/triage")
    second = limiter.check("tenant-a", "/v1/triage")
    rejected = limiter.check("tenant-a", "/v1/triage")
    isolated = limiter.check("tenant-b", "/v1/triage")

    assert first.allowed is True and first.remaining == 1
    assert second.allowed is True and second.remaining == 0
    assert rejected.allowed is False and rejected.reset_after_seconds == 10
    assert isolated.allowed is True and isolated.remaining == 1

    clock.value += 10
    reset = limiter.check("tenant-a", "/v1/triage")
    assert reset.allowed is True and reset.remaining == 1


def test_unknown_api_paths_share_one_bounded_bucket():
    app = create_app()
    app.state.rate_limiter = InMemoryRateLimiter(limit=1, window_seconds=60)

    with TestClient(app) as client:
        first = client.get("/v1/not-a-real-route-a")
        second = client.get("/v1/not-a-real-route-b")

    assert first.status_code == 404
    assert second.status_code == 429


def test_redis_rate_limit_is_atomic_and_does_not_expose_identity_in_key():
    redis = FakeRedis()
    limiter = RedisRateLimiter(
        "redis://unused",
        limit=1,
        window_seconds=30,
        client=redis,
    )

    assert limiter.check("hospital-sensitive", "/v1/triage").allowed is True
    assert limiter.check("hospital-sensitive", "/v1/triage").allowed is False
    assert redis.keys[0] == redis.keys[1]
    assert "hospital-sensitive" not in redis.keys[0]


def test_production_rate_limit_fails_closed_without_distributed_backend():
    manager = RateLimitManager(
        environment="production",
        enabled=True,
        redis_url=None,
        limit=10,
        window_seconds=60,
    )

    decision = manager.check("hospital-a", "/v1/triage")
    assert decision.allowed is False
    assert decision.available is False
    assert manager.backend_name == "unavailable"


def test_http_rate_limit_and_security_headers():
    app = create_app()
    app.state.rate_limiter = InMemoryRateLimiter(limit=2, window_seconds=60)

    with TestClient(app) as client:
        first = client.get("/v1/models", headers={"X-Request-Id": "rate-test-1"})
        second = client.get("/v1/models", headers={"X-Request-Id": "rate-test-2"})
        rejected = client.get("/v1/models", headers={"X-Request-Id": "rate-test-3"})

        assert first.status_code == 200
        assert first.headers["RateLimit-Remaining"] == "1"
        assert first.headers["Cache-Control"] == "no-store"
        assert first.headers["X-Content-Type-Options"] == "nosniff"
        assert second.status_code == 200
        assert second.headers["RateLimit-Remaining"] == "0"
        assert rejected.status_code == 429
        assert rejected.json()["error_code"] == "rate_limit_exceeded"
        assert rejected.json()["request_id"] == "rate-test-3"
        assert rejected.headers["Retry-After"] == "60"

        for _ in range(4):
            assert client.get("/v1/health").status_code == 200

        dashboard = client.get("/")
        assert dashboard.status_code == 200
        assert "default-src 'self'" in dashboard.headers["Content-Security-Policy"]
        assert dashboard.headers["X-Frame-Options"] == "DENY"


def test_invalid_request_id_is_replaced():
    app = create_app()
    app.state.rate_limiter = InMemoryRateLimiter(limit=2, window_seconds=60)

    with TestClient(app) as client:
        response = client.get("/v1/models", headers={"X-Request-Id": "not valid"})

    assert response.status_code == 200
    assert response.headers["X-Request-Id"].startswith("req_")
    assert response.headers["X-Request-Id"] != "not valid"
