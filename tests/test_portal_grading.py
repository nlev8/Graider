"""Tests for portal multipass grading service."""
import pytest
from unittest.mock import patch, MagicMock, ANY


class TestHasWrittenQuestions:
    """Test the auto-detection logic for written vs MC-only assignments."""

    def test_mc_only_returns_false(self):
        from backend.services.portal_grading import has_written_questions
        assessment = {
            "sections": [{
                "questions": [
                    {"type": "multiple_choice", "question": "Q1"},
                    {"type": "true_false", "question": "Q2"},
                    {"type": "matching", "question": "Q3"},
                ]
            }]
        }
        assert has_written_questions(assessment) is False

    def test_short_answer_returns_true(self):
        from backend.services.portal_grading import has_written_questions
        assessment = {
            "sections": [{
                "questions": [
                    {"type": "multiple_choice", "question": "Q1"},
                    {"type": "short_answer", "question": "Q2"},
                ]
            }]
        }
        assert has_written_questions(assessment) is True

    def test_extended_response_returns_true(self):
        from backend.services.portal_grading import has_written_questions
        assessment = {
            "sections": [{
                "questions": [
                    {"type": "extended_response", "question": "Q1"},
                ]
            }]
        }
        assert has_written_questions(assessment) is True

    def test_empty_assessment_returns_false(self):
        from backend.services.portal_grading import has_written_questions
        assert has_written_questions({}) is False
        assert has_written_questions({"sections": []}) is False


class TestBuildPortalAINotes:
    """Test that AI instruction string is built correctly for portal grading."""

    def test_includes_global_ai_notes(self):
        from backend.services.portal_grading import build_portal_ai_notes
        result = build_portal_ai_notes(
            global_ai_notes="Be encouraging",
            assignment_title="Test Assignment",
            grade_level="8",
            subject="US History",
        )
        assert "Be encouraging" in result

    def test_includes_grade_and_subject(self):
        from backend.services.portal_grading import build_portal_ai_notes
        result = build_portal_ai_notes(
            grade_level="8",
            subject="US History",
        )
        assert "8" in result
        assert "US History" in result


class TestGradeWrittenQuestions:
    """Test the written question grading orchestrator."""

    @patch("backend.services.portal_grading.grade_per_question")
    def test_calls_grade_per_question_for_each_written(self, mock_gpq):
        from backend.services.portal_grading import grade_written_questions
        mock_gpq.return_value = {
            "grade": {"score": 8, "possible": 10, "quality": "good", "reasoning": "Solid answer"}
        }
        questions = [
            {"type": "short_answer", "question": "Explain X", "answer": "Expected", "points": 10, "_answer_key": "0-1"},
            {"type": "extended_response", "question": "Analyze Y", "answer": "Expected", "points": 20, "_answer_key": "1-0"},
        ]
        answers = {"0-1": "Student answer 1", "1-0": "Student answer 2"}

        results = grade_written_questions(
            questions=questions,
            answers=answers,
            ai_notes="Be encouraging",
            grade_level="8",
            subject="US History",
            grading_style="standard",
            ai_model="gpt-4o-mini",
        )

        assert mock_gpq.call_count == 2
        assert len(results) == 2
        assert results[0]["grade"]["score"] == 8

    @patch("backend.services.portal_grading.grade_per_question")
    def test_uses_answer_key_not_sequential_index(self, mock_gpq):
        """Verify answers are looked up by section-question key, not sequential index."""
        from backend.services.portal_grading import grade_written_questions
        mock_gpq.return_value = {
            "grade": {"score": 5, "possible": 10, "quality": "ok", "reasoning": "Partial"}
        }
        questions = [
            {"type": "short_answer", "question": "Q", "answer": "A", "points": 10, "_answer_key": "2-3"},
        ]
        answers = {"0": "WRONG KEY", "2-3": "Correct student answer"}

        grade_written_questions(
            questions=questions, answers=answers,
            ai_notes="", grade_level="8", subject="History",
            grading_style="standard",
        )

        call_args = mock_gpq.call_args
        assert call_args[1]["student_answer"] == "Correct student answer" or call_args[0][1] == "Correct student answer"


class TestBuildResultRecord:
    """Test that result records match the analytics-expected format."""

    def test_builds_correct_format(self):
        from backend.services.portal_grading import build_result_record
        record = build_result_record(
            student_name="Jane Doe",
            student_id="stu_123",
            assignment_title="Colonial America",
            score=85,
            total_possible=100,
            period="Q3",
            feedback="Good work",
            breakdown={"content_accuracy": 88, "completeness": 90, "writing_quality": 78, "effort_engagement": 85},
            per_question_scores=[],
        )
        assert record["student_name"] == "Jane Doe"
        assert record["score"] == 85
        assert record["email_approval"] == "pending"
        assert record["source"] == "portal"
        assert record["breakdown"]["content_accuracy"] == 88
        assert record["letter_grade"] == "B"
