"""Tests for ClassLink OAuth2/OIDC SSO flow."""

import os
import json
import time
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from flask import Flask, session

# RSA keypair + id_token factory (shared with Task 3 tests via conftest_classlink)
from tests.conftest_classlink import make_id_token


def _make_app():
    """Create a minimal Flask app with ClassLink routes."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret'
    app.config['RATELIMIT_ENABLED'] = False

    os.environ['CLASSLINK_CLIENT_ID'] = 'test-client-id'
    os.environ['CLASSLINK_CLIENT_SECRET'] = 'test-client-secret'

    from backend.extensions import limiter
    limiter.init_app(app)

    from backend.routes.classlink_routes import classlink_bp
    app.register_blueprint(classlink_bp)
    return app


def _make_rsa_keypair():
    """Generate a fresh RSA-2048 keypair for test use."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return priv, priv.public_key()


def _mock_jwks_client(public_key):
    """Return a MagicMock JWKSClient whose get_signing_key_from_jwt returns the given key."""
    mock_jwks = MagicMock()
    mock_jwks.get_signing_key_from_jwt.return_value = MagicMock(key=public_key)
    return mock_jwks


def _mock_oidc_config():
    """Return a minimal ClassLink OIDC config dict."""
    return {
        "issuer": "https://launchpad.classlink.com",
        "jwks_uri": "https://launchpad.classlink.com/oauth2/v2/keys",
    }


def _run_callback(client, priv, pub, userinfo, sub="cl-sub", nonce=None):
    """Drive a LaunchPad-permissive callback (no initiated_by_us marker) with a
    given userinfo body. Returns the Flask response."""
    id_token = make_id_token(
        priv, aud="test-client-id", sub=sub, nonce=nonce,
        email=userinfo.get("Email", ""), given_name=userinfo.get("FirstName", ""),
        family_name=userinfo.get("LastName", ""), role=userinfo.get("Role", "teacher"),
    )
    mock_token_resp = MagicMock(); mock_token_resp.status_code = 200
    mock_token_resp.json.return_value = {"access_token": "tok", "id_token": id_token}
    mock_user_resp = MagicMock(); mock_user_resp.status_code = 200
    mock_user_resp.json.return_value = userinfo
    with client.session_transaction() as sess:
        sess['classlink_oauth_state'] = 'valid-state'
    with patch('backend.routes.classlink_routes.requests.post', return_value=mock_token_resp), \
         patch('backend.routes.classlink_routes.requests.get', return_value=mock_user_resp), \
         patch('backend.routes.classlink_routes.get_classlink_oidc_config', return_value=_mock_oidc_config()), \
         patch('backend.routes.classlink_routes.get_classlink_jwks_client', return_value=_mock_jwks_client(pub)), \
         patch('backend.routes.classlink_routes._trigger_roster_sync'):
        return client.get('/api/classlink/callback?code=c&state=valid-state')


class TestClassLinkTenantScopedIdentity:
    BASE = {"FirstName": "A", "LastName": "B", "Email": "a@school.edu", "Role": "teacher"}

    def test_teacher_guid_is_tenant_scoped(self):
        app = _make_app(); priv, pub = _make_rsa_keypair()
        with app.test_client() as client:
            resp = _run_callback(client, priv, pub,
                                 {**self.BASE, "SourcedId": "p1", "TenantId": "dist-A"})
            assert 'classlink_login=success' in resp.location
            with client.session_transaction() as sess:
                assert sess['classlink_user']['user_id'] == "classlink:dist-A:p1"

    def test_same_person_different_tenants_distinct_guids(self):
        app = _make_app(); priv, pub = _make_rsa_keypair()
        with app.test_client() as c1:
            _run_callback(c1, priv, pub, {**self.BASE, "SourcedId": "same", "TenantId": "dist-A"})
            with c1.session_transaction() as s1:
                guid_a = s1['classlink_user']['user_id']
        with app.test_client() as c2:
            _run_callback(c2, priv, pub, {**self.BASE, "SourcedId": "same", "TenantId": "dist-B"})
            with c2.session_transaction() as s2:
                guid_b = s2['classlink_user']['user_id']
        assert guid_a == "classlink:dist-A:same"
        assert guid_b == "classlink:dist-B:same"
        assert guid_a != guid_b

    def test_missing_tenant_rejected_fail_closed(self):
        app = _make_app(); priv, pub = _make_rsa_keypair()
        with app.test_client() as client:
            resp = _run_callback(client, priv, pub, {**self.BASE, "SourcedId": "p1"})  # no TenantId
            assert 'classlink_error=missing_tenant' in resp.location
            with client.session_transaction() as sess:
                assert 'classlink_user' not in sess

    def test_missing_person_id_rejected_fail_closed(self):
        app = _make_app(); priv, pub = _make_rsa_keypair()
        with app.test_client() as client:
            resp = _run_callback(client, priv, pub, {**self.BASE, "TenantId": "dist-A"})  # no SourcedId/UserId
            assert 'classlink_error=missing_identity' in resp.location

    def test_userinfo_sub_mismatch_rejected(self):
        app = _make_app(); priv, pub = _make_rsa_keypair()
        with app.test_client() as client:
            # id_token sub = "cl-sub"; userinfo carries a conflicting sub
            resp = _run_callback(client, priv, pub,
                                 {**self.BASE, "SourcedId": "p1", "TenantId": "dist-A", "sub": "OTHER"})
            assert 'classlink_error=identity_mismatch' in resp.location

    def test_role_as_list_resolves_student(self):
        app = _make_app(); priv, pub = _make_rsa_keypair()
        with app.test_client() as client:
            resp = _run_callback(client, priv, pub,
                                 {**self.BASE, "Role": ["student"], "SourcedId": "p1", "TenantId": "dist-A"})
            assert '/student?classlink_login=success' in resp.location

    def test_student_path_gets_tenant_scoped_guid(self):
        app = _make_app(); priv, pub = _make_rsa_keypair()
        with app.test_client() as client:
            _run_callback(client, priv, pub,
                          {**self.BASE, "Role": "student", "SourcedId": "stu1", "TenantId": "dist-A"})
            with client.session_transaction() as sess:
                assert sess['classlink_student']['user_id'] == "classlink:dist-A:stu1"


class TestClassLinkLoginURL:
    def test_returns_authorization_url(self):
        """Should return ClassLink OAuth authorization URL with state."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.get('/api/classlink/login-url')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'url' in data
        assert 'launchpad.classlink.com/oauth2/v2/auth' in data['url']
        assert 'client_id=test-client-id' in data['url']
        assert 'state=' in data['url']

    def test_returns_error_when_not_configured(self):
        """Should return error when CLASSLINK_CLIENT_ID is not set."""
        app = _make_app()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('CLASSLINK_CLIENT_ID', None)
            with app.test_client() as client:
                resp = client.get('/api/classlink/login-url')
        data = resp.get_json()
        assert 'error' in data or resp.status_code != 200


class TestClassLinkCallback:
    def test_rejects_missing_code(self):
        """Should redirect with error when no code parameter."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.get('/api/classlink/callback')
        assert resp.status_code == 302
        assert 'classlink_error' in resp.location

    def test_rejects_oauth_error(self):
        """Should redirect with error when OAuth returns error param."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.get('/api/classlink/callback?error=access_denied')
        assert resp.status_code == 302
        assert 'classlink_error=access_denied' in resp.location

    def test_successful_teacher_login(self):
        """Should create session and redirect on successful teacher login."""
        app = _make_app()
        priv, pub = _make_rsa_keypair()
        id_token = make_id_token(
            priv,
            aud="test-client-id",
            sub="cl-user-123",
            email="jane.smith@school.edu",
            given_name="Jane",
            family_name="Smith",
            role="teacher",
        )

        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "test-token", "id_token": id_token}

        mock_user_resp = MagicMock()
        mock_user_resp.status_code = 200
        mock_user_resp.json.return_value = {
            "UserId": "cl-user-123",
            "SourcedId": "cl-user-123",
            "FirstName": "Jane",
            "LastName": "Smith",
            "Email": "jane.smith@school.edu",
            "Role": "teacher",
            "TenantId": "district-456",
        }

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['classlink_oauth_state'] = 'valid-state'

            with patch('backend.routes.classlink_routes.requests.post', return_value=mock_token_resp), \
                 patch('backend.routes.classlink_routes.requests.get', return_value=mock_user_resp), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=_mock_jwks_client(pub)), \
                 patch('backend.routes.classlink_routes._trigger_roster_sync'):
                resp = client.get('/api/classlink/callback?code=auth-code-123&state=valid-state')

            assert resp.status_code == 302
            assert 'classlink_login=success' in resp.location

            with client.session_transaction() as sess:
                assert 'classlink_user' in sess
                assert sess['classlink_user']['email'] == 'jane.smith@school.edu'
                assert sess['classlink_user']['classlink_id'] == 'cl-user-123'

    def test_student_login_redirects_to_student_portal(self):
        """Should redirect students to /student path."""
        app = _make_app()
        priv, pub = _make_rsa_keypair()
        id_token = make_id_token(
            priv,
            aud="test-client-id",
            sub="cl-student-789",
            email="bob.jones@school.edu",
            given_name="Bob",
            family_name="Jones",
            role="student",
        )

        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "test-token", "id_token": id_token}

        mock_user_resp = MagicMock()
        mock_user_resp.status_code = 200
        mock_user_resp.json.return_value = {
            "UserId": "cl-student-789",
            "FirstName": "Bob",
            "LastName": "Jones",
            "Email": "bob.jones@school.edu",
            "Role": "student",
            "TenantId": "district-456",
        }

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['classlink_oauth_state'] = 'valid-state'

            with patch('backend.routes.classlink_routes.requests.post', return_value=mock_token_resp), \
                 patch('backend.routes.classlink_routes.requests.get', return_value=mock_user_resp), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=_mock_jwks_client(pub)):
                resp = client.get('/api/classlink/callback?code=auth-code-123&state=valid-state')

            assert resp.status_code == 302
            assert '/student' in resp.location

    def test_classlink_initiated_flow_no_state(self):
        """ClassLink-initiated flows (LaunchPad tile) may not have state — should still work."""
        app = _make_app()
        priv, pub = _make_rsa_keypair()
        id_token = make_id_token(
            priv,
            aud="test-client-id",
            sub="cl-user-123",
            email="jane@school.edu",
            given_name="Jane",
            family_name="Smith",
            role="teacher",
        )

        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "test-token", "id_token": id_token}

        mock_user_resp = MagicMock()
        mock_user_resp.status_code = 200
        mock_user_resp.json.return_value = {
            "UserId": "cl-user-123",
            "FirstName": "Jane",
            "LastName": "Smith",
            "Email": "jane@school.edu",
            "Role": "teacher",
            "TenantId": "district-456",
        }

        with app.test_client() as client:
            # No state in session (ClassLink-initiated, login-url never called)
            with patch('backend.routes.classlink_routes.requests.post', return_value=mock_token_resp), \
                 patch('backend.routes.classlink_routes.requests.get', return_value=mock_user_resp), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=_mock_jwks_client(pub)), \
                 patch('backend.routes.classlink_routes._trigger_roster_sync'):
                resp = client.get('/api/classlink/callback?code=auth-code-123')

            assert resp.status_code == 302
            assert 'classlink_login=success' in resp.location

    def test_token_exchange_failure(self):
        """Should redirect with error when token exchange fails."""
        app = _make_app()

        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 400
        mock_token_resp.json.return_value = {"error": "invalid_grant"}
        mock_token_resp.text = "invalid_grant"

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['classlink_oauth_state'] = 'valid-state'

            with patch('backend.routes.classlink_routes.requests.post', return_value=mock_token_resp):
                resp = client.get('/api/classlink/callback?code=bad-code&state=valid-state')

            assert resp.status_code == 302
            assert 'classlink_error' in resp.location


class TestClassLinkSession:
    def test_session_check_returns_status(self):
        """Should return session status."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.get('/api/classlink/session')
        data = resp.get_json()
        assert data['authenticated'] is False

    def test_session_check_when_logged_in(self):
        """Should return user info when session exists."""
        app = _make_app()
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['classlink_user'] = {
                    'classlink_id': 'cl-123',
                    'email': 'jane@school.edu',
                    'name': {'first': 'Jane', 'last': 'Smith'},
                    'type': 'teacher',
                    'tenant_id': 'district-456',
                }
            resp = client.get('/api/classlink/session')
        data = resp.get_json()
        assert data['authenticated'] is True
        assert data['email'] == 'jane@school.edu'


class TestClassLinkLogout:
    def test_logout_clears_session(self):
        """Should clear ClassLink session data."""
        app = _make_app()
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['classlink_user'] = {'classlink_id': 'cl-123'}
            resp = client.post('/api/classlink/logout')
        assert resp.status_code == 200
        with client.session_transaction() as sess:
            assert 'classlink_user' not in sess


class TestClassLinkIdTokenValidation:
    """Task 2: id_token consumption + validation in the ClassLink callback.

    All tests here verify the new OIDC id_token enforcement added by PR 1 of
    the SIS compliance hardening sprint.  The conftest_classlink helpers supply
    signed tokens; JWKS + OIDC config lookups are fully mocked so no network
    calls are made.
    """

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _make_token_response(id_token):
        """Return a mock requests.Response for the token endpoint."""
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = {"access_token": "test-access-token", "id_token": id_token}
        m.text = "{}"
        return m

    @staticmethod
    def _make_userinfo_response(role="teacher"):
        """Return a mock requests.Response for the userinfo endpoint."""
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = {
            "UserId": "cl-user-123",
            "FirstName": "Jane",
            "LastName": "Smith",
            "Email": "jane@school.edu",
            "Role": role,
            "TenantId": "t-district-456",
        }
        return m

    # ── test 1: missing id_token → fail closed ────────────────────────────────

    def test_callback_rejects_missing_id_token(self):
        """Token endpoint returns no id_token → redirect with classlink_error=no_id_token."""
        app = _make_app()

        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "test-access-token"}  # no id_token
        mock_token_resp.text = "{}"

        with app.test_client() as client:
            with patch('backend.routes.classlink_routes.requests.post',
                       return_value=mock_token_resp):
                resp = client.get('/api/classlink/callback?code=abc&state=xyz')

        assert resp.status_code == 302
        assert "classlink_error=no_id_token" in resp.headers["Location"]

    # ── test 2: invalid signature → oidc_invalid ──────────────────────────────

    def test_callback_rejects_invalid_id_token_signature(self):
        """id_token with a bogus signature → redirect with classlink_error=oidc_invalid."""
        app = _make_app()

        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {
            "access_token": "test-access-token",
            "id_token": "header.bogus_payload.bogus_signature",
        }
        mock_token_resp.text = "{}"

        # JWKS client raises when asked to resolve the signing key for the malformed token
        mock_jwks = MagicMock()
        import jwt as pyjwt
        mock_jwks.get_signing_key_from_jwt.side_effect = pyjwt.exceptions.PyJWKClientError(
            "Unable to find a signing key"
        )

        with app.test_client() as client:
            with patch('backend.routes.classlink_routes.requests.post',
                       return_value=mock_token_resp), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=mock_jwks):
                resp = client.get('/api/classlink/callback?code=abc&state=xyz')

        assert resp.status_code == 302
        assert "classlink_error=oidc_invalid" in resp.headers["Location"]

    # ── test 3: valid id_token → identity from claims ─────────────────────────

    def test_callback_uses_id_token_claims_for_identity(self):
        """Valid id_token → identity extracted from claims; redirect with classlink_login=success."""
        app = _make_app()
        priv, pub = _make_rsa_keypair()
        id_token = make_id_token(
            priv,
            aud="test-client-id",
            sub="cl-user-999",
            email="fromclaims@school.edu",
            given_name="ClaimsFirst",
            family_name="ClaimsLast",
            role="teacher",
        )

        # userinfo returns DIFFERENT values — session should use id_token claims
        mock_user_resp = MagicMock()
        mock_user_resp.status_code = 200
        mock_user_resp.json.return_value = {
            "UserId": "cl-user-999",
            "FirstName": "UserInfoFirst",
            "LastName": "UserInfoLast",
            "Email": "fromuserinfo@school.edu",
            "Role": "teacher",
            "TenantId": "t-district-999",
        }

        with app.test_client() as client:
            with patch('backend.routes.classlink_routes.requests.post',
                       return_value=self._make_token_response(id_token)), \
                 patch('backend.routes.classlink_routes.requests.get',
                       return_value=mock_user_resp), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=_mock_jwks_client(pub)), \
                 patch('backend.routes.classlink_routes._trigger_roster_sync'):
                resp = client.get('/api/classlink/callback?code=abc')

        assert resp.status_code == 302
        assert "classlink_login=success" in resp.headers["Location"]
        # The deeper "id_claims actually populate the session" assertion lives in
        # test_callback_uses_id_token_claims_session_contents below. This test
        # establishes that valid id_token + divergent userinfo → success redirect
        # (i.e., the validation block does not bail when fields disagree).

    def test_callback_uses_id_token_claims_session_contents(self):
        """id_token claims populate the session; sub maps to classlink_id."""
        app = _make_app()
        priv, pub = _make_rsa_keypair()
        id_token = make_id_token(
            priv,
            aud="test-client-id",
            sub="cl-user-claims-789",
            email="claims@school.edu",
            given_name="Jane",
            family_name="Smith",
            role="teacher",
        )

        mock_user_resp = MagicMock()
        mock_user_resp.status_code = 200
        mock_user_resp.json.return_value = {
            "UserId": "cl-user-claims-789",
            "FirstName": "Jane",
            "LastName": "Smith",
            "Email": "claims@school.edu",
            "Role": "teacher",
            "TenantId": "t-123",
        }

        with app.test_client() as client:
            with patch('backend.routes.classlink_routes.requests.post',
                       return_value=self._make_token_response(id_token)), \
                 patch('backend.routes.classlink_routes.requests.get',
                       return_value=mock_user_resp), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=_mock_jwks_client(pub)), \
                 patch('backend.routes.classlink_routes._trigger_roster_sync'):
                resp = client.get('/api/classlink/callback?code=abc&state=xyz')

            assert resp.status_code == 302
            assert "classlink_login=success" in resp.headers["Location"]

            with client.session_transaction() as sess:
                assert 'classlink_user' in sess
                # sub claim maps to classlink_id
                assert sess['classlink_user']['classlink_id'] == 'cl-user-claims-789'
                # email comes from id_token claim
                assert sess['classlink_user']['email'] == 'claims@school.edu'

    # ── test 4: expired id_token → oidc_expired ───────────────────────────────

    def test_callback_rejects_expired_id_token(self):
        """id_token with exp in the past → redirect with classlink_error=oidc_expired."""
        app = _make_app()
        priv, pub = _make_rsa_keypair()
        # exp_offset=-3601 puts exp well in the past (leeway=10 won't save it)
        id_token = make_id_token(priv, aud="test-client-id", exp_offset=-3601)

        with app.test_client() as client:
            with patch('backend.routes.classlink_routes.requests.post',
                       return_value=self._make_token_response(id_token)), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=_mock_jwks_client(pub)):
                resp = client.get('/api/classlink/callback?code=abc&state=xyz')

        assert resp.status_code == 302
        assert "classlink_error=oidc_expired" in resp.headers["Location"]

    # ── test 5: audience mismatch → oidc_claim_mismatch ──────────────────────

    def test_callback_rejects_audience_mismatch(self):
        """id_token aud does not match CLASSLINK_CLIENT_ID → classlink_error=oidc_claim_mismatch."""
        app = _make_app()
        priv, pub = _make_rsa_keypair()
        # Sign for a different audience
        id_token = make_id_token(priv, aud="some-other-client")

        with app.test_client() as client:
            with patch('backend.routes.classlink_routes.requests.post',
                       return_value=self._make_token_response(id_token)), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=_mock_jwks_client(pub)):
                resp = client.get('/api/classlink/callback?code=abc&state=xyz')

        assert resp.status_code == 302
        assert "classlink_error=oidc_claim_mismatch" in resp.headers["Location"]

    # ── test 6: issuer mismatch → oidc_claim_mismatch ────────────────────────

    def test_callback_rejects_issuer_mismatch(self):
        """id_token with wrong issuer claim is rejected."""
        app = _make_app()
        priv, pub = _make_rsa_keypair()
        id_token = make_id_token(
            priv,
            iss="https://attacker.example.com",  # wrong issuer
            aud="test-client-id",
        )
        with app.test_client() as client:
            with patch('backend.routes.classlink_routes.requests.post',
                       return_value=self._make_token_response(id_token)), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=_mock_jwks_client(pub)):
                resp = client.get('/api/classlink/callback?code=abc')
        assert resp.status_code == 302
        assert "classlink_error=oidc_claim_mismatch" in resp.headers["Location"]

    # ── test 7: alg=none unsigned token → oidc_invalid ───────────────────────

    def test_callback_rejects_alg_none_token(self):
        """Unsigned token with alg=none is rejected (algorithms pinned to RS256)."""
        import jwt as pyjwt
        # Build an unsigned token (alg=none) with otherwise-valid claims
        claims = {
            "iss": "https://launchpad.classlink.com",
            "aud": "test-client-id",
            "sub": "evil-user",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "nbf": int(time.time()),
        }
        unsigned_token = pyjwt.encode(claims, key="", algorithm="none")

        app = _make_app()
        _, pub = _make_rsa_keypair()
        with app.test_client() as client:
            with patch('backend.routes.classlink_routes.requests.post',
                       return_value=self._make_token_response(unsigned_token)), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=_mock_jwks_client(pub)):
                resp = client.get('/api/classlink/callback?code=abc')
        assert resp.status_code == 302
        assert "classlink_error=oidc_invalid" in resp.headers["Location"]

    # ── test 8: missing kid in token header → oidc_invalid ───────────────────

    def test_callback_rejects_token_missing_kid(self):
        """id_token without kid in header → JWKS lookup fails → oidc_invalid."""
        import jwt as pyjwt
        priv, pub = _make_rsa_keypair()
        claims = {
            "iss": "https://launchpad.classlink.com",
            "aud": "test-client-id",
            "sub": "user-no-kid",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "nbf": int(time.time()),
        }
        # Encode WITHOUT kid in the header — PyJWKClient.get_signing_key_from_jwt
        # will fail to resolve a key.
        no_kid_token = pyjwt.encode(claims, priv, algorithm="RS256")

        app = _make_app()
        # Mock JWKS client to raise on missing-kid lookup
        from jwt.exceptions import PyJWKClientError
        mock_jwks = MagicMock()
        mock_jwks.get_signing_key_from_jwt.side_effect = PyJWKClientError("no kid in JWT")

        with app.test_client() as client:
            with patch('backend.routes.classlink_routes.requests.post',
                       return_value=self._make_token_response(no_kid_token)), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=mock_jwks):
                resp = client.get('/api/classlink/callback?code=abc')
        assert resp.status_code == 302
        assert "classlink_error=oidc_invalid" in resp.headers["Location"]


class TestClassLinkStateNonceHardening:
    """Task 3: state + nonce hardening for self-initiated ClassLink OAuth flows.

    Self-initiated flows (login-url → callback) require strict state match AND
    nonce match in the id_token.  LaunchPad-initiated flows (no initiated_by_us
    marker) remain permissive — id_token signature is the auth proof.
    """

    def test_self_initiated_flow_requires_state(self):
        """If we initiated, state MUST match. Missing state → reject."""
        app = _make_app()
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["classlink_oauth_state"] = "expected-state"
                sess["classlink_oauth_initiated_by_us"] = True
                sess["classlink_oauth_nonce"] = "expected-nonce"
            resp = client.get("/api/classlink/callback?code=abc")  # no state param
        assert resp.status_code == 302
        assert "classlink_error=state_mismatch" in resp.location

    def test_self_initiated_flow_rejects_state_mismatch(self):
        """If we initiated, wrong state → reject."""
        app = _make_app()
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["classlink_oauth_state"] = "expected-state"
                sess["classlink_oauth_initiated_by_us"] = True
                sess["classlink_oauth_nonce"] = "expected-nonce"
            resp = client.get("/api/classlink/callback?code=abc&state=wrong-state")
        assert resp.status_code == 302
        assert "classlink_error=state_mismatch" in resp.location

    def test_launchpad_initiated_flow_accepts_no_state(self):
        """LaunchPad path: no initiated_by_us marker, no state expected → success."""
        app = _make_app()
        priv, pub = _make_rsa_keypair()
        id_token = make_id_token(priv, aud="test-client-id")
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "t", "id_token": id_token}
        mock_user_resp = MagicMock()
        mock_user_resp.status_code = 200
        mock_user_resp.json.return_value = {
            "UserId": "cl-1", "Email": "e@x.com", "Role": "teacher", "TenantId": "t1"
        }
        with app.test_client() as client:
            # No classlink_oauth_initiated_by_us in session (LaunchPad-initiated)
            with patch('backend.routes.classlink_routes.requests.post', return_value=mock_token_resp), \
                 patch('backend.routes.classlink_routes.requests.get', return_value=mock_user_resp), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=_mock_jwks_client(pub)), \
                 patch('backend.routes.classlink_routes._trigger_roster_sync'):
                resp = client.get("/api/classlink/callback?code=abc")
        assert resp.status_code == 302
        assert "classlink_login=success" in resp.location

    def test_self_initiated_nonce_mismatch_rejected(self):
        """When we initiated, id_token's nonce must match session-stored nonce."""
        app = _make_app()
        priv, pub = _make_rsa_keypair()
        # id_token has WRONG nonce
        id_token = make_id_token(priv, aud="test-client-id", nonce="wrong-nonce")
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "t", "id_token": id_token}
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["classlink_oauth_state"] = "expected-state"
                sess["classlink_oauth_initiated_by_us"] = True
                sess["classlink_oauth_nonce"] = "expected-nonce"
            with patch('backend.routes.classlink_routes.requests.post', return_value=mock_token_resp), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=_mock_jwks_client(pub)):
                resp = client.get("/api/classlink/callback?code=abc&state=expected-state")
        assert resp.status_code == 302
        assert "classlink_error=nonce_mismatch" in resp.location

    def test_self_initiated_nonce_match_accepted(self):
        """When we initiated, matching nonce → success."""
        app = _make_app()
        priv, pub = _make_rsa_keypair()
        id_token = make_id_token(priv, aud="test-client-id", nonce="expected-nonce")
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "t", "id_token": id_token}
        mock_user_resp = MagicMock()
        mock_user_resp.status_code = 200
        mock_user_resp.json.return_value = {
            "UserId": "u1", "Email": "u@x.com", "Role": "teacher", "TenantId": "t1"
        }
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["classlink_oauth_state"] = "expected-state"
                sess["classlink_oauth_initiated_by_us"] = True
                sess["classlink_oauth_nonce"] = "expected-nonce"
            with patch('backend.routes.classlink_routes.requests.post', return_value=mock_token_resp), \
                 patch('backend.routes.classlink_routes.requests.get', return_value=mock_user_resp), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=_mock_jwks_client(pub)), \
                 patch('backend.routes.classlink_routes._trigger_roster_sync'):
                resp = client.get("/api/classlink/callback?code=abc&state=expected-state")
        assert resp.status_code == 302
        assert "classlink_login=success" in resp.location

    def test_self_initiated_id_token_missing_nonce_rejected(self):
        """Self-initiated flow + id_token has NO nonce claim at all → reject."""
        app = _make_app()
        priv, pub = _make_rsa_keypair()
        # nonce=None → claim omitted from token entirely
        id_token = make_id_token(priv, aud="test-client-id", nonce=None)
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "t", "id_token": id_token}
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["classlink_oauth_state"] = "expected-state"
                sess["classlink_oauth_initiated_by_us"] = True
                sess["classlink_oauth_nonce"] = "expected-nonce"
            with patch('backend.routes.classlink_routes.requests.post', return_value=mock_token_resp), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=_mock_jwks_client(pub)):
                resp = client.get("/api/classlink/callback?code=abc&state=expected-state")
        assert "classlink_error=nonce_mismatch" in resp.location

    def test_login_url_includes_nonce_param(self):
        """/api/classlink/login-url generates a nonce and includes it in the URL."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.get("/api/classlink/login-url")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "nonce=" in data["url"]

    def test_launchpad_initiated_with_unexpected_state_audit_logs(self):
        """If session somehow has expected_state but no initiated_by_us marker
        (session pollution / attacker probe), and the callback supplies a
        different state, the warning is audit-logged but the flow proceeds
        (LaunchPad permissive)."""
        app = _make_app()
        priv, pub = _make_rsa_keypair()
        id_token = make_id_token(priv, aud="test-client-id")
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "t", "id_token": id_token}
        mock_user_resp = MagicMock()
        mock_user_resp.status_code = 200
        mock_user_resp.json.return_value = {
            "UserId": "u1", "Email": "u@x.com", "Role": "teacher", "TenantId": "t1"
        }
        audit_calls = []
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["classlink_oauth_state"] = "stale-state"
                # NO classlink_oauth_initiated_by_us marker → LaunchPad path
            with patch('backend.routes.classlink_routes.audit_log',
                       side_effect=lambda *args, **kwargs: audit_calls.append((args, kwargs))), \
                 patch('backend.routes.classlink_routes.requests.post', return_value=mock_token_resp), \
                 patch('backend.routes.classlink_routes.requests.get', return_value=mock_user_resp), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=_mock_jwks_client(pub)), \
                 patch('backend.routes.classlink_routes._trigger_roster_sync'):
                resp = client.get("/api/classlink/callback?code=abc&state=different-state")
        # Flow proceeds (LaunchPad permissive)
        assert "classlink_login=success" in resp.location
        # But the warning was audit-logged
        event_types = [c[0][0] for c in audit_calls]
        assert "CLASSLINK_OAUTH_LAUNCHPAD_STATE_MISMATCH" in event_types

    # ─── Round-2 regressions (Codex high-effort gate review, 2026-05-05) ────
    # Findings:
    #   1. CRITICAL — atomic pop downgraded subsequent callbacks to LaunchPad
    #      after a strict-mode rejection. Fix: peek (don't pop); clear only on
    #      success.
    #   2. MINOR — error/no_code paths returned before any cleanup. With the
    #      new design, markers SHOULD persist across error paths so a retry
    #      benefits from strict-mode validation. Test pins the contract.
    #   3. MINOR — state mismatch logging emitted raw state values. Fix:
    #      presence booleans only.
    # Each finding has a regression below.

    def test_self_initiated_rejection_does_not_downgrade_subsequent_callback(self):
        """Finding #1 (CRITICAL): a callback with mismatched state must not
        clear markers, so a subsequent callback in the same session cannot
        fall through to the permissive LaunchPad path. Reproduces the original
        CSRF-bypass vector Codex repro'd against the PR snapshot."""
        app = _make_app()
        priv, pub = _make_rsa_keypair()
        # Attacker would supply a validly-signed id_token from any source.
        id_token = make_id_token(priv, aud="test-client-id")
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "t", "id_token": id_token}
        mock_user_resp = MagicMock()
        mock_user_resp.status_code = 200
        mock_user_resp.json.return_value = {
            "UserId": "u1", "Email": "u@x.com", "Role": "teacher", "TenantId": "t1"
        }
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["classlink_oauth_state"] = "expected-state"
                sess["classlink_oauth_initiated_by_us"] = True
                sess["classlink_oauth_nonce"] = "expected-nonce"

            # Step 1: callback with wrong state → strict-mode rejection.
            first = client.get("/api/classlink/callback?code=abc&state=wrong-state")
            assert "classlink_error=state_mismatch" in first.location

            # Markers MUST still be in session — single-use enforced on
            # success only, never on rejection.
            with client.session_transaction() as sess:
                assert sess.get("classlink_oauth_state") == "expected-state"
                assert sess.get("classlink_oauth_initiated_by_us") is True
                assert sess.get("classlink_oauth_nonce") == "expected-nonce"

            # Step 2: attacker sends callback with no state → must reject in
            # strict mode (not succeed via LaunchPad-permissive downgrade).
            with patch('backend.routes.classlink_routes.requests.post', return_value=mock_token_resp), \
                 patch('backend.routes.classlink_routes.requests.get', return_value=mock_user_resp), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=_mock_jwks_client(pub)), \
                 patch('backend.routes.classlink_routes._trigger_roster_sync'):
                second = client.get("/api/classlink/callback?code=real-code")
        assert "classlink_error=state_mismatch" in second.location
        assert "classlink_login=success" not in second.location

    def test_error_path_preserves_markers_for_retry_in_strict_mode(self):
        """Finding #2: error/no_code paths must NOT clear markers — the user
        can retry the flow and still benefit from strict-mode validation. With
        the new design, markers persist across all non-success exits."""
        app = _make_app()
        priv, pub = _make_rsa_keypair()
        id_token = make_id_token(priv, aud="test-client-id", nonce="expected-nonce")
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "t", "id_token": id_token}
        mock_user_resp = MagicMock()
        mock_user_resp.status_code = 200
        mock_user_resp.json.return_value = {
            "UserId": "u1", "Email": "u@x.com", "Role": "teacher", "TenantId": "t1"
        }
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["classlink_oauth_state"] = "expected-state"
                sess["classlink_oauth_initiated_by_us"] = True
                sess["classlink_oauth_nonce"] = "expected-nonce"

            # User cancels at IdP → callback receives error → redirect.
            err = client.get("/api/classlink/callback?error=access_denied")
            assert "classlink_error=access_denied" in err.location

            # Markers persist for the retry.
            with client.session_transaction() as sess:
                assert sess.get("classlink_oauth_state") == "expected-state"
                assert sess.get("classlink_oauth_initiated_by_us") is True
                assert sess.get("classlink_oauth_nonce") == "expected-nonce"

            # Retry with correct state + nonce → strict-mode validation works.
            with patch('backend.routes.classlink_routes.requests.post', return_value=mock_token_resp), \
                 patch('backend.routes.classlink_routes.requests.get', return_value=mock_user_resp), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=_mock_jwks_client(pub)), \
                 patch('backend.routes.classlink_routes._trigger_roster_sync'):
                retry = client.get("/api/classlink/callback?code=abc&state=expected-state")
        assert "classlink_login=success" in retry.location

    def test_self_initiated_student_success_clears_markers(self):
        """Single-use enforcement: successful self-initiated student login
        clears all OAuth markers so subsequent flows in the same browser
        session start fresh. (Teacher path uses session.clear(); student path
        needs the explicit pops added in the fix.)"""
        app = _make_app()
        priv, pub = _make_rsa_keypair()
        id_token = make_id_token(priv, aud="test-client-id", nonce="expected-nonce")
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "t", "id_token": id_token}
        mock_user_resp = MagicMock()
        mock_user_resp.status_code = 200
        mock_user_resp.json.return_value = {
            "UserId": "s1", "Email": "s@x.com", "Role": "student", "TenantId": "t1"
        }
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["classlink_oauth_state"] = "expected-state"
                sess["classlink_oauth_initiated_by_us"] = True
                sess["classlink_oauth_nonce"] = "expected-nonce"
            with patch('backend.routes.classlink_routes.requests.post', return_value=mock_token_resp), \
                 patch('backend.routes.classlink_routes.requests.get', return_value=mock_user_resp), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=_mock_jwks_client(pub)):
                resp = client.get("/api/classlink/callback?code=abc&state=expected-state")
            assert "classlink_login=success" in resp.location
            # Markers cleared on success.
            with client.session_transaction() as sess:
                assert "classlink_oauth_state" not in sess
                assert "classlink_oauth_initiated_by_us" not in sess
                assert "classlink_oauth_nonce" not in sess

    def test_state_mismatch_logging_does_not_leak_secrets(self):
        """Finding #3: state values are auth secrets and must not appear in
        audit-log payloads (presence booleans only)."""
        app = _make_app()
        secret_expected = "secret-expected-state-value-do-not-leak"
        secret_attacker = "attacker-supplied-state-value-do-not-leak"
        audit_calls = []
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["classlink_oauth_state"] = secret_expected
                sess["classlink_oauth_initiated_by_us"] = True
                sess["classlink_oauth_nonce"] = "expected-nonce"
            with patch('backend.routes.classlink_routes.audit_log',
                       side_effect=lambda *args, **kwargs: audit_calls.append((args, kwargs))):
                client.get(f"/api/classlink/callback?code=abc&state={secret_attacker}")
        # Mismatch was audit-logged
        event_types = [c[0][0] for c in audit_calls]
        assert "CLASSLINK_OAUTH_STATE_MISMATCH" in event_types
        # ...but neither state value appears anywhere in the payload.
        for args, kwargs in audit_calls:
            payload = " ".join(str(a) for a in args) + " " + " ".join(str(v) for v in kwargs.values())
            assert secret_expected not in payload
            assert secret_attacker not in payload

    def test_back_to_back_login_url_calls_invalidate_first_flow(self):
        """Round-2 NIT (concurrent-flow safety): a second /api/classlink/login-url
        call overwrites the first flow's state + nonce in session. The first
        flow's callback (with stale state) MUST be rejected; the second flow's
        callback (with fresh state + nonce) succeeds. Pins the contract that
        the round-2 fix's marker-persistence design relies on."""
        app = _make_app()
        priv, pub = _make_rsa_keypair()
        with app.test_client() as client:
            # Flow 1: /login-url stores state-A + nonce-A.
            first = client.get("/api/classlink/login-url")
            assert first.status_code == 200
            with client.session_transaction() as sess:
                first_state = sess["classlink_oauth_state"]
                first_nonce = sess["classlink_oauth_nonce"]
                assert sess.get("classlink_oauth_initiated_by_us") is True

            # Flow 2: /login-url overwrites with state-B + nonce-B.
            second = client.get("/api/classlink/login-url")
            assert second.status_code == 200
            with client.session_transaction() as sess:
                second_state = sess["classlink_oauth_state"]
                second_nonce = sess["classlink_oauth_nonce"]
            # secrets.token_urlsafe(32) collision is astronomically unlikely;
            # if these match the entropy is broken and the assertion fires.
            assert second_state != first_state
            assert second_nonce != first_nonce

            # Flow 1's callback (stale state) → strict-mode rejection.
            stale_callback = client.get(
                f"/api/classlink/callback?code=abc&state={first_state}"
            )
            assert "classlink_error=state_mismatch" in stale_callback.location

            # Flow 2's callback (fresh state + nonce in id_token) → success.
            id_token = make_id_token(priv, aud="test-client-id", nonce=second_nonce)
            mock_token_resp = MagicMock()
            mock_token_resp.status_code = 200
            mock_token_resp.json.return_value = {"access_token": "t", "id_token": id_token}
            mock_user_resp = MagicMock()
            mock_user_resp.status_code = 200
            mock_user_resp.json.return_value = {
                "UserId": "u1", "Email": "u@x.com", "Role": "teacher", "TenantId": "t1"
            }
            with patch('backend.routes.classlink_routes.requests.post', return_value=mock_token_resp), \
                 patch('backend.routes.classlink_routes.requests.get', return_value=mock_user_resp), \
                 patch('backend.routes.classlink_routes.get_classlink_oidc_config',
                       return_value=_mock_oidc_config()), \
                 patch('backend.routes.classlink_routes.get_classlink_jwks_client',
                       return_value=_mock_jwks_client(pub)), \
                 patch('backend.routes.classlink_routes._trigger_roster_sync'):
                fresh_callback = client.get(
                    f"/api/classlink/callback?code=def&state={second_state}"
                )
        assert "classlink_login=success" in fresh_callback.location
