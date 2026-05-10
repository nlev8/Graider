"""Unit tests for backend/routes/automation_routes.py.

Audit MAJOR #4 sprint follow-up to PR #288. Targets the 159 uncovered
LOC (42% baseline). Companion to test_automation_routes_preflight.py
which already pins the per-teacher credential preflight contract.

Module has 13 endpoints + 2 helpers:
* CRUD (4): list/get/save/delete /api/automations
* Templates (3): list/get/delete /api/automations/templates
* Run (3): /api/automations/<id>/run, /run/status, /run/stop
* Picker (3): /picker/start, /picker/events, /picker/stop
* Helpers: _read_runner_output, _read_picker_output

Strategy
--------
A minimal Flask app fixture (mirroring test_automation_routes_preflight.py)
wraps `automation_bp` with `g.user_id` populated. Module-level paths
(AUTOMATIONS_DIR, TEMPLATES_DIR, RUNNER_SCRIPT, PICKER_SCRIPT) are
monkeypatched to tmp_path. _run_state and _picker_state are reset to
idle in every test to prevent cross-test pollution. subprocess.Popen
and threading.Thread are mocked so no real processes spawn.

Helpers are exercised directly with a mock proc whose .stdout iterates
over canned NDJSON lines.

write_temp_creds_file mocked to return True for the run/picker happy
paths so we don't depend on the credentials infrastructure here
(preflight tests already cover the False/missing-creds branch).
"""
from __future__ import annotations

import json
import threading
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def flask_app(tmp_path, monkeypatch):
    """Minimal Flask app + automation blueprint, with isolated tmp dirs."""
    from flask import Flask, g

    import backend.routes.automation_routes as auto_mod

    automations_dir = tmp_path / "automations"
    templates_dir = tmp_path / "templates"
    runner_script = tmp_path / "runner.js"
    picker_script = tmp_path / "picker.js"
    automations_dir.mkdir()
    templates_dir.mkdir()
    # Default: scripts exist so happy-path tests pass; missing-script
    # tests delete them before posting.
    runner_script.write_text("// stub")
    picker_script.write_text("// stub")

    monkeypatch.setattr(auto_mod, "AUTOMATIONS_DIR", str(automations_dir))
    monkeypatch.setattr(auto_mod, "TEMPLATES_DIR", str(templates_dir))
    monkeypatch.setattr(auto_mod, "RUNNER_SCRIPT", str(runner_script))
    monkeypatch.setattr(auto_mod, "PICKER_SCRIPT", str(picker_script))

    auto_mod._run_state.update({
        "process": None, "status": "idle",
        "workflow_name": "", "current_step": 0, "total_steps": 0,
        "step_label": "", "message": "", "log": [],
    })
    auto_mod._picker_state.update({
        "process": None, "status": "idle", "events": [],
    })

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.secret_key = "test-secret"

    @app.before_request
    def _set_user_id():
        g.user_id = "teacher-alice"

    app.register_blueprint(auto_mod.automation_bp)

    return {
        "app": app,
        "auto_mod": auto_mod,
        "automations_dir": automations_dir,
        "templates_dir": templates_dir,
        "runner_script": runner_script,
        "picker_script": picker_script,
    }


@pytest.fixture
def client(flask_app):
    return flask_app["app"].test_client()


# ──────────────────────────────────────────────────────────────────
# /api/automations (GET) — list_automations
# ──────────────────────────────────────────────────────────────────


class TestListAutomations:
    def test_empty_dir_returns_empty_list(self, client):
        resp = client.get("/api/automations")
        assert resp.status_code == 200
        assert resp.get_json() == {"workflows": []}

    def test_lists_workflows_with_metadata(self, flask_app, client):
        d = flask_app["automations_dir"]
        (d / "wf-a.json").write_text(json.dumps({
            "id": "wf-a", "name": "First",
            "description": "desc-a",
            "steps": [{"id": "s1"}, {"id": "s2"}],
            "updated_at": "2026-05-09T10:00:00",
        }))
        (d / "wf-b.json").write_text(json.dumps({
            "id": "wf-b", "name": "Second", "steps": [],
        }))
        resp = client.get("/api/automations")
        body = resp.get_json()
        assert len(body["workflows"]) == 2
        first = next(w for w in body["workflows"] if w["id"] == "wf-a")
        assert first["name"] == "First"
        assert first["description"] == "desc-a"
        assert first["step_count"] == 2
        assert first["updated_at"] == "2026-05-09T10:00:00"

    def test_skips_non_json_files(self, flask_app, client):
        d = flask_app["automations_dir"]
        (d / "ok.json").write_text(json.dumps({"name": "OK", "steps": []}))
        (d / "stray.txt").write_text("ignored")
        resp = client.get("/api/automations")
        assert len(resp.get_json()["workflows"]) == 1

    def test_corrupt_json_swallowed(self, flask_app, client):
        d = flask_app["automations_dir"]
        (d / "ok.json").write_text(json.dumps({"name": "OK", "steps": []}))
        (d / "broken.json").write_text("{ not valid")
        resp = client.get("/api/automations")
        # Only the parsable workflow survives; broken one logged + skipped
        assert len(resp.get_json()["workflows"]) == 1

    def test_filename_fallback_when_id_missing(self, flask_app, client):
        d = flask_app["automations_dir"]
        (d / "implicit-id.json").write_text(json.dumps({"name": "X"}))
        resp = client.get("/api/automations")
        wf = resp.get_json()["workflows"][0]
        assert wf["id"] == "implicit-id"


# ──────────────────────────────────────────────────────────────────
# /api/automations/<id> (GET) — get_automation
# ──────────────────────────────────────────────────────────────────


class TestGetAutomation:
    def test_returns_404_when_missing(self, client):
        resp = client.get("/api/automations/missing")
        assert resp.status_code == 404
        assert "not found" in resp.get_json()["error"].lower()

    def test_returns_workflow_json(self, flask_app, client):
        d = flask_app["automations_dir"]
        wf = {"id": "abc-123", "name": "Test", "steps": []}
        (d / "abc-123.json").write_text(json.dumps(wf))
        resp = client.get("/api/automations/abc-123")
        assert resp.status_code == 200
        assert resp.get_json() == wf

    def test_id_sanitization_strips_unsafe_chars(self, flask_app, client):
        # safe_id pattern is `re.sub(r'[^a-z0-9_-]', '', workflow_id)`,
        # so chars outside that set are stripped. (URL-traversal `/../`
        # is normalized by Flask routing BEFORE the handler runs, so
        # we exercise sanitization via uppercase/punctuation that
        # survives URL parsing.)
        d = flask_app["automations_dir"]
        (d / "abc.json").write_text('{"name": "honeypot"}')
        # "ABC" sanitizes to "" (uppercase stripped) → 404
        resp = client.get("/api/automations/ABC")
        assert resp.status_code == 404
        # "ab.c" sanitizes to "abc" → finds honeypot
        resp = client.get("/api/automations/ab.c")
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "honeypot"


# ──────────────────────────────────────────────────────────────────
# /api/automations (POST) — save_automation
# ──────────────────────────────────────────────────────────────────


class TestSaveAutomation:
    def test_no_name_returns_400(self, client):
        resp = client.post("/api/automations", json={})
        assert resp.status_code == 400
        assert "name required" in resp.get_json()["error"].lower()

    def test_empty_dict_returns_400(self, client):
        # `data = request.json; if not data or not data.get("name")` —
        # an empty dict is falsy in Python only when len==0; in fact
        # `bool({}) is False` so the `if not data` branch fires.
        resp = client.post("/api/automations", json={})
        assert resp.status_code == 400

    def test_auto_id_from_name(self, flask_app, client):
        resp = client.post(
            "/api/automations",
            json={"name": "My Workflow!", "steps": []},
        )
        body = resp.get_json()
        # Auto-id slugifies non-alphanumerics to '-' then strips trailing '-'
        assert body["id"] == "my-workflow"
        # Persisted file
        wf_path = flask_app["automations_dir"] / "my-workflow.json"
        assert wf_path.exists()
        wf = json.loads(wf_path.read_text())
        # Auto-fields populated
        assert wf["version"] == 1
        assert wf["created_at"]
        assert wf["updated_at"]

    def test_explicit_id_used(self, flask_app, client):
        resp = client.post(
            "/api/automations",
            json={"name": "X", "id": "custom-id", "steps": []},
        )
        assert resp.get_json()["id"] == "custom-id"

    def test_step_ids_auto_assigned(self, flask_app, client):
        resp = client.post(
            "/api/automations",
            json={
                "name": "stepy", "steps": [
                    {"action": "click"},        # no id → step-1
                    {"action": "type", "id": "explicit"},  # keep id
                    {"action": "wait"},         # no id → step-3
                ],
            },
        )
        wf_path = flask_app["automations_dir"] / "stepy.json"
        wf = json.loads(wf_path.read_text())
        assert wf["steps"][0]["id"] == "step-1"
        assert wf["steps"][1]["id"] == "explicit"
        assert wf["steps"][2]["id"] == "step-3"

    def test_existing_version_and_created_at_preserved(
        self, flask_app, client,
    ):
        resp = client.post(
            "/api/automations",
            json={
                "name": "v",
                "version": 7,
                "created_at": "2026-01-01T00:00:00",
                "steps": [],
            },
        )
        wf_path = flask_app["automations_dir"] / "v.json"
        wf = json.loads(wf_path.read_text())
        assert wf["version"] == 7
        assert wf["created_at"] == "2026-01-01T00:00:00"


# ──────────────────────────────────────────────────────────────────
# /api/automations/<id> (DELETE) — delete_automation
# ──────────────────────────────────────────────────────────────────


class TestDeleteAutomation:
    def test_idempotent_when_missing(self, client):
        resp = client.delete("/api/automations/never-existed")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "deleted"

    def test_removes_existing_file(self, flask_app, client):
        d = flask_app["automations_dir"]
        f = d / "doomed.json"
        f.write_text("{}")
        resp = client.delete("/api/automations/doomed")
        assert resp.status_code == 200
        assert not f.exists()


# ──────────────────────────────────────────────────────────────────
# /api/automations/templates — list_templates / get_template / delete_template
# ──────────────────────────────────────────────────────────────────


class TestTemplates:
    def test_list_templates_empty_returns_empty(self, client):
        resp = client.get("/api/automations/templates")
        assert resp.status_code == 200
        assert resp.get_json() == {"templates": []}

    def test_list_templates_no_dir_returns_empty(
        self, flask_app, client, monkeypatch,
    ):
        # Point TEMPLATES_DIR at a non-existent path
        monkeypatch.setattr(
            flask_app["auto_mod"], "TEMPLATES_DIR",
            str(flask_app["templates_dir"] / "no-such"),
        )
        resp = client.get("/api/automations/templates")
        assert resp.get_json() == {"templates": []}

    def test_list_templates_skips_non_json(self, flask_app, client):
        d = flask_app["templates_dir"]
        (d / "ok.json").write_text(json.dumps({
            "id": "tmpl-1", "name": "A", "steps": [{}, {}],
        }))
        (d / "stray.md").write_text("ignored")
        resp = client.get("/api/automations/templates")
        body = resp.get_json()
        assert len(body["templates"]) == 1
        assert body["templates"][0]["is_template"] is True
        assert body["templates"][0]["step_count"] == 2

    def test_list_templates_corrupt_json_swallowed(
        self, flask_app, client,
    ):
        d = flask_app["templates_dir"]
        (d / "ok.json").write_text(json.dumps({
            "id": "tmpl-1", "name": "A",
        }))
        (d / "broken.json").write_text("{ corrupt")
        resp = client.get("/api/automations/templates")
        assert len(resp.get_json()["templates"]) == 1

    def test_get_template_no_dir_returns_404(
        self, flask_app, client, monkeypatch,
    ):
        monkeypatch.setattr(
            flask_app["auto_mod"], "TEMPLATES_DIR",
            str(flask_app["templates_dir"] / "no-such"),
        )
        resp = client.get("/api/automations/templates/anything")
        assert resp.status_code == 404

    def test_get_template_not_found_returns_404(
        self, flask_app, client,
    ):
        d = flask_app["templates_dir"]
        (d / "tmpl-1.json").write_text(json.dumps({
            "id": "tmpl-1", "name": "A",
        }))
        resp = client.get("/api/automations/templates/missing-id")
        assert resp.status_code == 404

    def test_get_template_match_by_internal_id(self, flask_app, client):
        # Filename is "tmpl-x.json" but JSON `id` field is "tmpl-y" —
        # match should be done by JSON id, not filename.
        # Include a non-JSON stray to exercise the skip branch.
        d = flask_app["templates_dir"]
        (d / "tmpl-x.json").write_text(json.dumps({
            "id": "tmpl-y", "name": "Cross",
        }))
        (d / "stray.md").write_text("ignored by skip-non-json branch")
        resp = client.get("/api/automations/templates/tmpl-y")
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "Cross"

    def test_get_template_swallows_corrupt_json(self, flask_app, client):
        # Pin the get_template except-branch deterministically: the
        # ONLY file is broken.json. After listdir → except fires →
        # iteration ends → 404. (Order doesn't matter when there's
        # only one file.)
        d = flask_app["templates_dir"]
        (d / "broken.json").write_text("{ not json")
        resp = client.get("/api/automations/templates/anything")
        assert resp.status_code == 404

    def test_delete_template_no_dir_returns_idempotent_ok(
        self, flask_app, client, monkeypatch,
    ):
        monkeypatch.setattr(
            flask_app["auto_mod"], "TEMPLATES_DIR",
            str(flask_app["templates_dir"] / "no-such"),
        )
        resp = client.delete("/api/automations/templates/anything")
        # Returns 200 deleted even when no dir
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "deleted"

    def test_delete_template_match_by_internal_id(
        self, flask_app, client,
    ):
        # Include a non-JSON stray to exercise the skip branch in
        # delete_template's iteration loop (line 251).
        d = flask_app["templates_dir"]
        f = d / "tmpl-x.json"
        f.write_text(json.dumps({"id": "tmpl-x", "name": "X"}))
        (d / "stray.md").write_text("ignored")
        resp = client.delete("/api/automations/templates/tmpl-x")
        assert resp.status_code == 200
        assert not f.exists()

    def test_delete_template_no_match_idempotent(
        self, flask_app, client,
    ):
        d = flask_app["templates_dir"]
        (d / "tmpl-x.json").write_text(json.dumps({"id": "x", "name": "X"}))
        resp = client.delete("/api/automations/templates/missing")
        # No match → returns deleted (idempotent semantics)
        assert resp.status_code == 200

    def test_delete_template_swallows_corrupt_json(
        self, flask_app, client,
    ):
        d = flask_app["templates_dir"]
        (d / "broken.json").write_text("{ corrupt")
        resp = client.delete("/api/automations/templates/anything")
        assert resp.status_code == 200


# ──────────────────────────────────────────────────────────────────
# /api/automations/<id>/run — run_automation
# ──────────────────────────────────────────────────────────────────


class TestRunAutomation:
    def _setup(self, flask_app, wf_id="wf-1"):
        d = flask_app["automations_dir"]
        (d / f"{wf_id}.json").write_text(json.dumps({
            "id": wf_id, "name": "T", "steps": [],
        }))
        return wf_id

    def test_already_running_returns_409(self, flask_app, client):
        wf_id = self._setup(flask_app)
        flask_app["auto_mod"]._run_state["status"] = "running"
        resp = client.post(f"/api/automations/{wf_id}/run", json={})
        assert resp.status_code == 409

    def test_workflow_not_found_returns_404(self, client):
        resp = client.post("/api/automations/missing/run", json={})
        assert resp.status_code == 404

    def test_runner_script_missing_returns_500(self, flask_app, client):
        wf_id = self._setup(flask_app)
        flask_app["runner_script"].unlink()
        resp = client.post(f"/api/automations/{wf_id}/run", json={})
        assert resp.status_code == 500
        assert "runner.js not found" in resp.get_json()["error"]

    def test_happy_path_starts_subprocess_and_thread(
        self, flask_app, client,
    ):
        wf_id = self._setup(flask_app)
        fake_proc = MagicMock()
        fake_proc.stdout = iter([])  # empty — thread exits immediately
        fake_proc.poll.return_value = None

        with patch(
            "backend.routes.assistant_routes.write_temp_creds_file",
            return_value=True,
        ), patch(
            "backend.routes.assistant_routes._portal_credentials_file_for",
            return_value="/tmp/test-creds",
        ), patch(
            "subprocess.Popen", return_value=fake_proc,
        ) as popen, patch(
            "threading.Thread",
        ) as thread_cls:
            resp = client.post(
                f"/api/automations/{wf_id}/run",
                json={"vars": {"foo": "bar", "baz": 42}},
            )

        assert resp.status_code == 200
        assert resp.get_json()["status"] == "started"
        # subprocess.Popen called with var args appended after script path
        cmd = popen.call_args.args[0]
        assert cmd[0] == "node"
        assert cmd[2].endswith(f"{wf_id}.json")
        assert "--var" in cmd
        assert "foo=bar" in cmd
        assert "baz=42" in cmd
        # GRAIDER_PORTAL_CREDS_FILE forwarded to subprocess env
        env = popen.call_args.kwargs["env"]
        assert env["GRAIDER_PORTAL_CREDS_FILE"] == "/tmp/test-creds"
        # Background thread launched to drain NDJSON
        thread_cls.assert_called_once()
        # _run_state populated
        st = flask_app["auto_mod"]._run_state
        assert st["status"] == "running"
        assert st["workflow_name"] == wf_id
        assert st["process"] is fake_proc

    def test_id_sanitization_blocks_path_traversal(
        self, flask_app, client,
    ):
        # ../etc/wf would be sanitized to "etcwf" → 404 (no such file)
        resp = client.post("/api/automations/.././etc/wf/run", json={})
        # Flask routing: most likely 404 from the route matcher itself
        # because the path segment doesn't fit. But if it DOES reach
        # run_automation, the workflow file won't exist.
        assert resp.status_code in (404, 405)


# ──────────────────────────────────────────────────────────────────
# /api/automations/run/status
# ──────────────────────────────────────────────────────────────────


class TestRunStatus:
    def test_idle_default(self, client):
        resp = client.get("/api/automations/run/status")
        body = resp.get_json()
        assert body["status"] == "idle"
        assert body["workflow_name"] == ""

    def test_log_truncated_to_last_20(self, flask_app, client):
        flask_app["auto_mod"]._run_state.update({
            "status": "running",
            "workflow_name": "wf",
            "current_step": 5,
            "total_steps": 10,
            "step_label": "lbl",
            "message": "msg",
            "log": [{"i": i} for i in range(50)],
        })
        resp = client.get("/api/automations/run/status")
        body = resp.get_json()
        assert len(body["log"]) == 20
        # Last 20 of 50 → indices 30-49
        assert body["log"][0]["i"] == 30
        assert body["log"][-1]["i"] == 49


# ──────────────────────────────────────────────────────────────────
# /api/automations/run/stop
# ──────────────────────────────────────────────────────────────────


class TestStopRun:
    def test_no_process_just_marks_idle(self, flask_app, client):
        # No process attached → still returns stopped + state idle
        flask_app["auto_mod"]._run_state["status"] = "running"
        resp = client.post("/api/automations/run/stop")
        assert resp.get_json()["status"] == "stopped"
        assert flask_app["auto_mod"]._run_state["status"] == "idle"

    def test_running_process_terminated(self, flask_app, client):
        proc = MagicMock()
        proc.poll.return_value = None  # Still running
        flask_app["auto_mod"]._run_state.update({
            "status": "running",
            "process": proc,
        })
        resp = client.post("/api/automations/run/stop")
        assert resp.get_json()["status"] == "stopped"
        proc.terminate.assert_called_once()

    def test_already_dead_process_not_terminated(self, flask_app, client):
        proc = MagicMock()
        proc.poll.return_value = 0  # Already exited
        flask_app["auto_mod"]._run_state.update({
            "status": "running",
            "process": proc,
        })
        client.post("/api/automations/run/stop")
        proc.terminate.assert_not_called()


# ──────────────────────────────────────────────────────────────────
# /api/automations/picker/start
# ──────────────────────────────────────────────────────────────────


class TestStartPicker:
    def test_already_picking_returns_409(self, flask_app, client):
        flask_app["auto_mod"]._picker_state["status"] = "picking"
        resp = client.post("/api/automations/picker/start", json={})
        assert resp.status_code == 409

    def test_picker_script_missing_returns_500(self, flask_app, client):
        flask_app["picker_script"].unlink()
        resp = client.post("/api/automations/picker/start", json={})
        assert resp.status_code == 500
        assert "picker.js not found" in resp.get_json()["error"]

    def test_happy_path_no_login_skips_creds_write(
        self, flask_app, client,
    ):
        # auto_login=False → write_temp_creds_file NOT called (production
        # comment notes this is intentional).
        creds_writer = MagicMock(return_value=True)
        fake_proc = MagicMock()
        fake_proc.stdout = iter([])
        fake_proc.poll.return_value = None

        with patch(
            "backend.routes.assistant_routes.write_temp_creds_file",
            creds_writer,
        ), patch(
            "backend.routes.assistant_routes._portal_credentials_file_for",
            return_value="/tmp/creds",
        ), patch(
            "subprocess.Popen", return_value=fake_proc,
        ) as popen, patch(
            "threading.Thread",
        ):
            resp = client.post(
                "/api/automations/picker/start",
                json={"url": "https://example.com", "login": False},
            )

        assert resp.status_code == 200
        assert resp.get_json()["status"] == "picker_started"
        # Production conditional: only writes creds when auto_login=True
        creds_writer.assert_not_called()
        cmd = popen.call_args.args[0]
        assert "--login" not in cmd
        assert "--url" in cmd

    def test_happy_path_with_login_writes_creds(self, flask_app, client):
        fake_proc = MagicMock()
        fake_proc.stdout = iter([])
        fake_proc.poll.return_value = None

        with patch(
            "backend.routes.assistant_routes.write_temp_creds_file",
            return_value=True,
        ) as creds_writer, patch(
            "backend.routes.assistant_routes._portal_credentials_file_for",
            return_value="/tmp/creds",
        ), patch(
            "subprocess.Popen", return_value=fake_proc,
        ) as popen, patch(
            "threading.Thread",
        ):
            resp = client.post(
                "/api/automations/picker/start",
                json={"login": True},
            )

        assert resp.status_code == 200
        creds_writer.assert_called_once_with("teacher-alice")
        cmd = popen.call_args.args[0]
        assert "--login" in cmd
        assert flask_app["auto_mod"]._picker_state["status"] == "picking"


# ──────────────────────────────────────────────────────────────────
# /api/automations/picker/events
# ──────────────────────────────────────────────────────────────────


class TestPickerEvents:
    def test_idle_empty_events(self, client):
        resp = client.get("/api/automations/picker/events")
        body = resp.get_json()
        assert body["status"] == "idle"
        assert body["events"] == []

    def test_drains_buffered_events(self, flask_app, client):
        flask_app["auto_mod"]._picker_state.update({
            "status": "picking",
            "events": [
                {"type": "selector_picked", "selector": "#btn"},
                {"type": "selector_picked", "selector": ".class"},
            ],
        })
        resp = client.get("/api/automations/picker/events")
        body = resp.get_json()
        assert len(body["events"]) == 2
        # Buffer cleared after drain
        assert flask_app["auto_mod"]._picker_state["events"] == []
        # Status preserved (stays "picking" until subprocess closes)
        assert flask_app["auto_mod"]._picker_state["status"] == "picking"


# ──────────────────────────────────────────────────────────────────
# /api/automations/picker/stop
# ──────────────────────────────────────────────────────────────────


class TestStopPicker:
    def test_no_process_just_marks_idle(self, flask_app, client):
        flask_app["auto_mod"]._picker_state["status"] = "picking"
        resp = client.post("/api/automations/picker/stop")
        assert resp.get_json()["status"] == "stopped"
        assert flask_app["auto_mod"]._picker_state["status"] == "idle"

    def test_terminates_running_process(self, flask_app, client):
        proc = MagicMock()
        proc.poll.return_value = None
        flask_app["auto_mod"]._picker_state.update({
            "status": "picking", "process": proc,
        })
        client.post("/api/automations/picker/stop")
        proc.terminate.assert_called_once()


# ──────────────────────────────────────────────────────────────────
# Helper functions: _read_runner_output, _read_picker_output
# ──────────────────────────────────────────────────────────────────


class TestReadRunnerOutput:
    """The helper iterates over proc.stdout (NDJSON), updates _run_state
    based on event type, and trims log to last 100 entries when it grows
    past 200. Test by feeding canned lines through a fake proc."""

    def _make_proc(self, lines):
        proc = MagicMock()
        proc.stdout = iter(lines)
        return proc

    def _reset_state(self, flask_app):
        flask_app["auto_mod"]._run_state.update({
            "process": None, "status": "running",
            "workflow_name": "", "current_step": 0, "total_steps": 0,
            "step_label": "", "message": "", "log": [],
        })

    def test_start_event_sets_total_steps(self, flask_app):
        self._reset_state(flask_app)
        proc = self._make_proc([
            json.dumps({"type": "start", "total_steps": 7}),
        ])
        flask_app["auto_mod"]._read_runner_output(proc)
        st = flask_app["auto_mod"]._run_state
        assert st["total_steps"] == 7
        # Auto-flips running → done when stream closes
        assert st["status"] == "done"

    def test_step_start_updates_current_and_message(self, flask_app):
        self._reset_state(flask_app)
        proc = self._make_proc([
            json.dumps({
                "type": "step_start",
                "step": "3.foo",
                "label": "Click button",
            }),
        ])
        flask_app["auto_mod"]._read_runner_output(proc)
        st = flask_app["auto_mod"]._run_state
        assert st["current_step"] == 3
        assert "Click button" in st["message"]

    def test_step_done_message(self, flask_app):
        self._reset_state(flask_app)
        proc = self._make_proc([
            json.dumps({"type": "step_done", "label": "Login"}),
        ])
        flask_app["auto_mod"]._read_runner_output(proc)
        assert "Done: Login" in flask_app["auto_mod"]._run_state["message"]

    def test_step_error_message(self, flask_app):
        self._reset_state(flask_app)
        proc = self._make_proc([
            json.dumps({
                "type": "step_error",
                "label": "Type",
                "message": "selector missing",
            }),
        ])
        flask_app["auto_mod"]._read_runner_output(proc)
        msg = flask_app["auto_mod"]._run_state["message"]
        assert "Type" in msg and "selector missing" in msg

    def test_status_event_sets_message(self, flask_app):
        self._reset_state(flask_app)
        proc = self._make_proc([
            json.dumps({"type": "status", "message": "Halfway"}),
        ])
        flask_app["auto_mod"]._read_runner_output(proc)
        assert flask_app["auto_mod"]._run_state["message"] == "Halfway"

    def test_done_event_marks_done(self, flask_app):
        self._reset_state(flask_app)
        proc = self._make_proc([
            json.dumps({"type": "done", "message": "All steps complete"}),
        ])
        flask_app["auto_mod"]._read_runner_output(proc)
        st = flask_app["auto_mod"]._run_state
        assert st["status"] == "done"
        assert st["message"] == "All steps complete"

    def test_error_event_marks_error(self, flask_app):
        self._reset_state(flask_app)
        proc = self._make_proc([
            json.dumps({"type": "error", "message": "Browser crashed"}),
        ])
        flask_app["auto_mod"]._read_runner_output(proc)
        st = flask_app["auto_mod"]._run_state
        assert st["status"] == "error"
        assert st["message"] == "Browser crashed"

    def test_invalid_json_silently_skipped(self, flask_app):
        self._reset_state(flask_app)
        proc = self._make_proc([
            "not json",
            "",  # blank lines also skipped
            json.dumps({"type": "done"}),
        ])
        flask_app["auto_mod"]._read_runner_output(proc)
        assert flask_app["auto_mod"]._run_state["status"] == "done"

    def test_log_trimmed_to_last_100_when_past_200(self, flask_app):
        self._reset_state(flask_app)
        # Generate 250 step_start events so the log accumulates
        lines = [
            json.dumps({
                "type": "step_start",
                "step": f"{i}.x",
                "label": f"L{i}",
            })
            for i in range(250)
        ]
        proc = self._make_proc(lines)
        flask_app["auto_mod"]._read_runner_output(proc)
        log = flask_app["auto_mod"]._run_state["log"]
        # Trim happens lazily when len exceeds 200; final length must
        # be at most 200 (the trim leaves 100, then more events may
        # be appended after that).
        assert len(log) <= 200
        # And we kept the tail, not the head (last entry is the very
        # last produced event)
        assert log[-1]["label"] == "L249"


class TestReadPickerOutput:
    def _make_proc(self, lines):
        proc = MagicMock()
        proc.stdout = iter(lines)
        return proc

    def _reset_state(self, flask_app):
        flask_app["auto_mod"]._picker_state.update({
            "process": None, "status": "picking", "events": [],
        })

    def test_selector_picked_appends(self, flask_app):
        self._reset_state(flask_app)
        proc = self._make_proc([
            json.dumps({"type": "selector_picked", "selector": "#a"}),
            json.dumps({"type": "selector_picked", "selector": ".b"}),
        ])
        flask_app["auto_mod"]._read_picker_output(proc)
        events = flask_app["auto_mod"]._picker_state["events"]
        assert len(events) == 2
        # Stream closed → status flips to done
        assert flask_app["auto_mod"]._picker_state["status"] == "done"

    def test_done_event_marks_done(self, flask_app):
        self._reset_state(flask_app)
        proc = self._make_proc([
            json.dumps({"type": "done"}),
        ])
        flask_app["auto_mod"]._read_picker_output(proc)
        assert flask_app["auto_mod"]._picker_state["status"] == "done"

    def test_invalid_json_silently_skipped(self, flask_app):
        self._reset_state(flask_app)
        proc = self._make_proc([
            "garbage",
            "",
            json.dumps({"type": "selector_picked", "selector": "#x"}),
        ])
        flask_app["auto_mod"]._read_picker_output(proc)
        assert len(flask_app["auto_mod"]._picker_state["events"]) == 1

    def test_unknown_event_type_ignored(self, flask_app):
        self._reset_state(flask_app)
        proc = self._make_proc([
            json.dumps({"type": "unknown_event", "data": "x"}),
        ])
        flask_app["auto_mod"]._read_picker_output(proc)
        # Unknown events don't append to events array
        assert flask_app["auto_mod"]._picker_state["events"] == []
        # Stream-close fallthrough still marks done
        assert flask_app["auto_mod"]._picker_state["status"] == "done"


# ──────────────────────────────────────────────────────────────────
# _cleanup_subprocesses (atexit handler)
# ──────────────────────────────────────────────────────────────────


class TestCleanupSubprocesses:
    def test_terminates_live_processes(self, flask_app):
        run_proc = MagicMock(); run_proc.poll.return_value = None
        pick_proc = MagicMock(); pick_proc.poll.return_value = None
        flask_app["auto_mod"]._run_state["process"] = run_proc
        flask_app["auto_mod"]._picker_state["process"] = pick_proc

        flask_app["auto_mod"]._cleanup_subprocesses()

        run_proc.terminate.assert_called_once()
        pick_proc.terminate.assert_called_once()

    def test_skips_already_dead_processes(self, flask_app):
        run_proc = MagicMock(); run_proc.poll.return_value = 0  # exited
        flask_app["auto_mod"]._run_state["process"] = run_proc
        flask_app["auto_mod"]._cleanup_subprocesses()
        run_proc.terminate.assert_not_called()

    def test_falls_back_to_kill_on_terminate_failure(self, flask_app):
        proc = MagicMock()
        proc.poll.return_value = None
        proc.terminate.side_effect = OSError("permission denied")
        flask_app["auto_mod"]._run_state["process"] = proc
        flask_app["auto_mod"]._cleanup_subprocesses()
        # Try terminate, fail, fall to kill
        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()

    def test_kill_failure_swallowed(self, flask_app):
        # Both terminate and kill fail → no exception bubbles up
        proc = MagicMock()
        proc.poll.return_value = None
        proc.terminate.side_effect = OSError("nope")
        proc.kill.side_effect = OSError("also nope")
        flask_app["auto_mod"]._run_state["process"] = proc
        # Must not raise
        flask_app["auto_mod"]._cleanup_subprocesses()

    def test_no_processes_attached_is_noop(self, flask_app):
        # _run_state["process"] is None and _picker_state["process"] is None
        flask_app["auto_mod"]._cleanup_subprocesses()
        # Just confirm no exception raised
