"""Test that handle_route_errors decorator maps CircuitBreakerError to 503."""
from __future__ import annotations

import pybreaker
from flask import Flask

from backend.utils.errors import handle_route_errors


def test_handle_route_errors_maps_circuit_breaker_to_503():
    app = Flask(__name__)

    @app.route("/test")
    @handle_route_errors
    def _view():
        raise pybreaker.CircuitBreakerError("Circuit 'openai:gpt-4o' is open")

    client = app.test_client()
    resp = client.get("/test")

    assert resp.status_code == 503
    assert resp.headers.get("Retry-After") == "60"
    body = resp.get_json()
    assert "circuit breaker open" in body["error"].lower()
    assert body["retry_after_seconds"] == 60


def test_handle_route_errors_500_still_works_for_other_errors():
    app = Flask(__name__)

    @app.route("/test")
    @handle_route_errors
    def _view():
        raise RuntimeError("something else")

    client = app.test_client()
    resp = client.get("/test")

    assert resp.status_code == 500
    assert resp.get_json()["error"] == "Internal server error"
