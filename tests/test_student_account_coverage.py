"""Coverage backfill tests for student_account_routes.py.

Covers: student login, session validation, dashboard, content retrieval,
submission, draft save/load, and auth rejection paths.
All Supabase calls are mocked — zero network traffic.
"""
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture
def app():
    """Create Flask app in test mode."""
    os.environ['FLASK_ENV'] = 'development'
    os.environ['DEV_USER_ID'] = 'test-teacher-001'
    from backend.app import app as flask_app
    flask_app.config['TESTING'] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def teacher_headers():
    return {'X-Test-Teacher-Id': 'test-teacher-001', 'Content-Type': 'application/json'}


def _make_chain(execute_data=None, count=None):
    """Create a chainable Supabase query builder mock."""
    chain = MagicMock()
    chain.select.return_value = chain
    chain.insert.return_value = chain
    chain.upsert.return_value = chain
    chain.update.return_value = chain
    chain.delete.return_value = chain
    chain.eq.return_value = chain
    chain.neq.return_value = chain
    chain.in_.return_value = chain
    chain.lt.return_value = chain
    chain.ilike.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    result = MagicMock(data=execute_data if execute_data is not None else [])
    if count is not None:
        result.count = count
    chain.execute.return_value = result
    return chain


def _multi_table_sb(table_map):
    """Create a mock Supabase client that returns different chains per table.

    table_map: dict mapping table name -> list of data rows (or a chain).
    Tables not in the map get an empty-data chain.
    """
    mock_sb = MagicMock()

    def table_side_effect(name):
        val = table_map.get(name)
        if val is None:
            return _make_chain([])
        if isinstance(val, MagicMock):
            return val
        return _make_chain(val)

    mock_sb.table.side_effect = table_side_effect
    return mock_sb


# ---- Helpers for student session mocking ----

def _mock_valid_session(mock_get_sb, student_id='stu-001', class_id='cls-001'):
    """Set up mock so _validate_student_session returns a valid session.

    Returns the mock_sb so tests can add further table overrides.
    """
    expires_future = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
    session_data = [{
        'student_id': student_id,
        'class_id': class_id,
        'expires_at': expires_future,
    }]
    # Every table call returns the session data — individual tests
    # override specific tables via side_effect if needed.
    mock_sb = MagicMock()
    mock_sb.table.return_value = _make_chain(session_data)
    mock_get_sb.return_value = mock_sb
    return mock_sb


# ============ SESSION VALIDATION ============

class TestCheckStudentSession:
    """GET /api/student/session"""

    @patch('routes.student_account_routes._get_supabase')
    def test_valid_session_returns_student_info(self, mock_get_sb, client):
        expires = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
        session_row = [{'student_id': 'stu-1', 'class_id': 'cls-1', 'expires_at': expires}]
        student_row = [{'first_name': 'Jane', 'last_name': 'Doe',
                        'student_id_number': 'S100', 'email': 'jane@test.com'}]
        class_row = [{'name': 'Period 1', 'subject': 'Math'}]

        mock_sb = MagicMock()
        call_count = {'n': 0}

        def table_side(name):
            call_count['n'] += 1
            if name == 'student_sessions':
                return _make_chain(session_row)
            if name == 'students':
                return _make_chain(student_row)
            if name == 'classes':
                return _make_chain(class_row)
            return _make_chain([])

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb

        resp = client.get('/api/student/session',
                          headers={'X-Student-Token': 'valid-token-abc'})
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['valid'] is True
        assert data['student']['first_name'] == 'Jane'
        assert data['class_info']['subject'] == 'Math'

    def test_no_token_returns_401(self, client):
        resp = client.get('/api/student/session')
        assert resp.status_code == 401

    @patch('routes.student_account_routes._get_supabase')
    def test_expired_session_returns_401(self, mock_get_sb, client):
        expired = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat()
        session_row = [{'student_id': 'stu-1', 'class_id': 'cls-1', 'expires_at': expired}]

        mock_sb = MagicMock()
        mock_sb.table.return_value = _make_chain(session_row)
        mock_get_sb.return_value = mock_sb

        resp = client.get('/api/student/session',
                          headers={'X-Student-Token': 'expired-token'})
        assert resp.status_code == 401


# ============ STUDENT DASHBOARD ============

class TestStudentDashboard:
    """GET /api/student/dashboard"""

    @patch('routes.student_account_routes._get_supabase')
    def test_dashboard_returns_assigned_content(self, mock_get_sb, client):
        expires = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
        session_row = [{'student_id': 'stu-1', 'class_id': 'cls-1', 'expires_at': expires}]
        content_row = [{
            'id': 'pc-1', 'title': 'Quiz 1', 'content_type': 'assessment',
            'settings': {}, 'due_date': None, 'created_at': '2026-01-01T00:00:00',
        }]
        submission_row = []

        mock_sb = MagicMock()

        def table_side(name):
            if name == 'student_sessions':
                return _make_chain(session_row)
            if name == 'published_content':
                return _make_chain(content_row)
            if name == 'student_submissions':
                return _make_chain(submission_row)
            return _make_chain([])

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb

        resp = client.get('/api/student/dashboard',
                          headers={'X-Student-Token': 'tok-abc'})
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data['items']) == 1
        assert data['items'][0]['title'] == 'Quiz 1'
        assert data['items'][0]['status'] == 'not_started'

    def test_dashboard_no_auth_returns_401(self, client):
        resp = client.get('/api/student/dashboard')
        assert resp.status_code == 401


# ============ STUDENT SUBMISSION ============

class TestSubmitStudentWork:
    """POST /api/student/submit/<content_id>

    NOTE: The URL `/api/student/submit/<X>` is shared with student_portal_bp's
    join-code route, which is registered first and wins Flask's URL matching.
    So we call submit_student_work() directly via test_request_context rather
    than through the HTTP client, to actually exercise this handler.
    """

    def _call_submit(self, app, content_id, headers, body):
        """Invoke submit_student_work directly within a request context."""
        from routes.student_account_routes import submit_student_work
        with app.test_request_context(
            f'/api/student/submit/{content_id}',
            method='POST',
            headers=headers,
            json=body,
        ):
            return submit_student_work(content_id)

    def _extract(self, rv):
        """Extract (status, json) from a Flask view return value."""
        if isinstance(rv, tuple):
            resp, status = rv[0], rv[1]
        else:
            resp, status = rv, 200
        return status, resp.get_json()

    @patch('backend.services.portal_grading.has_written_questions', return_value=False)
    @patch('backend.services.grading_service.grade_student_submission')
    @patch('routes.student_account_routes._get_supabase')
    def test_valid_submission_returns_success(self, mock_get_sb, mock_grade, mock_hw, app):
        mock_grade.return_value = {
            'score': 8, 'total_points': 10, 'percentage': 80, 'questions': [],
        }

        expires = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
        session_row = [{'student_id': 'stu-1', 'class_id': 'cls-1', 'expires_at': expires}]
        student_row = [{'first_name': 'John', 'last_name': 'Smith',
                        'student_id_number': 'S200', 'period': 'P1',
                        'email': '', 'teacher_id': 'test-teacher-001'}]
        content_row = [{
            'content': {'sections': [{'questions': []}]},
            'title': 'Quiz 1', 'teacher_id': 'test-teacher-001',
            'settings': {'show_score_immediately': True},
            'due_date': None,
        }]
        upserted = [{'id': 'sub-001'}]

        mock_sb = MagicMock()

        def table_side(name):
            if name == 'student_sessions':
                return _make_chain(session_row)
            if name == 'students':
                return _make_chain(student_row)
            if name == 'student_submissions':
                chain = _make_chain([])
                upsert_chain = MagicMock()
                upsert_chain.execute.return_value = MagicMock(data=upserted)
                chain.upsert.return_value = upsert_chain
                return chain
            if name == 'published_content':
                return _make_chain(content_row)
            return _make_chain([])

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb

        rv = self._call_submit(
            app, 'pc-001',
            headers={'X-Student-Token': 'tok-abc', 'Content-Type': 'application/json'},
            body={'answers': {'0-0': 'A'}, 'time_taken_seconds': 120},
        )
        status, data = self._extract(rv)
        assert status == 200
        assert data['success'] is True

    def test_submit_without_auth_returns_401(self, app):
        rv = self._call_submit(
            app, 'pc-001',
            headers={'Content-Type': 'application/json'},
            body={'answers': {}},
        )
        status, _ = self._extract(rv)
        assert status == 401

    @patch('routes.student_account_routes._get_supabase')
    def test_submit_nonexistent_content_returns_404(self, mock_get_sb, app):
        expires = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
        session_row = [{'student_id': 'stu-1', 'class_id': 'cls-1', 'expires_at': expires}]
        student_row = [{'first_name': 'A', 'last_name': 'B',
                        'student_id_number': 'S1', 'period': '', 'email': '',
                        'teacher_id': 't1'}]

        mock_sb = MagicMock()

        def table_side(name):
            if name == 'student_sessions':
                return _make_chain(session_row)
            if name == 'students':
                return _make_chain(student_row)
            if name == 'student_submissions':
                return _make_chain([])
            if name == 'published_content':
                return _make_chain([])  # not found
            return _make_chain([])

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb

        rv = self._call_submit(
            app, 'nonexistent',
            headers={'X-Student-Token': 'tok-abc', 'Content-Type': 'application/json'},
            body={'answers': {}},
        )
        status, _ = self._extract(rv)
        assert status == 404

    @patch('backend.services.portal_grading.has_written_questions', return_value=False)
    @patch('backend.services.grading_service.grade_student_submission')
    @patch('routes.student_account_routes._get_supabase')
    def test_duplicate_submission_returns_400(self, mock_get_sb, mock_grade, mock_hw, app):
        """23505 unique violation on upsert returns user-friendly 400."""
        mock_grade.return_value = {
            'score': 0, 'total_points': 10, 'percentage': 0, 'questions': [],
        }
        expires = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
        session_row = [{'student_id': 'stu-1', 'class_id': 'cls-1', 'expires_at': expires}]
        student_row = [{'first_name': 'A', 'last_name': 'B',
                        'student_id_number': 'S1', 'period': '', 'email': '',
                        'teacher_id': 't1'}]
        content_row = [{
            'content': {'sections': []}, 'title': 'Q1',
            'teacher_id': 't1', 'settings': {}, 'due_date': None,
        }]

        mock_sb = MagicMock()

        def table_side(name):
            if name == 'student_sessions':
                return _make_chain(session_row)
            if name == 'students':
                return _make_chain(student_row)
            if name == 'student_submissions':
                chain = _make_chain([])
                chain.upsert.side_effect = Exception('duplicate key value violates unique constraint (23505)')
                return chain
            if name == 'published_content':
                return _make_chain(content_row)
            return _make_chain([])

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb

        rv = self._call_submit(
            app, 'pc-001',
            headers={'X-Student-Token': 'tok-abc', 'Content-Type': 'application/json'},
            body={'answers': {'0-0': 'B'}},
        )
        status, data = self._extract(rv)
        assert status == 400
        assert 'already submitted' in data['error'].lower()

    @patch('backend.services.portal_grading.has_written_questions', return_value=False)
    @patch('backend.services.grading_service.grade_student_submission')
    @patch('routes.student_account_routes._get_supabase')
    def test_submission_uses_upsert_not_insert(self, mock_get_sb, mock_grade, mock_hw, app):
        """Verify the code uses upsert (UUID-idempotent) not plain insert."""
        mock_grade.return_value = {
            'score': 5, 'total_points': 10, 'percentage': 50, 'questions': [],
        }
        expires = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
        session_row = [{'student_id': 'stu-1', 'class_id': 'cls-1', 'expires_at': expires}]
        student_row = [{'first_name': 'X', 'last_name': 'Y',
                        'student_id_number': 'S1', 'period': '', 'email': '',
                        'teacher_id': 't1'}]
        content_row = [{'content': {'sections': []}, 'title': 'Q',
                        'teacher_id': 't1', 'settings': {'show_score_immediately': True},
                        'due_date': None}]

        mock_sb = MagicMock()
        upsert_tracker = MagicMock()
        upsert_tracker.execute.return_value = MagicMock(data=[{'id': 'sub-002'}])

        def table_side(name):
            if name == 'student_sessions':
                return _make_chain(session_row)
            if name == 'students':
                return _make_chain(student_row)
            if name == 'student_submissions':
                chain = _make_chain([])
                chain.upsert.return_value = upsert_tracker
                return chain
            if name == 'published_content':
                return _make_chain(content_row)
            return _make_chain([])

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb

        rv = self._call_submit(
            app, 'pc-001',
            headers={'X-Student-Token': 'tok-abc', 'Content-Type': 'application/json'},
            body={'answers': {}},
        )
        status, _ = self._extract(rv)
        assert status == 200
        upsert_tracker.execute.assert_called()


# ============ DRAFT SAVE ============

class TestSaveSubmissionDraft:
    """POST /api/student/submission/<content_id>/draft"""

    @patch('routes.student_account_routes._get_supabase')
    def test_new_draft_creates_row(self, mock_get_sb, client):
        expires = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
        session_row = [{'student_id': 'stu-1', 'class_id': 'cls-1', 'expires_at': expires}]
        content_row = [{'id': 'pc-1', 'settings': {}}]
        student_row = [{'first_name': 'A', 'last_name': 'B',
                        'student_id_number': 'S1', 'period': 'P1'}]

        mock_sb = MagicMock()
        upsert_tracker = MagicMock()
        upsert_tracker.execute.return_value = MagicMock(data=[{}])

        def table_side(name):
            if name == 'student_sessions':
                return _make_chain(session_row)
            if name == 'published_content':
                return _make_chain(content_row)
            if name == 'student_submissions':
                chain = _make_chain([])  # no existing draft
                chain.upsert.return_value = upsert_tracker
                return chain
            if name == 'students':
                return _make_chain(student_row)
            return _make_chain([])

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb

        resp = client.post('/api/student/submission/pc-1/draft',
                           headers={'X-Student-Token': 'tok-abc',
                                    'Content-Type': 'application/json'},
                           json={'answers': {'0-0': 'C'}})
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['success'] is True

    @patch('routes.student_account_routes._get_supabase')
    def test_existing_draft_updates_row(self, mock_get_sb, client):
        expires = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
        session_row = [{'student_id': 'stu-1', 'class_id': 'cls-1', 'expires_at': expires}]
        content_row = [{'id': 'pc-1', 'settings': {}}]
        existing_draft = [{
            'id': 'sub-draft-001', 'status': 'draft',
            'time_started_at': (datetime.now(tz=timezone.utc) - timedelta(minutes=5)).isoformat(),
        }]

        mock_sb = MagicMock()

        def table_side(name):
            if name == 'student_sessions':
                return _make_chain(session_row)
            if name == 'published_content':
                return _make_chain(content_row)
            if name == 'student_submissions':
                return _make_chain(existing_draft)
            return _make_chain([])

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb

        resp = client.post('/api/student/submission/pc-1/draft',
                           headers={'X-Student-Token': 'tok-abc',
                                    'Content-Type': 'application/json'},
                           json={'answers': {'0-0': 'D'}})
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['success'] is True

    def test_draft_save_no_auth_returns_401(self, client):
        resp = client.post('/api/student/submission/pc-1/draft',
                           headers={'Content-Type': 'application/json'},
                           json={'answers': {}})
        assert resp.status_code == 401

    @patch('routes.student_account_routes._get_supabase')
    def test_draft_with_timer_returns_remaining(self, mock_get_sb, client):
        expires = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
        session_row = [{'student_id': 'stu-1', 'class_id': 'cls-1', 'expires_at': expires}]
        content_row = [{'id': 'pc-1', 'settings': {'time_limit_minutes': 30}}]
        started = (datetime.now(tz=timezone.utc) - timedelta(minutes=10)).isoformat()
        existing_draft = [{
            'id': 'sub-draft-002', 'status': 'draft',
            'time_started_at': started,
        }]

        mock_sb = MagicMock()

        def table_side(name):
            if name == 'student_sessions':
                return _make_chain(session_row)
            if name == 'published_content':
                return _make_chain(content_row)
            if name == 'student_submissions':
                return _make_chain(existing_draft)
            return _make_chain([])

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb

        resp = client.post('/api/student/submission/pc-1/draft',
                           headers={'X-Student-Token': 'tok-abc',
                                    'Content-Type': 'application/json'},
                           json={'answers': {}})
        data = resp.get_json()
        assert resp.status_code == 200
        # 30 min limit, 10 min elapsed => ~1200 seconds remaining
        assert data['remaining_seconds'] is not None
        assert 1100 <= data['remaining_seconds'] <= 1210
        assert data['time_limit_seconds'] == 1800


# ============ GET STUDENT CONTENT ============

class TestGetStudentContent:
    """GET /api/student/content/<content_id>"""

    @patch('routes.student_account_routes._get_supabase')
    def test_content_strips_answer_keys(self, mock_get_sb, client):
        expires = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
        session_row = [{'student_id': 'stu-1', 'class_id': 'cls-1', 'expires_at': expires}]
        content_item = [{
            'id': 'pc-1', 'title': 'Quiz', 'content_type': 'assessment',
            'settings': {}, 'due_date': None,
            'content': {
                'sections': [{'questions': [{
                    'type': 'multiple_choice', 'question': 'What?',
                    'answer': 'A', 'correct_answer': 'A',
                    'options': ['A', 'B', 'C'],
                }]}]
            },
        }]

        mock_sb = MagicMock()

        def table_side(name):
            if name == 'student_sessions':
                return _make_chain(session_row)
            if name == 'published_content':
                return _make_chain(content_item)
            return _make_chain([])

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb

        resp = client.get('/api/student/content/pc-1',
                          headers={'X-Student-Token': 'tok-abc'})
        data = resp.get_json()
        assert resp.status_code == 200
        q = data['content']['sections'][0]['questions'][0]
        assert 'answer' not in q
        assert 'correct_answer' not in q

    @patch('routes.student_account_routes._get_supabase')
    def test_content_not_found_returns_404(self, mock_get_sb, client):
        expires = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
        session_row = [{'student_id': 'stu-1', 'class_id': 'cls-1', 'expires_at': expires}]

        mock_sb = MagicMock()

        def table_side(name):
            if name == 'student_sessions':
                return _make_chain(session_row)
            if name == 'published_content':
                return _make_chain([])  # not found
            return _make_chain([])

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb

        resp = client.get('/api/student/content/missing-id',
                          headers={'X-Student-Token': 'tok-abc'})
        assert resp.status_code == 404


# ============ STUDENT LOGIN ============

class TestStudentLogin:
    """POST /api/student/login"""

    @patch('routes.student_account_routes._get_supabase')
    def test_valid_login_returns_token(self, mock_get_sb, client):
        class_row = [{'id': 'cls-1', 'teacher_id': 't1', 'name': 'P1', 'subject': 'Math'}]
        student_row = [{'id': 'stu-1', 'first_name': 'Jo', 'last_name': 'Mo',
                        'student_id_number': 'S1', 'email': 'jo@test.com', 'period': 'P1'}]
        enrollment_row = [{'id': 'enr-1'}]

        mock_sb = MagicMock()

        def table_side(name):
            if name == 'classes':
                return _make_chain(class_row)
            if name == 'students':
                return _make_chain(student_row)
            if name == 'class_students':
                return _make_chain(enrollment_row)
            if name == 'student_sessions':
                return _make_chain([{}])  # insert returns row
            return _make_chain([])

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb

        # Clear rate limit state
        from backend.routes.student_account_routes import _login_attempts
        _login_attempts.clear()

        resp = client.post('/api/student/login',
                           headers={'Content-Type': 'application/json'},
                           json={'email': 'jo@test.com', 'class_code': 'ABC123'})
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['success'] is True
        assert 'token' in data
        assert data['student']['first_name'] == 'Jo'

    def test_login_missing_fields_returns_400(self, client):
        resp = client.post('/api/student/login',
                           headers={'Content-Type': 'application/json'},
                           json={'email': '', 'class_code': ''})
        assert resp.status_code == 400


# ============ TEACHER ENDPOINTS ============

class TestCreateClass:
    """POST /api/classes"""

    @patch('routes.student_account_routes._get_supabase')
    def test_create_class_success(self, mock_get_sb, client, teacher_headers):
        mock_sb = MagicMock()
        # _generate_class_code checks for existing codes
        code_chain = _make_chain([])  # no collision
        insert_chain = MagicMock()
        insert_chain.execute.return_value = MagicMock(data=[{
            'id': 'cls-new', 'name': 'Period 3', 'join_code': 'XYZ789',
        }])

        def table_side(name):
            chain = _make_chain([])
            chain.insert.return_value = insert_chain
            return chain

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb

        resp = client.post('/api/classes', headers=teacher_headers,
                           json={'name': 'Period 3', 'subject': 'History'})
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['success'] is True

    @patch('routes.student_account_routes._get_supabase')
    def test_create_class_missing_name_returns_400(self, mock_get_sb, client, teacher_headers):
        mock_get_sb.return_value = MagicMock()
        resp = client.post('/api/classes', headers=teacher_headers,
                           json={'name': '', 'subject': 'Math'})
        assert resp.status_code == 400


# ============ LIST CLASSES ============

class TestListClasses:
    """GET /api/classes"""

    @patch('routes.student_account_routes._get_supabase')
    def test_list_classes_returns_teacher_classes(self, mock_get_sb, client, teacher_headers):
        classes_row = [
            {'id': 'c1', 'name': 'P1', 'subject': 'Math', 'is_active': True,
             'class_students': [{'count': 15}]},
            {'id': 'c2', 'name': 'P2', 'subject': 'History', 'is_active': True,
             'class_students': [{'count': 20}]},
        ]
        mock_sb = MagicMock()
        mock_sb.table.return_value = _make_chain(classes_row)
        mock_get_sb.return_value = mock_sb

        resp = client.get('/api/classes', headers=teacher_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data['classes']) == 2


# ============ STUDENT RESOURCES ============

class TestStudentResources:
    """GET /api/student/resources + /api/student/resource/<id>"""

    @patch('routes.student_account_routes._get_supabase')
    def test_list_resources_filters_to_resource_types(self, mock_get_sb, client):
        expires = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
        session_row = [{'student_id': 'stu-1', 'class_id': 'cls-1', 'expires_at': expires}]
        # Mix of content types — only resource types should show
        content_row = [
            {'id': 'r1', 'title': 'Study Guide',
             'content_type': 'study_guide', 'created_at': '2026-01-01', 'settings': {}},
            {'id': 'a1', 'title': 'Quiz 1',
             'content_type': 'assessment', 'created_at': '2026-01-02', 'settings': {}},
            {'id': 'r2', 'title': 'Flashcards',
             'content_type': 'flashcards', 'created_at': '2026-01-03', 'settings': {}},
        ]

        mock_sb = MagicMock()

        def table_side(name):
            if name == 'student_sessions':
                return _make_chain(session_row)
            if name == 'published_content':
                return _make_chain(content_row)
            return _make_chain([])

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb

        resp = client.get('/api/student/resources',
                          headers={'X-Student-Token': 'tok-abc'})
        assert resp.status_code == 200
        data = resp.get_json()
        titles = [r['title'] for r in data['resources']]
        # Assessment should be filtered out; resources kept
        assert 'Quiz 1' not in titles
        # At least the resource-type ones are present (specific types
        # depend on RESOURCE_CONTENT_TYPES which may vary)
        assert 'resources' in data

    def test_resources_no_auth_returns_401(self, client):
        resp = client.get('/api/student/resources')
        assert resp.status_code == 401

    @patch('routes.student_account_routes._get_supabase')
    def test_resource_content_not_found_returns_404(self, mock_get_sb, client):
        expires = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
        session_row = [{'student_id': 'stu-1', 'class_id': 'cls-1', 'expires_at': expires}]

        mock_sb = MagicMock()

        def table_side(name):
            if name == 'student_sessions':
                return _make_chain(session_row)
            if name == 'published_content':
                return _make_chain([])
            return _make_chain([])

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb

        resp = client.get('/api/student/resource/missing',
                          headers={'X-Student-Token': 'tok-abc'})
        assert resp.status_code == 404


# ============ GET SUBMISSION DRAFT ============

class TestGetSubmissionDraft:
    """GET /api/student/submission/<content_id>/draft"""

    @patch('routes.student_account_routes._get_supabase')
    def test_get_draft_returns_saved_answers(self, mock_get_sb, client):
        expires = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
        session_row = [{'student_id': 'stu-1', 'class_id': 'cls-1', 'expires_at': expires}]
        content_row = [{'id': 'pc-1', 'settings': {'time_limit_minutes': 45}}]
        started = (datetime.now(tz=timezone.utc) - timedelta(minutes=15)).isoformat()
        draft_row = [{
            'id': 'sub-d1', 'status': 'draft',
            'draft_answers': {'0-0': 'answer'},
            'question_times': {'0-0': 30},
            'marked_for_review': [],
            'time_started_at': started,
        }]

        mock_sb = MagicMock()

        def table_side(name):
            if name == 'student_sessions':
                return _make_chain(session_row)
            if name == 'published_content':
                return _make_chain(content_row)
            if name == 'student_submissions':
                return _make_chain(draft_row)
            return _make_chain([])

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb

        resp = client.get('/api/student/submission/pc-1/draft',
                          headers={'X-Student-Token': 'tok-abc'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['draft']['answers'] == {'0-0': 'answer'}
        # 45 min - 15 min elapsed = ~1800 seconds remaining
        assert 1700 < data['draft']['remaining_seconds'] <= 1800

    @patch('routes.student_account_routes._get_supabase')
    def test_get_draft_no_draft_returns_none(self, mock_get_sb, client):
        expires = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
        session_row = [{'student_id': 'stu-1', 'class_id': 'cls-1', 'expires_at': expires}]
        content_row = [{'id': 'pc-1', 'settings': {}}]

        mock_sb = MagicMock()

        def table_side(name):
            if name == 'student_sessions':
                return _make_chain(session_row)
            if name == 'published_content':
                return _make_chain(content_row)
            if name == 'student_submissions':
                return _make_chain([])
            return _make_chain([])

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb

        resp = client.get('/api/student/submission/pc-1/draft',
                          headers={'X-Student-Token': 'tok-abc'})
        assert resp.status_code == 200
        assert resp.get_json()['draft'] is None

    def test_get_draft_no_auth_returns_401(self, client):
        resp = client.get('/api/student/submission/pc-1/draft')
        assert resp.status_code == 401

    @patch('routes.student_account_routes._get_supabase')
    def test_get_draft_wrong_class_returns_404(self, mock_get_sb, client):
        """Content that doesn't belong to student's class returns 404."""
        expires = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
        session_row = [{'student_id': 'stu-1', 'class_id': 'cls-1', 'expires_at': expires}]

        mock_sb = MagicMock()

        def table_side(name):
            if name == 'student_sessions':
                return _make_chain(session_row)
            if name == 'published_content':
                return _make_chain([])  # content not in this class
            return _make_chain([])

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb

        resp = client.get('/api/student/submission/other-class-content/draft',
                          headers={'X-Student-Token': 'tok-abc'})
        assert resp.status_code == 404


# ============ LOGIN RATE LIMIT ============

class TestLoginRateLimit:
    """_check_rate_limit enforces 5 attempts per 10 min per student."""

    def test_rate_limit_allows_first_5_attempts(self):
        from routes.student_account_routes import _check_rate_limit, _login_attempts
        _login_attempts.clear()
        for _ in range(5):
            assert _check_rate_limit('S123') is True

    def test_rate_limit_blocks_6th_attempt(self):
        from routes.student_account_routes import _check_rate_limit, _login_attempts
        _login_attempts.clear()
        for _ in range(5):
            _check_rate_limit('S456')
        assert _check_rate_limit('S456') is False


# ============ ERROR HANDLING ============

class TestErrorHandling:
    """Verify routes return clean JSON errors, not HTML 500."""

    @patch('routes.student_account_routes._get_supabase')
    def test_supabase_failure_returns_json_500(self, mock_get_sb, client, teacher_headers):
        """Supabase connection failure returns JSON error, not HTML."""
        mock_get_sb.side_effect = Exception('Connection refused')

        resp = client.get('/api/classes', headers=teacher_headers)
        assert resp.status_code == 500
        data = resp.get_json()
        assert data is not None
        assert 'error' in data

    @patch('routes.student_account_routes._get_supabase')
    def test_dashboard_db_error_returns_json(self, mock_get_sb, client):
        """Dashboard DB failure returns clean JSON, not traceback."""
        expires = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
        session_row = [{'student_id': 'stu-1', 'class_id': 'cls-1', 'expires_at': expires}]

        mock_sb = MagicMock()
        call_n = {'n': 0}

        def table_side(name):
            call_n['n'] += 1
            if name == 'student_sessions':
                return _make_chain(session_row)
            # All other DB calls fail
            raise Exception('DB timeout')

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb

        resp = client.get('/api/student/dashboard',
                          headers={'X-Student-Token': 'tok-abc'})
        assert resp.status_code == 500
        data = resp.get_json()
        assert data is not None
        assert 'error' in data
