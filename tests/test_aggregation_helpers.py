"""Tests for _aggregate_mastery_for_student (Phase 4.3 Sprint 2).

The aggregator now operates on normalized (Sprint 2) shape internally.
Default output (include_dok=False) preserves the existing flat-shape
API contract; include_dok=True emits the new shape with by_dok
sub-aggregates.

Spec: docs/superpowers/specs/2026-05-01-phase4.3-sprint2-per-dok-mastery-design.md
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


def _sub(sub_id, content_id, mastery_dict, attempt=1):
    """Helper to build a fake submission row with results.standards_mastery."""
    return {
        'id': sub_id, 'content_id': content_id, 'attempt_number': attempt,
        'submitted_at': '2026-04-10T10:00:00Z',
        'results': {'standards_mastery': mastery_dict},
        'status': 'graded',
    }


class TestAggregateMasteryForStudent:
    """Aggregator handles old + new shapes via internal normalization
    and emits flat-by-default output (include_dok=False) or new-shape
    output (include_dok=True)."""

    def test_include_dok_false_preserves_flat_api(self):
        """Default include_dok=False — output matches pre-Sprint-2 shape
        exactly. Existing routes don't need to change."""
        from backend.routes.student_portal_routes import _aggregate_mastery_for_student
        # Pre-Sprint-2 stored shape — adapter wraps it inside aggregator.
        sub = _sub('s-1', 'ct-1', {
            'MA.6.AR.1': {
                'points_earned': 8, 'points_possible': 10, 'question_count': 2,
            },
        })
        result = _aggregate_mastery_for_student(
            {'ct-1': [sub]}, {'ct-1': 'Quiz 1'}, 'latest',
        )
        assert 'MA.6.AR.1' in result
        entry = result['MA.6.AR.1']
        # Existing flat fields present at top level
        assert entry['percentage'] == 80
        assert entry['points_earned'] == 8
        assert entry['points_possible'] == 10
        assert entry['question_count'] == 2
        # by_dok must NOT appear in flat-default output
        assert 'by_dok' not in entry

    def test_include_dok_true_emits_new_shape(self):
        from backend.routes.student_portal_routes import _aggregate_mastery_for_student
        # New-shape stored data with mixed DOK
        sub = _sub('s-1', 'ct-1', {
            'MA.6.AR.1': {
                'overall': {'points_earned': 6, 'points_possible': 10, 'question_count': 2},
                'by_dok': {
                    1: {'points_earned': 4, 'points_possible': 4, 'question_count': 1},
                    3: {'points_earned': 2, 'points_possible': 6, 'question_count': 1},
                },
            },
        })
        result = _aggregate_mastery_for_student(
            {'ct-1': [sub]}, {'ct-1': 'Quiz 1'}, 'latest',
            include_dok=True,
        )
        entry = result['MA.6.AR.1']
        # New-shape output: overall + by_dok with percentages computed at agg time
        assert entry['overall']['percentage'] == 60
        assert entry['overall']['points_earned'] == 6
        assert entry['overall']['question_count'] == 2
        assert sorted(entry['by_dok'].keys()) == [1, 3]
        assert entry['by_dok'][1]['percentage'] == 100
        assert entry['by_dok'][3]['percentage'] == round(2 / 6 * 100, 1)

    def test_old_shape_input_aggregates_via_adapter(self):
        """Aggregator's adapter handles old-shape stored data even with
        include_dok=True — by_dok will just be empty."""
        from backend.routes.student_portal_routes import _aggregate_mastery_for_student
        sub = _sub('s-1', 'ct-1', {
            'MA.6.AR.1': {
                'points_earned': 7, 'points_possible': 10, 'question_count': 2,
            },
        })
        result = _aggregate_mastery_for_student(
            {'ct-1': [sub]}, {'ct-1': 'Quiz'}, 'latest', include_dok=True,
        )
        entry = result['MA.6.AR.1']
        assert entry['overall']['percentage'] == 70
        assert entry['by_dok'] == {}, (
            "Old-shape stored data has no DOK info; by_dok must be empty"
        )

    def test_average_mode_aggregates_by_dok_across_attempts(self):
        from backend.routes.student_portal_routes import _aggregate_mastery_for_student
        sub_a = _sub('s-1', 'ct-1', {
            'MA.6.AR.1': {
                'overall': {'points_earned': 4, 'points_possible': 8, 'question_count': 2},
                'by_dok': {3: {'points_earned': 4, 'points_possible': 8, 'question_count': 2}},
            },
        }, attempt=1)
        sub_b = _sub('s-2', 'ct-1', {
            'MA.6.AR.1': {
                'overall': {'points_earned': 6, 'points_possible': 8, 'question_count': 2},
                'by_dok': {3: {'points_earned': 6, 'points_possible': 8, 'question_count': 2}},
            },
        }, attempt=2)
        result = _aggregate_mastery_for_student(
            {'ct-1': [sub_a, sub_b]}, {'ct-1': 'Quiz'}, 'average',
            include_dok=True,
        )
        entry = result['MA.6.AR.1']
        # Average mode averages percentages across attempts:
        #   attempt 1: 4/8 = 50%, attempt 2: 6/8 = 75%, average = 62.5%
        assert entry['overall']['percentage'] == 62.5
        # by_dok averaged the same way
        assert entry['by_dok'][3]['percentage'] == 62.5
