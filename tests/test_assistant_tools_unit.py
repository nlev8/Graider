"""
Unit tests for backend/services/assistant_tools.py.

Audit MAJOR #4 sprint follow-up to PR #252. Targets the 297 uncovered LOC.

Strategy:
- Pure helpers: direct assertions (_fuzzy_name_match, _extract_first_name,
  _safe_int_score, _normalize_assignment_name, _normalize_period,
  _get_period_assignments).
- Loader/saver functions with file fallback: HOME-redirect fixture +
  patch storage_load/storage_save to None to force the file branch.
  Then re-test with storage hit.
- execute_tool: unknown tool, teacher_id stripping (handler doesn't
  accept teacher_id), audit hook firing.

Pattern matches tests/test_document_generator_unit.py (PR #252) and
tests/test_assistant_tools_grading_unit.py (PR #251).
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch, MagicMock

import pytest


TID = "teacher-alice"


@pytest.fixture
def isolated_dirs(tmp_path, monkeypatch):
    """Redirect HOME + module-level path constants to tmp_path."""
    import backend.services.assistant_tools as at

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(at, "RESULTS_FILE", str(tmp_path / ".graider_results.json"))
    monkeypatch.setattr(at, "SETTINGS_FILE", str(tmp_path / ".graider_global_settings.json"))
    monkeypatch.setattr(at, "ACCOMMODATIONS_DIR", str(tmp_path / ".graider_data" / "accommodations"))
    monkeypatch.setattr(at, "CALENDAR_FILE", str(tmp_path / ".graider_data" / "teaching_calendar.json"))
    monkeypatch.setattr(at, "MEMORY_FILE", str(tmp_path / ".graider_data" / "assistant_memory.json"))
    monkeypatch.setattr(at, "PERIODS_DIR", str(tmp_path / ".graider_data" / "periods"))
    monkeypatch.setattr(at, "ASSIGNMENTS_DIR", str(tmp_path / ".graider_assignments"))

    return tmp_path, at


# ──────────────────────────────────────────────────────────────────
# _fuzzy_name_match
# ──────────────────────────────────────────────────────────────────


class TestFuzzyNameMatch:
    def test_exact_match_case_insensitive(self):
        from backend.services.assistant_tools import _fuzzy_name_match
        assert _fuzzy_name_match("Alice Smith", "alice smith") is True

    def test_word_prefix_match(self):
        """Search 'Luke Lundell' matches 'Luke J Lundell' (middle name in source)."""
        from backend.services.assistant_tools import _fuzzy_name_match
        assert _fuzzy_name_match("Luke Lundell", "Luke J Lundell") is True

    def test_compound_name_with_middle(self):
        """'Dicen Wilkins' matches 'Dicen Macheil Wilkins Reels'."""
        from backend.services.assistant_tools import _fuzzy_name_match
        assert _fuzzy_name_match("Dicen Wilkins", "Dicen Macheil Wilkins Reels") is True

    def test_comma_separated_format(self):
        """'Dicen Wilkins' matches 'Wilkins Reels, Dicen Macheil' (comma format)."""
        from backend.services.assistant_tools import _fuzzy_name_match
        assert _fuzzy_name_match("Dicen Wilkins", "Wilkins Reels, Dicen Macheil") is True

    def test_search_with_extra_middle_drops_to_first_last(self):
        """'Troy Jaxson Mikell' matches 'Troy Mikell' via middle-name tolerance."""
        from backend.services.assistant_tools import _fuzzy_name_match
        assert _fuzzy_name_match("Troy Jaxson Mikell", "Troy Mikell") is True

    def test_no_match(self):
        from backend.services.assistant_tools import _fuzzy_name_match
        assert _fuzzy_name_match("John Smith", "Jane Smith") is False

    def test_empty_search_returns_false(self):
        from backend.services.assistant_tools import _fuzzy_name_match
        assert _fuzzy_name_match("", "Alice Smith") is False

    def test_full_name_with_extra_words_in_source(self):
        """Reverse direction: source has 3+ words, search has 2."""
        from backend.services.assistant_tools import _fuzzy_name_match
        assert _fuzzy_name_match("Alice Smith", "Alice Marie Brown Smith") is True


# ──────────────────────────────────────────────────────────────────
# _extract_first_name
# ──────────────────────────────────────────────────────────────────


class TestExtractFirstName:
    def test_first_last(self):
        from backend.services.assistant_tools import _extract_first_name
        assert _extract_first_name("Alice Smith") == "Alice"

    def test_comma_separated(self):
        from backend.services.assistant_tools import _extract_first_name
        assert _extract_first_name("Smith, Alice Marie") == "Alice"

    def test_semicolon_separated(self):
        from backend.services.assistant_tools import _extract_first_name
        assert _extract_first_name("Smith; Alice Marie") == "Alice"

    def test_multiple_words(self):
        from backend.services.assistant_tools import _extract_first_name
        assert _extract_first_name("Alice Marie Brown Smith") == "Alice"

    def test_default_student(self):
        from backend.services.assistant_tools import _extract_first_name
        assert _extract_first_name("Student") == "Student"

    def test_empty(self):
        from backend.services.assistant_tools import _extract_first_name
        assert _extract_first_name("") == "Student"
        assert _extract_first_name(None) == "Student"


# ──────────────────────────────────────────────────────────────────
# _safe_int_score
# ──────────────────────────────────────────────────────────────────


class TestSafeIntScore:
    def test_int(self):
        from backend.services.assistant_tools import _safe_int_score
        assert _safe_int_score(85) == 85

    def test_float_truncates(self):
        from backend.services.assistant_tools import _safe_int_score
        assert _safe_int_score(85.7) == 85

    def test_string_int(self):
        from backend.services.assistant_tools import _safe_int_score
        assert _safe_int_score("90") == 90

    def test_string_float(self):
        from backend.services.assistant_tools import _safe_int_score
        assert _safe_int_score("85.5") == 85

    def test_none(self):
        from backend.services.assistant_tools import _safe_int_score
        assert _safe_int_score(None) == 0

    def test_empty_string(self):
        from backend.services.assistant_tools import _safe_int_score
        assert _safe_int_score("") == 0

    def test_invalid_string(self):
        from backend.services.assistant_tools import _safe_int_score
        assert _safe_int_score("not a number") == 0

    def test_zero(self):
        from backend.services.assistant_tools import _safe_int_score
        # '0' is falsy so the `if val` check returns 0 — still correct
        assert _safe_int_score(0) == 0


# ──────────────────────────────────────────────────────────────────
# _normalize_assignment_name
# ──────────────────────────────────────────────────────────────────


class TestNormalizeAssignmentName:
    def test_strips_docx(self):
        from backend.services.assistant_tools import _normalize_assignment_name
        assert _normalize_assignment_name("Quiz.docx") == "quiz"
        assert _normalize_assignment_name("Quiz.DOC") == "quiz"

    def test_strips_pdf(self):
        from backend.services.assistant_tools import _normalize_assignment_name
        assert _normalize_assignment_name("Final.pdf") == "final"

    def test_strips_version_at_end(self):
        """The version suffix regex is end-anchored (\\s*\\(\\d+\\)\\s*$).
        Strips trailing (1) from "Quiz (1)" but not when an extension
        is between (the .docx regex is also end-anchored and runs first,
        so "Quiz.docx (1)" — extension not at end — keeps the period and
        the punctuation regex turns it into 'quiz docx')."""
        from backend.services.assistant_tools import _normalize_assignment_name
        assert _normalize_assignment_name("Quiz (1)") == "quiz"
        # Extension-then-version: extension regex doesn't match (not at end),
        # version regex strips the (1), then punctuation cleanup leaves "quiz docx"
        assert _normalize_assignment_name("Quiz.docx (1)") == "quiz docx"

    def test_underscores_to_spaces(self):
        from backend.services.assistant_tools import _normalize_assignment_name
        assert _normalize_assignment_name("Cornell_Notes_Unit_3") == "cornell notes unit 3"

    def test_collapses_whitespace(self):
        from backend.services.assistant_tools import _normalize_assignment_name
        assert _normalize_assignment_name("Multi    Space") == "multi space"

    def test_keeps_ampersand_and_apostrophe(self):
        """Codex round-1 MINOR: previous version checked apostrophe-OR-ampersand;
        now pin the exact normalized output so a regression that drops one but
        not the other would fail."""
        from backend.services.assistant_tools import _normalize_assignment_name
        result = _normalize_assignment_name("Smith's Quiz & Test")
        assert result == "smith's quiz & test"


# ──────────────────────────────────────────────────────────────────
# _normalize_period
# ──────────────────────────────────────────────────────────────────


class TestNormalizePeriod:
    def test_extracts_number(self):
        from backend.services.assistant_tools import _normalize_period
        assert _normalize_period("6") == "Period 6"
        assert _normalize_period("Period 6") == "Period 6"
        assert _normalize_period("PERIOD_6") == "Period 6"
        assert _normalize_period("period 6") == "Period 6"

    def test_all_passthrough(self):
        from backend.services.assistant_tools import _normalize_period
        assert _normalize_period("all") == "all"

    def test_empty(self):
        from backend.services.assistant_tools import _normalize_period
        assert _normalize_period("") == ""
        assert _normalize_period(None) is None

    def test_no_number_returns_input(self):
        from backend.services.assistant_tools import _normalize_period
        # If no digit, returns input unchanged
        assert _normalize_period("no-number") == "no-number"


# ──────────────────────────────────────────────────────────────────
# _get_period_assignments
# ──────────────────────────────────────────────────────────────────


class TestGetPeriodAssignments:
    def test_groups_by_period(self):
        from backend.services.assistant_tools import _get_period_assignments
        rows = [
            {"period": "1", "assignment": "Quiz"},
            {"period": "1", "assignment": "Essay"},
            {"period": "2", "assignment": "Quiz"},
        ]
        period_assigns, display, merge = _get_period_assignments(rows)
        assert "Period 1" in period_assigns
        assert "Period 2" in period_assigns
        assert len(period_assigns["Period 1"]) == 2
        assert len(period_assigns["Period 2"]) == 1

    def test_uses_quarter_fallback(self):
        from backend.services.assistant_tools import _get_period_assignments
        rows = [{"quarter": "1", "assignment": "Quiz"}]  # no period field
        period_assigns, _, _ = _get_period_assignments(rows)
        assert "Period 1" in period_assigns

    def test_skips_empty_assignment_or_period(self):
        from backend.services.assistant_tools import _get_period_assignments
        rows = [
            {"period": "1", "assignment": ""},
            {"period": "", "assignment": "Quiz"},
        ]
        period_assigns, _, _ = _get_period_assignments(rows)
        assert period_assigns == {} or all(len(v) == 0 for v in period_assigns.values())

    def test_keeps_longest_display_name(self):
        """Codex round-1 MINOR: previous version had inputs that normalized
        to different keys, so the test would pass even if longest-name
        replacement broke. Now uses two inputs with the SAME normalized key
        (only differing in raw whitespace + version suffix), so the assertion
        actually tests the longest-display-name selection."""
        from backend.services.assistant_tools import (
            _get_period_assignments, _normalize_assignment_name,
        )
        # Same normalized key, two display forms; longest must win
        short_form = "Quiz"
        long_form = "Quiz Final"  # different normalized key, used for sanity check
        # For SAME normalized key, vary the raw padding/casing/version-suffix
        rows = [
            {"period": "1", "assignment": "  quiz   "},     # raw ugly version
            {"period": "1", "assignment": "Quiz"},          # canonical short
            {"period": "1", "assignment": "Quiz (1)"},      # version-suffix removed → same key
        ]
        _, display, _ = _get_period_assignments(rows)
        norm = _normalize_assignment_name("Quiz")
        # All three normalize to the same key
        assert norm in display
        # Display is the LONGEST raw form provided
        assert display[norm] == "  quiz   "


# ──────────────────────────────────────────────────────────────────
# _load_results / _load_settings / _load_accommodations
# ──────────────────────────────────────────────────────────────────


class TestLoadResults:
    def test_storage_hit_takes_precedence_and_passes_teacher_id(self, isolated_dirs):
        """Codex round-1 MINOR: pins multi-tenant routing — storage_load
        must be called with ('results', TID). A regression to default
        'local-dev' or omitted teacher_id would fail this assertion."""
        _, at = isolated_dirs
        with patch.object(at, "storage_load", return_value=[{"id": 1}]) as mock:
            assert at._load_results(TID) == [{"id": 1}]
        mock.assert_called_once_with("results", TID)

    def test_file_fallback_when_storage_returns_none(self, isolated_dirs):
        tmp, at = isolated_dirs
        # storage returns None, file fallback
        with open(at.RESULTS_FILE, 'w') as f:
            json.dump([{"from": "file"}], f)
        with patch.object(at, "storage_load", return_value=None):
            assert at._load_results(TID) == [{"from": "file"}]

    def test_no_storage_no_file_returns_empty_list(self, isolated_dirs):
        _, at = isolated_dirs
        with patch.object(at, "storage_load", return_value=None):
            assert at._load_results(TID) == []

    def test_storage_unavailable_falls_through(self, isolated_dirs):
        tmp, at = isolated_dirs
        with open(at.RESULTS_FILE, 'w') as f:
            json.dump([{"x": 1}], f)
        with patch.object(at, "storage_load", None):
            assert at._load_results(TID) == [{"x": 1}]

    def test_corrupt_file_returns_empty(self, isolated_dirs):
        tmp, at = isolated_dirs
        with open(at.RESULTS_FILE, 'w') as f:
            f.write("garbage{")
        with patch.object(at, "storage_load", return_value=None):
            assert at._load_results(TID) == []


class TestLoadSettings:
    def test_storage_hit_takes_precedence_and_passes_teacher_id(self, isolated_dirs):
        _, at = isolated_dirs
        with patch.object(at, "storage_load",
                          return_value={"config": {"subject": "Math"}}) as mock:
            assert at._load_settings(TID) == {"config": {"subject": "Math"}}
        mock.assert_called_once_with("settings", TID)

    def test_file_fallback(self, isolated_dirs):
        tmp, at = isolated_dirs
        with open(at.SETTINGS_FILE, 'w') as f:
            json.dump({"config": {"state": "FL"}}, f)
        with patch.object(at, "storage_load", return_value=None):
            assert at._load_settings(TID) == {"config": {"state": "FL"}}

    def test_no_storage_no_file_returns_empty(self, isolated_dirs):
        _, at = isolated_dirs
        with patch.object(at, "storage_load", return_value=None):
            assert at._load_settings(TID) == {}


class TestLoadAccommodations:
    def test_storage_hit_passes_teacher_id(self, isolated_dirs):
        _, at = isolated_dirs
        with patch.object(at, "storage_load",
                          return_value={"sid-1": {"presets": ["IEP"]}}) as mock:
            assert at._load_accommodations(TID) == {"sid-1": {"presets": ["IEP"]}}
        mock.assert_called_once_with("accommodations", TID)

    def test_no_dir_returns_empty(self, isolated_dirs):
        _, at = isolated_dirs
        with patch.object(at, "storage_load", return_value=None):
            assert at._load_accommodations(TID) == {}

    def test_file_dir_aggregates(self, isolated_dirs):
        tmp, at = isolated_dirs
        os.makedirs(at.ACCOMMODATIONS_DIR, exist_ok=True)
        with open(os.path.join(at.ACCOMMODATIONS_DIR, "sid-1.json"), 'w') as f:
            json.dump({"presets": ["IEP"], "notes": "Extended time"}, f)
        with open(os.path.join(at.ACCOMMODATIONS_DIR, "sid-2.json"), 'w') as f:
            json.dump({"presets": ["504"], "notes": ""}, f)
        with patch.object(at, "storage_load", return_value=None):
            result = at._load_accommodations(TID)
        assert "sid-1" in result
        assert result["sid-1"]["presets"] == ["IEP"]
        assert result["sid-1"]["notes"] == "Extended time"
        assert "sid-2" in result


# ──────────────────────────────────────────────────────────────────
# _load_calendar / _save_calendar
# ──────────────────────────────────────────────────────────────────


class TestLoadCalendar:
    def test_storage_hit_passes_teacher_id(self, isolated_dirs):
        _, at = isolated_dirs
        cal = {"scheduled_lessons": [{"id": 1}], "holidays": [], "school_days": {}}
        with patch.object(at, "storage_load", return_value=cal) as mock:
            assert at._load_calendar(TID) == cal
        mock.assert_called_once_with("teaching_calendar", TID)

    def test_default_when_no_storage_no_file(self, isolated_dirs):
        _, at = isolated_dirs
        with patch.object(at, "storage_load", return_value=None):
            result = at._load_calendar(TID)
        assert result == {"scheduled_lessons": [], "holidays": [], "school_days": {}}

    def test_file_fallback(self, isolated_dirs):
        tmp, at = isolated_dirs
        os.makedirs(os.path.dirname(at.CALENDAR_FILE), exist_ok=True)
        with open(at.CALENDAR_FILE, 'w') as f:
            json.dump({"scheduled_lessons": [{"id": 99}]}, f)
        with patch.object(at, "storage_load", return_value=None):
            result = at._load_calendar(TID)
        assert result == {"scheduled_lessons": [{"id": 99}]}


class TestSaveCalendar:
    def test_uses_storage_when_available(self, isolated_dirs):
        _, at = isolated_dirs
        with patch.object(at, "storage_save") as mock_save:
            at._save_calendar({"x": 1}, TID)
        mock_save.assert_called_once_with("teaching_calendar", {"x": 1}, TID)

    def test_file_fallback_when_no_storage(self, isolated_dirs):
        tmp, at = isolated_dirs
        with patch.object(at, "storage_save", None):
            at._save_calendar({"k": "v"}, TID)
        with open(at.CALENDAR_FILE) as f:
            assert json.load(f) == {"k": "v"}


# ──────────────────────────────────────────────────────────────────
# _load_memories / _save_memories
# ──────────────────────────────────────────────────────────────────


class TestLoadMemories:
    def test_storage_list_passes_teacher_id(self, isolated_dirs):
        _, at = isolated_dirs
        with patch.object(at, "storage_load",
                          return_value=["fact1", "fact2"]) as mock:
            assert at._load_memories(TID) == ["fact1", "fact2"]
        mock.assert_called_once_with("assistant_memory", TID)

    def test_storage_non_list_returns_empty(self, isolated_dirs):
        _, at = isolated_dirs
        with patch.object(at, "storage_load", return_value={"not": "a list"}):
            assert at._load_memories(TID) == []

    def test_no_storage_no_file_returns_empty(self, isolated_dirs):
        _, at = isolated_dirs
        with patch.object(at, "storage_load", return_value=None):
            assert at._load_memories(TID) == []

    def test_file_fallback_list(self, isolated_dirs):
        tmp, at = isolated_dirs
        os.makedirs(os.path.dirname(at.MEMORY_FILE), exist_ok=True)
        with open(at.MEMORY_FILE, 'w') as f:
            json.dump(["a", "b", "c"], f)
        with patch.object(at, "storage_load", return_value=None):
            assert at._load_memories(TID) == ["a", "b", "c"]

    def test_corrupt_file_returns_empty(self, isolated_dirs):
        tmp, at = isolated_dirs
        os.makedirs(os.path.dirname(at.MEMORY_FILE), exist_ok=True)
        with open(at.MEMORY_FILE, 'w') as f:
            f.write("garbage")
        with patch.object(at, "storage_load", return_value=None):
            assert at._load_memories(TID) == []


class TestSaveMemories:
    def test_uses_storage(self, isolated_dirs):
        _, at = isolated_dirs
        with patch.object(at, "storage_save") as mock_save:
            at._save_memories(["m1"], TID)
        mock_save.assert_called_once_with("assistant_memory", ["m1"], TID)

    def test_file_fallback(self, isolated_dirs):
        tmp, at = isolated_dirs
        with patch.object(at, "storage_save", None):
            at._save_memories(["x", "y"], TID)
        with open(at.MEMORY_FILE) as f:
            assert json.load(f) == ["x", "y"]


# ──────────────────────────────────────────────────────────────────
# _load_email_config
# ──────────────────────────────────────────────────────────────────


class TestLoadEmailConfig:
    def test_returns_empty_when_missing(self, isolated_dirs):
        from backend.services.assistant_tools import _load_email_config
        # tmp_path home → ~/.graider_email_config.json doesn't exist
        assert _load_email_config() == {}

    def test_reads_from_home_path(self, isolated_dirs, tmp_path):
        from backend.services.assistant_tools import _load_email_config
        config_path = tmp_path / ".graider_email_config.json"
        with open(config_path, 'w') as f:
            json.dump({"teacher_name": "Ms. Alice"}, f)
        result = _load_email_config()
        assert result == {"teacher_name": "Ms. Alice"}


# ──────────────────────────────────────────────────────────────────
# _load_period_class_levels
# ──────────────────────────────────────────────────────────────────


class TestLoadPeriodClassLevels:
    def test_no_dir_returns_empty(self, isolated_dirs):
        _, at = isolated_dirs
        # PERIODS_DIR doesn't exist
        assert at._load_period_class_levels(TID) == {}

    def test_reads_meta_files(self, isolated_dirs):
        tmp, at = isolated_dirs
        os.makedirs(at.PERIODS_DIR, exist_ok=True)
        with open(os.path.join(at.PERIODS_DIR, "p1.csv.meta.json"), 'w') as f:
            json.dump({"period_name": "Period 1", "class_level": "advanced"}, f)
        with open(os.path.join(at.PERIODS_DIR, "p2.csv.meta.json"), 'w') as f:
            json.dump({"period_name": "Period 2", "class_level": "support"}, f)

        result = at._load_period_class_levels(TID)
        assert result["Period 1"] == "advanced"
        assert result["Period 2"] == "support"

    def test_skips_non_meta_files(self, isolated_dirs):
        tmp, at = isolated_dirs
        os.makedirs(at.PERIODS_DIR, exist_ok=True)
        # Period CSV (no meta) should be ignored
        with open(os.path.join(at.PERIODS_DIR, "p1.csv"), 'w') as f:
            f.write("col1,col2\n")

        assert at._load_period_class_levels(TID) == {}

    def test_corrupt_meta_silently_skipped(self, isolated_dirs):
        tmp, at = isolated_dirs
        os.makedirs(at.PERIODS_DIR, exist_ok=True)
        with open(os.path.join(at.PERIODS_DIR, "bad.csv.meta.json"), 'w') as f:
            f.write("garbage")
        # Add a good one too — verify the good one survives
        with open(os.path.join(at.PERIODS_DIR, "good.csv.meta.json"), 'w') as f:
            json.dump({"period_name": "P", "class_level": "standard"}, f)

        result = at._load_period_class_levels(TID)
        assert "P" in result


# ──────────────────────────────────────────────────────────────────
# execute_tool
# ──────────────────────────────────────────────────────────────────


class TestExecuteTool:
    def test_unknown_tool_returns_error(self):
        from backend.services.assistant_tools import execute_tool
        result = execute_tool("not_a_real_tool", {"x": 1})
        assert "error" in result
        assert "Unknown tool" in result["error"]

    def test_handler_called_with_kwargs(self):
        import backend.services.assistant_tools as at
        from backend.services.assistant_tools import execute_tool

        captured = {}

        def fake_handler(arg1=None, arg2=None):
            captured["arg1"] = arg1
            captured["arg2"] = arg2
            return {"ok": True}

        with patch.dict(at.TOOL_HANDLERS, {"fake_tool": fake_handler}):
            result = execute_tool("fake_tool", {"arg1": "x", "arg2": "y"})

        assert result == {"ok": True}
        assert captured == {"arg1": "x", "arg2": "y"}

    def test_teacher_id_stripped_when_handler_does_not_accept(self):
        """execute_tool inspects the handler signature and removes
        teacher_id if it's not a parameter (and there's no **kwargs)."""
        import backend.services.assistant_tools as at
        from backend.services.assistant_tools import execute_tool

        captured = {}

        def handler_no_teacher_id(only_arg=None):
            captured["called_with"] = only_arg
            return {"ok": True}

        with patch.dict(at.TOOL_HANDLERS, {"strip_test": handler_no_teacher_id}):
            result = execute_tool("strip_test", {"only_arg": "v", "teacher_id": TID})

        assert result == {"ok": True}
        assert captured["called_with"] == "v"

    def test_teacher_id_kept_when_handler_accepts(self):
        import backend.services.assistant_tools as at
        from backend.services.assistant_tools import execute_tool

        captured = {}

        def handler_with_teacher_id(only_arg=None, teacher_id=None):
            captured["teacher_id"] = teacher_id
            return {"ok": True}

        with patch.dict(at.TOOL_HANDLERS, {"keep_test": handler_with_teacher_id}):
            execute_tool("keep_test", {"only_arg": "v", "teacher_id": TID})

        assert captured["teacher_id"] == TID

    def test_handler_kwargs_accepts_teacher_id(self):
        """If handler has **kwargs, teacher_id should be passed through."""
        import backend.services.assistant_tools as at
        from backend.services.assistant_tools import execute_tool

        captured = {}

        def handler_kwargs(**kwargs):
            captured.update(kwargs)
            return {"ok": True}

        with patch.dict(at.TOOL_HANDLERS, {"kwargs_test": handler_kwargs}):
            execute_tool("kwargs_test", {"x": 1, "teacher_id": TID})

        assert captured.get("teacher_id") == TID

    def test_handler_exception_returned_as_error(self):
        import backend.services.assistant_tools as at
        from backend.services.assistant_tools import execute_tool

        def buggy(x=None):
            raise RuntimeError("oops")

        with patch.dict(at.TOOL_HANDLERS, {"buggy_tool": buggy}):
            result = execute_tool("buggy_tool", {"x": 1})

        assert "error" in result
        assert "oops" in result["error"]

    def test_audit_invoked_for_data_tools(self):
        """Tools NOT in _STATELESS_TOOLS trigger audit_tool_action."""
        import backend.services.assistant_tools as at
        from backend.services.assistant_tools import execute_tool

        def fake(teacher_id=None):
            return {"ok": True}

        with patch.dict(at.TOOL_HANDLERS, {"data_tool": fake}), \
             patch("backend.utils.compliance.audit_tool_action") as mock_audit:
            execute_tool("data_tool", {"teacher_id": TID})

        mock_audit.assert_called_once_with(TID, "data_tool", "INVOKE")

    def test_stateless_tools_skip_audit(self):
        """Tools in _STATELESS_TOOLS (e.g. grade_math_question) are
        exempt from INVOKE audit even when teacher_id is present."""
        import backend.services.assistant_tools as at
        from backend.services.assistant_tools import execute_tool

        def fake(**kwargs):
            return {"ok": True}

        with patch.dict(at.TOOL_HANDLERS, {"grade_math_question": fake}), \
             patch("backend.utils.compliance.audit_tool_action") as mock_audit:
            execute_tool("grade_math_question", {"teacher_id": TID, "x": 1})

        mock_audit.assert_not_called()
