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

    def test_instant_login_no_state_restarts_auth(self):
        """Clever Instant Login arrives with NO state (neither query nor session).
        Per Clever best practices we must NOT complete auth from it (login-CSRF /
        session-fixation); instead restart with our own state. Assert the restart
        redirect AND that the code is never exchanged."""
        app = _make_app()
        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={"access_token": "test_token"})) as mock_exchange,
            patch("backend.routes.clever_routes.get_clever_user",
                  new=AsyncMock(return_value=_clever_user("teacher"))) as mock_user,
        ):
            with app.test_client() as client:
                # No session state, no query state → Instant Login no-state path.
                resp = client.get("/api/clever/callback?code=abc123")

        assert resp.status_code == 302
        assert "/api/clever/login-url" in resp.location
        assert "redirect=1" in resp.location
        # Auth must NOT be completed from the bare no-state request.
        mock_exchange.assert_not_called()
        mock_user.assert_not_called()

    def test_no_state_callback_preserves_pending_restart_state(self):
        """Codex regression guard: a no-state callback must NOT consume a pending
        restart state. Otherwise a duplicate Instant-Login hit would pop the
        state we just minted, and the real bounce-back (which carries that state)
        would then fail state_mismatch. The no-state branch must restart without
        touching session['clever_oauth_state']."""
        app = _make_app()
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["clever_oauth_state"] = "pending-restart-state"
            resp = client.get("/api/clever/callback?code=dup123")  # no state
            assert resp.status_code == 302
            assert "/api/clever/login-url" in resp.location
            with client.session_transaction() as sess:
                assert sess.get("clever_oauth_state") == "pending-restart-state", (
                    "no-state callback wrongly consumed the pending restart state"
                )

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
            patch("backend.api_keys.resolve_clever_district_token",
                  return_value="district-token-abc"),
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
            patch("backend.api_keys.resolve_clever_district_token",
                  return_value="district-token-abc"),
            patch("backend.routes.clever_routes._create_clever_student_session",
                  return_value=None),
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["clever_oauth_state"] = "valid-state"
                resp = client.get("/api/clever/callback?code=abc123&state=valid-state")

        assert resp.status_code == 302
        assert "clever_error=student_not_enrolled" in resp.location

    @pytest.mark.parametrize(
        "session_result",
        [{"status": "not_found"}, {"status": "no_enrollment"}],
    )
    def test_student_roster_miss_with_missing_district_token_surfaces_config(self, session_result):
        """Roster miss + no Secure-Sync token → config error, not roster absence.

        The token check runs AFTER the lookup: a missing token must never block
        an already-synced student from logging in (login reads Supabase only).
        """
        app = _make_app()

        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={"access_token": "test_token"})),
            patch("backend.routes.clever_routes.get_clever_user",
                  new=AsyncMock(return_value=_clever_user("student"))),
            patch("backend.api_keys.resolve_clever_district_token",
                  return_value=""),
            patch("backend.routes.clever_routes._create_clever_student_session",
                  return_value=session_result) as mock_create,
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["clever_oauth_state"] = "valid-state"
                resp = client.get("/api/clever/callback?code=abc123&state=valid-state")

        assert resp.status_code == 302
        assert "clever_error=district_token_missing" in resp.location
        mock_create.assert_called_once()

    def test_student_success_does_not_require_district_token(self):
        """An already-synced student logs in fine with NO district token configured."""
        app = _make_app()
        student_session_data = {
            "token": "session-token-xyz",
            "student": {"id": "db-stu-001", "first_name": "Jane"},
            "class": {"id": "cls-1", "name": "Math 9"},
        }

        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={"access_token": "test_token"})),
            patch("backend.routes.clever_routes.get_clever_user",
                  new=AsyncMock(return_value=_clever_user("student"))),
            patch("backend.api_keys.resolve_clever_district_token",
                  return_value=""),
            patch("backend.routes.clever_routes._create_clever_student_session",
                  return_value=student_session_data),
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["clever_oauth_state"] = "valid-state"
                resp = client.get("/api/clever/callback?code=abc123&state=valid-state")

        assert resp.status_code == 302
        assert "/student?" in resp.location
        assert "clever_error" not in resp.location

    @pytest.mark.parametrize(
        ("session_result", "expected_error"),
        [
            ({"status": "not_found"}, "student_not_found"),
            ({"status": "no_enrollment"}, "student_no_enrollment"),
        ],
    )
    def test_student_known_failure_redirects_specific_error(self, session_result, expected_error):
        app = _make_app()

        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={"access_token": "test_token"})),
            patch("backend.routes.clever_routes.get_clever_user",
                  new=AsyncMock(return_value=_clever_user("student"))),
            patch("backend.api_keys.resolve_clever_district_token",
                  return_value="district-token-abc"),
            patch("backend.routes.clever_routes._create_clever_student_session",
                  return_value=session_result),
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["clever_oauth_state"] = "valid-state"
                resp = client.get("/api/clever/callback?code=abc123&state=valid-state")

        assert resp.status_code == 302
        assert f"clever_error={expected_error}" in resp.location

    def test_teacher_role_redirects_success(self):
        """Teacher login → session populated, redirect with clever_login=success."""
        app = _make_app()

        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={"access_token": "test_token"})),
            patch("backend.routes.clever_routes.get_clever_user",
                  new=AsyncMock(return_value=_clever_user("teacher"))),
            patch("backend.routes.clever_routes.load_clever_links", return_value={}),
            patch("backend.routes.clever_routes.resolve_clever_user_id_or_create",
                  return_value=("clever:clever-teacher-001", "transient_legacy")),
            patch("backend.routes.clever_routes._get_supabase_safe", return_value=None),
            patch("backend.routes.clever_routes.os.getenv", return_value=None),
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["clever_oauth_state"] = "valid-state"
                resp = client.get("/api/clever/callback?code=abc123&state=valid-state")

        assert resp.status_code == 302
        assert "clever_login=success" in resp.location

    def test_contact_role_denied(self):
        """Clever `contact` = parent/guardian. Such accounts must NOT reach the
        teacher dashboard — it would expose student data (FERPA). Deny with
        `clever_error=role_not_permitted` and mint NO session (the resolver,
        which runs only on the accepted path, must never be called)."""
        app = _make_app()

        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={"access_token": "test_token"})),
            patch("backend.routes.clever_routes.get_clever_user",
                  new=AsyncMock(return_value=_clever_user("contact"))),
            patch("backend.routes.clever_routes.establish_sso_session") as mock_establish,
            patch("backend.routes.clever_routes.resolve_clever_user_id_or_create") as mock_resolve,
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["clever_oauth_state"] = "valid-state"
                resp = client.get("/api/clever/callback?code=abc123&state=valid-state")
                with client.session_transaction() as sess:
                    assert "clever_user" not in sess, (
                        "denied contact user still got a Clever session"
                    )

        assert resp.status_code == 302
        assert "clever_error=role_not_permitted" in resp.location
        # Denial returns BEFORE the session is established or a UUID resolved.
        mock_establish.assert_not_called()
        mock_resolve.assert_not_called()

    def test_unknown_role_denied(self):
        """Deny-by-default: an unrecognized / future non-educator role — and the
        v3.0 'user' sentinel get_clever_user returns when /users carries no
        `roles` object — is rejected, not silently treated as a teacher."""
        app = _make_app()

        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={"access_token": "test_token"})),
            patch("backend.routes.clever_routes.get_clever_user",
                  new=AsyncMock(return_value=_clever_user("user"))),
            patch("backend.routes.clever_routes.resolve_clever_user_id_or_create") as mock_resolve,
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["clever_oauth_state"] = "valid-state"
                resp = client.get("/api/clever/callback?code=abc123&state=valid-state")

        assert resp.status_code == 302
        assert "clever_error=role_not_permitted" in resp.location
        mock_resolve.assert_not_called()

    def test_staff_role_allowed(self):
        """`staff` (counselors, aides, non-teaching educators) stay valid →
        teacher dashboard. The denial allowlist must not lock them out."""
        app = _make_app()

        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={"access_token": "test_token"})),
            patch("backend.routes.clever_routes.get_clever_user",
                  new=AsyncMock(return_value=_clever_user("staff"))),
            patch("backend.routes.clever_routes.load_clever_links", return_value={}),
            patch("backend.routes.clever_routes.resolve_clever_user_id_or_create",
                  return_value=("clever:clever-teacher-001", "transient_legacy")),
            patch("backend.routes.clever_routes._get_supabase_safe", return_value=None),
            patch("backend.routes.clever_routes.os.getenv", return_value=None),
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["clever_oauth_state"] = "valid-state"
                resp = client.get("/api/clever/callback?code=abc123&state=valid-state")

        assert resp.status_code == 302
        assert "clever_login=success" in resp.location

    def test_district_admin_role_allowed(self):
        """`district_admin` is a valid admin role → teacher dashboard (and keeps
        the district-admin-gated route reachable)."""
        app = _make_app()

        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={"access_token": "test_token"})),
            patch("backend.routes.clever_routes.get_clever_user",
                  new=AsyncMock(return_value=_clever_user("district_admin"))),
            patch("backend.routes.clever_routes.load_clever_links", return_value={}),
            patch("backend.routes.clever_routes.resolve_clever_user_id_or_create",
                  return_value=("clever:clever-teacher-001", "transient_legacy")),
            patch("backend.routes.clever_routes._get_supabase_safe", return_value=None),
            patch("backend.routes.clever_routes.os.getenv", return_value=None),
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["clever_oauth_state"] = "valid-state"
                resp = client.get("/api/clever/callback?code=abc123&state=valid-state")

        assert resp.status_code == 302
        assert "clever_login=success" in resp.location

    def test_school_admin_role_allowed(self):
        """`school_admin` is in the educator allowlist (harmless legacy entry —
        Clever v3 folds school admins into `staff`, but if it ever surfaces it
        must not be denied)."""
        app = _make_app()

        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={"access_token": "test_token"})),
            patch("backend.routes.clever_routes.get_clever_user",
                  new=AsyncMock(return_value=_clever_user("school_admin"))),
            patch("backend.routes.clever_routes.load_clever_links", return_value={}),
            patch("backend.routes.clever_routes.resolve_clever_user_id_or_create",
                  return_value=("clever:clever-teacher-001", "transient_legacy")),
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
# TestCallbackUUIDResolve — callback wires resolve_clever_user_id_or_create
# ---------------------------------------------------------------------------

class TestCallbackUUIDResolve:
    """The teacher callback resolves to a Supabase UUID (link-or-create) and
    only sets session user_id + starts the roster sync on a UUID outcome."""

    def _run_callback(self, resolve_return, captured_threads):
        """Drive the teacher callback with a stubbed resolver. Captures any
        Thread starts into captured_threads so the test can assert on the
        roster-sync target/args (or its absence)."""
        app = _make_app()

        def _fake_thread(*args, **kwargs):
            t = MagicMock()
            captured_threads.append(kwargs)
            return t

        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={"access_token": "test_token"})),
            patch("backend.routes.clever_routes.get_clever_user",
                  new=AsyncMock(return_value=_clever_user("teacher"))),
            patch("backend.routes.clever_routes.resolve_clever_user_id_or_create",
                  return_value=resolve_return) as mock_resolve,
            patch("backend.routes.clever_routes._background_roster_sync"),
            patch("backend.routes.clever_routes.threading.Thread",
                  side_effect=_fake_thread),
            patch("backend.api_keys.resolve_clever_district_token",
                  return_value="district-token-abc"),
            patch("backend.routes.clever_routes._get_supabase_safe", return_value=None),
            patch("backend.routes.clever_routes.os.getenv", return_value=None),
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["clever_oauth_state"] = "valid-state"
                resp = client.get("/api/clever/callback?code=abc123&state=valid-state")
                with client.session_transaction() as sess:
                    clever_user = sess.get("clever_user", {})
        return resp, clever_user, mock_resolve

    def test_created_uuid_sets_user_id_and_starts_sync(self):
        """A 'created' UUID outcome → session user_id set + roster sync started
        with the UUID."""
        threads = []
        resp, clever_user, mock_resolve = self._run_callback(
            ("uuid-7", "created"), threads)

        assert resp.status_code == 302
        assert "clever_login=success" in resp.location
        assert clever_user.get("user_id") == "uuid-7"
        mock_resolve.assert_called_once()
        # exactly one roster-sync thread started, targeting the UUID
        assert len(threads) == 1
        assert threads[0]["args"] == ("district-token-abc", "uuid-7")

    def test_already_linked_uuid_sets_user_id_and_starts_sync(self):
        """An already-'linked' UUID outcome → same behavior (gating is on
        id-shape, not the outcome string)."""
        threads = []
        resp, clever_user, _ = self._run_callback(
            ("uuid-existing", "linked"), threads)

        assert resp.status_code == 302
        assert clever_user.get("user_id") == "uuid-existing"
        assert len(threads) == 1
        assert threads[0]["args"] == ("district-token-abc", "uuid-existing")

    def test_legacy_outcome_no_user_id_no_sync(self):
        """A legacy outcome → user_id NOT set and roster sync NOT started."""
        threads = []
        resp, clever_user, _ = self._run_callback(
            ("clever:clever-teacher-001", "ambiguous_legacy"), threads)

        assert resp.status_code == 302
        assert "clever_login=success" in resp.location
        assert "user_id" not in clever_user
        assert threads == []


# ---------------------------------------------------------------------------
# TestAccountMerging — email-based Clever ↔ Supabase account link
# ---------------------------------------------------------------------------

class TestAccountMerging:
    """The callback delegates email→UUID link-or-create to
    resolve_clever_user_id_or_create (the merge SEMANTICS — single-match link,
    multi-match ambiguity, already-linked, error fail-open — are owned and
    tested by that resolver in tests/test_clever_identity.py). These tests pin
    only the callback-layer contract: it calls the resolver with the Clever
    email + name, and the login always succeeds (fail-open)."""

    def _run_callback_as_teacher(self, resolve_return):
        """Run the teacher callback with a stubbed resolver. Returns the
        resolver mock so callers can assert on its call args."""
        app = _make_app()
        with (
            patch("backend.routes.clever_routes.exchange_code_for_token",
                  new=AsyncMock(return_value={"access_token": "test_token"})),
            patch("backend.routes.clever_routes.get_clever_user",
                  new=AsyncMock(return_value=_clever_user("teacher"))),
            patch("backend.routes.clever_routes.resolve_clever_user_id_or_create",
                  return_value=resolve_return) as mock_resolve,
            patch("backend.routes.clever_routes._get_supabase_safe", return_value=None),
            patch("backend.routes.clever_routes.os.getenv", return_value=None),
        ):
            with app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["clever_oauth_state"] = "valid-state"
                resp = client.get("/api/clever/callback?code=abc123&state=valid-state")
        return resp, mock_resolve

    def test_callback_delegates_email_and_name_to_resolver(self):
        """The callback passes the Clever id, email, and name to the resolver."""
        resp, mock_resolve = self._run_callback_as_teacher(("uuid-1", "matched"))

        assert resp.status_code == 302
        assert "clever_login=success" in resp.location
        mock_resolve.assert_called_once_with(
            "clever-teacher-001",
            "teacher@school.edu",
            {"first": "Ada", "last": "Lovelace"},
        )

    def test_ambiguous_outcome_login_still_succeeds(self):
        """A >1-match (ambiguous_legacy) outcome still lands a successful login
        (fail-open) — the resolver returns a legacy id, callback does not block."""
        resp, _ = self._run_callback_as_teacher(
            ("clever:clever-teacher-001", "ambiguous_legacy"))

        assert resp.status_code == 302
        assert "clever_login=success" in resp.location

    def test_transient_resolver_failure_login_still_succeeds(self):
        """A transient resolver failure (legacy fallback) is non-fatal — the
        login still succeeds."""
        resp, _ = self._run_callback_as_teacher(
            ("clever:clever-teacher-001", "transient_legacy"))

        assert resp.status_code == 302
        assert "clever_login=success" in resp.location


# ---------------------------------------------------------------------------
# TestCleverSessionCheck — /api/clever/session returns resolved user_id
# ---------------------------------------------------------------------------

class TestCleverSessionCheck:
    """GET /api/clever/session surfaces the session-stored resolved UUID as
    `user_id` so the frontend stores the real identity (Task 6)."""

    def test_session_returns_stored_user_id(self):
        """When the session already holds a resolved UUID, the response echoes
        it as user_id and account_linked is True (not a clever: legacy id)."""
        app = _make_app()
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["clever_user"] = {
                    "clever_id": "c1",
                    "user_id": "uuid-1",
                    "type": "teacher",
                    "email": "t@school.edu",
                    "name": {"first": "Ada", "last": "Lovelace"},
                    "district": "district-xyz",
                }
            resp = client.get("/api/clever/session")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get("user_id") == "uuid-1"
        assert body.get("account_linked") is True
