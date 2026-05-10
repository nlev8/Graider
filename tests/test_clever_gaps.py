"""Gap-fill tests for backend/clever.py.

Audit MAJOR #4 sprint follow-up to PR #330. Companion to existing
`tests/test_clever.py` and `tests/test_clever_callback.py`. Targets
the 14 missing LOC (95.6% baseline → 99%+ goal):

* `get_clever_user`: user-fetch non-200 status (lines 144-145)
* `sync_roster` async: sections HTTP non-200 break (237),
  sections HTTPError exception swallow + sentry (241-244),
  contacts HTTP non-200 break (252)
* `persist_roster_as_csv`: archive corrupt JSON fallback (373-374),
  overrides corrupt JSON fallback (418-419)
* `persist_parent_contacts`: existing contacts corrupt JSON
  fallback (559-560)

Per dual-rate-limit precedent: test-only PR merging on green CI.
"""
from __future__ import annotations

import asyncio
import csv
import json
import os
from unittest.mock import patch, MagicMock, AsyncMock

import httpx
import pytest


MODULE = "backend.clever"


# ──────────────────────────────────────────────────────────────────
# get_clever_user user-fetch non-200
# ──────────────────────────────────────────────────────────────────


class TestGetCleverUserFailure:
    def test_user_fetch_non_200_returns_none(self):
        # /me succeeds but /users/<id> returns 500 → return None
        from backend.clever import get_clever_user

        # First response: /me OK
        me_resp = MagicMock()
        me_resp.status_code = 200
        me_resp.json.return_value = {"data": {"id": "u1", "type": "teacher"}}

        # Second response: /users/u1 fails
        user_resp = MagicMock()
        user_resp.status_code = 500

        async def fake_get(url, **_):
            if url.endswith("/me"):
                return me_resp
            return user_resp

        async_client = MagicMock()
        async_client.get = fake_get
        async_client.__aenter__ = AsyncMock(return_value=async_client)
        async_client.__aexit__ = AsyncMock(return_value=None)

        with patch(f"{MODULE}.httpx.AsyncClient",
                   return_value=async_client):
            result = asyncio.run(get_clever_user("token"))
        assert result is None


# ──────────────────────────────────────────────────────────────────
# sync_roster sections + contacts edges
# ──────────────────────────────────────────────────────────────────


class TestFetchRosterErrors:
    def test_sections_non_200_breaks_loop(self):
        # Build a sync_roster scenario where teachers + students
        # succeed, but sections returns non-200 → loop breaks, no items
        from backend.clever import sync_roster

        async def fake_get(client, url, headers, label=""):
            resp = MagicMock()
            if "teachers" in url or "students" in url:
                resp.status_code = 200
                resp.json.return_value = {"data": []}
                return resp
            if "sections" in url or "users?role=contact" in url:
                resp.status_code = 503  # non-200 → break
                resp.json.return_value = {}
                return resp
            resp.status_code = 200
            resp.json.return_value = {"data": []}
            return resp

        with patch(f"{MODULE}._clever_get_with_retry",
                   side_effect=fake_get), \
             patch(f"{MODULE}._next_page_url", return_value=None):
            result = asyncio.run(sync_roster("token"))
        # Sections list empty due to non-200 break
        assert result["sections"] == []

    def test_sections_httperror_swallowed(self):
        from backend.clever import sync_roster

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"data": []}

        async def fake_get(client, url, headers, label=""):
            if "sections" in url or "users?role=contact" in url:
                raise httpx.HTTPError("network down")
            return ok_resp

        with patch(f"{MODULE}._clever_get_with_retry",
                   side_effect=fake_get), \
             patch(f"{MODULE}._next_page_url", return_value=None), \
             patch(f"{MODULE}.sentry_sdk.capture_exception") as mock_sentry:
            result = asyncio.run(sync_roster("token"))
        # Sections empty (loop exited via except → break)
        assert result["sections"] == []
        # Sentry capture invoked at least once (sections + contacts)
        mock_sentry.assert_called()


# ──────────────────────────────────────────────────────────────────
# persist_roster_as_csv corrupt-JSON fallbacks
# ──────────────────────────────────────────────────────────────────


class TestPersistRosterCorruptJson:
    def test_corrupt_archive_falls_back_to_empty(
        self, tmp_path, monkeypatch,
    ):
        # archive_path file exists but contains corrupt JSON →
        # archived = {} fallback (lines 373-374)
        from backend.clever import persist_roster_as_csv
        from backend import clever as mod

        monkeypatch.setattr(mod, "ROSTERS_DIR", str(tmp_path))

        safe_id = "test-teacher"
        archive_path = tmp_path / f"clever_roster_{safe_id}_archived.json"
        archive_path.write_text("{not valid json")

        students = [
            {"data": {
                "id": "s1",
                "name": {"first": "Alice", "last": "Smith"},
                "email": "a@b.com",
            }}
        ]
        # Should not raise — corrupt archive triggers fallback to {}
        persist_roster_as_csv(students, "test-teacher")

        # Verify CSV was created at expected path
        csv_path = tmp_path / f"clever_roster_{safe_id}.csv"
        assert csv_path.exists()

    def test_corrupt_overrides_falls_back_to_empty(
        self, tmp_path, monkeypatch,
    ):
        # overrides file exists but corrupt → overrides = {} fallback
        # (lines 418-419)
        from backend.clever import persist_roster_as_csv
        from backend import clever as mod

        monkeypatch.setattr(mod, "ROSTERS_DIR", str(tmp_path))

        safe_id = "test-teacher"
        overrides_path = tmp_path / f"clever_roster_{safe_id}_overrides.json"
        overrides_path.write_text("{not valid json")

        students = [
            {"data": {
                "id": "s1",
                "name": {"first": "Bob", "last": "Jones"},
                "email": "b@c.com",
            }}
        ]
        persist_roster_as_csv(students, "test-teacher")

        # CSV created
        csv_path = tmp_path / f"clever_roster_{safe_id}.csv"
        assert csv_path.exists()

    def test_no_archive_or_overrides_files_works(
        self, tmp_path, monkeypatch,
    ):
        # No archive or overrides files → both branches default to {}
        from backend.clever import persist_roster_as_csv
        from backend import clever as mod

        monkeypatch.setattr(mod, "ROSTERS_DIR", str(tmp_path))

        students = [
            {"data": {
                "id": "s1",
                "name": {"first": "Carol", "last": "Davis"},
                "email": "c@d.com",
            }}
        ]
        persist_roster_as_csv(students, "test-teacher")

        csv_path = tmp_path / "clever_roster_test-teacher.csv"
        assert csv_path.exists()


# ──────────────────────────────────────────────────────────────────
# persist_parent_contacts corrupt-JSON fallback
# ──────────────────────────────────────────────────────────────────


class TestPersistParentContactsCorruptJson:
    def test_corrupt_existing_contacts_falls_back_to_empty(
        self, tmp_path, monkeypatch,
    ):
        # existing contacts file is corrupt JSON → existing = {}
        # fallback (lines 559-560)
        from backend.clever import persist_parent_contacts
        from backend import clever as mod

        contacts_dir = tmp_path / "contacts"
        contacts_dir.mkdir()
        monkeypatch.setattr(mod, "GRAIDER_DATA_DIR", str(tmp_path))
        # The contacts dir is created via os.makedirs inside the function

        safe_id = "test-teacher"
        contacts_file = (
            tmp_path / "contacts" / f"parent_contacts_{safe_id}.json"
        )
        contacts_file.parent.mkdir(parents=True, exist_ok=True)
        contacts_file.write_text("{not valid json")

        contact_map = {
            "s1": {
                "parent_emails": ["mom@example.com"],
                "parent_phones": ["555-0100"],
            }
        }
        persist_parent_contacts(contact_map, "test-teacher")

        # File was rewritten with valid JSON (the corrupt JSON was
        # swallowed → existing={} fallback → contact_map merged in)
        loaded = json.loads(contacts_file.read_text())
        assert "s1" in loaded
        assert "mom@example.com" in loaded["s1"]["parent_emails"]
