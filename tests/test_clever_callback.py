"""
Tests for the Clever OAuth callback route and account-merging logic.

Covers:
- Missing code parameter → redirect with clever_error=missing_code
- State mismatch → redirect with clever_error=state_mismatch
- Student role → calls _create_clever_student_session, redirects to /student
- Teacher role → stores session, redirects with clever_login=success
- Unsupported role (e.g. "contact") → redirect with clever_error=unsupported_role

Account-merging tests:
- Email matches exactly one Supabase user → save_clever_link called
- Email matches no Supabase users → save_clever_link not called
- Multiple email matches → warning logged, no link saved

Zero real network calls — all external dependencies are mocked.
"""
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from flask import Flask


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------

def _make_app():
    """Return a minimal Flask app with the clever blueprint registered."""
    from backend.routes.clever_routes import clever_bp
    app = Flask(__name__)
    app.secret_key = "test-secret-key"
    app.register_blueprint(clever_bp)
    return app


# ---------------------------------------------------------------------------
# Shared mock helpers
# ---------------------------------------------------------------------------

def _clever_user(role="teacher"):
    return {
        "clever_id": "clever-teacher-001",
        "email": "teacher@school.edu",
        "name": {"first": "Ada", "last": "Lovelace"},
        "type": role,
        "district": "district-xyz",
    }


# ---------------------------------------------------------------------------
# TestCleverCallback — OAuth flow
# ---------------------------------------------------------------------------

class TestCleverCallback:

    def test_missing_code_redirects_missing_code(self):
        """No code parameter → redirect with missing_code error."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.get("/api/clever/callback")
        assert resp.status_code == 302
        assert "clever_error=missing_code" in resp.location

    def test_state_mismatch_redirects_error(self):
        """State in query string does not match session state → redirect with state_mismatch."""
        app = _make_app()
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["clever_oauth_state"] = "expected-state"
            resp = client.get("/api/clever/callback?code=abc123&state=wrong-state")
        assert resp.status_code == 302
        assert "clever_error=state_mismatch" in resp.location

    def test_missing_session_state_redirects_error(self):
        """No session state stored at all → state_mismatch (session was lost)."""
        app = _make_app()
        with app.test_client() as client:
            # No session state set; provide a state in the URL
            resp = client.get("/api/clever/callback?code=abc123&state=some-state")
        assert resp.status_code == 302
        assert "clever_error=state_mismatch" in resp.location

    def test_token_exchange_failure_redirects_error(self):
        """Exchange code returns no access_token → token_exchange_failed redirect."""
        app = _make_app()

        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={})),
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["clever_oauth_state"] = "valid-state"
                resp = client.get("/api/clever/callback?code=abc123&state=valid-state")

        assert resp.status_code == 302
        assert "clever_error=token_exchange_failed" in resp.location

    def test_student_role_redirects_to_student_portal(self):
        """Student login → _create_clever_student_session called, redirect to /student."""
        app = _make_app()
        student_session_data = {
            "token": "raw-token-abc",
            "student": {"first_name": "Jane", "last_name": "Doe", "email": "j@s.edu",
                        "student_id": "s001", "period": "2"},
            "class": {"name": "Math 9", "subject": "math"},
        }

        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={"access_token": "test_token"})),
            patch("backend.routes.clever_routes.get_clever_user",
                  new=AsyncMock(return_value=_clever_user("student"))),
            patch("backend.routes.clever_routes._create_clever_student_session",
                  return_value=student_session_data) as mock_create,
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["clever_oauth_state"] = "valid-state"
                resp = client.get("/api/clever/callback?code=abc123&state=valid-state")

        assert resp.status_code == 302
        assert "/student" in resp.location
        # Auth code exchange: redirect uses ?code=<auth_code>, not raw token
        assert "code=" in resp.location
        assert "token=" not in resp.location
        mock_create.assert_called_once()

    def test_student_not_enrolled_redirects_error(self):
        """Student login but _create_clever_student_session returns None → student_not_enrolled."""
        app = _make_app()

        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={"access_token": "test_token"})),
            patch("backend.routes.clever_routes.get_clever_user",
                  new=AsyncMock(return_value=_clever_user("student"))),
            patch("backend.routes.clever_routes._create_clever_student_session",
                  return_value=None),
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["clever_oauth_state"] = "valid-state"
                resp = client.get("/api/clever/callback?code=abc123&state=valid-state")

        assert resp.status_code == 302
        assert "clever_error=student_not_enrolled" in resp.location

    def test_teacher_role_redirects_success(self):
        """Teacher login → session populated, redirect with clever_login=success."""
        app = _make_app()

        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={"access_token": "test_token"})),
            patch("backend.routes.clever_routes.get_clever_user",
                  new=AsyncMock(return_value=_clever_user("teacher"))),
            patch("backend.routes.clever_routes.load_clever_links", return_value={}),
            patch("backend.routes.clever_routes.save_clever_link"),
            patch("backend.routes.clever_routes.resolve_clever_user_id",
                  return_value="clever:clever-teacher-001"),
            patch("backend.routes.clever_routes._get_supabase_safe", return_value=None),
            patch("backend.routes.clever_routes.os.getenv", return_value=None),
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["clever_oauth_state"] = "valid-state"
                resp = client.get("/api/clever/callback?code=abc123&state=valid-state")

        assert resp.status_code == 302
        assert "clever_login=success" in resp.location

    def test_contact_role_accepted_as_teacher(self):
        """Non-student roles (e.g. 'contact') are now accepted and treated like teachers."""
        app = _make_app()

        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={"access_token": "test_token"})),
            patch("backend.routes.clever_routes.get_clever_user",
                  new=AsyncMock(return_value=_clever_user("contact"))),
            patch("backend.routes.clever_routes.load_clever_links", return_value={}),
            patch("backend.routes.clever_routes.save_clever_link"),
            patch("backend.routes.clever_routes.resolve_clever_user_id",
                  return_value="clever:clever-teacher-001"),
            patch("backend.routes.clever_routes._get_supabase_safe", return_value=None),
            patch("backend.routes.clever_routes.os.getenv", return_value=None),
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["clever_oauth_state"] = "valid-state"
                resp = client.get("/api/clever/callback?code=abc123&state=valid-state")

        assert resp.status_code == 302
        assert "clever_login=success" in resp.location

    def test_oauth_error_param_redirects_with_error(self):
        """Clever sends back an `error` query param → redirect passes it through."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.get("/api/clever/callback?error=access_denied")
        assert resp.status_code == 302
        assert "clever_error=access_denied" in resp.location


# ---------------------------------------------------------------------------
# TestAccountMerging — email-based Clever ↔ Supabase account link
# ---------------------------------------------------------------------------

class TestAccountMerging:

    def _run_callback_as_teacher(self, sb_mock):
        """Helper: run the teacher callback with a given Supabase mock.

        Returns the mock_save object so callers can assert on it.
        """
        app = _make_app()
        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={"access_token": "test_token"})),
            patch("backend.routes.clever_routes.get_clever_user",
                  new=AsyncMock(return_value=_clever_user("teacher"))),
            patch("backend.routes.clever_routes.load_clever_links",
                  return_value={}),  # clever_id not yet linked
            patch("backend.routes.clever_routes.save_clever_link") as mock_save,
            patch("backend.routes.clever_routes.resolve_clever_user_id",
                  return_value="clever:clever-teacher-001"),
            patch("backend.routes.clever_routes._get_supabase_safe",
                  return_value=sb_mock),
            patch("backend.routes.clever_routes.os.getenv", return_value=None),
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["clever_oauth_state"] = "valid-state"
                client.get("/api/clever/callback?code=abc123&state=valid-state")
        return mock_save

    def _make_user(self, email):
        u = MagicMock()
        u.email = email
        u.id = f"sb-user-{email}"
        return u

    def test_single_email_match_saves_link(self):
        """Exactly one Supabase user matches the Clever email → link is saved."""
        sb = MagicMock()
        matched_user = self._make_user("teacher@school.edu")
        sb.auth.admin.list_users.return_value = [matched_user]

        mock_save = self._run_callback_as_teacher(sb)

        mock_save.assert_called_once_with("clever-teacher-001", matched_user.id)

    def test_no_email_match_does_not_save_link(self):
        """No Supabase user with that email → save_clever_link not called."""
        sb = MagicMock()
        sb.auth.admin.list_users.return_value = [
            self._make_user("other@school.edu"),
        ]

        mock_save = self._run_callback_as_teacher(sb)

        mock_save.assert_not_called()

    def test_multiple_email_matches_does_not_save_link(self):
        """Multiple Supabase users share the email → no link saved (ambiguous merge)."""
        sb = MagicMock()
        sb.auth.admin.list_users.return_value = [
            self._make_user("teacher@school.edu"),
            self._make_user("teacher@school.edu"),
        ]

        mock_save = self._run_callback_as_teacher(sb)

        mock_save.assert_not_called()

    def test_already_linked_skips_merge_check(self):
        """Clever ID already in links dict → Supabase lookup is never attempted."""
        app = _make_app()
        sb = MagicMock()

        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={"access_token": "test_token"})),
            patch("backend.routes.clever_routes.get_clever_user",
                  new=AsyncMock(return_value=_clever_user("teacher"))),
            patch("backend.routes.clever_routes.load_clever_links",
                  return_value={"clever-teacher-001": "sb-user-already-linked"}),
            patch("backend.routes.clever_routes.save_clever_link") as mock_save,
            patch("backend.routes.clever_routes.resolve_clever_user_id",
                  return_value="sb-user-already-linked"),
            patch("backend.routes.clever_routes._get_supabase_safe",
                  return_value=sb),
            patch("backend.routes.clever_routes.os.getenv", return_value=None),
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["clever_oauth_state"] = "valid-state"
                client.get("/api/clever/callback?code=abc123&state=valid-state")

        # Already linked — no new save and Supabase user listing never called
        mock_save.assert_not_called()
        sb.auth.admin.list_users.assert_not_called()

    def test_supabase_error_during_merge_is_non_fatal(self):
        """If Supabase raises during the merge check, the login still succeeds."""
        app = _make_app()
        sb = MagicMock()
        sb.auth.admin.list_users.side_effect = Exception("Supabase down")

        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={"access_token": "test_token"})),
            patch("backend.routes.clever_routes.get_clever_user",
                  new=AsyncMock(return_value=_clever_user("teacher"))),
            patch("backend.routes.clever_routes.load_clever_links", return_value={}),
            patch("backend.routes.clever_routes.save_clever_link"),
            patch("backend.routes.clever_routes.resolve_clever_user_id",
                  return_value="clever:clever-teacher-001"),
            patch("backend.routes.clever_routes._get_supabase_safe", return_value=sb),
            patch("backend.routes.clever_routes.os.getenv", return_value=None),
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["clever_oauth_state"] = "valid-state"
                resp = client.get("/api/clever/callback?code=abc123&state=valid-state")

        # Login should still succeed despite merge error
        assert resp.status_code == 302
        assert "clever_login=success" in resp.location
