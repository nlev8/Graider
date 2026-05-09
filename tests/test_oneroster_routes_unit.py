"""Unit tests for backend/routes/oneroster_routes.py.

Audit MAJOR #4 sprint follow-up to PR #284. Targets the 121 uncovered
LOC (36% baseline). Covers OneRoster config CRUD, connectivity test,
roster sync, accommodation application, teacher-id save, data delete,
and grade sync (8 endpoints).

Strategy
--------
Flask test_client + mocks for:
  * `get_oneroster_config` / `OneRosterClient` / `normalize_roster`
  * `sync_roster_to_db`, `delete_roster_data` (roster_sync helpers)
  * `ensure_line_item`, `post_results` (oneroster_gradebook async helpers)
  * `_run_async` is a thin wrapper around asyncio.new_event_loop —
    we patch the underlying coroutines/functions, not the wrapper.

`@require_teacher` bypassed via FLASK_ENV=development +
`X-Test-Teacher-Id` header (per the PR #283 pattern).
`limiter.reset()` in fixture.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock, AsyncMock

import pytest


@pytest.fixture
def client():
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
    return {"X-Test-Teacher-Id": "teach-1", "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def dev_env(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")


# ──────────────────────────────────────────────────────────────────
# GET /api/oneroster/config
# ──────────────────────────────────────────────────────────────────


class TestGetConfig:
    def test_unconfigured_returns_empty_status(self, client, auth_headers):
        with patch("backend.routes.oneroster_routes.get_oneroster_config",
                   return_value=None):
            resp = client.get("/api/oneroster/config", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["configured"] is False
        assert body["has_credentials"] is False
        # All empty/default fields present
        for k in ["base_url", "school_id", "teacher_sourced_id", "token_url"]:
            assert body[k] == ""

    def test_configured_returns_safe_fields_only(self, client, auth_headers):
        cfg = {
            "base_url": "https://sis.district.org/oneroster",
            "school_id": "school-1",
            "teacher_sourced_id": "teach-uuid-1",
            "token_url": "https://sis.district.org/token",
            "client_id": "ci",
            "client_secret": "sensitive-cs",  # MUST NOT be exposed
        }
        with patch("backend.routes.oneroster_routes.get_oneroster_config",
                   return_value=cfg):
            resp = client.get("/api/oneroster/config", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["configured"] is True
        assert body["has_credentials"] is True
        # Sensitive fields NOT exposed
        assert "client_id" not in body
        assert "client_secret" not in body
        # Safe fields ARE exposed
        assert body["base_url"] == cfg["base_url"]
        assert body["school_id"] == cfg["school_id"]

    def test_partial_credentials_reports_false(self, client, auth_headers):
        # Only client_id, no client_secret → has_credentials = False
        cfg = {
            "base_url": "https://sis.district.org",
            "client_id": "ci",
            "client_secret": "",
        }
        with patch("backend.routes.oneroster_routes.get_oneroster_config",
                   return_value=cfg):
            resp = client.get("/api/oneroster/config", headers=auth_headers)
        assert resp.get_json()["has_credentials"] is False


# ──────────────────────────────────────────────────────────────────
# POST /api/oneroster/config
# ──────────────────────────────────────────────────────────────────


class TestSaveConfig:
    def test_missing_required_fields_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/oneroster/config",
            json={"base_url": "https://x.com"},  # only one of 4 required
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "required" in resp.get_json()["error"]

    def test_happy_path_saves_and_audits(self, client, auth_headers):
        with patch("backend.storage.save") as mock_save, \
             patch("backend.utils.audit.audit_log") as mock_audit:
            resp = client.post(
                "/api/oneroster/config",
                json={
                    "base_url": "https://sis.district.org",
                    "client_id": "ci",
                    "client_secret": "cs",
                    "teacher_sourced_id": "teach-uuid",
                    "token_url": "https://sis.district.org/token",
                    "school_id": "school-1",
                },
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "saved"
        # storage.save called with key=oneroster_config
        mock_save.assert_called_once()
        key, payload, tid = mock_save.call_args.args
        assert key == "oneroster_config"
        assert payload["base_url"] == "https://sis.district.org"
        assert payload["client_secret"] == "cs"
        # Audit fired
        mock_audit.assert_called_once()

    def test_optional_fields_default_to_none(self, client, auth_headers):
        # token_url and school_id are optional — empty string → None
        with patch("backend.storage.save") as mock_save, \
             patch("backend.utils.audit.audit_log"):
            client.post(
                "/api/oneroster/config",
                json={
                    "base_url": "https://x.com",
                    "client_id": "c",
                    "client_secret": "s",
                    "teacher_sourced_id": "t",
                },
                headers=auth_headers,
            )
        payload = mock_save.call_args.args[1]
        assert payload["token_url"] is None
        assert payload["school_id"] is None


# ──────────────────────────────────────────────────────────────────
# POST /api/oneroster/test
# ──────────────────────────────────────────────────────────────────


class TestConnection:
    def test_unconfigured_returns_400(self, client, auth_headers):
        with patch("backend.routes.oneroster_routes.get_oneroster_config",
                   return_value=None):
            resp = client.post("/api/oneroster/test", headers=auth_headers)
        assert resp.status_code == 400

    def test_happy_path_returns_connected(self, client, auth_headers):
        cfg = {
            "base_url": "https://sis.district.org",
            "client_id": "ci", "client_secret": "cs",
            "token_url": "https://sis.district.org/token",
        }
        # Patch _run_async to just return the result of awaiting the coro
        with patch("backend.routes.oneroster_routes.get_oneroster_config",
                   return_value=cfg), \
             patch("backend.routes.oneroster_routes.OneRosterClient") as MockClient, \
             patch("backend.routes.oneroster_routes._run_async",
                   return_value={"data": []}):
            resp = client.post("/api/oneroster/test", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "connected"

    def test_connection_failure_returns_502(self, client, auth_headers):
        cfg = {"base_url": "https://x.com", "client_id": "c", "client_secret": "s"}
        with patch("backend.routes.oneroster_routes.get_oneroster_config",
                   return_value=cfg), \
             patch("backend.routes.oneroster_routes.OneRosterClient"), \
             patch("backend.routes.oneroster_routes._run_async",
                   side_effect=ConnectionError("network")):
            resp = client.post("/api/oneroster/test", headers=auth_headers)
        assert resp.status_code == 502
        assert "Connection failed" in resp.get_json()["error"]


# ──────────────────────────────────────────────────────────────────
# POST /api/oneroster/sync-roster
# ──────────────────────────────────────────────────────────────────


class TestSyncRoster:
    def test_provider_switch_in_progress_blocks_503(self, client, auth_headers):
        # Lock is recent (well under 5min TTL)
        import time
        with patch("backend.storage.load") as mock_load, \
             patch("backend.storage.save"):
            mock_load.return_value = {"timestamp": time.time() - 10}
            resp = client.post(
                "/api/oneroster/sync-roster",
                headers=auth_headers,
            )
        assert resp.status_code == 503
        assert "provider switch" in resp.get_json()["error"]

    def test_stale_lock_clears_and_proceeds(self, client, auth_headers):
        import time
        # Lock is >5min old → cleared, sync proceeds (then fails on no config)
        with patch("backend.storage.load") as mock_load, \
             patch("backend.storage.save"), \
             patch("backend.routes.oneroster_routes.get_oneroster_config",
                   return_value=None):
            mock_load.return_value = {"timestamp": time.time() - 600}  # 10 min old
            resp = client.post(
                "/api/oneroster/sync-roster",
                headers=auth_headers,
            )
        # Lock was cleared, then "not configured" path
        assert resp.status_code == 400
        assert "not configured" in resp.get_json()["error"]

    def test_unconfigured_returns_400(self, client, auth_headers):
        with patch("backend.storage.load", return_value=None), \
             patch("backend.routes.oneroster_routes.get_oneroster_config",
                   return_value=None):
            resp = client.post(
                "/api/oneroster/sync-roster",
                headers=auth_headers,
            )
        assert resp.status_code == 400

    def test_fetch_failure_returns_502(self, client, auth_headers):
        cfg = {"base_url": "https://x.com", "client_id": "c", "client_secret": "s"}
        with patch("backend.storage.load", return_value=None), \
             patch("backend.routes.oneroster_routes.get_oneroster_config",
                   return_value=cfg), \
             patch("backend.routes.oneroster_routes.OneRosterClient"), \
             patch("backend.routes.oneroster_routes._run_async",
                   side_effect=ConnectionError("api down")):
            resp = client.post(
                "/api/oneroster/sync-roster",
                headers=auth_headers,
            )
        assert resp.status_code == 502
        assert "Failed to fetch" in resp.get_json()["error"]

    def test_happy_path_returns_synced_with_counts(self, client, auth_headers):
        cfg = {"base_url": "https://x.com", "client_id": "c", "client_secret": "s"}
        raw = {"users": [], "classes": [], "enrollments": []}
        classes = [{"external_id": "oneroster:c1", "name": "Math 101"}]
        students = [
            {"external_id": "oneroster:s1", "first_name": "Alice",
             "last_name": "Smith", "email": "alice@x.com"},
        ]
        enrollments = [
            {"class_external_id": "oneroster:c1",
             "student_external_id": "oneroster:s1"},
        ]
        accommodations = [
            {"student_external_id": "oneroster:s1",
             "iep_status": "active", "ell_status": None,
             "home_language": "English"},
        ]

        with patch("backend.storage.load", return_value=None), \
             patch("backend.routes.oneroster_routes.get_oneroster_config",
                   return_value=cfg), \
             patch("backend.routes.oneroster_routes.OneRosterClient"), \
             patch("backend.routes.oneroster_routes._run_async",
                   return_value=raw), \
             patch("backend.routes.oneroster_routes.normalize_roster",
                   return_value=(classes, students, enrollments, accommodations)), \
             patch("backend.routes.oneroster_routes.sync_roster_to_db",
                   return_value={"classes": 1, "students": 1, "enrollments": 1}), \
             patch("backend.clever.persist_roster_as_csv"), \
             patch("backend.clever.persist_sections_as_periods"), \
             patch("backend.utils.audit.audit_log"):
            resp = client.post(
                "/api/oneroster/sync-roster",
                headers=auth_headers,
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "synced"
        assert body["counts"]["classes"] == 1
        # IEP suggestions built per accommodation
        assert "oneroster:s1" in body["accommodation_suggestions"]
        assert "modified_expectations" in body[
            "accommodation_suggestions"]["oneroster:s1"]["suggested_presets"]

    def test_ell_only_accommodation_emits_ell_presets(
        self, client, auth_headers,
    ):
        cfg = {"base_url": "https://x.com", "client_id": "c", "client_secret": "s"}
        with patch("backend.storage.load", return_value=None), \
             patch("backend.routes.oneroster_routes.get_oneroster_config",
                   return_value=cfg), \
             patch("backend.routes.oneroster_routes.OneRosterClient"), \
             patch("backend.routes.oneroster_routes._run_async",
                   return_value={}), \
             patch("backend.routes.oneroster_routes.normalize_roster",
                   return_value=(
                       [], [], [],
                       [{"student_external_id": "s2",
                         "iep_status": None, "ell_status": "active",
                         "home_language": "Spanish"}],
                   )), \
             patch("backend.routes.oneroster_routes.sync_roster_to_db",
                   return_value={"classes": 0, "students": 0, "enrollments": 0}), \
             patch("backend.clever.persist_roster_as_csv"), \
             patch("backend.clever.persist_sections_as_periods"), \
             patch("backend.utils.audit.audit_log"):
            resp = client.post(
                "/api/oneroster/sync-roster",
                headers=auth_headers,
            )
        body = resp.get_json()
        suggestions = body["accommodation_suggestions"]["s2"]["suggested_presets"]
        assert "ell_support" in suggestions
        assert "simplified_language" in suggestions

    def test_no_iep_no_ell_omits_from_suggestions(self, client, auth_headers):
        cfg = {"base_url": "https://x.com", "client_id": "c", "client_secret": "s"}
        with patch("backend.storage.load", return_value=None), \
             patch("backend.routes.oneroster_routes.get_oneroster_config",
                   return_value=cfg), \
             patch("backend.routes.oneroster_routes.OneRosterClient"), \
             patch("backend.routes.oneroster_routes._run_async",
                   return_value={}), \
             patch("backend.routes.oneroster_routes.normalize_roster",
                   return_value=(
                       [], [], [],
                       [{"student_external_id": "s3",
                         "iep_status": None, "ell_status": None}],
                   )), \
             patch("backend.routes.oneroster_routes.sync_roster_to_db",
                   return_value={"classes": 0, "students": 0, "enrollments": 0}), \
             patch("backend.clever.persist_roster_as_csv"), \
             patch("backend.clever.persist_sections_as_periods"), \
             patch("backend.utils.audit.audit_log"):
            resp = client.post(
                "/api/oneroster/sync-roster",
                headers=auth_headers,
            )
        body = resp.get_json()
        assert body["accommodation_suggestions"] == {}


# ──────────────────────────────────────────────────────────────────
# POST /api/oneroster/apply-accommodations
# ──────────────────────────────────────────────────────────────────


class TestApplyAccommodations:
    def test_empty_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/oneroster/apply-accommodations",
            json={"accommodations": {}},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_missing_field_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/oneroster/apply-accommodations",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_happy_path_applies_each_student(self, client, auth_headers):
        with patch("backend.accommodations.set_student_accommodation") as mock_set:
            resp = client.post(
                "/api/oneroster/apply-accommodations",
                json={
                    "accommodations": {
                        "s1": {
                            "presets": ["modified_expectations"],
                            "notes": "IEP",
                            "name": "Alice",
                        },
                        "s2": {
                            "presets": ["ell_support"],
                            "notes": "ELL",
                            "name": "Bob",
                        },
                    },
                },
                headers=auth_headers,
            )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "applied"
        assert body["count"] == 2
        # Each student got set_student_accommodation
        assert mock_set.call_count == 2


# ──────────────────────────────────────────────────────────────────
# POST /api/oneroster/teacher-id
# ──────────────────────────────────────────────────────────────────


class TestSaveTeacherId:
    def test_missing_id_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/oneroster/teacher-id",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_happy_path_saves(self, client, auth_headers):
        with patch("backend.storage.save") as mock_save:
            resp = client.post(
                "/api/oneroster/teacher-id",
                json={"teacher_sourced_id": "teach-uuid-1"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        # Saved under oneroster_teacher_id key
        mock_save.assert_called_once()
        key, payload, tid = mock_save.call_args.args
        assert key == "oneroster_teacher_id"
        assert payload["teacher_sourced_id"] == "teach-uuid-1"


# ──────────────────────────────────────────────────────────────────
# POST /api/oneroster/delete-data
# ──────────────────────────────────────────────────────────────────


class TestDeleteData:
    def test_deletes_and_audits(self, client, auth_headers):
        with patch("backend.roster_sync.delete_roster_data",
                   return_value={"classes": 5, "students": 30}) as mock_del, \
             patch("backend.storage.save") as mock_save, \
             patch("backend.utils.audit.audit_log") as mock_audit:
            resp = client.post(
                "/api/oneroster/delete-data",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "deleted"
        assert body["counts"]["classes"] == 5
        # Roster data deleted + config cleared
        mock_del.assert_called_once_with("teach-1")
        # save called to clear config
        save_calls = mock_save.call_args_list
        assert any(
            c.args[0] == "oneroster_config" and c.args[1] is None
            for c in save_calls
        )
        # Audit fired
        mock_audit.assert_called_once()


# ──────────────────────────────────────────────────────────────────
# POST /api/oneroster/sync-grades
# ──────────────────────────────────────────────────────────────────


class TestSyncGrades:
    def test_unconfigured_returns_400(self, client, auth_headers):
        with patch("backend.routes.oneroster_routes.get_oneroster_config",
                   return_value=None):
            resp = client.post(
                "/api/oneroster/sync-grades",
                json={
                    "assessment_id": "a1",
                    "title": "Q1",
                    "total_points": 100,
                    "class_sourced_id": "c1",
                    "scores": [{"student_id": "s1", "score": 80}],
                },
                headers=auth_headers,
            )
        assert resp.status_code == 400
        assert "not configured" in resp.get_json()["error"]

    def test_no_base_url_returns_400(self, client, auth_headers):
        # Config exists but base_url is empty
        with patch("backend.routes.oneroster_routes.get_oneroster_config",
                   return_value={"base_url": ""}):
            resp = client.post(
                "/api/oneroster/sync-grades",
                json={
                    "assessment_id": "a", "title": "T",
                    "total_points": 100, "class_sourced_id": "c",
                    "scores": [{}],
                },
                headers=auth_headers,
            )
        assert resp.status_code == 400

    def test_missing_required_fields_returns_400(self, client, auth_headers):
        cfg = {"base_url": "https://x.com", "client_id": "c", "client_secret": "s"}
        with patch("backend.routes.oneroster_routes.get_oneroster_config",
                   return_value=cfg):
            resp = client.post(
                "/api/oneroster/sync-grades",
                json={"assessment_id": "a"},
                headers=auth_headers,
            )
        assert resp.status_code == 400
        assert "Missing required fields" in resp.get_json()["error"]

    def test_no_scores_returns_400(self, client, auth_headers):
        cfg = {"base_url": "https://x.com", "client_id": "c", "client_secret": "s"}
        with patch("backend.routes.oneroster_routes.get_oneroster_config",
                   return_value=cfg):
            resp = client.post(
                "/api/oneroster/sync-grades",
                json={
                    "assessment_id": "a", "title": "T",
                    "total_points": 100, "class_sourced_id": "c",
                    "scores": [],
                },
                headers=auth_headers,
            )
        assert resp.status_code == 400
        assert "No scores" in resp.get_json()["error"]

    def test_lineitem_creation_failure_returns_500(self, client, auth_headers):
        cfg = {"base_url": "https://x.com", "client_id": "c", "client_secret": "s"}
        with patch("backend.routes.oneroster_routes.get_oneroster_config",
                   return_value=cfg), \
             patch("backend.routes.oneroster_routes.OneRosterClient"), \
             patch("backend.routes.oneroster_routes._run_async",
                   side_effect=RuntimeError("API down")):
            resp = client.post(
                "/api/oneroster/sync-grades",
                json={
                    "assessment_id": "a", "title": "T",
                    "total_points": 100, "class_sourced_id": "c",
                    "scores": [{"student_id": "s1", "score": 80}],
                },
                headers=auth_headers,
            )
        assert resp.status_code == 500
        assert "Failed to create assignment" in resp.get_json()["error"]

    def test_post_results_failure_returns_500(self, client, auth_headers):
        cfg = {"base_url": "https://x.com", "client_id": "c", "client_secret": "s"}
        # First _run_async (ensure_line_item) succeeds, second (post_results) fails
        with patch("backend.routes.oneroster_routes.get_oneroster_config",
                   return_value=cfg), \
             patch("backend.routes.oneroster_routes.OneRosterClient"), \
             patch("backend.routes.oneroster_routes._run_async",
                   side_effect=["lineitem-id-1", RuntimeError("score post failed")]):
            resp = client.post(
                "/api/oneroster/sync-grades",
                json={
                    "assessment_id": "a", "title": "T",
                    "total_points": 100, "class_sourced_id": "c",
                    "scores": [{"student_id": "s1", "score": 80}],
                },
                headers=auth_headers,
            )
        assert resp.status_code == 500
        assert "Failed to post scores" in resp.get_json()["error"]

    def test_happy_path_returns_synced_counts(self, client, auth_headers):
        cfg = {"base_url": "https://x.com", "client_id": "c", "client_secret": "s"}
        with patch("backend.routes.oneroster_routes.get_oneroster_config",
                   return_value=cfg), \
             patch("backend.routes.oneroster_routes.OneRosterClient"), \
             patch("backend.routes.oneroster_routes._run_async",
                   side_effect=[
                       "lineitem-1",  # ensure_line_item
                       {"synced": 5, "skipped": 1, "failed": 0, "errors": []},
                   ]):
            resp = client.post(
                "/api/oneroster/sync-grades",
                json={
                    "assessment_id": "a1", "title": "Quiz 1",
                    "total_points": 100, "class_sourced_id": "c1",
                    "scores": [
                        {"student_id": "s1", "score": 85},
                        {"student_id": "s2", "score": 90},
                    ],
                },
                headers=auth_headers,
            )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "success"
        assert body["line_item_id"] == "lineitem-1"
        assert body["synced"] == 5


# ──────────────────────────────────────────────────────────────────
# _run_async helper
# ──────────────────────────────────────────────────────────────────


class TestRunAsync:
    def test_runs_coroutine_and_returns_result(self):
        # Direct test of the helper
        from backend.routes.oneroster_routes import _run_async

        async def coro():
            return {"data": [1, 2, 3]}

        result = _run_async(coro())
        assert result == {"data": [1, 2, 3]}

    def test_propagates_exception(self):
        from backend.routes.oneroster_routes import _run_async

        async def coro():
            raise ValueError("oops")

        with pytest.raises(ValueError, match="oops"):
            _run_async(coro())
