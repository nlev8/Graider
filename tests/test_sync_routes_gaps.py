"""Gap-fill unit tests for backend/routes/sync_routes.py.

Audit MAJOR #4 sprint follow-up to PR #295. Companion to existing
tests/test_sync_routes.py which covers the orchestration + provider
syncs. Targets the remaining 25 uncovered LOC (83% → ~100%).

Branches covered
* get_supabase exception fallback (lines 31-35) → returns None
* _discover_teachers no-SIS-configs early return (line 66)
* _discover_teachers JSON-string config parsing (lines 99-100)
* _discover_teachers no-eligible-after-filtering early return (line 110)
* _discover_teachers wrap-around with JSON-string configs (132-133)
* _discover_teachers outer except (152-154)
* _save_cursor exception swallow + sentry (159-163)
* _sync_one_teacher clever no-district-token skipped branch (183)
* _sync_one_teacher unknown provider branch (238)
* _sync_one_teacher outer except (262-266)
"""
from __future__ import annotations

import os
import json
from unittest.mock import patch, MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────
# get_supabase exception fallback (lines 31-35)
# ──────────────────────────────────────────────────────────────────


class TestGetSupabaseFallback:
    def test_returns_none_when_supabase_client_call_raises(self):
        # The except clause catches any Exception from either the
        # `from backend.supabase_client import ...` line or the
        # subsequent _get_sb() call. Easiest path: make the call raise.
        with patch(
            "backend.supabase_client.get_supabase",
            side_effect=RuntimeError("supabase init failed"),
        ):
            from backend.routes.sync_routes import get_supabase
            assert get_supabase() is None


# ──────────────────────────────────────────────────────────────────
# _discover_teachers branches
# ──────────────────────────────────────────────────────────────────


def _build_sb_mock(config_data, session_data=None, students_data=None):
    """Build a sb.table().select()....execute() chain mock that returns
    different data per .table() name."""
    sb = MagicMock()

    def table_side_effect(name):
        chain = MagicMock()
        if name == "teacher_data":
            chain.select.return_value.eq.return_value \
                .execute.return_value = MagicMock(data=config_data)
        elif name == "student_sessions":
            chain.select.return_value.gt.return_value \
                .execute.return_value = MagicMock(data=session_data or [])
        elif name == "students":
            chain.select.return_value.in_.return_value \
                .execute.return_value = MagicMock(data=students_data or [])
        return chain

    sb.table.side_effect = table_side_effect
    return sb


class TestDiscoverTeachersBranches:
    def test_no_supabase_returns_empty(self):
        from backend.routes import sync_routes as mod
        with patch.object(mod, "get_supabase", return_value=None):
            assert mod._discover_teachers() == []

    def test_no_sis_configs_returns_empty(self):
        from backend.routes import sync_routes as mod
        sb = _build_sb_mock(config_data=[])  # No teacher_data rows
        with patch.object(mod, "get_supabase", return_value=sb):
            assert mod._discover_teachers() == []

    def test_string_config_parsed_as_json(self):
        from backend.routes import sync_routes as mod
        # Config stored as a JSON string (not dict) → parsed inline
        config_data = [
            {
                "teacher_id": "t-1",
                "data": json.dumps({"provider": "oneroster",
                                    "client_id": "ci"}),
                "updated_at": "2099-01-01T00:00:00",  # very recent
            },
        ]
        sb = _build_sb_mock(config_data=config_data)
        with patch.object(mod, "get_supabase", return_value=sb), patch(
            "backend.routes.sync_routes.storage_load",
            return_value=None,
        ):
            result = mod._discover_teachers()
        assert len(result) == 1
        assert result[0]["teacher_id"] == "t-1"
        assert result[0]["provider"] == "oneroster"
        # Verifies the config was parsed from JSON string into dict
        assert result[0]["config"]["client_id"] == "ci"

    def test_no_eligible_after_filtering_returns_empty(self):
        from backend.routes import sync_routes as mod
        # Config exists but updated_at is OLD (>30 days) AND no
        # student sessions → no eligible teachers.
        old_ts = "2020-01-01T00:00:00+00:00"
        config_data = [
            {
                "teacher_id": "t-stale",
                "data": {"provider": "oneroster"},
                "updated_at": old_ts,
            },
        ]
        sb = _build_sb_mock(config_data=config_data, session_data=[])
        with patch.object(mod, "get_supabase", return_value=sb):
            assert mod._discover_teachers() == []

    def test_cursor_wraparound_with_string_config(self):
        from backend.routes import sync_routes as mod
        # Two teachers with JSON-string configs. cursor points past the
        # last teacher → wrap-around branch re-builds the eligible list
        # via the same json.loads path (lines 132-133).
        future_ts = "2099-01-01T00:00:00+00:00"
        config_data = [
            {
                "teacher_id": "t-a",
                "data": json.dumps({"provider": "clever"}),
                "updated_at": future_ts,
            },
            {
                "teacher_id": "t-b",
                "data": json.dumps({"provider": "oneroster"}),
                "updated_at": future_ts,
            },
        ]
        sb = _build_sb_mock(config_data=config_data)

        # Cursor "t-z" is past everyone → triggers wrap-around (line 122)
        with patch.object(mod, "get_supabase", return_value=sb), patch(
            "backend.routes.sync_routes.storage_load",
            return_value={"last_teacher_id": "t-z"},
        ):
            result = mod._discover_teachers()
        # Wrap-around returns BOTH teachers via the rebuild loop
        ids = [t["teacher_id"] for t in result]
        assert "t-a" in ids
        assert "t-b" in ids

    def test_outer_exception_swallowed_returns_empty(self):
        from backend.routes import sync_routes as mod
        # Force the supabase chain to raise — outer except returns []
        sb = MagicMock()
        sb.table.side_effect = RuntimeError("supabase down")
        with patch.object(mod, "get_supabase", return_value=sb):
            # Must not raise; falls through to except
            assert mod._discover_teachers() == []


# ──────────────────────────────────────────────────────────────────
# _save_cursor (lines 159-163)
# ──────────────────────────────────────────────────────────────────


class TestSaveCursor:
    def test_save_cursor_failure_swallowed_with_sentry(self):
        from backend.routes import sync_routes as mod
        with patch(
            "backend.routes.sync_routes.storage_save",
            side_effect=RuntimeError("storage down"),
        ), patch(
            "backend.routes.sync_routes.sentry_sdk.capture_exception",
        ) as sentry_mock:
            # Must not raise
            mod._save_cursor("teacher-99")
        assert sentry_mock.called


# ──────────────────────────────────────────────────────────────────
# _sync_one_teacher branches
# ──────────────────────────────────────────────────────────────────


class TestSyncOneTeacherBranches:
    def test_clever_missing_district_token_skipped(self, monkeypatch):
        from backend.routes import sync_routes as mod
        # No district_token in config AND no env var → skipped result
        monkeypatch.delenv("CLEVER_DISTRICT_TOKEN", raising=False)
        teacher = {
            "teacher_id": "t-1",
            "provider": "clever",
            "config": {},  # No district_token
        }
        result = mod._sync_one_teacher(teacher)
        assert result["status"] == "skipped"
        assert "No Clever district token" in result["error"]
        assert "duration_s" in result

    def test_unknown_provider_skipped(self):
        from backend.routes import sync_routes as mod
        teacher = {
            "teacher_id": "t-x",
            "provider": "powerschool",  # not clever or oneroster
            "config": {},
        }
        result = mod._sync_one_teacher(teacher)
        assert result["status"] == "skipped"
        assert "Unknown provider" in result["error"]

    def test_outer_exception_returns_failed(self):
        from backend.routes import sync_routes as mod
        # Provider is clever, district_token present, but the
        # `clever_sync_roster` import raises → outer except.
        teacher = {
            "teacher_id": "t-fail",
            "provider": "clever",
            "config": {"district_token": "tok"},
        }
        with patch(
            "backend.clever.sync_roster",
            side_effect=RuntimeError("clever api dead"),
        ):
            result = mod._sync_one_teacher(teacher)
        assert result["status"] == "failed"
        assert "clever api dead" in result["error"]
        assert "duration_s" in result
