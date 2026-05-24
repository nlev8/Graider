"""Direct-import tests for backend/services/student_progress_reports.py
(Wave 5 Slice 3). Pins the new (payload, cacheable) contract that encodes the
progress-rank cache asymmetry, plus report-card assembly, independent of Flask."""
from unittest.mock import MagicMock


def _chain(data=None):
    c = MagicMock()
    for m in ('select', 'eq', 'neq', 'in_', 'order', 'limit'):
        getattr(c, m).return_value = c
    c.execute.return_value = MagicMock(data=data if data is not None else [])
    return c


def _db(table_map):
    db = MagicMock()
    db.table.side_effect = lambda name: _chain(table_map.get(name, []))
    return db


def test_progress_rank_empty_roster_returns_not_cacheable():
    from backend.services.student_progress_reports import build_class_progress_rank
    payload, cacheable = build_class_progress_rank(_db({'class_students': []}), 'c1', 'P1', 'latest')
    assert cacheable is False
    assert payload == {"class_id": "c1", "class_name": "P1", "attempt_mode": "latest",
                       "standards": [], "students": []}


def test_progress_rank_empty_content_returns_not_cacheable():
    from backend.services.student_progress_reports import build_class_progress_rank
    db = _db({
        'class_students': [{'student_id': 's1'}],
        'students': [{'id': 's1', 'first_name': 'A', 'last_name': 'B'}],
        'published_content': [],
    })
    payload, cacheable = build_class_progress_rank(db, 'c1', 'P1', 'latest')
    assert cacheable is False
    assert payload['standards'] == []
    assert payload['students'] == [{'student_id': 's1', 'student_name': 'A B', 'mastery': {}}]


def test_progress_rank_full_payload_is_cacheable():
    from backend.services.student_progress_reports import build_class_progress_rank
    db = _db({
        'class_students': [{'student_id': 's1'}],
        'students': [{'id': 's1', 'first_name': 'A', 'last_name': 'B'}],
        'published_content': [{'id': 'ct1', 'title': 'Q1', 'content_type': 'assessment'}],
        'student_submissions': [{
            'id': 'sub1', 'student_id': 's1', 'content_id': 'ct1', 'attempt_number': 1,
            'submitted_at': '2026-04-10T10:00:00Z', 'percentage': 90, 'status': 'graded',
            'results': {'standards_mastery': {'STD.1': {'points_earned': 9, 'points_possible': 10, 'question_count': 1}}},
        }],
    })
    payload, cacheable = build_class_progress_rank(db, 'c1', 'P1', 'latest')
    assert cacheable is True
    assert payload['standards'] == ['STD.1']
    assert payload['students'][0]['mastery']['STD.1']['percentage'] == 90.0


def test_report_card_no_content_returns_empty_arrays():
    from backend.services.student_progress_reports import build_student_report_card
    payload = build_student_report_card(_db({'published_content': []}), 'c1', 'P1', 's1', 'Amy Lee', 'latest')
    assert payload == {"student_id": "s1", "student_name": "Amy Lee", "class_id": "c1",
                       "class_name": "P1", "attempt_mode": "latest",
                       "trajectory": [], "standards_breakdown": []}


def test_report_card_assembles_trajectory_and_breakdown():
    from backend.services.student_progress_reports import build_student_report_card
    db = _db({
        'published_content': [{'id': 'ct1', 'title': 'Q1', 'content_type': 'assessment'}],
        'student_submissions': [{
            'id': 'sub1', 'student_id': 's1', 'content_id': 'ct1', 'attempt_number': 1,
            'submitted_at': '2026-04-10T10:00:00Z', 'percentage': 70, 'status': 'graded',
            'results': {'standards_mastery': {'STD.1': {'points_earned': 7, 'points_possible': 10, 'question_count': 1}},
                        'points_earned': 7, 'points_possible': 10},
        }],
    })
    payload = build_student_report_card(db, 'c1', 'P1', 's1', 'Amy Lee', 'latest')
    assert [t['submission_id'] for t in payload['trajectory']] == ['sub1']
    assert [b['code'] for b in payload['standards_breakdown']] == ['STD.1']
