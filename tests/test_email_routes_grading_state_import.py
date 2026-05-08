"""
Regression tests for GH #249: email_routes.py was importing
`grading_state` and `grading_lock` from `backend.routes.grading_routes`
post-Phase-3 refactor. Those symbols don't exist; the broken `from`
import raised ImportError, swallowed by the broad except → 500 in
production for /api/mark-confirmations-sent-file and
/api/send-confirmation-emails.

Fix: switched both routes to the per-teacher `_get_state(teacher_id)`
factory from `backend.grading.state`.

These tests pin the import path so a future broken import or a stray
revert can't silently re-introduce the 500.
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest


@pytest.fixture
def flask_app(tmp_path, monkeypatch):
    from flask import Flask, g
    import backend.routes.email_routes as er

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(er, "GRAIDER_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(er, "PARENT_CONTACTS_FILE", str(tmp_path / "parent_contacts.json"))
    monkeypatch.setattr(er, "CONFIRMATIONS_FILE", str(tmp_path / "confirmations_sent.json"))
    monkeypatch.setattr(er, "OUTLOOK_EXPORTS_DIR", str(tmp_path / "outlook_exports"))
    monkeypatch.setattr(er, "RESULTS_FILE", str(tmp_path / ".graider_results.json"))

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.secret_key = "test-secret"

    @app.before_request
    def _set_user_id():
        g.user_id = "teacher-alice"

    app.register_blueprint(er.email_bp)
    return app, er, tmp_path


# ──────────────────────────────────────────────────────────────────
# /api/mark-confirmations-sent-file
# ──────────────────────────────────────────────────────────────────


class TestMarkConfirmationsSentFile:
    def test_no_longer_500s_on_grading_state_import(self, flask_app):
        """Pre-fix: the route imported grading_state/grading_lock from
        grading_routes — those symbols don't exist post-refactor →
        ImportError swallowed → 500. Now must return 200 (or expected
        business error like 400 for missing filenames)."""
        app, _, _ = flask_app
        client = app.test_client()
        resp = client.post(
            "/api/mark-confirmations-sent-file",
            json={"filenames": ["a.docx"]},
        )
        assert resp.status_code != 500, (
            "Route 500'd — likely the grading_state import is broken "
            f"again. Body: {resp.get_data(as_text=True)}"
        )
        # Healthy path returns 200 with status='ok'
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get("status") == "ok"

    def test_writes_to_confirmations_file(self, flask_app):
        """Happy-path: filenames added to the confirmations file even when
        per-teacher grading state has no results."""
        app, er, _ = flask_app
        client = app.test_client()
        resp = client.post(
            "/api/mark-confirmations-sent-file",
            json={"filenames": ["a.docx", "b.pdf"]},
        )
        assert resp.status_code == 200
        # Confirmations file written
        with open(er.CONFIRMATIONS_FILE) as f:
            saved = json.load(f)
        assert "a.docx" in saved
        assert "b.pdf" in saved

    def test_marks_grading_state_results_when_match(self, flask_app):
        """When per-teacher grading state has matching filenames, those
        results get confirmation_sent=True. Pins the new fix path."""
        from backend.grading.state import _get_state
        app, er, _ = flask_app

        # Seed the per-teacher state with a result
        state = _get_state("teacher-alice")
        state["results"] = [
            {"filename": "a.docx", "score": 90, "confirmation_sent": False},
            {"filename": "b.docx", "score": 80, "confirmation_sent": False},
        ]

        try:
            client = app.test_client()
            resp = client.post(
                "/api/mark-confirmations-sent-file",
                json={"filenames": ["a.docx"]},
            )
            assert resp.status_code == 200
            body = resp.get_json()
            # 1 of 2 results matched
            assert body.get("updated") == 1
            # State mutated correctly
            assert state["results"][0]["confirmation_sent"] is True
            assert state["results"][1]["confirmation_sent"] is False
        finally:
            # Clean up state to avoid leaking into other tests
            state["results"] = []


# ──────────────────────────────────────────────────────────────────
# /api/send-confirmation-emails — same import pattern
# ──────────────────────────────────────────────────────────────────


class TestSendConfirmationEmailsImportPath:
    def test_no_500_on_assignments_folder_validation(self, flask_app):
        """The grading_state import sits AFTER several pre-flight checks.
        Even with no roster + no folder, the route returns 400 (folder
        validation) — not 500 (ImportError swallowed by broad except).
        If the import re-breaks, the route would still 500 when called
        with a valid folder, but this smoke check confirms the
        ImportError isn't being raised at module-load level."""
        app, _, _ = flask_app
        client = app.test_client()
        resp = client.post(
            "/api/send-confirmation-emails",
            json={"assignments_folder": ""},  # missing folder → 400
        )
        # 400 is the expected business error; 500 means the route exception
        # bubbled up before the validation check (e.g. import-time error).
        assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────────
# Direct import smoke test — pins the new fix path
# ──────────────────────────────────────────────────────────────────


class TestImportPath:
    def test_grading_state_module_exposes_factory_functions(self):
        """The new fix imports `_get_state` and `_get_lock` from
        `backend.grading.state` — verify those symbols exist so a
        future move doesn't silently break the route again."""
        from backend.grading.state import _get_state, _get_lock
        assert callable(_get_state)
        assert callable(_get_lock)
        # Both accept a teacher_id and return state/lock
        state = _get_state("teacher-test-import")
        assert isinstance(state, dict)
        lock = _get_lock("teacher-test-import")
        # Lock has acquire/release
        assert hasattr(lock, "acquire")
        assert hasattr(lock, "release")

    def test_old_broken_import_path_no_longer_used(self):
        """The pre-fix path `from backend.routes.grading_routes import
        grading_state, grading_lock` is what raised ImportError. We don't
        prevent that import here, but we DO assert email_routes.py no
        longer references those names directly via the broken import."""
        import backend.routes.email_routes as er
        import inspect

        source = inspect.getsource(er)
        # The broken pattern must not appear anywhere in the module.
        assert "from backend.routes.grading_routes import grading_state" not in source, (
            "email_routes.py is back on the broken import path that "
            "caused GH #249. Use `from backend.grading.state import "
            "_get_state, _get_lock` instead."
        )
