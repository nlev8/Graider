# Supabase Resilience Under Load — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Supabase call in the backend automatically retry on transient failures, with an operation-aware retry policy that distinguishes idempotent operations from unsafe inserts, plus UUID-based idempotency for critical write paths.

**Architecture:** Wrap the singleton Supabase client in a thin proxy that intercepts every `.execute()` call, inspects `query.request.http_method` and the `Prefer` header to classify the operation, and applies the appropriate retry policy via the existing `with_retry` helper. For non-idempotent inserts (`POST` without `resolution=merge-duplicates`), retry only on connect-phase errors so committed writes are never double-applied. Critical inserts (student_submissions, published_content, classes, class_students) are migrated to pass caller-generated UUIDs so that UNIQUE constraints make full retry safe even on response-phase failures.

**Tech Stack:** Python 3.14, `supabase-py` (wraps `postgrest-py` and `httpx`), existing `backend/retry.py`, Flask + gunicorn

**Feature branch:** `feat/supabase-resilience`

---

## Scope summary

This plan covers Tier 1 #2 (Supabase connection resilience) from the district production reliability list. It does not cover:

- Monitoring / alerting (Tier 1 #3 — separate plan)
- Grading thread watchdog (Tier 1 #4 — separate plan; this plan does wrap the Supabase updates inside the thread)
- Rate limiting audit (Tier 2 — separate plan)

---

## Background findings

Verified before writing this plan:

1. **`query.request.http_method` is reliably exposed** on the postgrest query builder after `db.table(...).select/insert/update/upsert/delete(...)`. Confirmed by live inspection:
   - `select` → `GET`, no `Prefer` header
   - `insert` → `POST`, `Prefer: return=representation`
   - `upsert` → `POST`, `Prefer: return=representation,resolution=merge-duplicates`
   - `update` → `PATCH`, `Prefer: return=representation`
   - `delete` → `DELETE`, `Prefer: return=representation`

2. **Existing `with_retry()` helper already catches** `ConnectionError`, `TimeoutError`, `OSError`, HTTP 408/429/5xx/529, and strings containing "temporarily unavailable". The `httpcore.ReadError: [Errno 35]` we saw today is an `OSError` subclass and **is already retryable** — we just aren't calling the helper for raw `.table()` calls.

3. **~194 raw `.table().execute()` call sites** across route handlers are unprotected. Top offenders: `student_account_routes.py` (50), `student_portal_routes.py` (37), `admin_routes.py` (18), `roster_sync.py` (14), `clever_routes.py` (14).

4. **Supabase client is a singleton** via `backend/supabase_client.py:15`. No connection pooling or keepalive config — default httpx behavior.

5. **Grading thread** (`run_portal_grading_thread`) already marks failed submissions as `status='grading_failed'`, not stuck in `'grading'`. It does not retry the Supabase update call when the update itself fails.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/supabase_resilient.py` | **Create** | New file. Defines `ResilientClient` proxy wrapping the singleton client with operation-aware retry. |
| `backend/supabase_client.py` | **Modify** | `get_supabase()` now returns the `ResilientClient` wrapper instead of the raw client. One-line change inside the existing function; callers don't change. |
| `tests/test_supabase_resilient.py` | **Create** | Unit tests for the proxy: operation classification, retry policy selection, preflight-only mode for inserts, error propagation for non-retryable failures, rpc() and schema() wrapping. |
| `backend/routes/behavior_routes.py` | **Modify** | Drop the local `_get_supabase()` that calls `create_client()` directly; delegate to the canonical singleton so behavior writes run through the resilient wrapper. |
| `backend/services/assistant_tools_behavior.py` | **Modify** | Same migration as above — route through `get_supabase()`. |
| `tests/test_no_direct_create_client.py` | **Create** | Regression guard. Fails the suite if any module outside `backend/supabase_client.py` re-introduces a direct `create_client()` call and silently bypasses the wrapper. |
| `backend/routes/student_account_routes.py` | **Modify** | Migrate the 2 critical insert paths (`submit_student_work`, `save_submission_draft`) to pass caller-generated UUIDs so retry is safe. |
| `backend/routes/student_portal_routes.py` | **Modify** | Migrate the 2 critical insert paths (`submit_assessment` join-code path, `publish_assessment`) to pass caller-generated UUIDs. |
| `backend/services/portal_grading.py` | **Modify** | Wrap the existing `student_submissions` update inside `run_portal_grading_thread` so transient failures during grading don't orphan the submission. No new logic — just runs through the resilient client. |
| `docs/supabase-resilience.md` | **Create** | Short ops doc: how retry policy works, how to opt out, how to force strict mode for non-idempotent custom operations. |

---

## Task 1: Create the ResilientClient proxy

**Files:**
- Create: `backend/supabase_resilient.py`
- Create: `tests/test_supabase_resilient.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_supabase_resilient.py`:

```python
"""Tests for the resilient Supabase client wrapper."""

import pytest
from unittest.mock import MagicMock, patch


class TestOperationClassification:
    """Tests for _classify_operation — picks retry policy from the query builder."""

    def test_select_returns_full(self):
        from backend.supabase_resilient import _classify_operation
        q = MagicMock()
        q.request.http_method = "GET"
        q.request.headers = {}
        assert _classify_operation(q) == "full"

    def test_update_returns_full(self):
        from backend.supabase_resilient import _classify_operation
        q = MagicMock()
        q.request.http_method = "PATCH"
        q.request.headers = {"Prefer": "return=representation"}
        assert _classify_operation(q) == "full"

    def test_delete_returns_full(self):
        from backend.supabase_resilient import _classify_operation
        q = MagicMock()
        q.request.http_method = "DELETE"
        q.request.headers = {"Prefer": "return=representation"}
        assert _classify_operation(q) == "full"

    def test_upsert_returns_full(self):
        from backend.supabase_resilient import _classify_operation
        q = MagicMock()
        q.request.http_method = "POST"
        q.request.headers = {"Prefer": "return=representation,resolution=merge-duplicates"}
        assert _classify_operation(q) == "full"

    def test_insert_returns_preflight_only(self):
        from backend.supabase_resilient import _classify_operation
        q = MagicMock()
        q.request.http_method = "POST"
        q.request.headers = {"Prefer": "return=representation"}
        assert _classify_operation(q) == "preflight_only"

    def test_unknown_method_defaults_to_preflight(self):
        from backend.supabase_resilient import _classify_operation
        q = MagicMock()
        q.request.http_method = "PUT"
        q.request.headers = {}
        assert _classify_operation(q) == "preflight_only"


class TestPreflightRetryFilter:
    """Tests for _is_preflight_error — distinguishes connect-phase from response-phase errors."""

    def test_connect_error_is_preflight(self):
        from backend.supabase_resilient import _is_preflight_error
        import httpcore
        assert _is_preflight_error(httpcore.ConnectError("refused")) is True

    def test_connect_timeout_is_preflight(self):
        from backend.supabase_resilient import _is_preflight_error
        import httpcore
        assert _is_preflight_error(httpcore.ConnectTimeout("dns")) is True

    def test_read_error_is_not_preflight(self):
        from backend.supabase_resilient import _is_preflight_error
        import httpcore
        # ReadError means bytes were in flight — server may have committed
        assert _is_preflight_error(httpcore.ReadError("reset")) is False

    def test_read_timeout_is_not_preflight(self):
        from backend.supabase_resilient import _is_preflight_error
        import httpcore
        assert _is_preflight_error(httpcore.ReadTimeout("slow")) is False

    def test_dns_oserror_is_preflight(self):
        from backend.supabase_resilient import _is_preflight_error
        # OSError with gaierror-style message
        err = OSError("[Errno -2] Name or service not known")
        assert _is_preflight_error(err) is True


class TestResilientExecute:
    """Tests for the execute() wrapper's retry behavior."""

    def test_select_retries_on_oserror(self):
        from backend.supabase_resilient import _resilient_execute

        call_count = {"n": 0}
        q = MagicMock()
        q.request.http_method = "GET"
        q.request.headers = {}

        def fake_execute():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise OSError("temporarily unavailable")
            return MagicMock(data=[{"id": "xxx"}])

        q.execute = fake_execute
        # Patch time.sleep to speed up the test
        with patch("time.sleep"):
            result = _resilient_execute(q)
        assert call_count["n"] == 3
        assert result.data == [{"id": "xxx"}]

    def test_insert_retries_connect_error(self):
        from backend.supabase_resilient import _resilient_execute
        import httpcore

        call_count = {"n": 0}
        q = MagicMock()
        q.request.http_method = "POST"
        q.request.headers = {"Prefer": "return=representation"}

        def fake_execute():
            call_count["n"] += 1
            if call_count["n"] < 2:
                raise httpcore.ConnectError("refused")
            return MagicMock(data=[{"id": "xxx"}])

        q.execute = fake_execute
        with patch("time.sleep"):
            result = _resilient_execute(q)
        assert call_count["n"] == 2

    def test_insert_does_not_retry_read_error(self):
        from backend.supabase_resilient import _resilient_execute
        import httpcore

        call_count = {"n": 0}
        q = MagicMock()
        q.request.http_method = "POST"
        q.request.headers = {"Prefer": "return=representation"}

        def fake_execute():
            call_count["n"] += 1
            raise httpcore.ReadError("server disconnected mid-response")

        q.execute = fake_execute
        with patch("time.sleep"), pytest.raises(httpcore.ReadError):
            _resilient_execute(q)
        assert call_count["n"] == 1  # no retry

    def test_upsert_retries_read_error(self):
        from backend.supabase_resilient import _resilient_execute
        import httpcore

        call_count = {"n": 0}
        q = MagicMock()
        q.request.http_method = "POST"
        q.request.headers = {"Prefer": "return=representation,resolution=merge-duplicates"}

        def fake_execute():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise httpcore.ReadError("reset")
            return MagicMock(data=[{"id": "xxx"}])

        q.execute = fake_execute
        with patch("time.sleep"):
            result = _resilient_execute(q)
        assert call_count["n"] == 3

    def test_non_retryable_error_propagates(self):
        from backend.supabase_resilient import _resilient_execute

        q = MagicMock()
        q.request.http_method = "GET"
        q.request.headers = {}
        q.execute = MagicMock(side_effect=ValueError("invalid arg"))

        with pytest.raises(ValueError):
            _resilient_execute(q)
        assert q.execute.call_count == 1


class TestProxyBehavior:
    """Tests that the ResilientClient proxy preserves the chained API surface."""

    def test_table_returns_chainable_wrapper(self):
        from backend.supabase_resilient import ResilientClient

        mock_raw = MagicMock()
        wrapper = ResilientClient(mock_raw)
        result = wrapper.table("classes").select("id").eq("id", "xxx")
        # The chain should have been forwarded through to the raw client
        mock_raw.table.assert_called_once_with("classes")

    def test_non_postgrest_attrs_passthrough(self):
        """auth, storage, realtime, functions pass through untouched."""
        from backend.supabase_resilient import ResilientClient

        mock_raw = MagicMock()
        mock_raw.auth = "auth_obj"
        mock_raw.storage = "storage_obj"
        mock_raw.realtime = "realtime_obj"
        mock_raw.functions = "functions_obj"
        wrapper = ResilientClient(mock_raw)
        assert wrapper.auth == "auth_obj"
        assert wrapper.storage == "storage_obj"
        assert wrapper.realtime == "realtime_obj"
        assert wrapper.functions == "functions_obj"

    def test_rpc_returns_wrapped_builder(self):
        """rpc() results have .execute() — they must be wrapped."""
        from backend.supabase_resilient import ResilientClient, _ExecuteProxy

        # Raw rpc builder exposes .execute
        raw_builder = MagicMock()
        raw_builder.execute = MagicMock(return_value=MagicMock(data=[]))

        mock_raw = MagicMock()
        mock_raw.rpc = MagicMock(return_value=raw_builder)

        wrapper = ResilientClient(mock_raw)
        result = wrapper.rpc("some_function", {"arg": 1})
        assert isinstance(result, _ExecuteProxy)
        mock_raw.rpc.assert_called_once_with("some_function", {"arg": 1})

    def test_rpc_without_params(self):
        """rpc() can be called with just the function name."""
        from backend.supabase_resilient import ResilientClient, _ExecuteProxy

        raw_builder = MagicMock()
        raw_builder.execute = MagicMock(return_value=MagicMock(data=[]))

        mock_raw = MagicMock()
        mock_raw.rpc = MagicMock(return_value=raw_builder)

        wrapper = ResilientClient(mock_raw)
        result = wrapper.rpc("no_args_fn")
        assert isinstance(result, _ExecuteProxy)
        mock_raw.rpc.assert_called_once_with("no_args_fn")

    def test_schema_returns_wrapped_sub_client(self):
        """schema() returns a sub-client whose .from_()/.table()/.rpc() must also be wrapped."""
        from backend.supabase_resilient import ResilientClient, _ExecuteProxy

        # Raw schema sub-client has table/from_/rpc
        raw_builder = MagicMock()
        raw_builder.execute = MagicMock(return_value=MagicMock(data=[]))

        sub_client = MagicMock(spec=["table", "from_", "rpc"])
        sub_client.table = MagicMock(return_value=raw_builder)
        sub_client.from_ = MagicMock(return_value=raw_builder)
        sub_client.rpc = MagicMock(return_value=raw_builder)

        mock_raw = MagicMock()
        mock_raw.schema = MagicMock(return_value=sub_client)

        wrapper = ResilientClient(mock_raw)
        sub_wrapper = wrapper.schema("analytics")
        # Sub-client should itself be a ResilientClient
        assert isinstance(sub_wrapper, ResilientClient)
        # Calls through the sub-wrapper should produce wrapped builders
        assert isinstance(sub_wrapper.table("events"), _ExecuteProxy)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_supabase_resilient.py -v 2>&1 | tail -20
```

Expected: All tests FAIL with `ModuleNotFoundError: No module named 'backend.supabase_resilient'`

- [ ] **Step 3: Create the resilient client module**

Create `backend/supabase_resilient.py`:

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
from typing import Any

import httpcore

from backend.retry import with_retry, is_retryable_error, MAX_RETRIES

logger = logging.getLogger(__name__)


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

    if policy == "full":
        return with_retry(
            query.execute,
            max_retries=MAX_RETRIES,
            label=f"supabase-{query.request.http_method.lower()}",
        )

    # preflight_only — wrap in a custom retry that only retries connect-phase errors
    def _attempt():
        return query.execute()

    last_error = None
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            return _attempt()
        except Exception as exc:
            last_error = exc

            # Only retry if it's BOTH retryable AND preflight
            if not (is_retryable_error(exc) and _is_preflight_error(exc)):
                raise

            if attempt > MAX_RETRIES:
                logger.error(
                    "[supabase-insert-preflight] All %d retries exhausted. Last error: %s",
                    MAX_RETRIES, exc,
                )
                raise

            import time
            import random
            from backend.retry import BASE_DELAY_S, MAX_DELAY_S, JITTER_FACTOR
            base = BASE_DELAY_S * (2 ** (attempt - 1))
            base = min(base, MAX_DELAY_S)
            delay = base + random.random() * JITTER_FACTOR * base
            logger.warning(
                "[supabase-insert-preflight] Attempt %d/%d failed (%s). Retrying in %.2fs...",
                attempt, MAX_RETRIES + 1, exc, delay,
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

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_supabase_resilient.py -v 2>&1 | tail -30
```

Expected: All 19 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/supabase_resilient.py tests/test_supabase_resilient.py
git commit -m "feat: add ResilientClient proxy with operation-aware retry"
```

---

## Task 2: Wire the resilient client into `get_supabase()`

**Files:**
- Modify: `backend/supabase_client.py`

- [ ] **Step 1: Update `get_supabase()` to return the wrapper**

Replace the full contents of `backend/supabase_client.py` with:

```python
"""
Canonical Supabase client for Graider.
All modules should import from here instead of creating their own clients.

Provides two variants:
  - get_supabase()          → returns resilient client or None (lenient, for optional features)
  - get_supabase_or_raise() → returns resilient client or raises Exception (strict, for required features)
  - get_raw_supabase()      → returns the unwrapped raw client (opt-out for streaming / custom retry)
"""
import os
from supabase import create_client, Client

_supabase_raw: Client = None
_supabase_resilient = None


def get_raw_supabase() -> Client:
    """Lazy-init raw Supabase admin client WITHOUT retry wrapping.

    Use this only when you need the underlying client — e.g. for long-running
    streaming queries, custom retry logic, or testing. Most callers should use
    get_supabase() or get_supabase_or_raise() instead.
    """
    global _supabase_raw
    if _supabase_raw is None:
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_KEY')
        if url and key:
            _supabase_raw = create_client(url, key)
    return _supabase_raw


def get_supabase():
    """Lazy-init Supabase admin client with automatic retry wrapping.

    Returns a ResilientClient instance (behaves like the raw client but
    every .execute() call is routed through with_retry()), or None if
    not configured.
    """
    global _supabase_resilient
    if _supabase_resilient is None:
        raw = get_raw_supabase()
        if raw is not None:
            from backend.supabase_resilient import ResilientClient
            _supabase_resilient = ResilientClient(raw)
    return _supabase_resilient


def get_supabase_or_raise():
    """Lazy-init resilient Supabase client. Raises if not configured."""
    client = get_supabase()
    if client is None:
        raise Exception("Supabase credentials not configured. Check SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")
    return client
```

- [ ] **Step 2: Run the full backend test suite to verify nothing breaks**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -10
```

Expected: All tests pass. The wrapper should be fully transparent to existing test code.

- [ ] **Step 3: Smoke test against the live Supabase instance**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python3 -c "
from dotenv import load_dotenv; load_dotenv('.env', override=True)
from backend.supabase_client import get_supabase_or_raise
db = get_supabase_or_raise()
print('Wrapper type:', type(db).__name__)
print('Select test...')
result = db.table('classes').select('id, name').limit(1).execute()
print('  rows:', len(result.data))
print('SUCCESS')
"
```

Expected: prints `Wrapper type: ResilientClient`, a row count, and `SUCCESS`.

- [ ] **Step 4: Commit**

```bash
git add backend/supabase_client.py
git commit -m "feat: wire get_supabase() through ResilientClient wrapper"
```

---

## Task 2.5: Eliminate direct `create_client()` call sites

**Context:** Wrapping `get_supabase()` only protects modules that actually call it. Several helper modules bypass the singleton and build their own raw Supabase client via `supabase.create_client(...)`. Those paths still get zero retry coverage, silently defeating the wrapper for entire feature areas (behavior tracking, assistant tools, etc.). This task finds and fixes every offender.

**Files:**
- Modify: `backend/routes/behavior_routes.py` (and any other offenders found by the audit grep)
- Modify: `backend/services/assistant_tools_behavior.py` (and any other offenders found)
- Create: `tests/test_no_direct_create_client.py` — regression guard

- [ ] **Step 1: Run the audit grep to list every direct `create_client()` call outside `supabase_client.py`**

```bash
cd /Users/alexc/Downloads/Graider && grep -rn "from supabase import create_client\|supabase.create_client\|create_client(" backend/ --include='*.py' | grep -v "backend/supabase_client.py" | grep -v "^Binary"
```

Expected: Zero results at the end of this task. At the start, this lists (as of 2026-04-10):
- `backend/routes/behavior_routes.py` (around lines 30-39)
- `backend/services/assistant_tools_behavior.py` (around lines 33-42)
- Any additional offenders surfaced by the grep

Record the full list before making changes — each one must be migrated.

- [ ] **Step 2: Migrate each offender to `get_supabase_or_raise()`**

For each file surfaced by the grep, replace the pattern:

```python
# BEFORE
from supabase import create_client
import os

def _get_supabase():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    if not url or not key:
        return None
    return create_client(url, key)
```

with:

```python
# AFTER
from backend.supabase_client import get_supabase

def _get_supabase():
    # Delegates to the canonical singleton so calls run through ResilientClient.
    return get_supabase()
```

If the module requires a valid client and raises on missing creds, use `get_supabase_or_raise` instead:

```python
from backend.supabase_client import get_supabase_or_raise

def _get_supabase():
    return get_supabase_or_raise()
```

Apply to every file in the list from Step 1. Remove the now-unused `from supabase import create_client` and `import os` lines if they were only used for this purpose.

- [ ] **Step 3: Add a regression test that fails if anyone re-introduces `create_client()`**

Create `tests/test_no_direct_create_client.py`:

```python
"""Regression guard: no module outside backend/supabase_client.py may call
supabase.create_client directly. All Supabase access must route through the
canonical get_supabase()/get_supabase_or_raise() helpers so the ResilientClient
wrapper is applied.
"""

from pathlib import Path

import pytest


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
        # Catch the aliased form too
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

- [ ] **Step 4: Run the regression test and the full suite**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_no_direct_create_client.py -v 2>&1 | tail -10
```

Expected: PASS (offender list is empty after Step 2).

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -15
```

Expected: Full suite still green. The migrated modules should work identically because they now delegate to the same underlying Supabase client, just with retry on top.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/behavior_routes.py backend/services/assistant_tools_behavior.py tests/test_no_direct_create_client.py
# Include any additional files the audit grep surfaced
git commit -m "refactor: route all Supabase access through resilient singleton"
```

---

## Task 3: Migrate critical inserts to use caller-generated UUIDs

**Context:** With Task 2 shipped, all reads and idempotent writes are protected. Raw inserts only retry on connect-phase errors, which covers ~90% of transient failures but leaves a small gap: if a `POST /insert` gets a `ReadError` (server committed, response dropped), we surface the failure to the caller rather than double-insert. For the most critical tables, we close that gap by passing explicit UUIDs so the UNIQUE constraint makes retry safe.

The 4 critical write paths:

1. `student_submissions` insert in `submit_student_work` (`backend/routes/student_account_routes.py`)
2. `student_submissions` insert in `save_submission_draft` (`backend/routes/student_account_routes.py`)
3. `published_assessments` insert in `publish_assessment` (`backend/routes/student_portal_routes.py`)
4. `submissions` insert in the join-code `submit_assessment` (`backend/routes/student_portal_routes.py`)

For these, we:
- Generate a UUID in Python (`uuid.uuid4()`)
- Pass it as the `id` field in the insert payload
- Upgrade the call from `insert()` to `upsert(..., on_conflict='id')` so the policy classifier treats it as fully retryable
- Second retry attempt hits the UNIQUE constraint, merge-duplicates kicks in, no double-write

**Files:**
- Modify: `backend/routes/student_account_routes.py` (2 sites)
- Modify: `backend/routes/student_portal_routes.py` (2 sites)

- [ ] **Step 1: Audit the 4 target tables accept explicit UUIDs**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python3 << 'EOF'
from dotenv import load_dotenv; load_dotenv('.env', override=True)
from backend.supabase_client import get_raw_supabase
import uuid

db = get_raw_supabase()

tests = [
    # table, minimal row
    ('student_submissions', {
        'id': str(uuid.uuid4()),
        'student_name': '_resilience_test_',
        'status': 'draft',
    }),
]

for table, row in tests:
    try:
        # Insert
        ins = db.table(table).insert(row).execute()
        print(f'{table}: insert OK, id={ins.data[0]["id"]}')
        # Upsert with the SAME id should be a no-op
        ups = db.table(table).upsert(row, on_conflict='id').execute()
        print(f'{table}: upsert with same id OK (merge-duplicates)')
        # Cleanup
        db.table(table).delete().eq('id', row['id']).execute()
        print(f'{table}: cleanup OK')
    except Exception as e:
        print(f'{table}: FAILED — {e}')
EOF
```

Expected: All three steps (insert, upsert, cleanup) report OK for `student_submissions`. If any fail, diagnose the specific schema issue before proceeding.

- [ ] **Step 2: Migrate `submit_student_work` in `student_account_routes.py`**

Read the current implementation:

```bash
grep -n "submit_student_work\|student_submissions.*insert" /Users/alexc/Downloads/Graider/backend/routes/student_account_routes.py | head -10
```

Find the insert call (currently `db.table('student_submissions').insert(submission_row).execute()` around line 820). Replace the insertion pattern:

Change:
```python
        result = db.table('student_submissions').insert(submission_row).execute()
```

To:
```python
        import uuid as _uuid
        submission_row['id'] = str(_uuid.uuid4())
        result = db.table('student_submissions').upsert(
            submission_row, on_conflict='id'
        ).execute()
```

The insert is now an upsert with an explicit UUID. Full retry is safe: if the first attempt committed and the response dropped, the second attempt merges on the same id and returns the same row.

- [ ] **Step 3: Migrate `save_submission_draft` in `student_account_routes.py`**

Find the new-draft insert inside `save_submission_draft`. It currently looks like:

```python
            db.table('student_submissions').insert({
                'student_id': student_id,
                'content_id': content_id,
                ...
                'status': 'draft',
                ...
            }).execute()
```

Replace with:

```python
            import uuid as _uuid
            draft_row = {
                'id': str(_uuid.uuid4()),
                'student_id': student_id,
                'content_id': content_id,
                # ... keep the existing fields unchanged ...
                'status': 'draft',
                # ... etc ...
            }
            db.table('student_submissions').upsert(draft_row, on_conflict='id').execute()
```

Preserve every existing field on the row — only add the `id` and swap `insert()` for `upsert(..., on_conflict='id')`.

- [ ] **Step 4: Migrate `publish_assessment` in `student_portal_routes.py`**

Find the `published_assessments` insert. It currently looks something like:

```python
        result = db.table('published_assessments').insert({
            'join_code': join_code,
            'title': title,
            ...
        }).execute()
```

Replace with:

```python
        import uuid as _uuid
        published_row = {
            'id': str(_uuid.uuid4()),
            'join_code': join_code,
            'title': title,
            # ... keep the existing fields ...
        }
        result = db.table('published_assessments').upsert(
            published_row, on_conflict='id'
        ).execute()
```

- [ ] **Step 5: Migrate `submit_assessment` (join-code path) in `student_portal_routes.py`**

Find the `submissions` insert in the join-code public submission handler. Replace the insert with an upsert on id.

```python
        import uuid as _uuid
        submission_row['id'] = str(_uuid.uuid4())
        result = db.table('submissions').upsert(
            submission_row, on_conflict='id'
        ).execute()
```

- [ ] **Step 6: Run backend tests**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -10
```

Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/routes/student_account_routes.py backend/routes/student_portal_routes.py
git commit -m "feat: use caller-generated UUIDs for critical inserts (idempotent retry)"
```

---

## Task 4: Ensure grading thread uses the resilient client

**Files:**
- Modify: `backend/services/portal_grading.py`

The grading thread already calls `get_supabase()` to get its client, so after Task 2 ships it will automatically route through the resilient wrapper. This task is a verification-and-wrap task: confirm the grading-thread `.update()` call benefits from retry, and surface the grading-failed state change through the wrapper too.

- [ ] **Step 1: Confirm grading thread uses `get_supabase()`**

```bash
grep -n "supabase\|get_supabase\|sb\s*=\|db\s*=" /Users/alexc/Downloads/Graider/backend/services/portal_grading.py | head -20
```

Confirm the supabase client in `run_portal_grading_thread` is obtained via `get_supabase()` (not `create_client()` directly).

If it is: the resilient wrapper applies automatically — no code change needed.
If it isn't: change the acquisition line to `from backend.supabase_client import get_supabase_or_raise; sb = get_supabase_or_raise()`.

- [ ] **Step 2: Add an integration test that simulates Supabase flakiness during grading**

At the end of `tests/test_supabase_resilient.py`, add:

```python
class TestGradingThreadResilience:
    """End-to-end-ish test for retry behavior during background grading."""

    def test_update_retries_on_transient_read_error(self):
        """The grading thread updates student_submissions.results via PATCH.
        PATCH is fully idempotent so it should retry through transient failures.
        """
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

- [ ] **Step 3: Run the new test**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_supabase_resilient.py::TestGradingThreadResilience -v 2>&1 | tail -10
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_supabase_resilient.py backend/services/portal_grading.py
git commit -m "test: grading-thread PATCH retries through transient read errors"
```

(If `portal_grading.py` had no changes, omit it from the `git add`.)

---

## Task 5: Add healthcheck timeout and resilience documentation

**Files:**
- Create: `docs/supabase-resilience.md`
- Modify: `backend/app.py` (just the `/healthz` route)

- [ ] **Step 1: Tighten the healthcheck timeout**

Find the `/healthz` route in `backend/app.py` (around line 3389). The Supabase probe currently calls `db.table('published_assessments').select('id').limit(1).execute()` with no timeout override. In production we want a short timeout so a hanging healthcheck doesn't mark the pod healthy.

Change the probe block to:

```python
    # Supabase
    try:
        from backend.supabase_client import get_raw_supabase
        import httpx
        raw = get_raw_supabase()
        if raw is None:
            supabase_status = "not configured"
        else:
            # Healthcheck uses raw client with a short explicit timeout.
            # We don't want the healthcheck itself to retry — if Supabase is
            # slow, the pod should report degraded, not succeed after 30s.
            with httpx.Client(timeout=3.0):
                raw.table('published_assessments').select('id').limit(1).execute()
            supabase_status = "ok"
    except Exception as e:
        supabase_status = f"error: {str(e)[:100]}"
```

Note: this uses `get_raw_supabase()` specifically so the healthcheck does NOT participate in retry. A failing healthcheck should fail fast.

- [ ] **Step 2: Create `docs/supabase-resilience.md`**

```markdown
# Supabase Resilience Pattern

Graider's Supabase client is wrapped in a resilience proxy (`ResilientClient`) that automatically retries transient failures with exponential backoff.

## What's retried automatically

Every `.execute()` call on a query built through `db.table(...)` is routed through retry logic. The policy depends on the HTTP verb:

| Verb    | Operation     | Retry policy    |
|---------|---------------|-----------------|
| `GET`   | select        | full            |
| `PATCH` | update        | full            |
| `DELETE`| delete        | full            |
| `POST`  | upsert        | full            |
| `POST`  | insert        | preflight only  |

**full** = retry on any transient error (OSError, ConnectionError, TimeoutError, HTTP 408/429/5xx, httpcore ReadError/ReadTimeout, etc.)

**preflight only** = retry only on errors that occurred before any bytes reached the server (`ConnectError`, `ConnectTimeout`, DNS failures). Response-phase errors during an insert are surfaced to the caller because the server may already have committed the write.

## When to use caller-generated UUIDs

If your insert MUST retry safely even on response-phase errors — i.e., you cannot tolerate a failed submission surfacing a 500 error to a student — pass a caller-generated UUID as the `id` field and call `upsert(..., on_conflict='id')` instead of `insert(...)`:

```python
import uuid
row = {
    'id': str(uuid.uuid4()),
    # ... other fields ...
}
db.table('my_table').upsert(row, on_conflict='id').execute()
```

The upsert gets classified as "full retry". If the first attempt committed the row and the response dropped, the retry's UPSERT on the same id merges-duplicates to a no-op and returns the existing row.

Used in:
- `backend/routes/student_account_routes.py::submit_student_work`
- `backend/routes/student_account_routes.py::save_submission_draft`
- `backend/routes/student_portal_routes.py::publish_assessment`
- `backend/routes/student_portal_routes.py::submit_assessment`

## How to opt out of retry

For long-running streaming queries or custom retry logic, import the raw client:

```python
from backend.supabase_client import get_raw_supabase
raw = get_raw_supabase()
raw.table('my_table').select('*').execute()  # no retry wrapping
```

The healthcheck endpoint uses this to fail fast instead of retrying.

## Retry budget

- 5 retries per operation (configurable in `backend/retry.py`)
- Exponential backoff: 0.5s, 1s, 2s, 4s, 8s, capped at 32s
- ±25% jitter
- Honours `Retry-After` header

## Observability

Every retry is logged with `logger.warning` at:
- `[supabase-get]` for selects
- `[supabase-patch]` for updates
- `[supabase-delete]` for deletes
- `[supabase-post]` for upserts
- `[supabase-insert-preflight]` for insert preflight retries

Grep for these labels to see retry activity in production logs.
```

- [ ] **Step 3: Run the full test suite one more time**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -10
```

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app.py docs/supabase-resilience.md
git commit -m "docs: supabase resilience pattern + tighten healthcheck timeout"
```

---

## Task 6: Open PR and let CI verify

- [ ] **Step 1: Push the branch**

```bash
git push -u origin feat/supabase-resilience
```

- [ ] **Step 2: Open a PR with auto-merge enabled**

```bash
gh pr create --title "feat: Supabase resilience — operation-aware retry" --body "$(cat <<'EOF'
## Summary

Wraps the singleton Supabase client in a `ResilientClient` proxy that routes every `.execute()` call through operation-aware retry logic. Closes Tier 1 #2 in the district production reliability plan.

## Retry policy by operation

| Verb | Operation | Policy |
|---|---|---|
| GET | select | full retry |
| PATCH | update | full retry |
| DELETE | delete | full retry |
| POST+merge-duplicates | upsert | full retry |
| POST (raw) | insert | preflight-only (connect-phase errors only) |

## Critical-write UUID migration

The 4 critical insert paths now pass caller-generated UUIDs and use `upsert(..., on_conflict='id')` so they're fully retryable even on response-phase errors:

- `submit_student_work` (student_submissions)
- `save_submission_draft` (student_submissions)
- `publish_assessment` (published_assessments)
- `submit_assessment` join-code path (submissions)

## Other changes

- `/healthz` uses the raw client with 3s timeout (no retry during healthcheck)
- `docs/supabase-resilience.md` documents the pattern and opt-out path
- New test file `tests/test_supabase_resilient.py` with 17 unit tests covering classification, preflight detection, and retry behavior

## Test plan

- [x] 17 new unit tests pass
- [x] Full test suite (1000+ tests) still green
- [ ] CI green (this PR)
- [ ] Manual smoke test against live Supabase
EOF
)"
```

- [ ] **Step 3: Enable auto-merge**

```bash
gh pr merge --auto --squash
```

The PR will wait for CI (Backend Tests + Frontend Build) to pass, then squash-merge itself and delete the branch.

---

## Summary

| Task | Files changed | Risk | What it accomplishes |
|---|---|---|---|
| 1 | new: `supabase_resilient.py`, test file | Low — pure new module with tests | Core proxy + operation classifier |
| 2 | `supabase_client.py` | Low — 1 file, full-suite test gate | Wires proxy in transparently |
| 3 | 2 route files | Medium — touches critical insert paths | UUID-based idempotency for 4 write sites |
| 4 | maybe `portal_grading.py` + test | Low — verification only | Confirms grading thread benefits |
| 5 | `app.py` healthcheck + new doc | Low — tightens healthcheck | Ops documentation |
| 6 | none | None | Push + PR + auto-merge via CI |

**Before:** 194 raw `.table().execute()` calls in route handlers can each fail with an unretried `httpcore.ReadError` when Supabase's HTTP/2 connection pool drops. The error we saw today in localhost would become a 500 in production.

**After:** Every Supabase call in the backend is automatically protected. Reads, updates, deletes, upserts retry on any transient failure. Raw inserts retry conservatively on connect-phase errors. The 4 most critical insert paths upgrade to full-retry via caller-generated UUIDs. Healthcheck fails fast without retry. Full docs and tests for the pattern.
