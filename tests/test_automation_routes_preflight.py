"""
Cross-tenant credential preflight regression tests for automation routes.

Codex round-5 (PR #246) caught that `g` was not imported at module scope
in `backend/routes/automation_routes.py`, so the `getattr(g, 'user_id', ...)`
calls in `run_automation` and `start_picker` raised `NameError` → 500
instead of the intended 400 missing-creds response. `start_picker` also
left `_picker_state["status"] = "picking"` on the failed path, wedging
the next picker call at 409.

These tests pin both behaviors so a future re-import omission can't
silently regress the multi-tenant credential isolation contract.
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest


@pytest.fixture
def flask_app(tmp_path, monkeypatch):
    """Minimal Flask app wrapping automation_bp with g.user_id set."""
    from flask import Flask, g

    import backend.routes.automation_routes as auto_mod
    monkeypatch.setattr(auto_mod, "AUTOMATIONS_DIR", str(tmp_path))
    # Reset state between tests
    auto_mod._run_state.update({"status": "idle", "process": None, "log": []})
    auto_mod._picker_state.update({"status": "idle", "process": None, "events": []})

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.secret_key = "test-secret"

    @app.before_request
    def _set_user_id():
        g.user_id = "teacher-alice"

    app.register_blueprint(auto_mod.automation_bp)
    return app, auto_mod, tmp_path


# ──────────────────────────────────────────────────────────────────
# run_automation: missing creds → 400 (not 500), state stays idle
# ──────────────────────────────────────────────────────────────────


class TestRunAutomationCredsPreflight:
    def _write_workflow(self, tmp_path, workflow_id="test-wf"):
        # audit #8: run_automation reads the per-teacher subdir
        # (_teacher_automations_dir). The fixture's teacher is "teacher-alice",
        # so the workflow must live there for run to reach the creds preflight.
        tdir = tmp_path / "teacher-alice"
        tdir.mkdir(exist_ok=True)
        wf_path = tdir / f"{workflow_id}.json"
        wf_path.write_text(json.dumps({"id": workflow_id, "steps": []}))
        return workflow_id

    def test_missing_creds_returns_400_not_500(self, flask_app):
        app, auto_mod, tmp_path = flask_app
        wf_id = self._write_workflow(tmp_path)

        with patch("backend.routes.assistant_routes.write_temp_creds_file",
                   return_value=False):
            client = app.test_client()
            resp = client.post(f"/api/automations/{wf_id}/run", json={})

        assert resp.status_code == 400, (
            f"Expected 400 missing-creds, got {resp.status_code} "
            f"(probably NameError on `g` → 500). Body: {resp.get_data(as_text=True)}"
        )
        body = resp.get_json()
        assert "VPortal credentials" in body.get("error", "")

    def test_missing_creds_leaves_run_state_idle(self, flask_app):
        """Preflight runs BEFORE _run_state mutation, so a 400 here must
        leave _run_state["status"] == "idle" (next call must not 409)."""
        app, auto_mod, tmp_path = flask_app
        wf_id = self._write_workflow(tmp_path)

        with patch("backend.routes.assistant_routes.write_temp_creds_file",
                   return_value=False):
            client = app.test_client()
            client.post(f"/api/automations/{wf_id}/run", json={})

        assert auto_mod._run_state["status"] == "idle", (
            "_run_state stuck at "
            f"{auto_mod._run_state['status']!r} after 400 — next call would 409"
        )

    def test_can_retry_after_missing_creds_400(self, flask_app):
        """End-to-end: a 400 missing-creds response must leave the
        endpoint retryable. Second call (still missing creds) returns 400,
        not 409 'already running'."""
        app, auto_mod, tmp_path = flask_app
        wf_id = self._write_workflow(tmp_path)

        with patch("backend.routes.assistant_routes.write_temp_creds_file",
                   return_value=False):
            client = app.test_client()
            r1 = client.post(f"/api/automations/{wf_id}/run", json={})
            r2 = client.post(f"/api/automations/{wf_id}/run", json={})

        assert r1.status_code == 400
        assert r2.status_code == 400, (
            f"Second call returned {r2.status_code} (likely 409 "
            "'already running'); preflight must not leave state stuck."
        )


# ──────────────────────────────────────────────────────────────────
# start_picker: auto_login=True missing creds → 400 + state rollback
# ──────────────────────────────────────────────────────────────────


class TestStartPickerCredsPreflight:
    def test_missing_creds_with_login_returns_400_not_500(self, flask_app):
        app, auto_mod, _ = flask_app

        with patch("backend.routes.assistant_routes.write_temp_creds_file",
                   return_value=False):
            client = app.test_client()
            resp = client.post(
                "/api/automations/picker/start",
                json={"url": "https://example.com", "login": True},
            )

        assert resp.status_code == 400, (
            f"Expected 400, got {resp.status_code} "
            f"(probably NameError on `g` → 500). Body: {resp.get_data(as_text=True)}"
        )
        body = resp.get_json()
        assert "VPortal credentials" in body.get("error", "")

    def test_missing_creds_rolls_back_picker_state_to_idle(self, flask_app):
        """start_picker sets _picker_state["status"]="picking" before the
        preflight, then rolls back to "idle" on the 400 path. Without
        rollback, the next picker call would 409."""
        app, auto_mod, _ = flask_app

        with patch("backend.routes.assistant_routes.write_temp_creds_file",
                   return_value=False):
            client = app.test_client()
            client.post(
                "/api/automations/picker/start",
                json={"url": "https://example.com", "login": True},
            )

        assert auto_mod._picker_state["status"] == "idle", (
            "_picker_state stuck at "
            f"{auto_mod._picker_state['status']!r} after 400 — next call would 409"
        )

    def test_can_retry_after_missing_creds_400(self, flask_app):
        app, auto_mod, _ = flask_app

        with patch("backend.routes.assistant_routes.write_temp_creds_file",
                   return_value=False):
            client = app.test_client()
            r1 = client.post(
                "/api/automations/picker/start",
                json={"url": "https://example.com", "login": True},
            )
            r2 = client.post(
                "/api/automations/picker/start",
                json={"url": "https://example.com", "login": True},
            )

        assert r1.status_code == 400
        assert r2.status_code == 400, (
            f"Second call returned {r2.status_code} (likely 409 "
            "'Picker already running'); state rollback must keep it retryable."
        )

    def test_no_login_skips_creds_preflight(self, flask_app, monkeypatch):
        """When auto_login=False, picker.js skips loadCredentials() entirely
        — the preflight should NOT run, even when creds are missing."""
        app, auto_mod, _ = flask_app

        # Stub Popen so we don't actually launch picker.js
        with patch("backend.routes.automation_routes.subprocess.Popen") as mock_popen, \
             patch("backend.routes.assistant_routes.write_temp_creds_file",
                   return_value=False) as mock_write, \
             patch("os.path.exists", return_value=True):
            mock_popen.return_value.stdout = iter([])
            client = app.test_client()
            resp = client.post(
                "/api/automations/picker/start",
                json={"url": "https://example.com", "login": False},
            )

        # Should have launched (status 200 picker_started), NOT 400
        assert resp.status_code == 200, (
            f"login=False should skip creds preflight; got {resp.status_code}"
        )
        # write_temp_creds_file should NOT have been called
        mock_write.assert_not_called()
