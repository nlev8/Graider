"""Unit tests for backend/routes/auth_routes.py.

Audit MAJOR #4 sprint follow-up to PR #282. Targets the 79 uncovered LOC
(25% baseline) — covers HMAC-signed one-click approval flow, signup
notifications, and approval status checks.

Strategy
--------
Flask test_client + mocks for:
  * `_get_supabase()` → MagicMock (covers approve, status, signup-lookup)
  * `requests.post` → no-op (covers resend email send)
  * `os.environ` via monkeypatch (covers SUPABASE_JWT_SECRET, ADMIN_EMAIL,
    RESEND_API_KEY, APP_URL, SUPABASE_URL)

All 4 routes get full validation/error/happy-path coverage, plus the
3 helper functions (_get_hmac_secret, _sign_approval, _build_approve_url).
"""
from __future__ import annotations

import hmac
import hashlib
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def client():
    """Flask test client with rate-limit storage reset before each test.

    The auth-routes endpoints have `@limiter.limit("X/minute")` decorators.
    Flask-Limiter uses module-level state, so per-test calls accumulate
    across the whole class. Reset the storage to keep tests isolated.
    """
    from backend.app import app
    from backend.extensions import limiter
    try:
        limiter.reset()
    except Exception:  # noqa: BLE001  # broad catch: best-effort, failure tolerated
        pass
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_client():
    """Authenticated client (g.user_id populated)."""
    from backend.app import app
    from backend.extensions import limiter
    try:
        limiter.reset()
    except Exception:  # noqa: BLE001  # broad catch: best-effort, failure tolerated
        pass
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['user_id'] = 'test-teacher-1'
        yield c


# ──────────────────────────────────────────────────────────────────
# _get_hmac_secret
# ──────────────────────────────────────────────────────────────────


class TestGetHmacSecret:
    def test_returns_secret_when_env_set(self, monkeypatch):
        from backend.routes.auth_routes import _get_hmac_secret
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret-xyz")
        assert _get_hmac_secret() == "test-secret-xyz"

    def test_raises_when_env_missing(self, monkeypatch):
        from backend.routes.auth_routes import _get_hmac_secret
        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        with pytest.raises(Exception, match="SUPABASE_JWT_SECRET not configured"):
            _get_hmac_secret()


# ──────────────────────────────────────────────────────────────────
# _sign_approval
# ──────────────────────────────────────────────────────────────────


class TestSignApproval:
    def test_signature_is_deterministic(self, monkeypatch):
        from backend.routes.auth_routes import _sign_approval
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "secret-1")
        sig1 = _sign_approval("user-1", "alice@x.com")
        sig2 = _sign_approval("user-1", "alice@x.com")
        assert sig1 == sig2

    def test_signature_changes_with_secret(self, monkeypatch):
        from backend.routes.auth_routes import _sign_approval
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "secret-A")
        sig_a = _sign_approval("user-1", "alice@x.com")
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "secret-B")
        sig_b = _sign_approval("user-1", "alice@x.com")
        assert sig_a != sig_b

    def test_signature_uses_sha256_hmac(self, monkeypatch):
        # Pin the exact algorithm — a regression to MD5 etc. would be
        # caught here.
        from backend.routes.auth_routes import _sign_approval
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret")
        expected = hmac.new(
            b"test-secret",
            b"approve:user-1:alice@x.com",
            hashlib.sha256,
        ).hexdigest()
        assert _sign_approval("user-1", "alice@x.com") == expected


# ──────────────────────────────────────────────────────────────────
# _build_approve_url
# ──────────────────────────────────────────────────────────────────


class TestBuildApproveUrl:
    def test_returns_url_with_default_base(self, monkeypatch):
        from backend.routes.auth_routes import _build_approve_url
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "s")
        monkeypatch.delenv("APP_URL", raising=False)
        url = _build_approve_url("user-1", "alice@x.com")
        assert url.startswith("https://app.graider.live/api/auth/approve-user?")
        assert "user_id=user-1" in url
        assert "alice%40x.com" in url
        assert "token=" in url

    def test_url_encodes_special_chars(self, monkeypatch):
        from backend.routes.auth_routes import _build_approve_url
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "s")
        url = _build_approve_url("user 1", "a+b@x.com")
        # Spaces and pluses get URL-encoded
        assert "user%201" in url or "user+1" in url
        assert "a%2Bb%40x.com" in url

    def test_app_url_env_overrides_default(self, monkeypatch):
        from backend.routes.auth_routes import _build_approve_url
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "s")
        monkeypatch.setenv("APP_URL", "https://staging.graider.live")
        url = _build_approve_url("user-1", "alice@x.com")
        assert url.startswith("https://staging.graider.live/")


# ──────────────────────────────────────────────────────────────────
# /api/auth/approve-user — one-click admin approval
# ──────────────────────────────────────────────────────────────────


class TestApproveUserRoute:
    def test_missing_params_returns_error_page(self, client):
        # No query params → "Missing parameters" page
        resp = client.get("/api/auth/approve-user")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "Missing parameters" in body

    def test_missing_token_returns_error(self, client):
        resp = client.get(
            "/api/auth/approve-user?user_id=u1&email=a@x.com",
        )
        body = resp.get_data(as_text=True)
        assert "Missing parameters" in body

    def test_server_error_when_secret_missing(self, client, monkeypatch):
        # Secret env var missing → _get_hmac_secret raises → caught
        monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
        resp = client.get(
            "/api/auth/approve-user?user_id=u1&email=a@x.com&token=fake",
        )
        body = resp.get_data(as_text=True)
        assert "Server configuration error" in body

    def test_invalid_token_rejected(self, client, monkeypatch):
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "s")
        resp = client.get(
            "/api/auth/approve-user?user_id=u1&email=a@x.com&token=wrongsig",
        )
        body = resp.get_data(as_text=True)
        assert "Invalid or expired" in body

    def test_valid_token_approves_user(self, client, monkeypatch):
        from backend.routes.auth_routes import _sign_approval
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "s")
        token = _sign_approval("u1", "alice@x.com")

        mock_sb = MagicMock()
        with patch("backend.routes.auth_routes._get_supabase",
                   return_value=mock_sb):
            resp = client.get(
                f"/api/auth/approve-user?user_id=u1&email=alice@x.com&token={token}",
            )
        body = resp.get_data(as_text=True)
        assert "alice@x.com has been approved" in body
        # VB10: approval written to app_metadata (service-role-only), not
        # the client-settable user_metadata.
        mock_sb.auth.admin.update_user_by_id.assert_called_once_with(
            "u1", {"app_metadata": {"approved": True}},
        )

    def test_supabase_error_returns_failure_page(self, client, monkeypatch):
        from backend.routes.auth_routes import _sign_approval
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "s")
        token = _sign_approval("u1", "alice@x.com")

        mock_sb = MagicMock()
        mock_sb.auth.admin.update_user_by_id.side_effect = RuntimeError("db down")
        with patch("backend.routes.auth_routes._get_supabase",
                   return_value=mock_sb):
            resp = client.get(
                f"/api/auth/approve-user?user_id=u1&email=alice@x.com&token={token}",
            )
        body = resp.get_data(as_text=True)
        assert "Failed to approve user" in body


# ──────────────────────────────────────────────────────────────────
# /api/auth/approval-status
# ──────────────────────────────────────────────────────────────────


class TestApprovalStatus:
    """The approval-status endpoint uses g.user_id (set by the
    `before_request` hook in `backend/auth.py`).

    Issue #353 (2026-05-15): the dev-shim at `auth.py:185-190` now sets
    `g.is_dev_shim = True` for any teacher_id resolved via the
    `X-Test-Teacher-Id` header, not just the literal `'local-dev'`.
    `approval_status` bypasses Supabase for any dev-shim user (the
    load harness and `multi-teacher.spec.js` previously 500'd here).
    To exercise the production Supabase lookup path these tests send a
    Bearer JWT — the dev-shim explicitly skips it per `auth.py:185`
    `and not has_bearer` — and mock `validate_token`.
    """

    def test_local_dev_always_approved(self, client, monkeypatch):
        """Backward-compat: literal `local-dev` via dev-shim."""
        monkeypatch.setenv("FLASK_ENV", "development")
        resp = client.get(
            "/api/auth/approval-status",
            headers={"X-Test-Teacher-Id": "local-dev"},
        )
        body = resp.get_json()
        assert body["approved"] is True

    def test_any_dev_shim_teacher_id_approved(self, client, monkeypatch):
        """Issue #353: dev-shim teachers OTHER than 'local-dev' (e.g.
        load harness or `multi-teacher.spec.js` `teach-A`) are also
        approved without hitting Supabase. Pre-fix this 500'd because
        only the literal `'local-dev'` was bypassed."""
        monkeypatch.setenv("FLASK_ENV", "development")
        resp = client.get(
            "/api/auth/approval-status",
            headers={"X-Test-Teacher-Id": "teach-A"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["approved"] is True

    def test_real_user_supabase_metadata_lookup(self, client, monkeypatch):
        monkeypatch.setenv("FLASK_ENV", "development")

        mock_user = MagicMock()
        mock_user.email = "alice@x.com"
        # VB10: approval read from app_metadata; first_name stays in user_metadata.
        mock_user.app_metadata = {"approved": True}
        mock_user.user_metadata = {"first_name": "Alice"}
        mock_resp = MagicMock()
        mock_resp.user = mock_user

        mock_sb = MagicMock()
        mock_sb.auth.admin.get_user_by_id.return_value = mock_resp

        with patch("backend.auth.validate_token",
                   return_value={"sub": "real-user-123",
                                 "email": "alice@x.com"}), \
             patch("backend.routes.auth_routes._get_supabase",
                   return_value=mock_sb):
            resp = client.get(
                "/api/auth/approval-status",
                headers={"Authorization": "Bearer fake-jwt"},
            )

        body = resp.get_json()
        assert body["approved"] is True
        assert body["email"] == "alice@x.com"
        assert body["first_name"] == "Alice"

    def test_unapproved_user_returns_false(self, client, monkeypatch):
        monkeypatch.setenv("FLASK_ENV", "development")

        mock_user = MagicMock()
        mock_user.email = "bob@x.com"
        # VB10: approval read from app_metadata (empty → not approved).
        mock_user.app_metadata = {}
        mock_user.user_metadata = {}
        mock_resp = MagicMock()
        mock_resp.user = mock_user

        mock_sb = MagicMock()
        mock_sb.auth.admin.get_user_by_id.return_value = mock_resp

        with patch("backend.auth.validate_token",
                   return_value={"sub": "unapproved-user",
                                 "email": "bob@x.com"}), \
             patch("backend.routes.auth_routes._get_supabase",
                   return_value=mock_sb):
            resp = client.get(
                "/api/auth/approval-status",
                headers={"Authorization": "Bearer fake-jwt"},
            )

        body = resp.get_json()
        assert body["approved"] is False

    def test_supabase_error_returns_500(self, client, monkeypatch):
        monkeypatch.setenv("FLASK_ENV", "development")

        mock_sb = MagicMock()
        mock_sb.auth.admin.get_user_by_id.side_effect = RuntimeError("supabase down")

        with patch("backend.auth.validate_token",
                   return_value={"sub": "real-user",
                                 "email": "real@x.com"}), \
             patch("backend.routes.auth_routes._get_supabase",
                   return_value=mock_sb):
            resp = client.get(
                "/api/auth/approval-status",
                headers={"Authorization": "Bearer fake-jwt"},
            )

        assert resp.status_code == 500
        assert "error" in resp.get_json()


# ──────────────────────────────────────────────────────────────────
# /api/auth/notify-signup
# ──────────────────────────────────────────────────────────────────


class TestNotifySignupRoute:
    def test_missing_email_returns_400(self, client):
        resp = client.post("/api/auth/notify-signup", json={})
        assert resp.status_code == 400
        assert "Missing email" in resp.get_json()["error"]

    def test_missing_admin_email_skips(self, client, monkeypatch):
        monkeypatch.delenv("ADMIN_EMAIL", raising=False)
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        resp = client.post(
            "/api/auth/notify-signup",
            json={"email": "alice@x.com"},
        )
        body = resp.get_json()
        assert body["status"] == "skipped"

    def test_missing_resend_key_skips(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAIL", "admin@x.com")
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        resp = client.post(
            "/api/auth/notify-signup",
            json={"email": "alice@x.com"},
        )
        assert resp.get_json()["status"] == "skipped"

    def test_happy_path_sends_resend_email(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAIL", "admin@x.com")
        monkeypatch.setenv("RESEND_API_KEY", "re_test_xyz")
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "s")

        # Mock supabase user lookup
        mock_user = MagicMock()
        mock_user.email = "alice@x.com"
        mock_user.id = "user-1"
        mock_sb = MagicMock()
        mock_sb.auth.admin.list_users.return_value = [mock_user]

        with patch("backend.routes.auth_routes._get_supabase",
                   return_value=mock_sb), \
             patch("backend.routes.auth_routes.requests.post") as mock_post:
            resp = client.post(
                "/api/auth/notify-signup",
                json={
                    "email": "alice@x.com",
                    "first_name": "Alice",
                    "last_name": "Smith",
                },
            )

        assert resp.get_json()["status"] == "ok"
        # Resend API was called
        mock_post.assert_called_once()
        url = mock_post.call_args.args[0]
        assert "api.resend.com" in url
        # Auth header has the resend key
        headers = mock_post.call_args.kwargs["headers"]
        assert "re_test_xyz" in headers["Authorization"]
        # Body contains the email
        payload = mock_post.call_args.kwargs["json"]
        assert "Alice Smith" in payload["subject"]
        assert payload["to"] == ["admin@x.com"]

    def test_user_not_found_omits_approve_link(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAIL", "admin@x.com")
        monkeypatch.setenv("RESEND_API_KEY", "re_test_xyz")
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "s")

        # Empty user list → no approve link built
        mock_sb = MagicMock()
        mock_sb.auth.admin.list_users.return_value = []

        with patch("backend.routes.auth_routes._get_supabase",
                   return_value=mock_sb), \
             patch("backend.routes.auth_routes.requests.post") as mock_post:
            resp = client.post(
                "/api/auth/notify-signup",
                json={"email": "alice@x.com", "first_name": "Alice"},
            )

        assert resp.get_json()["status"] == "ok"
        # Email still sent (just without the approve button)
        mock_post.assert_called_once()
        html = mock_post.call_args.kwargs["json"]["html"]
        # No "Approve Alice" button text
        assert "Approve Alice" not in html

    def test_supabase_lookup_error_swallowed(self, client):
        # Use patch.dict for env (more reliable cross-test than monkeypatch
        # in this fixture chain — saw intra-class pollution otherwise).
        with patch.dict("os.environ", {
            "ADMIN_EMAIL": "admin@x.com",
            "RESEND_API_KEY": "re_test_xyz",
            "SUPABASE_JWT_SECRET": "s",
        }), patch("backend.routes.auth_routes._get_supabase",
                  side_effect=RuntimeError("supabase down")), \
             patch("backend.routes.auth_routes.requests.post") as mock_post:
            resp = client.post(
                "/api/auth/notify-signup",
                json={"email": "alice@x.com"},
            )

        body = resp.get_json()
        assert body is not None
        assert body["status"] == "ok", f"got: {body}"
        mock_post.assert_called_once()

    def test_resend_post_exception_swallowed(self, client, monkeypatch):
        # Top-level `try/except Exception` swallows resend errors and
        # still returns "ok"
        monkeypatch.setenv("ADMIN_EMAIL", "admin@x.com")
        monkeypatch.setenv("RESEND_API_KEY", "re_test_xyz")
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "s")

        mock_sb = MagicMock()
        mock_sb.auth.admin.list_users.return_value = []

        with patch("backend.routes.auth_routes._get_supabase",
                   return_value=mock_sb), \
             patch("backend.routes.auth_routes.requests.post",
                   side_effect=ConnectionError("resend unreachable")):
            resp = client.post(
                "/api/auth/notify-signup",
                json={"email": "alice@x.com"},
            )

        # Fire-and-forget contract — still returns ok
        assert resp.get_json()["status"] == "ok"

    def test_supabase_url_used_for_dashboard_link(self, client, monkeypatch):
        # Dashboard link uses project_ref derived from SUPABASE_URL
        monkeypatch.setenv("ADMIN_EMAIL", "admin@x.com")
        monkeypatch.setenv("RESEND_API_KEY", "re_test_xyz")
        monkeypatch.setenv("SUPABASE_URL", "https://abc123xyz.supabase.co")
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "s")

        mock_sb = MagicMock()
        mock_sb.auth.admin.list_users.return_value = []

        with patch("backend.routes.auth_routes._get_supabase",
                   return_value=mock_sb), \
             patch("backend.routes.auth_routes.requests.post") as mock_post:
            client.post(
                "/api/auth/notify-signup",
                json={"email": "alice@x.com"},
            )

        html = mock_post.call_args.kwargs["json"]["html"]
        assert "supabase.com/dashboard/project/abc123xyz" in html

    def test_supabase_url_missing_fallback_dashboard(
        self, client, monkeypatch,
    ):
        monkeypatch.setenv("ADMIN_EMAIL", "admin@x.com")
        monkeypatch.setenv("RESEND_API_KEY", "re_test_xyz")
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "s")

        mock_sb = MagicMock()
        mock_sb.auth.admin.list_users.return_value = []

        with patch("backend.routes.auth_routes._get_supabase",
                   return_value=mock_sb), \
             patch("backend.routes.auth_routes.requests.post") as mock_post:
            client.post(
                "/api/auth/notify-signup",
                json={"email": "alice@x.com"},
            )

        html = mock_post.call_args.kwargs["json"]["html"]
        # Falls back to bare dashboard URL
        assert "supabase.com/dashboard" in html
