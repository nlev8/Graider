# Supabase Resilience Under Load — Implementation Plan (AS-SHIPPED)

> **Status:** SHIPPED on `feat/supabase-resilience`. This document is a post-execution reference — every code block matches what actually landed in the repo after Codex reviews, thread-safety fixes, and healthcheck corrections.
>
> **Original plan deviations are called out inline under "Plan correction" headings.** Read those to understand *why* the shipped code differs from the initial design.

**Goal:** Make every Supabase call in the backend automatically retry on transient failures, with an operation-aware retry policy that distinguishes idempotent operations from unsafe inserts, plus UUID-based idempotency for critical write paths.

**Architecture:** Wrap the singleton Supabase client in a thin proxy that intercepts every `.execute()` call, inspects `query.request.http_method` and the `Prefer` header to classify the operation, and applies the appropriate retry policy. For non-idempotent inserts (`POST` without `resolution=merge-duplicates`), retry only on connect-phase errors so committed writes are never double-applied. Critical inserts (student_submissions, published_assessments, submissions) are migrated to pass caller-generated UUIDs so that `upsert(..., on_conflict='id')` makes full retry safe even on response-phase failures.

**Tech Stack:** Python 3.14, `supabase-py` (wraps `postgrest-py` and `httpx`/`httpcore`), existing `backend/retry.py`, Flask + gunicorn

**Feature branch:** `feat/supabase-resilience`

---

## Scope summary

This plan covers Tier 1 #2 (Supabase connection resilience) from the district production reliability list. It does not cover:

- Monitoring / alerting (Tier 1 #3 — separate plan)
- Grading thread watchdog (Tier 1 #4 — separate plan; this plan does wrap the Supabase updates inside the thread)
- Rate limiting audit (Tier 2 — separate plan)

---

## Background findings

Verified before and during execution:

1. **`query.request.http_method` is reliably exposed** on the postgrest query builder. Confirmed by live inspection:
   - `select` → `GET`, no `Prefer` header
   - `insert` → `POST`, `Prefer: return=representation`
   - `upsert` → `POST`, `Prefer: return=representation,resolution=merge-duplicates`
   - `update` → `PATCH`, `Prefer: return=representation`
   - `delete` → `DELETE`, `Prefer: return=representation`

2. **`httpcore` exceptions do NOT subclass `OSError`, `ConnectionError`, or `TimeoutError`.** `httpcore.ConnectError`, `ReadError`, `WriteError`, etc. all inherit from `httpcore.NetworkError` → `Exception`. `httpcore.ConnectTimeout`, `ReadTimeout`, `WriteTimeout` inherit from `httpcore.TimeoutException` → `Exception`. `httpcore.ProtocolError` / `RemoteProtocolError` / `LocalProtocolError` inherit directly from `Exception`.
   - **Plan correction:** the original plan claimed `backend/retry.py::is_retryable_error()` would already catch these because "`httpcore.ReadError` is an `OSError` subclass". That was wrong. The shipped implementation adds a local `_is_supabase_retryable()` adapter in `backend/supabase_resilient.py` that catches `httpcore.NetworkError`, `httpcore.TimeoutException`, and `httpcore.ProtocolError` *in addition to* whatever `is_retryable_error()` already handles.

3. **~194 raw `.table().execute()` call sites** across route handlers are unprotected. Top offenders: `student_account_routes.py` (50), `student_portal_routes.py` (37), `admin_routes.py` (18), `roster_sync.py` (14), `clever_routes.py` (14).

4. **Two modules bypass the singleton entirely** and call `supabase.create_client()` directly: `backend/routes/behavior_routes.py` and `backend/services/assistant_tools_behavior.py`. Task 2.5 migrates both and adds a regression guard.

5. **Supabase client was a singleton** via `backend/supabase_client.py`. No thread safety. Task 2 adds an `RLock` to guard cold-start initialization.

6. **Grading thread** (`run_portal_grading_thread`) already imports `get_supabase()` from `backend.supabase_client`, so after Task 2 ships it automatically routes through the resilient wrapper for free.

7. **Existing `/healthz` had two bugs** discovered during Task 5:
   - Broken import path: `from supabase_client import get_supabase` (should be `backend.supabase_client`). The Supabase probe silently fell through to the `except` branch and never actually ran.
   - The original plan's fix (`with httpx.Client(timeout=3.0):`) was a **no-op** — it created and discarded an httpx client without passing it to supabase-py. **Plan correction:** the shipped healthcheck uses `httpx.get()` directly against the PostgREST REST API with a 3-second timeout.

---

## File Structure (as shipped)

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/supabase_resilient.py` | **Created** | `ResilientClient` proxy + operation classifier + `_is_supabase_retryable` adapter that handles httpcore exceptions. |
| `tests/test_supabase_resilient.py` | **Created** | 24 unit tests covering classification, preflight detection, retry behavior, proxy passthrough, rpc/schema wrapping, ProtocolError handling, and grading-thread PATCH retry. |
| `backend/supabase_client.py` | **Rewritten** | Adds `get_raw_supabase()` entry point. `get_supabase()` returns a `ResilientClient` wrapper. Thread-safe `RLock` guards singleton init. `get_supabase_or_raise()` names the specific missing env var. |
| `backend/routes/behavior_routes.py` | **Modified** | Removed `_supabase = None` module-level and `create_client()` call. `_get_supabase()` now delegates to `get_supabase_or_raise()`. |
| `backend/services/assistant_tools_behavior.py` | **Modified** | Same migration as behavior_routes.py. |
| `tests/test_no_direct_create_client.py` | **Created** | Regression guard. Fails the suite if any module outside `backend/supabase_client.py` re-introduces a direct `create_client()` call. |
| `backend/routes/student_account_routes.py` | **Modified** | `submit_student_work` and `save_submission_draft` insert → `upsert(..., on_conflict='id')` with caller-generated UUIDs. Added `import uuid`. |
| `backend/routes/student_portal_routes.py` | **Modified** | `publish_assessment` and join-code `submit_assessment` insert → `upsert(..., on_conflict='id')` with caller-generated UUIDs. Added `import uuid`. |
| `tests/test_integration_workflows.py` | **Modified** | Mechanical mock update — added `chain.upsert.return_value = insert_chain` alongside existing `chain.insert.return_value` so two integration tests survive the insert→upsert migration. No assertion logic changed. |
| `backend/app.py` | **Modified** | `/healthz` rewritten to use raw `httpx.get()` against the PostgREST REST API with a 3s timeout (fail fast, no retry). |
| `docs/supabase-resilience.md` | **Created** | Ops doc: retry policy table, UUID upsert pattern, opt-out via `get_raw_supabase()`, no-direct-`create_client` rule, retry budget, log labels. |

---

## Task 1: Create the ResilientClient proxy

**Files:**
- Create: `backend/supabase_resilient.py`
- Create: `tests/test_supabase_resilient.py`

### Step 1: Write failing tests

Create `tests/test_supabase_resilient.py`. The shipped file has 24 tests across 5 classes. Import this header:

```python
"""Tests for the resilient Supabase client wrapper."""

import pytest
from unittest.mock import MagicMock, patch
```

**TestOperationClassification** (6 tests): `test_select_returns_full`, `test_update_returns_full`, `test_delete_returns_full`, `test_upsert_returns_full`, `test_insert_returns_preflight_only`, `test_unknown_method_defaults_to_preflight`. Each creates a `MagicMock` with `q.request.http_method` and `q.request.headers` set, then asserts `_classify_operation(q)` returns the expected policy string.

**TestPreflightRetryFilter** (6 tests): `test_connect_error_is_preflight`, `test_connect_timeout_is_preflight`, `test_read_error_is_not_preflight`, `test_read_timeout_is_not_preflight`, `test_dns_oserror_is_preflight`, `test_protocol_error_is_not_preflight`. Each asserts `_is_preflight_error(err)` returns the expected bool.

> **Plan correction:** the original plan listed only 5 preflight tests. `test_protocol_error_is_not_preflight` was added after Codex review noted `httpcore.ProtocolError` slips past `_is_supabase_retryable` if it isn't explicitly handled. The test pins the contract that ProtocolError is retryable for upserts but NOT safe for raw inserts (server may have committed mid-stream).

**TestResilientExecute** (6 tests): `test_select_retries_on_oserror`, `test_insert_retries_connect_error`, `test_insert_does_not_retry_read_error`, `test_upsert_retries_read_error`, `test_non_retryable_error_propagates`, `test_upsert_retries_protocol_error`. Each builds a MagicMock `q`, sets `q.request.http_method` + `q.request.headers`, provides a `fake_execute` counter that raises N times then succeeds, patches `time.sleep`, and asserts the retry count matches.

> **Plan correction:** `test_upsert_retries_protocol_error` was added in the same post-review pass as the preflight test above.

**TestProxyBehavior** (5 tests): `test_table_returns_chainable_wrapper`, `test_non_postgrest_attrs_passthrough`, `test_rpc_returns_wrapped_builder`, `test_rpc_without_params`, `test_schema_returns_wrapped_sub_client`.

**TestGradingThreadResilience** (1 test): `test_update_retries_on_transient_read_error`. Lives in this file (not a separate file) because it tests the retry loop, not the grading thread itself. Added in Task 4.

See `tests/test_supabase_resilient.py` at commits `c47a3cf`, `2255db2`, and `7c7bb9c` for the full test source.

### Step 2: Run tests to verify they fail

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_supabase_resilient.py -v 2>&1 | tail -20
```

Expected: All tests FAIL with `ModuleNotFoundError: No module named 'backend.supabase_resilient'`.

### Step 3: Create `backend/supabase_resilient.py`

**Shipped source** (Python 3.14, 257 lines, commits `c47a3cf` + `2255db2`):

```python
"""Resilient Supabase client wrapper with operation-aware retry.

Wraps the singleton Supabase client so that every `.execute()` call is
automatically routed through `with_retry()` from backend.retry. The retry
policy is chosen per operation:

  - GET (select): full retry on any transient error
  - PATCH (update): full retry (idempotent — setting the same value twice is safe)
  - DELETE (delete): full retry (deleting an already-deleted row is a no-op)
  - POST with resolution=merge-duplicates (upsert): full retry (idempotent by design)
  - POST without resolution (raw insert): preflight-only retry
       We only retry on errors that occurred before any bytes reached the server
       (ConnectError, ConnectTimeout, DNS failures). For response-phase errors
       (ReadError, ReadTimeout, ProtocolError) we surface the exception because
       the server may already have committed the write — retrying would
       double-insert.

For critical writes that must remain safe under full retry even as raw inserts,
callers should generate their own UUID primary key and rely on the
schema-level UNIQUE constraint to reject duplicates. See
`docs/supabase-resilience.md` for the pattern.

Opt-out: callers that truly need the unwrapped client (e.g. for long-running
streaming queries) can import `get_raw_supabase()` from backend.supabase_client.
"""

import logging
import random
import time
from typing import Any

import httpcore

from backend.retry import (
    is_retryable_error,
    MAX_RETRIES,
    BASE_DELAY_S,
    MAX_DELAY_S,
    JITTER_FACTOR,
)

logger = logging.getLogger(__name__)


def _is_supabase_retryable(error: BaseException) -> bool:
    """Return True if *error* is a transient error worth retrying.

    Extends ``backend.retry.is_retryable_error`` to also recognise
    ``httpcore.NetworkError`` (ConnectError, ReadError, WriteError,
    ConnectTimeout, ReadTimeout, WriteTimeout, ProtocolError), which are
    what supabase-py surfaces when the underlying HTTP transport fails.
    ``httpcore`` exceptions do not subclass ``OSError``/``ConnectionError``,
    so the core retry helper does not catch them on its own.
    """
    if isinstance(error, (httpcore.NetworkError, httpcore.TimeoutException, httpcore.ProtocolError)):
        return True
    return is_retryable_error(error)


# ---------------------------------------------------------------------------
# Operation classification
# ---------------------------------------------------------------------------

def _classify_operation(query: Any) -> str:
    """Return the retry policy for a postgrest query builder.

    Returns one of:
      - "full"            — retry on any transient error
      - "preflight_only"  — retry only on connect-phase errors
    """
    try:
        method = query.request.http_method
        headers = query.request.headers or {}
    except AttributeError:
        # Unknown builder shape — be conservative
        return "preflight_only"

    prefer = headers.get("Prefer", "") or ""

    if method == "GET":
        return "full"
    if method in ("PATCH", "DELETE"):
        return "full"
    if method == "POST":
        if "resolution=merge-duplicates" in prefer:
            return "full"  # upsert
        return "preflight_only"  # raw insert
    return "preflight_only"


# ---------------------------------------------------------------------------
# Preflight error detection
# ---------------------------------------------------------------------------

# Errors that mean the request never reached the server (safe to retry even for inserts).
_PREFLIGHT_EXCEPTIONS = (
    httpcore.ConnectError,
    httpcore.ConnectTimeout,
)


def _is_preflight_error(error: BaseException) -> bool:
    """Return True if the error occurred before any bytes reached the server.

    This is the set of errors where retrying an insert is safe even without
    idempotency keys — the previous attempt never committed anything.
    """
    if isinstance(error, _PREFLIGHT_EXCEPTIONS):
        return True

    # DNS failures surface as OSError with errno -2 or -3 (gaierror on Linux/macOS)
    if isinstance(error, OSError):
        msg = str(error).lower()
        if "name or service not known" in msg:
            return True
        if "nodename nor servname" in msg:
            return True
        if "temporary failure in name resolution" in msg:
            return True

    return False


# ---------------------------------------------------------------------------
# Execute wrapper
# ---------------------------------------------------------------------------

def _resilient_execute(query: Any) -> Any:
    """Execute a postgrest query with operation-aware retry."""
    policy = _classify_operation(query)

    try:
        method = query.request.http_method.lower()
    except AttributeError:
        method = "unknown"

    if policy == "full":
        label = f"supabase-{method}"

        def _should_retry(exc: BaseException) -> bool:
            return _is_supabase_retryable(exc)
    else:
        label = f"supabase-{method}-preflight"

        def _should_retry(exc: BaseException) -> bool:
            # Raw inserts: only retry if the failure happened before any bytes
            # reached the server. Response-phase errors may indicate the write
            # was already committed and retrying would double-insert.
            return _is_supabase_retryable(exc) and _is_preflight_error(exc)

    last_error: BaseException | None = None
    for attempt in range(1, MAX_RETRIES + 2):  # 1 initial + MAX_RETRIES retries
        try:
            return query.execute()
        except Exception as exc:
            last_error = exc

            if not _should_retry(exc):
                raise

            if attempt > MAX_RETRIES:
                logger.error(
                    "[%s] All %d retries exhausted. Last error: %s",
                    label, MAX_RETRIES, exc,
                )
                raise

            base = BASE_DELAY_S * (2 ** (attempt - 1))
            base = min(base, MAX_DELAY_S)
            delay = base + random.random() * JITTER_FACTOR * base
            logger.warning(
                "[%s] Attempt %d/%d failed (%s). Retrying in %.2fs...",
                label, attempt, MAX_RETRIES + 1, exc, delay,
            )
            time.sleep(delay)

    raise last_error  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Proxy wrapper
# ---------------------------------------------------------------------------

class _ExecuteProxy:
    """Wraps a postgrest query builder so .execute() routes through retry."""

    def __init__(self, inner):
        self._inner = inner

    def execute(self):
        return _resilient_execute(self._inner)

    def __getattr__(self, name):
        result = getattr(self._inner, name)
        if callable(result):
            def wrapped(*args, **kwargs):
                sub = result(*args, **kwargs)
                # If the sub-result has a .execute, it's still a query builder — wrap it
                if hasattr(sub, "execute"):
                    return _ExecuteProxy(sub)
                return sub
            return wrapped
        return result


def _wrap_if_builder(obj):
    """Wrap any object that looks like a postgrest query builder.

    A builder is anything that exposes `.execute()` — direct table/from_ chains,
    rpc() results, and schema() sub-clients all satisfy this shape. Non-builder
    objects (auth, storage, realtime) are returned unchanged so their own
    APIs remain untouched.
    """
    if obj is None:
        return obj
    if hasattr(obj, "execute"):
        return _ExecuteProxy(obj)
    # schema() returns a SyncPostgrestClient whose .from_/.table/.rpc each
    # return builders — wrap the sub-client so those chains are proxied too.
    if hasattr(obj, "from_") or hasattr(obj, "table"):
        return ResilientClient(obj)
    return obj


class ResilientClient:
    """Proxies a Supabase client so every .execute() call goes through retry.

    Covers .table(), .from_(), .rpc(), and .schema() so that no entry point
    can reach `.execute()` without the retry wrapper. Non-postgrest attributes
    (auth, storage, realtime, functions) pass through unchanged.
    """

    def __init__(self, raw_client):
        self._raw = raw_client

    def table(self, name: str):
        return _ExecuteProxy(self._raw.table(name))

    def from_(self, name: str):
        return _ExecuteProxy(self._raw.from_(name))

    def rpc(self, fn: str, params=None):
        # supabase-py signature: rpc(fn, params=None)
        builder = self._raw.rpc(fn, params) if params is not None else self._raw.rpc(fn)
        return _wrap_if_builder(builder)

    def schema(self, name: str):
        sub_client = self._raw.schema(name)
        return _wrap_if_builder(sub_client)

    def __getattr__(self, name):
        # Pass through non-postgrest attributes (auth, storage, realtime, functions).
        # We deliberately do NOT auto-wrap here — these subsystems have their own
        # APIs and don't expose `.execute()`, so wrapping would be a no-op at best
        # and break their interfaces at worst.
        return getattr(self._raw, name)
```

> **Plan corrections captured in this file:**
>
> 1. **`_is_supabase_retryable()` adapter** — original plan tried to call `with_retry(query.execute, ...)` directly for the full path. That would have failed because `with_retry()` doesn't catch httpcore exceptions. The shipped code unifies the full and preflight paths through a single loop that uses `_is_supabase_retryable` (extended helper) and, for the preflight branch, *also* requires `_is_preflight_error`.
>
> 2. **Explicit `rpc()` and `schema()` wrapping** — original plan's `ResilientClient` only wrapped `.table()` and `.from_()`. Codex flagged that `.rpc()` / `.schema()` results still expose `.execute()` and would silently escape the wrapper. The shipped code adds explicit `rpc()` and `schema()` methods plus a `_wrap_if_builder()` helper that returns a nested `ResilientClient` for schema sub-clients.
>
> 3. **`httpcore.ProtocolError` in `_is_supabase_retryable`** — HTTP/2 stream resets can surface as `RemoteProtocolError` rather than `ReadError`. Added after Codex noted ProtocolError inherits directly from `Exception`, not `NetworkError`, so it would slip through an isinstance-on-`NetworkError` check alone.

### Step 4: Run tests to verify they pass

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_supabase_resilient.py -v 2>&1 | tail -30
```

Expected: All 24 tests PASS (23 from Tasks 1-3 plus the grading thread resilience test added in Task 4).

### Step 5: Commits

- `c47a3cf feat: add ResilientClient proxy with operation-aware retry`
- `2255db2 fix: retry httpcore.ProtocolError on idempotent operations`

---

## Task 2: Wire the resilient client into `get_supabase()`

**Files:**
- Modify: `backend/supabase_client.py`

### Step 1: Replace the full contents of `backend/supabase_client.py`

**Shipped source** (commits `4f07220` + `853874b`):

```python
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

from supabase import create_client, Client

_supabase_raw: Client = None
_supabase_resilient = None

# Guards cold-start singleton initialization across Flask request threads and
# background grading threads. The GIL makes attribute reads atomic, but the
# check-then-create pattern below is not — without the lock, two concurrent
# first calls can each construct a client and silently discard one.
# RLock (not Lock) because get_supabase() acquires the lock and then calls
# get_raw_supabase(), which acquires the same lock — a plain Lock would deadlock.
_init_lock = threading.RLock()


def get_raw_supabase() -> Client:
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
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_KEY')
        if url and key:
            _supabase_raw = create_client(url, key)
    return _supabase_raw


def get_supabase():
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


def get_supabase_or_raise():
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
```

> **Plan corrections captured in this file:**
>
> 1. **`threading.RLock`, not `threading.Lock`** — the original plan had no locking at all. The code reviewer flagged a cold-start race condition across Flask request threads and background grading threads. The first fix used a plain `Lock`, which deadlocked immediately: `get_supabase()` holds the lock and then calls `get_raw_supabase()`, which tries to re-acquire the same lock. `RLock` (reentrant) is the correct primitive.
>
> 2. **Named-missing-var error message** — `get_supabase_or_raise()` now builds a list of specifically which env var is missing (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, or both) instead of a generic "not configured" error. Added after the code reviewer flagged that partial misconfigurations were hard to diagnose.
>
> 3. **Two-path raise for the "set but still None" case** — if both env vars are set but the client is still None, the code raises a distinct error pointing to `create_client()` logs. This surfaces SDK-level init failures that would otherwise look like a generic misconfig.

### Step 2: Run the full backend test suite

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -10
```

Expected: All tests pass (~1026 as of Task 2). The wrapper should be fully transparent because `ResilientClient` forwards every call to the raw client.

### Step 3: Smoke test against live Supabase

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python3 -c "
from dotenv import load_dotenv; load_dotenv('.env', override=True)
from backend.supabase_client import get_supabase_or_raise, get_raw_supabase
db = get_supabase_or_raise()
print('Wrapper type:', type(db).__name__)
raw = get_raw_supabase()
print('Raw type:', type(raw).__name__)
result = db.table('classes').select('id, name').limit(1).execute()
print('rows:', len(result.data))
print('SUCCESS')
"
```

Expected: `Wrapper type: ResilientClient`, `Raw type: Client`, a row count, `SUCCESS`.

### Step 4: Commits

- `4f07220 feat: wire get_supabase() through ResilientClient wrapper`
- `853874b fix: thread-safe singleton init + precise env var error message`

---

## Task 2.5: Eliminate direct `create_client()` call sites

**Context:** Wrapping `get_supabase()` only protects modules that actually call it. Two modules bypass the singleton entirely and build their own raw Supabase client via `supabase.create_client(...)`, silently defeating retry protection for entire feature areas.

**Files:**
- Modify: `backend/routes/behavior_routes.py`
- Modify: `backend/services/assistant_tools_behavior.py`
- Create: `tests/test_no_direct_create_client.py`

### Step 1: Audit grep

```bash
cd /Users/alexc/Downloads/Graider && grep -rn "from supabase import create_client\|supabase.create_client\|create_client(" backend/ --include='*.py' | grep -v "backend/supabase_client.py"
```

Original offenders (2026-04-10):
- `backend/routes/behavior_routes.py` — lines 27-39 (original `_supabase = None` + `_get_supabase()` with direct `create_client()`)
- `backend/services/assistant_tools_behavior.py` — lines 29-42 (same pattern)

### Step 2: Migrate `behavior_routes.py`

**Shipped `_get_supabase()`** (replaces the old `_supabase = None` + direct-create-client pattern):

```python
def _get_supabase():
    """Return the canonical resilient Supabase client.

    Delegates to backend.supabase_client so all behavior calls route
    through ResilientClient and get automatic retry on transient failures.
    """
    from backend.supabase_client import get_supabase_or_raise
    return get_supabase_or_raise()
```

The module-level `_supabase = None` was removed because `get_supabase_or_raise()` has its own singleton. The lazy `from backend.supabase_client import get_supabase_or_raise` stays inside the function to avoid circular-import risk at module load time.

### Step 3: Migrate `assistant_tools_behavior.py`

Identical migration. `SETTINGS_FILE = os.path.expanduser(...)` is preserved. Only `_supabase = None` and the old `_get_supabase()` body are replaced with the snippet above (with its own docstring).

### Step 4: Create `tests/test_no_direct_create_client.py`

**Shipped source:**

```python
"""Regression guard: no module outside backend/supabase_client.py may call
supabase.create_client directly. All Supabase access must route through the
canonical get_supabase()/get_supabase_or_raise() helpers so the ResilientClient
wrapper is applied.
"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
ALLOWED = {BACKEND / "supabase_client.py"}


def _python_files():
    for path in BACKEND.rglob("*.py"):
        if path in ALLOWED:
            continue
        yield path


def test_no_direct_create_client_calls():
    offenders = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "create_client(" in text and "from supabase import" in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))
        elif "supabase.create_client(" in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))

    assert not offenders, (
        "Direct supabase.create_client() calls found outside "
        "backend/supabase_client.py. These bypass the ResilientClient "
        "wrapper and lose retry protection. Migrate them to "
        "backend.supabase_client.get_supabase() or get_supabase_or_raise():\n  - "
        + "\n  - ".join(offenders)
    )
```

### Step 5: Run the guard + full suite

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_no_direct_create_client.py -v
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -15
```

Expected: 1027 passing (was 1026 before the new guard).

### Step 6: Commit

- `10265c4 refactor: route all Supabase access through resilient singleton`

---

## Task 3: Migrate critical inserts to use caller-generated UUIDs

**Context:** With Task 2 shipped, all reads and idempotent writes are protected. Raw inserts only retry on connect-phase errors, which leaves a small gap: if a `POST /insert` gets a `ReadError` (server committed, response dropped), we surface the failure rather than double-insert. For the most critical tables, we close that gap by passing explicit UUIDs so the `on_conflict='id'` upsert path makes full retry safe.

**The 4 critical write paths:**

1. `backend/routes/student_account_routes.py::submit_student_work` → `student_submissions`
2. `backend/routes/student_account_routes.py::save_submission_draft` → `student_submissions`
3. `backend/routes/student_portal_routes.py::publish_assessment` → `published_assessments`
4. `backend/routes/student_portal_routes.py` join-code `submit_assessment` → `submissions`

**Files:**
- Modify: `backend/routes/student_account_routes.py` (2 sites + `import uuid`)
- Modify: `backend/routes/student_portal_routes.py` (2 sites + `import uuid`)
- Modify: `tests/test_integration_workflows.py` (mechanical mock update)

### Step 1: Audit target tables accept explicit UUIDs

Codex schema review confirmed all four target tables have `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` and no INSERT-only triggers that would misbehave under `ON CONFLICT DO UPDATE`:

- `student_submissions` (cloud_migration.sql:208, supabase_student_portal_schema.sql:82)
- `published_assessments` (cloud_migration.sql:14-17) — has `join_code VARCHAR(10) UNIQUE NOT NULL`; retries with the same UUID merge, genuine duplicates (different UUID, same join_code) still hit the UNIQUE constraint
- `submissions` (cloud_migration.sql:31-33) — `trigger_increment_submissions` fires `AFTER INSERT`, which Postgres intentionally skips on conflict-update, preventing counter inflation during retries

### Step 2: Migrate `submit_student_work` in `student_account_routes.py` (line ~822)

**Shipped:**

```python
        # Caller-generated UUID + upsert on id makes this retry-safe: if a
        # transient error drops the response after the server committed,
        # the retry merges-duplicates on the same id (no double-write).
        submission_row['id'] = str(uuid.uuid4())
        try:
            result = db.table('student_submissions').upsert(
                submission_row, on_conflict='id'
            ).execute()
        except Exception as insert_err:
            if '23505' in str(insert_err) or 'duplicate' in str(insert_err).lower():
                return jsonify({"error": "You have already submitted this assignment."}), 400
            raise
```

The `except` block is unchanged — 23505 duplicate detection still works because a fresh session generates a fresh UUID, so the upsert falls through to insert and the unique index on `(student_id, content_id, attempt_number)` fires.

### Step 3: Migrate `save_submission_draft` in `student_account_routes.py` (line ~1279)

**Shipped:**

```python
            db.table('student_submissions').upsert({
                'id': str(uuid.uuid4()),
                'student_id': student_id,
                'content_id': content_id,
                'student_name': (sdata.get('first_name', '') + ' ' + sdata.get('last_name', '')).strip(),
                'student_id_number': sdata.get('student_id_number'),
                'period': sdata.get('period'),
                'status': 'draft',
                'draft_answers': draft_answers,
                'question_times': question_times,
                'marked_for_review': marked_for_review,
                'time_started_at': now_iso,
            }, on_conflict='id').execute()
```

All 10 original draft fields preserved; only `id` is added and the call changes from `.insert(...).execute()` to `.upsert(..., on_conflict='id').execute()`.

### Step 4: Migrate `publish_assessment` in `student_portal_routes.py` (line ~258)

**Shipped:**

```python
        # Caller-generated UUID makes this retry-safe under full retry policy.
        result = db.table('published_assessments').upsert({
            "id": str(uuid.uuid4()),
            "join_code": join_code,
            "title": assessment.get('title', 'Untitled Assessment'),
            "assessment": assessment,
            "settings": db_settings,
            "teacher_id": g.teacher_id,
            "teacher_name": settings.get('teacher_name', 'Teacher'),
            "teacher_email": settings.get('teacher_email'),
            "is_active": True,
        }, on_conflict='id').execute()
```

### Step 5: Migrate `submit_assessment` (join-code path) in `student_portal_routes.py` (line ~778)

**Shipped:**

```python
        # Caller-generated UUID + upsert on id makes this retry-safe.
        submission_row['id'] = str(uuid.uuid4())
        try:
            submission_result = db.table('submissions').upsert(
                submission_row, on_conflict='id'
            ).execute()
        except Exception as insert_err:
            if '23505' in str(insert_err) or 'duplicate' in str(insert_err).lower():
                return jsonify({
                    "error": "You have already submitted this assessment.",
                }), 400
            raise
```

### Step 6: Add `import uuid` to both files

Add to the stdlib import section near the top of each file if not already present. Both files needed it added.

### Step 7: Fix integration test mocks (Plan correction)

> **Plan correction:** the original plan did not mention `tests/test_integration_workflows.py`. Two integration tests (`test_submit_mc_only_returns_score`, `test_publish_returns_join_code`) stubbed `.insert().execute()` on a MagicMock chain but nothing on `.upsert().execute()`. After the migration, those tests raised `TypeError: MagicMock not JSON serializable` because the code now reaches for `.upsert`. The fix is purely mechanical: wherever the test set `chain.insert.return_value = insert_chain`, add `chain.upsert.return_value = insert_chain` alongside it. No assertion logic is changed.

### Step 8: Run the full suite

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -10
```

Expected: 1027 passing.

### Step 9: Commit

- `c8d2c81 feat: use caller-generated UUIDs for critical inserts (idempotent retry)`

---

## Task 4: Ensure grading thread uses the resilient client

**Files:**
- Modify: `tests/test_supabase_resilient.py` (add TestGradingThreadResilience class)

The grading thread already calls `from backend.supabase_client import get_supabase` at three sites in `backend/services/portal_grading.py` (lines 234, 502, 547). After Task 2 ships, those calls return a `ResilientClient` automatically. **No code change needed in `portal_grading.py`.**

This task is verification-plus-test: add a unit test that pins the contract that a PATCH (the grading thread's update pattern) retries through `httpcore.ReadError` — exactly the failure mode seen in production today.

### Step 1: Append `TestGradingThreadResilience` to `tests/test_supabase_resilient.py`

**Shipped source** (appended as the last class in the file):

```python
class TestGradingThreadResilience:
    """End-to-end-ish test for retry behavior during background grading.

    The grading thread updates student_submissions.results via PATCH after
    multipass grading completes. Since PATCH is idempotent, it must retry
    through transient Supabase failures (including httpcore.ReadError from
    HTTP/2 stream resets) without surfacing an error to the grading worker.
    """

    def test_update_retries_on_transient_read_error(self):
        from backend.supabase_resilient import _resilient_execute
        from unittest.mock import MagicMock, patch
        import httpcore

        call_count = {"n": 0}
        q = MagicMock()
        q.request.http_method = "PATCH"
        q.request.headers = {"Prefer": "return=representation"}

        def fake_execute():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise httpcore.ReadError("server reset connection mid-update")
            return MagicMock(data=[{"id": "xxx", "results": {"score": 90}}])

        q.execute = fake_execute
        with patch("time.sleep"):
            result = _resilient_execute(q)
        assert call_count["n"] == 3
        assert result.data[0]["results"]["score"] == 90
```

### Step 2: Run the new test

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_supabase_resilient.py::TestGradingThreadResilience -v
```

Expected: 1 PASS. Total test file count is now 24.

### Step 3: Commit

- `7c7bb9c test: grading-thread PATCH retries through transient read errors`

---

## Task 5: Tighten healthcheck and write docs

**Files:**
- Modify: `backend/app.py` (just the `/healthz` route)
- Create: `docs/supabase-resilience.md`

### Step 1: Replace the `/healthz` Supabase probe

> **Plan correction:** the original plan's code used `with httpx.Client(timeout=3.0): raw.table('published_assessments').select('id').limit(1).execute()`. That was a **no-op** — the `httpx.Client(timeout=3.0)` context manager created and discarded a client without passing it to supabase-py. The supabase call ran with the default timeout. The shipped code bypasses supabase-py entirely and calls the PostgREST REST API directly with `httpx.get()`.
>
> **Also fixed:** the original `/healthz` had a broken import path (`from supabase_client import get_supabase` — missing the `backend.` prefix). The probe silently fell through to the `except` branch and never actually ran. The shipped code reads env vars directly without importing the supabase client module.

**Shipped `/healthz` probe block** (in `backend/app.py`, replaces the old Supabase try block):

```python
@app.route('/healthz')
def healthz():
    """General health check for Railway load balancer."""
    status = {"app": "ok"}
    # Supabase — raw httpx GET with a short timeout.
    # Deliberately bypasses ResilientClient: a healthcheck must fail fast,
    # not retry for 30s while the pod reports healthy. If this check fails
    # the pod should be marked degraded immediately so the orchestrator can
    # route around it.
    try:
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
        if not supabase_url or not supabase_key:
            status["supabase"] = "not configured"
        else:
            import httpx
            resp = httpx.get(
                f"{supabase_url.rstrip('/')}/rest/v1/published_assessments?select=id&limit=1",
                headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                },
                timeout=3.0,
            )
            if resp.status_code == 200:
                status["supabase"] = "ok"
            else:
                status["supabase"] = f"degraded (status {resp.status_code})"
    except Exception:
        status["supabase"] = "error"

    # Check Redis if configured
    try:
        redis_url = os.getenv('REDIS_URL')
        if redis_url:
            import redis
            r = redis.from_url(redis_url)
            r.ping()
            status["redis"] = "ok"
        else:
            status["redis"] = "not configured"
    except Exception:
        status["redis"] = "error"

    return jsonify(status)
```

Critical details:
- `timeout=3.0` on `httpx.get()` caps both connect and read phases
- URL format is Supabase PostgREST: `{SUPABASE_URL}/rest/v1/{table}?select={col}&limit={n}`
- Headers: `apikey` + `Authorization: Bearer` (Supabase service-role auth)
- No `get_supabase()`, no `ResilientClient`, no retry

### Step 2: Create `docs/supabase-resilience.md`

The full doc is at `docs/supabase-resilience.md` (commit `a6e3927`). Key sections:

- **What's retried automatically** — the policy table for GET/PATCH/DELETE/upsert/insert
- **When to use caller-generated UUIDs** — the Task 3 pattern, with code example and the list of current usages
- **How to opt out of retry** — `get_raw_supabase()` for streaming/healthchecks
- **Never bypass with `create_client()`** — points at the regression test from Task 2.5
- **Retry budget** — 5 retries, 0.5s → 32s exponential with ±25% jitter
- **Observability** — the log labels (`[supabase-get]`, `[supabase-patch]`, `[supabase-delete]`, `[supabase-post]`, `[supabase-insert-preflight]`)

### Step 3: Verify healthcheck with Flask test client

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python3 -c "
from dotenv import load_dotenv; load_dotenv('.env', override=True)
from backend.app import app
with app.test_client() as c:
    resp = c.get('/healthz')
    print('STATUS:', resp.status_code)
    print('BODY:', resp.get_json())
"
```

Expected: `STATUS: 200` and `BODY: {"app":"ok","redis":"not configured","supabase":"ok"}` (Redis status depends on env).

### Step 4: Run the full suite

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -15
```

Expected: 1028 passing.

### Step 5: Commit

- `a6e3927 feat: healthcheck fails fast via raw httpx + resilience docs`

---

## Task 6: Open PR and let CI verify

### Step 1: Push the branch

```bash
git push -u origin feat/supabase-resilience
```

### Step 2: Open a PR with auto-merge enabled

```bash
gh pr create --title "feat: Supabase resilience — operation-aware retry" --body "..."
gh pr merge --auto --squash
```

The PR will wait for CI (Backend Tests + Frontend Build) to pass, then squash-merge itself and delete the branch.

---

## Commit history (as shipped)

| # | SHA | Task | Summary |
|---|-----|------|---------|
| 1 | `c47a3cf` | 1 | add ResilientClient proxy with operation-aware retry |
| 2 | `2255db2` | 1 | retry httpcore.ProtocolError on idempotent operations |
| 3 | `4f07220` | 2 | wire get_supabase() through ResilientClient wrapper |
| 4 | `853874b` | 2 | thread-safe singleton init + precise env var error message |
| 5 | `10265c4` | 2.5 | route all Supabase access through resilient singleton |
| 6 | `c8d2c81` | 3 | use caller-generated UUIDs for critical inserts (idempotent retry) |
| 7 | `7c7bb9c` | 4 | grading-thread PATCH retries through transient read errors |
| 8 | `a6e3927` | 5 | healthcheck fails fast via raw httpx + resilience docs |

---

## Summary

| Task | Files changed | Risk | Shipped behaviour |
|---|---|---|---|
| 1 | new: `supabase_resilient.py`, test file | Low | Core proxy with `_is_supabase_retryable` httpcore adapter + explicit `rpc()`/`schema()` wrapping + ProtocolError coverage |
| 2 | `supabase_client.py` | Low → Medium | Wires the proxy in transparently with `RLock`-guarded singleton init and precise env-var errors |
| 2.5 | `behavior_routes.py`, `assistant_tools_behavior.py`, new regression test | Low | Kills the two direct `create_client()` offenders, adds a guard so future code cannot reintroduce them |
| 3 | 2 route files + 1 test file | Medium | UUID-based idempotency for 4 critical write sites; integration test mocks updated for insert→upsert |
| 4 | `test_supabase_resilient.py` only | None | Pins the PATCH-retry contract for the grading thread |
| 5 | `app.py` healthz + new docs | Low | Healthcheck now uses raw `httpx.get()` (3s timeout) against PostgREST directly — fails fast, no retry |
| 6 | none | None | Push + PR + auto-merge via CI |

**Before:** 194 raw `.table().execute()` calls in route handlers could each fail with an unretried `httpcore.ReadError` when Supabase's HTTP/2 connection pool drops. Two modules bypassed the singleton entirely. The healthcheck Supabase probe was silently broken.

**After:** Every Supabase call in the backend is automatically protected. Reads, updates, deletes, upserts retry on any transient failure including httpcore's exception hierarchy. Raw inserts retry conservatively on connect-phase errors. The 4 most critical insert paths upgrade to full-retry via caller-generated UUIDs. No module can bypass the wrapper via `create_client()` without breaking the build. Healthcheck fails fast in 3s. Full docs at `docs/supabase-resilience.md` and 24 unit tests pinning the retry contract.
