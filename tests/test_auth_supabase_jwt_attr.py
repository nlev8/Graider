"""Verify g.supabase_jwt is set ONLY on the direct-Bearer-JWT branch of
check_auth(), and remains unset for SSO / student / dev paths.

Phase 4.5 relies on this invariant: get_request_supabase() keys off
g.supabase_jwt to decide per-user vs service-role.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from flask import Flask, g


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "testing")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")
    monkeypatch.setenv(
        "SUPABASE_JWT_SECRET",
        "test-jwt-secret-at-least-32-chars-yes-ok",
    )
    monkeypatch.setenv("FLASK_SECRET_KEY", "x" * 64)

    from backend.app import app as flask_app
    yield flask_app


def test_supabase_jwt_attr_set_on_valid_bearer_token(app):
    """When validate_token() succeeds, g.supabase_jwt holds the raw token."""
    fake_token = "header.payload.signature"
    fake_payload = {
        "sub": "user-abc",
        "email": "t@example.com",
        "user_metadata": {"approved": True}
    }
    with patch("backend.auth.validate_token", return_value=fake_payload), \
         patch("backend.auth._get_supabase", return_value=None):
        with app.test_request_context(
            "/api/settings/load",
            headers={"Authorization": f"Bearer {fake_token}"},
        ):
            # Invoke the before_request check_auth hook manually.
            for fn in app.before_request_funcs[None]:
                rv = fn()
                if rv is not None:
                    # Returned a response → auth rejected. Not our case.
                    pytest.fail(
                        f"check_auth returned a rejection response: {rv!r}"
                    )
            assert getattr(g, "supabase_jwt", None) == fake_token


def test_supabase_jwt_attr_unset_on_dev_header_path(app):
    """Dev-mode X-Test-Teacher-Id returns early; g.supabase_jwt stays unset."""
    with app.test_request_context(
        "/api/settings/load",
        headers={"X-Test-Teacher-Id": "teacher-dev-1"},
        environ_overrides={"HTTP_HOST": "localhost"},
    ):
        for fn in app.before_request_funcs[None]:
            fn()
        assert getattr(g, "supabase_jwt", None) is None
