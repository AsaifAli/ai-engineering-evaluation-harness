"""Shared Upstash write quotas with a local-only development fallback."""
from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any


class RateLimitBackendUnavailable(RuntimeError):
    """Production shared rate-limit storage is unavailable."""


class SlidingWindowRateLimiter:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, *, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        safe_limit = max(1, int(limit))
        safe_window = max(1, int(window_seconds))
        now = self._clock()
        cutoff = now - safe_window
        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= safe_limit:
                retry_after = max(1, int(bucket[0] + safe_window - now + 0.999))
                return False, retry_after
            bucket.append(now)
            if len(self._buckets) > 20_000:
                stale = [name for name, events in self._buckets.items() if not events or events[-1] <= cutoff]
                for name in stale[:5_000]:
                    self._buckets.pop(name, None)
            return True, 0

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()


_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
local ttl = redis.call('TTL', KEYS[1])
if count == 1 or ttl < 0 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
  ttl = tonumber(ARGV[1])
end
return {count, ttl}
"""


class AdaptiveRateLimiter:
    def __init__(self) -> None:
        self._memory = SlidingWindowRateLimiter()
        self._client: Any | None = None
        self._lock = threading.Lock()

    def _production(self) -> bool:
        return (
            os.getenv("APP_ENV", "").strip().lower() in {"prod", "production"}
            or os.getenv("RENDER", "").strip().lower() in {"1", "true"}
        )

    def _upstash_client(self):
        url = os.getenv("UPSTASH_REDIS_REST_URL", "").strip()
        token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "").strip()
        if not url or not token:
            raise RateLimitBackendUnavailable("Upstash rate-limit credentials are not configured.")
        with self._lock:
            if self._client is None:
                try:
                    from upstash_redis import Redis
                    self._client = Redis(url=url, token=token, rest_retries=0, allow_telemetry=False)
                except Exception as exc:
                    raise RateLimitBackendUnavailable from exc
        return self._client

    def check(self, key: str, *, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        if not self._production():
            return self._memory.check(key, limit=limit, window_seconds=window_seconds)
        try:
            digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
            redis_key = f"harness:ratelimit:v1:{digest}"
            result = self._upstash_client().eval(
                _SCRIPT,
                keys=[redis_key],
                args=[max(1, int(window_seconds))],
            )
            count, ttl = int(result[0]), int(result[1] or window_seconds)
            return count <= max(1, int(limit)), max(1, ttl)
        except RateLimitBackendUnavailable:
            raise
        except Exception as exc:
            raise RateLimitBackendUnavailable from exc

    def clear(self) -> None:
        self._memory.clear()


rate_limiter = AdaptiveRateLimiter()
