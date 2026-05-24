"""Direct-import tests for backend/services/student_gradebook.py (Wave 5 Slice 4a).

The endpoint is comprehensively characterized by tests/test_gradebook.py; these
pin the service's new contract: it returns plain dicts (no jsonify) for both
empty short-circuits and the full case, callable Flask-free with a passed-in db.
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


def test_empty_roster_returns_empty_grid_dict():
    from backend.services.student_gradebook import build_class_gradebook
    out = build_class_gradebook(_db({'class_students': []}), 'c1', 'P1', 'latest')
    assert out == {"class_id": "c1", "class_name": "P1", "attempt_mode": "latest",
                   "students": [], "assessments": [], "grades": {}}


def test_no_assessments_returns_students_but_empty_assessments():
    from backend.services.student_gradebook import build_class_gradebook
    db = _db({
        'class_students': [{'student_id': 's1'}],
        'students': [{'id': 's1', 'first_name': 'A', 'last_name': 'B'}],
        'published_content': [],
    })
    out = build_class_gradebook(db, 'c1', 'P1', 'latest')
    assert out['assessments'] == []
    assert out['grades'] == {}
    assert out['students'] == [{'student_id': 's1', 'student_name': 'A B'}]


def test_full_grid_canonical_grade_latest():
    from backend.services.student_gradebook import build_class_gradebook
    db = _db({
        'class_students': [{'student_id': 's1'}],
        'students': [{'id': 's1', 'first_name': 'A', 'last_name': 'B'}],
        'published_content': [{'id': 'ct1', 'title': 'Q1', 'content_type': 'assessment',
                               'created_at': '2026-04-01', 'due_date': None,
                               'is_active': True, 'target_student_ids': None}],
        'student_submissions': [{'id': 'sub1', 'student_id': 's1', 'content_id': 'ct1',
                                 'attempt_number': 1, 'submitted_at': '2026-04-02T10:00:00Z',
                                 'percentage': 88, 'status': 'graded'}],
    })
    out = build_class_gradebook(db, 'c1', 'P1', 'latest')
    assert out['assessments'][0]['content_id'] == 'ct1'
    assert out['assessments'][0]['publish_date'] == '2026-04-01'  # sourced from created_at
    assert out['grades']['s1']['ct1']['percentage'] == 88
    assert out['grades']['s1']['ct1']['total_attempts'] == 1
