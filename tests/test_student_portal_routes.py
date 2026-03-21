"""Tests for student portal grading functions."""
import pytest
from unittest.mock import patch, MagicMock


class TestGradeInstantOnly:
    """Test the grade_instant_only function for MC/TF/matching."""

    def test_mc_correct(self):
        from backend.routes.student_portal_routes import grade_instant_only
        assessment = {
            "sections": [{
                "questions": [
                    {"type": "multiple_choice", "question": "Q1", "answer": "A", "options": ["A) Yes", "B) No"], "points": 5},
                ]
            }]
        }
        result = grade_instant_only(assessment, {"0-0": "A"})
        assert result["score"] == 5
        assert result["questions"][0]["is_correct"] is True

    def test_mc_incorrect(self):
        from backend.routes.student_portal_routes import grade_instant_only
        assessment = {
            "sections": [{
                "questions": [
                    {"type": "multiple_choice", "question": "Q1", "answer": "A", "options": ["A) Yes", "B) No"], "points": 5},
                ]
            }]
        }
        result = grade_instant_only(assessment, {"0-0": "B"})
        assert result["score"] == 0
        assert result["questions"][0]["is_correct"] is False

    def test_tf_correct(self):
        from backend.routes.student_portal_routes import grade_instant_only
        assessment = {
            "sections": [{
                "questions": [
                    {"type": "true_false", "question": "Q1", "answer": "True", "points": 3},
                ]
            }]
        }
        result = grade_instant_only(assessment, {"0-0": "True"})
        assert result["score"] == 3

    def test_tf_case_insensitive(self):
        from backend.routes.student_portal_routes import grade_instant_only
        assessment = {
            "sections": [{
                "questions": [
                    {"type": "true_false", "question": "Q1", "answer": "False", "points": 3},
                ]
            }]
        }
        result = grade_instant_only(assessment, {"0-0": "false"})
        assert result["score"] == 3

    def test_written_marked_pending(self):
        from backend.routes.student_portal_routes import grade_instant_only
        assessment = {
            "sections": [{
                "questions": [
                    {"type": "short_answer", "question": "Explain", "answer": "expected", "points": 10},
                ]
            }]
        }
        result = grade_instant_only(assessment, {"0-0": "student answer"})
        assert result["questions"][0]["status"] == "pending_review"
        assert result["questions"][0]["points_earned"] == 0

    def test_mixed_assignment(self):
        from backend.routes.student_portal_routes import grade_instant_only
        assessment = {
            "sections": [
                {"questions": [
                    {"type": "multiple_choice", "question": "MC", "answer": "B", "options": ["A", "B", "C"], "points": 5},
                ]},
                {"questions": [
                    {"type": "short_answer", "question": "SA", "answer": "expected", "points": 10},
                ]},
            ]
        }
        result = grade_instant_only(assessment, {"0-0": "B", "1-0": "answer"})
        assert result["score"] == 5  # Only MC scored
        assert result["questions"][0]["is_correct"] is True
        assert result["questions"][1]["status"] == "pending_review"

    def test_no_answer_provided(self):
        from backend.routes.student_portal_routes import grade_instant_only
        assessment = {
            "sections": [{
                "questions": [
                    {"type": "multiple_choice", "question": "Q1", "answer": "A", "options": ["A", "B"], "points": 5},
                ]
            }]
        }
        result = grade_instant_only(assessment, {})
        assert result["score"] == 0

    def test_question_type_fallback(self):
        """Questions with question_type but no type should still be graded."""
        from backend.routes.student_portal_routes import grade_instant_only
        assessment = {
            "sections": [{
                "questions": [
                    {"question_type": "true_false", "question": "Q1", "answer": "True", "points": 5},
                ]
            }]
        }
        result = grade_instant_only(assessment, {"0-0": "True"})
        assert result["score"] == 5

    def test_matching_scoring(self):
        from backend.routes.student_portal_routes import grade_instant_only
        assessment = {
            "sections": [{
                "questions": [{
                    "type": "matching",
                    "question": "Match terms",
                    "terms": ["Cat", "Dog"],
                    "definitions": ["Feline", "Canine"],
                    "answer": {"Cat": "Feline", "Dog": "Canine"},
                    "points": 10,
                }]
            }]
        }
        # Must include base key "0-0" to pass the None/empty check,
        # plus individual match keys for each term.
        result = grade_instant_only(assessment, {
            "0-0": "matching",
            "0-0-match-0": "A",
            "0-0-match-1": "B",
        })
        assert result["score"] == 10


class TestGradeStudentSubmission:
    """Test the full grading function (with AI mocked)."""

    def test_mc_only_no_ai(self):
        from backend.routes.student_portal_routes import grade_student_submission
        assessment = {
            "sections": [{
                "questions": [
                    {"type": "multiple_choice", "question": "Q1", "answer": "C", "options": ["A", "B", "C", "D"], "points": 10},
                ]
            }]
        }
        result = grade_student_submission(assessment, {"0-0": "C"})
        assert result["score"] == 10
        assert result["percentage"] == 100
