"""Gap-fill tests for backend/services/assistant_tools_grading.py.

Audit MAJOR #4 sprint follow-up to PR #313. Companion to existing
test_assistant_tools_grading*.py. Targets the 105 missing LOC
(82.8% baseline → 95%+ goal). Bulk of the gap is the two
filesystem-heavy folder scanners:

* `_scan_submission_folder` (lines 77-152, ~75 LOC) — internal
  helper that walks an assignments folder, parses
  `First_Last_Assignment.ext` filenames, and matches them to the
  roster + saved configs.
* `scan_submissions_folder` (lines 837-969) — public tool that
  reads UI settings, calls staging, and returns a top-N summary
  with graded/ungraded breakdown.

Strategy: real tmp_path filesystem fixture so we test the actual
file-walk logic. Mock only `backend.staging.stage_files` so we
control the staging output and `MANIFEST_NAME` skip semantics.

Per `feedback_codex_medium_effort_2026-05-09.md` and
`reference_gemini_cli_codex_fallback.md`: dual-rate-limit
precedent.
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch, MagicMock

import pytest


MODULE = "backend.services.assistant_tools_grading"


# ──────────────────────────────────────────────────────────────────
# _scan_submission_folder
# ──────────────────────────────────────────────────────────────────


class TestScanSubmissionFolder:
    def test_no_folder_in_settings_returns_empty(self):
        from backend.services.assistant_tools_grading import (
            _scan_submission_folder,
        )

        with patch(f"{MODULE}._load_settings",
                   return_value={"config": {"assignments_folder": ""}}):
            result = _scan_submission_folder(
                roster_name_map={}, saved_norms=set(),
                saved_display={}, alias_to_norm={},
            )
        assert result == {}

    def test_nonexistent_folder_returns_empty(self):
        from backend.services.assistant_tools_grading import (
            _scan_submission_folder,
        )

        with patch(f"{MODULE}._load_settings",
                   return_value={"config": {
                       "assignments_folder": "/nonexistent/path/x"}}):
            result = _scan_submission_folder(
                roster_name_map={}, saved_norms=set(),
                saved_display={}, alias_to_norm={},
            )
        assert result == {}

    def test_full_pipeline_first_last_format(self, tmp_path):
        # Real folder + staging mock: roster has "First Last" names;
        # filename is `First_Last_Assignment.docx`
        from backend.services.assistant_tools_grading import (
            _scan_submission_folder,
        )

        folder = tmp_path / "assignments"
        folder.mkdir()
        (folder / "Alice_Smith_Quiz One.docx").touch()
        (folder / "_staging_manifest.json").write_text("{}")  # Skipped
        # Gemini quality-review (MAJOR fold): .txt IS in the
        # production supported set; use .xlsx for an actual
        # unsupported-extension test.
        (folder / "ignore.xlsx").touch()  # Skipped (not in supported set)
        (folder / "Quiz_Bob_Notes.docx").touch()  # parts[1]="Bob" but order is fname_lname so "Quiz" "Bob" → fail to match roster

        from backend.staging import MANIFEST_NAME

        with patch(f"{MODULE}._load_settings",
                   return_value={"config": {
                       "assignments_folder": str(folder)}}), \
             patch("backend.staging.stage_files",
                   return_value={"staging_folder": str(folder),
                                 "duplicates_skipped": 0}), \
             patch(f"{MODULE}._fuzzy_name_match",
                   side_effect=lambda q, n: False), \
             patch(f"{MODULE}._match_assignment_to_config",
                   return_value="quiz_one"):
            result = _scan_submission_folder(
                roster_name_map={"sid-1": "Alice Smith"},
                saved_norms={"quiz_one"},
                saved_display={"quiz_one": "Quiz One"},
                alias_to_norm={},
            )
        assert "sid-1" in result
        assert "quiz_one" in result["sid-1"]

    def test_full_pipeline_last_first_format(self, tmp_path):
        # Roster uses "Last, First Middle" format (Focus SIS)
        from backend.services.assistant_tools_grading import (
            _scan_submission_folder,
        )

        folder = tmp_path / "assignments"
        folder.mkdir()
        (folder / "Alice_Smith_Quiz One.docx").touch()

        with patch(f"{MODULE}._load_settings",
                   return_value={"config": {
                       "assignments_folder": str(folder)}}), \
             patch("backend.staging.stage_files",
                   return_value={"staging_folder": str(folder),
                                 "duplicates_skipped": 0}), \
             patch(f"{MODULE}._match_assignment_to_config",
                   return_value="quiz_one"):
            result = _scan_submission_folder(
                roster_name_map={"sid-1": "Smith, Alice Marie"},
                saved_norms={"quiz_one"},
                saved_display={"quiz_one": "Quiz One"},
                alias_to_norm={},
            )
        assert "sid-1" in result

    def test_full_pipeline_last_semicolon_first(self, tmp_path):
        from backend.services.assistant_tools_grading import (
            _scan_submission_folder,
        )

        folder = tmp_path / "assignments"
        folder.mkdir()
        (folder / "Alice_Smith_Q.docx").touch()

        with patch(f"{MODULE}._load_settings",
                   return_value={"config": {
                       "assignments_folder": str(folder)}}), \
             patch("backend.staging.stage_files",
                   return_value={"staging_folder": str(folder),
                                 "duplicates_skipped": 0}), \
             patch(f"{MODULE}._match_assignment_to_config",
                   return_value="q"):
            result = _scan_submission_folder(
                roster_name_map={"sid-1": "Smith; Alice"},
                saved_norms={"q"},
                saved_display={"q": "Q"},
                alias_to_norm={},
            )
        assert "sid-1" in result

    def test_filename_with_too_few_parts_skipped(self, tmp_path):
        from backend.services.assistant_tools_grading import (
            _scan_submission_folder,
        )

        folder = tmp_path / "assignments"
        folder.mkdir()
        # Only 2 parts → < 3 → skipped
        (folder / "Alice_Smith.docx").touch()

        with patch(f"{MODULE}._load_settings",
                   return_value={"config": {
                       "assignments_folder": str(folder)}}), \
             patch("backend.staging.stage_files",
                   return_value={"staging_folder": str(folder),
                                 "duplicates_skipped": 0}):
            result = _scan_submission_folder(
                roster_name_map={"sid-1": "Alice Smith"},
                saved_norms=set(),
                saved_display={},
                alias_to_norm={},
            )
        assert result == {}

    def test_unmatched_student_falls_through_fuzzy(self, tmp_path):
        # Filename's First/Last don't match exact roster lookup, but
        # fuzzy match is configured to succeed
        from backend.services.assistant_tools_grading import (
            _scan_submission_folder,
        )

        folder = tmp_path / "assignments"
        folder.mkdir()
        (folder / "Alex_Sm_Quiz.docx").touch()

        with patch(f"{MODULE}._load_settings",
                   return_value={"config": {
                       "assignments_folder": str(folder)}}), \
             patch("backend.staging.stage_files",
                   return_value={"staging_folder": str(folder),
                                 "duplicates_skipped": 0}), \
             patch(f"{MODULE}._fuzzy_name_match",
                   side_effect=lambda q, n: "alex" in q.lower()), \
             patch(f"{MODULE}._match_assignment_to_config",
                   return_value="quiz"):
            result = _scan_submission_folder(
                roster_name_map={"sid-99": "Alexander Smithson"},
                saved_norms={"quiz"},
                saved_display={"quiz": "Quiz"},
                alias_to_norm={},
            )
        assert "sid-99" in result

    def test_no_assignment_match_skipped(self, tmp_path):
        from backend.services.assistant_tools_grading import (
            _scan_submission_folder,
        )

        folder = tmp_path / "assignments"
        folder.mkdir()
        (folder / "Alice_Smith_Random.docx").touch()

        with patch(f"{MODULE}._load_settings",
                   return_value={"config": {
                       "assignments_folder": str(folder)}}), \
             patch("backend.staging.stage_files",
                   return_value={"staging_folder": str(folder),
                                 "duplicates_skipped": 0}), \
             patch(f"{MODULE}._match_assignment_to_config",
                   return_value=None):
            result = _scan_submission_folder(
                roster_name_map={"sid-1": "Alice Smith"},
                saved_norms=set(),
                saved_display={},
                alias_to_norm={},
            )
        # Student matched but no assignment match → result is empty
        assert "sid-1" not in result

    def test_staging_exception_falls_back_to_raw_folder(self, tmp_path):
        from backend.services.assistant_tools_grading import (
            _scan_submission_folder,
        )

        folder = tmp_path / "assignments"
        folder.mkdir()
        (folder / "Alice_Smith_Q.docx").touch()

        with patch(f"{MODULE}._load_settings",
                   return_value={"config": {
                       "assignments_folder": str(folder)}}), \
             patch("backend.staging.stage_files",
                   side_effect=RuntimeError("staging failure")), \
             patch(f"{MODULE}._match_assignment_to_config",
                   return_value="q"):
            result = _scan_submission_folder(
                roster_name_map={"sid-1": "Alice Smith"},
                saved_norms={"q"},
                saved_display={"q": "Q"},
                alias_to_norm={},
            )
        # Falls back to raw folder; still finds the submission
        assert "sid-1" in result


# ──────────────────────────────────────────────────────────────────
# scan_submissions_folder
# ──────────────────────────────────────────────────────────────────


class TestScanSubmissionsFolder:
    def test_folder_not_in_ui_settings_falls_back_to_global(self, tmp_path):
        from backend.services.assistant_tools_grading import (
            scan_submissions_folder,
        )

        # No ~/.graider_settings.json → falls back to _load_settings
        # which returns global settings with empty config
        with patch(f"{MODULE}.os.path.expanduser",
                   return_value=str(tmp_path / "no_such.json")), \
             patch(f"{MODULE}._load_settings",
                   return_value={"config": {}}):
            result = scan_submissions_folder(teacher_id="t")
        # Default fallback: ~/Downloads/Graider/Assignments — we patched
        # expanduser globally, so the default path also gets redirected
        # → not a directory → error response
        assert "error" in result

    def test_folder_not_a_dir_returns_error(self, tmp_path, monkeypatch):
        from backend.services.assistant_tools_grading import (
            scan_submissions_folder,
        )

        # Settings JSON exists but folder doesn't
        settings = tmp_path / ".graider_settings.json"
        settings.write_text(json.dumps(
            {"config": {"assignments_folder": "/nonexistent"}}
        ))
        monkeypatch.setenv("HOME", str(tmp_path))
        with patch(f"{MODULE}.os.path.expanduser",
                   side_effect=lambda p: p.replace(
                       "~", str(tmp_path),
                   )):
            result = scan_submissions_folder(teacher_id="t")
        assert "error" in result
        assert "Assignments folder not found" in result["error"]

    def test_full_happy_with_graded_match(self, tmp_path, monkeypatch):
        from backend.services.assistant_tools_grading import (
            scan_submissions_folder,
        )

        folder = tmp_path / "assignments"
        folder.mkdir()
        (folder / "Alice_Smith_QuizOne.docx").touch()
        (folder / "Bob_Jones_QuizOne.docx").touch()
        (folder / "Carol_Davis_Random.docx").touch()
        (folder / "_staging_manifest.json").write_text("{}")  # MANIFEST skip
        (folder / "ignore.txt").touch()  # Not in supported set
        (folder / "noparts.docx").touch()  # Unparseable (no underscores)

        # Settings JSON with the folder configured
        settings_path = tmp_path / ".graider_settings.json"
        settings_path.write_text(json.dumps(
            {"config": {"assignments_folder": str(folder)}}
        ))

        # Pre-graded results: Alice's QuizOne is graded by exact filename
        results = [
            {"filename": "Alice_Smith_QuizOne.docx",
             "student_name": "Alice Smith",
             "assignment": "QuizOne", "score": 90},
            # Bob graded via student_name + assignment match (no filename)
            {"student_name": "Bob Jones", "assignment": "QuizOne",
             "score": 85},
        ]

        with patch(f"{MODULE}.os.path.expanduser",
                   side_effect=lambda p: p.replace(
                       "~", str(tmp_path),
                   )), \
             patch("backend.staging.stage_files",
                   return_value={"staging_folder": str(folder),
                                 "duplicates_skipped": 1}), \
             patch(f"{MODULE}._load_results", return_value=results):
            result = scan_submissions_folder(teacher_id="t")

        assert "error" not in result
        assert result["folder"] == str(folder)
        assert result["duplicates_removed"] == 1
        assert result["unique_students"] >= 2

        # Find the QuizOne row
        quiz_rows = [
            r for r in result["top_assignments"]
            if "Quiz" in r["assignment"]
        ]
        assert len(quiz_rows) >= 1
        # Both Alice + Bob should be marked graded (one via filename,
        # one via student_name+assignment)
        for r in quiz_rows:
            if "Quizone" in r["assignment"].lower() or "QuizOne" in r["assignment"]:
                assert r["graded"] >= 2

        # Unparseable file appears in the unparseable list
        assert "noparts.docx" in result["unparseable_files"]

    def test_assignment_filter_includes_students_list(
        self, tmp_path, monkeypatch,
    ):
        from backend.services.assistant_tools_grading import (
            scan_submissions_folder,
        )

        folder = tmp_path / "assignments"
        folder.mkdir()
        (folder / "Alice_Smith_QuizOne.docx").touch()
        (folder / "Bob_Jones_QuizOne.docx").touch()

        settings_path = tmp_path / ".graider_settings.json"
        settings_path.write_text(json.dumps(
            {"config": {"assignments_folder": str(folder)}}
        ))

        with patch(f"{MODULE}.os.path.expanduser",
                   side_effect=lambda p: p.replace(
                       "~", str(tmp_path),
                   )), \
             patch("backend.staging.stage_files",
                   return_value={"staging_folder": str(folder),
                                 "duplicates_skipped": 0}), \
             patch(f"{MODULE}._load_results", return_value=[]):
            result = scan_submissions_folder(
                teacher_id="t", assignment_filter="quiz",
            )

        # Filter applied → student list included in entry
        assert len(result["top_assignments"]) >= 1
        first = result["top_assignments"][0]
        assert "students" in first
        # Names like "Alice S." per display format
        assert any("Alice" in s for s in first["students"])

    def test_settings_json_read_exception_swallowed(
        self, tmp_path, monkeypatch,
    ):
        # Settings file exists but is invalid JSON → exception swallowed
        from backend.services.assistant_tools_grading import (
            scan_submissions_folder,
        )

        settings_path = tmp_path / ".graider_settings.json"
        settings_path.write_text("{not valid json")

        # Set up the fallback chain: corrupt file → _load_settings →
        # default path which won't exist
        with patch(f"{MODULE}.os.path.expanduser",
                   side_effect=lambda p: p.replace(
                       "~", str(tmp_path),
                   )), \
             patch(f"{MODULE}._load_settings",
                   return_value={"config": {}}):
            result = scan_submissions_folder(teacher_id="t")
        # Hits the "folder not found" error path because all fallbacks
        # resolved to nonexistent paths
        assert "error" in result

    def test_top_n_clamped_between_1_and_25(self, tmp_path):
        # Gemini quality-review (CRITICAL fold): pre-fix seeded
        # only 1 file → production returned max 1 item regardless
        # of top_n value, so the clamping logic could be deleted
        # without breaking the test. Now seed 30 unique
        # assignments and assert exact lengths.
        from backend.services.assistant_tools_grading import (
            scan_submissions_folder,
        )

        folder = tmp_path / "assignments"
        folder.mkdir()
        # 30 unique assignments × 1 submission each
        for i in range(30):
            (folder / f"Student{i}_Last{i}_Quiz{i}.docx").touch()

        settings_path = tmp_path / ".graider_settings.json"
        settings_path.write_text(json.dumps(
            {"config": {"assignments_folder": str(folder)}}
        ))

        with patch(f"{MODULE}.os.path.expanduser",
                   side_effect=lambda p: p.replace(
                       "~", str(tmp_path),
                   )), \
             patch("backend.staging.stage_files",
                   return_value={"staging_folder": str(folder),
                                 "duplicates_skipped": 0}), \
             patch(f"{MODULE}._load_results", return_value=[]):
            # top_n=100 → clamped to 25 (would return 30 if clamp removed)
            r1 = scan_submissions_folder(teacher_id="t", top_n=100)
            assert "error" not in r1
            assert len(r1["top_assignments"]) == 25
            # top_n=-5 → max(-5, 1) = 1 (lower-bound clamp)
            # NOTE: top_n=0 is falsy and triggers the `top_n or 10`
            # default, NOT the lower clamp. So use a negative value
            # to exercise the max(..., 1) branch.
            r2 = scan_submissions_folder(teacher_id="t", top_n=-5)
            assert "error" not in r2
            assert len(r2["top_assignments"]) == 1
            # Bonus: top_n=None → default 10
            r3 = scan_submissions_folder(teacher_id="t", top_n=None)
            assert len(r3["top_assignments"]) == 10

    def test_staging_exception_falls_back_to_raw(self, tmp_path):
        from backend.services.assistant_tools_grading import (
            scan_submissions_folder,
        )

        folder = tmp_path / "assignments"
        folder.mkdir()
        (folder / "Alice_Smith_Q.docx").touch()

        settings_path = tmp_path / ".graider_settings.json"
        settings_path.write_text(json.dumps(
            {"config": {"assignments_folder": str(folder)}}
        ))

        with patch(f"{MODULE}.os.path.expanduser",
                   side_effect=lambda p: p.replace(
                       "~", str(tmp_path),
                   )), \
             patch("backend.staging.stage_files",
                   side_effect=RuntimeError("staging down")), \
             patch(f"{MODULE}._load_results", return_value=[]):
            result = scan_submissions_folder(teacher_id="t")
        # Falls back to raw folder
        assert "error" not in result
        assert result["duplicates_removed"] == 0


# ──────────────────────────────────────────────────────────────────
# _build_missing_assignments_data — additional branches
# ──────────────────────────────────────────────────────────────────


class TestBuildMissingAssignmentsDataMore:
    def test_master_csv_assignment_match_populates(self):
        # Pass 1 master CSV: a row with sid=s1 and assignment=Quiz one
        # → matched into student_data["s1"]["assigns"]
        from backend.services.assistant_tools_grading import (
            _build_missing_assignments_data,
        )

        rows = [{
            "student_id": "s1", "student_name": "Alice Smith",
            "assignment": "Quiz One", "score": 90,
        }]
        saved = [{"norm": "quiz one", "title": "Quiz One",
                  "aliases": []}]
        roster = [{"student_id": "s1", "name": "Alice Smith",
                   "period": "P1"}]

        with patch(f"{MODULE}._load_master_csv", return_value=rows), \
             patch(f"{MODULE}._load_saved_assignments",
                   return_value=saved), \
             patch(f"{MODULE}._load_roster", return_value=roster), \
             patch(f"{MODULE}._scan_submission_folder", return_value={}):
            student_data, sn, sd, err = _build_missing_assignments_data()

        assert err is None
        assert "quiz one" in student_data["s1"]["assigns"]
        # Period set from roster
        assert student_data["s1"]["period"] == "Period 1"
        # Roster name preferred (longer)
        assert student_data["s1"]["name"] == "Alice Smith"

    def test_master_csv_no_sid_skipped(self):
        # Row without student_id (or "UNKNOWN") → skipped in pass 1
        from backend.services.assistant_tools_grading import (
            _build_missing_assignments_data,
        )

        rows = [
            {"student_id": "", "student_name": "No ID",
             "assignment": "Q1", "score": 80},
            {"student_id": "UNKNOWN", "student_name": "Unknown",
             "assignment": "Q1", "score": 75},
        ]
        saved = [{"norm": "q1", "title": "Q1", "aliases": []}]

        with patch(f"{MODULE}._load_master_csv", return_value=rows), \
             patch(f"{MODULE}._load_saved_assignments",
                   return_value=saved), \
             patch(f"{MODULE}._load_roster", return_value=[]), \
             patch(f"{MODULE}._scan_submission_folder", return_value={}):
            student_data, _, _, err = _build_missing_assignments_data()
        # No students survive pass 1 + no roster fallback
        assert student_data == {}

    def test_master_csv_uses_csv_name_when_roster_misses(self):
        # student in master CSV but NOT in roster → uses CSV name as
        # display name (longer-than-existing branch)
        from backend.services.assistant_tools_grading import (
            _build_missing_assignments_data,
        )

        rows = [{
            "student_id": "s1", "student_name": "Alice Smith",
            "assignment": "Quiz", "score": 90,
        }]
        saved = [{"norm": "quiz", "title": "Quiz", "aliases": []}]

        with patch(f"{MODULE}._load_master_csv", return_value=rows), \
             patch(f"{MODULE}._load_saved_assignments",
                   return_value=saved), \
             patch(f"{MODULE}._load_roster", return_value=[]), \
             patch(f"{MODULE}._scan_submission_folder", return_value={}):
            student_data, _, _, err = _build_missing_assignments_data()
        # Name from CSV
        assert student_data["s1"]["name"] == "Alice Smith"

    def test_folder_submissions_propagate(self):
        from backend.services.assistant_tools_grading import (
            _build_missing_assignments_data,
        )

        saved = [{"norm": "q1", "title": "Q1", "aliases": []}]
        roster = [{"student_id": "s1", "name": "Alice Smith",
                   "period": "P2"}]

        with patch(f"{MODULE}._load_master_csv", return_value=[]), \
             patch(f"{MODULE}._load_saved_assignments",
                   return_value=saved), \
             patch(f"{MODULE}._load_roster", return_value=roster), \
             patch(f"{MODULE}._scan_submission_folder",
                   return_value={"s1": {"q1"}}):
            student_data, _, _, err = _build_missing_assignments_data()
        # Folder submission added
        assert "q1" in student_data["s1"]["assigns"]
        # Period from roster
        assert student_data["s1"]["period"] == "Period 2"
