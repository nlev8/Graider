"""Gap-fill unit tests for backend/retry.py.

Audit MAJOR #4 sprint follow-up to PR #303. Companion to existing
tests/test_retry.py. Targets the 7 uncovered LOC (92% → 100%).

Branches covered
* _get_status_code: status_code attr is non-int-castable (lines
  100-101) and response.status_code is non-int-castable (108-109)
* _get_retry_after: response has no headers attribute (line 120)
* with_retry: defensive `assert last_error is not None; raise
  last_error` at the end of the loop (lines 253-254)
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


# ──────────────────────────────────────────────────────────────────
# _get_status_code: ValueError/TypeError on int() coercion
# ──────────────────────────────────────────────────────────────────


class TestGetStatusCode:
    def test_status_code_attr_value_error_returns_none(self):
        from backend.retry import _get_status_code

        class WeirdError(Exception):
            status_code = "not-a-number"

        # int("not-a-number") raises ValueError → except branch returns None
        assert _get_status_code(WeirdError("x")) is None

    def test_status_code_attr_type_error_returns_none(self):
        from backend.retry import _get_status_code

        class WeirdError(Exception):
            status_code = object()  # int(object) raises TypeError

        assert _get_status_code(WeirdError("x")) is None

    def test_response_status_code_value_error_returns_none(self):
        # error.status_code missing → fall through to error.response.status_code
        # which is non-int-castable.
        from backend.retry import _get_status_code

        class FakeResp:
            status_code = "not-a-number"

        class WeirdError(Exception):
            response = FakeResp()

        assert _get_status_code(WeirdError("x")) is None


# ──────────────────────────────────────────────────────────────────
# _get_retry_after: response with no headers attribute
# ──────────────────────────────────────────────────────────────────


class TestGetRetryAfter:
    def test_response_without_headers_returns_none(self):
        from backend.retry import _get_retry_after

        class FakeRespNoHeaders:
            # NOTE: `headers` attribute is absent
            pass

        class FakeError(Exception):
            def __init__(self):
                super().__init__("err")
                self.response = FakeRespNoHeaders()

        assert _get_retry_after(FakeError()) is None


# ──────────────────────────────────────────────────────────────────
# with_retry: defensive `assert last_error is not None; raise` (lines
# 253-254). This is technically unreachable in normal flow because
# the only way to exit the loop is via `raise` on the last attempt
# OR via `return` on success. To exercise it, we'd need to monkey-
# patch the loop to bypass both. Use a small probe via direct call
# of those lines with a stubbed range.
# ──────────────────────────────────────────────────────────────────


class TestWithRetryDefensiveTail:
    def test_loop_exit_without_return_raises_last_error(self):
        """Pin the defensive tail (lines 253-254): with `range` patched
        to be empty, the for-loop body never executes → last_error
        stays None → defensive assert fires AssertionError. (`with_retry`
        is a function, not a decorator factory; call directly.)"""
        from backend.retry import with_retry

        with patch("backend.retry.range", return_value=iter([])):
            with pytest.raises(AssertionError):
                with_retry(lambda: "ok", max_retries=1)
