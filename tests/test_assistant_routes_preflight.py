"""SSE preflight breaker check test (Phase 5b PR 1 Task 1.8)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pybreaker
import pytest

from backend.services.llm_adapter import breakers


@pytest.fixture(autouse=True)
def _reset_breakers():
    breakers._BREAKERS.clear()
    yield
    breakers._BREAKERS.clear()


def _force_breaker_open(provider: str, model: str) -> None:
    """Trip the breaker for (provider, model) by recording enough failures."""
    b = breakers.get_breaker(provider, model)

    def _always_fail():
        raise ConnectionError("forced open for test")

    for _ in range(breakers.FAIL_MAX):
        try:
            b.call(_always_fail)
        except (ConnectionError, pybreaker.CircuitBreakerError):
            pass

    assert b.current_state == pybreaker.STATE_OPEN


def test_assistant_chat_returns_503_when_breaker_open(monkeypatch):
    """With the breaker for (active_provider, active_model) in STATE_OPEN,
    the SSE route returns 503 + Retry-After: 60 BEFORE entering generate().

    Uses a minimal Flask test app wrapping the assistant_bp blueprint."""
    from flask import Flask
    from backend.routes.assistant_routes import assistant_bp

    # Force the openai gpt-4o breaker open up front
    _force_breaker_open("openai", "gpt-4o")

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.secret_key = "test-secret"

    @app.before_request
    def _set_user_id():
        from flask import g
        g.user_id = "test-teacher"

    app.register_blueprint(assistant_bp)

    # Stub _get_assistant_model to return (openai, gpt-4o) so preflight
    # targets the already-open breaker.
    with patch(
        "backend.routes.assistant_routes._get_assistant_model",
        return_value={"provider": "openai", "model": "gpt-4o"},
    ), patch("backend.api_keys.get_api_key", return_value="sk-test"), \
         patch("backend.routes.assistant_routes.openai_pkg", MagicMock()):
        client = app.test_client()
        resp = client.post(
            "/api/assistant/chat",
            json={"messages": [{"role": "user", "content": "hi"}], "session_id": "test-session"},
        )

    assert resp.status_code == 503, f"got {resp.status_code}, body={resp.get_data(as_text=True)}"
    assert resp.headers.get("Retry-After") == "60"
    body = resp.get_json()
    assert "circuit breaker open" in body["error"].lower()
    assert body["retry_after_seconds"] == 60


def test_assistant_chat_passes_through_when_breaker_closed(monkeypatch):
    """With breaker CLOSED, the preflight does NOT return 503 — the route
    proceeds to its normal (streamed) handling. We don't drive generate()
    to completion here; we only verify the preflight path doesn't hijack."""
    from flask import Flask
    from backend.routes.assistant_routes import assistant_bp

    # Create a closed breaker (fresh)
    breakers.get_breaker("openai", "gpt-4o")

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.secret_key = "test-secret"

    @app.before_request
    def _set_user_id():
        from flask import g
        g.user_id = "test-teacher"

    app.register_blueprint(assistant_bp)

    # Minimal request body that fails AFTER the preflight check —
    # we omit "messages", which the route rejects with a 400 further down.
    # If 503 were returned here, it'd be a preflight false-positive.
    with patch(
        "backend.routes.assistant_routes._get_assistant_model",
        return_value={"provider": "openai", "model": "gpt-4o"},
    ), patch("backend.api_keys.get_api_key", return_value="sk-test"), \
         patch("backend.routes.assistant_routes.openai_pkg", MagicMock()):
        client = app.test_client()
        resp = client.post("/api/assistant/chat", json={})

    # Preflight passed (not 503); the 400 comes from the "messages required" check.
    assert resp.status_code != 503
    assert resp.status_code == 400
