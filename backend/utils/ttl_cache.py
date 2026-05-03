"""
Tiny thread-safe in-process TTL cache.

Used for short-window memoization of expensive read endpoints (e.g. the
class progress-rank grid, where re-aggregating thousands of submissions
on every poll is wasteful when the underlying data changes infrequently
on a teacher-dashboard cadence).

Not meant to replace a proper materialized view or Redis cache — those
arrive in a follow-up. This is the 5%-effort fix that buys 80% of the
perf headroom while the materialized rollup design is built.

Process-local: each Railway worker has its own cache. Acceptable for a
short TTL (≤60s) where cache divergence is bounded by the TTL itself.
"""
from __future__ import annotations

import threading
import time
from typing import Any


class TTLCache:
    """Thread-safe TTL cache. Keys are arbitrary hashables.

    Lazy expiry: stale entries are evicted on the next get() / set() that
    touches them. There is no background reaper. For a small dashboard
    cache this is fine; for high-cardinality keys add a periodic prune
    or migrate to Redis.
    """

    def __init__(self, ttl_seconds: float):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        self._ttl = float(ttl_seconds)
        self._store: dict[Any, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: Any) -> Any:
        """Return the cached value, or None if missing / expired.

        Note: None is also a valid stored value in principle. Callers that
        need to distinguish "absent" from "explicitly cached None" should
        use a sentinel — this cache is not used that way today.
        """
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at < now:
                # Lazy expiry
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: Any, value: Any) -> None:
        """Store value at key with a fresh TTL window."""
        expires_at = time.monotonic() + self._ttl
        with self._lock:
            self._store[key] = (expires_at, value)

    def invalidate(self, key: Any) -> None:
        """Drop a single key. No-op if missing."""
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Drop everything. Useful in tests."""
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
