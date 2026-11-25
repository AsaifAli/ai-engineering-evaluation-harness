"""Thread-safe in-process sliding-window quotas for harness write APIs.

Keep these limits inexpensive and dependency-free. Multi-instance production
deployments should enforce equivalent or stricter limits at the ingress too.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable


class SlidingWindowRateLimiter:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, *, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        limit = max(1, int(limit))
        window_seconds = max(1, int(window_seconds))
        now = self._clock()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, int(bucket[0] + window_seconds - now + 0.999))
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


rate_limiter = SlidingWindowRateLimiter()
