"""Tests for ClassLink OAuth2/OIDC SSO flow."""

import os
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from flask import Flask, session


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

        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "test-token"}

        mock_user_resp = MagicMock()
        mock_user_resp.status_code = 200
        mock_user_resp.json.return_value = {
            "UserId": "cl-user-123",
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
                 patch('backend.routes.classlink_routes._link_classlink_account'), \
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

        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "test-token"}

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
                 patch('backend.routes.classlink_routes.requests.get', return_value=mock_user_resp):
                resp = client.get('/api/classlink/callback?code=auth-code-123&state=valid-state')

            assert resp.status_code == 302
            assert '/student' in resp.location

    def test_classlink_initiated_flow_no_state(self):
        """ClassLink-initiated flows (LaunchPad tile) may not have state — should still work."""
        app = _make_app()

        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "test-token"}

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
                 patch('backend.routes.classlink_routes._link_classlink_account'), \
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
