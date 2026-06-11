"""Regression tests for issue #353 (Resolution B) — shard local-file
storage by teacher_id so concurrent dev-shim teachers don't share state.

Pre-fix, `backend/storage.py::_key_to_filepath` returned hardcoded paths
under `~/` regardless of `teacher_id`. With Supabase unconfigured (the
default in CI), `_use_supabase(teacher_id)` returned False for every
teacher_id and the file backend wrote to the same `~/.graider_*` files
for everyone. This was the "concurrency theater" Codex flagged in the
Phase 2 load-test review and the same race blocking `multi-teacher.spec.js:22`
(issue #370 part 2, consolidated here).

Post-fix:
- `teacher_id='local-dev'` still routes to the global `~/.graider_*`
  layout (zero behavioral change for the canonical single-tenant path).
- Any non-`'local-dev'` teacher_id routes to a sanitized per-tenant
  subdirectory `~/.graider_tenants/<safe_id>/` so two teachers never
  share files.
- `auth_routes.py::approval_status` no longer 500s for dev-shim
  teacher_ids — it bypasses the Supabase user lookup the same way it
  bypassed for `'local-dev'`.
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Redirect `backend.storage.HOME` (captured at import time) to
    tmp_path so every test gets a clean filesystem."""
    from backend import storage as st

    monkeypatch.setenv("HOME", str(tmp_path))
    new_home = str(tmp_path)
    monkeypatch.setattr(st, "HOME", new_home)
    monkeypatch.setattr(
        st, "ASSIGNMENTS_DIR", os.path.join(new_home, ".graider_assignments"),
    )
    monkeypatch.setattr(
        st, "GRAIDER_DATA_DIR", os.path.join(new_home, ".graider_data"),
    )
    monkeypatch.setattr(
        st, "PERIODS_DIR",
        os.path.join(new_home, ".graider_data", "periods"),
    )
    monkeypatch.setattr(
        st, "ACCOMMODATIONS_DIR",
        os.path.join(new_home, ".graider_data", "accommodations"),
    )
    monkeypatch.setattr(
        st, "LESSONS_DIR", os.path.join(new_home, ".graider_lessons"),
    )
    monkeypatch.setattr(
        st, "STUDENT_HISTORY_DIR",
        os.path.join(new_home, ".graider_data", "student_history"),
    )
    monkeypatch.setattr(
        st, "RESOURCES_DIR",
        os.path.join(new_home, ".graider_data", "resources"),
    )
    # Force the file backend regardless of dev-machine Supabase env vars
    monkeypatch.setattr(st, "_is_supabase_configured", lambda: False)
    return tmp_path


# ──────────────────────────────────────────────────────────────────
# Storage: local-dev unchanged (backward-compat sanity)
# ──────────────────────────────────────────────────────────────────


class TestLocalDevUnshardedLayoutUnchanged:
    """`local-dev` must keep the historical unsharded layout."""

    def test_local_dev_settings_uses_global_path(self, isolated_home):
        from backend.storage import _key_to_filepath

        p = _key_to_filepath("settings", teacher_id="local-dev")
        assert p == os.path.join(isolated_home, ".graider_settings.json")

    def test_local_dev_default_teacher_id_uses_global_path(
        self, isolated_home,
    ):
        # Existing callers that pass no teacher_id should still get the
        # global path.
        from backend.storage import _key_to_filepath

        p = _key_to_filepath("settings")
        assert p == os.path.join(isolated_home, ".graider_settings.json")

    def test_local_dev_save_load_roundtrip_unchanged(self, isolated_home):
        from backend.storage import save, load

        save("settings", {"key": "v"}, teacher_id="local-dev")
        loaded = load("settings", teacher_id="local-dev")
        assert loaded == {"key": "v"}
        # Verify physical path is the global one
        assert (isolated_home / ".graider_settings.json").exists()


# ──────────────────────────────────────────────────────────────────
# Storage: non-local-dev shards under a per-tenant subdir
# ──────────────────────────────────────────────────────────────────


class TestNonLocalDevShardsByTeacherId:
    def test_settings_under_tenant_subdir(self, isolated_home):
        from backend.storage import _key_to_filepath

        p = _key_to_filepath("settings", teacher_id="teach-A")
        assert ".graider_tenants" in p, (
            f"expected per-tenant subdir in path, got {p}"
        )
        assert "teach-A" in p, (
            f"expected teacher_id in path, got {p}"
        )
        # local-dev path is NOT what we get
        local_dev_path = _key_to_filepath("settings", teacher_id="local-dev")
        assert p != local_dev_path

    def test_two_teachers_get_distinct_paths(self, isolated_home):
        from backend.storage import _key_to_filepath

        keys = [
            "settings", "rubric", "results", "accommodations",
            "ell_students", "parent_contacts",
            "assignment:Quiz1", "lesson:U1:Day1",
            "period:P1.csv", "resource:res-1",
        ]
        for k in keys:
            p_a = _key_to_filepath(k, teacher_id="teach-A")
            p_b = _key_to_filepath(k, teacher_id="teach-B")
            assert p_a != p_b, (
                f"key {k!r} shared a path across teachers: {p_a}"
            )

    def test_teacher_id_sanitized_for_filesystem_safety(self, isolated_home):
        """Path-traversal attempts in teacher_id must not escape the
        tenant root — same defense as `_safe_style_name`."""
        from backend.storage import _key_to_filepath

        evil = "../../../etc"
        p = _key_to_filepath("settings", teacher_id=evil)
        # The dangerous chars must not appear literally in the resolved
        # path; the sanitizer should replace them with underscores.
        assert "/../" not in p, (
            f"path-traversal not sanitized: {p}"
        )
        # And the path must still be under HOME
        assert p.startswith(str(isolated_home)), (
            f"resolved path escapes HOME: {p}"
        )

    def test_save_load_isolated_across_teachers(self, isolated_home):
        from backend.storage import save, load

        save("settings", {"by": "A"}, teacher_id="teach-A")
        save("settings", {"by": "B"}, teacher_id="teach-B")

        assert load("settings", teacher_id="teach-A") == {"by": "A"}
        assert load("settings", teacher_id="teach-B") == {"by": "B"}
        # local-dev never wrote — must be None
        assert load("settings", teacher_id="local-dev") is None

    def test_delete_one_tenant_doesnt_affect_other(self, isolated_home):
        from backend.storage import save, load, delete

        save("settings", {"by": "A"}, teacher_id="teach-A")
        save("settings", {"by": "B"}, teacher_id="teach-B")

        delete("settings", teacher_id="teach-A")

        assert load("settings", teacher_id="teach-A") is None
        assert load("settings", teacher_id="teach-B") == {"by": "B"}

    def test_list_keys_isolated_across_teachers(self, isolated_home):
        from backend.storage import save, list_keys

        save("assignment:QuizA", {"x": 1}, teacher_id="teach-A")
        save("assignment:QuizB", {"y": 2}, teacher_id="teach-B")

        keys_a = list_keys("assignment:", teacher_id="teach-A")
        keys_b = list_keys("assignment:", teacher_id="teach-B")

        assert "assignment:QuizA" in keys_a
        assert "assignment:QuizB" not in keys_a
        assert "assignment:QuizB" in keys_b
        assert "assignment:QuizA" not in keys_b

    def test_student_history_isolated_across_teachers(self, isolated_home):
        from backend.storage import save_student_history, load_student_history

        save_student_history(
            teacher_id="teach-A", student_id="sid-1",
            history={"by": "A"},
        )
        save_student_history(
            teacher_id="teach-B", student_id="sid-1",  # same sid
            history={"by": "B"},
        )

        assert load_student_history(
            teacher_id="teach-A", student_id="sid-1",
        ) == {"by": "A"}
        assert load_student_history(
            teacher_id="teach-B", student_id="sid-1",
        ) == {"by": "B"}


# ──────────────────────────────────────────────────────────────────
# Auth: approval_status bypass for dev-shim teacher_ids
# ──────────────────────────────────────────────────────────────────


class TestApprovalStatusDevShimBypass:
    """`/api/auth/approval-status` was bypassing only for literal
    `'local-dev'`. When `X-Test-Teacher-Id: teach-A` was injected
    (per the dev-shim at `backend/auth.py:185-190`), the route called
    `sb.auth.admin.get_user_by_id('teach-A')` which 500'd in CI (no
    Supabase configured). Post-fix any dev-shim teacher_id is treated
    as approved."""

    @pytest.fixture
    def client(self):
        from backend.app import app
        from backend.extensions import limiter
        try:
            limiter.reset()
        except Exception:  # noqa: BLE001  # broad catch: best-effort, failure tolerated
            pass
        with app.test_client() as c:
            yield c

    @pytest.fixture(autouse=True)
    def dev_env(self, monkeypatch):
        monkeypatch.setenv("FLASK_ENV", "development")
        # Note: `backend/app.py` calls `load_dotenv(..., override=True)`
        # at import time, so `monkeypatch.setenv("DEV_USER_ID", ...)`
        # would be clobbered by the dev machine's .env. Every test below
        # sends `X-Test-Teacher-Id` explicitly to bypass the DEV_USER_ID
        # env fallback at `auth.py:187`, matching how the load harness
        # and `multi-teacher.spec.js` actually drive the API.

    def test_local_dev_still_approved(self, client):
        """Backward-compat: the literal 'local-dev' value still works."""
        resp = client.get(
            "/api/auth/approval-status",
            headers={"X-Test-Teacher-Id": "local-dev"},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get("approved") is True, (
            f"expected approved=True, got body={body}"
        )

    def test_non_local_dev_dev_shim_id_also_approved(self, client):
        """Was 500: `sb.auth.admin.get_user_by_id('teach-A')` on None
        Supabase. Now: dev-shim teacher_id is recognized as 'developer
        testing' and approved without hitting Supabase."""
        resp = client.get(
            "/api/auth/approval-status",
            headers={"X-Test-Teacher-Id": "teach-A"},
        )
        assert resp.status_code == 200, (
            f"dev-shim teacher_id should bypass Supabase user lookup; "
            f"got {resp.status_code}: {resp.get_data(as_text=True)[:200]}"
        )
        body = resp.get_json()
        assert body.get("approved") is True, (
            f"expected approved=True for dev-shim teacher_id, got body={body}"
        )
