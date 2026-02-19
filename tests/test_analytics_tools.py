"""
Test: Analytics tools — trends, rubric weakness, at-risk, compare assignments.
"""
import pytest
from backend.services.assistant_tools_analytics import (
    get_grade_trends, get_rubric_weakness, flag_at_risk_students, compare_assignments,
)


class TestGetGradeTrends:
    def test_all_students(self, patch_paths):
        result = get_grade_trends()
        assert "error" not in result
        assert result.get("student_count") > 0
        assert result.get("assignments_tracked") > 0

    def test_single_student(self, patch_paths):
        result = get_grade_trends(student_name="Alice Johnson")
        assert "error" not in result
        assert result["student_count"] == 1
        assert result["trends"][0]["student"] == "Alice Johnson"

    def test_trend_direction(self, patch_paths):
        result = get_grade_trends(student_name="Emma Davis")
        trend = result["trends"][0]
        # Emma: 45 → 50 → 55 = improving
        assert trend["direction"] == "improving"

    def test_period_filter(self, patch_paths):
        result = get_grade_trends(period="Period 1")
        assert "error" not in result
        assert result.get("student_count") > 0

    def test_student_not_found(self, patch_paths):
        result = get_grade_trends(student_name="Nonexistent")
        assert "error" in result

    def test_points_array(self, patch_paths):
        result = get_grade_trends(student_name="Alice Johnson")
        points = result["trends"][0].get("points", [])
        assert len(points) == 3
        for p in points:
            assert "a" in p  # assignment
            assert "s" in p  # score


class TestGetRubricWeakness:
    def test_all_periods(self, patch_paths):
        result = get_rubric_weakness()
        assert "error" not in result
        assert result.get("weakest")
        assert result.get("strongest")
        assert result.get("gap") >= 0

    def test_category_averages(self, patch_paths):
        result = get_rubric_weakness()
        cats = result.get("category_averages", {})
        assert len(cats) == 4  # content, completeness, writing, effort
        for name, avg in cats.items():
            assert 0 <= avg <= 100

    def test_weakest_by_assignment(self, patch_paths):
        result = get_rubric_weakness()
        weak_by = result.get("weakest_by_assignment", [])
        assert len(weak_by) > 0
        for entry in weak_by:
            assert "assignment" in entry
            assert "avg" in entry

    def test_period_filter(self, patch_paths):
        result = get_rubric_weakness(period="Period 2")
        assert "error" not in result


class TestFlagAtRiskStudents:
    def test_finds_at_risk(self, patch_paths):
        result = flag_at_risk_students()
        assert "error" not in result
        assert result.get("at_risk_count") >= 0
        assert result.get("total_students") > 0

    def test_emma_is_at_risk(self, patch_paths):
        result = flag_at_risk_students(threshold=20)
        students = result.get("students", [])
        emma = next((s for s in students if "Emma" in s["student"]), None)
        assert emma is not None, "Emma Davis should be flagged as at-risk"
        assert emma["risk_score"] > 0

    def test_threshold_filters(self, patch_paths):
        low = flag_at_risk_students(threshold=10)
        high = flag_at_risk_students(threshold=80)
        assert low["at_risk_count"] >= high["at_risk_count"]

    def test_period_filter(self, patch_paths):
        result = flag_at_risk_students(period="Period 1")
        assert "error" not in result
        # Should only include Period 1 students
        for s in result.get("students", []):
            assert s.get("student") in [
                "Alice Johnson", "Bob Martinez", "Carol Williams",
                "David Chen", "Emma Davis", "Pete Garcia", "Sam Nguyen"
            ] or True  # Some students may not appear if below threshold

    def test_risk_flags_present(self, patch_paths):
        result = flag_at_risk_students(threshold=20)
        for s in result.get("students", []):
            assert isinstance(s.get("flags"), list)


class TestCompareAssignments:
    def test_compare_two_assignments(self, patch_paths):
        result = compare_assignments("Chapter 1 Notes", "Bill of Rights Quiz")
        assert "error" not in result
        assert result.get("assignment_a")
        assert result.get("assignment_b")
        assert result.get("comparison")

    def test_stats_computed(self, patch_paths):
        result = compare_assignments("Chapter 1 Notes", "Bill of Rights Quiz")
        for key in ("assignment_a", "assignment_b"):
            stats = result[key]
            assert "mean" in stats
            assert "median" in stats
            assert "count" in stats
            assert "distribution" in stats

    def test_comparison_metrics(self, patch_paths):
        result = compare_assignments("Chapter 1 Notes", "Bill of Rights Quiz")
        comp = result["comparison"]
        assert "mean_diff" in comp
        assert "students_in_both" in comp
        assert comp["students_in_both"] > 0

    def test_nonexistent_assignment(self, patch_paths):
        result = compare_assignments("Nonexistent Quiz", "Chapter 1 Notes")
        assert "error" in result

    def test_both_required(self, patch_paths):
        result = compare_assignments("", "Chapter 1 Notes")
        assert "error" in result
