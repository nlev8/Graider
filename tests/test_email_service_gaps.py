"""Targeted coverage extension for backend/services/email_service.py.

Audit MAJOR #4 sprint follow-up to PR #273. The module was at 75% from
PR #263 + `tests/test_email_service_unit.py`. Targets the remaining
reachable uncovered lines:

  * 110-111 — `send_email` returns False when `RESEND_AVAILABLE` is False
              at call time (existing test patches it only during __init__,
              so the function-level guard at line 109 isn't hit)
  * 242-243 — same pattern for `test_connection`
  * 58-62  — `_init_resend` `.env`-file parsing fallback (when env var is
             absent, walk Path(__file__)/parent/parent/parent/.env and
             cwd/.env looking for `RESEND_API_KEY=...` lines)

Lines 24-26 (ImportError fallback for the resend package) and 267-303
(the `if __name__ == "__main__"` CLI block) are intentionally out of
scope — they require import-time stubbing or subprocess invocation.

Per `feedback_codex_medium_effort_2026-05-09.md` and
`reference_gemini_cli_codex_fallback.md`, Codex is rate-limited; Gemini
3.1 Pro Preview is the validated fallback reviewer this session.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def isolated_dirs(tmp_path, monkeypatch):
    """Redirect HOME so config files write to a tmp dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


# ──────────────────────────────────────────────────────────────────
# send_email — RESEND_AVAILABLE False at call time
# ──────────────────────────────────────────────────────────────────


class TestSendEmailResendUnavailableAtCallTime:
    def test_returns_false_when_resend_package_missing_at_call_time(
        self, isolated_dirs, monkeypatch,
    ):
        # PR #274 gap-fill: existing test patches RESEND_AVAILABLE only
        # during __init__, so the function-level guard at email_service.py:109
        # is not hit. Keep the patch active across the send_email call.
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        from backend.services.email_service import GraiderEmailer

        with patch("backend.services.email_service.RESEND_AVAILABLE", True):
            # Init with True so resend_available IS set, then flip to False
            # while calling send_email.
            emailer = GraiderEmailer(
                config_path=str(isolated_dirs / "cfg.json"),
            )

        with patch("backend.services.email_service.RESEND_AVAILABLE", False):
            result = emailer.send_email("a@x.com", "Alice", "Subj", "Body")
        assert result is False


# ──────────────────────────────────────────────────────────────────
# test_connection — RESEND_AVAILABLE False at call time
# ──────────────────────────────────────────────────────────────────


class TestTestConnectionResendUnavailableAtCallTime:
    def test_returns_false_when_resend_package_missing_at_call_time(
        self, isolated_dirs, monkeypatch,
    ):
        # Symmetric to TestSendEmail above — covers lines 242-243.
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        from backend.services.email_service import GraiderEmailer

        with patch("backend.services.email_service.RESEND_AVAILABLE", True):
            emailer = GraiderEmailer(
                config_path=str(isolated_dirs / "cfg.json"),
            )

        with patch("backend.services.email_service.RESEND_AVAILABLE", False):
            result = emailer.test_connection()
        assert result is False

    def test_returns_false_when_resend_available_flag_is_false_at_call_time(
        self, isolated_dirs, monkeypatch,
    ):
        # Symmetric to existing send_email "api_key not configured" test
        # but for test_connection — covers the lines 245-247 path
        # (`if not self.resend_available`).
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        from backend.services.email_service import GraiderEmailer

        emailer = GraiderEmailer(config_path=str(isolated_dirs / "cfg.json"))
        emailer.resend_available = False  # explicitly clear

        with patch("backend.services.email_service.RESEND_AVAILABLE", True):
            result = emailer.test_connection()
        assert result is False


# ──────────────────────────────────────────────────────────────────
# _init_resend — .env file parsing fallback
# ──────────────────────────────────────────────────────────────────


class TestInitResendDotEnvFallback:
    """Test the `.env`-file parsing path in `_init_resend` (lines 51-62).

    The production code at email_service.py:51-62 walks two paths looking
    for a `RESEND_API_KEY=...` line:
      1. Path(__file__).parent.parent.parent / '.env'  (project root)
      2. Path.cwd() / '.env'

    In this test environment, the actual project root `.env` exists with
    a real RESEND_API_KEY — so to test the fallback in isolation, we
    patch the `env_paths` source by patching the `Path` class used in
    the module. We provide a controlled list of paths that point only
    to a tmp directory.
    """

    @staticmethod
    def _patch_env_paths_to(*paths):
        """Build a mock `Path` whose `Path(...) / '.env'` returns paths in
        order: first call returns paths[0], second call returns paths[1], etc.

        Returns a `patch` context manager that replaces `email_service.Path`.
        """
        from pathlib import Path as _RealPath

        # Production constructs:
        #   Path(__file__).parent.parent.parent / '.env'
        #   Path.cwd() / '.env'
        # We need both `Path(arg)` and `Path.cwd()` to chain to controlled
        # outputs. Easiest approach: use a callable that, when invoked,
        # returns a chain ending in one of our `paths` (popped FIFO).

        queue = list(paths)

        class _StubPath:
            """Builds a chainable object whose `.parent` / `.cwd()` /
            `/ '.env'` ultimately yields a real Path from the queue."""

            def __init__(self, *args):
                self._stub = True

            @property
            def parent(self):
                return self

            @classmethod
            def cwd(cls):
                return cls()

            def __truediv__(self, other):
                # The final `/ '.env'` returns the next queued real Path
                if queue:
                    return queue.pop(0)
                return _RealPath("/nonexistent")

        return patch("backend.services.email_service.Path", _StubPath)

    def test_loads_api_key_from_env_file_when_env_var_absent(
        self, tmp_path, monkeypatch,
    ):
        # PR #274 gap-fill: `_init_resend` falls back to reading `.env` files
        # at backend/services/email_service.py:51-62 when `os.getenv()` is empty.
        monkeypatch.delenv("RESEND_API_KEY", raising=False)

        # First env_path is the only one that exists, contains the key
        first_env = tmp_path / "first.env"
        first_env.write_text(
            "OTHER_VAR=ignored\n"
            'RESEND_API_KEY="re_test_abcd_1234"\n'
            "ANOTHER=also_ignored\n"
        )
        # Second is non-existent (won't be reached due to outer break)
        second_env = tmp_path / "nonexistent.env"

        with self._patch_env_paths_to(first_env, second_env), \
             patch("backend.services.email_service.RESEND_AVAILABLE", True), \
             patch("backend.services.email_service.resend") as mock_resend:
            from backend.services.email_service import GraiderEmailer
            emailer = GraiderEmailer(
                config_path=str(tmp_path / "cfg.json"),
            )

        assert mock_resend.api_key == "re_test_abcd_1234"
        assert emailer.resend_available is True

    def test_strips_single_quotes_from_env_file_value(
        self, tmp_path, monkeypatch,
    ):
        # The .env parser strips both `"..."` and `'...'` quotes per
        # email_service.py:59 — `.strip().strip('"').strip("'")`
        monkeypatch.delenv("RESEND_API_KEY", raising=False)

        first_env = tmp_path / "first.env"
        first_env.write_text("RESEND_API_KEY='re_singly_quoted'\n")
        second_env = tmp_path / "missing.env"

        with self._patch_env_paths_to(first_env, second_env), \
             patch("backend.services.email_service.RESEND_AVAILABLE", True), \
             patch("backend.services.email_service.resend") as mock_resend:
            from backend.services.email_service import GraiderEmailer
            GraiderEmailer(config_path=str(tmp_path / "cfg.json"))
        assert mock_resend.api_key == "re_singly_quoted"

    def test_strips_unquoted_env_file_value(
        self, tmp_path, monkeypatch,
    ):
        monkeypatch.delenv("RESEND_API_KEY", raising=False)

        first_env = tmp_path / "first.env"
        first_env.write_text("RESEND_API_KEY=re_unquoted_xyz\n")
        second_env = tmp_path / "missing.env"

        with self._patch_env_paths_to(first_env, second_env), \
             patch("backend.services.email_service.RESEND_AVAILABLE", True), \
             patch("backend.services.email_service.resend") as mock_resend:
            from backend.services.email_service import GraiderEmailer
            GraiderEmailer(config_path=str(tmp_path / "cfg.json"))
        assert mock_resend.api_key == "re_unquoted_xyz"

    def test_inner_break_after_finding_api_key(
        self, tmp_path, monkeypatch,
    ):
        # `break` at line 60 after finding RESEND_API_KEY= — first match wins
        monkeypatch.delenv("RESEND_API_KEY", raising=False)

        first_env = tmp_path / "first.env"
        first_env.write_text(
            "RESEND_API_KEY=first_value\n"
            "RESEND_API_KEY=second_value\n"
        )
        second_env = tmp_path / "missing.env"

        with self._patch_env_paths_to(first_env, second_env), \
             patch("backend.services.email_service.RESEND_AVAILABLE", True), \
             patch("backend.services.email_service.resend") as mock_resend:
            from backend.services.email_service import GraiderEmailer
            GraiderEmailer(config_path=str(tmp_path / "cfg.json"))
        assert mock_resend.api_key == "first_value"

    def test_falls_through_to_second_path_when_first_missing(
        self, tmp_path, monkeypatch,
    ):
        # First env path doesn't exist → loop continues to second path
        # which has the key. Pins the iteration through the env_paths list.
        monkeypatch.delenv("RESEND_API_KEY", raising=False)

        first_env = tmp_path / "missing-first.env"  # doesn't exist
        second_env = tmp_path / "second.env"
        second_env.write_text("RESEND_API_KEY=second_path_key\n")

        with self._patch_env_paths_to(first_env, second_env), \
             patch("backend.services.email_service.RESEND_AVAILABLE", True), \
             patch("backend.services.email_service.resend") as mock_resend:
            from backend.services.email_service import GraiderEmailer
            GraiderEmailer(config_path=str(tmp_path / "cfg.json"))
        assert mock_resend.api_key == "second_path_key"

    def test_resend_available_false_when_no_key_anywhere(
        self, tmp_path, monkeypatch,
    ):
        # Both env paths exist but neither has a RESEND_API_KEY line —
        # falls through to the `resend_available = False` branch at line 69.
        monkeypatch.delenv("RESEND_API_KEY", raising=False)

        first_env = tmp_path / "first.env"
        first_env.write_text("OTHER_VAR=irrelevant\n")
        second_env = tmp_path / "second.env"
        second_env.write_text("ALSO_IRRELEVANT=value\n")

        with self._patch_env_paths_to(first_env, second_env), \
             patch("backend.services.email_service.RESEND_AVAILABLE", True):
            from backend.services.email_service import GraiderEmailer
            emailer = GraiderEmailer(
                config_path=str(tmp_path / "cfg.json"),
            )
        assert emailer.resend_available is False
