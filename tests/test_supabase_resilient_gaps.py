"""Gap-fill tests for backend/supabase_resilient.py.

Audit MAJOR #4 sprint follow-up to PR #325. Companion to existing
`tests/test_supabase_resilient.py`. Targets the 17 missing LOC
(84.4% baseline → 100% goal):

* `_classify_operation` AttributeError fallback (lines 74, 76)
* `_is_preflight_error` DNS error variants — "nodename nor servname"
  + "Temporary failure in name resolution" (lines 116-119)
* `_resilient_execute` method-extraction AttributeError fallback
  (lines 134-135), retries-exhausted log+raise (lines 162, 166),
  defensive assert+raise post-loop (lines 177-178)
* `_ExecuteProxy.__getattr__` non-callable + non-builder branch
  (lines 202, 204)
* `_wrap_if_builder` None passthrough (line 216), non-builder
  passthrough (line 223)
* `ResilientClient.from_` (line 241)

Per dual-rate-limit precedent: test-only PR merging on green CI.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpcore
import pytest


MODULE = "backend.supabase_resilient"


# ──────────────────────────────────────────────────────────────────
# _classify_operation AttributeError fallback
# ──────────────────────────────────────────────────────────────────


class TestClassifyOperationFallback:
    def test_attribute_error_returns_preflight_only(self):
        from backend.supabase_resilient import _classify_operation

        # An object without `.request.http_method` → AttributeError
        # → fallback to "preflight_only"
        bad_query = object()
        assert _classify_operation(bad_query) == "preflight_only"

    def test_get_returns_full(self):
        from backend.supabase_resilient import _classify_operation
        q = MagicMock()
        q.request.http_method = "GET"
        q.request.headers = {}
        assert _classify_operation(q) == "full"

    def test_patch_returns_full(self):
        from backend.supabase_resilient import _classify_operation
        q = MagicMock()
        q.request.http_method = "PATCH"
        q.request.headers = {}
        assert _classify_operation(q) == "full"

    def test_post_with_merge_duplicates_returns_full(self):
        # Upsert pattern (POST + merge-duplicates header)
        from backend.supabase_resilient import _classify_operation
        q = MagicMock()
        q.request.http_method = "POST"
        q.request.headers = {"Prefer": "return=representation,resolution=merge-duplicates"}
        assert _classify_operation(q) == "full"

    def test_post_without_merge_duplicates_returns_preflight(self):
        from backend.supabase_resilient import _classify_operation
        q = MagicMock()
        q.request.http_method = "POST"
        q.request.headers = {"Prefer": "return=representation"}
        assert _classify_operation(q) == "preflight_only"

    def test_unknown_method_returns_preflight(self):
        from backend.supabase_resilient import _classify_operation
        q = MagicMock()
        q.request.http_method = "OPTIONS"
        q.request.headers = {}
        assert _classify_operation(q) == "preflight_only"


# ──────────────────────────────────────────────────────────────────
# _is_preflight_error DNS variants
# ──────────────────────────────────────────────────────────────────


class TestIsPreflightErrorDns:
    def test_name_or_service_not_known(self):
        from backend.supabase_resilient import _is_preflight_error
        e = OSError("[Errno -2] Name or service not known")
        assert _is_preflight_error(e) is True

    def test_nodename_nor_servname(self):
        from backend.supabase_resilient import _is_preflight_error
        e = OSError("[Errno 8] nodename nor servname provided")
        assert _is_preflight_error(e) is True

    def test_temporary_failure_in_name_resolution(self):
        from backend.supabase_resilient import _is_preflight_error
        e = OSError("[Errno -3] Temporary failure in name resolution")
        assert _is_preflight_error(e) is True

    def test_unrelated_oserror_returns_false(self):
        from backend.supabase_resilient import _is_preflight_error
        e = OSError("Some unrelated error")
        assert _is_preflight_error(e) is False

    def test_connect_error_is_preflight(self):
        from backend.supabase_resilient import _is_preflight_error
        # httpcore.ConnectError requires a message arg in some versions
        e = httpcore.ConnectError("connection refused")
        assert _is_preflight_error(e) is True

    def test_unrelated_error_returns_false(self):
        from backend.supabase_resilient import _is_preflight_error
        e = ValueError("just a value error")
        assert _is_preflight_error(e) is False


# ──────────────────────────────────────────────────────────────────
# _resilient_execute method-extraction fallback + exhausted retries
# ──────────────────────────────────────────────────────────────────


class TestResilientExecute:
    def test_method_attribute_error_uses_unknown_label(self):
        # Query lacks .request entirely → AttributeError → method="unknown"
        # (covered through happy execute path with no retries needed)
        from backend.supabase_resilient import _resilient_execute

        q = MagicMock()
        # Force AttributeError by removing nested attribute
        del q.request
        # Make execute() succeed immediately
        q.execute.return_value = MagicMock(data=[])

        result = _resilient_execute(q)
        assert result is q.execute.return_value

    def test_full_retry_exhausted_raises_after_max(self):
        # Force a retryable error to keep firing past MAX_RETRIES
        from backend.supabase_resilient import _resilient_execute, MAX_RETRIES

        q = MagicMock()
        q.request.http_method = "GET"
        q.request.headers = {}

        retryable = httpcore.NetworkError("transient")
        q.execute.side_effect = retryable

        with patch(f"{MODULE}.time.sleep"):
            with pytest.raises(httpcore.NetworkError):
                _resilient_execute(q)
        # Called MAX_RETRIES + 1 times total (1 initial + retries)
        assert q.execute.call_count == MAX_RETRIES + 1

    def test_preflight_only_skips_retry_for_response_phase_error(self):
        # POST raw insert + a NON-preflight error (e.g., ReadError) →
        # _should_retry returns False → raise immediately, no retry
        from backend.supabase_resilient import _resilient_execute

        q = MagicMock()
        q.request.http_method = "POST"
        q.request.headers = {"Prefer": "return=representation"}

        read_err = httpcore.ReadError("server-side error")
        q.execute.side_effect = read_err

        with patch(f"{MODULE}.time.sleep"):
            with pytest.raises(httpcore.ReadError):
                _resilient_execute(q)
        # Only one call — never retried
        assert q.execute.call_count == 1

    def test_non_retryable_error_raises_immediately(self):
        # ValueError isn't retryable per is_retryable_error
        from backend.supabase_resilient import _resilient_execute

        q = MagicMock()
        q.request.http_method = "GET"
        q.request.headers = {}
        q.execute.side_effect = ValueError("not retryable")

        with patch(f"{MODULE}.time.sleep"):
            with pytest.raises(ValueError):
                _resilient_execute(q)
        assert q.execute.call_count == 1


# ──────────────────────────────────────────────────────────────────
# _ExecuteProxy.__getattr__ branches
# ──────────────────────────────────────────────────────────────────


class TestExecuteProxyGetattr:
    def test_callable_returning_non_builder_passes_through(self):
        from backend.supabase_resilient import _ExecuteProxy

        inner = MagicMock()

        # Build a method that returns a plain object (no execute)
        def some_method(*args, **kwargs):
            return "plain-result"

        inner.some_method = some_method

        proxy = _ExecuteProxy(inner)
        # Calling proxy.some_method() should return the raw "plain-result"
        # (NOT wrapped, because no .execute attribute)
        assert proxy.some_method() == "plain-result"

    def test_non_callable_attribute_passes_through(self):
        from backend.supabase_resilient import _ExecuteProxy

        inner = MagicMock()
        inner.some_field = "field-value"

        proxy = _ExecuteProxy(inner)
        assert proxy.some_field == "field-value"

    def test_callable_returning_builder_wraps(self):
        # If a method on inner returns something with .execute, wrap it
        from backend.supabase_resilient import _ExecuteProxy

        inner = MagicMock()
        sub_builder = MagicMock()
        sub_builder.execute = MagicMock(return_value="sub-data")
        inner.eq = MagicMock(return_value=sub_builder)

        proxy = _ExecuteProxy(inner)
        wrapped = proxy.eq("col", "val")
        # Wrapped is itself an _ExecuteProxy
        assert isinstance(wrapped, _ExecuteProxy)


# ──────────────────────────────────────────────────────────────────
# _wrap_if_builder branches
# ──────────────────────────────────────────────────────────────────


class TestWrapIfBuilder:
    def test_none_passes_through(self):
        from backend.supabase_resilient import _wrap_if_builder
        assert _wrap_if_builder(None) is None

    def test_object_with_execute_wrapped_in_proxy(self):
        from backend.supabase_resilient import (
            _wrap_if_builder, _ExecuteProxy,
        )
        builder = MagicMock()
        builder.execute = MagicMock(return_value="data")
        result = _wrap_if_builder(builder)
        assert isinstance(result, _ExecuteProxy)

    def test_object_with_table_attr_wrapped_in_resilient_client(self):
        from backend.supabase_resilient import (
            _wrap_if_builder, ResilientClient,
        )
        sub_client = MagicMock(spec=["table", "from_"])
        # No .execute on sub_client itself, but has .table → wrap
        result = _wrap_if_builder(sub_client)
        assert isinstance(result, ResilientClient)

    def test_plain_object_passes_through_unchanged(self):
        from backend.supabase_resilient import _wrap_if_builder

        plain = MagicMock(spec=[])  # No execute, table, or from_
        result = _wrap_if_builder(plain)
        assert result is plain


# ──────────────────────────────────────────────────────────────────
# ResilientClient.from_
# ──────────────────────────────────────────────────────────────────


class TestResilientClientFrom:
    def test_from_returns_execute_proxy(self):
        from backend.supabase_resilient import (
            ResilientClient, _ExecuteProxy,
        )
        raw = MagicMock()
        raw.from_ = MagicMock(return_value=MagicMock())

        client = ResilientClient(raw)
        result = client.from_("my_table")
        assert isinstance(result, _ExecuteProxy)
        raw.from_.assert_called_once_with("my_table")

    def test_table_returns_execute_proxy(self):
        from backend.supabase_resilient import (
            ResilientClient, _ExecuteProxy,
        )
        raw = MagicMock()
        raw.table = MagicMock(return_value=MagicMock())

        client = ResilientClient(raw)
        result = client.table("my_table")
        assert isinstance(result, _ExecuteProxy)

    def test_rpc_with_params_wrapped(self):
        from backend.supabase_resilient import ResilientClient
        raw = MagicMock()
        builder = MagicMock()
        builder.execute = MagicMock()
        raw.rpc.return_value = builder

        client = ResilientClient(raw)
        result = client.rpc("my_fn", {"k": "v"})
        # rpc() called with both args
        raw.rpc.assert_called_once_with("my_fn", {"k": "v"})

    def test_rpc_no_params_wrapped(self):
        from backend.supabase_resilient import ResilientClient
        raw = MagicMock()
        builder = MagicMock()
        builder.execute = MagicMock()
        raw.rpc.return_value = builder

        client = ResilientClient(raw)
        client.rpc("my_fn")
        # Single-arg call when params=None
        raw.rpc.assert_called_once_with("my_fn")

    def test_schema_wraps_sub_client(self):
        from backend.supabase_resilient import (
            ResilientClient,
        )
        raw = MagicMock()
        sub_client = MagicMock(spec=["table", "from_"])
        raw.schema = MagicMock(return_value=sub_client)

        client = ResilientClient(raw)
        result = client.schema("private")
        # sub_client gets wrapped in ResilientClient
        assert isinstance(result, ResilientClient)

    def test_passthrough_attribute(self):
        # Non-postgrest attrs (auth, storage, etc.) pass through unchanged
        from backend.supabase_resilient import ResilientClient
        raw = MagicMock()
        raw.auth = "auth-handle"

        client = ResilientClient(raw)
        assert client.auth == "auth-handle"
