"""Tests for the student report card endpoint and bridge helper.

Spec: docs/superpowers/specs/2026-04-25-phase2b-student-report-card-design.md
"""
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


# ============ Bridge helper unit tests ============

class TestBuildStandardsBreakdownForStudent:
    """_build_standards_breakdown_for_student: dict → sorted array + enrichment."""

    def test_empty_input_returns_empty_array(self):
        from backend.routes.student_portal_routes import _build_standards_breakdown_for_student
        result = _build_standards_breakdown_for_student({}, {})
        assert result == []

    def test_single_standard_passes_through_with_code(self):
        from backend.routes.student_portal_routes import _build_standards_breakdown_for_student
        mastery_by_code = {
            "MA.6.AR.1.1": {
                "percentage": 75,
                "points_earned": 15,
                "points_possible": 20,
                "question_count": 4,
                "contributing_submissions": [
                    {"submission_id": "sub-1", "title": "Quiz 1",
                     "points_earned": 15, "points_possible": 20, "attempt_number": 1},
                ],
            },
        }
        submission_lookup = {
            "sub-1": {"submitted_at": "2026-04-12T15:30:00Z", "percentage": 70},
        }
        result = _build_standards_breakdown_for_student(mastery_by_code, submission_lookup)
        assert len(result) == 1
        assert result[0]["code"] == "MA.6.AR.1.1"
        assert result[0]["percentage"] == 75
        assert result[0]["points_earned"] == 15
        # contributing_submission enriched with submitted_at + percentage
        cs = result[0]["contributing_submissions"][0]
        assert cs["submission_id"] == "sub-1"
        assert cs["submitted_at"] == "2026-04-12T15:30:00Z"
        assert cs["percentage"] == 75.0  # 15/20 * 100

    def test_multiple_standards_sorted_worst_first(self):
        from backend.routes.student_portal_routes import _build_standards_breakdown_for_student
        mastery_by_code = {
            "MA.6.AR.1.1": {"percentage": 90, "points_earned": 18, "points_possible": 20,
                            "question_count": 4, "contributing_submissions": []},
            "MA.6.AR.2.1": {"percentage": 50, "points_earned": 5, "points_possible": 10,
                            "question_count": 2, "contributing_submissions": []},
            "MA.6.AR.3.1": {"percentage": 75, "points_earned": 15, "points_possible": 20,
                            "question_count": 4, "contributing_submissions": []},
        }
        result = _build_standards_breakdown_for_student(mastery_by_code, {})
        # ASC by percentage (worst first)
        assert [r["code"] for r in result] == ["MA.6.AR.2.1", "MA.6.AR.3.1", "MA.6.AR.1.1"]

    def test_contributing_submission_missing_in_lookup_keeps_existing_fields(self):
        """If submission_lookup doesn't have an entry for a contributor, the
        contributor still appears with its original fields (no submitted_at/
        percentage enrichment, but not dropped)."""
        from backend.routes.student_portal_routes import _build_standards_breakdown_for_student
        mastery_by_code = {
            "MA.6.AR.1.1": {
                "percentage": 75, "points_earned": 15, "points_possible": 20,
                "question_count": 4,
                "contributing_submissions": [
                    {"submission_id": "sub-missing", "title": "Quiz 1",
                     "points_earned": 15, "points_possible": 20, "attempt_number": 1},
                ],
            },
        }
        result = _build_standards_breakdown_for_student(mastery_by_code, {})
        cs = result[0]["contributing_submissions"][0]
        assert cs["submission_id"] == "sub-missing"
        # No submitted_at because lookup miss; percentage still computed
        assert "submitted_at" not in cs or cs["submitted_at"] is None
        assert cs["percentage"] == 75.0  # 15/20 — computed from points, not lookup


class TestBuildTrajectoryForStudent:
    """_build_trajectory_for_student: list[submission] → chronological list."""

    def test_empty_input_returns_empty_array(self):
        from backend.routes.student_portal_routes import _build_trajectory_for_student
        assert _build_trajectory_for_student([], {}) == []

    def test_orders_ascending_by_submitted_at(self):
        from backend.routes.student_portal_routes import _build_trajectory_for_student
        subs = [
            {"id": "s2", "content_id": "c1", "submitted_at": "2026-04-15T10:00:00Z",
             "percentage": 80, "attempt_number": 1, "results": {"points_earned": 8, "points_possible": 10}},
            {"id": "s1", "content_id": "c1", "submitted_at": "2026-04-10T10:00:00Z",
             "percentage": 60, "attempt_number": 1, "results": {"points_earned": 6, "points_possible": 10}},
            {"id": "s3", "content_id": "c1", "submitted_at": "2026-04-20T10:00:00Z",
             "percentage": 90, "attempt_number": 2, "results": {"points_earned": 9, "points_possible": 10}},
        ]
        content_titles = {"c1": "Quiz 1"}
        result = _build_trajectory_for_student(subs, content_titles)
        assert [r["submission_id"] for r in result] == ["s1", "s2", "s3"]
        assert result[0]["title"] == "Quiz 1"
        assert result[0]["percentage"] == 60
        assert result[0]["points_earned"] == 6
        assert result[0]["points_possible"] == 10

    def test_null_submitted_at_sorted_to_end(self):
        from backend.routes.student_portal_routes import _build_trajectory_for_student
        subs = [
            {"id": "s_null", "content_id": "c1", "submitted_at": None,
             "percentage": 50, "attempt_number": 1, "results": {}},
            {"id": "s_dated", "content_id": "c1", "submitted_at": "2026-04-10T10:00:00Z",
             "percentage": 70, "attempt_number": 1, "results": {}},
        ]
        result = _build_trajectory_for_student(subs, {"c1": "Q"})
        # Null sorts to END
        assert [r["submission_id"] for r in result] == ["s_dated", "s_null"]

    def test_missing_content_title_uses_empty_string(self):
        from backend.routes.student_portal_routes import _build_trajectory_for_student
        subs = [
            {"id": "s1", "content_id": "c-missing", "submitted_at": "2026-04-10T10:00:00Z",
             "percentage": 70, "attempt_number": 1, "results": {}},
        ]
        result = _build_trajectory_for_student(subs, {})
        assert result[0]["title"] == ""
