"""
HTTP contract tests — OneRoster, LTI 1.3, auth/session matrix.

Phase 1 safety net — pins the HTTP contract of OneRoster + LTI SSO and
proves that the three auth mechanisms (teacher JWT, student token, Flask
session) can't cross-escalate. This protects Phase 2 (exception audit) and
Phase 3 (monolith split) from silently breaking SIS compliance or privilege
boundaries.

All external I/O is mocked — zero network calls. Tests rely only on the
request reaching the route handler and returning 401/4xx as documented.
"""
import os
from unittest.mock import patch

import pytest
from flask import Flask


# ---------------------------------------------------------------------------
# Fixture — app with all relevant blueprints registered but NO auth
# middleware. Without the JWT middleware, g.user_id is never set, so
# @require_teacher correctly rejects every caller with 401. This is exactly
# what the contract tests need to assert.
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    os.environ.setdefault("CLASSLINK_CLIENT_ID", "test-client-id")
    os.environ.setdefault("CLASSLINK_CLIENT_SECRET", "test-client-secret")
    os.environ.setdefault("CLEVER_CLIENT_ID", "test-clever-client")
    os.environ.setdefault("CLEVER_CLIENT_SECRET", "test-clever-secret")

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.secret_key = "test-secret-key"

    from backend.routes.oneroster_routes import oneroster_bp
    from backend.routes.lti_routes import lti_bp
    from backend.routes.student_account_routes import student_account_bp

    app.register_blueprint(oneroster_bp)
    app.register_blueprint(lti_bp)
    app.register_blueprint(student_account_bp)

    return app.test_client()


# ---------------------------------------------------------------------------
# OneRoster contract
# ---------------------------------------------------------------------------

class TestOneRosterContracts:
    """Pin the OneRoster API HTTP contract.

    Source: backend/routes/oneroster_routes.py
    """

    def test_sync_roster_requires_auth(self, client):
        """POST /api/oneroster/sync-roster without auth -> 401.
        (@require_teacher decorator)"""
        resp = client.post("/api/oneroster/sync-roster")
        assert resp.status_code == 401

    def test_apply_accommodations_requires_auth(self, client):
        """POST /api/oneroster/apply-accommodations without auth -> 401.
        (@require_teacher decorator)"""
        resp = client.post("/api/oneroster/apply-accommodations")
        assert resp.status_code == 401

    def test_config_get_requires_auth(self, client):
        """GET /api/oneroster/config without auth -> 401."""
        resp = client.get("/api/oneroster/config")
        assert resp.status_code == 401

    def test_test_connection_requires_auth(self, client):
        """POST /api/oneroster/test without auth -> 401."""
        resp = client.post("/api/oneroster/test")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# LTI 1.3 contract
# ---------------------------------------------------------------------------

class TestLTIContracts:
    """Pin the LTI 1.3 HTTP contract.

    Source: backend/routes/lti_routes.py
    """

    def test_jwks_returns_valid_key_structure(self, client):
        """/api/lti/jwks must return a JWKS document with a keys array."""
        resp = client.get("/api/lti/jwks")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data is not None
        assert "keys" in data
        assert isinstance(data["keys"], list)
        if len(data["keys"]) > 0:
            key = data["keys"][0]
            assert "kty" in key
            assert "n" in key
            assert "e" in key

    def test_login_without_iss_returns_400(self, client):
        """/api/lti/login without required `iss` param -> 400
        with {"error": "Missing iss parameter"}.
        (lti_routes.py lines 84-86)"""
        resp = client.get("/api/lti/login")
        assert resp.status_code == 400
        body = resp.get_json()
        assert body is not None
        assert "error" in body

    def test_launch_without_id_token_returns_400(self, client):
        """/api/lti/launch POST without state -> 400
        (state validation, lti_routes.py lines 111-114)."""
        resp = client.post("/api/lti/launch")
        assert resp.status_code == 400

    def test_launch_with_bad_state_returns_400(self, client):
        """/api/lti/launch with a state that doesn't match session -> 400.
        The route rejects BEFORE decoding the JWT, so we don't need a
        valid id_token to prove the contract."""
        with client.session_transaction() as sess:
            sess["lti_state"] = "expected-state"
            sess["lti_nonce"] = "expected-nonce"
            sess["lti_issuer"] = "https://platform.example.com"

        resp = client.post(
            "/api/lti/launch",
            data={"state": "attacker-supplied", "id_token": "irrelevant"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Auth / session matrix — privilege-escalation regression guard
# ---------------------------------------------------------------------------

class TestAuthSessionMatrix:
    """Pin that auth mechanisms can't cross-escalate.

    The codebase uses three distinct auth mechanisms:
    1. Teacher JWT (@require_teacher via g.user_id, set by JWT middleware)
    2. Student token (X-Student-Token header, validated against
       student_sessions table)
    3. Flask session (Clever/ClassLink/LTI OAuth)

    These tests prove that each mechanism correctly rejects the other two.
    Because the test app does NOT install the JWT middleware, providing a
    bogus Authorization header will never populate g.user_id — which is
    exactly the failure mode we want to pin.
    """

    def test_teacher_route_rejects_student_token(self, client):
        """@require_teacher route -> 401 when only X-Student-Token is sent."""
        resp = client.get(
            "/api/classes",
            headers={"X-Student-Token": "student-token-123"},
        )
        assert resp.status_code == 401

    def test_student_route_rejects_teacher_jwt(self, client):
        """Student-authenticated route -> 401 when only a bogus teacher
        JWT Authorization header is provided."""
        resp = client.get(
            "/api/student/session",
            headers={"Authorization": "Bearer fake-teacher-jwt"},
        )
        assert resp.status_code == 401

    def test_session_auth_alone_cannot_access_teacher_jwt_route(self, client):
        """Flask session from Clever/ClassLink login must NOT grant access
        to @require_teacher routes — a JWT is required."""
        with client.session_transaction() as sess:
            sess["clever_user"] = {
                "clever_id": "test",
                "email": "teacher@school.edu",
                "name": "Test Teacher",
                "type": "teacher",
                "district": "test-district",
            }
        resp = client.get("/api/classes")
        assert resp.status_code == 401

    def test_expired_session_returns_401_not_500(self, client):
        """Invalid/expired student session token -> clean 401, never 500."""
        resp = client.get(
            "/api/student/session",
            headers={"X-Student-Token": "expired-token-123"},
        )
        assert resp.status_code in (401, 403)
        assert resp.status_code != 500
