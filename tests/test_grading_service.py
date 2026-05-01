"""Tests for backend.services.grading_service per-question + mastery contracts.

Phase 4.3 Sprint 2 — verifies the dok passthrough at both per-question
writers (grade_student_submission + grade_instant_only) and the new
{overall, by_dok} shape from _build_standards_mastery.
"""
import inspect

import pytest


class TestGradingServiceDokPassthrough:
    """Phase 4.3 Sprint 2: per-question result writers must include
    "dok": question.get("dok") so dok flows from published_content.content
    into student_submissions.results.questions[i].dok.

    Mirrors the source-check pattern used by Sprint 1 in
    test_grade_portal_submission_sync.py — behavioral grading tests need
    extensive AI/DB mocking, so this pinning is intentional.
    """

    def test_grade_student_submission_emits_dok_in_question_result(self):
        from backend.services.grading_service import grade_student_submission
        src = inspect.getsource(grade_student_submission)
        assert '"dok": question.get("dok")' in src, (
            "grade_student_submission's question_result dict must include "
            "the dok field so per-DOK mastery can be computed downstream"
        )

    def test_grade_instant_only_emits_dok_in_question_result(self):
        from backend.services.grading_service import grade_instant_only
        src = inspect.getsource(grade_instant_only)
        assert '"dok": question.get("dok")' in src, (
            "grade_instant_only's question_result dict must include the "
            "dok field so per-DOK mastery can be computed downstream"
        )
