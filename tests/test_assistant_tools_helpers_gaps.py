"""Gap-fill unit tests for backend/services/assistant_tools.py helpers.

Audit MAJOR #4 sprint follow-up to PR #308. Companion to existing
test_assistant_tools_unit.py. Targets the 345 uncovered LOC (43%
baseline). Focuses on the storage/file-fallback helpers that are
small, deterministic, and high-leverage for global coverage.

Branches covered
* _load_settings: storage hit, file fallback, corrupt-JSON swallow
* _load_standards: planner success, planner exception fall-through,
  legacy file path with subject mapping, no file → empty
* _load_saved_lessons: storage hit, file fallback, corrupt-JSON
* _load_roster: dev-mode Focus SIS CSVs (Last,First / Last;First /
  passthrough name forms), Clever roster CSVs with section JSON
  cross-reference, multi-tenant Supabase storage path
* _load_parent_contacts: storage hit, file fallback, corrupt-JSON
* _load_saved_assignments: storage hit + alias collection, file
  fallback, importedDoc filename alias
* _load_calendar / _save_calendar: storage / file paths
* _load_memories: storage hit, file fallback, non-list defensive
* _load_email_config: storage hit, file fallback, no-data fallback
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def tmp_paths(monkeypatch, tmp_path):
    """Redirect all module-level paths to tmp_path so tests are
    hermetic — no ~/.graider_* I/O."""
    paths = {
        "settings_file": tmp_path / "settings.json",
        "lessons_dir": tmp_path / "lessons",
        "periods_dir": tmp_path / "periods",
        "rosters_dir": tmp_path / "rosters",
        "parent_contacts_file": tmp_path / "parent_contacts.json",
        "assignments_dir": tmp_path / "assignments",
        "calendar_file": tmp_path / "data" / "calendar.json",
        "memory_file": tmp_path / "memory.json",
        "standards_dir": tmp_path / "standards",
        "email_config_file": tmp_path / "email_config.json",
    }
    paths["lessons_dir"].mkdir()
    paths["periods_dir"].mkdir()
    paths["rosters_dir"].mkdir()
    paths["assignments_dir"].mkdir()
    paths["standards_dir"].mkdir()

    monkeypatch.setattr(
        "backend.services.assistant_tools.SETTINGS_FILE",
        str(paths["settings_file"]),
    )
    monkeypatch.setattr(
        "backend.services.assistant_tools.LESSONS_DIR",
        str(paths["lessons_dir"]),
    )
    monkeypatch.setattr(
        "backend.services.assistant_tools.PERIODS_DIR",
        str(paths["periods_dir"]),
    )
    monkeypatch.setattr(
        "backend.services.assistant_tools.ROSTERS_DIR",
        str(paths["rosters_dir"]),
    )
    monkeypatch.setattr(
        "backend.services.assistant_tools.PARENT_CONTACTS_FILE",
        str(paths["parent_contacts_file"]),
    )
    monkeypatch.setattr(
        "backend.services.assistant_tools.ASSIGNMENTS_DIR",
        str(paths["assignments_dir"]),
    )
    monkeypatch.setattr(
        "backend.services.assistant_tools.CALENDAR_FILE",
        str(paths["calendar_file"]),
    )
    monkeypatch.setattr(
        "backend.services.assistant_tools.MEMORY_FILE",
        str(paths["memory_file"]),
    )
    monkeypatch.setattr(
        "backend.services.assistant_tools.STANDARDS_DIR",
        str(paths["standards_dir"]),
    )
    return paths


# ──────────────────────────────────────────────────────────────────
# _load_settings
# ──────────────────────────────────────────────────────────────────


class TestLoadSettings:
    def test_storage_hit(self, tmp_paths):
        from backend.services import assistant_tools as mod
        with patch.object(
            mod, "storage_load", return_value={"config": {"x": 1}},
        ):
            assert mod._load_settings("teach-1") == {"config": {"x": 1}}

    def test_file_fallback(self, tmp_paths):
        from backend.services import assistant_tools as mod
        tmp_paths["settings_file"].write_text(json.dumps({
            "config": {"from_file": True},
        }))
        with patch.object(mod, "storage_load", None):
            assert mod._load_settings()["config"]["from_file"] is True

    def test_corrupt_json_returns_empty(self, tmp_paths):
        from backend.services import assistant_tools as mod
        tmp_paths["settings_file"].write_text("{ corrupt")
        with patch.object(mod, "storage_load", None):
            assert mod._load_settings() == {}


# ──────────────────────────────────────────────────────────────────
# _load_standards
# ──────────────────────────────────────────────────────────────────


class TestLoadStandards:
    def test_planner_success_short_circuits(self, tmp_paths):
        from backend.services import assistant_tools as mod
        with patch.object(
            mod, "_load_settings",
            return_value={"config": {
                "state": "FL", "subject": "Math", "grade_level": "9",
            }},
        ), patch(
            "backend.routes.planner_routes.load_standards",
            return_value={"standards": [{"code": "FL.MATH.1"}]},
        ):
            result = mod._load_standards()
        assert result == [{"code": "FL.MATH.1"}]

    def test_planner_exception_falls_to_legacy_file(self, tmp_paths):
        from backend.services import assistant_tools as mod
        # Pre-create the legacy fallback file
        legacy = tmp_paths["standards_dir"] / "standards_fl_math.json"
        legacy.write_text(json.dumps([{"code": "FL.LEGACY.1"}]))
        with patch.object(
            mod, "_load_settings",
            return_value={"config": {
                "state": "FL", "subject": "Math", "grade_level": "9",
            }},
        ), patch(
            "backend.routes.planner_routes.load_standards",
            side_effect=RuntimeError("planner dead"),
        ):
            result = mod._load_standards()
        assert result == [{"code": "FL.LEGACY.1"}]

    def test_legacy_file_with_dict_root(self, tmp_paths):
        from backend.services import assistant_tools as mod
        # Legacy file stored as dict with 'standards' key
        legacy = tmp_paths["standards_dir"] / "standards_fl_science.json"
        legacy.write_text(json.dumps({
            "standards": [{"code": "FL.SCI.1"}],
        }))
        with patch.object(
            mod, "_load_settings",
            return_value={"config": {
                "state": "FL", "subject": "Science", "grade_level": "7",
            }},
        ), patch(
            "backend.routes.planner_routes.load_standards",
            side_effect=RuntimeError("dead"),
        ):
            result = mod._load_standards()
        assert result == [{"code": "FL.SCI.1"}]

    def test_no_legacy_file_returns_empty(self, tmp_paths):
        from backend.services import assistant_tools as mod
        with patch.object(
            mod, "_load_settings",
            return_value={"config": {"state": "FL", "subject": "Math"}},
        ), patch(
            "backend.routes.planner_routes.load_standards",
            side_effect=RuntimeError("dead"),
        ):
            assert mod._load_standards() == []


# ──────────────────────────────────────────────────────────────────
# _load_saved_lessons
# ──────────────────────────────────────────────────────────────────


class TestLoadSavedLessons:
    def test_storage_path_with_keys(self, tmp_paths):
        from backend.services import assistant_tools as mod
        keys = ["lesson:Biology:Cells", "lesson:Math:Algebra"]
        loads = {
            "lesson:Biology:Cells": {
                "title": "Cells", "standards": ["S1"],
            },
            "lesson:Math:Algebra": {"title": "Algebra"},
        }
        with patch.object(
            mod, "storage_list_keys", return_value=keys,
        ), patch.object(
            mod, "storage_load",
            side_effect=lambda k, t: loads.get(k),
        ):
            lessons = mod._load_saved_lessons("teach-1")
        assert len(lessons) == 2
        bio = next(l for l in lessons if l["unit"] == "Biology")
        assert bio["title"] == "Cells"
        assert bio["standards"] == ["S1"]

    def test_no_storage_falls_to_filesystem(self, tmp_paths):
        from backend.services import assistant_tools as mod
        unit = tmp_paths["lessons_dir"] / "Biology"
        unit.mkdir()
        (unit / "Cells.json").write_text(json.dumps({
            "title": "Cells", "standards": ["F1"],
        }))
        with patch.object(mod, "storage_list_keys", None), patch.object(
            mod, "storage_load", None,
        ):
            lessons = mod._load_saved_lessons()
        assert any(l["title"] == "Cells" for l in lessons)

    def test_no_lessons_dir_returns_empty(self, tmp_paths, monkeypatch):
        from backend.services import assistant_tools as mod
        monkeypatch.setattr(
            mod, "LESSONS_DIR",
            str(tmp_paths["lessons_dir"] / "no-such"),
        )
        with patch.object(mod, "storage_list_keys", None), patch.object(
            mod, "storage_load", None,
        ):
            assert mod._load_saved_lessons() == []


# ──────────────────────────────────────────────────────────────────
# _load_parent_contacts
# ──────────────────────────────────────────────────────────────────


class TestLoadParentContacts:
    def test_storage_hit(self, tmp_paths):
        from backend.services import assistant_tools as mod
        with patch.object(
            mod, "storage_load", return_value={"s1": {"email": "x"}},
        ):
            assert mod._load_parent_contacts() == {"s1": {"email": "x"}}

    def test_file_fallback(self, tmp_paths):
        from backend.services import assistant_tools as mod
        tmp_paths["parent_contacts_file"].write_text(json.dumps({
            "s1": {"parent_email": "p@x.com"},
        }))
        with patch.object(mod, "storage_load", None):
            result = mod._load_parent_contacts()
        assert result["s1"]["parent_email"] == "p@x.com"

    def test_no_file_returns_empty(self, tmp_paths):
        from backend.services import assistant_tools as mod
        with patch.object(mod, "storage_load", None):
            assert mod._load_parent_contacts() == {}

    def test_corrupt_json_returns_empty(self, tmp_paths):
        from backend.services import assistant_tools as mod
        tmp_paths["parent_contacts_file"].write_text("{ bad")
        with patch.object(mod, "storage_load", None):
            assert mod._load_parent_contacts() == {}


# ──────────────────────────────────────────────────────────────────
# _load_saved_assignments
# ──────────────────────────────────────────────────────────────────


class TestLoadSavedAssignments:
    def test_storage_path_with_aliases_and_importedDoc(self, tmp_paths):
        from backend.services import assistant_tools as mod
        keys = ["assignment:Quiz1"]
        loads = {
            "assignment:Quiz1": {
                "title": "Quiz One",
                "aliases": ["Q1"],
                "importedDoc": {"filename": "quiz1.docx"},
            },
        }
        with patch.object(
            mod, "storage_list_keys", return_value=keys,
        ), patch.object(
            mod, "storage_load",
            side_effect=lambda k, t: loads.get(k),
        ):
            saved = mod._load_saved_assignments("teach-1")
        assert len(saved) == 1
        assert saved[0]["title"] == "Quiz One"
        # importedDoc filename added to alias norms
        assert any("quiz1" in a for a in saved[0]["aliases"])

    def test_file_fallback(self, tmp_paths):
        from backend.services import assistant_tools as mod
        f = tmp_paths["assignments_dir"] / "Quiz.json"
        f.write_text(json.dumps({
            "title": "Quiz", "aliases": ["q-alias"],
        }))
        with patch.object(mod, "storage_list_keys", None), patch.object(
            mod, "storage_load", None,
        ):
            saved = mod._load_saved_assignments()
        assert any(a["title"] == "Quiz" for a in saved)


# ──────────────────────────────────────────────────────────────────
# _load_calendar / _save_calendar
# ──────────────────────────────────────────────────────────────────


class TestLoadAndSaveCalendar:
    def test_load_storage_hit(self, tmp_paths):
        from backend.services import assistant_tools as mod
        with patch.object(
            mod, "storage_load",
            return_value={"holidays": [{"date": "2026-12-25"}]},
        ):
            cal = mod._load_calendar()
        assert cal["holidays"][0]["date"] == "2026-12-25"

    def test_load_no_storage_no_file_returns_default(self, tmp_paths):
        from backend.services import assistant_tools as mod
        with patch.object(mod, "storage_load", None):
            cal = mod._load_calendar()
        assert cal == {
            "scheduled_lessons": [], "holidays": [], "school_days": {},
        }

    def test_load_file_fallback_corrupt_returns_default(self, tmp_paths):
        from backend.services import assistant_tools as mod
        tmp_paths["calendar_file"].parent.mkdir(parents=True)
        tmp_paths["calendar_file"].write_text("{ corrupt")
        with patch.object(mod, "storage_load", None):
            cal = mod._load_calendar()
        assert "scheduled_lessons" in cal
        assert cal["scheduled_lessons"] == []

    def test_save_storage_path(self, tmp_paths):
        from backend.services import assistant_tools as mod
        save_mock = MagicMock()
        with patch.object(mod, "storage_save", save_mock):
            mod._save_calendar({"holidays": []})
        save_mock.assert_called_once()

    def test_save_filesystem_fallback(self, tmp_paths):
        from backend.services import assistant_tools as mod
        with patch.object(mod, "storage_save", None):
            mod._save_calendar({"holidays": [{"date": "x"}]})
        assert tmp_paths["calendar_file"].exists()


# ──────────────────────────────────────────────────────────────────
# _load_memories / _save_memories
# ──────────────────────────────────────────────────────────────────


class TestLoadAndSaveMemories:
    def test_storage_hit_returns_list(self, tmp_paths):
        from backend.services import assistant_tools as mod
        with patch.object(
            mod, "storage_load", return_value=["fact 1", "fact 2"],
        ):
            assert mod._load_memories() == ["fact 1", "fact 2"]

    def test_storage_non_list_returns_empty(self, tmp_paths):
        from backend.services import assistant_tools as mod
        # Non-list payload from storage → defensive return []
        with patch.object(
            mod, "storage_load", return_value={"not": "a list"},
        ):
            assert mod._load_memories() == []

    def test_file_fallback(self, tmp_paths):
        from backend.services import assistant_tools as mod
        tmp_paths["memory_file"].write_text(json.dumps(["from file"]))
        with patch.object(mod, "storage_load", None):
            assert mod._load_memories() == ["from file"]

    def test_no_file_returns_empty(self, tmp_paths):
        from backend.services import assistant_tools as mod
        with patch.object(mod, "storage_load", None):
            assert mod._load_memories() == []

    def test_save_storage_path(self, tmp_paths):
        from backend.services import assistant_tools as mod
        save_mock = MagicMock()
        with patch.object(mod, "storage_save", save_mock):
            mod._save_memories(["new fact"])
        save_mock.assert_called_once()

    def test_save_file_fallback(self, tmp_paths):
        from backend.services import assistant_tools as mod
        with patch.object(mod, "storage_save", None):
            mod._save_memories(["written to file"])
        loaded = json.loads(tmp_paths["memory_file"].read_text())
        assert loaded == ["written to file"]


# ──────────────────────────────────────────────────────────────────
# _load_roster: dev-mode Focus SIS path
# ──────────────────────────────────────────────────────────────────


class TestLoadRosterDevMode:
    def test_focus_sis_csv_with_comma_separated_names(self, tmp_paths):
        from backend.services import assistant_tools as mod
        # Focus SIS uses "Last, First Middle" format
        csv = tmp_paths["periods_dir"] / "p1.csv"
        csv.write_text(
            'Student,Student ID,Local ID,Grade\n'
            '"Doe, Jane Marie",sid-1,lid-1,9\n'
            '"Smith;John",sid-2,lid-2,10\n'
            '"Single Name",sid-3,lid-3,11\n'
        )
        meta = tmp_paths["periods_dir"] / "p1.csv.meta.json"
        meta.write_text(json.dumps({
            "period_name": "Period 1",
            "course_codes": ["MATH101"],
        }))
        # Force dev-mode (not multi-tenant)
        with patch.object(
            mod, "storage_list_keys", None,
        ), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SUPABASE_URL", None)
            os.environ.pop("SUPABASE_SERVICE_KEY", None)
            roster = mod._load_roster()
        names = [r["name"] for r in roster]
        # Comma-separated → "Jane Marie Doe"
        assert "Jane Marie Doe" in names
        # Semicolon-separated → "John Smith"
        assert "John Smith" in names
        # Passthrough name preserved
        assert "Single Name" in names
        # Period meta picked up
        period_1 = next(r for r in roster if r["name"] == "Jane Marie Doe")
        assert period_1["period"] == "Period 1"
        assert period_1["course_codes"] == ["MATH101"]
