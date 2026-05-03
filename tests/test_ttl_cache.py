"""Tests for backend.utils.ttl_cache.TTLCache."""
import threading
import time

import pytest

from backend.utils.ttl_cache import TTLCache


def test_set_and_get_within_ttl():
    cache = TTLCache(ttl_seconds=5)
    cache.set("k", "v")
    assert cache.get("k") == "v"


def test_get_missing_key_returns_none():
    cache = TTLCache(ttl_seconds=5)
    assert cache.get("absent") is None


def test_expired_entry_returns_none():
    cache = TTLCache(ttl_seconds=0.05)  # 50 ms
    cache.set("k", "v")
    time.sleep(0.1)
    assert cache.get("k") is None


def test_expired_entry_is_evicted_lazily():
    cache = TTLCache(ttl_seconds=0.05)
    cache.set("k", "v")
    time.sleep(0.1)
    cache.get("k")  # triggers lazy eviction
    assert len(cache) == 0


def test_set_refreshes_ttl_window():
    cache = TTLCache(ttl_seconds=0.1)
    cache.set("k", "v1")
    time.sleep(0.05)
    cache.set("k", "v2")  # refresh
    time.sleep(0.07)  # total 0.12s since first set, but only 0.07s since refresh
    assert cache.get("k") == "v2"


def test_invalidate_drops_key():
    cache = TTLCache(ttl_seconds=5)
    cache.set("k", "v")
    cache.invalidate("k")
    assert cache.get("k") is None


def test_invalidate_missing_is_noop():
    cache = TTLCache(ttl_seconds=5)
    cache.invalidate("absent")  # should not raise


def test_clear_drops_everything():
    cache = TTLCache(ttl_seconds=5)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    assert len(cache) == 0
    assert cache.get("a") is None


def test_zero_ttl_rejected():
    with pytest.raises(ValueError):
        TTLCache(ttl_seconds=0)


def test_negative_ttl_rejected():
    with pytest.raises(ValueError):
        TTLCache(ttl_seconds=-1)


def test_concurrent_access_does_not_corrupt():
    cache = TTLCache(ttl_seconds=5)
    iterations = 200

    def worker(i):
        for j in range(iterations):
            cache.set(f"k-{i}-{j}", j)
            cache.get(f"k-{i}-{j}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All entries written, none lost. (Sanity check, not strict ordering.)
    assert len(cache) == 8 * iterations


def test_tuple_keys_supported():
    cache = TTLCache(ttl_seconds=5)
    cache.set(("teacher-1", "class-1", "latest"), {"foo": "bar"})
    assert cache.get(("teacher-1", "class-1", "latest")) == {"foo": "bar"}
    assert cache.get(("teacher-1", "class-1", "best")) is None
