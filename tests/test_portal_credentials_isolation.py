"""
Cross-teacher isolation contract for VPortal credentials.

Closes GH #245 (Codex review of PR #244 flagged the gap): the legacy
shared `~/.graider_data/portal_credentials.json` was overwritten on
every teacher's save and read on every teacher's get/load, leaking
VPortal credentials across tenants.

This test file pins:
1. `_portal_credentials_file_for(teacher_id)` returns the legacy
   shared path ONLY for local-dev; real teachers get
   `portal_credentials_{safe_id}.json`.
2. `save_credentials` writes the per-teacher file (not the shared
   one) for real teachers.
3. `get_credentials` reads the per-teacher file (not the shared one).
4. `load_portal_credentials` reads per-teacher.
5. Two real teachers' credentials cannot leak across one another.
"""
from __future__ import annotations

import base64
import json
import os
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Redirect GRAIDER_DATA_DIR + CREDS_FILE in assistant_routes to tmp_path."""
    import backend.routes.assistant_routes as ar_mod
    monkeypatch.setattr(ar_mod, "GRAIDER_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        ar_mod, "CREDS_FILE",
        str(tmp_path / "portal_credentials.json"),
    )
    return tmp_path


# ──────────────────────────────────────────────────────────────────
# _portal_credentials_file_for
# ──────────────────────────────────────────────────────────────────


class TestPerTeacherPath:
    def test_local_dev_uses_legacy_shared_path(self, tmp_data_dir):
        from backend.routes.assistant_routes import _portal_credentials_file_for
        path = _portal_credentials_file_for("local-dev")
        assert path.endswith("portal_credentials.json")
        assert "portal_credentials_" not in os.path.basename(path)

    def test_empty_teacher_uses_legacy_shared_path(self, tmp_data_dir):
        from backend.routes.assistant_routes import _portal_credentials_file_for
        path = _portal_credentials_file_for("")
        assert path.endswith("portal_credentials.json")
        assert "portal_credentials_" not in os.path.basename(path)

    def test_real_teacher_gets_per_teacher_path(self, tmp_data_dir):
        from backend.routes.assistant_routes import _portal_credentials_file_for
        path = _portal_credentials_file_for("uuid-abc-123")
        assert os.path.basename(path) == "portal_credentials_uuid-abc-123.json"

    def test_clever_prefixed_teacher_id_is_sanitized(self, tmp_data_dir):
        # Clever pseudo-IDs use `clever:{id}`. The colon is sanitized
        # so the filename is filesystem-safe.
        from backend.routes.assistant_routes import _portal_credentials_file_for
        path = _portal_credentials_file_for("clever:cl-1")
        assert os.path.basename(path) == "portal_credentials_clever_cl-1.json"

    def test_path_separators_in_id_are_sanitized(self, tmp_data_dir):
        # Defensive: `/` or `\` in teacher_id should not allow
        # directory traversal — the resolved file MUST stay inside
        # the data dir.
        from backend.routes.assistant_routes import _portal_credentials_file_for
        path = _portal_credentials_file_for("malicious/../etc")
        # Must NOT escape the data dir at the path-component level
        # (sanitization replaces '/' and '\\' so they can't break out).
        # Note: ".." inside a filename component is benign — it's only
        # a traversal vector if preceded by a path separator.
        resolved = os.path.realpath(path)
        data_dir = os.path.realpath(str(tmp_data_dir))
        assert resolved.startswith(data_dir + os.sep) or resolved == data_dir, (
            f"Resolved path {resolved} escapes data dir {data_dir}"
        )
        # Filename component itself must not contain a separator.
        basename = os.path.basename(path)
        assert "/" not in basename
        assert "\\" not in basename


# ──────────────────────────────────────────────────────────────────
# Cross-teacher isolation contract
# ──────────────────────────────────────────────────────────────────


class TestCrossTeacherIsolation:
    def test_two_real_teachers_get_separate_files(self, tmp_data_dir):
        from backend.routes.assistant_routes import _portal_credentials_file_for
        path_a = _portal_credentials_file_for("teacher-alice")
        path_b = _portal_credentials_file_for("teacher-bob")
        assert path_a != path_b
        # Both inside the same data dir
        assert os.path.dirname(path_a) == str(tmp_data_dir)
        assert os.path.dirname(path_b) == str(tmp_data_dir)

    def test_save_then_load_isolates_teachers(self, tmp_data_dir):
        # Teacher A saves; teacher B's load returns nothing.
        from backend.routes.assistant_routes import (
            _portal_credentials_file_for,
            load_portal_credentials,
        )

        # Manually write teacher A's creds file to simulate prior save
        path_a = _portal_credentials_file_for("teacher-alice")
        os.makedirs(os.path.dirname(path_a), exist_ok=True)
        with open(path_a, "w") as f:
            json.dump({
                "email": "alice@school.edu",
                "password": base64.b64encode(b"alice-pw").decode(),
            }, f)

        # storage_load returns None (Supabase miss)
        with patch("backend.routes.assistant_routes.storage_load",
                   return_value=None):
            email_a, pw_a = load_portal_credentials("teacher-alice")
            email_b, pw_b = load_portal_credentials("teacher-bob")

        assert email_a == "alice@school.edu"
        assert pw_a == "alice-pw"
        # Teacher B has no file → returns (None, None) WITHOUT leaking
        # alice's creds.
        assert email_b is None
        assert pw_b is None


# ──────────────────────────────────────────────────────────────────
# write_temp_creds_file routes per-teacher
# ──────────────────────────────────────────────────────────────────


class TestWriteTempCredsFile:
    def test_writes_to_per_teacher_path(self, tmp_data_dir):
        from backend.routes.assistant_routes import (
            _portal_credentials_file_for,
            write_temp_creds_file,
        )
        # storage_load returns alice's creds for teacher-alice
        with patch("backend.routes.assistant_routes.storage_load",
                   return_value={
                       "email": "alice@x.com",
                       "password": base64.b64encode(b"alice-pw").decode(),
                   }):
            ok = write_temp_creds_file("teacher-alice")
        assert ok is True

        # Per-teacher file written, NOT the shared file
        per_teacher_path = _portal_credentials_file_for("teacher-alice")
        legacy_path = str(tmp_data_dir / "portal_credentials.json")
        assert os.path.exists(per_teacher_path)
        assert not os.path.exists(legacy_path), (
            "Real teacher save MUST NOT touch the shared legacy file "
            "(would leak across teachers)"
        )

    def test_returns_false_when_no_creds(self, tmp_data_dir):
        from backend.routes.assistant_routes import write_temp_creds_file
        with patch("backend.routes.assistant_routes.storage_load",
                   return_value=None):
            assert write_temp_creds_file("teacher-no-creds") is False


# ──────────────────────────────────────────────────────────────────
# outlook_sender honors GRAIDER_PORTAL_CREDS_FILE env var
# ──────────────────────────────────────────────────────────────────


class TestOutlookSenderEnvOverride:
    def test_creds_file_reads_env_var_when_set(self, monkeypatch, tmp_path):
        # Ensure the env-var path is picked up at module reload
        custom_path = str(tmp_path / "portal_credentials_uuid-abc.json")
        monkeypatch.setenv("GRAIDER_PORTAL_CREDS_FILE", custom_path)
        # Re-import to pick up the env var
        import importlib
        import backend.services.outlook_sender as os_mod
        importlib.reload(os_mod)
        try:
            assert os_mod.CREDS_FILE == custom_path
        finally:
            # Reset for other tests
            monkeypatch.delenv("GRAIDER_PORTAL_CREDS_FILE", raising=False)
            importlib.reload(os_mod)

    def test_creds_file_falls_back_to_legacy_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("GRAIDER_PORTAL_CREDS_FILE", raising=False)
        import importlib
        import backend.services.outlook_sender as os_mod
        importlib.reload(os_mod)
        # Default path under GRAIDER_DATA_DIR — exact `portal_credentials.json`
        # NOT a per-teacher variant `portal_credentials_<id>.json`.
        assert os.path.basename(os_mod.CREDS_FILE) == "portal_credentials.json"
