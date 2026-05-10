"""Gap-fill tests for backend/routes/oneroster_routes.py.

Audit MAJOR #4 sprint follow-up to PR #329. Companion to existing
`tests/test_oneroster_routes_unit.py`. Targets the 12 missing LOC
(93.6% baseline → 99%+ goal):

* `/test` endpoint async _test() body — token + roster preflight
  (lines 117-120)
* `/sync-roster` provider-switch lock-load exception swallow
  (lines 158-159)
* `/sync-roster` persist_roster_as_csv exception swallow + sentry
  (lines 205-207)
* `/sync-roster` persist_sections_as_periods exception swallow +
  sentry (lines 220-222)

Per dual-rate-limit precedent: test-only PR merging on green CI.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock, AsyncMock

import pytest


MODULE = "backend.routes.oneroster_routes"


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
# /test endpoint — async _test() inner body
# ──────────────────────────────────────────────────────────────────


class TestConnectionTest:
    def test_connection_test_happy_path(self, client, auth_headers):
        # Lines 117-120: the inner `async def _test()` body executes
        # _ensure_token + _get_with_retry. We mock the OneRosterClient
        # constructor so its instance methods become async mocks.
        cfg = {
            "base_url": "https://sis.example.org/oneroster",
            "client_id": "ci",
            "client_secret": "cs",
            "token_url": "https://sis.example.org/token",
        }
        mock_client = MagicMock()
        mock_client.base_url = "https://sis.example.org/oneroster"
        mock_client._ensure_token = AsyncMock()
        mock_client._get_with_retry = AsyncMock(
            return_value={"classes": [{"sourcedId": "c1"}]}
        )

        with patch(f"{MODULE}.get_oneroster_config", return_value=cfg), \
             patch(f"{MODULE}.OneRosterClient",
                   return_value=mock_client):
            resp = client.post("/api/oneroster/test", headers=auth_headers)

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "connected"

    def test_connection_test_failure_returns_502(self, client, auth_headers):
        # Existing test_oneroster_routes_unit.py covers this, but
        # adding for completeness across both client setup and
        # _run_async inner exception
        cfg = {
            "base_url": "https://sis.example.org/oneroster",
            "client_id": "ci",
            "client_secret": "cs",
        }
        mock_client = MagicMock()
        mock_client._ensure_token = AsyncMock(
            side_effect=RuntimeError("auth failed"),
        )

        with patch(f"{MODULE}.get_oneroster_config", return_value=cfg), \
             patch(f"{MODULE}.OneRosterClient",
                   return_value=mock_client):
            resp = client.post("/api/oneroster/test", headers=auth_headers)

        assert resp.status_code == 502
        assert "Connection failed" in resp.get_json()["error"]


# ──────────────────────────────────────────────────────────────────
# /sync-roster provider-switch lock-load exception (lines 158-159)
# ──────────────────────────────────────────────────────────────────


class TestSyncRosterLockLoadException:
    def test_storage_load_exception_swallowed_continues_sync(
        self, client, auth_headers,
    ):
        # Force the provider-switch-lock load to raise → exception
        # swallowed via sentry, sync proceeds normally
        cfg = {
            "base_url": "https://sis.example.org/oneroster",
            "client_id": "ci",
            "client_secret": "cs",
            "school_id": "school-1",
        }
        # Mock OneRoster client + normalize_roster
        mock_client_instance = MagicMock()
        mock_client_instance.fetch_roster = AsyncMock(
            return_value={"classes": [], "students": [],
                          "enrollments": []}
        )

        with patch("backend.storage.load",
                   side_effect=RuntimeError("storage broke")), \
             patch(f"{MODULE}.sentry_sdk.capture_exception") as mock_sentry, \
             patch(f"{MODULE}.get_oneroster_config", return_value=cfg), \
             patch(f"{MODULE}.OneRosterClient",
                   return_value=mock_client_instance), \
             patch(f"{MODULE}.normalize_roster",
                   return_value=([], [], [], [])), \
             patch(f"{MODULE}.sync_roster_to_db",
                   return_value={"classes": 0, "students": 0,
                                 "enrollments": 0}), \
             patch("backend.clever.persist_roster_as_csv"), \
             patch("backend.clever.persist_sections_as_periods"):
            resp = client.post("/api/oneroster/sync-roster",
                               headers=auth_headers)

        # Sync still succeeded despite storage exception
        assert resp.status_code == 200
        # Sentry was called for the storage exception
        mock_sentry.assert_called()


# ──────────────────────────────────────────────────────────────────
# /sync-roster persist_roster_as_csv + persist_sections_as_periods
# exception swallow (205-207, 220-222)
# ──────────────────────────────────────────────────────────────────


class TestSyncRosterPersistExceptions:
    def test_persist_roster_as_csv_exception_swallowed(
        self, client, auth_headers,
    ):
        cfg = {
            "base_url": "https://sis.example.org/oneroster",
            "client_id": "ci",
            "client_secret": "cs",
            "school_id": "school-1",
        }
        mock_client_instance = MagicMock()
        mock_client_instance.fetch_roster = AsyncMock(
            return_value={"students": [{"sourcedId": "s1"}],
                          "classes": [], "enrollments": []}
        )

        with patch(f"{MODULE}.get_oneroster_config", return_value=cfg), \
             patch(f"{MODULE}.OneRosterClient",
                   return_value=mock_client_instance), \
             patch(f"{MODULE}.normalize_roster",
                   return_value=(
                       [],  # classes
                       [{"first_name": "A", "last_name": "B",
                         "external_id": "oneroster:s1",
                         "email": "a@b.com"}],  # students
                       [],  # enrollments
                       [],  # accommodations
                   )), \
             patch(f"{MODULE}.sync_roster_to_db",
                   return_value={"classes": 0, "students": 1,
                                 "enrollments": 0}), \
             patch("backend.clever.persist_roster_as_csv",
                   side_effect=RuntimeError("csv write failed")), \
             patch("backend.clever.persist_sections_as_periods"), \
             patch(f"{MODULE}.sentry_sdk.capture_exception") as mock_sentry:
            resp = client.post("/api/oneroster/sync-roster",
                               headers=auth_headers)

        # Sync still succeeds; exception swallowed
        assert resp.status_code == 200
        # Sentry alerted
        mock_sentry.assert_called()

    def test_persist_sections_as_periods_exception_swallowed(
        self, client, auth_headers,
    ):
        cfg = {
            "base_url": "https://sis.example.org/oneroster",
            "client_id": "ci",
            "client_secret": "cs",
            "school_id": "school-1",
        }
        mock_client_instance = MagicMock()
        mock_client_instance.fetch_roster = AsyncMock(
            return_value={"classes": [{"sourcedId": "c1"}],
                          "students": [], "enrollments": []}
        )

        with patch(f"{MODULE}.get_oneroster_config", return_value=cfg), \
             patch(f"{MODULE}.OneRosterClient",
                   return_value=mock_client_instance), \
             patch(f"{MODULE}.normalize_roster",
                   return_value=(
                       [{"name": "Class 1",
                         "external_id": "oneroster:c1",
                         "subject": "Math", "grade_level": "7"}],
                       [], [], [],
                   )), \
             patch(f"{MODULE}.sync_roster_to_db",
                   return_value={"classes": 1, "students": 0,
                                 "enrollments": 0}), \
             patch("backend.clever.persist_roster_as_csv"), \
             patch("backend.clever.persist_sections_as_periods",
                   side_effect=RuntimeError("periods write failed")), \
             patch(f"{MODULE}.sentry_sdk.capture_exception") as mock_sentry:
            resp = client.post("/api/oneroster/sync-roster",
                               headers=auth_headers)

        # Sync still succeeds; exception swallowed
        assert resp.status_code == 200
        mock_sentry.assert_called()
