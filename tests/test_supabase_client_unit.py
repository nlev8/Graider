"""Unit tests for backend/supabase_client.py.

Audit MAJOR #4 sprint follow-up to PR #271. Targets 10 uncovered LOC
(76% baseline). Three functions:
  1. `get_raw_supabase` — lazy singleton with double-check lock
  2. `get_supabase` — wraps raw client in ResilientClient (also lazy + locked)
  3. `get_supabase_or_raise` — calls get_supabase, raises with specific
     missing-var message when client is None

Existing test files (`tests/test_supabase_client_scoped.py`) cover the
public happy-path; this file adds tests for the singleton mechanics,
the threading double-check branch, and the raise paths in
`get_supabase_or_raise`.

Per `feedback_codex_medium_effort_2026-05-09.md`, Codex review uses
medium effort this session (rate-limit workaround); Gemini 3.1 Pro is
the validated fallback per `reference_gemini_cli_codex_fallback.md`.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────
# Fixture — reset singletons between tests
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def reset_singletons():
    """Reset module-level singleton variables before/after each test.

    The `_supabase_raw` and `_supabase_resilient` globals are populated on
    first call and cached for the process lifetime. Without resetting,
    each test would see whatever the previous test left behind.
    """
    from backend import supabase_client as mod

    saved_raw = mod._supabase_raw
    saved_resilient = mod._supabase_resilient
    mod._supabase_raw = None
    mod._supabase_resilient = None
    yield mod
    mod._supabase_raw = saved_raw
    mod._supabase_resilient = saved_resilient


# ──────────────────────────────────────────────────────────────────
# get_raw_supabase
# ──────────────────────────────────────────────────────────────────


class TestGetRawSupabase:
    def test_creates_client_when_env_vars_set(self, reset_singletons):
        from backend.supabase_client import get_raw_supabase

        sentinel_client = MagicMock(name="raw_client")
        with patch.dict("os.environ",
                        {"SUPABASE_URL": "https://x.supabase.co",
                         "SUPABASE_SERVICE_KEY": "key-1"}), \
             patch("backend.supabase_client.create_client",
                   return_value=sentinel_client) as mock_create:
            result = get_raw_supabase()
        assert result is sentinel_client
        mock_create.assert_called_once_with("https://x.supabase.co", "key-1")

    def test_returns_none_when_url_missing(self, reset_singletons):
        from backend.supabase_client import get_raw_supabase
        import os

        env = {k: v for k, v in os.environ.items()
               if k not in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY")}
        env["SUPABASE_SERVICE_KEY"] = "key-1"
        with patch.dict("os.environ", env, clear=True), \
             patch("backend.supabase_client.create_client") as mock_create:
            result = get_raw_supabase()
        assert result is None
        mock_create.assert_not_called()

    def test_returns_none_when_key_missing(self, reset_singletons):
        from backend.supabase_client import get_raw_supabase
        import os

        env = {k: v for k, v in os.environ.items()
               if k not in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY")}
        env["SUPABASE_URL"] = "https://x.supabase.co"
        with patch.dict("os.environ", env, clear=True), \
             patch("backend.supabase_client.create_client") as mock_create:
            result = get_raw_supabase()
        assert result is None
        mock_create.assert_not_called()

    def test_singleton_cached_after_first_call(self, reset_singletons):
        from backend.supabase_client import get_raw_supabase

        sentinel = MagicMock(name="raw_client")
        with patch.dict("os.environ",
                        {"SUPABASE_URL": "https://x.supabase.co",
                         "SUPABASE_SERVICE_KEY": "key-1"}), \
             patch("backend.supabase_client.create_client",
                   return_value=sentinel) as mock_create:
            r1 = get_raw_supabase()
            r2 = get_raw_supabase()
            r3 = get_raw_supabase()
        assert r1 is sentinel
        assert r2 is sentinel
        assert r3 is sentinel
        # Critical contract: create_client called EXACTLY once across all
        # three calls — that's what makes this a singleton (not just a
        # cache).
        mock_create.assert_called_once()

    def test_double_check_inside_lock_branch(self, reset_singletons):
        # Hit line 46: the second `if _supabase_raw is not None: return`
        # inside the lock. Simulates: thread-A holds the lock and creates
        # the client; thread-B was waiting on the lock and now needs to
        # see the cached value rather than create a duplicate.
        from backend import supabase_client as mod
        from backend.supabase_client import get_raw_supabase

        sentinel = MagicMock(name="raw_client")

        # Pre-set the singleton to None so the first outer check fails.
        # Then mock the lock's __enter__ to set the singleton, simulating
        # another thread completing initialization while we waited.
        mod._supabase_raw = None
        original_lock = mod._init_lock

        class _FakeLock:
            def __enter__(self):
                # Another thread "won the race" — populate the singleton
                mod._supabase_raw = sentinel
                return self
            def __exit__(self, *a):
                return False

        with patch.dict("os.environ",
                        {"SUPABASE_URL": "https://x.supabase.co",
                         "SUPABASE_SERVICE_KEY": "key-1"}), \
             patch("backend.supabase_client._init_lock", _FakeLock()), \
             patch("backend.supabase_client.create_client") as mock_create:
            result = get_raw_supabase()
        # The double-check path must return the sentinel WITHOUT calling
        # create_client again (preventing the duplicate-client race that
        # the lock exists to prevent).
        assert result is sentinel
        mock_create.assert_not_called()


# ──────────────────────────────────────────────────────────────────
# get_supabase (resilient wrapper)
# ──────────────────────────────────────────────────────────────────


class TestGetSupabase:
    def test_wraps_raw_client_in_resilient(self, reset_singletons):
        from backend.supabase_client import get_supabase

        raw_sentinel = MagicMock(name="raw_client")
        with patch.dict("os.environ",
                        {"SUPABASE_URL": "https://x.supabase.co",
                         "SUPABASE_SERVICE_KEY": "key-1"}), \
             patch("backend.supabase_client.create_client",
                   return_value=raw_sentinel), \
             patch("backend.supabase_resilient.ResilientClient") as MockResilient:
            wrapped = MagicMock(name="wrapped")
            MockResilient.return_value = wrapped
            result = get_supabase()
        # The raw client gets wrapped in a ResilientClient
        MockResilient.assert_called_once_with(raw_sentinel)
        assert result is wrapped

    def test_returns_none_when_raw_unavailable(self, reset_singletons):
        from backend.supabase_client import get_supabase
        import os

        env = {k: v for k, v in os.environ.items()
               if k not in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY")}
        with patch.dict("os.environ", env, clear=True):
            result = get_supabase()
        assert result is None

    def test_singleton_cached_after_first_wrap(self, reset_singletons):
        from backend.supabase_client import get_supabase

        with patch.dict("os.environ",
                        {"SUPABASE_URL": "https://x.supabase.co",
                         "SUPABASE_SERVICE_KEY": "key-1"}), \
             patch("backend.supabase_client.create_client",
                   return_value=MagicMock()), \
             patch("backend.supabase_resilient.ResilientClient") as MockResilient:
            wrapped = MagicMock(name="wrapped")
            MockResilient.return_value = wrapped
            r1 = get_supabase()
            r2 = get_supabase()
        assert r1 is wrapped
        assert r2 is wrapped
        # ResilientClient constructed exactly once
        MockResilient.assert_called_once()

    def test_double_check_inside_lock_branch(self, reset_singletons):
        # Hit line 66: the second `if _supabase_resilient is not None:
        # return` inside the lock for the resilient wrapper.
        from backend import supabase_client as mod
        from backend.supabase_client import get_supabase

        sentinel = MagicMock(name="resilient_client")

        mod._supabase_resilient = None

        class _FakeLock:
            def __enter__(self):
                mod._supabase_resilient = sentinel
                return self
            def __exit__(self, *a):
                return False

        with patch.dict("os.environ",
                        {"SUPABASE_URL": "https://x.supabase.co",
                         "SUPABASE_SERVICE_KEY": "key-1"}), \
             patch("backend.supabase_client._init_lock", _FakeLock()), \
             patch("backend.supabase_resilient.ResilientClient") as MockResilient:
            result = get_supabase()
        # Double-check returned the sentinel without constructing a new
        # ResilientClient.
        assert result is sentinel
        MockResilient.assert_not_called()


# ──────────────────────────────────────────────────────────────────
# get_supabase_or_raise
# ──────────────────────────────────────────────────────────────────


class TestGetSupabaseOrRaise:
    def test_returns_client_when_configured(self, reset_singletons):
        from backend.supabase_client import get_supabase_or_raise

        wrapped = MagicMock(name="resilient_client")
        with patch("backend.supabase_client.get_supabase",
                   return_value=wrapped):
            result = get_supabase_or_raise()
        assert result is wrapped

    def test_raises_naming_missing_url(self, reset_singletons):
        # Hit lines 84-93: identify which env var is missing
        from backend.supabase_client import get_supabase_or_raise
        import os

        env = {k: v for k, v in os.environ.items()
               if k not in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY")}
        env["SUPABASE_SERVICE_KEY"] = "key-1"  # only key present
        with patch.dict("os.environ", env, clear=True), \
             patch("backend.supabase_client.get_supabase", return_value=None):
            with pytest.raises(Exception) as exc_info:
                get_supabase_or_raise()
        msg = str(exc_info.value)
        assert "SUPABASE_URL" in msg
        # The other env var should NOT be in the missing list since it's set
        assert "SUPABASE_SERVICE_KEY" not in msg
        assert ".env" in msg or "credentials not configured" in msg

    def test_raises_naming_missing_key(self, reset_singletons):
        from backend.supabase_client import get_supabase_or_raise
        import os

        env = {k: v for k, v in os.environ.items()
               if k not in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY")}
        env["SUPABASE_URL"] = "https://x.supabase.co"
        with patch.dict("os.environ", env, clear=True), \
             patch("backend.supabase_client.get_supabase", return_value=None):
            with pytest.raises(Exception) as exc_info:
                get_supabase_or_raise()
        msg = str(exc_info.value)
        assert "SUPABASE_SERVICE_KEY" in msg
        # Should NOT mention SUPABASE_URL (which IS set)
        assert "SUPABASE_URL" not in msg

    def test_raises_naming_both_missing(self, reset_singletons):
        from backend.supabase_client import get_supabase_or_raise
        import os

        env = {k: v for k, v in os.environ.items()
               if k not in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY")}
        with patch.dict("os.environ", env, clear=True), \
             patch("backend.supabase_client.get_supabase", return_value=None):
            with pytest.raises(Exception) as exc_info:
                get_supabase_or_raise()
        msg = str(exc_info.value)
        # Both should be named in the missing list
        assert "SUPABASE_URL" in msg
        assert "SUPABASE_SERVICE_KEY" in msg

    def test_raises_init_failed_when_both_set_but_client_none(
        self, reset_singletons,
    ):
        # Hit lines 94-98: both env vars set, but client is still None
        # — likely a create_client() failure that didn't raise.
        from backend.supabase_client import get_supabase_or_raise

        with patch.dict("os.environ",
                        {"SUPABASE_URL": "https://x.supabase.co",
                         "SUPABASE_SERVICE_KEY": "key-1"}), \
             patch("backend.supabase_client.get_supabase", return_value=None):
            with pytest.raises(Exception) as exc_info:
                get_supabase_or_raise()
        msg = str(exc_info.value)
        # Different message branch — points at create_client() specifically
        assert "initialization failed" in msg.lower()
        assert "create_client()" in msg

    def test_error_message_actionable_for_dev_diagnosis(self, reset_singletons):
        # Stronger pin — the error message must mention a concrete fix
        # path so a dev seeing this in prod can actually act on it.
        from backend.supabase_client import get_supabase_or_raise
        import os

        env = {k: v for k, v in os.environ.items()
               if k not in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY")}
        with patch.dict("os.environ", env, clear=True), \
             patch("backend.supabase_client.get_supabase", return_value=None):
            with pytest.raises(Exception) as exc_info:
                get_supabase_or_raise()
        msg = str(exc_info.value)
        # The concrete remediation hint
        assert ".env" in msg
