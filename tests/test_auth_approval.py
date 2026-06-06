"""Tests for the SSO short-circuit in /api/auth/approval-status.

Task 5: ClassLink and Clever sessions are district-approved by definition.
The approval_status endpoint must short-circuit for SSO sessions — returning
{"approved": True} WITHOUT calling Supabase's get_user_by_id.

Strategy
--------
Use the real Flask app (`backend.app.app`) + session cookie to drive the real
auth middleware (`backend/auth.py`). The middleware already reads
`session['classlink_user']` and sets `g.auth_source = 'classlink'`; similarly
for `session['clever_user']` → `g.auth_source = 'clever'`. No Bearer token is
sent, so the middleware takes the SSO branch (not the JWT branch).

Supabase is patched to raise `AssertionError` if called, which proves the
short-circuit fires before the `_get_supabase()` call.

Both auth_source values are tested independently.
"""
from __future__ import annotations

import time

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def app_client():
    """Flask test client with rate-limit storage reset before each test."""
    from backend.app import app
    from backend.extensions import limiter
    try:
        limiter.reset()
    except Exception:
        pass
    with app.test_client() as c:
        yield c


class TestApprovalStatusSSOShortCircuit:
    """Approval-status endpoint returns approved=True for SSO sessions
    without calling Supabase get_user_by_id."""

    def test_approval_status_approved_for_classlink_session(
        self, app_client, monkeypatch,
    ):
        """ClassLink SSO session → approved=True without any Supabase call.

        This is the load-bearing regression test for the Task 5 fix.
        The supabase mock is set to raise AssertionError if called; a
        call reaching it means the short-circuit is missing or broken.
        """
        monkeypatch.setenv("FLASK_ENV", "production")  # no dev-shim path

        # Populate the session with a classlink_user — the auth middleware
        # in backend/auth.py reads this and sets g.auth_source='classlink'.
        with app_client.session_transaction() as sess:
            sess['classlink_user'] = {
                'user_id': 'classlink-uuid-abc123',
                'email': 'teacher@school.edu',
                'type': 'teacher',
                'tenant_id': 'dist-1',
            }
            sess['sso_login_ts'] = time.time()  # VB8 #18 absolute-cap anchor

        def _supabase_must_not_be_called():
            raise AssertionError(
                "get_supabase must NOT be called for a ClassLink SSO session — "
                "the short-circuit is missing."
            )

        with patch(
            "backend.routes.auth_routes._get_supabase",
            side_effect=_supabase_must_not_be_called,
        ):
            resp = app_client.get("/api/auth/approval-status")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["approved"] is True, f"Expected approved=True, got: {body}"
        assert "email" in body  # contract: email is returned alongside approved

    def test_approval_status_approved_for_clever_session(
        self, app_client, monkeypatch,
    ):
        """Clever SSO session → approved=True without any Supabase call.

        Mirrors the ClassLink test for the Clever auth path.
        auth.py reads session['clever_user'] and sets g.auth_source='clever'.
        """
        monkeypatch.setenv("FLASK_ENV", "production")  # no dev-shim path

        def _supabase_must_not_be_called():
            raise AssertionError(
                "get_supabase must NOT be called for a Clever SSO session — "
                "the short-circuit is missing."
            )

        # Clever SSO session — auth.py calls resolve_clever_user_id(clever_id)
        # to get g.user_id; patch it to return a sentinel UUID.
        with patch(
            "backend.auth.resolve_clever_user_id",
            return_value="clever-uuid-def456",
        ), patch(
            "backend.routes.auth_routes._get_supabase",
            side_effect=_supabase_must_not_be_called,
        ):
            with app_client.session_transaction() as sess:
                sess['clever_user'] = {
                    'clever_id': 'clever-id-xyz',
                    'email': 'teacher2@school.edu',
                    'district': 'dist-2',
                }
                sess['sso_login_ts'] = time.time()  # VB8 #18 absolute-cap anchor

            resp = app_client.get("/api/auth/approval-status")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["approved"] is True, f"Expected approved=True, got: {body}"
        assert "email" in body
