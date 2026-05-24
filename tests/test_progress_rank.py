"""Characterization tests for get_class_progress_rank.

Written BEFORE the Wave 5 Slice 3 route-body extraction to pin the behavior
that has no dedicated test today — in particular the CACHE ASYMMETRY: only the
full payload is cached; the empty-roster and empty-content short-circuits are
returned un-cached (so a teacher who just added their first assessment/student
doesn't see a stale-empty grid for up to the 30s TTL). The extraction must
preserve this exactly.
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

TEACHER = 'test-teacher-001'


@pytest.fixture
def app():
    os.environ['FLASK_ENV'] = 'development'
    os.environ['DEV_USER_ID'] = TEACHER
    from backend.app import app as flask_app
    flask_app.config['TESTING'] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def headers():
    return {'X-Test-Teacher-Id': TEACHER, 'Content-Type': 'application/json'}


@pytest.fixture(autouse=True)
def _clear_cache():
    from backend.routes.student_portal_routes import _progress_rank_cache
    _progress_rank_cache.clear()
    yield
    _progress_rank_cache.clear()


def _make_chain(execute_data=None):
    chain = MagicMock()
    for m in ('select', 'eq', 'neq', 'in_', 'order', 'limit'):
        getattr(chain, m).return_value = chain
    chain.execute.return_value = MagicMock(data=execute_data if execute_data is not None else [])
    return chain


def _multi_table_sb(table_map):
    mock_sb = MagicMock()
    mock_sb.table.side_effect = lambda name: _make_chain(table_map.get(name, []))
    return mock_sb


def _cache_key(class_id, mode='latest'):
    return (TEACHER, class_id, mode)


def test_wrong_teacher_returns_403_and_not_cached(client, headers):
    with patch('backend.routes.student_portal_routes._get_teacher_supabase') as sb:
        sb.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'OTHER'}],
        })
        resp = client.get('/api/teacher/class/cls-1/progress-rank', headers=headers)
    assert resp.status_code == 403
    from backend.routes.student_portal_routes import _progress_rank_cache
    assert _progress_rank_cache.get(_cache_key('cls-1')) is None


def test_empty_roster_short_circuit_is_not_cached(client, headers):
    with patch('backend.routes.student_portal_routes._get_teacher_supabase') as sb:
        sb.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-2', 'name': 'Period 2', 'teacher_id': TEACHER}],
            'class_students': [],          # no roster
        })
        resp = client.get('/api/teacher/class/cls-2/progress-rank', headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {"class_id": "cls-2", "class_name": "Period 2",
                    "attempt_mode": "latest", "standards": [], "students": []}
    from backend.routes.student_portal_routes import _progress_rank_cache
    assert _progress_rank_cache.get(_cache_key('cls-2')) is None  # asymmetry: empty NOT cached


def test_empty_content_short_circuit_is_not_cached(client, headers):
    with patch('backend.routes.student_portal_routes._get_teacher_supabase') as sb:
        sb.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-3', 'name': 'Period 3', 'teacher_id': TEACHER}],
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'Jane', 'last_name': 'Doe'}],
            'published_content': [],       # roster exists but no assessments yet
        })
        resp = client.get('/api/teacher/class/cls-3/progress-rank', headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['standards'] == []
    assert body['students'] == [{'student_id': 'stu-1', 'student_name': 'Jane Doe', 'mastery': {}}]
    from backend.routes.student_portal_routes import _progress_rank_cache
    assert _progress_rank_cache.get(_cache_key('cls-3')) is None  # asymmetry: empty-content NOT cached


def test_full_payload_is_cached_and_served_on_second_call(client, headers):
    full_tables = {
        'classes': [{'id': 'cls-4', 'name': 'Period 4', 'teacher_id': TEACHER}],
        'class_students': [{'student_id': 'stu-1'}],
        'students': [{'id': 'stu-1', 'first_name': 'Amy', 'last_name': 'Lee'}],
        'published_content': [{'id': 'ct-1', 'title': 'Quiz 1', 'content_type': 'assessment'}],
        'student_submissions': [{
            'id': 'sub-1', 'student_id': 'stu-1', 'content_id': 'ct-1',
            'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
            'percentage': 80, 'status': 'graded',
            'results': {'standards_mastery': {'MA.6.AR.1.1': {
                'points_earned': 8, 'points_possible': 10, 'question_count': 2}}},
        }],
    }
    with patch('backend.routes.student_portal_routes._get_teacher_supabase') as sb:
        sb.return_value = _multi_table_sb(full_tables)
        resp1 = client.get('/api/teacher/class/cls-4/progress-rank', headers=headers)
    assert resp1.status_code == 200
    body1 = resp1.get_json()
    assert body1['class_name'] == 'Period 4'
    assert body1['standards'] == ['MA.6.AR.1.1']
    assert body1['students'][0]['student_name'] == 'Amy Lee'
    assert body1['students'][0]['mastery']['MA.6.AR.1.1']['percentage'] == 80.0

    # The full payload IS cached.
    from backend.routes.student_portal_routes import _progress_rank_cache
    assert _progress_rank_cache.get(_cache_key('cls-4')) == body1

    # Second call: even if the DB now returns nothing, the cached payload is served.
    with patch('backend.routes.student_portal_routes._get_teacher_supabase') as sb2:
        sb2.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-4', 'name': 'Period 4', 'teacher_id': TEACHER}],
            'class_students': [],  # would be empty now, but cache wins
        })
        resp2 = client.get('/api/teacher/class/cls-4/progress-rank', headers=headers)
    assert resp2.get_json() == body1  # served from cache, not recomputed


def test_invalid_attempt_mode_falls_back_to_latest(client, headers):
    with patch('backend.routes.student_portal_routes._get_teacher_supabase') as sb:
        sb.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-5', 'name': 'P5', 'teacher_id': TEACHER}],
            'class_students': [],
        })
        resp = client.get('/api/teacher/class/cls-5/progress-rank?attempt_mode=bogus', headers=headers)
    assert resp.get_json()['attempt_mode'] == 'latest'
