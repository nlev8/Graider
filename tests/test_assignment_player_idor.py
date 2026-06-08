"""Tenant-isolation regression tests for the assignment-player endpoints.

Origin: security audit 2026-06 (#2, #19). `GET /api/assignment/<id>/submissions`
was guarded only by @require_teacher with NO ownership check, against a flat global
ASSIGNMENTS_DIR whose assignment records carried no owner — so any authenticated
teacher could read any other teacher's students' submissions (FERPA PII) given the
assignment id (which is the anonymous student share link, so it leaks easily).

Fix under test: create_assignment stamps teacher_id; get_submissions returns 404
unless the calling teacher owns the assignment.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture
def app(tmp_path, monkeypatch):
    os.environ['FLASK_ENV'] = 'development'
    from backend.app import app as flask_app
    flask_app.config['TESTING'] = True
    import backend.routes.assignment_player_routes as apr
    monkeypatch.setattr(apr, 'ASSIGNMENTS_DIR', str(tmp_path / 'active_assignments'))
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def _hdr(teacher_id):
    return {'X-Test-Teacher-Id': teacher_id, 'Content-Type': 'application/json'}


def _create(client, teacher_id, title='Quiz'):
    r = client.post('/api/assignment',
                    json={'assignment': {'title': title, 'sections': []}},
                    headers=_hdr(teacher_id))
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()['assignment_id']


def test_create_assignment_records_owner(client):
    aid = _create(client, 'teacher-A')
    import backend.routes.assignment_player_routes as apr
    with open(os.path.join(apr.ASSIGNMENTS_DIR, f'{aid}.json')) as f:
        stored = json.load(f)
    assert stored.get('teacher_id') == 'teacher-A', "owner must be stamped at create time"


def test_get_submissions_denies_non_owner(client):
    """The core IDOR: teacher B must NOT read teacher A's submissions."""
    aid = _create(client, 'teacher-A')
    r = client.get(f'/api/assignment/{aid}/submissions', headers=_hdr('teacher-B'))
    assert r.status_code == 404
    body = r.get_json() or {}
    assert 'submissions' not in body, "non-owner must not receive submissions payload"


def test_get_submissions_allows_owner(client):
    aid = _create(client, 'teacher-A')
    r = client.get(f'/api/assignment/{aid}/submissions', headers=_hdr('teacher-A'))
    assert r.status_code == 200
    assert 'submissions' in r.get_json()


def test_get_submissions_legacy_no_owner_denied(client):
    """A pre-fix assignment file with no teacher_id is unverifiable → denied."""
    import backend.routes.assignment_player_routes as apr
    os.makedirs(apr.ASSIGNMENTS_DIR, exist_ok=True)
    legacy_id = 'assign_legacyNoOwner'
    with open(os.path.join(apr.ASSIGNMENTS_DIR, f'{legacy_id}.json'), 'w') as f:
        json.dump({'id': legacy_id, 'title': 'old', 'sections': []}, f)
    r = client.get(f'/api/assignment/{legacy_id}/submissions', headers=_hdr('teacher-A'))
    assert r.status_code == 404
