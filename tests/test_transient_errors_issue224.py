"""Regression tests for issue #224 — inner catches in the grading
pipeline swallow AI transients before Celery autoretry can see them.

Four catch sites flagged by Codex round-1 review of PR #223:

  - `grade_per_question` outer try (now in backend/services/grading_leaves.py,
    Wave 7 Phase B; re-exported via assignment_grader)
  - `generate_feedback` outer try (now in backend/services/grading_leaves.py)
  - `backend/services/portal_grading.py::grade_written_questions`
    per-question loop catch (line 184)
  - `backend/services/portal_grading.py::_safe_generate_feedback`
    wrapper (line 257)

Pre-fix each one caught `Exception` and returned a fallback dict,
producing silently-bad grades during AI 5xx storms (provider
unavailable → 0-score "grading error" → submission marked graded →
Celery never sees the transient → no retry). Post-fix the inner
catches classify via `backend.retry.is_retryable_error`; transient
failures re-raise as `backend.tasks.grading_tasks.TransientError`
so Celery's `autoretry_for=(TransientError,)` can fire. Non-transient
errors (ValueError, programming bugs) still produce the fallback so
single-question failures don't kill the whole grading run.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _celery_broker_env(monkeypatch):
    """`backend.tasks.grading_tasks` imports `backend.celery_app`,
    which `raise RuntimeError` if `CELERY_BROKER_URL` is unset (see
    `celery_app.py:14-17`). Set a dummy value so the import succeeds
    — we never actually connect to Redis in these tests. Matches the
    pattern at `tests/test_celery_transient_retry.py:27`."""
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/15")


# A transient class name `is_retryable_error` matches by name without
# needing the real openai/anthropic SDK imports.
class _FakeAPIConnectionError(Exception):
    """Mimics openai.APIConnectionError's class-name signature."""
    pass


_FakeAPIConnectionError.__name__ = "APIConnectionError"


# ──────────────────────────────────────────────────────────────────
# assignment_grader.grade_per_question
# ──────────────────────────────────────────────────────────────────


class TestGradePerQuestionTransientPropagates:
    """Transient exceptions inside `grade_per_question`'s outer try
    must propagate as `TransientError`, not be swallowed into a
    fallback dict."""

    def test_transient_class_name_raises_transient_error(self):
        import assignment_grader
        from backend.tasks.grading_tasks import TransientError

        # Patch `with_retry` (wraps the provider call) to raise a
        # transient-class exception. The inner catch must classify
        # and re-raise.
        def _raise_transient(*args, **kwargs):
            raise _FakeAPIConnectionError("provider 5xx storm")

        with patch("backend.services.grading_leaves.with_retry",
                          side_effect=_raise_transient), \
             patch.object(assignment_grader, "openai_client",
                          create=True):
            with pytest.raises(TransientError) as excinfo:
                assignment_grader.grade_per_question(
                    question="What is the capital of France?",
                    student_answer="Paris",
                    expected_answer="Paris",
                    points=10,
                    grade_level="6",
                    subject="Social Studies",
                    teacher_instructions="",
                    grading_style="standard",
                    ai_provider="openai",
                )

        # Original transient is preserved as the chained cause.
        assert isinstance(excinfo.value.__cause__, _FakeAPIConnectionError)

    def test_non_transient_returns_fallback_dict(self):
        """Programming errors (e.g. ValueError) still hit the fallback
        path — don't kill the whole grading run for one bad question."""
        import assignment_grader

        def _raise_value_error(*args, **kwargs):
            raise ValueError("malformed schema")

        with patch("backend.services.grading_leaves.with_retry",
                          side_effect=_raise_value_error), \
             patch.object(assignment_grader, "openai_client",
                          create=True):
            result = assignment_grader.grade_per_question(
                question="What is the capital of France?",
                student_answer="Paris",
                expected_answer="Paris",
                points=10,
                grade_level="6",
                subject="Social Studies",
                teacher_instructions="",
                grading_style="standard",
                ai_provider="openai",
            )

        # Fallback dict — graceful degradation for non-transient errors.
        assert result["grade"]["score"] == 0
        assert "could not" in result["grade"]["reasoning"].lower() or \
               "error" in result["grade"]["reasoning"].lower()


# ──────────────────────────────────────────────────────────────────
# assignment_grader.generate_feedback
# ──────────────────────────────────────────────────────────────────


class TestGenerateFeedbackTransientPropagates:
    def test_transient_class_name_raises_transient_error(self):
        import assignment_grader
        from backend.tasks.grading_tasks import TransientError

        def _raise_transient(*args, **kwargs):
            raise _FakeAPIConnectionError("provider down")

        with patch("backend.services.grading_leaves.with_retry",
                          side_effect=_raise_transient), \
             patch.object(assignment_grader, "openai_client",
                          create=True):
            with pytest.raises(TransientError):
                assignment_grader.generate_feedback(
                    question_results=[],
                    total_score=80,
                    total_possible=100,
                    letter_grade="B",
                    grade_level="6",
                    subject="Social Studies",
                    ai_provider="openai",
                )

    def test_non_transient_returns_fallback(self):
        import assignment_grader

        def _raise_value_error(*args, **kwargs):
            raise ValueError("bad input")

        with patch("backend.services.grading_leaves.with_retry",
                          side_effect=_raise_value_error), \
             patch.object(assignment_grader, "openai_client",
                          create=True):
            result = assignment_grader.generate_feedback(
                question_results=[],
                total_score=80,
                total_possible=100,
                letter_grade="B",
                grade_level="6",
                subject="Social Studies",
                ai_provider="openai",
            )

        # Generic encouraging fallback rather than a raise.
        assert "feedback" in result
        assert isinstance(result["feedback"], str)


# ──────────────────────────────────────────────────────────────────
# portal_grading.grade_written_questions per-question loop
# ──────────────────────────────────────────────────────────────────


class TestPortalGradeWrittenQuestionsTransientPropagates:
    """`grade_written_questions` (portal_grading.py:184) wraps each
    `grade_per_question` call in a per-question try/except so one bad
    question doesn't crash the whole submission. Pre-fix that catch
    also swallowed TransientErrors that grade_per_question now raises.
    Post-fix transients are re-raised so Celery's outer retry sees
    them; only non-transient errors get the per-question fallback."""

    def _questions_and_answers(self):
        return (
            [{
                "type": "short_answer",
                "question": "Define democracy.",
                "answer": "Government by the people.",
                "points": 10,
                "_answer_key": "0-0",
                "section_name": "Civics",
            }],
            {"0-0": "Government by the people."},
        )

    def test_transient_from_grade_per_question_propagates(self):
        from backend.services import portal_grading
        from backend.tasks.grading_tasks import TransientError

        questions, answers = self._questions_and_answers()

        with patch.object(
            portal_grading, "grade_per_question",
            side_effect=TransientError("transient: provider 5xx"),
        ):
            with pytest.raises(TransientError):
                portal_grading.grade_written_questions(
                    questions, answers,
                    ai_notes="", grade_level="6", subject="Civics",
                    grading_style="standard", ai_model="gpt-4o-mini",
                )

    def test_non_transient_returns_per_question_fallback(self):
        """A plain ValueError on one question still falls back so the
        rest of the questions can grade."""
        from backend.services import portal_grading

        questions, answers = self._questions_and_answers()

        with patch.object(
            portal_grading, "grade_per_question",
            side_effect=ValueError("bad question schema"),
        ):
            results = portal_grading.grade_written_questions(
                questions, answers,
                ai_notes="", grade_level="6", subject="Civics",
                grading_style="standard", ai_model="gpt-4o-mini",
            )

        # 1 question → 1 fallback result, not a raise.
        assert len(results) == 1
        assert results[0]["grade"]["score"] == 0


# ──────────────────────────────────────────────────────────────────
# portal_grading._safe_generate_feedback
# ──────────────────────────────────────────────────────────────────


class TestSafeGenerateFeedbackTransientPropagates:
    def test_transient_from_generate_feedback_propagates(self):
        from backend.services import portal_grading
        from backend.tasks.grading_tasks import TransientError

        with patch.object(
            portal_grading, "generate_feedback",
            side_effect=TransientError("transient: provider 5xx"),
        ):
            with pytest.raises(TransientError):
                portal_grading._safe_generate_feedback(
                    question_results=[],
                    total_score=80,
                    total_possible=100,
                    letter_grade="B",
                    grade_level="6",
                    subject="Civics",
                )

    def test_non_transient_returns_safe_fallback(self):
        from backend.services import portal_grading

        with patch.object(
            portal_grading, "generate_feedback",
            side_effect=ValueError("malformed result"),
        ):
            result = portal_grading._safe_generate_feedback(
                question_results=[],
                total_score=80,
                total_possible=100,
                letter_grade="B",
                grade_level="6",
                subject="Civics",
            )

        # Returns a dict (not raise) for non-transient errors.
        assert isinstance(result, dict)
