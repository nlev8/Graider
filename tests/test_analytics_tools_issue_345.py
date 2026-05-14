"""Regression tests for the 5 production bugs in issue #345.

Surfaced by Gemini batch-5 quality review of test_analytics_tools_gaps.py
(see GH #345). Bugs live in backend/services/assistant_tools_analytics.py.

Each test class pins ONE bug's intended behavior so a future regression
shows up as a focused failure.
"""
from __future__ import annotations

from unittest.mock import patch

MODULE = "backend.services.assistant_tools_analytics"


def _rows(*entries):
    """Build a master-csv-like row list from concise kwargs dicts.

    Defaults fill the keys the production code reads so tests stay focused on
    the field under test.
    """
    out = []
    for i, e in enumerate(entries):
        out.append({
            "student_name": e.get("student", f"S{i}"),
            "score": e.get("score", 80),
            "assignment": e.get("assignment", "A1"),
            "period": e.get("period", "Period 1"),
            "date": e.get("date", f"2026-01-{i+1:02d}"),
            "content": e.get("content", ""),
            "completeness": e.get("completeness", ""),
            "writing": e.get("writing", ""),
            "effort": e.get("effort", ""),
        })
    return out


# ──────────────────────────────────────────────────────────────────
# Bug #2: explicit zero rubric scores must be counted
# ──────────────────────────────────────────────────────────────────


class TestBug2ExplicitZeroIsCounted:
    """A student who genuinely earned 0 in a rubric category should pull the
    category average DOWN, not be silently dropped from the denominator.
    """

    def test_get_rubric_weakness_includes_explicit_zero(self):
        from backend.services.assistant_tools_analytics import (
            get_rubric_weakness,
        )
        # Three students. Two earned 100 in `effort`; one earned 0.
        # Correct average = 200/3 ≈ 66.7. Buggy average (drops 0) = 200/2 = 100.
        rows = _rows(
            {"student": "Top1", "effort": "100"},
            {"student": "Top2", "effort": "100"},
            {"student": "ZeroEarner", "effort": "0"},
        )
        with patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = get_rubric_weakness(teacher_id="t")
        effort_avg = result["category_averages"]["Effort & Engagement"]
        assert effort_avg < 70, (
            f"Expected effort avg ~66.7 (zero counted); got {effort_avg} "
            f"— bug #2 still drops explicit zeros."
        )

    def test_assignment_stats_includes_explicit_zero_int(self):
        from backend.services.assistant_tools_analytics import (
            _assignment_stats,
        )
        # Latent bug: line 165 uses `if r.get(cat)` which treats int 0 as falsy
        # and drops the row. String "0" already works (truthy), so the bug is
        # only exposed when data arrives as native int 0 (e.g., future JSON
        # path bypassing the CSV stringifier).
        rows = _rows(
            {"student": "Top1", "content": 100},
            {"student": "Top2", "content": 100},
            {"student": "ZeroEarner", "content": 0},
        )
        stats = _assignment_stats(rows)
        content_avg = stats["categories"]["content"]
        assert content_avg < 70, (
            f"Expected content avg ~66.7; got {content_avg} — _assignment_stats "
            f"still drops int-zero explicit zeros."
        )

    def test_flag_at_risk_includes_explicit_zero_int(self):
        from backend.services.assistant_tools_analytics import (
            flag_at_risk_students,
        )
        # Same latent bug at line 380. Int 0 in rubric categories must not be
        # dropped — three int-zero rubric scores should trigger the "weak: ..."
        # flag (3 weak categories → +15 risk).
        rows = _rows(
            {"student": "ZeroEarner", "score": 50, "assignment": "A1",
             "content": 0, "completeness": 0, "writing": 0},
        )
        with patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = flag_at_risk_students(threshold=10, teacher_id="t")
        students = result.get("students", [])
        zero = next((s for s in students if s["student"] == "ZeroEarner"), None)
        assert zero is not None
        weak = next((f for f in zero["flags"] if f.startswith("weak:")), None)
        assert weak is not None, (
            f"Expected a weak-categories flag for ZeroEarner; got flags={zero['flags']} "
            f"— bug #2 still drops int-zero rubric scores."
        )


# ──────────────────────────────────────────────────────────────────
# Bug #3: substring collision in assignment filter
# ──────────────────────────────────────────────────────────────────


class TestBug3ExactAssignmentMatch:
    """`compare_assignments('Quiz 1', 'Quiz 2')` must NOT also pull in 'Quiz 10'."""

    def test_compare_assignments_quiz_1_excludes_quiz_10(self):
        from backend.services.assistant_tools_analytics import (
            compare_assignments,
        )
        rows = _rows(
            {"student": "Alice", "assignment": "Quiz 1", "score": 100},
            {"student": "Bob",   "assignment": "Quiz 1", "score": 100},
            {"student": "Alice", "assignment": "Quiz 2", "score": 80},
            {"student": "Bob",   "assignment": "Quiz 2", "score": 80},
            # Decoy: substring match on "quiz 1" must NOT include this row.
            {"student": "Alice", "assignment": "Quiz 10", "score": 30},
            {"student": "Bob",   "assignment": "Quiz 10", "score": 30},
        )
        with patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = compare_assignments("Quiz 1", "Quiz 2", teacher_id="t")
        # If Quiz 10 leaks into rows_a, mean drops from 100 to 65.
        assert result["assignment_a"]["mean"] == 100.0, (
            f"Quiz 1 mean should be 100; got {result['assignment_a']['mean']} "
            f"— bug #3 substring match still includes Quiz 10."
        )
        assert result["assignment_a"]["count"] == 2

    def test_grade_distribution_quiz_1_excludes_quiz_10(self):
        from backend.services.assistant_tools_analytics import (
            get_grade_distribution,
        )
        rows = _rows(
            {"student": "Alice", "assignment": "Quiz 1", "score": 95},
            {"student": "Bob",   "assignment": "Quiz 1", "score": 95},
            # Decoy
            {"student": "Alice", "assignment": "Quiz 10", "score": 55},
            {"student": "Bob",   "assignment": "Quiz 10", "score": 55},
        )
        with patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = get_grade_distribution(assignment="Quiz 1", teacher_id="t")
        assert result["count"] == 2, (
            f"Quiz 1 distribution should have 2 rows; got {result['count']} "
            f"— substring match leaked Quiz 10 in."
        )
        assert result["counts"]["F"] == 0

    def test_detect_outliers_quiz_1_excludes_quiz_10(self):
        from backend.services.assistant_tools_analytics import (
            detect_score_outliers,
        )
        # Three tight Quiz 1 scores (no outlier) + a Quiz 10 outlier that
        # would only show up if the substring filter wrongly merged them.
        rows = _rows(
            {"student": "A", "assignment": "Quiz 1", "score": 80},
            {"student": "B", "assignment": "Quiz 1", "score": 81},
            {"student": "C", "assignment": "Quiz 1", "score": 79},
            # Decoy: 3 tight scores + 1 far outlier; only this group has an outlier.
            {"student": "D", "assignment": "Quiz 10", "score": 10},
            {"student": "E", "assignment": "Quiz 10", "score": 11},
            {"student": "F", "assignment": "Quiz 10", "score": 12},
            {"student": "G", "assignment": "Quiz 10", "score": 99},
        )
        with patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = detect_score_outliers(assignment="Quiz 1", teacher_id="t")
        # If Quiz 10 leaked in, the assignment is merged into Quiz 1's group
        # (defaultdict key is the raw assignment name) — outlier set non-empty.
        assignments_scanned = result.get("assignments_scanned", 0)
        assert assignments_scanned == 1, (
            f"detect_score_outliers should scan only Quiz 1 (1 group); "
            f"scanned {assignments_scanned} — bug #3 leaked Quiz 10."
        )


# ──────────────────────────────────────────────────────────────────
# Bug #4: avg-flag threshold must match scoring threshold
# ──────────────────────────────────────────────────────────────────


class TestBug4AvgFlagMatchesScoringThreshold:
    """A student with avg in [70, 75) is scored +10 risk but the old code
    only emitted the human-readable avg flag if avg < 70. Teachers saw the
    student flagged with no explanation. Align the thresholds.
    """

    def test_avg_72_gets_flagged(self):
        from backend.services.assistant_tools_analytics import (
            flag_at_risk_students,
        )
        # Two scores averaging 72 (>= 70, < 75). Risk score = 10 from avg
        # band alone; we also need direction != declining (force stable)
        # so the flag list comes purely from the avg band.
        rows = _rows(
            {"student": "Borderline", "score": 70, "assignment": "A1"},
            {"student": "Borderline", "score": 74, "assignment": "A2"},
        )
        with patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = flag_at_risk_students(threshold=10, teacher_id="t")
        students = result["students"]
        borderline = next(
            (s for s in students if s["student"] == "Borderline"), None,
        )
        assert borderline is not None, (
            "Borderline student should appear above threshold=10."
        )
        avg_flag = next(
            (f for f in borderline["flags"] if f.startswith("avg ")), None,
        )
        assert avg_flag is not None, (
            f"Expected an 'avg X%' flag for avg=72%; got flags={borderline['flags']} "
            f"— bug #4 still hides the avg flag for the 70-74 band."
        )


# ──────────────────────────────────────────────────────────────────
# Bug #1: period='all' missing-assignments scoped globally (product call)
# ──────────────────────────────────────────────────────────────────


class TestBug1MissingAssignmentsGlobal:
    """Product decision (2026-05-13): when period='all', the
    missing-assignment penalty pool is the GLOBAL union of all assignments
    across all periods, not per-period. Pin this contract so a future
    refactor doesn't silently flip the semantics.
    """

    def test_period_all_uses_global_assignment_pool(self):
        from backend.services.assistant_tools_analytics import (
            flag_at_risk_students,
        )
        # Period 1 had assignments A1, A2, A3. Period 2 had assignment B1.
        # Alice (Period 1) completed only A1. Under global-pool semantics
        # she is missing {A2, A3, B1} = 3 of 4 (75%) → 20-point penalty.
        # Under per-period semantics she'd be missing {A2, A3} = 2 of 3 (66%) → 20-point.
        # Both branches penalize her; distinguish via assignments_missing count.
        rows = _rows(
            {"student": "Alice", "assignment": "A1", "period": "Period 1", "score": 50},
            {"student": "Bob",   "assignment": "A1", "period": "Period 1", "score": 80},
            {"student": "Bob",   "assignment": "A2", "period": "Period 1", "score": 80},
            {"student": "Bob",   "assignment": "A3", "period": "Period 1", "score": 80},
            {"student": "Carol", "assignment": "B1", "period": "Period 2", "score": 80},
        )
        with patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = flag_at_risk_students(threshold=10, teacher_id="t")
        # total_assignments reflects the global union under current contract
        assert result["total_assignments"] == 4, (
            f"Expected 4 global assignments under period='all'; got "
            f"{result['total_assignments']} — bug #1 semantics drifted."
        )
        alice = next(s for s in result["students"] if s["student"] == "Alice")
        assert alice["assignments_missing"] == 3, (
            f"Expected Alice missing 3 (global A2,A3,B1); got "
            f"{alice['assignments_missing']} — bug #1 semantics drifted."
        )


# ──────────────────────────────────────────────────────────────────
# Bug #5: D counts as passing
# ──────────────────────────────────────────────────────────────────


class TestBug5DCountsAsPassing:
    """Product decision (2026-05-13): grades A/B/C/D all count toward
    pass_rate (>= 60). Aligns backend with the frontend AnalyticsTab
    which already uses `s >= 60` as the passing threshold.
    """

    def test_pass_rate_includes_d(self):
        from backend.services.assistant_tools_analytics import (
            get_grade_distribution,
        )
        # Mix: 1 A, 1 B, 1 C, 1 D, 1 F → 4 of 5 = 80% pass rate.
        rows = _rows(
            {"student": "A", "score": 95},
            {"student": "B", "score": 85},
            {"student": "C", "score": 75},
            {"student": "D", "score": 65},
            {"student": "F", "score": 55},
        )
        with patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = get_grade_distribution(teacher_id="t")
        assert result["pass_rate"] == 80.0, (
            f"Expected 80% pass rate (A+B+C+D over 5); got "
            f"{result['pass_rate']}% — bug #5 still excludes D from pass_rate."
        )

    def test_pass_rate_in_grouped_view(self):
        from backend.services.assistant_tools_analytics import (
            get_grade_distribution,
        )
        # Single assignment, all D's: pass_rate should be 100%, not 0%.
        rows = _rows(
            {"student": "A", "assignment": "A1", "score": 65},
            {"student": "B", "assignment": "A1", "score": 62},
            {"student": "C", "assignment": "A1", "score": 68},
        )
        with patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = get_grade_distribution(
                group_by="assignment", teacher_id="t",
            )
        d = result["distributions"][0]
        assert d["pass_rate"] == 100.0, (
            f"All-D class should have 100% pass rate; got {d['pass_rate']}%."
        )
