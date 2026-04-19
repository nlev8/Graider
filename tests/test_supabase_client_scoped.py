"""Unit tests for backend/supabase_client_scoped.py.

Covers the 5 decision paths of get_request_supabase():
  1. Flag off → service-role (no change from today)
  2. Flag on + no request context → service-role
  3. Flag on + in request context but no g.supabase_jwt → service-role
  4. Flag on + g.supabase_jwt set + env vars present → per-user client
  5. Flag on + g.supabase_jwt set + env vars MISSING → RuntimeError

Per-user client construction is verified by inspecting the arguments
passed to supabase.create_client() (mocked) — we don't make a real
Supabase connection in unit tests.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, g


@pytest.fixture
def app():
    app = Flask(__name__)
    return app


def _service_mock_sentinel():
    """Distinguishable sentinel object returned by the mocked service-role
    helper so the test can prove "we got the service client back" without
    touching real Supabase config."""
    return object()


def test_flag_off_returns_service_role(app, monkeypatch):
    monkeypatch.setenv("USE_PER_USER_JWT", "0")
    sentinel = _service_mock_sentinel()
    with patch(
        "backend.supabase_client_scoped._get_service_client",
        return_value=sentinel,
    ):
        from backend.supabase_client_scoped import get_request_supabase
        with app.test_request_context("/api/ping"):
            g.supabase_jwt = "should-be-ignored-because-flag-is-off"
            assert get_request_supabase() is sentinel


def test_flag_on_no_request_context_returns_service_role(monkeypatch):
    monkeypatch.setenv("USE_PER_USER_JWT", "1")
    sentinel = _service_mock_sentinel()
    with patch(
        "backend.supabase_client_scoped._get_service_client",
        return_value=sentinel,
    ):
        from backend.supabase_client_scoped import get_request_supabase
        # NO with app.test_request_context — we're outside any Flask request
        assert get_request_supabase() is sentinel


def test_flag_on_no_jwt_attr_returns_service_role(app, monkeypatch):
    monkeypatch.setenv("USE_PER_USER_JWT", "1")
    sentinel = _service_mock_sentinel()
    with patch(
        "backend.supabase_client_scoped._get_service_client",
        return_value=sentinel,
    ):
        from backend.supabase_client_scoped import get_request_supabase
        with app.test_request_context("/api/ping"):
            # No g.supabase_jwt set — simulates SSO / student / dev paths.
            assert get_request_supabase() is sentinel


def test_flag_on_missing_env_raises(app, monkeypatch):
    monkeypatch.setenv("USE_PER_USER_JWT", "1")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    from backend.supabase_client_scoped import get_request_supabase
    with app.test_request_context("/api/ping"):
        g.supabase_jwt = "some.jwt.token"
        with pytest.raises(RuntimeError) as excinfo:
            get_request_supabase()
    assert "SUPABASE_URL" in str(excinfo.value) or "SUPABASE_ANON_KEY" in str(
        excinfo.value
    )


def test_flag_on_jwt_present_constructs_per_user_client(app, monkeypatch):
    monkeypatch.setenv("USE_PER_USER_JWT", "1")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test-anon-key")

    fake_raw_client = MagicMock(name="raw_client")
    fake_resilient_client = MagicMock(name="resilient_client")

    with patch(
        "backend.supabase_client_scoped.create_client",
        return_value=fake_raw_client,
    ) as mock_create, patch(
        "backend.supabase_client_scoped.ResilientClient",
        return_value=fake_resilient_client,
    ) as mock_resilient:
        from backend.supabase_client_scoped import get_request_supabase
        with app.test_request_context("/api/ping"):
            g.supabase_jwt = "user.jwt.token"
            result = get_request_supabase()

    assert result is fake_resilient_client
    mock_resilient.assert_called_once_with(fake_raw_client)
    mock_create.assert_called_once()
    call_args = mock_create.call_args
    # Positional: (url, anon_key); options kwarg carries the Authorization.
    assert call_args.args[0] == "https://test.supabase.co"
    assert call_args.args[1] == "test-anon-key"
    options = call_args.kwargs["options"]
    # ClientOptions is a dataclass-like object on supabase-py 2.x; inspect via attr.
    assert options.auto_refresh_token is False
    assert options.persist_session is False
    assert options.headers == {"Authorization": "Bearer user.jwt.token"}
