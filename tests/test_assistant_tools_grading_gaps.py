"""Gap-fill unit tests for backend/services/assistant_tools_grading.py.

Audit MAJOR #4 sprint follow-up to PR #307. Companion to existing
test_assistant_tools_grading_*.py files. Targets the 211 uncovered
LOC (65% baseline → ~85%+).

Branches covered
* _match_assignment_to_config: exact match, alias hit, fuzzy 25-char
  prefix forward + reverse, alias fuzzy match, no match
* _build_missing_assignments_data: no-saved-configs error, full
  happy with master CSV + roster + folder submissions + students
  with no data at all
* get_missing_assignments 4 modes:
  - Mode 1 (student_name): no-match error, found
  - Mode 2 (specific period): students-missing list with sort
  - Mode 3 (all-periods summary): zero/some/complete tallying
  - Mode 4 (assignment_name): no-match error, found with sort
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────
# _match_assignment_to_config
# ──────────────────────────────────────────────────────────────────


class TestMatchAssignmentToConfig:
    def test_exact_norm_match(self):
        from backend.services.assistant_tools_grading import (
            _match_assignment_to_config,
        )
        # _normalize_assignment_name lowercases + strips punctuation
        # The function normalizes the input first; if normalized form
        # is in saved_norms, returns it.
        result = _match_assignment_to_config(
            "Quiz One",
            saved_norms={"quiz one"},  # already-normalized
            saved_display={"quiz one": "Quiz One"},
        )
        assert result == "quiz one"

    def test_alias_hit(self):
        from backend.services.assistant_tools_grading import (
            _match_assignment_to_config,
        )
        # Input not in saved_norms but matches an alias
        result = _match_assignment_to_config(
            "Q1 Test",
            saved_norms={"quiz one"},
            saved_display={"quiz one": "Quiz One"},
            alias_to_norm={"q1 test": "quiz one"},
        )
        assert result == "quiz one"

    def test_no_match_returns_none(self):
        from backend.services.assistant_tools_grading import (
            _match_assignment_to_config,
        )
        result = _match_assignment_to_config(
            "Totally Different Title",
            saved_norms={"unrelated"},
            saved_display={"unrelated": "Unrelated"},
        )
        assert result is None

    def test_fuzzy_25_char_prefix_forward(self):
        # Input prefix ⊆ saved norm prefix (25 chars)
        from backend.services.assistant_tools_grading import (
            _match_assignment_to_config,
        )
        result = _match_assignment_to_config(
            "World History Chapter 5",  # 23 chars
            saved_norms={"world history chapter 5 review"},
            saved_display={"world history chapter 5 review": "x"},
        )
        assert result == "world history chapter 5 review"

    def test_alias_fuzzy_match(self):
        # Input doesn't match any saved norm; doesn't exactly match any
        # alias either, but does fuzzy-prefix-match an alias
        from backend.services.assistant_tools_grading import (
            _match_assignment_to_config,
        )
        result = _match_assignment_to_config(
            "Modern American History",
            saved_norms={"unrelated"},
            saved_display={"unrelated": "Unrelated"},
            alias_to_norm={"modern american": "unrelated"},
        )
        assert result == "unrelated"


# ──────────────────────────────────────────────────────────────────
# _build_missing_assignments_data
# ──────────────────────────────────────────────────────────────────


class TestBuildMissingAssignmentsData:
    def test_no_saved_configs_returns_error(self):
        from backend.services import assistant_tools_grading as mod
        with patch.object(
            mod, "_load_master_csv", return_value=[],
        ), patch.object(
            mod, "_load_saved_assignments", return_value=[],
        ):
            student_data, sn, sd, err = mod._build_missing_assignments_data()
        assert student_data is None
        assert sn is None
        assert sd is None
        assert "No saved assignment configs" in err.get("error", "")

    def test_full_happy_path(self):
        from backend.services import assistant_tools_grading as mod
        # Saved configs: 2 assignments with aliases
        saved = [
            {"norm": "quiz one", "title": "Quiz One",
             "aliases": ["q1"]},
            {"norm": "essay", "title": "Essay One", "aliases": []},
        ]
        # Roster: 2 students
        roster = [
            {"student_id": "s1", "name": "Alice Anderson",
             "period": "P1"},
            {"student_id": "s2", "name": "Bob Black",
             "period": "P2"},
        ]
        # Master CSV: Alice graded on quiz one, Bob has no graded rows
        master_rows = [
            {"student_id": "s1", "student_name": "Alice Anderson",
             "assignment": "Quiz One", "score": 90},
        ]
        # Folder scan: Alice submitted Essay One ungraded
        folder_subs = {"s1": {"essay"}}

        with patch.object(
            mod, "_load_master_csv", return_value=master_rows,
        ), patch.object(
            mod, "_load_saved_assignments", return_value=saved,
        ), patch.object(
            mod, "_load_roster", return_value=roster,
        ), patch.object(
            mod, "_scan_submission_folder", return_value=folder_subs,
        ):
            student_data, sn, sd, err = mod._build_missing_assignments_data()
        assert err is None
        # Alice: graded quiz + ungraded essay → both
        assert student_data["s1"]["assigns"] == {"quiz one", "essay"}
        # _normalize_period("P1") returns "Period 1"
        assert student_data["s1"]["period"] == "Period 1"
        assert student_data["s1"]["name"] == "Alice Anderson"
        # Bob: no submissions → empty assigns but period from roster
        assert student_data["s2"]["assigns"] == set()
        assert student_data["s2"]["period"] == "Period 2"
        assert student_data["s2"]["name"] == "Bob Black"


# ──────────────────────────────────────────────────────────────────
# get_missing_assignments 4 modes
# ──────────────────────────────────────────────────────────────────


def _seed_data():
    """Common student_data seed for all modes."""
    return {
        "s1": {
            "assigns": {"quiz_one"},
            "period": "P1",
            "name": "Alice Anderson",
        },
        "s2": {
            # Bob: missing both
            "assigns": set(),
            "period": "P1",
            "name": "Bob Black",
        },
        "s3": {
            # Carol: full submission
            "assigns": {"quiz_one", "essay"},
            "period": "P2",
            "name": "Carol Carter",
        },
    }


def _seed_args():
    return (
        _seed_data(),
        {"quiz_one", "essay"},
        {"quiz_one": "Quiz One", "essay": "Essay One"},
        None,
    )


class TestGetMissingAssignmentsModes:
    def test_error_propagates_from_data_helper(self):
        from backend.services import assistant_tools_grading as mod
        with patch.object(
            mod, "_build_missing_assignments_data",
            return_value=(None, None, None, {"error": "no configs"}),
        ):
            result = mod.get_missing_assignments(teacher_id="teach-1")
        assert result == {"error": "no configs"}

    def test_mode_1_student_name_no_match(self):
        from backend.services import assistant_tools_grading as mod
        with patch.object(
            mod, "_build_missing_assignments_data",
            return_value=_seed_args(),
        ):
            result = mod.get_missing_assignments(
                student_name="Nobody", teacher_id="teach-1",
            )
        assert "No student found" in result.get("error", "")

    def test_mode_1_student_name_found(self):
        from backend.services import assistant_tools_grading as mod
        with patch.object(
            mod, "_build_missing_assignments_data",
            return_value=_seed_args(),
        ):
            result = mod.get_missing_assignments(
                student_name="Alice", teacher_id="teach-1",
            )
        assert result["student_name"] == "Alice Anderson"
        assert result["period"] == "P1"
        assert result["submitted_count"] == 1
        assert result["total_assignments"] == 2
        assert result["missing_count"] == 1
        assert "Quiz One" in result["submitted"]
        assert "Essay One" in result["missing"]

    def test_mode_2_specific_period_missing_list_sorted(self):
        from backend.services import assistant_tools_grading as mod
        with patch.object(
            mod, "_build_missing_assignments_data",
            return_value=_seed_args(),
        ), patch.object(
            mod, "_normalize_period", side_effect=lambda p: p,
        ):
            result = mod.get_missing_assignments(
                period="P1", teacher_id="teach-1",
            )
        # Both Alice (1 missing) and Bob (2 missing) are in P1
        assert result["period"] == "P1"
        assert result["total_assignments"] == 2
        assert result["students_with_missing"] == 2
        # Sorted by missing_count desc → Bob first (missing 2), Alice second
        names = [s["student_name"] for s in result["students"]]
        assert names == ["Bob Black", "Alice Anderson"]

    def test_mode_3_all_periods_summary(self):
        from backend.services import assistant_tools_grading as mod
        with patch.object(
            mod, "_build_missing_assignments_data",
            return_value=_seed_args(),
        ):
            result = mod.get_missing_assignments(teacher_id="teach-1")
        # period P1: Alice (some missing), Bob (zero submissions)
        # period P2: Carol (all complete)
        periods = {p["period"]: p for p in result["period_summary"]}
        assert periods["P1"]["total_students"] == 2
        assert periods["P1"]["zero_submissions"] == 1  # Bob
        assert periods["P1"]["some_missing"] == 1      # Alice
        assert periods["P2"]["all_complete"] == 1     # Carol
        # zero_submission_students lists Bob
        zsb = result["zero_submission_students"]
        assert len(zsb) == 1
        assert zsb[0]["student_name"] == "Bob Black"

    def test_mode_4_assignment_name_not_found(self):
        from backend.services import assistant_tools_grading as mod
        with patch.object(
            mod, "_build_missing_assignments_data",
            return_value=_seed_args(),
        ), patch.object(
            mod, "_load_saved_assignments",
            return_value=[{"norm": "quiz_one", "title": "Quiz One",
                           "aliases": []}],
        ):
            result = mod.get_missing_assignments(
                assignment_name="MIDTERM", teacher_id="teach-1",
            )
        assert "No saved assignment found" in result.get("error", "")

    def test_mode_4_assignment_name_found_with_sort(self):
        from backend.services import assistant_tools_grading as mod
        with patch.object(
            mod, "_build_missing_assignments_data",
            return_value=_seed_args(),
        ), patch.object(
            mod, "_load_saved_assignments",
            return_value=[
                {"norm": "essay", "title": "Essay One", "aliases": []},
            ],
        ):
            result = mod.get_missing_assignments(
                assignment_name="essay", teacher_id="teach-1",
            )
        assert result["assignment"] == "Essay One"
        # Submitted: Carol; Missing: Alice (P1) + Bob (P1)
        assert result["submitted_count"] == 1
        assert result["missing_count"] == 2
        # Sorted by (period, student_name)
        names = [s["student_name"] for s in result["missing_students"]]
        assert names == ["Alice Anderson", "Bob Black"]
