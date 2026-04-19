"""Verify db_mode.register() installs an after_request hook that emits
one structured JSON log line per /api/* request.

The spec requires these fields in the emitted JSON:
  event, path, method, status, auth_source, db_mode, user_id
"""
from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock

import pytest
from flask import Flask, g


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("USE_PER_USER_JWT", "0")
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"

    @app.route("/api/ping")
    def ping():
        return {"ok": True}

    @app.route("/not-api")
    def not_api():
        return "ok"

    from backend.observability import db_mode
    db_mode.register(app)
    return app


def _capture_logs(caplog):
    """Return only log records from the db_mode logger."""
    return [r for r in caplog.records if r.name == "backend.db_mode"]


def test_emits_one_log_per_api_request(app, caplog):
    caplog.set_level(logging.INFO, logger="backend.db_mode")
    with app.test_client() as client:
        resp = client.get("/api/ping")
    assert resp.status_code == 200
    records = _capture_logs(caplog)
    assert len(records) == 1
    payload = json.loads(records[0].getMessage())
    assert payload["event"] == "request.db_mode"
    assert payload["path"] == "/api/ping"
    assert payload["method"] == "GET"
    assert payload["status"] == 200
    assert payload["db_mode"] == "service_role"
    assert payload["auth_source"] == "none"


def test_non_api_requests_not_logged(app, caplog):
    caplog.set_level(logging.INFO, logger="backend.db_mode")
    with app.test_client() as client:
        client.get("/not-api")
    assert _capture_logs(caplog) == []


def test_auth_source_jwt_when_supabase_jwt_attr_present(app, caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="backend.db_mode")

    @app.before_request
    def set_jwt():
        g.supabase_jwt = "test.jwt"
        g.user_id = "user-xyz"

    with app.test_client() as client:
        client.get("/api/ping")
    payload = json.loads(_capture_logs(caplog)[0].getMessage())
    assert payload["auth_source"] == "jwt"
    assert payload["user_id"] == "user-xyz"


def test_db_mode_per_user_when_flag_on_and_jwt_present(app, caplog, monkeypatch):
    monkeypatch.setenv("USE_PER_USER_JWT", "1")
    caplog.set_level(logging.INFO, logger="backend.db_mode")

    @app.before_request
    def set_jwt():
        g.supabase_jwt = "test.jwt"
        g.user_id = "user-xyz"

    with app.test_client() as client:
        client.get("/api/ping")
    payload = json.loads(_capture_logs(caplog)[0].getMessage())
    assert payload["db_mode"] == "per_user_jwt"
