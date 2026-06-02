"""
Contract tests for Clever SSO HTTP surface.

These tests pin the *HTTP contract* — URLs, response shapes, status codes,
redirect targets — so Phase 2 (exception audit) and Phase 3 (monolith split)
refactors cannot silently break SIS compliance.

Pinned contracts (verified against backend/routes/clever_routes.py):

  GET /api/clever/login-url
    - 200 with {"url": "https://clever.com/oauth/authorize?..."} when configured
      (URL includes client_id, redirect_uri, response_type=code, scope)
    - 503 with {"error": "Clever not configured"} when config missing

  GET /api/clever/callback
    - 302 redirect to "/?clever_error=missing_code" when no ?code param
    - 302 redirect to "/?clever_error=token_exchange_failed" when the Clever
      token endpoint returns any non-200 (401, 500, etc.) — NOT a raw 4xx/5xx
      to the browser.  Contract surprise vs spec: the route collapses upstream
      401 AND upstream 5xx into the same 302 redirect, because
      exchange_code_for_token() returns None on any non-200 and the callback
      only branches on truthiness. 502 does NOT appear in this route — it's
      exclusive to /api/clever/sync-roster.

  GET /api/clever/session
    - 200 with {"authenticated": false} when no session cookie
    - 200 with {"authenticated": true, ...} when clever_user is in session

Zero real network calls — all external dependencies are mocked.
"""
from unittest.mock import patch, AsyncMock
from urllib.parse import urlparse, parse_qs

from flask import Flask


# ---------------------------------------------------------------------------
# App fixture (mirrors tests/test_clever_callback.py pattern)
# ---------------------------------------------------------------------------

def _make_app():
    """Minimal Flask app with the clever blueprint registered."""
    from backend.routes.clever_routes import clever_bp
    app = Flask(__name__)
    app.secret_key = "test-secret-key"
    app.register_blueprint(clever_bp)
    return app


# ---------------------------------------------------------------------------
# 1. /api/clever/login-url — happy path contract
# ---------------------------------------------------------------------------

class TestLoginUrlContract:

    def test_login_url_contract(self):
        """GET /api/clever/login-url returns 200 with an authorize URL
        containing client_id, redirect_uri, response_type=code, and scope."""
        app = _make_app()

        fake_config = {
            "client_id": "test-client-id",
            "client_secret": "test-secret",
            "redirect_uri": "https://app.graider.live/api/clever/callback",
        }
        authorize_url = (
            "https://clever.com/oauth/authorize"
            "?response_type=code"
            "&client_id=test-client-id"
            "&redirect_uri=https%3A%2F%2Fapp.graider.live%2Fapi%2Fclever%2Fcallback"
            "&scope=read%3Auser_id%20read%3Asis"
            "&state=abc123"
        )

        with patch("backend.routes.clever_routes.get_clever_config",
                   return_value=fake_config), \
             patch("backend.routes.clever_routes.get_authorize_url",
                   return_value=authorize_url):
            with app.test_client() as client:
                resp = client.get("/api/clever/login-url")

        assert resp.status_code == 200
        body = resp.get_json()
        assert "url" in body, "contract requires 'url' key in response"

        url = body["url"]
        assert url.startswith("https://clever.com/oauth/authorize"), \
            f"URL must start with clever.com/oauth/authorize, got {url!r}"

        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        # Contract surface: each of these must be present
        assert "client_id" in qs
        assert "redirect_uri" in qs
        assert qs.get("response_type") == ["code"]
        assert "scope" in qs

    def test_login_url_redirect_param_302s_to_provider(self):
        """GET /api/clever/login-url?redirect=1 → 302 straight to the authorize
        URL (cross-origin landing page initiates SSO via top-level nav so the
        session cookie sets first-party). No param still returns JSON."""
        app = _make_app()
        fake_config = {
            "client_id": "test-client-id", "client_secret": "s",
            "redirect_uri": "https://app.graider.live/api/clever/callback",
        }
        authorize_url = ("https://clever.com/oauth/authorize?response_type=code"
                         "&client_id=test-client-id&state=abc123")
        with patch("backend.routes.clever_routes.get_clever_config",
                   return_value=fake_config), \
             patch("backend.routes.clever_routes.get_authorize_url",
                   return_value=authorize_url):
            with app.test_client() as client:
                resp = client.get("/api/clever/login-url?redirect=1")
        assert resp.status_code == 302
        assert resp.headers["Location"] == authorize_url
        # The point of redirect mode: the session cookie is set on THIS response
        # (top-level nav, first-party) so oauth_state survives to the callback.
        assert "session=" in resp.headers.get("Set-Cookie", "")

    def test_login_url_missing_config(self):
        """GET /api/clever/login-url returns 503 when Clever config absent."""
        app = _make_app()

        with patch("backend.routes.clever_routes.get_clever_config",
                   return_value=None):
            with app.test_client() as client:
                resp = client.get("/api/clever/login-url")

        assert resp.status_code == 503, \
            "Missing Clever config must return 503 (service unavailable)"
        body = resp.get_json()
        assert "error" in body
        assert "configured" in body["error"].lower()


# ---------------------------------------------------------------------------
# 2. /api/clever/callback — failure-mode contracts
# ---------------------------------------------------------------------------

class TestCallbackContract:

    def test_callback_missing_code_contract(self):
        """GET /api/clever/callback without ?code redirects (302) to
        /?clever_error=missing_code. Contract: NEVER a raw 400 to the browser."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.get("/api/clever/callback")

        assert resp.status_code == 302, \
            "Missing code must produce a 302 redirect, not a 4xx JSON error"
        assert resp.location is not None
        assert "clever_error=missing_code" in resp.location
        # Redirect target must be root-relative (stays on Graider origin)
        assert resp.location.startswith("/?") or resp.location.startswith("/?"), \
            f"Redirect must target site root, got {resp.location!r}"

    def test_callback_token_exchange_failure_contract(self):
        """When Clever's token endpoint returns 401 (invalid code), the
        callback MUST redirect 302 to /?clever_error=token_exchange_failed —
        NOT surface a raw 401 to the end user."""
        app = _make_app()

        with patch("backend.routes.clever_routes.exchange_code_for_token",
                   new=AsyncMock(return_value=None)):
            with app.test_client() as client:
                # No state on either side — Instant-Login branch, allowed.
                resp = client.get("/api/clever/callback?code=bogus-code")

        assert resp.status_code == 302, \
            "Token exchange failure must redirect, not return 401 to the user"
        assert resp.location is not None
        assert "clever_error=token_exchange_failed" in resp.location
        assert resp.location.startswith("/?"), \
            f"Redirect must be same-origin, got {resp.location!r}"

    def test_callback_upstream_5xx_contract(self):
        """When the Clever token endpoint is down (upstream 5xx),
        exchange_code_for_token() returns None, so the callback collapses
        to the same 302 → /?clever_error=token_exchange_failed as a 401.

        Contract surprise: the route does NOT return 502 on upstream 5xx —
        502 only appears in /api/clever/sync-roster. This test pins the
        actual behavior so refactors don't accidentally "improve" it
        without updating the frontend error handler."""
        app = _make_app()

        # Simulate upstream 5xx the same way exchange_code_for_token handles
        # it in production: resp.status_code != 200 → returns None.
        with patch("backend.routes.clever_routes.exchange_code_for_token",
                   new=AsyncMock(return_value=None)):
            with app.test_client() as client:
                resp = client.get("/api/clever/callback?code=any-code")

        assert resp.status_code == 302, \
            "Upstream 5xx must NOT bubble up as a 5xx to the browser"
        assert resp.location is not None
        assert "clever_error=token_exchange_failed" in resp.location


# ---------------------------------------------------------------------------
# 3. /api/clever/session — unauthenticated shape
# ---------------------------------------------------------------------------

class TestSessionContract:

    def test_session_no_auth_contract(self):
        """GET /api/clever/session with no session cookie returns 200 with
        {"authenticated": false}. Contract: status is 200 (NOT 401), and
        the key is literally "authenticated" (NOT "user": null or similar)."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.get("/api/clever/session")

        assert resp.status_code == 200, \
            "Unauthenticated session check must be 200, not 401"
        body = resp.get_json()
        assert body is not None
        assert "authenticated" in body, \
            "Response must include 'authenticated' key (not 'user', not 'loggedIn')"
        assert body["authenticated"] is False, \
            "Unauthenticated response must set authenticated=false (boolean)"
