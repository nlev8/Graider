"""
Test: Existing query tools — verify they still work with fixture data.
"""
import pytest
from backend.services.assistant_tools import (
    query_grades, get_student_summary, get_class_analytics,
    get_assignment_stats, list_assignments_tool,
)


class TestQueryGrades:
    def test_all_grades(self, patch_paths):
        result = query_grades()
        assert "error" not in result
        assert result.get("total_matches") > 0

    def test_by_student_name(self, patch_paths):
        result = query_grades(student_name="Alice")
        assert result.get("total_matches") > 0
        for r in result.get("results", []):
            assert "Alice" in r.get("student_name", "")

    def test_by_period(self, patch_paths):
        result = query_grades(period="Period 2")
        assert result.get("total_matches") > 0

    def test_by_score_range(self, patch_paths):
        result = query_grades(min_score=90)
        for r in result.get("results", []):
            assert r.get("score", 0) >= 90

    def test_limit(self, patch_paths):
        result = query_grades(limit=5)
        assert len(result.get("results", [])) <= 5


class TestGetStudentSummary:
    def test_existing_student(self, patch_paths):
        result = get_student_summary(student_name="Alice Johnson")
        assert "error" not in result
        assert result.get("student_name")
        assert result.get("average_score") > 0

    def test_not_found(self, patch_paths):
        result = get_student_summary(student_name="Nonexistent")
        assert "error" in result


class TestGetClassAnalytics:
    def test_all_periods(self, patch_paths):
        result = get_class_analytics()
        assert "error" not in result
        assert result.get("total_students") > 0
        assert result.get("class_average") > 0

    def test_period_filter(self, patch_paths):
        result = get_class_analytics(period="Period 1")
        assert "error" not in result


class TestGetAssignmentStats:
    def test_existing_assignment(self, patch_paths):
        result = get_assignment_stats(assignment_name="Chapter 1 Notes")
        assert "error" not in result
        assert result.get("count") > 0
        assert result.get("mean") > 0

    def test_not_found(self, patch_paths):
        result = get_assignment_stats(assignment_name="Nonexistent Quiz XYZ")
        assert "error" in result


class TestListAssignments:
    def test_lists_assignments(self, patch_paths):
        result = list_assignments_tool()
        assert "error" not in result
        assert result.get("total_graded") > 0
        assert len(result.get("graded_assignments", [])) > 0
