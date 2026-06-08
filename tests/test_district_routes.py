"""Tests for district admin setup routes.

Covers auth flow, config status, config CRUD, and validation.
"""
import json
import os
import pytest
from unittest.mock import patch, MagicMock
from werkzeug.security import generate_password_hash


@pytest.fixture
def app():
    """Create a minimal Flask app with district routes registered."""
    from flask import Flask
    from backend.routes.district_routes import district_bp

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.register_blueprint(district_bp)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


# ── Auth Tests ───────────────────────────────────────────────────────────────

class TestDistrictAuth:
    """Test POST /api/district/auth endpoint."""

    def test_auth_without_password_no_stored_returns_needs_setup(self, client):
        """When no password is stored and none in env, return needs_setup."""
        with patch("backend.routes.district_routes.storage_load", return_value=None), \
             patch.dict(os.environ, {}, clear=True):
            resp = client.post("/api/district/auth", json={})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data.get("needs_setup") is True

    def test_auth_setup_creates_password(self, client):
        """Setup mode with a VALID setup token creates the admin password.

        audit #1: self-service bootstrap now requires an out-of-band
        DISTRICT_SETUP_TOKEN (see TestDistrictBootstrapTokenGate for the
        refusal cases); this pins the token-gated happy path.
        """
        with patch("backend.routes.district_routes.storage_load", return_value=None), \
             patch("backend.routes.district_routes.storage_save") as mock_save, \
             patch("backend.routes.district_routes.audit_log"), \
             patch.dict(os.environ, {"DISTRICT_SETUP_TOKEN": "setup-tok"}, clear=True):
            resp = client.post("/api/district/auth", json={
                "setup": True,
                "password": "securepass123",
                "setup_token": "setup-tok",
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data.get("authenticated") is True
            # Verify password hash was saved
            mock_save.assert_called_once()
            call_args = mock_save.call_args
            assert call_args[0][0] == "district:password_hash"
            assert "hash" in call_args[0][1]

    def test_auth_setup_rejects_short_password(self, client):
        """Setup with a valid token but password shorter than 8 chars is rejected
        (the token gate passes, then the length check returns 400)."""
        with patch("backend.routes.district_routes.storage_load", return_value=None), \
             patch.dict(os.environ, {"DISTRICT_SETUP_TOKEN": "setup-tok"}, clear=True):
            resp = client.post("/api/district/auth", json={
                "setup": True,
                "password": "short",
                "setup_token": "setup-tok",
            })
            assert resp.status_code == 400

    def test_auth_wrong_password_returns_403(self, client):
        """Wrong password returns 403."""
        pw_hash = generate_password_hash("correctpassword")
        with patch("backend.routes.district_routes.storage_load", return_value={"hash": pw_hash}), \
             patch("backend.routes.district_routes.audit_log"):
            resp = client.post("/api/district/auth", json={
                "password": "wrongpassword"
            })
            assert resp.status_code == 403

    def test_auth_correct_password_sets_session(self, client):
        """Correct password sets session and returns authenticated."""
        pw_hash = generate_password_hash("correctpassword")
        with patch("backend.routes.district_routes.storage_load", return_value={"hash": pw_hash}), \
             patch("backend.routes.district_routes.audit_log"):
            resp = client.post("/api/district/auth", json={
                "password": "correctpassword"
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data.get("authenticated") is True


# ── Config Status Tests ──────────────────────────────────────────────────────

class TestDistrictConfigStatus:
    """Test GET /api/district/config-status (public)."""

    def test_config_status_is_public(self, client):
        """Config status returns 200 without auth."""
        with patch("backend.routes.district_routes.storage_load", return_value=None):
            resp = client.get("/api/district/config-status")
            assert resp.status_code == 200
            data = resp.get_json()
            assert "sis_provider" in data
            assert "has_ai_keys" in data

    def test_config_status_shows_provider(self, client):
        """Config status reflects stored SIS type."""
        def mock_load(key, teacher_id):
            if key == "district:sis_config":
                return {"sis_type": "oneroster"}
            return None

        with patch("backend.routes.district_routes.storage_load", side_effect=mock_load):
            resp = client.get("/api/district/config-status")
            data = resp.get_json()
            assert data["sis_provider"] == "oneroster"
            assert data["has_ai_keys"] is False


# ── Config CRUD Tests ────────────────────────────────────────────────────────

class TestDistrictConfig:
    """Test GET/POST /api/district/config (requires admin)."""

    def test_get_config_requires_admin(self, client):
        """GET config without session returns 401."""
        resp = client.get("/api/district/config")
        assert resp.status_code == 401

    def test_post_config_validates_sis_type(self, client):
        """POST config with invalid sis_type returns 400."""
        # First authenticate
        pw_hash = generate_password_hash("testpass123")
        with patch("backend.routes.district_routes.storage_load", return_value={"hash": pw_hash}), \
             patch("backend.routes.district_routes.audit_log"):
            client.post("/api/district/auth", json={"password": "testpass123"})

        # Now try saving invalid SIS type
        with patch("backend.routes.district_routes.storage_load", return_value=None), \
             patch("backend.routes.district_routes.storage_save"):
            resp = client.post("/api/district/config", json={
                "sis": {"sis_type": "invalid_provider"}
            })
            assert resp.status_code == 400
            data = resp.get_json()
            assert "sis_type" in data.get("error", "")

    def test_post_config_saves_valid_sis(self, client):
        """POST config with valid SIS data saves successfully."""
        pw_hash = generate_password_hash("testpass123")
        with patch("backend.routes.district_routes.storage_load", return_value={"hash": pw_hash}), \
             patch("backend.routes.district_routes.audit_log"):
            client.post("/api/district/auth", json={"password": "testpass123"})

        with patch("backend.routes.district_routes.storage_load", return_value=None), \
             patch("backend.routes.district_routes.storage_save") as mock_save, \
             patch("backend.routes.district_routes.audit_log"):
            resp = client.post("/api/district/config", json={
                "sis": {
                    "sis_type": "oneroster",
                    "client_id": "test-id",
                    "client_secret": "test-secret",
                    "base_url": "https://sis.example.com/api/v1p1",
                }
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data.get("status") == "saved"

    def test_get_config_masks_secrets(self, client):
        """GET config returns has_client_secret instead of actual secret."""
        pw_hash = generate_password_hash("testpass123")

        def mock_load(key, teacher_id):
            if key == "district:password_hash":
                return {"hash": pw_hash}
            if key == "district:sis_config":
                return {"sis_type": "oneroster", "client_id": "id-123", "client_secret": "super-secret"}
            if key == "district:ai_keys":
                return {"openai_api_key": "sk-test"}
            return None

        with patch("backend.routes.district_routes.storage_load", side_effect=mock_load), \
             patch("backend.routes.district_routes.audit_log"):
            client.post("/api/district/auth", json={"password": "testpass123"})

        with patch("backend.routes.district_routes.storage_load", side_effect=mock_load):
            resp = client.get("/api/district/config")
            assert resp.status_code == 200
            data = resp.get_json()
            # Secret should be masked
            assert data["sis"]["has_client_secret"] is True
            assert "client_secret" not in data["sis"] or data["sis"].get("client_secret") is None
            # AI keys should be masked
            assert data["ai_keys"]["has_openai_key"] is True


# ── Logout Tests ─────────────────────────────────────────────────────────────

class TestDistrictLogout:
    """Test DELETE /api/district/auth."""

    def test_logout_clears_session(self, client):
        """Logout clears district_admin from session."""
        pw_hash = generate_password_hash("testpass123")
        with patch("backend.routes.district_routes.storage_load", return_value={"hash": pw_hash}), \
             patch("backend.routes.district_routes.audit_log"):
            client.post("/api/district/auth", json={"password": "testpass123"})

        resp = client.delete("/api/district/auth")
        assert resp.status_code == 200

        # Verify session is cleared — config should now require auth
        resp = client.get("/api/district/config")
        assert resp.status_code == 401


# ── Provider Switch Tests ─────────────────────────────────────────────────────

class TestProviderSwitch:
    def test_provider_switch_triggers_cleanup(self, client):
        """When district admin changes sis_type, old roster data should be cleared."""
        with client.session_transaction() as sess:
            sess["district_admin"] = True

        with patch("backend.routes.district_routes.storage_save") as mock_save, \
             patch("backend.routes.district_routes.storage_load") as mock_load, \
             patch("backend.routes.district_routes._clear_old_provider_data") as mock_clear:
            mock_load.return_value = {"sis_type": "clever", "client_id": "old"}
            resp = client.post("/api/district/config",
                               data=json.dumps({"sis": {
                                   "sis_type": "oneroster",
                                   "client_id": "new-id",
                                   "client_secret": "new-secret",
                                   "base_url": "https://example.com",
                               }}),
                               content_type="application/json")
            assert resp.status_code == 200
            mock_clear.assert_called_once_with("clever")

    def test_same_provider_no_cleanup(self, client):
        """Saving same sis_type should NOT trigger cleanup."""
        with client.session_transaction() as sess:
            sess["district_admin"] = True

        with patch("backend.routes.district_routes.storage_save"), \
             patch("backend.routes.district_routes.storage_load") as mock_load, \
             patch("backend.routes.district_routes._clear_old_provider_data") as mock_clear:
            mock_load.return_value = {"sis_type": "oneroster", "client_id": "existing"}
            resp = client.post("/api/district/config",
                               data=json.dumps({"sis": {
                                   "sis_type": "oneroster",
                                   "client_id": "updated-id",
                                   "client_secret": "updated-secret",
                                   "base_url": "https://example.com",
                               }}),
                               content_type="application/json")
            assert resp.status_code == 200
            mock_clear.assert_not_called()
