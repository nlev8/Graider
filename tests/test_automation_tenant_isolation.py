"""Tenant-isolation regression tests for automation-workflow endpoints.

Origin: security audit 2026-06 (#8). All automation CRUD/run handlers were
@require_teacher but operated on a single flat global AUTOMATIONS_DIR with no
per-teacher scoping and NO teacher_id on records, AND the workflow id is derived
from the workflow NAME (predictable + collision-prone) — so any authenticated
teacher could list/read/run/delete (or silently overwrite) another teacher's
workflows.

Fix under test: per-tenant sharding of the automations dir (local-dev keeps the
flat layout; real teachers get an isolated subdir), applied to list/get/save/
delete/run.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture
def app(tmp_path, monkeypatch):
    os.environ['FLASK_ENV'] = 'development'
    from backend.app import app as flask_app
    flask_app.config['TESTING'] = True
    import backend.routes.automation_routes as ar
    monkeypatch.setattr(ar, 'AUTOMATIONS_DIR', str(tmp_path / 'automations'))
    os.makedirs(ar.AUTOMATIONS_DIR, exist_ok=True)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def _hdr(teacher_id):
    return {'X-Test-Teacher-Id': teacher_id, 'Content-Type': 'application/json'}


def _save(client, teacher_id, name):
    r = client.post('/api/automations', json={'name': name, 'steps': []}, headers=_hdr(teacher_id))
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()['id']


def test_list_does_not_leak_other_teachers(client):
    _save(client, 'teacher-A', 'A only workflow')
    lb = client.get('/api/automations', headers=_hdr('teacher-B')).get_json()['workflows']
    assert lb == [], "teacher B must not see teacher A's workflows"


def test_same_name_workflows_do_not_collide(client):
    """Name-derived ids would collide in one global file without sharding."""
    _save(client, 'teacher-A', 'Weekly Grading')
    _save(client, 'teacher-B', 'Weekly Grading')
    la = client.get('/api/automations', headers=_hdr('teacher-A')).get_json()['workflows']
    lb = client.get('/api/automations', headers=_hdr('teacher-B')).get_json()['workflows']
    assert len(la) == 1, "teacher A's workflow must survive teacher B saving the same name"
    assert len(lb) == 1


def test_get_other_teacher_workflow_denied(client):
    wf_id = _save(client, 'teacher-A', 'Secret WF')
    rb = client.get(f'/api/automations/{wf_id}', headers=_hdr('teacher-B'))
    assert rb.status_code == 404


def test_delete_other_teacher_workflow_is_noop(client):
    wf_id = _save(client, 'teacher-A', 'Secret WF')
    client.delete(f'/api/automations/{wf_id}', headers=_hdr('teacher-B'))
    ra = client.get(f'/api/automations/{wf_id}', headers=_hdr('teacher-A'))
    assert ra.status_code == 200, "teacher B's delete must not affect teacher A's workflow"


def test_run_other_teacher_workflow_denied(client):
    """Teacher B cannot run teacher A's workflow (404 before any subprocess)."""
    import backend.routes.automation_routes as ar
    ar._run_state['status'] = 'idle'  # ensure not blocked by 409
    wf_id = _save(client, 'teacher-A', 'Secret WF')
    rb = client.post(f'/api/automations/{wf_id}/run', json={}, headers=_hdr('teacher-B'))
    assert rb.status_code == 404


def test_owner_can_get_own_workflow(client):
    wf_id = _save(client, 'teacher-A', 'My WF')
    ra = client.get(f'/api/automations/{wf_id}', headers=_hdr('teacher-A'))
    assert ra.status_code == 200
