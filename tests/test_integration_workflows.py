"""Integration tests — real HTTP requests through Flask endpoints.

Simulates teacher and student workflows via Flask test client.
Supabase is mocked to avoid external dependencies.
"""
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

# Ensure backend imports work
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
    """Headers that simulate an authenticated teacher."""
    return {'X-Test-Teacher-Id': 'test-teacher-001', 'Content-Type': 'application/json'}


def _make_chain(execute_data=None):
    """Create a chainable Supabase query builder mock.

    Every query method returns the same chain so calls like
    ``db.table('x').select('*').eq('a', 'b').execute()`` work.
    """
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
    chain.execute.return_value = MagicMock(data=execute_data if execute_data is not None else [])
    return chain


def _simple_sb(default_data=None):
    """Create a mock Supabase client where every table returns the same chain.

    Use this when the endpoint only hits one table and you want simple setup.
    """
    mock_sb = MagicMock()
    chain = _make_chain(default_data)
    mock_sb.table.return_value = chain
    return mock_sb, chain


# ============ TEACHER WORKFLOW ============

class TestPublishAssessment:
    """Test POST /api/publish-assessment — teacher publishes via join code."""

    @patch('routes.student_portal_routes.get_supabase')
    def test_publish_returns_join_code(self, mock_get_sb, client, teacher_headers):
        mock_sb = MagicMock()

        def table_side_effect(name):
            chain = _make_chain()
            # insert/upsert call for publishing returns a row
            insert_chain = MagicMock()
            insert_chain.execute.return_value = MagicMock(data=[{
                'id': 'pub-001',
                'join_code': 'ABC123',
            }])
            chain.insert.return_value = insert_chain
            chain.upsert.return_value = insert_chain
            return chain

        mock_sb.table.side_effect = table_side_effect
        mock_get_sb.return_value = mock_sb

        response = client.post('/api/publish-assessment', headers=teacher_headers, json={
            'assessment': {
                'title': 'Test Quiz',
                'sections': [{'questions': [{'type': 'multiple_choice', 'question': 'Q1', 'answer': 'A', 'points': 5}]}],
            },
            'settings': {
                'teacher_name': 'Test Teacher',
                'content_type': 'assessment',
                'show_score_immediately': False,
                'show_correct_answers': False,
            }
        })

        data = json.loads(response.data)
        assert response.status_code == 200
        assert data.get('success') is True
        assert 'join_code' in data

    @patch('routes.student_portal_routes.get_supabase')
    def test_publish_requires_assessment(self, mock_get_sb, client, teacher_headers):
        mock_sb, _ = _simple_sb()
        mock_get_sb.return_value = mock_sb

        response = client.post('/api/publish-assessment', headers=teacher_headers, json={
            'settings': {}
        })

        data = json.loads(response.data)
        assert response.status_code == 400
        assert 'error' in data


class TestTeacherAssessmentList:
    """Test GET /api/teacher/assessments — list teacher's published assessments."""

    @patch('routes.student_portal_routes.get_supabase')
    def test_returns_assessments_for_teacher(self, mock_get_sb, client, teacher_headers):
        mock_sb, chain = _simple_sb([
            {'id': 'a1', 'join_code': 'XYZ789', 'title': 'Quiz 1', 'created_at': '2026-03-20T10:00:00',
             'submission_count': 5, 'is_active': True, 'settings': {'period': 'P1'}},
        ])
        mock_get_sb.return_value = mock_sb

        response = client.get('/api/teacher/assessments', headers=teacher_headers)
        data = json.loads(response.data)
        assert response.status_code == 200
        assert len(data['assessments']) == 1
        assert data['assessments'][0]['join_code'] == 'XYZ789'


# ============ STUDENT JOIN-CODE WORKFLOW ============

class TestStudentJoinCode:
    """Test the join-code portal flow: join -> submit -> results."""

    @patch('routes.student_portal_routes.get_supabase')
    def test_join_returns_sanitized_assessment(self, mock_get_sb, client):
        """GET /api/student/join/<code> should return assessment WITHOUT answer keys."""
        mock_sb, chain = _simple_sb([{
            'id': 'pub-001',
            'is_active': True,
            'assessment': {
                'title': 'Test Quiz',
                'sections': [{
                    'name': 'Part A',
                    'questions': [{
                        'number': 1,
                        'question': 'What is 2+2?',
                        'type': 'multiple_choice',
                        'options': ['3', '4', '5'],
                        'answer': 'B',  # This should be STRIPPED
                        'points': 5,
                    }]
                }]
            },
            'settings': {
                'show_score_immediately': True,
                'show_correct_answers': True,
                'student_accommodations': {},
                'time_limit_minutes': 30,
                'content_type': 'assessment',
            },
            'teacher_name': 'Test Teacher',
        }])
        mock_get_sb.return_value = mock_sb

        response = client.get('/api/student/join/ABC123')
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data['title'] == 'Test Quiz'
        # Answer keys should be stripped
        questions = data['sections'][0]['questions']
        assert 'answer' not in questions[0]
        assert questions[0]['question'] == 'What is 2+2?'
        assert questions[0]['options'] is not None

    @patch('routes.student_portal_routes.get_supabase')
    def test_join_inactive_assessment_returns_403(self, mock_get_sb, client):
        mock_sb, _ = _simple_sb([{
            'id': 'pub-002',
            'is_active': False,
            'assessment': {'title': 'Closed Quiz'},
            'settings': {},
        }])
        mock_get_sb.return_value = mock_sb

        response = client.get('/api/student/join/CLOSED1')
        assert response.status_code == 403

    @patch('routes.student_portal_routes.get_supabase')
    def test_join_nonexistent_code_returns_404(self, mock_get_sb, client):
        mock_sb, _ = _simple_sb([])
        mock_get_sb.return_value = mock_sb

        response = client.get('/api/student/join/ZZZZZ1')
        assert response.status_code == 404

    @patch('backend.services.portal_grading.has_written_questions', return_value=False)
    @patch('routes.student_portal_routes.grade_student_submission')
    @patch('routes.student_portal_routes.get_supabase')
    def test_submit_mc_only_returns_score(self, mock_get_sb, mock_grade, mock_has_written, client):
        """POST /api/student/submit/<code> with MC-only should return instant score."""
        mock_grade.return_value = {
            'score': 10,
            'total_points': 10,
            'percentage': 100.0,
            'questions': [{'is_correct': True, 'type': 'multiple_choice', 'points_earned': 10}],
            'feedback_summary': 'Perfect score!',
        }

        assessment_data = {
            'id': 'pub-003',
            'is_active': True,
            'assessment': {
                'title': 'MC Quiz',
                'sections': [{
                    'questions': [{
                        'type': 'multiple_choice',
                        'question': 'Q1',
                        'answer': 'B',
                        'options': ['A', 'B', 'C'],
                        'points': 10,
                    }]
                }]
            },
            'settings': {
                'show_score_immediately': True,
                'show_correct_answers': True,
                'allow_multiple_attempts': False,
            },
        }

        mock_sb = MagicMock()

        def table_side_effect(name):
            chain = _make_chain()
            if name == 'published_assessments':
                chain.execute.return_value = MagicMock(data=[assessment_data])
            elif name == 'submissions':
                # duplicate check returns empty
                chain.execute.return_value = MagicMock(data=[])
                # insert/upsert returns a row with id
                insert_chain = MagicMock()
                insert_chain.execute.return_value = MagicMock(data=[{'id': 'sub-001'}])
                chain.insert.return_value = insert_chain
                chain.upsert.return_value = insert_chain
            return chain

        mock_sb.table.side_effect = table_side_effect
        mock_get_sb.return_value = mock_sb

        response = client.post('/api/student/submit/TESTMC', json={
            'student_name': 'Test Student',
            'answers': {'0-0': 'B'},
            'time_taken_seconds': 120,
        })

        data = json.loads(response.data)
        assert response.status_code == 200
        assert data.get('success') is True
        assert data.get('score') == 10


class TestSubmitAvailabilityWindow:
    """Test that submissions are blocked outside availability windows."""

    @patch('routes.student_portal_routes.get_supabase')
    def test_submit_before_available_returns_403(self, mock_get_sb, client):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        mock_sb, _ = _simple_sb([{
            'id': 'pub-004',
            'is_active': True,
            'assessment': {'title': 'Future Quiz', 'sections': []},
            'settings': {
                'available_from': future,
                'allow_multiple_attempts': True,
            },
        }])
        mock_get_sb.return_value = mock_sb

        response = client.post('/api/student/submit/FUTURE', json={
            'student_name': 'Student',
            'answers': {},
        })

        data = json.loads(response.data)
        assert response.status_code == 403
        assert 'not yet available' in data['error']

    @patch('routes.student_portal_routes.get_supabase')
    def test_submit_after_window_returns_403(self, mock_get_sb, client):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        mock_sb, _ = _simple_sb([{
            'id': 'pub-005',
            'is_active': True,
            'assessment': {'title': 'Closed Quiz', 'sections': []},
            'settings': {
                'available_until': past,
                'allow_multiple_attempts': True,
            },
        }])
        mock_get_sb.return_value = mock_sb

        response = client.post('/api/student/submit/PAST01', json={
            'student_name': 'Student',
            'answers': {},
        })

        data = json.loads(response.data)
        assert response.status_code == 403
        assert 'no longer accepting' in data['error']


# ============ CLEVER HEALTH CHECK ============

class TestCleverHealth:
    """Test GET /api/clever/health endpoint."""

    def test_health_returns_status(self, client):
        response = client.get('/api/clever/health')
        data = json.loads(response.data)
        # Endpoint returns 200 if configured, 503 if not; either is valid in test
        assert response.status_code in (200, 503)
        assert 'configured' in data
        assert 'supabase_available' in data
