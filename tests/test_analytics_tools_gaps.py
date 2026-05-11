"""Gap-fill tests for backend/services/assistant_tools_analytics.py.

Audit MAJOR #4 sprint follow-up to PR #322. Targets the 22 missing
LOC (92.5% baseline → 100% goal):

* `_compute_trend_direction` <2-scores → "insufficient_data" (line 145)
* `_assignment_stats` no-scores → None (line 162)
* `get_grade_trends` no-rows error (202), no-recent-assignments
  filter empty (237)
* `get_rubric_weakness` no-rows (269), no-rubric-data (291)
* `flag_at_risk_students` no-rows (330), no-scores-skip (345),
  missing-pct branches (371-375), missing flag (398)
* `compare_assignments` no_a / no_b (431, 442)
* `get_grade_distribution` no-rows (483), _dist empty list (495),
  no-valid-scores (545)
* `detect_score_outliers` no-rows (555), <3-scores-skip (574),
  stdev=0-skip (578)

Per dual-rate-limit precedent: test-only PR merging on green CI.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


MODULE = "backend.services.assistant_tools_analytics"


# ──────────────────────────────────────────────────────────────────
# _compute_trend_direction
# ──────────────────────────────────────────────────────────────────


class TestComputeTrendDirection:
    def test_zero_scores_insufficient_data(self):
        from backend.services.assistant_tools_analytics import (
            _compute_trend_direction,
        )
        assert _compute_trend_direction([]) == "insufficient_data"

    def test_one_score_insufficient_data(self):
        from backend.services.assistant_tools_analytics import (
            _compute_trend_direction,
        )
        assert _compute_trend_direction([85]) == "insufficient_data"


# ──────────────────────────────────────────────────────────────────
# _assignment_stats no-scores → None
# ──────────────────────────────────────────────────────────────────


class TestAssignmentStats:
    def test_empty_rows_returns_none(self):
        from backend.services.assistant_tools_analytics import (
            _assignment_stats,
        )
        # Empty list → no scores → None (line 162 early return).
        # The "rows without scores" variant is not a real branch:
        # _safe_int_score returns 0 for missing/invalid, so
        # `scores = [0, 0, ...]` is truthy and stats are returned.
        assert _assignment_stats([]) is None


# ──────────────────────────────────────────────────────────────────
# get_grade_trends no-rows + no-recent
# ──────────────────────────────────────────────────────────────────


class TestGetGradeTrends:
    def test_no_rows_returns_error(self):
        from backend.services.assistant_tools_analytics import (
            get_grade_trends,
        )
        with patch(f"{MODULE}._load_master_csv", return_value=[]):
            result = get_grade_trends(teacher_id="t")
        assert "error" in result
        assert "No grade data" in result["error"]

    def test_student_not_found_returns_error(self):
        from backend.services.assistant_tools_analytics import (
            get_grade_trends,
        )
        rows = [{"student_name": "Alice", "score": 80,
                 "assignment": "Q1", "date": "2026-01-01"}]
        with patch(f"{MODULE}._load_master_csv", return_value=rows), \
             patch(f"{MODULE}._fuzzy_name_match", return_value=False):
            result = get_grade_trends(
                student_name="Nobody", teacher_id="t",
            )
        assert "error" in result
        assert "Nobody" in result["error"]


# ──────────────────────────────────────────────────────────────────
# get_rubric_weakness errors
# ──────────────────────────────────────────────────────────────────


class TestGetRubricWeakness:
    def test_no_rows_error(self):
        from backend.services.assistant_tools_analytics import (
            get_rubric_weakness,
        )
        with patch(f"{MODULE}._load_master_csv", return_value=[]):
            result = get_rubric_weakness(teacher_id="t")
        assert "error" in result
        assert "No grade data" in result["error"]

    def test_no_rubric_data_error(self):
        # Rows present but no category data → rubric error
        from backend.services.assistant_tools_analytics import (
            get_rubric_weakness,
        )
        rows = [
            {"assignment": "Q", "student_name": "Alice", "score": 80}
            # No content/completeness/writing/effort columns
        ]
        with patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = get_rubric_weakness(teacher_id="t")
        assert "error" in result
        assert "rubric category" in result["error"]


# ──────────────────────────────────────────────────────────────────
# flag_at_risk_students - error, signal branches
# ──────────────────────────────────────────────────────────────────


class TestFlagAtRiskStudents:
    def test_no_rows_returns_error(self):
        from backend.services.assistant_tools_analytics import (
            flag_at_risk_students,
        )
        with patch(f"{MODULE}._load_master_csv", return_value=[]):
            result = flag_at_risk_students(teacher_id="t")
        assert "error" in result

    def test_high_missing_assignment_pct_triggers_flag(self):
        # 4 unique assignments class-wide, student has 1 → 75% missing
        # → 20-point risk + low avg + declining triggers risk
        from backend.services.assistant_tools_analytics import (
            flag_at_risk_students,
        )
        rows = [
            # class-wide assignments
            {"student_name": "Bob", "score": 85, "assignment": "A1",
             "date": "2026-01-01"},
            {"student_name": "Bob", "score": 80, "assignment": "A2",
             "date": "2026-01-02"},
            {"student_name": "Bob", "score": 80, "assignment": "A3",
             "date": "2026-01-03"},
            {"student_name": "Bob", "score": 80, "assignment": "A4",
             "date": "2026-01-04"},
            # Alice only completed 1 → 75% missing
            {"student_name": "Alice", "score": 50,
             "assignment": "A1", "date": "2026-01-01"},
        ]
        with patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = flag_at_risk_students(threshold=10, teacher_id="t")
        # Alice flagged
        names = [s["student"] for s in result["students"]]
        assert "Alice" in names

    def test_25_to_50_pct_missing_triggers_smaller_flag(self):
        """Verify the `elif missing_pct > 25` branch (line 374) adds
        +10 risk in isolation. Alice has avg=86.7 (>=75 → no Signal 1),
        stable trend (no Signal 2), 30% missing (Signal 3 = +10), and
        no rubric categories (no Signal 4). So risk_score == 10 EXACTLY
        proves only the >25-missing branch fired."""
        from backend.services.assistant_tools_analytics import (
            flag_at_risk_students,
        )
        rows = []
        # 10 unique assignments class-wide via Bob (filler)
        for i in range(1, 11):
            rows.append({"student_name": "Bob", "score": 85,
                         "assignment": f"A{i}",
                         "date": f"2026-01-{i:02d}"})
        # Alice has 7 of 10 → missing 3 → missing_pct = 30%
        # Scores [85,86,87,88,87,86,85]: avg=86.3 (no Signal 1),
        # first_half_avg=86.0, second_half_avg=86.5, diff=0.5 → stable
        # (no Signal 2), no rubric cats (no Signal 4). Only Signal 3 fires.
        for i, score in enumerate([85, 86, 87, 88, 87, 86, 85], start=1):
            rows.append({"student_name": "Alice", "score": score,
                         "assignment": f"A{i}",
                         "date": f"2026-01-{i:02d}"})

        with patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = flag_at_risk_students(threshold=10, teacher_id="t")

        alice = next(
            (s for s in result["students"] if s["student"] == "Alice"),
            None,
        )
        assert alice is not None, "Alice should be flagged"
        # risk_score == 10 EXACTLY proves only the >25-missing branch
        # contributed — any other signal would push it higher.
        assert alice["risk_score"] == 10, (
            f"Expected risk_score=10 (only >25-missing branch), "
            f"got {alice['risk_score']} with flags={alice.get('flags')}"
        )
        # Production builds risk_flags from missing>0 (line 397-398)
        assert any("missing" in f for f in alice["flags"]), (
            f"Expected 'missing' in flags, got {alice['flags']}"
        )


# ──────────────────────────────────────────────────────────────────
# compare_assignments - error paths
# ──────────────────────────────────────────────────────────────────


class TestCompareAssignments:
    def test_missing_args_returns_error(self):
        from backend.services.assistant_tools_analytics import (
            compare_assignments,
        )
        result = compare_assignments(
            assignment_a="", assignment_b="Q2", teacher_id="t",
        )
        assert "error" in result
        assert "required" in result["error"]

    def test_no_rows_returns_error(self):
        from backend.services.assistant_tools_analytics import (
            compare_assignments,
        )
        with patch(f"{MODULE}._load_master_csv", return_value=[]):
            result = compare_assignments("Q1", "Q2", teacher_id="t")
        assert "error" in result

    def test_no_rows_for_a_returns_error(self):
        from backend.services.assistant_tools_analytics import (
            compare_assignments,
        )
        rows = [{"student_name": "Alice",
                 "assignment": "Quiz Two", "score": 90}]
        with patch(f"{MODULE}._load_master_csv", return_value=rows), \
             patch(f"{MODULE}._normalize_assignment_name",
                   side_effect=lambda x: x):
            result = compare_assignments(
                "Quiz One", "Quiz Two", teacher_id="t",
            )
        assert "error" in result
        assert "Quiz One" in result["error"]

    def test_no_rows_for_b_returns_error(self):
        from backend.services.assistant_tools_analytics import (
            compare_assignments,
        )
        rows = [{"student_name": "Alice",
                 "assignment": "Quiz One", "score": 90}]
        with patch(f"{MODULE}._load_master_csv", return_value=rows), \
             patch(f"{MODULE}._normalize_assignment_name",
                   side_effect=lambda x: x):
            result = compare_assignments(
                "Quiz One", "Quiz Two", teacher_id="t",
            )
        assert "error" in result
        assert "Quiz Two" in result["error"]


# ──────────────────────────────────────────────────────────────────
# get_grade_distribution - error + dist edges
# ──────────────────────────────────────────────────────────────────


class TestGetGradeDistribution:
    def test_no_rows_returns_error(self):
        from backend.services.assistant_tools_analytics import (
            get_grade_distribution,
        )
        with patch(f"{MODULE}._load_master_csv", return_value=[]):
            result = get_grade_distribution(teacher_id="t")
        assert "error" in result

    def test_assignment_filter_no_match_returns_error(self):
        from backend.services.assistant_tools_analytics import (
            get_grade_distribution,
        )
        rows = [{"student_name": "Alice",
                 "assignment": "Other", "score": 80}]
        with patch(f"{MODULE}._load_master_csv", return_value=rows), \
             patch(f"{MODULE}._normalize_assignment_name",
                   side_effect=lambda x: x):
            result = get_grade_distribution(
                assignment="Quiz One", teacher_id="t",
            )
        assert "error" in result

    def test_default_combined_distribution(self):
        from backend.services.assistant_tools_analytics import (
            get_grade_distribution,
        )
        rows = [
            {"student_name": "Alice", "assignment": "Q",
             "score": 95, "period": "P1"},
            {"student_name": "Bob", "assignment": "Q",
             "score": 75, "period": "P1"},
        ]
        with patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = get_grade_distribution(teacher_id="t")
        assert result["group_by"] == "none"
        assert result["count"] == 2
        assert result["counts"]["A"] == 1  # 95
        assert result["counts"]["C"] == 1  # 75

    def test_group_by_assignment(self):
        from backend.services.assistant_tools_analytics import (
            get_grade_distribution,
        )
        rows = [
            {"student_name": "Alice", "assignment": "Q1", "score": 95},
            {"student_name": "Bob", "assignment": "Q2", "score": 75},
        ]
        with patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = get_grade_distribution(
                group_by="assignment", teacher_id="t",
            )
        assert result["group_by"] == "assignment"
        assert len(result["distributions"]) == 2

    def test_group_by_period(self):
        from backend.services.assistant_tools_analytics import (
            get_grade_distribution,
        )
        rows = [
            {"student_name": "Alice", "assignment": "Q", "score": 95,
             "period": "P1"},
            {"student_name": "Bob", "assignment": "Q", "score": 75,
             "period": "P2"},
        ]
        with patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = get_grade_distribution(
                group_by="period", teacher_id="t",
            )
        assert result["group_by"] == "period"
        assert len(result["distributions"]) == 2


# ──────────────────────────────────────────────────────────────────
# detect_score_outliers - error + edge skips
# ──────────────────────────────────────────────────────────────────


class TestDetectScoreOutliers:
    def test_no_rows_returns_error(self):
        from backend.services.assistant_tools_analytics import (
            detect_score_outliers,
        )
        with patch(f"{MODULE}._load_master_csv", return_value=[]):
            result = detect_score_outliers(teacher_id="t")
        assert "error" in result

    def test_assignment_filter_no_match_returns_error(self):
        from backend.services.assistant_tools_analytics import (
            detect_score_outliers,
        )
        rows = [{"assignment": "Other", "score": 80,
                 "student_name": "Alice"}]
        with patch(f"{MODULE}._load_master_csv", return_value=rows), \
             patch(f"{MODULE}._normalize_assignment_name",
                   side_effect=lambda x: x):
            result = detect_score_outliers(
                assignment="Quiz", teacher_id="t",
            )
        assert "error" in result

    def test_under_3_scores_skipped(self):
        from backend.services.assistant_tools_analytics import (
            detect_score_outliers,
        )
        # Only 2 rows for the assignment → skipped (need 3+)
        rows = [
            {"assignment": "Q1", "score": 80,
             "student_name": "Alice"},
            {"assignment": "Q1", "score": 90,
             "student_name": "Bob"},
        ]
        with patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = detect_score_outliers(teacher_id="t")
        # No outliers (skipped due to insufficient data)
        assert result["outlier_count"] == 0

    def test_zero_stdev_skipped(self):
        # All identical scores → stdev=0 → skip
        from backend.services.assistant_tools_analytics import (
            detect_score_outliers,
        )
        rows = [
            {"assignment": "Q", "score": 80, "student_name": "A"},
            {"assignment": "Q", "score": 80, "student_name": "B"},
            {"assignment": "Q", "score": 80, "student_name": "C"},
            {"assignment": "Q", "score": 80, "student_name": "D"},
        ]
        with patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = detect_score_outliers(teacher_id="t")
        assert result["outlier_count"] == 0
