"""Unit tests for backend/routes/lesson_routes.py.

Audit MAJOR #4 sprint follow-up to PR #287. Targets the 314 uncovered
LOC (22% baseline). Module has 16 endpoints across three sections:

* Lesson plan CRUD (5)
  - POST   /api/save-lesson
  - GET    /api/list-lessons
  - GET    /api/load-lesson
  - DELETE /api/delete-lesson
  - GET    /api/list-units
* Teaching calendar (8)
  - GET    /api/calendar
  - PUT    /api/calendar/schedule
  - DELETE /api/calendar/schedule/<id>
  - POST   /api/calendar/holiday
  - DELETE /api/calendar/holiday
  - PUT    /api/calendar/school-days
  - POST   /api/calendar/parse-document
  - POST   /api/calendar/import-events
* Resources / Assets (4)
  - POST /api/save-resource
  - GET  /api/list-resources
  - POST /api/load-resource
  - POST /api/delete-resource

Also exercises 2 helpers (_safe_filename, _load_calendar/_save_calendar
indirectly).

Strategy
--------
Flask test_client + storage-layer patching. Module-level paths
(LESSONS_DIR, GRAIDER_DATA_DIR, CALENDAR_FILE, DOCUMENTS_DIR) are
monkeypatched to `tmp_path` per test. Two storage modes covered:
storage_save/load/list_keys/delete patched as MagicMock for the
"storage available" path, and patched to None for the "filesystem
fallback" path.

Auth: FLASK_ENV=development + X-Test-Teacher-Id header.
limiter.reset() in fixture (Flask-Limiter is module-level).
"""
from __future__ import annotations

import io
import json
import os
from unittest.mock import patch, MagicMock

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


@pytest.fixture
def tmp_lesson_dirs(monkeypatch, tmp_path):
    """Redirect all module-level filesystem paths into tmp_path so tests
    can write/read freely without touching the real ~/.graider_lessons
    or ~/.graider_data."""
    lessons = tmp_path / "lessons"
    data = tmp_path / "data"
    documents = data / "documents"
    calendar_file = data / "teaching_calendar.json"

    monkeypatch.setattr(
        "backend.routes.lesson_routes.LESSONS_DIR", str(lessons),
    )
    monkeypatch.setattr(
        "backend.routes.lesson_routes.GRAIDER_DATA_DIR", str(data),
    )
    monkeypatch.setattr(
        "backend.routes.lesson_routes.DOCUMENTS_DIR", str(documents),
    )
    monkeypatch.setattr(
        "backend.routes.lesson_routes.CALENDAR_FILE", str(calendar_file),
    )

    return {
        "lessons": lessons,
        "data": data,
        "documents": documents,
        "calendar_file": calendar_file,
    }


# ──────────────────────────────────────────────────────────────────
# /api/save-lesson
# ──────────────────────────────────────────────────────────────────


class TestSaveLesson:
    def test_storage_path_writes_via_storage_save(
        self, client, auth_headers,
    ):
        sentinel = MagicMock()
        with patch(
            "backend.routes.lesson_routes.storage_save", sentinel,
        ):
            resp = client.post(
                "/api/save-lesson",
                data=json.dumps({
                    "lesson": {"title": "Photosynthesis"},
                    "unitName": "Biology",
                }),
                headers=auth_headers,
            )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "saved"
        assert body["unit"] == "Biology"
        # storage_save called with (key, lesson_dict, teacher_id)
        sentinel.assert_called_once()
        args = sentinel.call_args.args
        assert args[0] == "lesson:Biology:Photosynthesis"
        assert args[1]["title"] == "Photosynthesis"
        assert args[1]["_unit"] == "Biology"
        assert "_saved_at" in args[1]
        assert args[2] == "teach-1"

    def test_filesystem_fallback_when_storage_unavailable(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        with patch("backend.routes.lesson_routes.storage_save", None):
            resp = client.post(
                "/api/save-lesson",
                data=json.dumps({
                    "lesson": {"title": "Cells"},
                    "unitName": "Biology",
                }),
                headers=auth_headers,
            )
        assert resp.status_code == 200
        # File written under LESSONS_DIR/Biology/Cells.json
        f = tmp_lesson_dirs["lessons"] / "Biology" / "Cells.json"
        assert f.exists()
        loaded = json.loads(f.read_text())
        assert loaded["title"] == "Cells"

    def test_filesystem_write_failure_returns_500(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        with patch("backend.routes.lesson_routes.storage_save", None), \
             patch("builtins.open", side_effect=IOError("disk gone")):
            resp = client.post(
                "/api/save-lesson",
                data=json.dumps({
                    "lesson": {"title": "X"},
                    "unitName": "U",
                }),
                headers=auth_headers,
            )
        assert resp.status_code == 500
        assert "internal error" in resp.get_json()["error"]

    def test_default_unit_name_is_general(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        with patch("backend.routes.lesson_routes.storage_save", None):
            resp = client.post(
                "/api/save-lesson",
                data=json.dumps({
                    "lesson": {"title": "Untitled"},
                }),
                headers=auth_headers,
            )
        assert resp.get_json()["unit"] == "General"

    def test_safe_filename_strips_unsafe_chars(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        # `_safe_filename` keeps alphanumerics, spaces, hyphens, underscores.
        # Slashes and asterisks should be stripped.
        with patch("backend.routes.lesson_routes.storage_save", None):
            resp = client.post(
                "/api/save-lesson",
                data=json.dumps({
                    "lesson": {"title": "Foo/Bar*Baz"},
                    "unitName": "U/T",
                }),
                headers=auth_headers,
            )
        assert resp.status_code == 200
        # Sanitized to "FooBarBaz" and unit "UT"
        unit_dir = tmp_lesson_dirs["lessons"] / "UT"
        assert unit_dir.exists()
        assert (unit_dir / "FooBarBaz.json").exists()


# ──────────────────────────────────────────────────────────────────
# /api/list-lessons
# ──────────────────────────────────────────────────────────────────


class TestListLessons:
    def test_storage_hit_returns_grouped_lessons(
        self, client, auth_headers,
    ):
        keys = ["lesson:Biology:Cells", "lesson:Biology:DNA",
                "lesson:Math:Algebra"]
        loads = {
            "lesson:Biology:Cells": {
                "title": "Cells", "standards": ["S1"],
                "learning_objectives": ["O1"], "_saved_at": "t1",
            },
            "lesson:Biology:DNA": {"title": "DNA"},
            "lesson:Math:Algebra": {"title": "Algebra"},
        }
        with patch("backend.routes.lesson_routes.storage_list_keys",
                   return_value=keys), \
             patch("backend.routes.lesson_routes.storage_load",
                   side_effect=lambda k, t: loads.get(k, {})):
            resp = client.get("/api/list-lessons", headers=auth_headers)
        body = resp.get_json()
        assert "Biology" in body["units"]
        assert len(body["units"]["Biology"]) == 2
        assert "Math" in body["units"]
        assert len(body["lessons"]) == 3
        # Cells has the metadata fields populated
        cells = next(
            l for l in body["lessons"] if l["title"] == "Cells"
        )
        assert cells["standards"] == ["S1"]
        assert cells["objectives"] == ["O1"]
        assert cells["saved_at"] == "t1"

    def test_storage_returns_no_keys_falls_through_to_file(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        # Empty keys list → falls into the file fallback. Pre-create
        # one lesson on disk under tmp_path.
        tmp_lesson_dirs["lessons"].mkdir(parents=True, exist_ok=True)
        unit = tmp_lesson_dirs["lessons"] / "FromFile"
        unit.mkdir()
        (unit / "L1.json").write_text(json.dumps({
            "title": "From File",
            "standards": ["F1"],
            "learning_objectives": ["FO1"],
            "_saved_at": "f1",
        }))

        with patch("backend.routes.lesson_routes.storage_list_keys",
                   return_value=[]):
            resp = client.get("/api/list-lessons", headers=auth_headers)
        body = resp.get_json()
        assert "FromFile" in body["units"]
        assert body["units"]["FromFile"][0]["title"] == "From File"

    def test_no_lessons_dir_returns_empty(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        # Module-level storage_list_keys exists but returns empty AND
        # LESSONS_DIR doesn't exist → empty response
        with patch("backend.routes.lesson_routes.storage_list_keys",
                   return_value=[]), \
             patch("backend.routes.lesson_routes.storage_load",
                   return_value=None):
            resp = client.get("/api/list-lessons", headers=auth_headers)
        body = resp.get_json()
        assert body["units"] == {}
        assert body["lessons"] == []

    def test_storage_unavailable_uses_file_fallback(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        # storage_list_keys/load = None → goes straight to filesystem.
        unit = tmp_lesson_dirs["lessons"] / "U"
        unit.mkdir(parents=True)
        (unit / "Lesson.json").write_text(json.dumps({"title": "L"}))
        # Create a non-directory entry to exercise the isdir filter
        (tmp_lesson_dirs["lessons"] / "stray.txt").write_text("ignored")

        with patch("backend.routes.lesson_routes.storage_list_keys", None), \
             patch("backend.routes.lesson_routes.storage_load", None):
            resp = client.get("/api/list-lessons", headers=auth_headers)
        body = resp.get_json()
        assert "U" in body["units"]
        assert "stray.txt" not in body["units"]

    def test_filesystem_corrupt_json_swallowed(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        # A JSON file in a unit folder with malformed contents should
        # be skipped without crashing the listing.
        unit = tmp_lesson_dirs["lessons"] / "U"
        unit.mkdir(parents=True)
        (unit / "broken.json").write_text("{ not valid")
        (unit / "ok.json").write_text(json.dumps({"title": "OK"}))

        with patch("backend.routes.lesson_routes.storage_list_keys", None):
            resp = client.get("/api/list-lessons", headers=auth_headers)
        body = resp.get_json()
        assert "U" in body["units"]
        # Only the valid lesson made it through
        titles = [l["title"] for l in body["lessons"]]
        assert "OK" in titles
        assert all("broken" not in t for t in titles)


# ──────────────────────────────────────────────────────────────────
# /api/load-lesson
# ──────────────────────────────────────────────────────────────────


class TestLoadLesson:
    def test_storage_hit(self, client, auth_headers):
        with patch(
            "backend.routes.lesson_routes.storage_load",
            return_value={"title": "Loaded"},
        ) as load:
            resp = client.get(
                "/api/load-lesson?unit=Biology&filename=Cells",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.get_json()["lesson"]["title"] == "Loaded"
        load.assert_called_once_with("lesson:Biology:Cells", "teach-1")

    def test_storage_miss_falls_back_to_file(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        unit = tmp_lesson_dirs["lessons"] / "Biology"
        unit.mkdir(parents=True)
        (unit / "Cells.json").write_text(json.dumps({"title": "FromFile"}))
        with patch(
            "backend.routes.lesson_routes.storage_load",
            return_value=None,
        ):
            resp = client.get(
                "/api/load-lesson?unit=Biology&filename=Cells",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.get_json()["lesson"]["title"] == "FromFile"

    def test_file_not_found_returns_error(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        with patch(
            "backend.routes.lesson_routes.storage_load",
            return_value=None,
        ):
            resp = client.get(
                "/api/load-lesson?unit=X&filename=Y",
                headers=auth_headers,
            )
        body = resp.get_json()
        assert body["error"] == "Lesson not found"

    def test_file_open_failure_returns_500(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        unit = tmp_lesson_dirs["lessons"] / "Biology"
        unit.mkdir(parents=True)
        (unit / "Cells.json").write_text("{}")
        # storage_load returns None so we fall to the file branch, then
        # open raises IOError on the actual read.
        real_open = open

        def selective(path, *args, **kwargs):
            if "Cells.json" in str(path):
                raise IOError("read fail")
            return real_open(path, *args, **kwargs)

        with patch(
            "backend.routes.lesson_routes.storage_load",
            return_value=None,
        ), patch("builtins.open", side_effect=selective):
            resp = client.get(
                "/api/load-lesson?unit=Biology&filename=Cells",
                headers=auth_headers,
            )
        assert resp.status_code == 500


# ──────────────────────────────────────────────────────────────────
# /api/delete-lesson
# ──────────────────────────────────────────────────────────────────


class TestDeleteLesson:
    def test_deletes_via_storage_and_file(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        unit = tmp_lesson_dirs["lessons"] / "Biology"
        unit.mkdir(parents=True)
        f = unit / "Cells.json"
        f.write_text("{}")
        delete_mock = MagicMock()
        with patch(
            "backend.routes.lesson_routes.storage_delete", delete_mock,
        ):
            resp = client.delete(
                "/api/delete-lesson?unit=Biology&filename=Cells",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "deleted"
        delete_mock.assert_called_once_with(
            "lesson:Biology:Cells", "teach-1",
        )
        # File also gone
        assert not f.exists()

    def test_no_local_file_still_returns_success(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        # No file on disk → just storage_delete is called, no file ops
        with patch(
            "backend.routes.lesson_routes.storage_delete", MagicMock(),
        ):
            resp = client.delete(
                "/api/delete-lesson?unit=X&filename=Y",
                headers=auth_headers,
            )
        assert resp.get_json()["status"] == "deleted"

    def test_file_remove_failure_returns_500(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        unit = tmp_lesson_dirs["lessons"] / "Biology"
        unit.mkdir(parents=True)
        (unit / "Cells.json").write_text("{}")
        with patch(
            "backend.routes.lesson_routes.storage_delete", MagicMock(),
        ), patch("os.remove", side_effect=IOError("perm denied")):
            resp = client.delete(
                "/api/delete-lesson?unit=Biology&filename=Cells",
                headers=auth_headers,
            )
        assert resp.status_code == 500


# ──────────────────────────────────────────────────────────────────
# /api/list-units
# ──────────────────────────────────────────────────────────────────


class TestListUnits:
    def test_storage_hit_returns_sorted_units(
        self, client, auth_headers,
    ):
        with patch(
            "backend.routes.lesson_routes.storage_list_keys",
            return_value=[
                "lesson:Math:A", "lesson:Biology:B", "lesson:Math:C",
            ],
        ):
            resp = client.get("/api/list-units", headers=auth_headers)
        units = resp.get_json()["units"]
        assert units == ["Biology", "Math"]

    def test_no_storage_falls_through_to_file(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        for u in ["Bio", "Algebra"]:
            (tmp_lesson_dirs["lessons"] / u).mkdir(parents=True)
        # Add a stray file that isn't a directory
        tmp_lesson_dirs["lessons"].mkdir(exist_ok=True)
        (tmp_lesson_dirs["lessons"] / "stray.txt").write_text("x")

        with patch(
            "backend.routes.lesson_routes.storage_list_keys", None,
        ):
            resp = client.get("/api/list-units", headers=auth_headers)
        assert resp.get_json()["units"] == ["Algebra", "Bio"]

    def test_no_file_dir_returns_empty(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        with patch(
            "backend.routes.lesson_routes.storage_list_keys",
            return_value=[],
        ):
            resp = client.get("/api/list-units", headers=auth_headers)
        assert resp.get_json()["units"] == []


# ──────────────────────────────────────────────────────────────────
# /api/calendar (GET)
# ──────────────────────────────────────────────────────────────────


class TestGetCalendar:
    def test_storage_hit_merges_defaults_for_missing_keys(
        self, client, auth_headers,
    ):
        # storage returns a partial calendar without 'holidays' and
        # without 'school_days' → the load helper fills defaults.
        partial = {"scheduled_lessons": [{"id": "1", "date": "2026-05-09"}]}
        with patch(
            "backend.routes.lesson_routes.storage_load",
            return_value=partial,
        ):
            resp = client.get("/api/calendar", headers=auth_headers)
        cal = resp.get_json()
        assert cal["scheduled_lessons"][0]["id"] == "1"
        assert cal["holidays"] == []
        assert cal["school_days"]["monday"] is True

    def test_storage_miss_file_fallback(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        # File exists with one holiday + missing scheduled_lessons key
        tmp_lesson_dirs["data"].mkdir(parents=True)
        tmp_lesson_dirs["calendar_file"].write_text(json.dumps({
            "holidays": [{"date": "2026-12-25", "name": "Xmas"}],
        }))
        with patch(
            "backend.routes.lesson_routes.storage_load",
            return_value=None,
        ):
            resp = client.get("/api/calendar", headers=auth_headers)
        cal = resp.get_json()
        assert cal["holidays"][0]["name"] == "Xmas"
        assert cal["scheduled_lessons"] == []

    def test_no_file_returns_full_default(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        with patch(
            "backend.routes.lesson_routes.storage_load",
            return_value=None,
        ):
            resp = client.get("/api/calendar", headers=auth_headers)
        cal = resp.get_json()
        assert cal["scheduled_lessons"] == []
        assert cal["holidays"] == []
        # All weekdays default True, weekend False
        assert cal["school_days"]["monday"] is True
        assert cal["school_days"]["saturday"] is False

    def test_corrupt_json_returns_default(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        tmp_lesson_dirs["data"].mkdir(parents=True)
        tmp_lesson_dirs["calendar_file"].write_text("{ corrupt")
        with patch(
            "backend.routes.lesson_routes.storage_load",
            return_value=None,
        ):
            resp = client.get("/api/calendar", headers=auth_headers)
        # Should fall back to defaults rather than raise
        assert resp.status_code == 200
        cal = resp.get_json()
        assert cal["scheduled_lessons"] == []


# ──────────────────────────────────────────────────────────────────
# /api/calendar/schedule (PUT)
# ──────────────────────────────────────────────────────────────────


class TestScheduleLesson:
    def test_no_data_returns_400(self, client, auth_headers):
        resp = client.put(
            "/api/calendar/schedule",
            data=json.dumps(None),
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_no_date_returns_400(self, client, auth_headers):
        resp = client.put(
            "/api/calendar/schedule",
            data=json.dumps({"unit": "X"}),
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "date is required" in resp.get_json()["error"]

    def test_new_entry_appended(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        with patch(
            "backend.routes.lesson_routes.storage_load",
            return_value=None,
        ), patch(
            "backend.routes.lesson_routes.storage_save", MagicMock(),
        ):
            resp = client.put(
                "/api/calendar/schedule",
                data=json.dumps({
                    "date": "2026-05-09",
                    "unit": "Biology",
                    "lesson_title": "Cells",
                    "day_number": 3,
                }),
                headers=auth_headers,
            )
        body = resp.get_json()
        assert body["status"] == "scheduled"
        assert body["entry"]["date"] == "2026-05-09"
        # An auto-generated id (uuid4)
        assert len(body["entry"]["id"]) > 0
        # File written via _save_calendar
        assert tmp_lesson_dirs["calendar_file"].exists()

    def test_existing_entry_updated_in_place(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        # Pre-populate calendar with an existing entry, then PUT same id.
        tmp_lesson_dirs["data"].mkdir(parents=True)
        tmp_lesson_dirs["calendar_file"].write_text(json.dumps({
            "scheduled_lessons": [
                {"id": "abc", "date": "old", "unit": "old", "lesson_title": "old"},
            ],
            "holidays": [],
            "school_days": {},
        }))
        with patch(
            "backend.routes.lesson_routes.storage_load",
            return_value=None,
        ), patch(
            "backend.routes.lesson_routes.storage_save", MagicMock(),
        ):
            resp = client.put(
                "/api/calendar/schedule",
                data=json.dumps({
                    "id": "abc",
                    "date": "2026-05-09",
                    "lesson_title": "new title",
                }),
                headers=auth_headers,
            )
        body = resp.get_json()
        assert body["entry"]["lesson_title"] == "new title"
        # Only one entry remains (in-place update, not append)
        cal = json.loads(tmp_lesson_dirs["calendar_file"].read_text())
        assert len(cal["scheduled_lessons"]) == 1


# ──────────────────────────────────────────────────────────────────
# /api/calendar/schedule/<id> (DELETE)
# ──────────────────────────────────────────────────────────────────


class TestUnscheduleLesson:
    def test_not_found_returns_404(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        with patch(
            "backend.routes.lesson_routes.storage_load",
            return_value=None,
        ):
            resp = client.delete(
                "/api/calendar/schedule/missing",
                headers=auth_headers,
            )
        assert resp.status_code == 404

    def test_found_removed_and_persisted(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        tmp_lesson_dirs["data"].mkdir(parents=True)
        tmp_lesson_dirs["calendar_file"].write_text(json.dumps({
            "scheduled_lessons": [
                {"id": "abc", "date": "d", "unit": "u", "lesson_title": "t"},
            ],
            "holidays": [],
            "school_days": {},
        }))
        save_mock = MagicMock()
        with patch(
            "backend.routes.lesson_routes.storage_load",
            return_value=None,
        ), patch(
            "backend.routes.lesson_routes.storage_save", save_mock,
        ):
            resp = client.delete(
                "/api/calendar/schedule/abc",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        cal = json.loads(tmp_lesson_dirs["calendar_file"].read_text())
        assert cal["scheduled_lessons"] == []


# ──────────────────────────────────────────────────────────────────
# /api/calendar/holiday
# ──────────────────────────────────────────────────────────────────


class TestHoliday:
    def test_add_no_data_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/calendar/holiday",
            data=json.dumps(None),
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_add_no_date_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/calendar/holiday",
            data=json.dumps({"name": "Xmas"}),
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_add_dedupes_by_date_and_sorts(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        # Pre-populate with same-date holiday and a later one — adding a
        # new same-date holiday should replace, not duplicate, and the
        # final list should be date-sorted.
        tmp_lesson_dirs["data"].mkdir(parents=True)
        tmp_lesson_dirs["calendar_file"].write_text(json.dumps({
            "scheduled_lessons": [],
            "holidays": [
                {"date": "2026-12-25", "name": "Old Xmas"},
                {"date": "2026-01-01", "name": "NYE"},
            ],
            "school_days": {},
        }))
        with patch(
            "backend.routes.lesson_routes.storage_load",
            return_value=None,
        ), patch(
            "backend.routes.lesson_routes.storage_save", MagicMock(),
        ):
            resp = client.post(
                "/api/calendar/holiday",
                data=json.dumps({
                    "date": "2026-12-25",
                    "name": "New Xmas",
                    "end_date": "2026-12-26",
                }),
                headers=auth_headers,
            )
        body = resp.get_json()
        assert body["status"] == "added"
        cal = json.loads(tmp_lesson_dirs["calendar_file"].read_text())
        # Exactly two holidays remain, sorted by date
        assert [h["date"] for h in cal["holidays"]] == [
            "2026-01-01", "2026-12-25",
        ]
        new_xmas = next(h for h in cal["holidays"]
                        if h["date"] == "2026-12-25")
        assert new_xmas["name"] == "New Xmas"
        assert new_xmas["end_date"] == "2026-12-26"

    def test_remove_no_date_400(self, client, auth_headers):
        resp = client.delete(
            "/api/calendar/holiday",
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_remove_not_found_404(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        with patch(
            "backend.routes.lesson_routes.storage_load",
            return_value=None,
        ):
            resp = client.delete(
                "/api/calendar/holiday?date=2026-04-01",
                headers=auth_headers,
            )
        assert resp.status_code == 404

    def test_remove_found_removes_and_persists(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        tmp_lesson_dirs["data"].mkdir(parents=True)
        tmp_lesson_dirs["calendar_file"].write_text(json.dumps({
            "scheduled_lessons": [],
            "holidays": [{"date": "2026-12-25", "name": "X"}],
            "school_days": {},
        }))
        with patch(
            "backend.routes.lesson_routes.storage_load",
            return_value=None,
        ), patch(
            "backend.routes.lesson_routes.storage_save", MagicMock(),
        ):
            resp = client.delete(
                "/api/calendar/holiday?date=2026-12-25",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        cal = json.loads(tmp_lesson_dirs["calendar_file"].read_text())
        assert cal["holidays"] == []


# ──────────────────────────────────────────────────────────────────
# /api/calendar/school-days
# ──────────────────────────────────────────────────────────────────


class TestUpdateSchoolDays:
    def test_no_data_returns_400(self, client, auth_headers):
        resp = client.put(
            "/api/calendar/school-days",
            data=json.dumps(None),
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_partial_update_only_known_days(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        with patch(
            "backend.routes.lesson_routes.storage_load",
            return_value=None,
        ), patch(
            "backend.routes.lesson_routes.storage_save", MagicMock(),
        ):
            resp = client.put(
                "/api/calendar/school-days",
                data=json.dumps({
                    "saturday": True,
                    "monday": False,
                    # Garbage key shouldn't pollute output
                    "garbage_key": "ignore me",
                }),
                headers=auth_headers,
            )
        body = resp.get_json()
        assert body["status"] == "updated"
        sd = body["school_days"]
        assert sd["monday"] is False
        assert sd["saturday"] is True
        # Defaults preserved for un-touched days
        assert sd["tuesday"] is True
        assert "garbage_key" not in sd


# ──────────────────────────────────────────────────────────────────
# /api/calendar/parse-document
# ──────────────────────────────────────────────────────────────────


class TestParseDocumentForCalendar:
    def test_no_filename_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/calendar/parse-document",
            data=json.dumps({}),
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_file_not_found_returns_404(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        resp = client.post(
            "/api/calendar/parse-document",
            data=json.dumps({"filename": "missing.pdf"}),
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_unsupported_extension_returns_400(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        tmp_lesson_dirs["documents"].mkdir(parents=True)
        f = tmp_lesson_dirs["documents"] / "x.txt"
        f.write_text("not a doc")
        resp = client.post(
            "/api/calendar/parse-document",
            data=json.dumps({"filename": "x.txt"}),
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "Unsupported file type" in resp.get_json()["error"]

    def test_extraction_returns_empty_or_error_marker(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        # Production checks: text empty OR text starts with '['. Both
        # paths return the same 400 error.
        tmp_lesson_dirs["documents"].mkdir(parents=True)
        f = tmp_lesson_dirs["documents"] / "x.pdf"
        f.write_text("dummy")
        with patch(
            "backend.routes.lesson_routes._extract_pdf_text",
            return_value=("[Error: corrupted]", None),
        ):
            resp = client.post(
                "/api/calendar/parse-document",
                data=json.dumps({"filename": "x.pdf"}),
                headers=auth_headers,
            )
        assert resp.status_code == 400
        assert "Could not extract text" in resp.get_json()["error"]

    def test_extraction_raises_returns_500(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        tmp_lesson_dirs["documents"].mkdir(parents=True)
        f = tmp_lesson_dirs["documents"] / "x.pdf"
        f.write_text("dummy")
        with patch(
            "backend.routes.lesson_routes._extract_pdf_text",
            side_effect=RuntimeError("pdf parse failed"),
        ):
            resp = client.post(
                "/api/calendar/parse-document",
                data=json.dumps({"filename": "x.pdf"}),
                headers=auth_headers,
            )
        assert resp.status_code == 500
        assert "Failed to read document" in resp.get_json()["error"]

    def test_no_anthropic_api_key_returns_500(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        tmp_lesson_dirs["documents"].mkdir(parents=True)
        f = tmp_lesson_dirs["documents"] / "x.pdf"
        f.write_text("dummy")
        with patch(
            "backend.routes.lesson_routes._extract_pdf_text",
            return_value=("Lorem ipsum body text.", None),
        ), patch(
            "backend.api_keys.get_api_key",
            return_value=None,
        ):
            resp = client.post(
                "/api/calendar/parse-document",
                data=json.dumps({"filename": "x.pdf"}),
                headers=auth_headers,
            )
        assert resp.status_code == 500
        assert "ANTHROPIC_API_KEY" in resp.get_json()["error"]

    def test_ai_returns_valid_events(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        tmp_lesson_dirs["documents"].mkdir(parents=True)
        (tmp_lesson_dirs["documents"] / "x.pdf").write_text("dummy")
        events = [
            {"date": "2026-09-05", "title": "Labor Day",
             "type": "holiday", "unit": ""},
            {"date": "2026-09-08", "title": "Cells intro",
             "type": "lesson", "unit": "Biology"},
        ]
        # Build a fake adapter.chat() response with markdown fence
        fake_msg = MagicMock()
        text_part = MagicMock()
        text_part.text = "```json\n" + json.dumps(events) + "\n```"
        fake_msg.content_parts = [text_part]
        fake_adapter = MagicMock()
        fake_adapter.chat.return_value = fake_msg

        with patch(
            "backend.routes.lesson_routes._extract_pdf_text",
            return_value=("Some text", None),
        ), patch(
            "backend.api_keys.get_api_key",
            return_value="sk-fake",
        ), patch(
            "backend.services.llm_adapter.AnthropicAdapter",
            return_value=fake_adapter,
        ):
            resp = client.post(
                "/api/calendar/parse-document",
                data=json.dumps({"filename": "x.pdf"}),
                headers=auth_headers,
            )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["count"] == 2
        assert body["events"][1]["title"] == "Cells intro"

    def test_ai_returns_non_list_returns_500(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        tmp_lesson_dirs["documents"].mkdir(parents=True)
        (tmp_lesson_dirs["documents"] / "x.pdf").write_text("dummy")
        # AI returns valid JSON but not a list
        fake_msg = MagicMock()
        text_part = MagicMock()
        text_part.text = json.dumps({"oops": "object not array"})
        fake_msg.content_parts = [text_part]
        fake_adapter = MagicMock()
        fake_adapter.chat.return_value = fake_msg
        with patch(
            "backend.routes.lesson_routes._extract_pdf_text",
            return_value=("Some text", None),
        ), patch(
            "backend.api_keys.get_api_key",
            return_value="sk-fake",
        ), patch(
            "backend.services.llm_adapter.AnthropicAdapter",
            return_value=fake_adapter,
        ):
            resp = client.post(
                "/api/calendar/parse-document",
                data=json.dumps({"filename": "x.pdf"}),
                headers=auth_headers,
            )
        assert resp.status_code == 500
        assert "invalid format" in resp.get_json()["error"]

    def test_ai_returns_invalid_json_returns_500(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        tmp_lesson_dirs["documents"].mkdir(parents=True)
        (tmp_lesson_dirs["documents"] / "x.docx").write_text("dummy")
        fake_msg = MagicMock()
        text_part = MagicMock()
        text_part.text = "not actually json"
        fake_msg.content_parts = [text_part]
        fake_adapter = MagicMock()
        fake_adapter.chat.return_value = fake_msg
        with patch(
            "backend.routes.lesson_routes._extract_docx_text",
            return_value="Some text",
        ), patch(
            "backend.api_keys.get_api_key",
            return_value="sk-fake",
        ), patch(
            "backend.services.llm_adapter.AnthropicAdapter",
            return_value=fake_adapter,
        ):
            resp = client.post(
                "/api/calendar/parse-document",
                data=json.dumps({"filename": "x.docx"}),
                headers=auth_headers,
            )
        assert resp.status_code == 500
        assert "could not parse" in resp.get_json()["error"]

    def test_ai_adapter_raises_returns_500(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        tmp_lesson_dirs["documents"].mkdir(parents=True)
        (tmp_lesson_dirs["documents"] / "x.pdf").write_text("dummy")
        fake_adapter = MagicMock()
        fake_adapter.chat.side_effect = RuntimeError("network down")
        with patch(
            "backend.routes.lesson_routes._extract_pdf_text",
            return_value=("Some text", None),
        ), patch(
            "backend.api_keys.get_api_key",
            return_value="sk-fake",
        ), patch(
            "backend.services.llm_adapter.AnthropicAdapter",
            return_value=fake_adapter,
        ):
            resp = client.post(
                "/api/calendar/parse-document",
                data=json.dumps({"filename": "x.pdf"}),
                headers=auth_headers,
            )
        assert resp.status_code == 500
        assert "AI parsing failed" in resp.get_json()["error"]


# ──────────────────────────────────────────────────────────────────
# /api/calendar/import-events
# ──────────────────────────────────────────────────────────────────


class TestImportEvents:
    def test_no_events_array_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/calendar/import-events",
            data=json.dumps({}),
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_events_must_be_list_400(self, client, auth_headers):
        resp = client.post(
            "/api/calendar/import-events",
            data=json.dumps({"events": "not a list"}),
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_imports_lessons_and_holidays_with_dedup(
        self, client, auth_headers, tmp_lesson_dirs,
    ):
        tmp_lesson_dirs["data"].mkdir(parents=True)
        tmp_lesson_dirs["calendar_file"].write_text(json.dumps({
            "scheduled_lessons": [],
            "holidays": [{"date": "2026-09-05", "name": "Old"}],
            "school_days": {},
        }))
        events = [
            {"date": "2026-09-05", "title": "Labor", "type": "holiday"},
            {"date": "2026-09-08", "title": "Cells", "type": "lesson",
             "unit": "Biology"},
            # Skipped — no date
            {"title": "no date"},
            # Skipped — no title
            {"date": "2026-09-10"},
        ]
        with patch(
            "backend.routes.lesson_routes.storage_load",
            return_value=None,
        ), patch(
            "backend.routes.lesson_routes.storage_save", MagicMock(),
        ):
            resp = client.post(
                "/api/calendar/import-events",
                data=json.dumps({"events": events}),
                headers=auth_headers,
            )
        body = resp.get_json()
        assert body["status"] == "imported"
        assert body["lessons_added"] == 1
        assert body["holidays_added"] == 1
        cal = json.loads(tmp_lesson_dirs["calendar_file"].read_text())
        # Old "Old" replaced by new "Labor"
        assert len(cal["holidays"]) == 1
        assert cal["holidays"][0]["name"] == "Labor"


# ──────────────────────────────────────────────────────────────────
# Resources / Assets endpoints
# ──────────────────────────────────────────────────────────────────


class TestSaveResource:
    def test_no_content_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/save-resource",
            data=json.dumps({}),
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_no_storage_returns_500(self, client, auth_headers):
        with patch(
            "backend.routes.lesson_routes.storage_save", None,
        ):
            resp = client.post(
                "/api/save-resource",
                data=json.dumps({"content": "data", "title": "T"}),
                headers=auth_headers,
            )
        assert resp.status_code == 500

    def test_auto_generates_resource_id(self, client, auth_headers):
        save_mock = MagicMock()
        with patch(
            "backend.routes.lesson_routes.storage_save", save_mock,
        ):
            resp = client.post(
                "/api/save-resource",
                data=json.dumps({"content": "data", "title": "T"}),
                headers=auth_headers,
            )
        body = resp.get_json()
        assert body["success"] is True
        assert len(body["resource_id"]) == 8
        save_mock.assert_called_once()

    def test_uses_provided_resource_id(self, client, auth_headers):
        save_mock = MagicMock()
        with patch(
            "backend.routes.lesson_routes.storage_save", save_mock,
        ):
            resp = client.post(
                "/api/save-resource",
                data=json.dumps({
                    "content": "data",
                    "resource_id": "abc12345",
                    "title": "T",
                }),
                headers=auth_headers,
            )
        body = resp.get_json()
        assert body["resource_id"] == "abc12345"
        # Storage key built from resource_id
        save_mock.assert_called_once()
        assert save_mock.call_args.args[0] == "resource:abc12345"


class TestListResources:
    def test_filter_by_content_type(self, client, auth_headers):
        with patch(
            "backend.routes.lesson_routes.storage_list_keys",
            return_value=["resource:1", "resource:2"],
        ), patch(
            "backend.routes.lesson_routes.storage_load",
            side_effect=lambda k, t: {
                "resource:1": {"id": "1", "content_type": "assessment",
                               "title": "A1", "updated_at": "2026-05-09"},
                "resource:2": {"id": "2", "content_type": "lesson",
                               "title": "L1", "updated_at": "2026-05-08"},
            }.get(k),
        ):
            resp = client.get(
                "/api/list-resources?type=assessment",
                headers=auth_headers,
            )
        body = resp.get_json()
        assert len(body["resources"]) == 1
        assert body["resources"][0]["title"] == "A1"

    def test_sorted_by_updated_at_desc(self, client, auth_headers):
        with patch(
            "backend.routes.lesson_routes.storage_list_keys",
            return_value=["resource:old", "resource:new"],
        ), patch(
            "backend.routes.lesson_routes.storage_load",
            side_effect=lambda k, t: {
                "resource:old": {"id": "old",
                                 "content_type": "assessment",
                                 "title": "Old",
                                 "updated_at": "2026-01-01"},
                "resource:new": {"id": "new",
                                 "content_type": "assessment",
                                 "title": "New",
                                 "updated_at": "2026-12-31"},
            }.get(k),
        ):
            resp = client.get(
                "/api/list-resources",
                headers=auth_headers,
            )
        body = resp.get_json()
        assert body["resources"][0]["title"] == "New"
        assert body["resources"][1]["title"] == "Old"

    def test_skips_loads_returning_none(self, client, auth_headers):
        with patch(
            "backend.routes.lesson_routes.storage_list_keys",
            return_value=["resource:gone"],
        ), patch(
            "backend.routes.lesson_routes.storage_load",
            return_value=None,
        ):
            resp = client.get(
                "/api/list-resources",
                headers=auth_headers,
            )
        assert resp.get_json()["resources"] == []


class TestLoadResource:
    def test_no_resource_id_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/load-resource",
            data=json.dumps({}),
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_no_storage_returns_500(self, client, auth_headers):
        with patch(
            "backend.routes.lesson_routes.storage_load", None,
        ):
            resp = client.post(
                "/api/load-resource",
                data=json.dumps({"resource_id": "abc"}),
                headers=auth_headers,
            )
        assert resp.status_code == 500

    def test_not_found_returns_404(self, client, auth_headers):
        with patch(
            "backend.routes.lesson_routes.storage_load",
            return_value=None,
        ):
            resp = client.post(
                "/api/load-resource",
                data=json.dumps({"resource_id": "abc"}),
                headers=auth_headers,
            )
        assert resp.status_code == 404

    def test_happy_path_returns_resource(self, client, auth_headers):
        loaded = {"id": "abc", "title": "T"}
        with patch(
            "backend.routes.lesson_routes.storage_load",
            return_value=loaded,
        ):
            resp = client.post(
                "/api/load-resource",
                data=json.dumps({"resource_id": "abc"}),
                headers=auth_headers,
            )
        body = resp.get_json()
        assert body["success"] is True
        assert body["resource"]["title"] == "T"


class TestDeleteResource:
    def test_no_resource_id_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/delete-resource",
            data=json.dumps({}),
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_no_storage_returns_500(self, client, auth_headers):
        with patch(
            "backend.routes.lesson_routes.storage_delete", None,
        ):
            resp = client.post(
                "/api/delete-resource",
                data=json.dumps({"resource_id": "abc"}),
                headers=auth_headers,
            )
        assert resp.status_code == 500

    def test_happy_path_calls_delete(self, client, auth_headers):
        delete_mock = MagicMock()
        with patch(
            "backend.routes.lesson_routes.storage_delete", delete_mock,
        ):
            resp = client.post(
                "/api/delete-resource",
                data=json.dumps({"resource_id": "abc"}),
                headers=auth_headers,
            )
        body = resp.get_json()
        assert body["success"] is True
        delete_mock.assert_called_once_with("resource:abc", "teach-1")


# ──────────────────────────────────────────────────────────────────
# parse-document Rule-#11 regression: ensure removed `anthropic`
# NameError gate doesn't reappear via dead code path.
# ──────────────────────────────────────────────────────────────────


class TestRuleEleven:
    def test_parse_document_does_not_reference_module_level_anthropic(
        self,
    ):
        """Pin: PR #288 removed an `if anthropic is None:` gate that
        referenced an undeclared name and would NameError in production
        when the route was hit. Make sure no future patch reintroduces
        that bare reference."""
        import inspect
        from backend.routes import lesson_routes
        src = inspect.getsource(
            lesson_routes.parse_document_for_calendar
        )
        # The fix is durable as long as no top-level `anthropic` symbol
        # is consulted in this function body.
        assert "anthropic is None" not in src
        # Sanity: AnthropicAdapter is what we actually use
        assert "AnthropicAdapter" in src
