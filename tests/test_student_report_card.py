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


