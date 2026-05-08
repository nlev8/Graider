"""
Unit tests for backend/services/assistant_tools_grading.py.

Audit MAJOR #4 sprint follow-up to PR #250. Targets the 448 uncovered LOC
in assistant_tools_grading.py.

Strategy: mock the loader helpers (`_load_master_csv`, `_load_results`,
`_load_roster`, `_load_settings`, `_load_saved_assignments`,
`_get_period_assignments`) and verify the pure-Python tool logic.
require_teacher_id accepts non-empty non-'local-dev' values, so tests
pass `teacher_id="teacher-alice"` throughout.

Pattern matches tests/test_grading_routes_unit.py (PR #250).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


TID = "teacher-alice"


# ──────────────────────────────────────────────────────────────────
# _match_assignment_to_config
# ──────────────────────────────────────────────────────────────────


class TestMatchAssignmentToConfig:
    def test_exact_norm_match(self):
        from backend.services.assistant_tools_grading import _match_assignment_to_config
        with patch("backend.services.assistant_tools_grading._normalize_assignment_name",
                   side_effect=lambda x: x.lower()):
            result = _match_assignment_to_config(
                "Quiz", saved_norms={"quiz", "essay"}, saved_display={"quiz": "Quiz"},
            )
        assert result == "quiz"

    def test_alias_lookup(self):
        from backend.services.assistant_tools_grading import _match_assignment_to_config
        with patch("backend.services.assistant_tools_grading._normalize_assignment_name",
                   side_effect=lambda x: x.lower()):
            result = _match_assignment_to_config(
                "Pop Quiz",
                saved_norms={"quiz"},
                saved_display={"quiz": "Quiz"},
                alias_to_norm={"pop quiz": "quiz"},
            )
        assert result == "quiz"

    def test_prefix_fuzzy_match_via_saved_norm_only(self):
        """Codex round-1 LOW: previous version matched via saved_display
        prefix path. This version forces the saved_norm branch by:
        - Making saved_norm a SHORT string that's a prefix of the input
          (sn_lower[:25] == sn_lower since len(sn) < 25)
        - Making saved_display unrelated so its branch can't match."""
        from backend.services.assistant_tools_grading import _match_assignment_to_config
        with patch("backend.services.assistant_tools_grading._normalize_assignment_name",
                   side_effect=lambda x: x.lower()):
            result = _match_assignment_to_config(
                "Long Quiz About History of Rome",
                # Short saved_norm prefix (9 chars < 25)
                saved_norms={"long quiz"},
                # saved_display is "Z" so its prefix check can't match
                saved_display={"long quiz": "Z"},
            )
        assert result == "long quiz"

    def test_prefix_fuzzy_match_via_saved_display(self):
        """Distinct branch: saved_norm doesn't share prefix, but
        saved_display does match the 25-char prefix check."""
        from backend.services.assistant_tools_grading import _match_assignment_to_config
        with patch("backend.services.assistant_tools_grading._normalize_assignment_name",
                   side_effect=lambda x: x.lower()):
            result = _match_assignment_to_config(
                "Long Quiz About History of Rome",
                # saved_norm doesn't prefix-match input
                saved_norms={"abbrev"},
                # saved_display "Long Quiz About History of Rome..." matches
                saved_display={"abbrev": "Long Quiz About History of Rome Final"},
            )
        assert result == "abbrev"

    def test_no_match(self):
        from backend.services.assistant_tools_grading import _match_assignment_to_config
        with patch("backend.services.assistant_tools_grading._normalize_assignment_name",
                   side_effect=lambda x: x.lower()):
            result = _match_assignment_to_config(
                "Random",
                saved_norms={"quiz", "essay"},
                saved_display={"quiz": "Quiz", "essay": "Essay"},
            )
        assert result is None


# ──────────────────────────────────────────────────────────────────
# query_grades
# ──────────────────────────────────────────────────────────────────


class TestQueryGrades:
    @staticmethod
    def _row(name="Alice Smith", sid="sid-1", assign="Quiz", score=85,
             letter="B", quarter="1", date="2026-01-01"):
        return {
            "student_name": name, "student_id": sid, "assignment": assign,
            "score": score, "letter_grade": letter, "quarter": quarter, "date": date,
        }

    def test_no_filters_returns_all_and_propagates_teacher_id(self):
        """Codex round-1 LOW: pin tenant propagation. _load_master_csv
        and _load_results must receive teacher_id=TID."""
        from backend.services.assistant_tools_grading import query_grades
        rows = [self._row("Alice", "1", "Quiz", 90),
                self._row("Bob", "2", "Quiz", 70)]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows) as mock_master, \
             patch("backend.services.assistant_tools_grading._load_results",
                   return_value=[]) as mock_results:
            result = query_grades(teacher_id=TID)
        assert result["total_matches"] == 2
        assert result["showing"] == 2
        # Multi-tenant propagation contract
        master_kwargs = mock_master.call_args.kwargs
        assert master_kwargs.get("teacher_id") == TID, (
            f"_load_master_csv called with teacher_id="
            f"{master_kwargs.get('teacher_id')!r} (expected {TID!r})"
        )
        # _load_results is called positionally
        assert mock_results.call_args.args[0] == TID, (
            f"_load_results called with teacher_id="
            f"{mock_results.call_args.args[0]!r} (expected {TID!r})"
        )

    def test_student_name_fuzzy_filter(self):
        from backend.services.assistant_tools_grading import query_grades
        rows = [self._row("Alice Smith", "1"),
                self._row("Bob Jones", "2")]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_grading._load_results",
                   return_value=[]), \
             patch("backend.services.assistant_tools_grading._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in n.lower()):
            result = query_grades(student_name="alice", teacher_id=TID)
        assert result["total_matches"] == 1
        assert result["results"][0]["student_name"] == "Alice Smith"

    def test_assignment_substring_filter(self):
        from backend.services.assistant_tools_grading import query_grades
        rows = [self._row(assign="Pop Quiz"), self._row(assign="Final Essay")]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_grading._load_results",
                   return_value=[]):
            result = query_grades(assignment="quiz", teacher_id=TID)
        assert result["total_matches"] == 1
        assert "Quiz" in result["results"][0]["assignment"]

    def test_min_max_score_filter(self):
        from backend.services.assistant_tools_grading import query_grades
        rows = [self._row(score=60), self._row(score=80), self._row(score=95)]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_grading._load_results",
                   return_value=[]):
            result = query_grades(min_score=70, max_score=90, teacher_id=TID)
        assert result["total_matches"] == 1
        assert result["results"][0]["score"] == 80

    def test_letter_grade_filter(self):
        from backend.services.assistant_tools_grading import query_grades
        rows = [self._row(letter="A"), self._row(letter="B"), self._row(letter="A")]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_grading._load_results",
                   return_value=[]):
            result = query_grades(letter_grade="A", teacher_id=TID)
        assert result["total_matches"] == 2

    def test_limit_truncation(self):
        from backend.services.assistant_tools_grading import query_grades
        rows = [self._row() for _ in range(50)]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_grading._load_results",
                   return_value=[]):
            result = query_grades(limit=5, teacher_id=TID)
        assert result["total_matches"] == 50
        assert result["showing"] == 5
        assert len(result["results"]) == 5

    def test_feedback_lookup_truncated_at_150(self):
        from backend.services.assistant_tools_grading import query_grades
        long_fb = "a" * 200
        rows = [self._row(name="Alice", assign="Quiz")]
        results_json = [{"student_name": "Alice", "assignment": "Quiz", "feedback": long_fb}]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_grading._load_results",
                   return_value=results_json):
            result = query_grades(teacher_id=TID)
        assert result["results"][0]["feedback_preview"].endswith("...")
        assert len(result["results"][0]["feedback_preview"]) == 153  # 150 + "..."


# ──────────────────────────────────────────────────────────────────
# get_student_summary
# ──────────────────────────────────────────────────────────────────


class TestGetStudentSummary:
    @staticmethod
    def _row(name="Alice Smith", sid="sid-1", assign="Q1", score=80,
             letter="B", quarter="1", date="2026-01-01",
             content=4, completeness=4, writing=4, effort=4, period="1"):
        return {
            "student_name": name, "student_id": sid, "assignment": assign,
            "score": score, "letter_grade": letter, "quarter": quarter, "date": date,
            "content": content, "completeness": completeness, "writing": writing,
            "effort": effort, "period": period,
        }

    def test_no_match_returns_error(self):
        from backend.services.assistant_tools_grading import get_student_summary
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=[]), \
             patch("backend.services.assistant_tools_grading._fuzzy_name_match",
                   return_value=False):
            result = get_student_summary("Alice", teacher_id=TID)
        assert "error" in result

    def test_improving_trend(self):
        from backend.services.assistant_tools_grading import get_student_summary
        rows = [
            self._row(date="2026-01-01", score=60),
            self._row(date="2026-02-01", score=65),
            self._row(date="2026-03-01", score=85),
            self._row(date="2026-04-01", score=90),
        ]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_grading._fuzzy_name_match",
                   return_value=True), \
             patch("backend.services.assistant_tools_grading._normalize_period",
                   side_effect=lambda x: x), \
             patch("backend.services.assistant_tools_grading._normalize_assignment_name",
                   side_effect=lambda x: x), \
             patch("backend.services.assistant_tools_grading._get_period_assignments",
                   return_value=({"1": set()}, {}, {})):
            result = get_student_summary("Alice", teacher_id=TID)
        assert result["trend"] == "improving"

    def test_declining_trend(self):
        from backend.services.assistant_tools_grading import get_student_summary
        rows = [
            self._row(date="2026-01-01", score=95),
            self._row(date="2026-02-01", score=90),
            self._row(date="2026-03-01", score=70),
            self._row(date="2026-04-01", score=60),
        ]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_grading._fuzzy_name_match",
                   return_value=True), \
             patch("backend.services.assistant_tools_grading._normalize_period",
                   side_effect=lambda x: x), \
             patch("backend.services.assistant_tools_grading._normalize_assignment_name",
                   side_effect=lambda x: x), \
             patch("backend.services.assistant_tools_grading._get_period_assignments",
                   return_value=({"1": set()}, {}, {})):
            result = get_student_summary("Alice", teacher_id=TID)
        assert result["trend"] == "declining"

    def test_stable_trend(self):
        from backend.services.assistant_tools_grading import get_student_summary
        rows = [
            self._row(date="2026-01-01", score=80),
            self._row(date="2026-02-01", score=82),
            self._row(date="2026-03-01", score=81),
            self._row(date="2026-04-01", score=80),
        ]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_grading._fuzzy_name_match",
                   return_value=True), \
             patch("backend.services.assistant_tools_grading._normalize_period",
                   side_effect=lambda x: x), \
             patch("backend.services.assistant_tools_grading._normalize_assignment_name",
                   side_effect=lambda x: x), \
             patch("backend.services.assistant_tools_grading._get_period_assignments",
                   return_value=({"1": set()}, {}, {})):
            result = get_student_summary("Alice", teacher_id=TID)
        assert result["trend"] == "stable"

    def test_insufficient_data_trend(self):
        from backend.services.assistant_tools_grading import get_student_summary
        rows = [self._row(date="2026-01-01", score=80)]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_grading._fuzzy_name_match",
                   return_value=True), \
             patch("backend.services.assistant_tools_grading._normalize_period",
                   side_effect=lambda x: x), \
             patch("backend.services.assistant_tools_grading._normalize_assignment_name",
                   side_effect=lambda x: x), \
             patch("backend.services.assistant_tools_grading._get_period_assignments",
                   return_value=({"1": set()}, {}, {})):
            result = get_student_summary("Alice", teacher_id=TID)
        assert result["trend"] == "insufficient data"

    def test_category_averages_and_strengths_weaknesses(self):
        from backend.services.assistant_tools_grading import get_student_summary
        # content high, effort low → strengths=content+something, weaknesses=effort
        rows = [
            self._row(content=10, completeness=8, writing=8, effort=2),
            self._row(content=10, completeness=8, writing=8, effort=2),
        ]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_grading._fuzzy_name_match",
                   return_value=True), \
             patch("backend.services.assistant_tools_grading._normalize_period",
                   side_effect=lambda x: x), \
             patch("backend.services.assistant_tools_grading._normalize_assignment_name",
                   side_effect=lambda x: x), \
             patch("backend.services.assistant_tools_grading._get_period_assignments",
                   return_value=({"1": set()}, {}, {})):
            result = get_student_summary("Alice", teacher_id=TID)
        assert result["category_averages"]["content"] == 10
        assert result["category_averages"]["effort"] == 2
        assert "content" in result["strengths"]
        assert "effort" in result["weaknesses"]

    def test_missing_assignments_diff_against_period(self):
        from backend.services.assistant_tools_grading import get_student_summary
        rows = [self._row(assign="Q1")]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_grading._fuzzy_name_match",
                   return_value=True), \
             patch("backend.services.assistant_tools_grading._normalize_period",
                   side_effect=lambda x: x), \
             patch("backend.services.assistant_tools_grading._normalize_assignment_name",
                   side_effect=lambda x: x), \
             patch("backend.services.assistant_tools_grading._get_period_assignments",
                   return_value=({"1": {"Q1", "Q2", "Q3"}},
                                 {"Q1": "Q1", "Q2": "Q2", "Q3": "Q3"},
                                 {})):
            result = get_student_summary("Alice", teacher_id=TID)
        assert set(result["missing_assignments"]) == {"Q2", "Q3"}
        assert result["missing_count"] == 2


# ──────────────────────────────────────────────────────────────────
# get_class_analytics
# ──────────────────────────────────────────────────────────────────


class TestGetClassAnalytics:
    @staticmethod
    def _row(name="Alice", score=80, assign="Q1", date="2026-01-01"):
        return {
            "student_name": name, "assignment": assign, "score": score,
            "date": date,
        }

    def test_no_data_returns_error(self):
        from backend.services.assistant_tools_grading import get_class_analytics
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=[]):
            result = get_class_analytics(teacher_id=TID)
        assert "error" in result

    def test_basic_analytics_and_propagates_teacher_id(self):
        """Codex round-1 LOW: pin tenant propagation for class analytics."""
        from backend.services.assistant_tools_grading import get_class_analytics
        rows = [
            self._row("Alice", 90), self._row("Alice", 95),
            self._row("Bob", 60), self._row("Bob", 65),
        ]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows) as mock_master, \
             patch("backend.services.assistant_tools_grading._load_roster",
                   return_value=[]) as mock_roster, \
             patch("backend.services.assistant_tools_grading._normalize_period",
                   side_effect=lambda x: x):
            result = get_class_analytics(teacher_id=TID)
        assert mock_master.call_args.kwargs.get("teacher_id") == TID
        assert mock_roster.call_args.args[0] == TID
        # Class avg = (90+95+60+65)/4 = 77.5
        assert result["class_average"] == 77.5
        assert result["total_students"] == 2
        # Alice's avg = 92.5 → A; Bob's avg = 62.5 → D
        assert result["grade_distribution"]["A"] == 1
        assert result["grade_distribution"]["D"] == 1

    def test_top_performers_sorted_by_average(self):
        from backend.services.assistant_tools_grading import get_class_analytics
        rows = [
            self._row("HighStudent", 95),
            self._row("MidStudent", 80),
            self._row("LowStudent", 60),
        ]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_grading._load_roster",
                   return_value=[]), \
             patch("backend.services.assistant_tools_grading._normalize_period",
                   side_effect=lambda x: x):
            result = get_class_analytics(teacher_id=TID)
        assert result["top_performers"][0]["name"] == "HighStudent"
        assert result["top_performers"][0]["average"] == 95

    def test_attention_needed_includes_below_70(self):
        from backend.services.assistant_tools_grading import get_class_analytics
        rows = [self._row("Alice", 95), self._row("Bob", 65)]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_grading._load_roster",
                   return_value=[]), \
             patch("backend.services.assistant_tools_grading._normalize_period",
                   side_effect=lambda x: x):
            result = get_class_analytics(teacher_id=TID)
        attention_names = [s["name"] for s in result["attention_needed"]]
        assert "Bob" in attention_names
        assert "Alice" not in attention_names

    def test_period_filter_uses_roster(self):
        from backend.services.assistant_tools_grading import get_class_analytics
        rows = [self._row("Alice", 90)]
        roster = [
            {"student_id": "1", "name": "Alice", "period": "1"},
            {"student_id": "2", "name": "Bob", "period": "1"},
            {"student_id": "3", "name": "Carol", "period": "2"},
        ]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows), \
             patch("backend.services.assistant_tools_grading._load_roster",
                   return_value=roster), \
             patch("backend.services.assistant_tools_grading._normalize_period",
                   side_effect=lambda x: x):
            result = get_class_analytics(period="1", teacher_id=TID)
        # Roster has 2 in period 1; only Alice is graded
        assert result["total_students"] == 2
        assert result["students_with_grades"] == 1
        assert result["students_not_graded"] == 1


# ──────────────────────────────────────────────────────────────────
# get_assignment_stats
# ──────────────────────────────────────────────────────────────────


class TestGetAssignmentStats:
    def test_no_match_returns_error(self):
        from backend.services.assistant_tools_grading import get_assignment_stats
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=[]):
            result = get_assignment_stats("X", teacher_id=TID)
        assert "error" in result

    def test_full_stats(self):
        from backend.services.assistant_tools_grading import get_assignment_stats
        rows = [
            {"assignment": "Quiz", "score": s, "student_name": f"S{i}"}
            for i, s in enumerate([60, 70, 80, 90, 100])
        ]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows):
            result = get_assignment_stats("Quiz", teacher_id=TID)
        assert result["count"] == 5
        assert result["mean"] == 80.0
        assert result["median"] == 80.0
        assert result["min"] == 60
        assert result["max"] == 100
        # std dev for [60,70,80,90,100] = ~15.81
        assert 15 < result["std_dev"] < 17
        assert result["grade_distribution"]["A"] == 2  # 90 + 100
        assert result["grade_distribution"]["B"] == 1
        assert result["grade_distribution"]["C"] == 1
        assert result["grade_distribution"]["D"] == 1

    def test_partial_match(self):
        from backend.services.assistant_tools_grading import get_assignment_stats
        rows = [
            {"assignment": "Pop Quiz Unit 3", "score": 80, "student_name": "Alice"},
        ]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows):
            result = get_assignment_stats("quiz", teacher_id=TID)
        assert result["assignment_name"] == "Pop Quiz Unit 3"
        assert result["count"] == 1


# ──────────────────────────────────────────────────────────────────
# list_assignments_tool
# ──────────────────────────────────────────────────────────────────


class TestListAssignmentsTool:
    def test_empty_master_csv(self, tmp_path, monkeypatch):
        import backend.services.assistant_tools_grading as m
        monkeypatch.setattr(m, "ASSIGNMENTS_DIR", str(tmp_path))
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=[]):
            result = m.list_assignments_tool(teacher_id=TID)
        assert result["total_graded"] == 0
        assert result["graded_assignments"] == []

    def test_aggregates_by_assignment(self, tmp_path, monkeypatch):
        import backend.services.assistant_tools_grading as m
        monkeypatch.setattr(m, "ASSIGNMENTS_DIR", str(tmp_path))
        rows = [
            {"assignment": "Quiz", "score": 90, "student_name": "Alice"},
            {"assignment": "Quiz", "score": 70, "student_name": "Bob"},
            {"assignment": "Essay", "score": 100, "student_name": "Alice"},
        ]
        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=rows):
            result = m.list_assignments_tool(teacher_id=TID)
        assert result["total_graded"] == 2
        # Sorted alphabetically: Essay, Quiz
        assert result["graded_assignments"][0]["assignment"] == "Essay"
        assert result["graded_assignments"][0]["student_count"] == 1
        assert result["graded_assignments"][1]["assignment"] == "Quiz"
        assert result["graded_assignments"][1]["student_count"] == 2
        assert result["graded_assignments"][1]["average_score"] == 80.0

    def test_saved_configs_listed(self, tmp_path, monkeypatch):
        import backend.services.assistant_tools_grading as m
        monkeypatch.setattr(m, "ASSIGNMENTS_DIR", str(tmp_path))
        # Create some config files
        (tmp_path / "Quiz.json").write_text("{}")
        (tmp_path / "Essay.json").write_text("{}")
        (tmp_path / "ignored.txt").write_text("not json")

        with patch("backend.services.assistant_tools_grading._load_master_csv",
                   return_value=[]):
            result = m.list_assignments_tool(teacher_id=TID)
        assert "Quiz" in result["saved_configs"]
        assert "Essay" in result["saved_configs"]
        assert "ignored" not in result["saved_configs"]


# ──────────────────────────────────────────────────────────────────
# compare_periods
# ──────────────────────────────────────────────────────────────────


class TestComparePeriods:
    def test_no_results_returns_error(self):
        from backend.services.assistant_tools_grading import compare_periods
        with patch("backend.services.assistant_tools_grading._load_results",
                   return_value=[]):
            result = compare_periods(teacher_id=TID)
        assert "error" in result

    def test_assignment_filter_no_match(self):
        from backend.services.assistant_tools_grading import compare_periods
        with patch("backend.services.assistant_tools_grading._load_results",
                   return_value=[{"assignment": "Other", "period": "1", "score": 80}]):
            result = compare_periods(assignment_name="quiz", teacher_id=TID)
        assert "error" in result

    def test_groups_by_period_and_ranks(self):
        from backend.services.assistant_tools_grading import compare_periods
        results = [
            {"assignment": "Q1", "period": "1", "score": 90,
             "student_name": "A", "breakdown": {}},
            {"assignment": "Q1", "period": "1", "score": 85,
             "student_name": "B", "breakdown": {}},
            {"assignment": "Q1", "period": "2", "score": 60,
             "student_name": "C", "breakdown": {}},
            {"assignment": "Q1", "period": "2", "score": 65,
             "student_name": "D", "breakdown": {}},
        ]
        with patch("backend.services.assistant_tools_grading._load_results",
                   return_value=results), \
             patch("backend.services.assistant_tools_grading._load_roster",
                   return_value=[]), \
             patch("backend.services.assistant_tools_grading._normalize_period",
                   side_effect=lambda x: x), \
             patch("backend.services.assistant_tools_grading._safe_int_score",
                   side_effect=lambda x: int(x) if x is not None else 0):
            result = compare_periods(teacher_id=TID)
        # Period 1 (avg 87.5) ranked higher than Period 2 (avg 62.5)
        assert result["best_period"] == "1"
        assert result["lowest_period"] == "2"
        # Both periods present
        assert len(result["periods"]) == 2

    def test_assignment_filter_partial_match(self):
        from backend.services.assistant_tools_grading import compare_periods
        results = [
            {"assignment": "Pop Quiz Unit 3", "period": "1", "score": 80,
             "student_name": "A", "breakdown": {}},
        ]
        with patch("backend.services.assistant_tools_grading._load_results",
                   return_value=results), \
             patch("backend.services.assistant_tools_grading._load_roster",
                   return_value=[]), \
             patch("backend.services.assistant_tools_grading._normalize_period",
                   side_effect=lambda x: x), \
             patch("backend.services.assistant_tools_grading._safe_int_score",
                   side_effect=lambda x: int(x) if x is not None else 0):
            result = compare_periods(assignment_name="quiz", teacher_id=TID)
        assert "error" not in result
        assert result["assignment"] == "quiz"


# ──────────────────────────────────────────────────────────────────
# require_teacher_id contract
# ──────────────────────────────────────────────────────────────────


class TestTeacherIdRequired:
    """Pin the multi-tenant safety contract — empty teacher_id raises."""

    def test_query_grades_empty_teacher_id_raises(self):
        from backend.services.assistant_tools_grading import query_grades
        with pytest.raises(ValueError, match="teacher_id is required"):
            query_grades(teacher_id="")

    def test_get_student_summary_empty_teacher_id_raises(self):
        from backend.services.assistant_tools_grading import get_student_summary
        with pytest.raises(ValueError, match="teacher_id is required"):
            get_student_summary("Alice", teacher_id="")

    def test_get_class_analytics_empty_teacher_id_raises(self):
        from backend.services.assistant_tools_grading import get_class_analytics
        with pytest.raises(ValueError, match="teacher_id is required"):
            get_class_analytics(teacher_id="")

    def test_list_assignments_tool_empty_teacher_id_raises(self):
        from backend.services.assistant_tools_grading import list_assignments_tool
        with pytest.raises(ValueError, match="teacher_id is required"):
            list_assignments_tool(teacher_id="")

    def test_get_assignment_stats_empty_teacher_id_raises(self):
        """Codex round-1 LOW: TestTeacherIdRequired covered 4 entrypoints
        but skipped these two public tools. Closing the gap."""
        from backend.services.assistant_tools_grading import get_assignment_stats
        with pytest.raises(ValueError, match="teacher_id is required"):
            get_assignment_stats("Quiz", teacher_id="")

    def test_compare_periods_empty_teacher_id_raises(self):
        from backend.services.assistant_tools_grading import compare_periods
        with pytest.raises(ValueError, match="teacher_id is required"):
            compare_periods(teacher_id="")
