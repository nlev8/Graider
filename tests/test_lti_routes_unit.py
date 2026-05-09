"""Unit tests for backend/routes/lti_routes.py.

Audit MAJOR #4 sprint follow-up to PR #283. Targets the 111 uncovered
LOC (40% baseline) — covers LTI 1.3 OIDC login, launch callback,
platform config CRUD, AGS context listing, and grade sync.

Strategy
--------
Flask test_client + mocks for the `backend.lti` module's helpers
(get_jwks, build_oidc_login_response, validate_launch_jwt,
extract_launch_data, get_platform_config, save_platform_config,
list_platform_configs, delete_platform_config, save_ags_context,
get_ags_context, list_ags_contexts, save_lti_user_mapping,
get_lti_user_mappings, match_scores_to_lti_users, AGSClient).

The teacher-authenticated routes use `g.teacher_id` populated by
`@require_teacher` from the session (`X-Test-Teacher-Id` header).
`limiter.reset()` in the fixture (per PR #283 lesson).
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def client():
    """Test client with limiter reset + teacher session."""
    from backend.app import app
    from backend.extensions import limiter
    try:
        limiter.reset()
    except Exception:
        pass
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_headers():
    """Auth headers for teacher-authenticated routes."""
    return {"X-Test-Teacher-Id": "teach-1", "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def dev_env(monkeypatch):
    """Force FLASK_ENV=development so X-Test-Teacher-Id bypass works."""
    monkeypatch.setenv("FLASK_ENV", "development")


# ──────────────────────────────────────────────────────────────────
# /api/lti/jwks
# ──────────────────────────────────────────────────────────────────


class TestJwks:
    def test_returns_jwks_document(self, client):
        canned = {"keys": [{"kty": "RSA", "kid": "k1"}]}
        with patch("backend.routes.lti_routes.get_jwks", return_value=canned):
            resp = client.get("/api/lti/jwks")
        assert resp.status_code == 200
        assert resp.get_json() == canned


# ──────────────────────────────────────────────────────────────────
# /api/lti/login
# ──────────────────────────────────────────────────────────────────


class TestLogin:
    def test_missing_iss_returns_400(self, client):
        resp = client.get("/api/lti/login")
        assert resp.status_code == 400
        assert "iss" in resp.get_json()["error"]

    def test_unregistered_platform_returns_403(self, client):
        with patch("backend.routes.lti_routes.get_platform_config",
                   return_value=None):
            resp = client.get(
                "/api/lti/login?iss=https://canvas.lms",
            )
        assert resp.status_code == 403

    def test_get_success_redirects(self, client):
        platform_cfg = {"client_id": "c1", "auth_endpoint": "https://canvas.lms/auth"}
        with patch("backend.routes.lti_routes.get_platform_config",
                   return_value=platform_cfg), \
             patch("backend.routes.lti_routes.build_oidc_login_response",
                   return_value=("https://canvas.lms/auth?state=s1",
                                 "state-1", "nonce-1")):
            resp = client.get(
                "/api/lti/login?iss=https://canvas.lms&login_hint=u1",
            )
        assert resp.status_code == 302
        assert "canvas.lms/auth" in resp.headers["Location"]

    def test_post_success_redirects(self, client):
        platform_cfg = {"client_id": "c1"}
        with patch("backend.routes.lti_routes.get_platform_config",
                   return_value=platform_cfg), \
             patch("backend.routes.lti_routes.build_oidc_login_response",
                   return_value=("https://canvas.lms/auth?state=s1",
                                 "state-1", "nonce-1")):
            resp = client.post(
                "/api/lti/login",
                data={
                    "iss": "https://canvas.lms",
                    "login_hint": "u1",
                    "target_link_uri": "https://app.graider.live/api/lti/launch",
                    "client_id": "c1",
                },
            )
        assert resp.status_code == 302

    def test_session_state_persisted(self, client):
        platform_cfg = {"client_id": "c1"}
        with patch("backend.routes.lti_routes.get_platform_config",
                   return_value=platform_cfg), \
             patch("backend.routes.lti_routes.build_oidc_login_response",
                   return_value=("redir", "S-1", "N-1")):
            client.get("/api/lti/login?iss=https://canvas.lms")

        # Verify session state was set
        with client.session_transaction() as sess:
            assert sess["lti_state"] == "S-1"
            assert sess["lti_nonce"] == "N-1"
            assert sess["lti_issuer"] == "https://canvas.lms"


# ──────────────────────────────────────────────────────────────────
# /api/lti/launch
# ──────────────────────────────────────────────────────────────────


class TestLaunch:
    def test_state_mismatch_returns_400(self, client):
        # No lti_state in session → fails
        resp = client.post(
            "/api/lti/launch",
            data={"id_token": "x", "state": "wrong"},
        )
        assert resp.status_code == 400
        assert "state" in resp.get_json()["error"].lower()

    def test_unregistered_platform_returns_403(self, client):
        with client.session_transaction() as sess:
            sess["lti_state"] = "s1"
            sess["lti_issuer"] = "https://canvas.lms"

        with patch("backend.routes.lti_routes.get_platform_config",
                   return_value=None):
            resp = client.post(
                "/api/lti/launch",
                data={"id_token": "x", "state": "s1"},
            )
        assert resp.status_code == 403

    def test_invalid_jwt_returns_400(self, client):
        with client.session_transaction() as sess:
            sess["lti_state"] = "s1"
            sess["lti_issuer"] = "https://canvas.lms"

        with patch("backend.routes.lti_routes.get_platform_config",
                   return_value={"client_id": "c1"}), \
             patch("backend.routes.lti_routes.validate_launch_jwt",
                   side_effect=ValueError("bad signature")):
            resp = client.post(
                "/api/lti/launch",
                data={"id_token": "bad", "state": "s1"},
            )
        assert resp.status_code == 400
        assert "bad signature" in resp.get_json()["error"]

    def test_invalid_nonce_returns_400(self, client):
        with client.session_transaction() as sess:
            sess["lti_state"] = "s1"
            sess["lti_nonce"] = "expected"
            sess["lti_issuer"] = "https://canvas.lms"

        with patch("backend.routes.lti_routes.get_platform_config",
                   return_value={"client_id": "c1"}), \
             patch("backend.routes.lti_routes.validate_launch_jwt",
                   return_value={"nonce": "wrong"}):
            resp = client.post(
                "/api/lti/launch",
                data={"id_token": "x", "state": "s1"},
            )
        assert resp.status_code == 400
        assert "nonce" in resp.get_json()["error"].lower()

    def test_instructor_launch_redirects_to_root(self, client):
        with client.session_transaction() as sess:
            sess["lti_state"] = "s1"
            sess["lti_nonce"] = "n1"
            sess["lti_issuer"] = "https://canvas.lms"

        with patch("backend.routes.lti_routes.get_platform_config",
                   return_value={"_registered_by": "teach-owner"}), \
             patch("backend.routes.lti_routes.validate_launch_jwt",
                   return_value={"nonce": "n1"}), \
             patch("backend.routes.lti_routes.extract_launch_data",
                   return_value={
                       "is_instructor": True,
                       "user_id": "u1",
                       "context_id": "ctx-1",
                       "ags_endpoint": "https://canvas.lms/ags",
                       "ags_lineitems_url": "https://canvas.lms/lineitems",
                       "ags_scores_url": "https://canvas.lms/scores",
                       "context_title": "Math 101",
                       "resource_link_id": "rl-1",
                   }), \
             patch("backend.routes.lti_routes.save_ags_context") as mock_save_ags:
            resp = client.post(
                "/api/lti/launch",
                data={"id_token": "x", "state": "s1"},
            )

        assert resp.status_code == 302
        assert resp.headers["Location"] == "/"
        # AGS context saved with full launch data
        mock_save_ags.assert_called_once()
        owner_id, issuer, ctx_id, ctx_data = mock_save_ags.call_args.args
        assert owner_id == "teach-owner"
        assert ctx_id == "ctx-1"
        assert ctx_data["context_title"] == "Math 101"

    def test_student_launch_saves_user_mapping_and_redirects(self, client):
        with client.session_transaction() as sess:
            sess["lti_state"] = "s1"
            sess["lti_nonce"] = "n1"
            sess["lti_issuer"] = "https://canvas.lms"

        with patch("backend.routes.lti_routes.get_platform_config",
                   return_value={"_registered_by": "teach-owner"}), \
             patch("backend.routes.lti_routes.validate_launch_jwt",
                   return_value={"nonce": "n1"}), \
             patch("backend.routes.lti_routes.extract_launch_data",
                   return_value={
                       "is_instructor": False,
                       "user_id": "student-sub-1",
                       "context_id": "ctx-1",
                       "name": "Alice Smith",
                       "email": "alice@school.edu",
                   }), \
             patch("backend.routes.lti_routes.save_lti_user_mapping") as mock_save_user:
            resp = client.post(
                "/api/lti/launch",
                data={"id_token": "x", "state": "s1"},
            )

        assert resp.status_code == 302
        assert resp.headers["Location"] == "/student"
        # User mapping saved with student identity
        mock_save_user.assert_called_once()
        kw = mock_save_user.call_args.kwargs
        assert kw["teacher_id"] == "teach-owner"
        assert kw["lti_sub"] == "student-sub-1"
        assert kw["student_name"] == "Alice Smith"


# ──────────────────────────────────────────────────────────────────
# /api/lti/config
# ──────────────────────────────────────────────────────────────────


class TestConfigGet:
    def test_lists_registered_platforms(self, client, auth_headers):
        from backend import storage

        with patch("backend.routes.lti_routes.list_platform_configs",
                   return_value=["lti_platform:https://canvas.lms"]), \
             patch.object(storage, "load",
                          return_value={
                              "issuer": "https://canvas.lms",
                              "client_id": "c1",
                              "auth_endpoint": "https://canvas.lms/auth",
                              "jwks_uri": "https://canvas.lms/jwks",
                              "token_url": "https://canvas.lms/token",
                              "_registered_by": "teach-1",
                              "secret_field": "should-not-be-exposed",
                          }):
            resp = client.get("/api/lti/config", headers=auth_headers)

        assert resp.status_code == 200
        body = resp.get_json()
        assert "tool_config" in body
        assert "platforms" in body
        assert len(body["platforms"]) == 1
        platform = body["platforms"][0]
        assert platform["issuer"] == "https://canvas.lms"
        # Sensitive fields NOT exposed
        assert "secret_field" not in platform
        assert "_registered_by" not in platform

    def test_empty_when_no_platforms(self, client, auth_headers):
        with patch("backend.routes.lti_routes.list_platform_configs",
                   return_value=[]):
            resp = client.get("/api/lti/config", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.get_json()["platforms"] == []


class TestConfigPost:
    def test_missing_required_fields_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/lti/config",
            json={"issuer": "https://canvas.lms"},  # missing other required
            headers=auth_headers,
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert "Missing required fields" in body["error"]
        # All 4 missing fields should be listed
        for field in ["client_id", "auth_login_url", "auth_token_url", "jwks_url"]:
            assert field in body["error"]

    def test_happy_path_saves_and_audits(self, client, auth_headers):
        with patch("backend.routes.lti_routes.save_platform_config") as mock_save, \
             patch("backend.routes.lti_routes.audit_log") as mock_audit:
            resp = client.post(
                "/api/lti/config",
                json={
                    "issuer": "https://canvas.lms",
                    "client_id": "c1",
                    "auth_login_url": "https://canvas.lms/auth",
                    "auth_token_url": "https://canvas.lms/token",
                    "jwks_url": "https://canvas.lms/jwks",
                    "deployment_ids": ["d1", "d2"],
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"
        # Saved with teacher_id stamping
        mock_save.assert_called_once()
        issuer, config, tid = mock_save.call_args.args
        assert config["_registered_by"] == "teach-1"
        assert config["deployment_ids"] == ["d1", "d2"]
        # Audit log fired
        mock_audit.assert_called_once()
        assert "lti_platform_registered" in mock_audit.call_args.args[0]


class TestConfigDelete:
    def test_missing_issuer_returns_400(self, client, auth_headers):
        resp = client.delete(
            "/api/lti/config",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "issuer" in resp.get_json()["error"].lower()

    def test_happy_path_deletes_and_audits(self, client, auth_headers):
        with patch("backend.routes.lti_routes.delete_platform_config") as mock_del, \
             patch("backend.routes.lti_routes.audit_log") as mock_audit:
            resp = client.delete(
                "/api/lti/config",
                json={"issuer": "https://canvas.lms"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        mock_del.assert_called_once_with("https://canvas.lms", "teach-1")
        mock_audit.assert_called_once()


# ──────────────────────────────────────────────────────────────────
# /api/lti/contexts
# ──────────────────────────────────────────────────────────────────


class TestContexts:
    def test_lists_contexts_with_student_counts(self, client, auth_headers):
        from backend import storage

        ctx_data = {
            "platform_issuer": "https://canvas.lms",
            "context_id": "ctx-1",
            "context_title": "Math 101",
            "ags_endpoint": "https://canvas.lms/ags",
        }
        with patch("backend.routes.lti_routes.list_ags_contexts",
                   return_value=["lti_ags:c"]), \
             patch.object(storage, "load", return_value=ctx_data), \
             patch("backend.routes.lti_routes.get_lti_user_mappings",
                   return_value=[{"lti_sub": "u1"}, {"lti_sub": "u2"}]):
            resp = client.get("/api/lti/contexts", headers=auth_headers)

        assert resp.status_code == 200
        contexts = resp.get_json()["contexts"]
        assert len(contexts) == 1
        assert contexts[0]["student_count"] == 2
        assert contexts[0]["context_title"] == "Math 101"

    def test_empty_contexts(self, client, auth_headers):
        with patch("backend.routes.lti_routes.list_ags_contexts",
                   return_value=[]):
            resp = client.get("/api/lti/contexts", headers=auth_headers)

        assert resp.status_code == 200
        assert resp.get_json()["contexts"] == []


# ──────────────────────────────────────────────────────────────────
# /api/lti/sync-grades
# ──────────────────────────────────────────────────────────────────


class TestSyncGrades:
    def test_missing_required_fields_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/lti/sync-grades",
            json={"label": "Q1"},  # missing platform_issuer + context_id
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_no_ags_context_returns_404(self, client, auth_headers):
        with patch("backend.routes.lti_routes.get_ags_context",
                   return_value=None):
            resp = client.post(
                "/api/lti/sync-grades",
                json={
                    "platform_issuer": "https://canvas.lms",
                    "context_id": "ctx-1",
                },
                headers=auth_headers,
            )
        assert resp.status_code == 404

    def test_no_ags_endpoint_returns_400(self, client, auth_headers):
        with patch("backend.routes.lti_routes.get_ags_context",
                   return_value={"context_id": "ctx-1"}):
            resp = client.post(
                "/api/lti/sync-grades",
                json={
                    "platform_issuer": "https://canvas.lms",
                    "context_id": "ctx-1",
                },
                headers=auth_headers,
            )
        assert resp.status_code == 400
        assert "AGS endpoint" in resp.get_json()["error"]

    def test_no_platform_config_returns_404(self, client, auth_headers):
        with patch("backend.routes.lti_routes.get_ags_context",
                   return_value={"ags_endpoint": "https://canvas.lms/ags"}), \
             patch("backend.routes.lti_routes.get_platform_config",
                   return_value=None):
            resp = client.post(
                "/api/lti/sync-grades",
                json={
                    "platform_issuer": "https://canvas.lms",
                    "context_id": "ctx-1",
                },
                headers=auth_headers,
            )
        assert resp.status_code == 404
        assert "Platform not configured" in resp.get_json()["error"]

    def test_neither_scores_nor_resolved_scores_returns_400(
        self, client, auth_headers,
    ):
        with patch("backend.routes.lti_routes.get_ags_context",
                   return_value={"ags_endpoint": "https://canvas.lms/ags"}), \
             patch("backend.routes.lti_routes.get_platform_config",
                   return_value={"client_id": "c1"}):
            resp = client.post(
                "/api/lti/sync-grades",
                json={
                    "platform_issuer": "https://canvas.lms",
                    "context_id": "ctx-1",
                },
                headers=auth_headers,
            )
        assert resp.status_code == 400
        assert "scores" in resp.get_json()["error"]

    def test_direct_mode_posts_resolved_scores(self, client, auth_headers):
        mock_client = MagicMock()
        mock_client.post_score.return_value = True

        with patch("backend.routes.lti_routes.get_ags_context",
                   return_value={
                       "ags_endpoint": "https://canvas.lms/ags",
                       "resource_link_id": "rl-1",
                   }), \
             patch("backend.routes.lti_routes.get_platform_config",
                   return_value={"client_id": "c1"}), \
             patch("backend.routes.lti_routes.AGSClient",
                   return_value=mock_client):
            resp = client.post(
                "/api/lti/sync-grades",
                json={
                    "platform_issuer": "https://canvas.lms",
                    "context_id": "ctx-1",
                    "lineitem_url": "https://canvas.lms/lineitem/123",
                    "max_score": 100,
                    "resolved_scores": [
                        {"user_id": "u1", "score": 85},
                        {"user_id": "u2", "score": 90},
                    ],
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["posted"] == 2
        assert body["total"] == 2
        assert body["errors"] == []

    def test_auto_match_mode_resolves_via_mappings(self, client, auth_headers):
        mock_client = MagicMock()
        mock_client.post_score.return_value = True

        with patch("backend.routes.lti_routes.get_ags_context",
                   return_value={
                       "ags_endpoint": "https://canvas.lms/ags",
                       "resource_link_id": "rl-1",
                   }), \
             patch("backend.routes.lti_routes.get_platform_config",
                   return_value={"client_id": "c1"}), \
             patch("backend.routes.lti_routes.get_lti_user_mappings",
                   return_value=[
                       {"lti_sub": "lti-u1", "student_name": "Alice"},
                   ]), \
             patch("backend.routes.lti_routes.match_scores_to_lti_users",
                   return_value=(
                       [{"lti_sub": "lti-u1", "score": 85}],
                       ["Bob"],  # unmatched
                   )), \
             patch("backend.routes.lti_routes.AGSClient",
                   return_value=mock_client):
            resp = client.post(
                "/api/lti/sync-grades",
                json={
                    "platform_issuer": "https://canvas.lms",
                    "context_id": "ctx-1",
                    "lineitem_url": "https://canvas.lms/lineitem/123",
                    "scores": [
                        {"student_name": "Alice", "score": 85},
                        {"student_name": "Bob", "score": 90},
                    ],
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["posted"] == 1
        assert body["unmatched_students"] == ["Bob"]

    def test_lineitem_creation_when_missing(self, client, auth_headers):
        mock_client = MagicMock()
        mock_client.post_score.return_value = True
        mock_client.create_lineitem.return_value = {"id": "https://canvas.lms/lineitem/new"}

        with patch("backend.routes.lti_routes.get_ags_context",
                   return_value={
                       "ags_endpoint": "https://canvas.lms/ags",
                       "resource_link_id": "rl-1",
                   }), \
             patch("backend.routes.lti_routes.get_platform_config",
                   return_value={"client_id": "c1"}), \
             patch("backend.routes.lti_routes.AGSClient",
                   return_value=mock_client):
            resp = client.post(
                "/api/lti/sync-grades",
                json={
                    "platform_issuer": "https://canvas.lms",
                    "context_id": "ctx-1",
                    # NO lineitem_url → must be created
                    "label": "Quiz 1",
                    "max_score": 100,
                    "resolved_scores": [{"user_id": "u1", "score": 85}],
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        # create_lineitem was called with label + max_score
        mock_client.create_lineitem.assert_called_once_with("Quiz 1", 100, "rl-1")

    def test_lineitem_creation_failure_returns_500(self, client, auth_headers):
        mock_client = MagicMock()
        mock_client.create_lineitem.side_effect = RuntimeError("AGS down")

        with patch("backend.routes.lti_routes.get_ags_context",
                   return_value={
                       "ags_endpoint": "https://canvas.lms/ags",
                   }), \
             patch("backend.routes.lti_routes.get_platform_config",
                   return_value={"client_id": "c1"}), \
             patch("backend.routes.lti_routes.AGSClient",
                   return_value=mock_client):
            resp = client.post(
                "/api/lti/sync-grades",
                json={
                    "platform_issuer": "https://canvas.lms",
                    "context_id": "ctx-1",
                    "resolved_scores": [{"user_id": "u1", "score": 85}],
                },
                headers=auth_headers,
            )

        assert resp.status_code == 500

    def test_partial_post_failure_recorded_in_errors(self, client, auth_headers):
        mock_client = MagicMock()
        # First post succeeds, second fails
        mock_client.post_score.side_effect = [True, False]

        with patch("backend.routes.lti_routes.get_ags_context",
                   return_value={
                       "ags_endpoint": "https://canvas.lms/ags",
                       "resource_link_id": "rl-1",
                   }), \
             patch("backend.routes.lti_routes.get_platform_config",
                   return_value={"client_id": "c1"}), \
             patch("backend.routes.lti_routes.AGSClient",
                   return_value=mock_client):
            resp = client.post(
                "/api/lti/sync-grades",
                json={
                    "platform_issuer": "https://canvas.lms",
                    "context_id": "ctx-1",
                    "lineitem_url": "https://canvas.lms/lineitem/x",
                    "resolved_scores": [
                        {"user_id": "u1", "score": 85},
                        {"user_id": "u2", "score": 90},
                    ],
                },
                headers=auth_headers,
            )

        body = resp.get_json()
        assert body["posted"] == 1
        assert body["errors"] == ["u2"]


# ──────────────────────────────────────────────────────────────────
# _get_tool_url helper
# ──────────────────────────────────────────────────────────────────


class TestGetToolUrl:
    def test_env_var_takes_priority(self, client, monkeypatch):
        # When LTI_TOOL_URL is set, it wins (used by the jwks endpoint)
        monkeypatch.setenv("LTI_TOOL_URL", "https://staging.graider.live")
        # We can verify via the config endpoint output which uses _get_tool_url
        with client.session_transaction() as sess:
            sess['user_id'] = 'teach-1'
        with patch("backend.routes.lti_routes.list_platform_configs",
                   return_value=[]):
            resp = client.get(
                "/api/lti/config",
                headers={"X-Test-Teacher-Id": "teach-1"},
            )
        body = resp.get_json()
        assert "staging.graider.live" in body["tool_config"]["oidc_login_url"]

    def test_env_var_strips_trailing_slash(self, client, monkeypatch):
        monkeypatch.setenv("LTI_TOOL_URL", "https://staging.graider.live/")
        with patch("backend.routes.lti_routes.list_platform_configs",
                   return_value=[]):
            resp = client.get(
                "/api/lti/config",
                headers={"X-Test-Teacher-Id": "teach-1"},
            )
        body = resp.get_json()
        # Slash trimmed: URL is `staging.graider.live/api/...` not `staging.graider.live//api/...`
        assert "https://staging.graider.live//" not in body["tool_config"]["oidc_login_url"]
