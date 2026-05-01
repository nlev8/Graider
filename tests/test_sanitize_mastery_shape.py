"""Tests for _sanitize_standards_mastery shape-awareness (Phase 4.3 Sprint 2).

Spec: docs/superpowers/specs/2026-05-01-phase4.3-sprint2-per-dok-mastery-design.md
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


class TestSanitizeStandardsMasteryShapeAware:
    """_sanitize_standards_mastery now retrofits old shape -> new shape
    in place, drops malformed entries, and preserves new-shape entries
    with sub-structure validation.

    Mutates submission dict in place; returns nothing.
    """

    def test_sanitize_old_flat_shape_wraps_in_place(self):
        from backend.routes.student_portal_routes import _sanitize_standards_mastery
        sub = {
            'results': {
                'standards_mastery': {
                    'MA.6.AR.1': {
                        'points_earned': 8, 'points_possible': 10,
                        'question_count': 2, 'percentage': 80,
                    },
                },
            },
        }
        _sanitize_standards_mastery(sub)
        entry = sub['results']['standards_mastery']['MA.6.AR.1']
        assert 'overall' in entry
        assert entry['overall']['points_earned'] == 8
        assert entry['by_dok'] == {}

    def test_sanitize_new_shape_passthrough(self):
        from backend.routes.student_portal_routes import _sanitize_standards_mastery
        sub = {
            'results': {
                'standards_mastery': {
                    'MA.6.AR.1': {
                        'overall': {'points_earned': 7, 'points_possible': 10, 'question_count': 2},
                        'by_dok': {3: {'points_earned': 7, 'points_possible': 10, 'question_count': 2}},
                    },
                },
            },
        }
        _sanitize_standards_mastery(sub)
        entry = sub['results']['standards_mastery']['MA.6.AR.1']
        assert entry['overall']['points_earned'] == 7
        assert 3 in entry['by_dok']

    def test_sanitize_malformed_entry_dropped(self):
        from backend.routes.student_portal_routes import _sanitize_standards_mastery
        sub = {
            'results': {
                'standards_mastery': {
                    'MA.6.AR.1': "not a dict",
                    'MA.6.AR.2': {'overall': {'points_earned': 5, 'points_possible': 5, 'question_count': 1}, 'by_dok': {}},
                },
            },
        }
        _sanitize_standards_mastery(sub)
        cleaned = sub['results']['standards_mastery']
        assert 'MA.6.AR.1' not in cleaned
        assert 'MA.6.AR.2' in cleaned

    def test_sanitize_string_dok_keys_in_by_dok_normalized(self):
        """JSON serialization can produce string DOK keys; sanitize
        normalizes via the adapter."""
        from backend.routes.student_portal_routes import _sanitize_standards_mastery
        sub = {
            'results': {
                'standards_mastery': {
                    'MA.6.AR.1': {
                        'overall': {'points_earned': 4, 'points_possible': 4, 'question_count': 1},
                        'by_dok': {'3': {'points_earned': 4, 'points_possible': 4, 'question_count': 1}},
                    },
                },
            },
        }
        _sanitize_standards_mastery(sub)
        entry = sub['results']['standards_mastery']['MA.6.AR.1']
        assert 3 in entry['by_dok']
