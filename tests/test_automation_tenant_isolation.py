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


def test_save_id_traversal_cannot_overwrite_other_tenant(client):
    """Codex-found bypass: save_automation trusted the client-supplied body 'id'.
    A crafted id like '../teacher-B/<wf>' would escape the caller's subdir and
    overwrite another teacher's workflow. The body id must be sanitized like the
    URL handlers sanitize workflow_id."""
    _save(client, 'teacher-B', 'Victim WF')  # teacher-B owns id 'victim-wf'
    client.post('/api/automations',
                json={'id': '../teacher-B/victim-wf', 'name': 'evil', 'steps': []},
                headers=_hdr('teacher-A'))
    lb = client.get('/api/automations', headers=_hdr('teacher-B')).get_json()['workflows']
    victim = next((w for w in lb if w['id'] == 'victim-wf'), None)
    assert victim is not None and victim['name'] == 'Victim WF', (
        "teacher-A overwrote teacher-B's workflow via path traversal in the save body id"
    )


def test_run_status_does_not_leak_other_tenant_run(client):
    """The runner is a single global subprocess; teacher B must not see
    teacher A's run status/workflow_name/log (audit #8 / Codex residual)."""
    import backend.routes.automation_routes as ar
    try:
        ar._run_state.update({"status": "running", "workflow_name": "A secret wf",
                              "teacher_id": "teacher-A", "process": None, "log": ["secret"]})
        st = client.get('/api/automations/run/status', headers=_hdr('teacher-B')).get_json()
        assert st["status"] == "idle"
        assert st["workflow_name"] == ""
        assert st["log"] == []
    finally:
        ar._run_state.update({"status": "idle", "teacher_id": None, "process": None, "log": []})


def test_stop_run_cannot_stop_other_tenant_run(client):
    """Teacher B must not be able to kill teacher A's running automation (DoS)."""
    import backend.routes.automation_routes as ar
    try:
        ar._run_state.update({"status": "running", "teacher_id": "teacher-A",
                              "process": None, "log": []})
        r = client.post('/api/automations/run/stop', headers=_hdr('teacher-B'))
        assert r.status_code == 404
        assert ar._run_state["status"] == "running", "teacher B stopped teacher A's run"
    finally:
        ar._run_state.update({"status": "idle", "teacher_id": None, "process": None, "log": []})


def test_stop_run_cannot_reset_other_tenant_terminal_state(client):
    """A done/error run owned by A must not be resettable by B (Codex round-3 #3)."""
    import backend.routes.automation_routes as ar
    try:
        ar._run_state.update({"status": "done", "teacher_id": "teacher-A", "process": None, "log": []})
        r = client.post('/api/automations/run/stop', headers=_hdr('teacher-B'))
        assert r.status_code == 404
        assert ar._run_state["status"] == "done", "teacher B reset teacher A's terminal state"
    finally:
        ar._run_state.update({"status": "idle", "teacher_id": None, "process": None, "log": []})


def test_picker_events_do_not_leak_other_tenant(client):
    """Picker is a single global subprocess; B must not drain A's selector events."""
    import backend.routes.automation_routes as ar
    try:
        ar._picker_state.update({"status": "picking", "teacher_id": "teacher-A",
                                 "events": [{"selector": "#secret"}], "process": None})
        st = client.get('/api/automations/picker/events', headers=_hdr('teacher-B')).get_json()
        assert st["status"] == "idle"
        assert st["events"] == []
        # A's events must remain undrained
        assert ar._picker_state["events"] == [{"selector": "#secret"}]
    finally:
        ar._picker_state.update({"status": "idle", "teacher_id": None, "events": [], "process": None})


def test_stop_picker_cannot_stop_other_tenant(client):
    import backend.routes.automation_routes as ar
    try:
        ar._picker_state.update({"status": "picking", "teacher_id": "teacher-A",
                                 "events": [], "process": None})
        r = client.post('/api/automations/picker/stop', headers=_hdr('teacher-B'))
        assert r.status_code == 404
        assert ar._picker_state["status"] == "picking", "teacher B stopped teacher A's picker"
    finally:
        ar._picker_state.update({"status": "idle", "teacher_id": None, "events": [], "process": None})


def test_stop_picker_cannot_touch_other_tenant_nonpicking_state(client):
    """stop_picker must protect ANY non-idle owned state (Codex round-4): a
    terminal/stamped picker state owned by A must not be resettable by B."""
    import backend.routes.automation_routes as ar
    try:
        ar._picker_state.update({"status": "done", "teacher_id": "teacher-A",
                                 "events": [], "process": None})
        r = client.post('/api/automations/picker/stop', headers=_hdr('teacher-B'))
        assert r.status_code == 404
        assert ar._picker_state["status"] == "done", "teacher B reset teacher A's picker state"
    finally:
        ar._picker_state.update({"status": "idle", "teacher_id": None, "events": [], "process": None})
