"""Tests for RFC 7807 problem+json error envelope (Phase 5d PR 1).

Verifies that error_response() and handle_route_errors() produce bodies
matching RFC 7807 § 3 (type, title, status, detail, instance), set
Content-Type: application/problem+json, and preserve the legacy `error`
field for backward compatibility with the React frontend.

Spec: docs/superpowers/specs/2026-04-24-phase5d-polish-slice-design.md § PR 1.
"""
from __future__ import annotations

import pybreaker
import pytest
from flask import Flask

from backend.utils.errors import error_response, handle_route_errors


@pytest.fixture
def app():
    app = Flask(__name__)
    return app


def test_error_response_default_has_rfc7807_fields(app):
    with app.test_request_context("/api/example"):
        resp = error_response("validation failed", 400)
    body = resp.get_json()
    assert body["type"] == "https://graider.live/errors/bad-request"
    assert body["title"] == "Bad Request"
    assert body["status"] == 400
    assert body["detail"] == "validation failed"
    assert body["instance"] == "/api/example"
    # Legacy field preserved for the React frontend
    assert body["error"] == "validation failed"
    assert resp.headers["Content-Type"] == "application/problem+json"


def test_error_response_with_code_extension(app):
    with app.test_request_context("/api/x"):
        resp = error_response("invalid email", 400, code="invalid-email")
    body = resp.get_json()
    # `code` becomes the type slug AND a top-level extension field
    assert body["type"] == "https://graider.live/errors/invalid-email"
    assert body["code"] == "invalid-email"
    assert body["error"] == "invalid email"


def test_error_response_404(app):
    with app.test_request_context("/api/missing"):
        resp = error_response("not found", 404)
    body = resp.get_json()
    assert body["type"] == "https://graider.live/errors/not-found"
    assert body["title"] == "Not Found"
    assert body["status"] == 404


def test_error_response_unknown_status_falls_back(app):
    with app.test_request_context("/api/x"):
        resp = error_response("teapot", 418)
    body = resp.get_json()
    assert body["type"] == "https://graider.live/errors/http-418"
    assert body["title"] == "HTTP 418"


def test_handle_route_errors_500_path_emits_rfc7807():
    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.route("/test")
    @handle_route_errors
    def _view():
        raise RuntimeError("boom")

    client = app.test_client()
    resp = client.get("/test")

    assert resp.status_code == 500
    assert resp.headers["Content-Type"] == "application/problem+json"
    body = resp.get_json()
    assert body["type"] == "https://graider.live/errors/internal"
    assert body["title"] == "Internal Server Error"
    assert body["detail"] == "Internal server error"
    assert body["instance"] == "/test"
    # Legacy field preserved
    assert body["error"] == "Internal server error"


def test_handle_route_errors_503_breaker_path_emits_rfc7807():
    app = Flask(__name__)
    app.config["TESTING"] = True

    @app.route("/test")
    @handle_route_errors
    def _view():
        raise pybreaker.CircuitBreakerError("Circuit 'openai:gpt-4o' is open")

    client = app.test_client()
    resp = client.get("/test")

    assert resp.status_code == 503
    assert resp.headers["Retry-After"] == "60"
    assert resp.headers["Content-Type"] == "application/problem+json"
    body = resp.get_json()
    assert body["type"] == "https://graider.live/errors/breaker-open"
    assert body["title"] == "Service Unavailable"
    assert body["status"] == 503
    assert "circuit breaker open" in body["detail"].lower()
    assert body["instance"] == "/test"
    # Legacy fields preserved for backward compat
    assert "circuit breaker open" in body["error"].lower()
    assert body["retry_after_seconds"] == 60
