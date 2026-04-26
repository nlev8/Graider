"""Tests for the submission detail endpoint.

Spec: docs/superpowers/specs/2026-04-25-phase3a-gradebook-design.md
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture
def app():
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


@pytest.fixture
def client_no_auth():
    from flask import Flask
    from backend.routes.student_portal_routes import student_portal_bp
    isolated = Flask(__name__)
    isolated.config['TESTING'] = True
    isolated.config['SECRET_KEY'] = 'test'
    isolated.register_blueprint(student_portal_bp)
    return isolated.test_client()


def _make_chain(execute_data=None):
    """Chainable Supabase mock that ACTUALLY APPLIES `.eq()` filters when
    `.execute()` is called. Critical for the submission-detail tests
    because the route looks up `student_submissions` twice — once by id,
    then again for sibling attempts (same student × same content). Without
    filter-aware mocking, both queries get the same unfiltered data.
    """
    data = list(execute_data) if execute_data else []
    chain = MagicMock()
    chain.select.return_value = chain
    chain.in_.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    filters = []

    def _eq(field, value):
        filters.append(('eq', field, value))
        return chain
    chain.eq.side_effect = _eq

    def _execute():
        result = data
        for op, field, value in filters:
            if op == 'eq':
                result = [r for r in result if r.get(field) == value]
        filters.clear()
        return MagicMock(data=result)
    chain.execute.side_effect = _execute
    return chain


def _multi_table_sb(table_map):
    mock_sb = MagicMock()
    def table_side_effect(name):
        val = table_map.get(name)
        if val is None:
            return _make_chain([])
        return _make_chain(val)
    mock_sb.table.side_effect = table_side_effect
    return mock_sb


class TestSubmissionDetailAuthz:
    """Auth + ownership chain checks."""

    def test_unauthenticated_returns_401(self, client_no_auth):
        resp = client_no_auth.get('/api/teacher/submission/sub-1/detail')
        assert resp.status_code == 401

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_submission_not_found_returns_404(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/submission/missing-id/detail', headers=teacher_headers)
        assert resp.status_code == 404

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_submission_content_deleted_returns_404(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'student_submissions': [
                {'id': 'sub-1', 'student_id': 'stu-1', 'content_id': 'ct-deleted',
                 'attempt_number': 1, 'percentage': 80, 'submitted_at': '2026-04-10T10:00:00Z',
                 'results': {'questions': [], 'score': 8, 'total_points': 10}, 'status': 'graded'},
            ],
            'published_content': [],  # content row missing
        })
        resp = client.get('/api/teacher/submission/sub-1/detail', headers=teacher_headers)
        assert resp.status_code == 404

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_other_teacher_submission_returns_403(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'student_submissions': [
                {'id': 'sub-1', 'student_id': 'stu-1', 'content_id': 'ct-1',
                 'attempt_number': 1, 'percentage': 80, 'submitted_at': '2026-04-10T10:00:00Z',
                 'results': {'questions': [], 'score': 8, 'total_points': 10}, 'status': 'graded'},
            ],
            'published_content': [
                {'id': 'ct-1', 'title': 'Q', 'class_id': 'cls-other'},
            ],
            'classes': [{'id': 'cls-other', 'teacher_id': 'OTHER-teacher'}],
        })
        resp = client.get('/api/teacher/submission/sub-1/detail', headers=teacher_headers)
        assert resp.status_code == 403
        body = resp.get_json()
        assert body.get('type') == 'https://graider.live/errors/forbidden'


class TestSubmissionDetailHappyPath:
    """Per-question normalization + sibling attempts."""

    def _setup_with_submission(self, mock_sb_fn, results):
        mock_sb_fn.return_value = _multi_table_sb({
            'student_submissions': [
                {'id': 'sub-1', 'student_id': 'stu-1', 'content_id': 'ct-1',
                 'attempt_number': 2, 'percentage': 80, 'submitted_at': '2026-04-12T10:00:00Z',
                 'results': results, 'status': 'graded',
                 'score': results.get('score'), 'total_points': results.get('total_points')},
                # Sibling attempt 1
                {'id': 'sub-0', 'student_id': 'stu-1', 'content_id': 'ct-1',
                 'attempt_number': 1, 'percentage': 60, 'submitted_at': '2026-04-10T10:00:00Z',
                 'results': {}, 'status': 'graded'},
            ],
            'published_content': [
                {'id': 'ct-1', 'title': 'Quiz 1', 'class_id': 'cls-1'},
            ],
            'classes': [{'id': 'cls-1', 'teacher_id': 'test-teacher-001'}],
            'students': [{'id': 'stu-1', 'first_name': 'Alice', 'last_name': 'Anderson'}],
        })

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_questions_normalized_with_fallback_keys(self, mock_sb_fn, client, teacher_headers):
        # Mix of grader-shapes: one entry uses `question`, one uses `question_text`,
        # one uses `feedback`, one uses `reasoning`.
        results = {
            "score": 8, "total_points": 10,
            "questions": [
                {"question": "What is 2+2?", "type": "multiple_choice", "answer": "4",
                 "correct_answer": "4", "is_correct": True, "feedback": "Correct.",
                 "points_earned": 5, "points_possible": 5},
                {"question_text": "Discuss photosynthesis.", "question_type": "written",
                 "student_answer": "Plants convert light to energy.", "correct_answer": None,
                 "is_correct": None, "reasoning": "Mostly correct but lacks chlorophyll mention.",
                 "points": 5, "score": 3},
            ],
        }
        self._setup_with_submission(mock_sb_fn, results)
        resp = client.get('/api/teacher/submission/sub-1/detail', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # Top-level
        assert body['submission_id'] == 'sub-1'
        assert body['student_name'] == 'Alice Anderson'
        assert body['content_title'] == 'Quiz 1'
        assert body['attempt_number'] == 2
        assert body['total_attempts'] == 2  # sub-0 + sub-1
        assert body['points_earned'] == 8
        assert body['points_possible'] == 10
        # Per-question normalization
        qs = body['questions']
        assert len(qs) == 2
        assert qs[0]['question_text'] == 'What is 2+2?'
        assert qs[0]['question_type'] == 'multiple_choice'
        assert qs[0]['student_answer'] == '4'
        assert qs[0]['ai_feedback'] == 'Correct.'
        assert qs[0]['points_earned'] == 5
        assert qs[0]['points_possible'] == 5
        # Second question uses fallback keys
        assert qs[1]['question_text'] == 'Discuss photosynthesis.'
        assert qs[1]['question_type'] == 'written'
        assert qs[1]['student_answer'] == 'Plants convert light to energy.'
        assert qs[1]['ai_feedback'] == 'Mostly correct but lacks chlorophyll mention.'
        assert qs[1]['points_earned'] == 3  # falls back to `score`
        assert qs[1]['points_possible'] == 5  # falls back to `points`
        assert qs[1]['correct_answer'] is None
        assert qs[1]['is_correct'] is None

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_zero_score_not_falsy_treated(self, mock_sb_fn, client, teacher_headers):
        """Legitimate 0 must not fall through to row.score fallback."""
        results = {
            "score": 0, "total_points": 10,
            "questions": [{"question": "Q", "answer": "wrong",
                            "points_earned": 0, "points_possible": 5}],
        }
        self._setup_with_submission(mock_sb_fn, results)
        resp = client.get('/api/teacher/submission/sub-1/detail', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['points_earned'] == 0
        assert body['questions'][0]['points_earned'] == 0

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_missing_questions_returns_empty_array_with_200(self, mock_sb_fn, client, teacher_headers):
        results = {"score": 8, "total_points": 10}  # no `questions` key
        self._setup_with_submission(mock_sb_fn, results)
        resp = client.get('/api/teacher/submission/sub-1/detail', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['questions'] == []

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_malformed_results_questions_returns_empty_array_with_200(self, mock_sb_fn, client, teacher_headers):
        """results.questions is non-list (e.g., string). Route returns 200
        with questions: [] and logs a WARNING — does NOT 500."""
        results = {"score": 8, "total_points": 10, "questions": "broken-not-a-list"}
        self._setup_with_submission(mock_sb_fn, results)
        resp = client.get('/api/teacher/submission/sub-1/detail', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['questions'] == []

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_no_sibling_attempts_returns_only_self(self, mock_sb_fn, client, teacher_headers):
        """Single-attempt case: sibling_attempts should contain only the
        submission itself. total_attempts == 1."""
        # Override _setup_with_submission's two-sibling setup with a single one
        results = {"score": 8, "total_points": 10, "questions": []}
        mock_sb_fn.return_value = _multi_table_sb({
            'student_submissions': [
                {'id': 'sub-only', 'student_id': 'stu-1', 'content_id': 'ct-1',
                 'attempt_number': 1, 'percentage': 80, 'submitted_at': '2026-04-12T10:00:00Z',
                 'results': results, 'status': 'graded',
                 'score': 8, 'total_points': 10},
            ],
            'published_content': [{'id': 'ct-1', 'title': 'Quiz 1', 'class_id': 'cls-1'}],
            'classes': [{'id': 'cls-1', 'teacher_id': 'test-teacher-001'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
        })
        resp = client.get('/api/teacher/submission/sub-only/detail', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['total_attempts'] == 1
        assert len(body['sibling_attempts']) == 1
        assert body['sibling_attempts'][0]['submission_id'] == 'sub-only'
