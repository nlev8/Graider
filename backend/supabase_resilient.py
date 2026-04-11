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
    if isinstance(error, httpcore.NetworkError):
        return True
    if isinstance(error, httpcore.TimeoutException):
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
