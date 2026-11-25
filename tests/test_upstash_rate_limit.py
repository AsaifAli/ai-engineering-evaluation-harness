import pytest

from app.rate_limit import AdaptiveRateLimiter, RateLimitBackendUnavailable


class FakeRedis:
    def __init__(self):
        self.counts = {}
        self.calls = []

    def eval(self, script, *, keys, args):
        self.calls.append((script, keys, args))
        key = keys[0]
        self.counts[key] = self.counts.get(key, 0) + 1
        return [self.counts[key], args[0]]


def test_production_quota_uses_shared_upstash_and_hashed_project_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://redis.example")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "test-token")
    limiter = AdaptiveRateLimiter()
    client = FakeRedis()
    limiter._client = client

    assert limiter.check("project-token:secret-token-fingerprint", limit=1) == (True, 60)
    assert limiter.check("project-token:secret-token-fingerprint", limit=1) == (False, 60)
    script, keys, args = client.calls[0]
    assert "INCR" in script and "EXPIRE" in script
    assert keys[0].startswith("harness:ratelimit:v1:")
    assert "secret-token-fingerprint" not in keys[0]
    assert args == [60]


def test_production_quota_fails_closed_without_upstash_credentials(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_TOKEN", raising=False)

    with pytest.raises(RateLimitBackendUnavailable):
        AdaptiveRateLimiter().check("write-ip:unknown", limit=1)
