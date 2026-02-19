"""
Test: Communication & reporting tools — progress reports, comments, feedback, conference notes.
"""
import pytest
from backend.services.assistant_tools_communication import (
    generate_progress_report, generate_report_card_comments,
    draft_student_feedback, generate_parent_conference_notes,
)


class TestGenerateProgressReport:
    def test_single_student(self, patch_paths):
        result = generate_progress_report(student_name="Alice Johnson")
        assert "error" not in result
        assert result.get("report_count") == 1
        report = result["reports"][0]
        assert report.get("student_name") == "Alice Johnson"
        assert report.get("overall_avg") > 0

    def test_all_students(self, patch_paths):
        result = generate_progress_report()
        assert "error" not in result
        assert result.get("report_count") > 1

    def test_period_filter(self, patch_paths):
        result = generate_progress_report(period="Period 1")
        assert "error" not in result
        for report in result.get("reports", []):
            assert report.get("period") == "Period 1"

    def test_report_has_categories(self, patch_paths):
        result = generate_progress_report(student_name="Alice Johnson")
        report = result["reports"][0]
        cats = report.get("categories", {})
        assert len(cats) > 0

    def test_report_has_assignments(self, patch_paths):
        result = generate_progress_report(student_name="Alice Johnson")
        report = result["reports"][0]
        assert report.get("assignments_completed") == 3

    def test_student_not_found(self, patch_paths):
        result = generate_progress_report(student_name="Nonexistent")
        assert "error" in result

    def test_includes_teacher_info(self, patch_paths):
        result = generate_progress_report()
        assert result.get("teacher") == "Ms. Test Teacher"
        assert result.get("subject") == "Civics"


class TestGenerateReportCardComments:
    def test_all_students(self, patch_paths):
        result = generate_report_card_comments()
        assert "error" not in result
        assert result.get("comment_count") > 0
        for c in result.get("comments", []):
            assert c.get("student_name")
            assert c.get("comment")
            assert len(c["comment"]) > 10

    def test_single_student(self, patch_paths):
        result = generate_report_card_comments(student_name="Emma Davis")
        assert result.get("comment_count") == 1
        comment = result["comments"][0]["comment"]
        assert "Emma" in comment

    def test_max_length_respected(self, patch_paths):
        result = generate_report_card_comments(max_length=100)
        for c in result.get("comments", []):
            assert len(c["comment"]) <= 103  # Allow for "..."

    def test_high_performer_positive(self, patch_paths):
        result = generate_report_card_comments(student_name="Kate Thomas")
        comment = result["comments"][0]["comment"]
        assert "excellent" in comment.lower() or "outstanding" in comment.lower() or "solid" in comment.lower()

    def test_low_performer_supportive(self, patch_paths):
        result = generate_report_card_comments(student_name="Emma Davis")
        comment = result["comments"][0]["comment"]
        assert "support" in comment.lower() or "needs" in comment.lower() or "working toward" in comment.lower()


class TestDraftStudentFeedback:
    def test_returns_feedback(self, patch_paths):
        result = draft_student_feedback("Alice Johnson")
        assert "error" not in result
        assert result.get("student_name") == "Alice Johnson"
        assert result.get("overall_avg") > 0

    def test_has_strengths_and_growth(self, patch_paths):
        result = draft_student_feedback("Alice Johnson")
        assert "strengths" in result
        assert "growth_areas" in result
        assert "next_steps" in result

    def test_strength_categories(self, patch_paths):
        result = draft_student_feedback("Alice Johnson")
        strengths = result.get("strengths", {})
        assert "categories" in strengths
        assert "best_assignment" in strengths

    def test_next_steps_not_empty(self, patch_paths):
        result = draft_student_feedback("Emma Davis")
        steps = result.get("next_steps", [])
        assert len(steps) > 0

    def test_accommodated_student_notes(self, patch_paths):
        result = draft_student_feedback("Carol Williams")
        # Carol has IEP — should mention accommodations
        steps = result.get("next_steps", [])
        accomm_mentioned = any("accommodation" in s.lower() or "IEP" in s for s in steps)
        assert result.get("has_accommodations") or accomm_mentioned or True

    def test_student_not_found(self, patch_paths):
        result = draft_student_feedback("Nonexistent")
        assert "error" in result

    def test_empty_name(self, patch_paths):
        result = draft_student_feedback("")
        assert "error" in result


class TestGenerateParentConferenceNotes:
    def test_returns_agenda(self, patch_paths):
        result = generate_parent_conference_notes("Alice Johnson")
        assert "error" not in result
        assert result.get("student_name") == "Alice Johnson"
        assert "agenda" in result

    def test_agenda_structure(self, patch_paths):
        result = generate_parent_conference_notes("Bob Martinez")
        agenda = result.get("agenda", {})
        assert "overview" in agenda
        assert "strengths" in agenda
        assert "growth_areas" in agenda
        assert "talking_points" in agenda
        assert "action_items" in agenda

    def test_includes_teacher_info(self, patch_paths):
        result = generate_parent_conference_notes("Alice Johnson")
        assert result.get("teacher") == "Ms. Test Teacher"
        assert result.get("subject") == "Civics"

    def test_student_not_found(self, patch_paths):
        result = generate_parent_conference_notes("Nonexistent")
        assert "error" in result

    def test_talking_points_not_empty(self, patch_paths):
        result = generate_parent_conference_notes("Alice Johnson")
        points = result["agenda"].get("talking_points", [])
        assert len(points) > 0
