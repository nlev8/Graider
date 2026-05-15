"""Gap-fill tests for backend/services/assistant_tools_grading.py.

Audit MAJOR #4 sprint follow-up to PR #333. Companion to existing
`tests/test_assistant_tools_grading*.py`. Covered here:

* `_scan_submission_folder`: unsupported extension skip (line 119),
  empty filename-parts skip (line 133)
* `compare_periods` roster lookup + empty-breakdown skip (749,
  783-789)
* `scan_submissions_folder` non-file filepath skip (874)
* `get_missing_assignments` mode 3 + mode 4 missing-period skip
  (1058, 1102)

Deferred (need fixtures with full row schema OR fuzzy/Counter
state setup — better covered by characterization tests):

* `get_student_summary` student_id filter + longest-name display
  (lines 304-306) — see `tests/characterization/test_query_grades_golden.py`
  and `tests/test_grading_routes_unit.py`

Closed by #348 (2026-05-15):

* `scan_submissions_folder` prefix-fuzzy graded match (944-945) and
  display_name fallback (957) — see `TestScanSubmissionsFolderIssue348`
  below.

Per dual-rate-limit precedent: test-only PR merging on green CI.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


MODULE = "backend.services.assistant_tools_grading"


# ──────────────────────────────────────────────────────────────────
# _scan_submission_folder edge skips
# ──────────────────────────────────────────────────────────────────


class TestScanSubmissionFolderSkips:
    def test_unsupported_extension_skipped(self, tmp_path):
        from backend.services.assistant_tools_grading import (
            _scan_submission_folder,
        )

        folder = tmp_path / "assignments"
        folder.mkdir()
        (folder / "Alice_Smith_Quiz.unsupported_ext").touch()
        # File present but extension not in supported set → line 119 skip

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
        # File skipped → no result for sid-1
        assert "sid-1" not in result

    def test_empty_filename_parts_skipped(self, tmp_path):
        from backend.services.assistant_tools_grading import (
            _scan_submission_folder,
        )

        folder = tmp_path / "assignments"
        folder.mkdir()
        # Whitespace in parts → all stripped to empty → line 132-133 skip
        (folder / "_ _ _.docx").touch()
        # Also test single underscore (parts < 3)
        (folder / "Just_File.docx").touch()

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


# ──────────────────────────────────────────────────────────────────
# get_student_summary student_id filter + longest-name display
# ──────────────────────────────────────────────────────────────────


class TestGetGradeHistoryNameResolution:
    """Lines 300-306 require full row schema (content/completeness/
    writing/effort/letter_grade fields). Adequately covered by
    existing tests/characterization/test_query_grades_golden.py and
    test_grading_routes_unit.py — skipping here to avoid brittle
    fixture-shape coupling."""
    pass


# ──────────────────────────────────────────────────────────────────
# compare_periods roster + breakdown loop
# ──────────────────────────────────────────────────────────────────


class TestCompareClassPeriodsBranches:
    def test_full_pipeline_with_breakdown_and_roster(self):
        # Lines 749 (roster_by_period), 784-789 (breakdown iteration)
        from backend.services.assistant_tools_grading import (
            compare_periods,
        )

        # Build results with breakdown data. Carol's row has an empty
        # breakdown to exercise the `if bd:` falsy branch at production
        # line 783 (the category-aggregation loop must skip her).
        results = [
            {"student_name": "Alice", "period": "P1",
             "score": 90, "assignment": "Quiz",
             "breakdown": {"content": 23, "completeness": 22,
                           "writing": 18, "effort": 15}},
            {"student_name": "Bob", "period": "P1",
             "score": 80, "assignment": "Quiz",
             "breakdown": {"content": 20, "completeness": 20,
                           "writing": 20, "effort": 20}},
            {"student_name": "Carol", "period": "P1",
             "score": 85, "assignment": "Quiz",
             "breakdown": {}},  # empty → if bd: falsy → skipped
        ]
        roster = [
            {"student_id": "s1", "name": "Alice", "period": "P1"},
            {"student_id": "s2", "name": "Bob", "period": "P1"},
            {"student_id": "s3", "name": "Carol", "period": "P1"},
        ]
        with patch(f"{MODULE}._load_results", return_value=results), \
             patch(f"{MODULE}._load_roster", return_value=roster):
            result = compare_periods(teacher_id="t")

        # Period data populated with category averages
        assert "periods" in result
        p1 = result["periods"][0]
        assert "category_averages" in p1
        assert len(p1["category_averages"]) == 4
        # Roster count (3) == graded count (3). Carol's empty breakdown
        # was correctly skipped — averages computed from Alice+Bob only:
        # content = (23+20)/2 = 21.5, NOT (23+20+0)/3 = 14.3
        assert p1["category_averages"]["content"] == 21.5
        assert p1["student_count"] == 3
        assert p1["students_with_grades"] == 3


# ──────────────────────────────────────────────────────────────────
# scan_submissions_folder non-file + display fallback
# ──────────────────────────────────────────────────────────────────


class TestScanSubmissionsFolderRemainingEdges:
    def test_non_file_filepath_skipped(self, tmp_path, monkeypatch):
        # Line 874: filepath is_file() False → skipped.
        # The directory must have a parseable 3-part underscored name
        # so it WOULD parse if is_file() check were missing — prior
        # "subdir.docx" had only 1 part and would have been rejected
        # by the later `len(parts) < 3` check regardless, making the
        # test vacuous.
        from backend.services.assistant_tools_grading import (
            scan_submissions_folder,
        )
        import json

        folder = tmp_path / "assignments"
        folder.mkdir()
        # Directory shaped like a valid submission filename — would
        # parse to Bob/Jones/Quiz if is_file() check were broken.
        (folder / "Bob_Jones_Quiz.docx").mkdir()
        # Real file for context
        (folder / "Alice_Smith_Quiz.docx").touch()

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
            result = scan_submissions_folder(teacher_id="t")

        # The directory was filtered (is_file=False) — only Alice's
        # real file was parsed. If is_file() check were missing, Bob
        # would also appear → unique_students == 2.
        assert "error" not in result
        assert result["total_files"] == 1
        assert result["unique_students"] == 1


# ──────────────────────────────────────────────────────────────────
# Issue #348: prefix-fuzzy graded match + display_name fallback
# ──────────────────────────────────────────────────────────────────


class TestScanSubmissionsFolderIssue348:
    """Coverage gap-fill for two branches in `scan_submissions_folder`:

      * Lines 944-945 — `ga.startswith(_anorm) or _anorm.startswith(ga)`
        fires when a student's graded assignment norm is a prefix of
        (or prefixed by) the staged filename's assignment norm.
      * Line 957 — `display_name = assignment_norm` fallback when the
        raw_parts comprehension finds no matching entry. In production
        flow this is defensive dead code (the comprehension can only
        come up empty if `_normalize_assignment_name` is non-idempotent
        between Phase 2 and Phase 5). Exercised here via a side_effect
        mock that returns different normalizations across calls — the
        test pins the safety-net string so a future refactor that
        removes the fallback breaks the assertion intentionally.
    """

    def test_prefix_fuzzy_graded_match_counts_submission_as_graded(
        self, tmp_path,
    ):
        """Graded result `assignment="Quiz"` (`_anorm="quiz"`) marks
        the staged file `Alice_Smith_Quiz1.docx` (`_anorm="quiz1"`) as
        graded via the `_anorm.startswith(ga)` branch at line 944."""
        from backend.services.assistant_tools_grading import (
            scan_submissions_folder,
        )
        import json

        folder = tmp_path / "assignments"
        folder.mkdir()
        (folder / "Alice_Smith_Quiz1.docx").touch()

        settings_path = tmp_path / ".graider_settings.json"
        settings_path.write_text(json.dumps(
            {"config": {"assignments_folder": str(folder)}}
        ))

        # Graded result whose normalized assignment ("quiz") is a strict
        # prefix of the file's normalized assignment ("quiz1"). The
        # exact-membership check at line 941 fails ("quiz1" not in
        # {"quiz"}); fuzzy fallback at 944 succeeds via
        # "quiz1".startswith("quiz").
        # NB: graded_by_student is keyed by f"{first}_{last}" lowered,
        # built from the result row's student_name (line 916-918).
        graded_results = [{
            "student_name": "Alice Smith",
            "assignment": "Quiz",
            "score": 90,
        }]

        with patch(f"{MODULE}.os.path.expanduser",
                   side_effect=lambda p: p.replace(
                       "~", str(tmp_path),
                   )), \
             patch("backend.staging.stage_files",
                   return_value={"staging_folder": str(folder),
                                 "duplicates_skipped": 0}), \
             patch(f"{MODULE}._load_results", return_value=graded_results):
            result = scan_submissions_folder(teacher_id="t")

        assert "error" not in result
        # Exactly one assignment group, exactly one submission, and it
        # should be flagged as graded via the fuzzy prefix match.
        assert len(result["top_assignments"]) == 1
        entry = result["top_assignments"][0]
        assert entry["submissions"] == 1
        assert entry["graded"] == 1, (
            "Submission was not counted as graded — prefix-fuzzy match "
            "at scan_submissions_folder:944-945 did not fire. "
            f"entry={entry}"
        )
        assert entry["ungraded"] == 0

    def test_display_name_fallback_when_normalize_non_idempotent(
        self, tmp_path,
    ):
        """Line 957: `display_name = assignment_norm` when no parsed
        entry's normalization equals `assignment_norm`. The only way to
        trigger this in normal flow is for `_normalize_assignment_name`
        to return different values across calls for the same input —
        which doesn't happen with the real implementation but is a
        valid defensive guardrail worth pinning."""
        from backend.services.assistant_tools_grading import (
            scan_submissions_folder,
        )
        import json

        folder = tmp_path / "assignments"
        folder.mkdir()
        (folder / "Alice_Smith_Quiz1.docx").touch()

        settings_path = tmp_path / ".graider_settings.json"
        settings_path.write_text(json.dumps(
            {"config": {"assignments_folder": str(folder)}}
        ))

        # Non-idempotent normalize:
        #   Phase 2 (line 893) → "phase2-norm" (becomes the group key)
        #   Phase 5 (line 953) → "phase5-norm" (mismatches the key)
        # raw_parts comprehension returns [] → fallback at line 957
        # sets display_name = assignment_norm ("phase2-norm").
        calls = {"n": 0}

        def non_idempotent_norm(_s):
            calls["n"] += 1
            # First call is during Phase 2 grouping. All subsequent calls
            # are either Phase 3 results processing (skipped — no
            # results) or Phase 5 raw_parts (return a different value).
            return "phase2-norm" if calls["n"] == 1 else "phase5-norm"

        with patch(f"{MODULE}.os.path.expanduser",
                   side_effect=lambda p: p.replace(
                       "~", str(tmp_path),
                   )), \
             patch("backend.staging.stage_files",
                   return_value={"staging_folder": str(folder),
                                 "duplicates_skipped": 0}), \
             patch(f"{MODULE}._load_results", return_value=[]), \
             patch(f"{MODULE}._normalize_assignment_name",
                   side_effect=non_idempotent_norm):
            result = scan_submissions_folder(teacher_id="t")

        assert "error" not in result
        assert len(result["top_assignments"]) == 1
        # Without the fallback, display_name would be derived from
        # Counter(raw_parts).most_common(1)[0][0] — but raw_parts is
        # empty here, so the safety net hands us the assignment_norm
        # group key instead. Pins the value so removing the fallback
        # breaks this test intentionally.
        assert result["top_assignments"][0]["assignment"] == "phase2-norm"


# ──────────────────────────────────────────────────────────────────
# get_missing_assignments mode 3 + mode 4 missing-period skip
# ──────────────────────────────────────────────────────────────────


class TestGetMissingAssignmentsPeriodSkip:
    def test_mode_3_skips_students_without_period(self):
        # Line 1058: in mode 3 (all-periods summary), students with
        # empty period field are skipped
        from backend.services.assistant_tools_grading import (
            get_missing_assignments,
        )

        student_data = {
            "s1": {"assigns": set(), "period": "P1",
                   "name": "Alice"},
            "s2": {"assigns": set(), "period": "",  # skipped
                   "name": "NoPeriodStudent"},
        }
        with patch(f"{MODULE}._build_missing_assignments_data",
                   return_value=(student_data, {"q1"},
                                 {"q1": "Q1"}, None)):
            result = get_missing_assignments(teacher_id="t")

        # Only P1 in summary (s2 with empty period was skipped)
        periods = [p["period"] for p in result["period_summary"]]
        assert "P1" in periods
        assert "" not in periods

    def test_mode_4_skips_students_without_period(self):
        # Line 1102: in mode 4 (assignment_name), same skip
        from backend.services.assistant_tools_grading import (
            get_missing_assignments,
        )

        student_data = {
            "s1": {"assigns": set(), "period": "P1",
                   "name": "Alice"},
            "s2": {"assigns": set(), "period": "",
                   "name": "NoPeriodStudent"},
        }
        with patch(f"{MODULE}._build_missing_assignments_data",
                   return_value=(student_data, {"q1"},
                                 {"q1": "Q1"}, None)), \
             patch(f"{MODULE}._load_saved_assignments",
                   return_value=[{"norm": "q1", "title": "Q1",
                                  "aliases": []}]):
            result = get_missing_assignments(
                assignment_name="Q1", teacher_id="t",
            )
        # Missing students list excludes s2 (no period)
        names = [s["student_name"] for s in result["missing_students"]]
        assert "Alice" in names
        assert "NoPeriodStudent" not in names
