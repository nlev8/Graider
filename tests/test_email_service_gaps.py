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

    Production walks two paths looking for `RESEND_API_KEY=...`:
      1. Path(__file__).parent.parent.parent / '.env'  (project root)
      2. Path.cwd() / '.env'

    The real project-root `.env` exists with a real key, so naive tests
    collide with it. Tests here use REAL Path objects: a fake project
    structure under `tmp_path` and `monkeypatch` of (a) the module's
    `__file__` so `.parent.parent.parent` traverses to the fake root,
    and (b) `monkeypatch.chdir` so `Path.cwd()` returns the fake cwd.

    PR #274 Gemini round-1 MAJOR fold: the prior `_StubPath` approach
    short-circuited path traversal (`.parent` → self) and ignored the
    operand of `/ '.env'`, so production regressions like dropping a
    `.parent` or changing the filename would still pass.
    """

    @staticmethod
    def _make_fake_layout(tmp_path):
        """Set up a fake project root + cwd structure under tmp_path.

        Returns (project_root, cwd, module_file) — module_file is positioned
        3 directories deep so `Path(module_file).parent.parent.parent`
        resolves to project_root via real pathlib traversal.
        """
        project_root = tmp_path / "fake_root"
        cwd = tmp_path / "fake_cwd"
        # Production calls Path(__file__).parent.parent.parent — needs 3
        # levels of directory above the module file
        module_dir = project_root / "backend" / "services"
        module_dir.mkdir(parents=True)
        cwd.mkdir()
        module_file = module_dir / "email_service.py"
        module_file.write_text("# fake module")
        return project_root, cwd, module_file

    def test_loads_api_key_from_env_file_when_env_var_absent(
        self, tmp_path, monkeypatch,
    ):
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        project_root, cwd, module_file = self._make_fake_layout(tmp_path)

        # Place the .env at the project root (first path checked)
        (project_root / ".env").write_text(
            "OTHER_VAR=ignored\n"
            'RESEND_API_KEY="re_test_abcd_1234"\n'
            "ANOTHER=also_ignored\n"
        )

        # Real Path.cwd() returns fake_cwd; module __file__ resolves so
        # .parent.parent.parent → project_root.
        monkeypatch.chdir(cwd)
        with patch("backend.services.email_service.__file__", str(module_file)), \
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
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        project_root, cwd, module_file = self._make_fake_layout(tmp_path)

        (project_root / ".env").write_text(
            "RESEND_API_KEY='re_singly_quoted'\n"
        )
        monkeypatch.chdir(cwd)
        with patch("backend.services.email_service.__file__", str(module_file)), \
             patch("backend.services.email_service.RESEND_AVAILABLE", True), \
             patch("backend.services.email_service.resend") as mock_resend:
            from backend.services.email_service import GraiderEmailer
            GraiderEmailer(config_path=str(tmp_path / "cfg.json"))
        assert mock_resend.api_key == "re_singly_quoted"

    def test_strips_unquoted_env_file_value(
        self, tmp_path, monkeypatch,
    ):
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        project_root, cwd, module_file = self._make_fake_layout(tmp_path)

        (project_root / ".env").write_text("RESEND_API_KEY=re_unquoted_xyz\n")
        monkeypatch.chdir(cwd)
        with patch("backend.services.email_service.__file__", str(module_file)), \
             patch("backend.services.email_service.RESEND_AVAILABLE", True), \
             patch("backend.services.email_service.resend") as mock_resend:
            from backend.services.email_service import GraiderEmailer
            GraiderEmailer(config_path=str(tmp_path / "cfg.json"))
        assert mock_resend.api_key == "re_unquoted_xyz"

    def test_inner_break_after_finding_api_key(
        self, tmp_path, monkeypatch,
    ):
        # `break` at line 60 — first match wins inside a single .env file
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        project_root, cwd, module_file = self._make_fake_layout(tmp_path)

        (project_root / ".env").write_text(
            "RESEND_API_KEY=first_value\n"
            "RESEND_API_KEY=second_value\n"
        )
        monkeypatch.chdir(cwd)
        with patch("backend.services.email_service.__file__", str(module_file)), \
             patch("backend.services.email_service.RESEND_AVAILABLE", True), \
             patch("backend.services.email_service.resend") as mock_resend:
            from backend.services.email_service import GraiderEmailer
            GraiderEmailer(config_path=str(tmp_path / "cfg.json"))
        assert mock_resend.api_key == "first_value"

    def test_falls_through_to_cwd_env_when_project_root_missing(
        self, tmp_path, monkeypatch,
    ):
        # Project-root .env doesn't exist → loop continues to cwd/.env
        # which has the key. Real path traversal verifies both paths
        # are actually checked in the right order.
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        project_root, cwd, module_file = self._make_fake_layout(tmp_path)

        # NO .env at project_root; only at cwd
        (cwd / ".env").write_text("RESEND_API_KEY=cwd_path_key\n")

        monkeypatch.chdir(cwd)
        with patch("backend.services.email_service.__file__", str(module_file)), \
             patch("backend.services.email_service.RESEND_AVAILABLE", True), \
             patch("backend.services.email_service.resend") as mock_resend:
            from backend.services.email_service import GraiderEmailer
            GraiderEmailer(config_path=str(tmp_path / "cfg.json"))
        assert mock_resend.api_key == "cwd_path_key"

    def test_project_root_env_takes_precedence_over_cwd(
        self, tmp_path, monkeypatch,
    ):
        # Both env files exist with different keys. Project-root .env is
        # checked first → outer-loop break at line 61-62 prevents reading
        # cwd/.env. Pins the search-order contract.
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        project_root, cwd, module_file = self._make_fake_layout(tmp_path)

        (project_root / ".env").write_text("RESEND_API_KEY=root_key\n")
        (cwd / ".env").write_text("RESEND_API_KEY=cwd_key\n")

        monkeypatch.chdir(cwd)
        with patch("backend.services.email_service.__file__", str(module_file)), \
             patch("backend.services.email_service.RESEND_AVAILABLE", True), \
             patch("backend.services.email_service.resend") as mock_resend:
            from backend.services.email_service import GraiderEmailer
            GraiderEmailer(config_path=str(tmp_path / "cfg.json"))
        # Project root wins (first in env_paths list)
        assert mock_resend.api_key == "root_key"

    def test_resend_available_false_when_no_key_anywhere(
        self, tmp_path, monkeypatch,
    ):
        # Both .env files exist but neither has RESEND_API_KEY → falls
        # through to `resend_available = False` at line 69.
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        project_root, cwd, module_file = self._make_fake_layout(tmp_path)

        (project_root / ".env").write_text("OTHER_VAR=irrelevant\n")
        (cwd / ".env").write_text("ALSO_IRRELEVANT=value\n")

        monkeypatch.chdir(cwd)
        with patch("backend.services.email_service.__file__", str(module_file)), \
             patch("backend.services.email_service.RESEND_AVAILABLE", True):
            from backend.services.email_service import GraiderEmailer
            emailer = GraiderEmailer(
                config_path=str(tmp_path / "cfg.json"),
            )
        assert emailer.resend_available is False
