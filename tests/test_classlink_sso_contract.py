"""
Contract tests for ClassLink SSO HTTP surface.

These tests pin the *HTTP contract* — URLs, response shapes, status codes,
redirect targets — so Phase 2 (exception audit) and Phase 3 (monolith split)
refactors cannot silently break SIS compliance.

Pinned contracts (verified against backend/routes/classlink_routes.py):

  GET /api/classlink/login-url
    - 200 with {"url": "https://launchpad.classlink.com/oauth2/v2/auth?..."} when
      configured. URL MUST include client_id, redirect_uri, response_type=code,
      scope, and a CSRF state token.
    - 400 with {"error": "ClassLink SSO is not configured"} when CLASSLINK_CLIENT_ID
      is empty.  Contract surprise vs Clever (which returns 503): ClassLink's
      route returns 400. This is pinned here so refactors don't "normalize" it
      without coordinating with the frontend.

  GET /api/classlink/callback
    - 302 redirect to "/?classlink_error=no_code" when no ?code param.
      Contract surprise vs spec: the error token is "no_code", NOT "missing_code"
      as in the Clever route. Frontend error handler branches on this literal.
    - 302 redirect to "/?classlink_error=token_failed" when the ClassLink token
      endpoint returns any non-200 (400, 401, 5xx, etc.). The route collapses
      ALL token-exchange failure modes into the single "token_failed" token.

  GET /api/classlink/session
    - 200 with {"authenticated": false} when no session cookie present.
      Status is 200 (NOT 401), shape uses the key "authenticated" (boolean).

Zero real network calls — all external dependencies are mocked.
"""
import os
from unittest.mock import patch, MagicMock
from urllib.parse import urlparse, parse_qs

from flask import Flask


# ---------------------------------------------------------------------------
# App fixture (mirrors tests/test_classlink_sso.py pattern)
# ---------------------------------------------------------------------------

def _make_app():
    """Minimal Flask app with the ClassLink blueprint registered."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.secret_key = "test-secret-key"

    # Ensure ClassLink client id is present for login-url happy path.
    os.environ['CLASSLINK_CLIENT_ID'] = 'test-client-id'
    os.environ['CLASSLINK_CLIENT_SECRET'] = 'test-client-secret'

    from backend.routes.classlink_routes import classlink_bp
    app.register_blueprint(classlink_bp)
    return app


# ---------------------------------------------------------------------------
# 1. /api/classlink/login-url — happy path contract
# ---------------------------------------------------------------------------

class TestLoginUrlContract:

    def test_login_url_contract(self):
        """GET /api/classlink/login-url returns 200 with a ClassLink LaunchPad
        authorize URL containing client_id, redirect_uri, response_type=code,
        scope, and a CSRF state token."""
        app = _make_app()

        with app.test_client() as client:
            resp = client.get("/api/classlink/login-url")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body is not None
        assert "url" in body, "contract requires 'url' key in response"

        url = body["url"]
        # Pin the exact authorize host — SIS compliance depends on hitting
        # launchpad.classlink.com, not a generic OAuth proxy.
        assert url.startswith("https://launchpad.classlink.com/oauth2/v2/auth"), (
            f"URL must start with ClassLink LaunchPad authorize endpoint, got {url!r}"
        )

        parsed = urlparse(url)
        qs = parse_qs(parsed.query)

        # Contract surface: each of these MUST be present.
        assert qs.get("client_id") == ["test-client-id"]
        assert "redirect_uri" in qs
        assert qs.get("response_type") == ["code"]
        assert "scope" in qs
        # CSRF state token must always be emitted.
        assert "state" in qs and qs["state"][0], \
            "login-url must emit a non-empty CSRF state token"


# ---------------------------------------------------------------------------
# 2. /api/classlink/callback — failure-mode contracts
# ---------------------------------------------------------------------------

class TestCallbackContract:

    def test_callback_missing_code_contract(self):
        """GET /api/classlink/callback without ?code redirects (302) to
        /?classlink_error=no_code. Contract: NEVER a raw 400 to the browser.

        Contract surprise: the error token is literally "no_code", NOT
        "missing_code" as in the Clever route. The frontend error handler
        pattern-matches this string — any rename requires a paired frontend
        change."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.get("/api/classlink/callback")

        assert resp.status_code == 302, \
            "Missing code must produce a 302 redirect, not a 4xx JSON error"
        assert resp.location is not None
        assert "classlink_error=no_code" in resp.location, (
            f"Missing-code redirect must use 'classlink_error=no_code', "
            f"got {resp.location!r}"
        )
        # Redirect target must be root-relative (stays on Graider origin).
        assert resp.location.startswith("/?"), \
            f"Redirect must target site root, got {resp.location!r}"

    def test_callback_token_failure_contract(self):
        """When ClassLink's token endpoint returns a non-200 (e.g. 400 invalid
        grant, 401 bad client, 5xx outage), the callback MUST redirect 302 to
        /?classlink_error=token_failed — NOT surface the upstream status to
        the browser.

        Contract surprise: the route collapses ALL non-200 token-endpoint
        responses (4xx AND 5xx) into the same 'token_failed' token. If a
        refactor wants to distinguish 5xx as a 502, the frontend error
        handler must be updated in the same change."""
        app = _make_app()

        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 500  # simulate upstream outage
        mock_token_resp.text = "internal error"
        mock_token_resp.json.return_value = {}

        with app.test_client() as client:
            # No state on either side → ClassLink-initiated branch, allowed.
            with patch(
                "backend.routes.classlink_routes.requests.post",
                return_value=mock_token_resp,
            ):
                resp = client.get("/api/classlink/callback?code=bogus-code")

        assert resp.status_code == 302, \
            "Token exchange failure must redirect, not return 5xx to the user"
        assert resp.location is not None
        assert "classlink_error=token_failed" in resp.location, (
            f"Token-failure redirect must use 'classlink_error=token_failed', "
            f"got {resp.location!r}"
        )
        assert resp.location.startswith("/?"), \
            f"Redirect must be same-origin, got {resp.location!r}"


# ---------------------------------------------------------------------------
# 3. /api/classlink/session — unauthenticated shape
# ---------------------------------------------------------------------------

class TestSessionContract:

    def test_session_no_auth_contract(self):
        """GET /api/classlink/session with no session cookie returns 200 with
        {"authenticated": false}. Contract: status is 200 (NOT 401), and the
        key is literally "authenticated" (NOT "user": null or similar)."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.get("/api/classlink/session")

        assert resp.status_code == 200, \
            "Unauthenticated session check must be 200, not 401"
        body = resp.get_json()
        assert body is not None
        assert "authenticated" in body, \
            "Response must include 'authenticated' key (not 'user', not 'loggedIn')"
        assert body["authenticated"] is False, \
            "Unauthenticated response must set authenticated=false (boolean)"
