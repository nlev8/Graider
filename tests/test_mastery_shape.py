"""Tests for _normalize_mastery_shape — the boundary adapter that handles
both old flat shape (pre-Sprint-2) and new {overall, by_dok} shape.

Spec: docs/superpowers/specs/2026-05-01-phase4.3-sprint2-per-dok-mastery-design.md
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


class TestNormalizeMasteryShape:
    """_normalize_mastery_shape always returns either:
    - A dict with 'overall' (a dict) + 'by_dok' (a dict, possibly empty), OR
    - None (malformed input)

    Old flat shape gets wrapped: existing fields go into overall, by_dok={}.
    New shape passes through with sub-structure validation.
    Bool DOK keys are rejected (via _validate_dok); numeric-string keys are normalized.
    """

    def test_old_flat_shape_wraps_to_new_with_empty_by_dok(self):
        from backend.routes.student_portal_routes import _normalize_mastery_shape
        result = _normalize_mastery_shape({
            'points_earned': 8,
            'points_possible': 10,
            'question_count': 2,
            'percentage': 80,
        })
        assert result is not None
        assert result['overall'] == {
            'points_earned': 8,
            'points_possible': 10,
            'question_count': 2,
            'percentage': 80,
        }
        assert result['by_dok'] == {}

    def test_new_shape_passes_through(self):
        from backend.routes.student_portal_routes import _normalize_mastery_shape
        raw = {
            'overall': {'points_earned': 8, 'points_possible': 10, 'question_count': 2},
            'by_dok': {
                1: {'points_earned': 4, 'points_possible': 4, 'question_count': 1},
                3: {'points_earned': 4, 'points_possible': 6, 'question_count': 1},
            },
        }
        result = _normalize_mastery_shape(raw)
        assert result is not None
        assert result['overall'] == raw['overall']
        assert result['by_dok'] == raw['by_dok']

    def test_string_dok_keys_normalized(self):
        """JSON serialization may produce string keys ("1") instead of ints.
        Adapter normalizes via _validate_dok."""
        from backend.routes.student_portal_routes import _normalize_mastery_shape
        result = _normalize_mastery_shape({
            'overall': {'points_earned': 4, 'points_possible': 4, 'question_count': 1},
            'by_dok': {
                '1': {'points_earned': 4, 'points_possible': 4, 'question_count': 1},
            },
        })
        assert 1 in result['by_dok']
        assert '1' not in result['by_dok'], "string keys must be normalized to int"

    def test_malformed_returns_none(self):
        from backend.routes.student_portal_routes import _normalize_mastery_shape
        assert _normalize_mastery_shape(None) is None
        assert _normalize_mastery_shape("invalid") is None
        assert _normalize_mastery_shape([1, 2, 3]) is None
        assert _normalize_mastery_shape(42) is None


class TestFlattenMasteryForResponse:
    """Phase 4.3 Sprint 2 (Codex full-PR MAJOR) — endpoints that return
    raw `results` JSONB project the new {overall, by_dok} shape down to
    flat shape so existing API consumers don't break."""

    def test_new_shape_flattens_to_flat(self):
        from backend.routes.student_portal_routes import _flatten_mastery_for_response
        result = _flatten_mastery_for_response({
            'standards_mastery': {
                'MA.6.AR.1': {
                    'overall': {'points_earned': 8, 'points_possible': 10, 'question_count': 2},
                    'by_dok': {3: {'points_earned': 8, 'points_possible': 10, 'question_count': 2}},
                },
            },
        })
        entry = result['standards_mastery']['MA.6.AR.1']
        assert entry == {
            'percentage': 80.0,
            'points_earned': 8,
            'points_possible': 10,
            'question_count': 2,
        }
        assert 'overall' not in entry
        assert 'by_dok' not in entry

    def test_flat_shape_passes_through(self):
        from backend.routes.student_portal_routes import _flatten_mastery_for_response
        result = _flatten_mastery_for_response({
            'standards_mastery': {
                'MA.6.AR.1': {
                    'percentage': 80, 'points_earned': 8,
                    'points_possible': 10, 'question_count': 2,
                },
            },
        })
        entry = result['standards_mastery']['MA.6.AR.1']
        assert entry['percentage'] == 80
        assert entry['points_earned'] == 8

    def test_does_not_mutate_input(self):
        from backend.routes.student_portal_routes import _flatten_mastery_for_response
        original = {
            'standards_mastery': {
                'MA.6.AR.1': {
                    'overall': {'points_earned': 8, 'points_possible': 10, 'question_count': 2},
                    'by_dok': {3: {'points_earned': 8, 'points_possible': 10, 'question_count': 2}},
                },
            },
        }
        _flatten_mastery_for_response(original)
        # Input still has new shape
        assert 'overall' in original['standards_mastery']['MA.6.AR.1']

    def test_none_results_returns_none(self):
        from backend.routes.student_portal_routes import _flatten_mastery_for_response
        assert _flatten_mastery_for_response(None) is None

    def test_no_standards_mastery_passes_through(self):
        from backend.routes.student_portal_routes import _flatten_mastery_for_response
        result = _flatten_mastery_for_response({'score': 5, 'total_points': 10})
        # Other fields preserved; standards_mastery untouched (absent)
        assert result.get('score') == 5
