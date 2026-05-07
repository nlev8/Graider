"""Tests for school admin routes.

Covers auth requirements, status, claim validation, and admin-only access.
"""
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask, g


@pytest.fixture
def app():
    """Create a minimal Flask app with admin routes registered."""
    from backend.routes.admin_routes import admin_bp

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.register_blueprint(admin_bp)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def authed_app(app):
    """App with before_request that sets g.user_id from header."""
    @app.before_request
    def set_test_user():
        from flask import request
        teacher_id = request.headers.get("X-Test-Teacher-Id")
        if teacher_id:
            g.user_id = teacher_id

    return app


@pytest.fixture
def authed_client(authed_app):
    return authed_app.test_client()


# ── Status Tests ─────────────────────────────────────────────────────────

class TestAdminStatus:
    """Test GET /api/admin/status."""

    def test_status_requires_auth(self, client):
        """Status without auth returns 401."""
        resp = client.get("/api/admin/status")
        assert resp.status_code == 401

    def test_status_returns_false_for_non_admin(self, authed_client):
        """Non-admin teacher gets is_admin: false."""
        with patch("backend.routes.admin_routes.storage_load", return_value=None):
            resp = authed_client.get("/api/admin/status",
                                     headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["is_admin"] is False

    def test_status_returns_true_for_admin(self, authed_client):
        """Admin teacher gets is_admin: true with school name."""
        admin_role = {"school": "Lincoln High", "claimed_at": "2026-03-20T00:00:00"}

        def mock_load(key, teacher_id):
            if key == "admin_role:teacher-123":
                return admin_role
            return None

        with patch("backend.routes.admin_routes.storage_load", side_effect=mock_load), \
             patch("backend.routes.admin_routes.audit_log"):
            resp = authed_client.get("/api/admin/status",
                                     headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["is_admin"] is True
            assert data["school"] == "Lincoln High"


# ── Claim Tests ──────────────────────────────────────────────────────────

class TestAdminClaim:
    """Test POST /api/admin/claim."""

    def test_claim_requires_auth(self, client):
        """Claim without auth returns 401."""
        resp = client.post("/api/admin/claim", json={"code": "ABC123"})
        assert resp.status_code == 401

    def test_claim_requires_code(self, authed_client):
        """Claim without code returns 400 (generic failure shape)."""
        resp = authed_client.post("/api/admin/claim", json={},
                                  headers={"X-Test-Teacher-Id": "teacher-123"})
        assert resp.status_code == 400

    def test_claim_invalid_code_returns_generic_400(self, authed_client):
        """Audit MAJOR #8 (Codex 2026-05-06): non-existent code returns
        the SAME generic 400 + error body as missing/expired/malformed,
        so the response shape carries zero validity signal."""
        with patch("backend.routes.admin_routes.storage_load", return_value=None):
            resp = authed_client.post("/api/admin/claim", json={"code": "BADCODE"},
                                      headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 400
            assert "Unable to claim invite" in resp.get_json()["error"]

    def test_claim_valid_code_succeeds(self, authed_client):
        """Claim with valid invite code creates admin role."""
        from datetime import datetime, timezone
        invite = {
            "school": "Lincoln High",
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "manual_teachers": [],
        }

        def mock_load(key, teacher_id):
            if key == "admin_invite:VALID1":
                return invite
            return None

        with patch("backend.routes.admin_routes.storage_load", side_effect=mock_load), \
             patch("backend.routes.admin_routes.storage_save") as mock_save, \
             patch("backend.storage.delete") as mock_delete, \
             patch("backend.routes.admin_routes.audit_log"):
            resp = authed_client.post("/api/admin/claim", json={"code": "VALID1"},
                                      headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "claimed"
            assert data["school"] == "Lincoln High"
            # Verify admin_role was saved
            mock_save.assert_called_once()
            save_args = mock_save.call_args[0]
            assert save_args[0] == "admin_role:teacher-123"

    def test_claim_expired_code_returns_generic_400(self, authed_client):
        """Audit MAJOR #8: expired invite returns the same generic 400 +
        error shape as invalid/missing — no enumeration signal."""
        invite = {
            "school": "Lincoln High",
            "created_at": "2026-03-01T00:00:00+00:00",  # well past 7 days
        }

        def mock_load(key, teacher_id):
            if key == "admin_invite:EXPIRED":
                return invite
            return None

        with patch("backend.routes.admin_routes.storage_load", side_effect=mock_load):
            resp = authed_client.post("/api/admin/claim", json={"code": "EXPIRED"},
                                      headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 400
            assert "Unable to claim invite" in resp.get_json()["error"]

    def test_claim_failure_shapes_are_indistinguishable(self, authed_client):
        """Audit MAJOR #8: missing code, invalid code, malformed invite,
        expired invite must ALL return byte-identical responses (same
        status code, same body) so an attacker can't distinguish them."""
        responses = []

        # 1. Empty code
        r1 = authed_client.post("/api/admin/claim", json={"code": ""},
                                headers={"X-Test-Teacher-Id": "t"})
        responses.append(("empty", r1.status_code, r1.get_json()))

        # 2. Non-existent code (storage_load returns None)
        with patch("backend.routes.admin_routes.storage_load", return_value=None):
            r2 = authed_client.post("/api/admin/claim", json={"code": "MISSING"},
                                    headers={"X-Test-Teacher-Id": "t"})
            responses.append(("missing", r2.status_code, r2.get_json()))

        # 3. Malformed invite shape (string instead of dict)
        with patch("backend.routes.admin_routes.storage_load", return_value="garbage"):
            r3 = authed_client.post("/api/admin/claim", json={"code": "MALFORMED"},
                                    headers={"X-Test-Teacher-Id": "t"})
            responses.append(("malformed", r3.status_code, r3.get_json()))

        # 4. Expired invite
        with patch("backend.routes.admin_routes.storage_load",
                   return_value={"school": "X", "created_at": "2026-03-01T00:00:00+00:00"}):
            r4 = authed_client.post("/api/admin/claim", json={"code": "EXPIRED"},
                                    headers={"X-Test-Teacher-Id": "t"})
            responses.append(("expired", r4.status_code, r4.get_json()))

        # 5. Bad created_at format (parse failure)
        with patch("backend.routes.admin_routes.storage_load",
                   return_value={"school": "X", "created_at": "garbage-date"}):
            r5 = authed_client.post("/api/admin/claim", json={"code": "BADDATE"},
                                    headers={"X-Test-Teacher-Id": "t"})
            responses.append(("bad-date", r5.status_code, r5.get_json()))

        # All 5 failure modes → IDENTICAL status code + body.
        statuses = {label: status for label, status, _ in responses}
        bodies = {label: body for label, _, body in responses}

        assert all(s == 400 for s in statuses.values()), (
            f"All admin-claim failures must return 400; got {statuses}"
        )
        unique_bodies = {tuple(sorted(b.items())) for b in bodies.values()}
        assert len(unique_bodies) == 1, (
            f"All admin-claim failure bodies must be byte-identical to "
            f"prevent enumeration; got {len(unique_bodies)} distinct shapes: {bodies}"
        )

    def test_claim_has_rate_limit_decorator(self):
        """Static-source pin (Audit MAJOR #8): the @limiter.limit decorator
        must remain on the admin_claim route. Without it, the route is
        brute-forceable by any authenticated teacher."""
        from pathlib import Path

        src = Path(__file__).resolve().parent.parent / "backend/routes/admin_routes.py"
        text = src.read_text()
        # Decorator order: @admin_bp.route + @limiter.limit + @require_teacher + ...
        # before def admin_claim. Limiter MUST be present and reasonable.
        assert "@limiter.limit(" in text, "admin_claim must carry @limiter.limit"
        # The exact budget shape — strict enough to choke enumeration
        assert '"10 per hour;5 per minute"' in text, (
            "admin_claim rate-limit budget must remain '10 per hour;5 per minute' "
            "(loosen only with a security review)."
        )


# ── Admin-Only Endpoint Tests ────────────────────────────────────────────

class TestAdminOnlyEndpoints:
    """Test that teachers/overview/activity/drill-down require admin."""

    def test_teachers_requires_admin(self, authed_client):
        """GET /api/admin/teachers without admin role returns 403."""
        with patch("backend.storage.load", return_value=None):
            resp = authed_client.get("/api/admin/teachers",
                                     headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 403

    def test_overview_requires_admin(self, authed_client):
        """GET /api/admin/overview without admin role returns 403."""
        with patch("backend.storage.load", return_value=None):
            resp = authed_client.get("/api/admin/overview",
                                     headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 403

    def test_activity_requires_admin(self, authed_client):
        """GET /api/admin/activity without admin role returns 403."""
        with patch("backend.storage.load", return_value=None):
            resp = authed_client.get("/api/admin/activity",
                                     headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 403

    def test_teacher_summary_requires_admin(self, authed_client):
        """GET /api/admin/teacher/<id>/summary without admin returns 403."""
        with patch("backend.storage.load", return_value=None):
            resp = authed_client.get("/api/admin/teacher/some-id/summary",
                                     headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 403

    def test_teachers_without_auth_returns_401(self, client):
        """GET /api/admin/teachers without any auth returns 401."""
        resp = client.get("/api/admin/teachers")
        assert resp.status_code == 401

    def test_overview_without_auth_returns_401(self, client):
        """GET /api/admin/overview without any auth returns 401."""
        resp = client.get("/api/admin/overview")
        assert resp.status_code == 401

    def test_activity_without_auth_returns_401(self, client):
        """GET /api/admin/activity without any auth returns 401."""
        resp = client.get("/api/admin/activity")
        assert resp.status_code == 401
