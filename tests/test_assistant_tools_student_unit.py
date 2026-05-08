"""
Unit tests for backend/services/assistant_tools_student.py.

Audit MAJOR #4 sprint follow-up to PR #255. Targets the 561 uncovered LOC
(was 15% before) — biggest remaining target on the priority list.

Strategy:
- Pure helpers (_parse_csv_name) via direct assertions.
- get_student_accommodations + get_student_streak via mocking the loader
  helpers (_load_roster, _load_master_csv, _load_accommodations,
  _fuzzy_name_match) — these functions are pure-Python orchestrators.
- _find_all_student_files + _remove_student_from_csv via real CSV
  fixtures (no mocking — the I/O is the contract under test).
- TestTeacherIdRequired contract pin for the 4 user-facing tools.

Pattern matches PR #255 (assistant_tools_behavior).
Lessons applied: HOME redirect from fixture, no real Supabase calls,
no real ~/.graider_* writes. Final coverage delta will be verified
with two full-suite runs before opening the PR.
"""
from __future__ import annotations

import csv
import json
import os
from unittest.mock import patch, MagicMock

import pytest


TID = "teacher-alice"


# ──────────────────────────────────────────────────────────────────
# _parse_csv_name (pure helper)
# ──────────────────────────────────────────────────────────────────


class TestParseCsvName:
    def test_last_comma_first(self):
        from backend.services.assistant_tools_student import _parse_csv_name
        assert _parse_csv_name("Smith, Alice") == "Alice Smith"

    def test_last_semicolon_first(self):
        from backend.services.assistant_tools_student import _parse_csv_name
        assert _parse_csv_name("Smith; Alice") == "Alice Smith"

    def test_strips_quotes(self):
        from backend.services.assistant_tools_student import _parse_csv_name
        assert _parse_csv_name('"Smith, Alice"') == "Alice Smith"

    def test_strips_whitespace(self):
        from backend.services.assistant_tools_student import _parse_csv_name
        assert _parse_csv_name("  Smith,  Alice  ") == "Alice Smith"

    def test_first_last_returned_unchanged(self):
        from backend.services.assistant_tools_student import _parse_csv_name
        # No comma/semicolon → returned as-is (after strip)
        assert _parse_csv_name("Alice Smith") == "Alice Smith"

    def test_handles_middle_after_separator(self):
        from backend.services.assistant_tools_student import _parse_csv_name
        # "Smith, Alice Marie" → "Alice Marie Smith"
        assert _parse_csv_name("Smith, Alice Marie") == "Alice Marie Smith"


# ──────────────────────────────────────────────────────────────────
# get_student_accommodations
# ──────────────────────────────────────────────────────────────────


class TestGetStudentAccommodations:
    def test_empty_student_name_returns_error(self):
        from backend.services.assistant_tools_student import get_student_accommodations
        result = get_student_accommodations("", teacher_id=TID)
        assert "error" in result
        assert "student_name is required" in result["error"]

    def test_no_match_returns_error(self):
        from backend.services.assistant_tools_student import get_student_accommodations
        with patch("backend.services.assistant_tools_student._load_roster",
                   return_value=[]), \
             patch("backend.services.assistant_tools_student._load_master_csv",
                   return_value=[]):
            result = get_student_accommodations("Ghost Student", teacher_id=TID)
        assert "error" in result
        assert "No student found" in result["error"]

    def test_match_in_roster_no_accommodations(self):
        from backend.services.assistant_tools_student import get_student_accommodations
        roster = [{"student_name": "Alice Smith", "student_id": "sid-1"}]
        with patch("backend.services.assistant_tools_student._load_roster",
                   return_value=roster), \
             patch("backend.services.assistant_tools_student._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in n.lower()), \
             patch("backend.services.assistant_tools_student._load_accommodations",
                   return_value={}):
            result = get_student_accommodations("Alice", teacher_id=TID)
        assert result["has_accommodations"] is False
        assert result["student_id"] == "sid-1"
        assert result["student_name"] == "Alice Smith"
        assert "does not have IEP/504" in result["message"]

    def test_match_with_accommodations_includes_grading_impacts(self):
        from backend.services.assistant_tools_student import get_student_accommodations
        roster = [{"student_name": "Alice Smith", "student_id": "sid-1"}]
        accommodations = {
            "sid-1": {
                "presets": ["extended_time", "calculator", "read_aloud"],
                "notes": "Needs quiet room for tests",
            }
        }
        with patch("backend.services.assistant_tools_student._load_roster",
                   return_value=roster), \
             patch("backend.services.assistant_tools_student._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in n.lower()), \
             patch("backend.services.assistant_tools_student._load_accommodations",
                   return_value=accommodations):
            result = get_student_accommodations("Alice", teacher_id=TID)

        assert result["has_accommodations"] is True
        assert result["presets"] == ["extended_time", "calculator", "read_aloud"]
        assert result["notes"] == "Needs quiet room for tests"
        # Grading impacts are mapped from preset keys to descriptions
        assert any("Extra time" in i for i in result["grading_impacts"])
        assert any("Calculator" in i for i in result["grading_impacts"])
        assert any("read aloud" in i for i in result["grading_impacts"])

    def test_unknown_preset_uses_titlecased_fallback(self):
        from backend.services.assistant_tools_student import get_student_accommodations
        roster = [{"student_name": "Alice", "student_id": "sid-1"}]
        accommodations = {
            "sid-1": {
                "presets": ["custom_preset_not_in_map"],
                "notes": "",
            }
        }
        with patch("backend.services.assistant_tools_student._load_roster",
                   return_value=roster), \
             patch("backend.services.assistant_tools_student._fuzzy_name_match",
                   side_effect=lambda q, n: True), \
             patch("backend.services.assistant_tools_student._load_accommodations",
                   return_value=accommodations):
            result = get_student_accommodations("Alice", teacher_id=TID)

        # Fallback: underscore→space + title case
        assert result["grading_impacts"] == ["Custom Preset Not In Map"]

    def test_falls_back_to_master_csv_when_roster_misses(self):
        from backend.services.assistant_tools_student import get_student_accommodations
        # Empty roster — should look in master CSV
        rows = [{"student_name": "Bob Jones", "student_id": "sid-2"}]
        with patch("backend.services.assistant_tools_student._load_roster",
                   return_value=[]), \
             patch("backend.services.assistant_tools_student._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_student._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in n.lower()), \
             patch("backend.services.assistant_tools_student._load_accommodations",
                   return_value={}):
            result = get_student_accommodations("Bob", teacher_id=TID)

        assert result["student_id"] == "sid-2"


# ──────────────────────────────────────────────────────────────────
# get_student_streak
# ──────────────────────────────────────────────────────────────────


class TestGetStudentStreak:
    @staticmethod
    def _row(name="Alice", date="2026-05-01", score=80, assignment="Q1"):
        return {
            "student_name": name, "date": date, "score": score,
            "assignment": assignment,
        }

    def test_empty_student_name_returns_error(self):
        from backend.services.assistant_tools_student import get_student_streak
        result = get_student_streak("", teacher_id=TID)
        assert "error" in result
        assert "student_name is required" in result["error"]

    def test_no_grades_returns_error(self):
        from backend.services.assistant_tools_student import get_student_streak
        with patch("backend.services.assistant_tools_student._load_master_csv",
                   return_value=[]):
            result = get_student_streak("Alice", teacher_id=TID)
        assert "error" in result
        assert "No grades found" in result["error"]

    def test_improving_streak(self):
        from backend.services.assistant_tools_student import get_student_streak
        rows = [
            self._row(date="2026-01-01", score=60),
            self._row(date="2026-02-01", score=70),
            self._row(date="2026-03-01", score=80),
            self._row(date="2026-04-01", score=90),
        ]
        with patch("backend.services.assistant_tools_student._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_student._fuzzy_name_match",
                   return_value=True):
            result = get_student_streak("Alice", teacher_id=TID)

        assert result["current_streak"] == "improving"
        # Streak count grows by 1 each step (3 transitions: 60→70, 70→80, 80→90)
        assert result["improving_streak"] == 3
        assert result["declining_streak"] == 0
        # History entries have direction markers
        assert result["history"][1]["direction"] == "up"
        assert result["history"][1]["change"] == "+10"

    def test_declining_streak(self):
        from backend.services.assistant_tools_student import get_student_streak
        rows = [
            self._row(date="2026-01-01", score=95),
            self._row(date="2026-02-01", score=85),
            self._row(date="2026-03-01", score=75),
        ]
        with patch("backend.services.assistant_tools_student._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_student._fuzzy_name_match",
                   return_value=True):
            result = get_student_streak("Alice", teacher_id=TID)

        assert result["current_streak"] == "declining"
        assert result["declining_streak"] == 2
        assert result["improving_streak"] == 0
        assert result["history"][1]["direction"] == "down"
        assert result["history"][1]["change"] == "-10"

    def test_stable_breaks_streak(self):
        from backend.services.assistant_tools_student import get_student_streak
        rows = [
            self._row(date="2026-01-01", score=80),
            self._row(date="2026-02-01", score=85),
            self._row(date="2026-03-01", score=85),  # tie → resets streak
        ]
        with patch("backend.services.assistant_tools_student._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_student._fuzzy_name_match",
                   return_value=True):
            result = get_student_streak("Alice", teacher_id=TID)

        assert result["current_streak"] == "stable"
        assert result["improving_streak"] == 0
        assert result["declining_streak"] == 0

    def test_streak_history_sorted_by_date(self):
        from backend.services.assistant_tools_student import get_student_streak
        # Out-of-order input
        rows = [
            self._row(date="2026-03-01", score=80, assignment="Q3"),
            self._row(date="2026-01-01", score=60, assignment="Q1"),
            self._row(date="2026-02-01", score=70, assignment="Q2"),
        ]
        with patch("backend.services.assistant_tools_student._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_student._fuzzy_name_match",
                   return_value=True):
            result = get_student_streak("Alice", teacher_id=TID)
        # History sorted by date asc
        dates = [h["date"] for h in result["history"]]
        assert dates == ["2026-01-01", "2026-02-01", "2026-03-01"]

    def test_first_entry_has_no_direction(self):
        """The first entry can't compare to a prior score, so it has no
        direction/change keys."""
        from backend.services.assistant_tools_student import get_student_streak
        rows = [self._row(score=80)]
        with patch("backend.services.assistant_tools_student._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_student._fuzzy_name_match",
                   return_value=True):
            result = get_student_streak("Alice", teacher_id=TID)
        first = result["history"][0]
        assert "direction" not in first
        assert "change" not in first

    def test_average_calculated(self):
        from backend.services.assistant_tools_student import get_student_streak
        rows = [
            self._row(date="2026-01-01", score=70),
            self._row(date="2026-02-01", score=80),
            self._row(date="2026-03-01", score=90),
        ]
        with patch("backend.services.assistant_tools_student._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_student._fuzzy_name_match",
                   return_value=True):
            result = get_student_streak("Alice", teacher_id=TID)
        assert result["average"] == 80.0


# ──────────────────────────────────────────────────────────────────
# _find_all_student_files (real CSV fixtures)
# ──────────────────────────────────────────────────────────────────


class TestFindAllStudentFiles:
    def test_finds_focus_format_with_student_column(self, tmp_path):
        """Focus SIS format: column 'Student' with 'Last, First'."""
        from backend.services.assistant_tools_student import _find_all_student_files

        period_dir = tmp_path / "periods"
        period_dir.mkdir()
        with open(period_dir / "p1.csv", 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["Student", "Student ID"])
            writer.writeheader()
            writer.writerow({"Student": "Smith, Alice", "Student ID": "sid-1"})
            writer.writerow({"Student": "Jones, Bob", "Student ID": "sid-2"})

        with patch("backend.services.assistant_tools_student._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in n.lower()):
            results = _find_all_student_files("Alice", [(str(period_dir), "periods")])

        assert len(results) == 1
        matched_name, filepath, label = results[0]
        # _parse_csv_name normalizes "Smith, Alice" → "Alice Smith"
        assert "Alice Smith" in matched_name
        assert filepath.endswith("p1.csv")

    def test_finds_clever_format_with_first_last_columns(self, tmp_path):
        """Clever format: separate first_name / last_name columns."""
        from backend.services.assistant_tools_student import _find_all_student_files

        rosters_dir = tmp_path / "rosters"
        rosters_dir.mkdir()
        with open(rosters_dir / "section1.csv", 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["first_name", "last_name", "student_id"])
            writer.writeheader()
            writer.writerow({"first_name": "Carol", "last_name": "Davis", "student_id": "sid-3"})

        with patch("backend.services.assistant_tools_student._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in n.lower()):
            results = _find_all_student_files("Carol", [(str(rosters_dir), "rosters")])

        assert len(results) == 1
        assert "Carol Davis" in results[0][0]

    def test_uses_meta_json_for_period_label(self, tmp_path):
        """When a sibling .meta.json exists for a period CSV, label uses
        period_name from the meta file."""
        from backend.services.assistant_tools_student import _find_all_student_files

        period_dir = tmp_path / "periods"
        period_dir.mkdir()
        with open(period_dir / "raw_filename.csv", 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["Student"])
            writer.writeheader()
            writer.writerow({"Student": "Smith, Alice"})
        with open(period_dir / "raw_filename.meta.json", 'w') as f:
            json.dump({"period_name": "Period 3 Honors"}, f)

        with patch("backend.services.assistant_tools_student._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in n.lower()):
            results = _find_all_student_files("Alice", [(str(period_dir), "periods")])

        assert results[0][2] == "Period 3 Honors"

    def test_skips_non_csv_files(self, tmp_path):
        from backend.services.assistant_tools_student import _find_all_student_files
        period_dir = tmp_path / "periods"
        period_dir.mkdir()
        # Non-CSV files
        with open(period_dir / "ignore.txt", 'w') as f:
            f.write("not csv")
        with open(period_dir / "ignore.json", 'w') as f:
            json.dump({}, f)

        with patch("backend.services.assistant_tools_student._fuzzy_name_match",
                   return_value=True):
            results = _find_all_student_files("Anyone", [(str(period_dir), "periods")])
        assert results == []

    def test_returns_empty_when_dir_missing(self, tmp_path):
        from backend.services.assistant_tools_student import _find_all_student_files
        results = _find_all_student_files(
            "Anyone", [(str(tmp_path / "nonexistent"), "periods")]
        )
        assert results == []


# ──────────────────────────────────────────────────────────────────
# _remove_student_from_csv (real CSV mutation)
# ──────────────────────────────────────────────────────────────────


class TestRemoveStudentFromCsv:
    def test_removes_focus_format_row(self, tmp_path):
        from backend.services.assistant_tools_student import _remove_student_from_csv
        path = tmp_path / "p1.csv"
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["Student", "Student ID"])
            writer.writeheader()
            writer.writerow({"Student": "Smith, Alice", "Student ID": "sid-1"})
            writer.writerow({"Student": "Jones, Bob", "Student ID": "sid-2"})

        with patch("backend.services.assistant_tools_student._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in n.lower()):
            removed, remaining = _remove_student_from_csv("Alice", str(path))

        assert removed == 1
        assert remaining == 1
        # Re-read file to confirm Alice is gone
        with open(path) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["Student"] == "Jones, Bob"

    def test_removes_clever_format_row(self, tmp_path):
        from backend.services.assistant_tools_student import _remove_student_from_csv
        path = tmp_path / "section.csv"
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["first_name", "last_name", "id"])
            writer.writeheader()
            writer.writerow({"first_name": "Carol", "last_name": "Davis", "id": "sid-3"})
            writer.writerow({"first_name": "Dan", "last_name": "Eaton", "id": "sid-4"})

        with patch("backend.services.assistant_tools_student._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in n.lower()):
            removed, remaining = _remove_student_from_csv("Carol", str(path))

        assert removed == 1
        assert remaining == 1
        with open(path) as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["first_name"] == "Dan"

    def test_no_match_returns_zero_removed(self, tmp_path):
        from backend.services.assistant_tools_student import _remove_student_from_csv
        path = tmp_path / "p1.csv"
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["Student"])
            writer.writeheader()
            writer.writerow({"Student": "Smith, Alice"})

        with patch("backend.services.assistant_tools_student._fuzzy_name_match",
                   return_value=False):
            removed, remaining = _remove_student_from_csv("Ghost", str(path))

        assert removed == 0
        assert remaining == 1


# ──────────────────────────────────────────────────────────────────
# require_teacher_id contract pin
# ──────────────────────────────────────────────────────────────────


class TestTeacherIdRequired:
    def test_get_student_accommodations_empty_raises(self):
        from backend.services.assistant_tools_student import get_student_accommodations
        with pytest.raises(ValueError, match="teacher_id is required"):
            get_student_accommodations("Alice", teacher_id="")

    def test_get_student_streak_empty_raises(self):
        from backend.services.assistant_tools_student import get_student_streak
        with pytest.raises(ValueError, match="teacher_id is required"):
            get_student_streak("Alice", teacher_id="")

    def test_remove_student_from_roster_empty_raises(self):
        from backend.services.assistant_tools_student import remove_student_from_roster
        with pytest.raises(ValueError, match="teacher_id is required"):
            remove_student_from_roster("Alice", teacher_id="")

    def test_export_student_data_empty_raises(self):
        from backend.services.assistant_tools_student import export_student_data
        with pytest.raises(ValueError, match="teacher_id is required"):
            export_student_data("Alice", teacher_id="")
