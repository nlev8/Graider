"""Direct-import tests for backend/services/student_comparison.py (Wave 5 Slice 4c).

The endpoint is comprehensively characterized by tests/test_assessment_comparison.py;
these pin the service's contract: callable Flask-free with a passed-in db + the
already-validated `found` rows, returning the distribution-stats + standards-matrix
payload dict.
"""
from unittest.mock import MagicMock


def _chain(data=None):
    c = MagicMock()
    for m in ('select', 'eq', 'neq', 'in_', 'order', 'range', 'limit'):
        getattr(c, m).return_value = c
    c.execute.return_value = MagicMock(data=data if data is not None else [])
    return c


def _db(table_map):
    db = MagicMock()
    db.table.side_effect = lambda name: _chain(table_map.get(name, []))
    return db


def test_empty_roster_yields_zero_stats():
    from backend.services.student_comparison import build_assessment_comparison
    found = [{'id': 'ct1', 'title': 'A', 'content_type': 'assessment', 'content': {}, 'settings': {}},
             {'id': 'ct2', 'title': 'B', 'content_type': 'assessment', 'content': {}, 'settings': {}}]
    out = build_assessment_comparison(_db({'class_students': []}), 'c1', 'P1', ['ct1', 'ct2'], found, 'latest')
    assert out['class_roster_size'] == 0
    assert {a['content_id'] for a in out['assessments']} == {'ct1', 'ct2'}
    for a in out['assessments']:
        assert a['n'] == 0 and a['mean'] == 0 and a['submission_rate'] == 0.0
    assert out['standards_matrix']['standards'] == []


def test_two_students_distribution_stats():
    from backend.services.student_comparison import build_assessment_comparison
    found = [{'id': 'ct1', 'title': 'Quiz', 'content_type': 'assessment', 'content': {}, 'settings': {}}]
    db = _db({
        'class_students': [{'student_id': 's1'}, {'student_id': 's2'}],
        'students': [{'id': 's1'}, {'id': 's2'}],
        'student_submissions': [
            {'id': 'a', 'student_id': 's1', 'content_id': 'ct1', 'attempt_number': 1,
             'submitted_at': '2026-04-01T00:00:00Z', 'percentage': 60, 'status': 'graded', 'results': {}},
            {'id': 'b', 'student_id': 's2', 'content_id': 'ct1', 'attempt_number': 1,
             'submitted_at': '2026-04-01T00:00:00Z', 'percentage': 80, 'status': 'graded', 'results': {}},
        ],
    })
    out = build_assessment_comparison(db, 'c1', 'P1', ['ct1'], found, 'latest')
    a = out['assessments'][0]
    assert a['n'] == 2
    assert a['mean'] == 70.0          # (60 + 80) / 2
    assert a['min'] == 60 and a['max'] == 80
    assert a['submission_rate'] == 1.0  # 2 of 2 enrolled
