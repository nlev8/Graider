"""Phase 4: deny-tests for single-row student-facing endpoints when the
viewer is not in target_student_ids.

Each of: get_student_content, student_resource_content, submit_student_work,
save_submission_draft, get_submission_draft must return 404 (not the row's
content) when target_student_ids is set and the viewer is NOT in it.

NOTE: Task 11 adds a session-enrollment-recheck call inside _validate_student_session,
which adds a 4th .execute() in the route's call sequence. Step 11.1 will retroactively
update the mock chains in this file to a 4-element sequence. At this Task 9 point in
the plan, the route makes 3 .execute() calls — the 3-element mock sequences below match.
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture
def app():
    from backend.app import app as flask_app
    flask_app.config['TESTING'] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def student_headers():
    return {'X-Student-Token': 'test-token-stu-1'}


def _session_chain(student_id, class_id):
    """Mock for the student_sessions lookup in _validate_student_session."""
    from datetime import datetime, timezone, timedelta
    expires = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat().replace('+00:00', 'Z')
    return [{'student_id': student_id, 'class_id': class_id, 'expires_at': expires}]


def _content_chain_targeted_to(other_student_id, content_id='ct-1', class_id='cls-1'):
    """A published_content row visible only to other_student_id."""
    return [{'id': content_id, 'class_id': class_id, 'is_active': True,
             'target_student_ids': [other_student_id], 'content': {'questions': []},
             'title': 'T', 'content_type': 'assessment', 'settings': {}}]


STU_VIEWER = '11111111-1111-1111-1111-111111111111'
STU_OTHER = '22222222-2222-2222-2222-222222222222'


@patch('backend.routes.student_account_routes._get_supabase')
def test_get_student_content_404_for_non_targeted(mock_sb, client, student_headers):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    # Sequence: session lookup → enrollment recheck → content fetch.
    chain.execute.side_effect = [
        MagicMock(data=_session_chain(STU_VIEWER, 'cls-1')),
        MagicMock(data=[{'student_id': STU_VIEWER}]),  # session enrollment recheck (Task 11)
        MagicMock(data=[{'student_id': STU_VIEWER}]),  # helper enrollment check
        MagicMock(data=_content_chain_targeted_to(STU_OTHER)),
    ]
    sb = MagicMock(); sb.table.return_value = chain
    mock_sb.return_value = sb
    resp = client.get('/api/student/content/ct-1', headers=student_headers)
    assert resp.status_code == 404


@patch('backend.routes.student_account_routes._get_supabase')
def test_student_resource_content_404_for_non_targeted(mock_sb, client, student_headers):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.execute.side_effect = [
        MagicMock(data=_session_chain(STU_VIEWER, 'cls-1')),
        MagicMock(data=[{'student_id': STU_VIEWER}]),  # session enrollment recheck (Task 11)
        MagicMock(data=[{'student_id': STU_VIEWER}]),  # helper enrollment check
        MagicMock(data=_content_chain_targeted_to(STU_OTHER)),
    ]
    sb = MagicMock(); sb.table.return_value = chain
    mock_sb.return_value = sb
    resp = client.get('/api/student/resource/ct-1', headers=student_headers)
    assert resp.status_code == 404


@patch('backend.routes.student_account_routes._get_supabase')
def test_submit_student_work_404_for_non_targeted(mock_sb, client, student_headers):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.insert.return_value = chain
    chain.execute.side_effect = [
        MagicMock(data=_session_chain(STU_VIEWER, 'cls-1')),
        MagicMock(data=[{'student_id': STU_VIEWER}]),  # session enrollment recheck (Task 11)
        MagicMock(data=[{'student_id': STU_VIEWER}]),  # helper enrollment check
        MagicMock(data=_content_chain_targeted_to(STU_OTHER)),
    ]
    sb = MagicMock(); sb.table.return_value = chain
    mock_sb.return_value = sb
    resp = client.post('/api/student/submit/ct-1', json={'answers': {}}, headers=student_headers)
    assert resp.status_code == 404


@patch('backend.routes.student_account_routes._get_supabase')
def test_save_submission_draft_404_for_non_targeted(mock_sb, client, student_headers):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.execute.side_effect = [
        MagicMock(data=_session_chain(STU_VIEWER, 'cls-1')),
        MagicMock(data=[{'student_id': STU_VIEWER}]),  # session enrollment recheck (Task 11)
        MagicMock(data=[{'student_id': STU_VIEWER}]),  # helper enrollment check
        MagicMock(data=_content_chain_targeted_to(STU_OTHER)),
    ]
    sb = MagicMock(); sb.table.return_value = chain
    mock_sb.return_value = sb
    resp = client.post('/api/student/submission/ct-1/draft', json={'answers': {}}, headers=student_headers)
    assert resp.status_code == 404


@patch('backend.routes.student_account_routes._get_supabase')
def test_get_submission_draft_404_for_non_targeted(mock_sb, client, student_headers):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.execute.side_effect = [
        MagicMock(data=_session_chain(STU_VIEWER, 'cls-1')),
        MagicMock(data=[{'student_id': STU_VIEWER}]),  # session enrollment recheck (Task 11)
        MagicMock(data=[{'student_id': STU_VIEWER}]),  # helper enrollment check
        MagicMock(data=_content_chain_targeted_to(STU_OTHER)),
    ]
    sb = MagicMock(); sb.table.return_value = chain
    mock_sb.return_value = sb
    resp = client.get('/api/student/submission/ct-1/draft', headers=student_headers)
    assert resp.status_code == 404
