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


class TestBuildStandardsMasteryNewShape:
    """Phase 4.3 Sprint 2: _build_standards_mastery emits new shape
    {standard: {overall, by_dok}}. overall always present (matches
    pre-Sprint-2 flat fields). by_dok only contains DOKs that
    contributed at least one question; questions with missing/invalid
    dok count toward overall but NOT any by_dok bucket.
    """

    def test_uniform_dok_emits_overall_plus_one_dok_bucket(self):
        from backend.services.grading_service import _build_standards_mastery
        result = _build_standards_mastery([
            {'standard': 'MA.6.AR.1', 'points_earned': 3, 'points_possible': 5, 'dok': 3},
            {'standard': 'MA.6.AR.1', 'points_earned': 4, 'points_possible': 5, 'dok': 3},
        ])
        assert 'MA.6.AR.1' in result
        entry = result['MA.6.AR.1']
        assert entry['overall'] == {
            'points_earned': 7,
            'points_possible': 10,
            'question_count': 2,
        }
        assert list(entry['by_dok'].keys()) == [3]
        assert entry['by_dok'][3] == {
            'points_earned': 7,
            'points_possible': 10,
            'question_count': 2,
        }

    def test_mixed_dok_emits_multiple_dok_buckets(self):
        from backend.services.grading_service import _build_standards_mastery
        result = _build_standards_mastery([
            {'standard': 'MA.6.AR.1', 'points_earned': 4, 'points_possible': 4, 'dok': 1},
            {'standard': 'MA.6.AR.1', 'points_earned': 2, 'points_possible': 6, 'dok': 3},
        ])
        entry = result['MA.6.AR.1']
        assert entry['overall']['points_earned'] == 6
        assert entry['overall']['points_possible'] == 10
        assert entry['overall']['question_count'] == 2
        assert sorted(entry['by_dok'].keys()) == [1, 3]
        assert entry['by_dok'][1] == {
            'points_earned': 4, 'points_possible': 4, 'question_count': 1,
        }
        assert entry['by_dok'][3] == {
            'points_earned': 2, 'points_possible': 6, 'question_count': 1,
        }

    def test_questions_without_dok_count_toward_overall_only(self):
        """Questions with missing/invalid dok contribute to overall but
        get NO by_dok bucket. Preserves mastery totals while refusing
        bad categorization."""
        from backend.services.grading_service import _build_standards_mastery
        result = _build_standards_mastery([
            {'standard': 'MA.6.AR.1', 'points_earned': 3, 'points_possible': 4, 'dok': 2},
            {'standard': 'MA.6.AR.1', 'points_earned': 5, 'points_possible': 5},  # no dok
            {'standard': 'MA.6.AR.1', 'points_earned': 1, 'points_possible': 2, 'dok': 'garbage'},
        ])
        entry = result['MA.6.AR.1']
        assert entry['overall']['question_count'] == 3, "all 3 count toward overall"
        assert entry['overall']['points_earned'] == 9
        assert entry['overall']['points_possible'] == 11
        assert list(entry['by_dok'].keys()) == [2], "only DOK 2 has a bucket"
        assert entry['by_dok'][2]['question_count'] == 1

    def test_questions_without_standard_skipped(self):
        from backend.services.grading_service import _build_standards_mastery
        result = _build_standards_mastery([
            {'points_earned': 3, 'points_possible': 4, 'dok': 1},  # no standard
            {'standard': '', 'points_earned': 2, 'points_possible': 2, 'dok': 1},
            {'standard': 'MA.6.AR.1', 'points_earned': 5, 'points_possible': 5, 'dok': 2},
        ])
        assert list(result.keys()) == ['MA.6.AR.1']
        assert result['MA.6.AR.1']['overall']['question_count'] == 1

    def test_empty_questions_returns_empty_dict(self):
        from backend.services.grading_service import _build_standards_mastery
        assert _build_standards_mastery([]) == {}
        assert _build_standards_mastery(None) == {}
