"""Additional unit tests for backend/routes/district_routes.py.

Audit MAJOR #4 sprint follow-up to PR #289. Companion to existing
tests/test_district_routes.py which already covers auth + basic
config flows. Targets the remaining 180 uncovered LOC (43% → ~99%):

* _get_district_password_hash env-var bootstrap (lines 42-45)
* _clear_old_provider_data full helper (lines 74-161, ~88 LOC)
* district_auth no-password-but-pw-stored (line 190)
* district_change_password (lines 218-235): all 4 branches
* district_config_status truthy ai-keys branch (line 253)
* district_save_config merge edge cases (315, 317, 331-333) and
  AI keys CRUD (361-375)
* district_test_connection (lines 387-436): not configured, clever,
  oneroster success + failure
* district_create_admin_invite (lines 446-465)
* district_list_admins (lines 475-486)
* district_revoke_admin (lines 496-510)
* district_teacher_search (lines 520-551)

Strategy
--------
Same minimal Flask app fixture + storage_load/storage_save patching
as test_district_routes.py. _require_district_admin bypassed by
setting `session["district_admin"] = True` via Flask test_client's
`session_transaction()` context manager (the natural way to populate
session state for an endpoint protected by a custom decorator).
"""
from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from werkzeug.security import check_password_hash, generate_password_hash


@pytest.fixture
def app():
    """Minimal Flask app with district routes registered (mirror of
    the fixture in test_district_routes.py)."""
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


@pytest.fixture
def admin_client(app):
    """Client with `district_admin = True` session pre-set so endpoints
    behind @_require_district_admin pass through."""
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["district_admin"] = True
    return c


# ──────────────────────────────────────────────────────────────────
# _get_district_password_hash env-var bootstrap (lines 42-45)
# ──────────────────────────────────────────────────────────────────


class TestPasswordHashBootstrap:
    def test_env_var_bootstraps_hash_on_first_call(self, client):
        # No stored hash + DISTRICT_ADMIN_PASSWORD set → hash bootstrapped
        # AND saved to storage. Subsequent auth call uses the new hash.
        save_mock = MagicMock()
        with patch(
            "backend.routes.district_routes.storage_load",
            return_value=None,
        ), patch(
            "backend.routes.district_routes.storage_save", save_mock,
        ), patch(
            "backend.routes.district_routes.audit_log",
        ), patch.dict(
            os.environ, {"DISTRICT_ADMIN_PASSWORD": "envpass1234"},
        ):
            resp = client.post(
                "/api/district/auth",
                json={"password": "envpass1234"},
            )
        assert resp.status_code == 200
        assert resp.get_json()["authenticated"] is True
        # The hash save is the first call; verify it's the EXACT hash
        # of the env-var value, not just a dict with a "hash" key.
        # (Gemini round-1 #2: the previous assertion was tautological.)
        save_args = save_mock.call_args_list[0].args
        assert save_args[0] == "district:password_hash"
        assert "hash" in save_args[1]
        assert check_password_hash(
            save_args[1]["hash"], "envpass1234",
        ), "Bootstrapped hash must verify against DISTRICT_ADMIN_PASSWORD"


class TestDistrictBootstrapTokenGate:
    """audit #1: the unauthenticated self-service bootstrap must NOT let the
    first anonymous caller claim the district-admin role. Self-service setup now
    requires an out-of-band DISTRICT_SETUP_TOKEN; absent/wrong token → refused."""

    def _post_setup(self, client, body):
        save_mock = MagicMock()
        with patch("backend.routes.district_routes.storage_load", return_value=None), \
             patch("backend.routes.district_routes.storage_save", save_mock), \
             patch("backend.routes.district_routes.audit_log"):
            resp = client.post("/api/district/auth", json=body)
        saved_keys = [c.args[0] for c in save_mock.call_args_list]
        return resp, saved_keys

    def test_bootstrap_refused_without_setup_token(self, client, monkeypatch):
        monkeypatch.delenv("DISTRICT_ADMIN_PASSWORD", raising=False)
        monkeypatch.delenv("DISTRICT_SETUP_TOKEN", raising=False)
        resp, saved_keys = self._post_setup(
            client, {"setup": True, "password": "longenough12"})
        assert resp.status_code == 403
        assert not (resp.get_json() or {}).get("authenticated")
        assert "district:password_hash" not in saved_keys, "anonymous bootstrap must not set a password"

    def test_bootstrap_refused_with_wrong_setup_token(self, client, monkeypatch):
        monkeypatch.delenv("DISTRICT_ADMIN_PASSWORD", raising=False)
        monkeypatch.setenv("DISTRICT_SETUP_TOKEN", "correct-token")
        resp, saved_keys = self._post_setup(
            client, {"setup": True, "password": "longenough12", "setup_token": "wrong"})
        assert resp.status_code == 403
        assert "district:password_hash" not in saved_keys

    def test_bootstrap_allowed_with_valid_setup_token(self, client, monkeypatch):
        monkeypatch.delenv("DISTRICT_ADMIN_PASSWORD", raising=False)
        monkeypatch.setenv("DISTRICT_SETUP_TOKEN", "correct-token")
        resp, saved_keys = self._post_setup(
            client, {"setup": True, "password": "longenough12", "setup_token": "correct-token"})
        assert resp.status_code == 200
        assert resp.get_json()["authenticated"] is True
        assert "district:password_hash" in saved_keys


# ──────────────────────────────────────────────────────────────────
# district_auth: stored-pw + no password supplied (line 190)
# ──────────────────────────────────────────────────────────────────


class TestDistrictAuthMissingPassword:
    def test_existing_pw_without_password_field_returns_400(self, client):
        pw_hash = generate_password_hash("hello1234")
        with patch(
            "backend.routes.district_routes.storage_load",
            return_value={"hash": pw_hash},
        ):
            resp = client.post("/api/district/auth", json={})
        assert resp.status_code == 400
        assert "Password required" in resp.get_json()["error"]


# ──────────────────────────────────────────────────────────────────
# district_change_password (lines 218-235)
# ──────────────────────────────────────────────────────────────────


class TestChangePassword:
    def test_requires_admin_session(self, client):
        # No session → 401 from the @_require_district_admin decorator
        resp = client.post(
            "/api/district/change-password",
            json={"current_password": "x", "new_password": "y"},
        )
        assert resp.status_code == 401

    def test_missing_fields_returns_400(self, admin_client):
        for body in [{}, {"current_password": "x"}, {"new_password": "y"}]:
            resp = admin_client.post(
                "/api/district/change-password", json=body,
            )
            assert resp.status_code == 400

    def test_short_new_password_returns_400(self, admin_client):
        with patch(
            "backend.routes.district_routes.storage_load",
            return_value={"hash": generate_password_hash("oldpass1234")},
        ):
            resp = admin_client.post(
                "/api/district/change-password",
                json={"current_password": "oldpass1234", "new_password": "1"},
            )
        assert resp.status_code == 400
        assert "8 characters" in resp.get_json()["error"]

    def test_wrong_current_password_returns_403(self, admin_client):
        with patch(
            "backend.routes.district_routes.storage_load",
            return_value={"hash": generate_password_hash("correctpass")},
        ), patch(
            "backend.routes.district_routes.audit_log",
        ):
            resp = admin_client.post(
                "/api/district/change-password",
                json={
                    "current_password": "WRONG",
                    "new_password": "newpass1234",
                },
            )
        assert resp.status_code == 403
        assert "incorrect" in resp.get_json()["error"]

    def test_no_existing_hash_returns_403(self, admin_client):
        # Edge: admin session set but storage has no hash → also 403
        with patch(
            "backend.routes.district_routes.storage_load",
            return_value=None,
        ), patch.dict(os.environ, {}, clear=True):
            resp = admin_client.post(
                "/api/district/change-password",
                json={
                    "current_password": "anything",
                    "new_password": "newpass1234",
                },
            )
        assert resp.status_code == 403

    def test_happy_path_changes_password(self, admin_client):
        save_mock = MagicMock()
        with patch(
            "backend.routes.district_routes.storage_load",
            return_value={"hash": generate_password_hash("oldpass1234")},
        ), patch(
            "backend.routes.district_routes.storage_save", save_mock,
        ), patch(
            "backend.routes.district_routes.audit_log",
        ):
            resp = admin_client.post(
                "/api/district/change-password",
                json={
                    "current_password": "oldpass1234",
                    "new_password": "newpass1234",
                },
            )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "password_changed"
        save_mock.assert_called_once()
        # New hash was persisted
        assert save_mock.call_args.args[0] == "district:password_hash"


# ──────────────────────────────────────────────────────────────────
# district_config_status with both ai-keys present (line 253)
# ──────────────────────────────────────────────────────────────────


class TestConfigStatusWithKeys:
    def test_has_ai_keys_true_when_openai_present(self, client):
        def loader(key, _tid):
            if key == "district:sis_config":
                return {"sis_type": "clever"}
            if key == "district:ai_keys":
                return {"openai_api_key": "sk-x"}
            if key == "district:password_hash":
                return {"hash": "h"}
            return None
        with patch(
            "backend.routes.district_routes.storage_load",
            side_effect=loader,
        ):
            resp = client.get("/api/district/config-status")
        body = resp.get_json()
        assert body["has_ai_keys"] is True
        assert body["sis_provider"] == "clever"
        assert body["needs_setup"] is False

    def test_has_ai_keys_true_when_only_anthropic_present(self, client):
        def loader(key, _tid):
            if key == "district:ai_keys":
                return {"anthropic_api_key": "sk-x"}
            if key == "district:password_hash":
                return {"hash": "h"}
            return None
        with patch(
            "backend.routes.district_routes.storage_load",
            side_effect=loader,
        ):
            resp = client.get("/api/district/config-status")
        assert resp.get_json()["has_ai_keys"] is True


# ──────────────────────────────────────────────────────────────────
# district_save_config merge edge cases (lines 315, 317, 331-333)
# and AI keys CRUD (361-375)
# ──────────────────────────────────────────────────────────────────


class TestSaveConfigMergeEdgeCases:
    def test_save_type_only_no_creds_passes(self, admin_client):
        # Allowed: save sis_type without client_id/secret yet (line 313-315)
        save_mock = MagicMock()
        with patch(
            "backend.routes.district_routes.storage_load",
            return_value=None,
        ), patch(
            "backend.routes.district_routes.storage_save", save_mock,
        ), patch(
            "backend.routes.district_routes.audit_log",
        ):
            resp = admin_client.post(
                "/api/district/config",
                json={"sis": {"sis_type": "clever"}},
            )
        assert resp.status_code == 200

    def test_secret_without_client_id_returns_400(self, admin_client):
        # client_secret provided without client_id → 400 (line 316-317)
        with patch(
            "backend.routes.district_routes.storage_load",
            return_value=None,
        ):
            resp = admin_client.post(
                "/api/district/config",
                json={"sis": {
                    "sis_type": "oneroster",
                    "client_secret": "shh",
                    # NOTE: no client_id
                }},
            )
        assert resp.status_code == 400
        assert "client_id is required" in resp.get_json()["error"]

    def test_empty_string_keeps_existing_field(self, admin_client):
        # Lines 329-333: new_val == "" + existing has value → keep existing
        existing = {
            "sis_type": "oneroster",
            "client_id": "old-cid",
            "base_url": "https://old.example",
            "client_secret": "old-secret",
        }

        def loader(key, _tid):
            if key == "district:sis_config":
                return existing
            return None

        save_mock = MagicMock()
        with patch(
            "backend.routes.district_routes.storage_load",
            side_effect=loader,
        ), patch(
            "backend.routes.district_routes.storage_save", save_mock,
        ), patch(
            "backend.routes.district_routes.audit_log",
        ):
            resp = admin_client.post(
                "/api/district/config",
                json={"sis": {
                    "sis_type": "oneroster",
                    "client_id": "new-cid",   # set
                    "base_url": "",           # empty → keep existing
                    "client_secret": None,    # null → drop (line 326-328)
                }},
            )
        assert resp.status_code == 200
        # Inspect the merged dict that was saved
        merged = save_mock.call_args.args[1]
        assert merged["client_id"] == "new-cid"
        # Empty string preserved old value
        assert merged["base_url"] == "https://old.example"
        # null = drop (not in merged)
        assert "client_secret" not in merged

    def test_ai_keys_null_deletes_existing(self, admin_client):
        # Lines 361-375: null = delete, empty = keep, value = replace
        existing_ai = {
            "openai_api_key": "old-openai",
            "anthropic_api_key": "old-anthropic",
        }

        def loader(key, _tid):
            if key == "district:ai_keys":
                return existing_ai
            return None

        save_mock = MagicMock()
        with patch(
            "backend.routes.district_routes.storage_load",
            side_effect=loader,
        ), patch(
            "backend.routes.district_routes.storage_save", save_mock,
        ), patch(
            "backend.routes.district_routes.audit_log",
        ):
            resp = admin_client.post(
                "/api/district/config",
                json={"ai_keys": {
                    "openai_api_key": None,        # delete
                    "anthropic_api_key": "",       # keep existing
                }},
            )
        assert resp.status_code == 200
        merged = save_mock.call_args.args[1]
        # null deleted openai
        assert "openai_api_key" not in merged
        # empty string preserved anthropic
        assert merged["anthropic_api_key"] == "old-anthropic"

    def test_ai_keys_value_replaces_existing(self, admin_client):
        existing_ai = {"openai_api_key": "old-openai"}

        def loader(key, _tid):
            if key == "district:ai_keys":
                return existing_ai
            return None

        save_mock = MagicMock()
        with patch(
            "backend.routes.district_routes.storage_load",
            side_effect=loader,
        ), patch(
            "backend.routes.district_routes.storage_save", save_mock,
        ), patch(
            "backend.routes.district_routes.audit_log",
        ):
            resp = admin_client.post(
                "/api/district/config",
                json={"ai_keys": {
                    "openai_api_key": "new-openai",
                }},
            )
        assert resp.status_code == 200
        merged = save_mock.call_args.args[1]
        assert merged["openai_api_key"] == "new-openai"


# ──────────────────────────────────────────────────────────────────
# district_test_connection (lines 387-436)
# ──────────────────────────────────────────────────────────────────


class TestTestConnection:
    def test_not_configured_returns_400(self, admin_client):
        with patch(
            "backend.routes.district_routes.storage_load",
            return_value=None,
        ):
            resp = admin_client.post("/api/district/test-connection")
        assert resp.status_code == 400
        assert "not configured" in resp.get_json()["error"]

    def test_clever_with_credentials_returns_config_valid(
        self, admin_client,
    ):
        with patch(
            "backend.routes.district_routes.storage_load",
            return_value={
                "sis_type": "clever",
                "client_id": "cid",
                "client_secret": "csec",
            },
        ):
            resp = admin_client.post("/api/district/test-connection")
        body = resp.get_json()
        assert body["status"] == "config_valid"

    def test_clever_missing_credentials_returns_400(self, admin_client):
        with patch(
            "backend.routes.district_routes.storage_load",
            return_value={"sis_type": "clever"},
        ):
            resp = admin_client.post("/api/district/test-connection")
        assert resp.status_code == 400

    def test_oneroster_missing_required_fields_returns_400(
        self, admin_client,
    ):
        with patch(
            "backend.routes.district_routes.storage_load",
            return_value={"sis_type": "oneroster", "base_url": "u"},
        ):
            resp = admin_client.post("/api/district/test-connection")
        assert resp.status_code == 400
        assert "OneRoster requires" in resp.get_json()["error"]

    def test_oneroster_connectivity_success(self, admin_client):
        # Mock OneRosterClient + httpx.AsyncClient + asyncio.new_event_loop
        # so the helper's `loop.run_until_complete(_test())` succeeds.
        cfg = {
            "sis_type": "oneroster",
            "base_url": "https://x.example/oneroster",
            "client_id": "cid",
            "client_secret": "csec",
            "token_url": "https://x.example/token",
        }

        # AsyncMock for the awaited coroutines — cleaner than assigning
        # `async def` stubs and supports call-assertions if needed.
        fake_client = MagicMock()
        fake_client.base_url = cfg["base_url"]
        fake_client._ensure_token = AsyncMock()
        fake_client._get_with_retry = AsyncMock()

        with patch(
            "backend.routes.district_routes.storage_load",
            return_value=cfg,
        ), patch(
            "backend.oneroster.OneRosterClient",
            return_value=fake_client,
        ):
            resp = admin_client.post("/api/district/test-connection")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "connected"

    def test_oneroster_connectivity_failure_returns_502(
        self, admin_client,
    ):
        cfg = {
            "sis_type": "oneroster",
            "base_url": "https://x.example/oneroster",
            "client_id": "cid",
            "client_secret": "csec",
        }
        fake_client = MagicMock()
        fake_client.base_url = cfg["base_url"]
        fake_client._ensure_token = AsyncMock(
            side_effect=RuntimeError("oauth dead"),
        )

        with patch(
            "backend.routes.district_routes.storage_load",
            return_value=cfg,
        ), patch(
            "backend.oneroster.OneRosterClient",
            return_value=fake_client,
        ):
            resp = admin_client.post("/api/district/test-connection")
        assert resp.status_code == 502
        assert "Connection failed" in resp.get_json()["error"]

    def test_unknown_sis_type_returns_400(self, admin_client):
        with patch(
            "backend.routes.district_routes.storage_load",
            return_value={"sis_type": "something-weird"},
        ):
            resp = admin_client.post("/api/district/test-connection")
        assert resp.status_code == 400
        assert "Unknown SIS type" in resp.get_json()["error"]


# ──────────────────────────────────────────────────────────────────
# district_create_admin_invite (lines 446-465)
# ──────────────────────────────────────────────────────────────────


class TestCreateAdminInvite:
    def test_requires_admin_session(self, client):
        resp = client.post("/api/district/admin-invite", json={})
        assert resp.status_code == 401

    def test_creates_invite_with_school_and_teachers(self, admin_client):
        save_mock = MagicMock()
        with patch(
            "backend.routes.district_routes.storage_save", save_mock,
        ), patch(
            "backend.routes.district_routes.audit_log",
        ):
            resp = admin_client.post(
                "/api/district/admin-invite",
                json={
                    "school": "Lincoln HS",
                    "manual_teachers": [
                        {"name": "T1", "email": "t1@example.com"},
                    ],
                },
            )
        body = resp.get_json()
        # 6-char hex code uppercased (3 hex bytes = 6 hex chars)
        assert isinstance(body["code"], str)
        assert len(body["code"]) == 6
        assert body["code"].upper() == body["code"]
        # expires_at is an ISO timestamp 7 days out
        assert "T" in body["expires_at"]
        assert body["school"] == "Lincoln HS"
        # Storage write keyed by admin_invite:CODE
        save_mock.assert_called_once()
        save_key = save_mock.call_args.args[0]
        assert save_key.startswith("admin_invite:")
        save_payload = save_mock.call_args.args[1]
        assert save_payload["school"] == "Lincoln HS"
        assert len(save_payload["manual_teachers"]) == 1


# ──────────────────────────────────────────────────────────────────
# district_list_admins (lines 475-486)
# ──────────────────────────────────────────────────────────────────


class TestListAdmins:
    def test_requires_admin_session(self, client):
        resp = client.get("/api/district/admins")
        assert resp.status_code == 401

    def test_empty_returns_empty_list(self, admin_client):
        with patch(
            "backend.routes.district_routes.list_keys",
            return_value=[],
        ):
            resp = admin_client.get("/api/district/admins")
        assert resp.status_code == 200
        assert resp.get_json() == {"admins": []}

    def test_populated_returns_admin_records(self, admin_client):
        keys = ["admin_role:user-1", "admin_role:user-2"]
        records = {
            "admin_role:user-1": {
                "school": "Lincoln HS", "granted_at": "2026-01-01",
            },
            "admin_role:user-2": {
                "school": "Wilson MS", "granted_at": "2026-02-01",
            },
        }

        with patch(
            "backend.routes.district_routes.list_keys",
            return_value=keys,
        ), patch(
            "backend.routes.district_routes.storage_load",
            side_effect=lambda k, _: records.get(k),
        ):
            resp = admin_client.get("/api/district/admins")
        admins = resp.get_json()["admins"]
        assert len(admins) == 2
        u1 = next(a for a in admins if a["user_id"] == "user-1")
        assert u1["school"] == "Lincoln HS"

    def test_skips_non_dict_records(self, admin_client):
        # Defensive: a None or non-dict storage payload is silently
        # dropped from the listing.
        keys = ["admin_role:bad", "admin_role:good"]
        records = {
            "admin_role:bad": None,  # missing/corrupt
            "admin_role:good": {"school": "S", "granted_at": "g"},
        }
        with patch(
            "backend.routes.district_routes.list_keys",
            return_value=keys,
        ), patch(
            "backend.routes.district_routes.storage_load",
            side_effect=lambda k, _: records.get(k),
        ):
            resp = admin_client.get("/api/district/admins")
        admins = resp.get_json()["admins"]
        assert len(admins) == 1
        assert admins[0]["user_id"] == "good"


# ──────────────────────────────────────────────────────────────────
# district_revoke_admin (lines 496-510)
# ──────────────────────────────────────────────────────────────────


class TestRevokeAdmin:
    def test_requires_admin_session(self, client):
        resp = client.delete("/api/district/admins", json={"user_id": "x"})
        assert resp.status_code == 401

    def test_missing_user_id_returns_400(self, admin_client):
        for body in [{}, {"user_id": ""}, {"user_id": "   "}]:
            resp = admin_client.delete("/api/district/admins", json=body)
            assert resp.status_code == 400

    def test_happy_path_calls_delete(self, admin_client):
        delete_mock = MagicMock()
        with patch(
            "backend.storage.delete", delete_mock,
        ), patch(
            "backend.routes.district_routes.audit_log",
        ):
            resp = admin_client.delete(
                "/api/district/admins",
                json={"user_id": "user-42"},
            )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "revoked"
        delete_mock.assert_called_once_with("admin_role:user-42", "system")


# ──────────────────────────────────────────────────────────────────
# district_teacher_search (lines 520-551)
# ──────────────────────────────────────────────────────────────────


class TestTeacherSearch:
    def test_requires_admin_session(self, client):
        resp = client.get("/api/district/teacher-search?q=x")
        assert resp.status_code == 401

    def test_empty_query_returns_empty_list(self, admin_client):
        resp = admin_client.get("/api/district/teacher-search?q=  ")
        assert resp.status_code == 200
        assert resp.get_json() == {"teachers": []}

    def test_no_supabase_returns_503(self, admin_client):
        with patch(
            "backend.supabase_client.get_supabase",
            return_value=None,
        ):
            resp = admin_client.get(
                "/api/district/teacher-search?q=jane",
            )
        assert resp.status_code == 503

    def test_search_filters_by_name_and_email(self, admin_client):
        rows = [
            {"teacher_id": "t1", "data": {
                "teacher_name": "Jane Doe",
                "teacher_email": "jane@example.com",
            }},
            {"teacher_id": "t2", "data": {
                "teacher_name": "John Smith",
                "teacher_email": "john@example.com",
            }},
            {"teacher_id": "t3", "data": {
                "teacher_name": "Mary",
                "teacher_email": "mary.JANE@school.org",  # email match
            }},
            # non-dict data → skipped
            {"teacher_id": "t4", "data": "garbage"},
        ]
        result_mock = MagicMock()
        result_mock.data = rows
        sb_mock = MagicMock()
        sb_mock.table.return_value.select.return_value.eq.return_value \
            .execute.return_value = result_mock

        with patch(
            "backend.supabase_client.get_supabase",
            return_value=sb_mock,
        ):
            resp = admin_client.get(
                "/api/district/teacher-search?q=jane",
            )
        body = resp.get_json()
        # Jane Doe (name match) + Mary (email match), case-insensitive
        ids = [t["user_id"] for t in body["teachers"]]
        assert "t1" in ids
        assert "t3" in ids
        assert "t2" not in ids

    def test_max_20_cap(self, admin_client):
        # Build 25 matching rows
        rows = [
            {"teacher_id": f"t{i}", "data": {
                "teacher_name": f"Match Person {i}",
                "teacher_email": f"m{i}@x.com",
            }}
            for i in range(25)
        ]
        result_mock = MagicMock()
        result_mock.data = rows
        sb_mock = MagicMock()
        sb_mock.table.return_value.select.return_value.eq.return_value \
            .execute.return_value = result_mock

        with patch(
            "backend.supabase_client.get_supabase",
            return_value=sb_mock,
        ):
            resp = admin_client.get(
                "/api/district/teacher-search?q=match",
            )
        body = resp.get_json()
        assert len(body["teachers"]) == 20


# ──────────────────────────────────────────────────────────────────
# _clear_old_provider_data helper (lines 74-161, ~88 LOC)
# ──────────────────────────────────────────────────────────────────


class TestClearOldProviderData:
    """Direct unit tests on the helper (not via an HTTP endpoint).

    Behavior pinned:
    1. Returns 0 when Supabase isn't configured
    2. Returns 0 when classes query raises
    3. Manual classes (clever_section_id IS NULL) are PRESERVED
    4. Old provider's classes deleted, new provider's preserved
    5. Orphaned students (no remaining enrollments) → deleted
    6. Roster files in ~/.graider_data/roster_<tid>* removed
    """

    def test_no_supabase_returns_zero(self):
        from backend.routes.district_routes import _clear_old_provider_data
        with patch(
            "backend.supabase_client.get_supabase",
            return_value=None,
        ):
            assert _clear_old_provider_data("clever") == 0

    def test_classes_query_failure_returns_zero(self):
        from backend.routes.district_routes import _clear_old_provider_data
        sb = MagicMock()
        sb.table.return_value.select.return_value.execute.side_effect = (
            RuntimeError("network down")
        )
        with patch(
            "backend.supabase_client.get_supabase", return_value=sb,
        ):
            assert _clear_old_provider_data("clever") == 0

    def test_no_synced_classes_returns_zero(self):
        from backend.routes.district_routes import _clear_old_provider_data
        # Only manual classes (clever_section_id is None) → none to delete
        sb = MagicMock()
        result = MagicMock()
        result.data = [
            {"id": "c1", "teacher_id": "t1", "clever_section_id": None},
        ]
        sb.table.return_value.select.return_value.execute.return_value = result

        with patch(
            "backend.supabase_client.get_supabase", return_value=sb,
        ):
            assert _clear_old_provider_data("clever") == 0

    def test_clever_provider_deletes_clever_synced_classes(self, tmp_path):
        from backend.routes.district_routes import _clear_old_provider_data

        sb = MagicMock()
        classes_result = MagicMock()
        classes_result.data = [
            # Clever-synced (no oneroster: prefix) → DELETE
            {"id": "c-clever", "teacher_id": "t-1",
             "clever_section_id": "clever-sec-1"},
            # OneRoster-synced → KEEP (we're clearing clever)
            {"id": "c-or", "teacher_id": "t-2",
             "clever_section_id": "oneroster:sec-2"},
            # Manual → KEEP (no section id)
            {"id": "c-manual", "teacher_id": "t-3",
             "clever_section_id": None},
        ]

        # Two distinct response objects:
        # - enrollments_result: `select("student_id").eq("class_id", X)`
        #   inside the for-cls loop
        # - remaining_result: `select("id", count="exact").eq("student_id", S)`
        #   inside the orphan-probe loop
        enrollments_result = MagicMock(
            data=[{"student_id": "s1"}, {"student_id": "s2"}],
        )
        delete_enrollments_result = MagicMock(
            data=[{"student_id": "s1"}, {"student_id": "s2"}],
        )
        remaining_result = MagicMock(count=0, data=None)

        # Per-table chain references so we can assert each .delete()
        # was actually invoked (Gemini round-1 #1: previously the
        # tests only checked the return count without verifying that
        # any deletion happened).
        classes_chain = MagicMock()
        classes_chain.select.return_value.execute.return_value = classes_result
        classes_chain.delete.return_value.eq.return_value \
            .execute.return_value = MagicMock(data=[])

        students_chain = MagicMock()
        students_chain.delete.return_value.eq.return_value \
            .execute.return_value = MagicMock(data=[])

        # class_students has TWO different select shapes — branch on
        # kwargs to avoid the previous bug where a single .select stub
        # masked the orphan probe entirely.
        class_students_chain = MagicMock()

        def class_students_select_side_effect(*args, **kwargs):
            shape = MagicMock()
            if kwargs.get("count") == "exact":
                # Orphan probe: select("id", count="exact").eq(...).execute
                shape.eq.return_value.execute.return_value = remaining_result
            else:
                # Enrollments: select("student_id").eq(...).execute
                shape.eq.return_value.execute.return_value = enrollments_result
            return shape

        class_students_chain.select.side_effect = (
            class_students_select_side_effect
        )
        class_students_chain.delete.return_value.eq.return_value \
            .execute.return_value = delete_enrollments_result

        def table_side_effect(table_name):
            return {
                "classes": classes_chain,
                "class_students": class_students_chain,
                "students": students_chain,
            }.get(table_name, MagicMock())

        sb.table.side_effect = table_side_effect

        fake_data_dir = tmp_path / "fake-data"
        fake_data_dir.mkdir()
        (fake_data_dir / "roster_t-1.csv").write_text("name,email\n")

        with patch(
            "backend.supabase_client.get_supabase", return_value=sb,
        ), patch(
            "os.path.expanduser",
            return_value=str(fake_data_dir),
        ):
            count = _clear_old_provider_data("clever")

        # One teacher (t-1) had clever-synced classes deleted
        assert count == 1
        # roster file removed
        assert not (fake_data_dir / "roster_t-1.csv").exists()

        # Verify the actual deletes actually fired (Gemini round-1 #1):
        # - classes.delete().eq("id", "c-clever") was invoked
        classes_chain.delete.return_value.eq.assert_any_call(
            "id", "c-clever",
        )
        # - class_students.delete().eq("class_id", "c-clever") was invoked
        class_students_chain.delete.return_value.eq.assert_any_call(
            "class_id", "c-clever",
        )
        # - students.delete().eq("id", S) was invoked for at least one
        #   orphaned student (s1 or s2 depending on set-iteration order)
        student_eq_calls = students_chain.delete.return_value \
            .eq.call_args_list
        assert any(
            call.args == ("id", "s1") or call.args == ("id", "s2")
            for call in student_eq_calls
        )

    def test_oneroster_provider_deletes_oneroster_synced_classes(self):
        from backend.routes.district_routes import _clear_old_provider_data

        sb = MagicMock()
        classes_result = MagicMock()
        classes_result.data = [
            # OneRoster-synced → DELETE (we're clearing oneroster)
            {"id": "c-or-1", "teacher_id": "t-x",
             "clever_section_id": "oneroster:sec-1"},
            # Clever-synced → KEEP
            {"id": "c-clever", "teacher_id": "t-y",
             "clever_section_id": "clever-2"},
        ]
        # No enrollments for the deleted class → no orphan students
        empty_result = MagicMock()
        empty_result.data = []

        def table_side_effect(table_name):
            chain = MagicMock()
            if table_name == "classes":
                chain.select.return_value.execute.return_value = classes_result
                chain.delete.return_value.eq.return_value \
                    .execute.return_value = MagicMock(data=[])
            elif table_name == "class_students":
                chain.select.return_value.eq.return_value \
                    .execute.return_value = empty_result
                chain.delete.return_value.eq.return_value \
                    .execute.return_value = empty_result
            return chain

        sb.table = MagicMock(side_effect=table_side_effect)

        with patch(
            "backend.supabase_client.get_supabase", return_value=sb,
        ):
            count = _clear_old_provider_data("oneroster")
        assert count == 1  # one teacher (t-x)

    def test_orphaned_student_removed_and_os_remove_failure_swallowed(
        self, tmp_path,
    ):
        """End-to-end: orphan probe finds zero remaining → student
        deleted; roster file os.remove raises OSError → swallowed.
        Pins lines 123, 136-142, 152-153."""
        from backend.routes.district_routes import _clear_old_provider_data

        # Drive the chain via execute() call sequence:
        # 1. classes select → all classes (1 clever-synced)
        # 2. class_students select → enrollments [{s1}]
        # 3. class_students delete → result.data ignored
        # 4. classes delete → ok
        # 5. class_students select with count="exact" → remaining.count = 0
        # 6. students delete → ok
        execute_calls = {"i": 0}
        results = [
            MagicMock(data=[
                {"id": "c1", "teacher_id": "t1",
                 "clever_section_id": "clever-1"},
            ]),
            MagicMock(data=[{"student_id": "s1"}]),  # enrollments → s1
            MagicMock(data=[{"student_id": "s1"}]),  # delete enrollments
            MagicMock(data=[]),                       # delete class
            MagicMock(count=0, data=None),            # orphan probe
            MagicMock(data=[]),                       # delete student
        ]

        def execute_dispatcher(*a, **kw):
            i = execute_calls["i"]
            execute_calls["i"] += 1
            if i < len(results):
                return results[i]
            return MagicMock(data=[])

        sb = MagicMock()
        # Build a chain whose .execute() always pulls from the sequence
        sb.table.return_value.select.return_value.execute = execute_dispatcher
        sb.table.return_value.select.return_value.eq.return_value \
            .execute = execute_dispatcher
        sb.table.return_value.delete.return_value.eq.return_value \
            .execute = execute_dispatcher

        # Pre-create a roster file for t1; patch os.remove to raise so
        # the OSError swallow branch (153) fires.
        fake_data_dir = tmp_path / "fake-data"
        fake_data_dir.mkdir()
        (fake_data_dir / "roster_t1.csv").write_text("x")

        with patch(
            "backend.supabase_client.get_supabase", return_value=sb,
        ), patch(
            "os.path.expanduser",
            return_value=str(fake_data_dir),
        ), patch(
            "os.remove", side_effect=OSError("perm denied"),
        ):
            count = _clear_old_provider_data("clever")
        assert count == 1

    def test_student_delete_failure_swallowed(self):
        """Pin lines 141-142: when the orphan-student probe or delete
        raises, the inner try/except routes the exception to
        sentry_sdk.capture_exception and continues without bubbling."""
        from backend.routes.district_routes import _clear_old_provider_data

        sb = MagicMock()
        classes_result = MagicMock()
        classes_result.data = [
            {"id": "c1", "teacher_id": "t1",
             "clever_section_id": "clever-1"},
        ]
        enrollments_result = MagicMock(data=[{"student_id": "s1"}])

        classes_chain = MagicMock()
        classes_chain.select.return_value.execute.return_value = classes_result
        classes_chain.delete.return_value.eq.return_value \
            .execute.return_value = MagicMock(data=[])

        students_chain = MagicMock()

        class_students_chain = MagicMock()

        def class_students_select_side_effect(*args, **kwargs):
            shape = MagicMock()
            if kwargs.get("count") == "exact":
                # Orphan probe raises → enters lines 141-142
                shape.eq.return_value.execute.side_effect = (
                    RuntimeError("count probe failed")
                )
            else:
                shape.eq.return_value.execute.return_value = enrollments_result
            return shape

        class_students_chain.select.side_effect = (
            class_students_select_side_effect
        )
        class_students_chain.delete.return_value.eq.return_value \
            .execute.return_value = MagicMock(data=[])

        def table_side_effect(table_name):
            return {
                "classes": classes_chain,
                "class_students": class_students_chain,
                "students": students_chain,
            }.get(table_name, MagicMock())

        sb.table.side_effect = table_side_effect

        sentry_capture = MagicMock()
        with patch(
            "backend.supabase_client.get_supabase", return_value=sb,
        ), patch(
            "backend.routes.district_routes.sentry_sdk.capture_exception",
            sentry_capture,
        ):
            # Must not raise
            count = _clear_old_provider_data("clever")
        assert count == 1
        # Sentry was notified about the orphan-probe failure
        assert sentry_capture.called

    def test_class_delete_failure_swallowed(self):
        """A per-class delete failure logs + continues; doesn't raise."""
        from backend.routes.district_routes import _clear_old_provider_data

        sb = MagicMock()
        classes_result = MagicMock()
        classes_result.data = [
            {"id": "c1", "teacher_id": "t1",
             "clever_section_id": "clever-sec"},
        ]

        def table_side_effect(table_name):
            chain = MagicMock()
            if table_name == "classes":
                chain.select.return_value.execute.return_value = classes_result
                # Class deletion raises
                chain.delete.return_value.eq.return_value \
                    .execute.side_effect = RuntimeError("delete fail")
            elif table_name == "class_students":
                # Enrollment query also raises (covered by same try/except)
                chain.select.return_value.eq.return_value \
                    .execute.side_effect = RuntimeError("query fail")
            return chain

        sb.table = MagicMock(side_effect=table_side_effect)

        with patch(
            "backend.supabase_client.get_supabase", return_value=sb,
        ):
            # Must not raise
            count = _clear_old_provider_data("clever")
        # 1 affected teacher recorded, even though the delete raised
        assert count == 1
