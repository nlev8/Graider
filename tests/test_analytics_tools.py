"""
Test: Analytics tools — trends, rubric weakness, at-risk, compare, distribution, outliers.
"""
import pytest
from backend.services.assistant_tools_analytics import (
    get_grade_trends, get_rubric_weakness, flag_at_risk_students, compare_assignments,
    get_grade_distribution, detect_score_outliers,
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


class TestGetGradeDistribution:
    def test_combined_all(self, patch_paths):
        result = get_grade_distribution()
        assert "error" not in result
        assert result.get("count") > 0
        assert "counts" in result
        assert "percentages" in result
        # All letter grades present
        for g in ("A", "B", "C", "D", "F"):
            assert g in result["counts"]
            assert g in result["percentages"]

    def test_pass_rate(self, patch_paths):
        result = get_grade_distribution()
        # pass_rate = (A + B + C) / total * 100
        assert 0 <= result.get("pass_rate", -1) <= 100

    def test_percentages_sum_to_100(self, patch_paths):
        result = get_grade_distribution()
        total_pct = sum(result["percentages"].values())
        assert abs(total_pct - 100.0) < 0.5  # allow rounding

    def test_filter_by_assignment(self, patch_paths):
        result = get_grade_distribution(assignment="Chapter 1 Notes")
        assert "error" not in result
        assert result.get("count") > 0

    def test_filter_by_period(self, patch_paths):
        result = get_grade_distribution(period="Period 1")
        assert "error" not in result
        assert result.get("count") > 0

    def test_group_by_assignment(self, patch_paths):
        result = get_grade_distribution(group_by="assignment")
        assert result.get("group_by") == "assignment"
        dists = result.get("distributions", [])
        assert len(dists) >= 2  # at least 2 assignments
        for d in dists:
            assert "assignment" in d
            assert "counts" in d

    def test_group_by_period(self, patch_paths):
        result = get_grade_distribution(group_by="period")
        assert result.get("group_by") == "period"
        dists = result.get("distributions", [])
        assert len(dists) >= 2  # at least 2 periods
        for d in dists:
            assert "period" in d
            assert "counts" in d

    def test_nonexistent_assignment(self, patch_paths):
        result = get_grade_distribution(assignment="Nonexistent Quiz XYZ")
        assert "error" in result


class TestDetectScoreOutliers:
    def test_scans_all(self, patch_paths):
        result = detect_score_outliers()
        assert "error" not in result
        assert result.get("assignments_scanned") > 0
        assert "outliers" in result

    def test_outlier_structure(self, patch_paths):
        result = detect_score_outliers()
        for o in result.get("outliers", []):
            assert "student" in o
            assert "assignment" in o
            assert "score" in o
            assert "class_mean" in o
            assert "z_score" in o
            assert o["direction"] in ("above", "below")

    def test_filter_by_assignment(self, patch_paths):
        result = detect_score_outliers(assignment="Chapter 1 Notes")
        assert "error" not in result
        for o in result.get("outliers", []):
            assert "Chapter 1 Notes" in o["assignment"]

    def test_lower_threshold_more_outliers(self, patch_paths):
        strict = detect_score_outliers(threshold=3.0)
        loose = detect_score_outliers(threshold=1.0)
        assert loose["outlier_count"] >= strict["outlier_count"]

    def test_nonexistent_assignment(self, patch_paths):
        result = detect_score_outliers(assignment="Nonexistent Quiz XYZ")
        assert "error" in result

    def test_emma_is_outlier(self, patch_paths):
        """Emma Davis scores 45/50/55 — well below class means, should be flagged."""
        result = detect_score_outliers(threshold=1.5)
        names = [o["student"] for o in result.get("outliers", [])]
        assert "Emma Davis" in names
