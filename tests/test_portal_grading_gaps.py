"""Gap-fill tests for backend/services/portal_grading.py.

Audit MAJOR #4 sprint follow-up to PR #334. Targets the 69 missing
LOC (83.0% baseline). Focus: deterministic helpers and exception
paths in grade_written_questions, _score_to_letter, build_portal_ai_notes.

Per dual-rate-limit precedent: test-only PR merging on green CI.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


MODULE = "backend.services.portal_grading"


# ──────────────────────────────────────────────────────────────────
# _score_to_letter pure helper
# ──────────────────────────────────────────────────────────────────


class TestScoreToLetter:
    def test_a_grade(self):
        from backend.services.portal_grading import _score_to_letter
        assert _score_to_letter(95) == "A"
        assert _score_to_letter(90) == "A"

    def test_b_grade(self):
        from backend.services.portal_grading import _score_to_letter
        assert _score_to_letter(85) == "B"
        assert _score_to_letter(80) == "B"

    def test_c_grade(self):
        from backend.services.portal_grading import _score_to_letter
        assert _score_to_letter(75) == "C"
        assert _score_to_letter(70) == "C"

    def test_d_grade(self):
        from backend.services.portal_grading import _score_to_letter
        assert _score_to_letter(65) == "D"
        assert _score_to_letter(60) == "D"

    def test_f_grade(self):
        from backend.services.portal_grading import _score_to_letter
        assert _score_to_letter(50) == "F"
        assert _score_to_letter(0) == "F"


# ──────────────────────────────────────────────────────────────────
# has_written_questions
# ──────────────────────────────────────────────────────────────────


class TestHasWrittenQuestions:
    def test_no_written_returns_false(self):
        from backend.services.portal_grading import has_written_questions
        assessment = {"sections": [
            {"questions": [
                {"type": "multiple_choice"},
                {"type": "true_false"},
            ]}
        ]}
        assert has_written_questions(assessment) is False

    def test_short_answer_returns_true(self):
        from backend.services.portal_grading import has_written_questions
        assessment = {"sections": [
            {"questions": [
                {"type": "multiple_choice"},
                {"type": "short_answer"},
            ]}
        ]}
        assert has_written_questions(assessment) is True

    def test_essay_returns_true(self):
        from backend.services.portal_grading import has_written_questions
        assessment = {"sections": [
            {"questions": [{"type": "essay"}]}
        ]}
        assert has_written_questions(assessment) is True

    def test_extended_response_returns_true(self):
        from backend.services.portal_grading import has_written_questions
        assessment = {"sections": [
            {"questions": [{"type": "extended_response"}]}
        ]}
        assert has_written_questions(assessment) is True

    def test_default_type_multiple_choice_returns_false(self):
        # Question without 'type' field defaults to multiple_choice
        from backend.services.portal_grading import has_written_questions
        assessment = {"sections": [
            {"questions": [{}]}  # no type
        ]}
        assert has_written_questions(assessment) is False

    def test_empty_assessment_returns_false(self):
        from backend.services.portal_grading import has_written_questions
        assert has_written_questions({}) is False
        assert has_written_questions({"sections": []}) is False


# ──────────────────────────────────────────────────────────────────
# build_portal_ai_notes - all parameter branches
# ──────────────────────────────────────────────────────────────────


class TestBuildPortalAiNotes:
    def test_includes_global_ai_notes(self):
        from backend.services.portal_grading import build_portal_ai_notes
        result = build_portal_ai_notes(global_ai_notes="be lenient")
        assert "be lenient" in result

    def test_includes_assignment_title(self):
        from backend.services.portal_grading import build_portal_ai_notes
        result = build_portal_ai_notes(assignment_title="Quiz 1")
        assert "ASSIGNMENT: Quiz 1" in result

    def test_includes_grade_and_subject(self):
        from backend.services.portal_grading import build_portal_ai_notes
        result = build_portal_ai_notes(grade_level="8", subject="Civics")
        assert "GRADE LEVEL: 8" in result
        assert "SUBJECT: Civics" in result

    def test_includes_grading_style(self):
        from backend.services.portal_grading import build_portal_ai_notes
        result = build_portal_ai_notes(grading_style="strict")
        assert "GRADING STYLE: strict" in result

    def test_includes_accommodation_prompt(self):
        from backend.services.portal_grading import build_portal_ai_notes
        result = build_portal_ai_notes(
            accommodation_prompt="Extended time + word bank",
        )
        assert "Extended time" in result

    def test_includes_student_history(self):
        from backend.services.portal_grading import build_portal_ai_notes
        result = build_portal_ai_notes(
            student_history="Previous scores: 85, 90",
        )
        assert "Previous scores" in result

    def test_includes_class_period(self):
        from backend.services.portal_grading import build_portal_ai_notes
        result = build_portal_ai_notes(class_period="Period 3")
        assert "Period 3" in result

    def test_includes_correction_context(self):
        from backend.services.portal_grading import build_portal_ai_notes
        result = build_portal_ai_notes(
            correction_context="prior teacher edits: x → y",
        )
        assert "prior teacher edits" in result


# ──────────────────────────────────────────────────────────────────
# grade_written_questions - provider routing + exception fallback
# ──────────────────────────────────────────────────────────────────


class TestGradeWrittenQuestions:
    def test_anthropic_model_routes_to_anthropic_provider(self):
        from backend.services.portal_grading import grade_written_questions

        questions = [
            {"type": "short_answer", "_answer_key": "0-0",
             "question": "Why?", "answer": "Because", "points": 5},
        ]
        answers = {"0-0": "I think because..."}

        with patch(f"{MODULE}.grade_per_question",
                   return_value={"grade": {"score": 4}}) as mock_gpq:
            results = grade_written_questions(
                questions=questions, answers=answers,
                ai_notes="", grade_level="8", subject="Civics",
                grading_style="standard",
                ai_model="claude-sonnet-4-20250514",
            )
        assert len(results) == 1
        # Verify provider passed to grade_per_question is anthropic
        call_kwargs = mock_gpq.call_args.kwargs
        assert call_kwargs["ai_provider"] == "anthropic"

    def test_gemini_model_routes_to_gemini_provider(self):
        from backend.services.portal_grading import grade_written_questions

        questions = [
            {"type": "short_answer", "_answer_key": "0-0",
             "question": "Q", "answer": "A", "points": 5},
        ]
        with patch(f"{MODULE}.grade_per_question",
                   return_value={"grade": {"score": 5}}) as mock_gpq:
            grade_written_questions(
                questions=questions, answers={"0-0": "answer"},
                ai_notes="", grade_level="", subject="",
                grading_style="standard",
                ai_model="gemini-2.0-flash",
            )
        assert mock_gpq.call_args.kwargs["ai_provider"] == "gemini"

    def test_openai_model_default_provider(self):
        from backend.services.portal_grading import grade_written_questions

        questions = [
            {"type": "short_answer", "_answer_key": "0-0",
             "question": "Q", "answer": "A", "points": 5},
        ]
        with patch(f"{MODULE}.grade_per_question",
                   return_value={"grade": {"score": 5}}) as mock_gpq:
            grade_written_questions(
                questions=questions, answers={"0-0": "ans"},
                ai_notes="", grade_level="", subject="",
                grading_style="standard",
            )
        assert mock_gpq.call_args.kwargs["ai_provider"] == "openai"

    def test_non_written_question_type_skipped(self):
        from backend.services.portal_grading import grade_written_questions

        questions = [
            {"type": "multiple_choice", "_answer_key": "0-0",
             "question": "Q", "answer": "A", "points": 5},
        ]
        with patch(f"{MODULE}.grade_per_question") as mock_gpq:
            results = grade_written_questions(
                questions=questions, answers={},
                ai_notes="", grade_level="", subject="",
                grading_style="standard",
            )
        # MC question skipped (not in WRITTEN_TYPES)
        assert results == []
        mock_gpq.assert_not_called()

    def test_empty_student_answer_default_empty_string(self):
        from backend.services.portal_grading import grade_written_questions

        questions = [
            {"type": "short_answer", "_answer_key": "0-0",
             "question": "Q", "answer": "A", "points": 5},
        ]
        # No answer provided → defaults to empty string
        with patch(f"{MODULE}.grade_per_question",
                   return_value={"grade": {"score": 0}}) as mock_gpq:
            grade_written_questions(
                questions=questions, answers={},
                ai_notes="", grade_level="", subject="",
                grading_style="standard",
            )
        assert mock_gpq.call_args.kwargs["student_answer"] == ""

    def test_grade_per_question_exception_returns_error_result(self):
        # Lines 179-188: exception in grade_per_question → fallback dict
        from backend.services.portal_grading import grade_written_questions

        questions = [
            {"type": "short_answer", "_answer_key": "0-0",
             "question": "Q", "answer": "A", "points": 7},
        ]
        with patch(f"{MODULE}.grade_per_question",
                   side_effect=RuntimeError("API down")):
            results = grade_written_questions(
                questions=questions, answers={"0-0": "ans"},
                ai_notes="", grade_level="", subject="",
                grading_style="standard",
            )
        assert len(results) == 1
        assert results[0]["grade"]["score"] == 0
        assert results[0]["grade"]["possible"] == 7
        assert results[0]["grade"]["quality"] == "error"
        assert "Grading failed" in results[0]["grade"]["reasoning"]


# ──────────────────────────────────────────────────────────────────
# _import_from_assignment_grader exception path
# ──────────────────────────────────────────────────────────────────


class TestImportFromAssignmentGrader:
    def test_import_error_returns_none_pages_sentry(self):
        from backend.services.portal_grading import (
            _import_from_assignment_grader,
        )

        with patch(f"{MODULE}.import_module",
                   side_effect=ImportError("module missing")), \
             patch(f"{MODULE}.sentry_sdk.capture_exception") as mock_sentry:
            result = _import_from_assignment_grader("nonexistent_attr")
        assert result is None
        mock_sentry.assert_called_once()

    def test_attribute_error_returns_none_pages_sentry(self):
        from backend.services.portal_grading import (
            _import_from_assignment_grader,
        )

        # import_module succeeds but attribute doesn't exist
        fake_mod = MagicMock(spec=[])  # no attributes
        # getattr will raise AttributeError on the spec=[] mock
        with patch(f"{MODULE}.import_module", return_value=fake_mod), \
             patch(f"{MODULE}.sentry_sdk.capture_exception") as mock_sentry:
            result = _import_from_assignment_grader("nonexistent_attr")
        assert result is None
        mock_sentry.assert_called_once()

    def test_happy_path_returns_attribute(self):
        from backend.services.portal_grading import (
            _import_from_assignment_grader,
        )

        fake_mod = MagicMock()
        fake_mod.my_function = lambda x: x * 2
        with patch(f"{MODULE}.import_module", return_value=fake_mod):
            result = _import_from_assignment_grader("my_function")
        assert result(5) == 10
