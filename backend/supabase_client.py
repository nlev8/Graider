"""
Canonical Supabase client for Graider.
All modules should import from here instead of creating their own clients.

Provides three variants:
  - get_supabase()          → returns resilient client or None (lenient, for optional features)
  - get_supabase_or_raise() → returns resilient client or raises Exception (strict, for required features)
  - get_raw_supabase()      → returns the unwrapped raw client (opt-out for streaming / custom retry / healthchecks)

Default for new code: get_supabase() / get_supabase_or_raise(). Only reach for
get_raw_supabase() when you specifically need to bypass the retry wrapper.
"""
import os
import threading
from typing import Any

from supabase import create_client

# supabase.Client is untyped upstream (postgrest-py has no stubs); we use Any
# for the singleton variables so strict mypy doesn't reject `None` assignments.
_supabase_raw: Any = None
_supabase_resilient: Any = None

# Guards cold-start singleton initialization across Flask request threads and
# background grading threads. The GIL makes attribute reads atomic, but the
# check-then-create pattern below is not — without the lock, two concurrent
# first calls can each construct a client and silently discard one.
# RLock (not Lock) because get_supabase() acquires the lock and then calls
# get_raw_supabase(), which acquires the same lock — a plain Lock would deadlock.
_init_lock = threading.RLock()


def _fake_supabase_enabled() -> bool:
    """Test-only hook: GRAIDER_FAKE_SUPABASE=1 swaps in the in-memory fake.

    Added for hardening sprint PR5 (e2e de-skip wave 1): the `Frontend E2E
    Extended` CI job spawns the real backend with this flag so the join-code
    publish/take/results flow runs hermetically without a live Supabase
    project (backend/testing/fake_supabase.py).

    Fail-closed: outside dev/test FLASK_ENV values this RAISES instead of
    activating — a leaked flag on a production service must crash the boot
    loudly, never silently serve fake data.
    """
    if os.getenv('GRAIDER_FAKE_SUPABASE') != '1':
        return False
    flask_env = (os.getenv('FLASK_ENV') or '').lower()
    if flask_env not in ('development', 'dev', 'testing', 'test'):
        raise RuntimeError(
            "GRAIDER_FAKE_SUPABASE=1 is a test-only hook and requires "
            f"FLASK_ENV=development/testing (got {flask_env!r}). Refusing to "
            "fake the database outside dev/test."
        )
    return True


def get_raw_supabase() -> Any:  # returns supabase.Client — untyped upstream
    """Lazy-init raw Supabase admin client WITHOUT retry wrapping.

    Use this only when you need the underlying client — e.g. for long-running
    streaming queries, custom retry logic, or healthchecks that must fail fast.
    Most callers should use get_supabase() or get_supabase_or_raise() instead.
    """
    global _supabase_raw
    if _supabase_raw is not None:
        return _supabase_raw
    with _init_lock:
        # Double-check: another thread may have initialized while we waited.
        if _supabase_raw is not None:
            return _supabase_raw
        # Test-only e2e hook — checked BEFORE real credentials so a dev
        # .env with a live SUPABASE_URL can't defeat the fake flag.
        if _fake_supabase_enabled():
            from backend.testing.fake_supabase import get_fake_supabase
            _supabase_raw = get_fake_supabase()
            return _supabase_raw
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_KEY')
        if url and key:
            _supabase_raw = create_client(url, key)
    return _supabase_raw


def get_supabase() -> Any:  # returns ResilientClient | None — postgrest-py is untyped upstream
    """Lazy-init Supabase admin client with automatic retry wrapping.

    Returns a ResilientClient instance (behaves like the raw client but
    every .execute() call is routed through operation-aware retry), or None
    if not configured.
    """
    global _supabase_resilient
    if _supabase_resilient is not None:
        return _supabase_resilient
    with _init_lock:
        if _supabase_resilient is not None:
            return _supabase_resilient
        raw = get_raw_supabase()
        if raw is not None:
            from backend.supabase_resilient import ResilientClient
            _supabase_resilient = ResilientClient(raw)
    return _supabase_resilient


def get_supabase_or_raise() -> Any:  # returns ResilientClient — raises if not configured
    """Lazy-init resilient Supabase client. Raises if not configured.

    Names the specific missing env var so misconfigurations are easy to diagnose.
    """
    client = get_supabase()
    if client is not None:
        return client

    # Identify which var is missing so the error message is actionable.
    missing = []
    if not os.getenv('SUPABASE_URL'):
        missing.append('SUPABASE_URL')
    if not os.getenv('SUPABASE_SERVICE_KEY'):
        missing.append('SUPABASE_SERVICE_KEY')
    if missing:
        raise Exception(
            f"Supabase credentials not configured. Missing: {', '.join(missing)}. "
            "Check your .env file."
        )
    # Both env vars are set but client still None — something else went wrong.
    raise Exception(
        "Supabase client initialization failed despite SUPABASE_URL and "
        "SUPABASE_SERVICE_KEY being set. Check logs for create_client() errors."
    )
