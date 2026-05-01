"""Tests for the gradebook endpoint and the _coalesce helper.

Spec: docs/superpowers/specs/2026-04-25-phase3a-gradebook-design.md
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


# ============ _coalesce helper unit tests ============

class TestCoalesce:
    """_coalesce: first-non-None semantics (NOT `or`-truthiness)."""

    def test_returns_first_non_none(self):
        from backend.routes.student_portal_routes import _coalesce
        assert _coalesce(None, "fallback", "later") == "fallback"

    def test_returns_default_when_all_none(self):
        from backend.routes.student_portal_routes import _coalesce
        assert _coalesce(None, None, default=42) == 42

    def test_zero_is_kept_not_treated_as_falsy(self):
        """The whole reason this helper exists: legitimate 0 must not fall through."""
        from backend.routes.student_portal_routes import _coalesce
        assert _coalesce(0, 999, default=-1) == 0

    def test_empty_string_is_kept_not_treated_as_falsy(self):
        from backend.routes.student_portal_routes import _coalesce
        assert _coalesce("", "fallback", default="default") == ""


# ============ Test fixtures ============

@pytest.fixture
def app():
    """Flask app in test mode."""
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
    """Minimal Flask app WITHOUT the dev-mode before_request hook so
    require_teacher can return 401. Mirrors tests/test_sso_contracts.py."""
    from flask import Flask
    from backend.routes.student_portal_routes import student_portal_bp
    isolated = Flask(__name__)
    isolated.config['TESTING'] = True
    isolated.config['SECRET_KEY'] = 'test'
    isolated.register_blueprint(student_portal_bp)
    return isolated.test_client()


def _make_chain(execute_data=None):
    """Chainable Supabase mock that ACTUALLY APPLIES `.eq()` filters when
    `.execute()` is called. This makes a single mock-table answer multiple
    queries with different filters correctly (e.g., looking up one
    submission by id, then later querying for sibling attempts of the
    same student/content). Without this, the same data set is returned
    regardless of filter, which masks query bugs.
    """
    data = list(execute_data) if execute_data else []
    chain = MagicMock()
    chain.select.return_value = chain
    chain.neq.return_value = chain
    chain.in_.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.range.return_value = chain
    filters = []  # list of ('eq', field, value)

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
    """Mock supabase that returns a FRESH `_make_chain` per `db.table(name)`
    call (so each query gets its own filter list). Same-table queries are
    distinguished by their `.eq()` filters."""
    mock_sb = MagicMock()
    def table_side_effect(name):
        val = table_map.get(name)
        if val is None:
            return _make_chain([])
        return _make_chain(val)
    mock_sb.table.side_effect = table_side_effect
    return mock_sb


# ============ Authz tests ============

class TestGradebookAuthz:
    """Auth + class-ownership checks."""

    def test_unauthenticated_returns_401(self, client_no_auth):
        resp = client_no_auth.get('/api/teacher/class/cls-1/gradebook')
        assert resp.status_code == 401

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_other_teacher_class_returns_403(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'OTHER-teacher'}],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        assert resp.status_code == 403
        body = resp.get_json()
        assert body.get('type') == 'https://graider.live/errors/forbidden'
        assert body.get('status') == 403
        assert 'error' in body


class TestGradebookHappyPath:
    """Happy-path data assembly: students × assessments × grades."""

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_returns_full_grid(self, mock_sb_fn, client, teacher_headers):
        # 2 students × 2 assessments. stu-1 submitted both; stu-2 only the first.
        subs = [
            {"id": "sub-1-A", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 1, "submitted_at": "2026-04-10T10:00:00Z",
             "percentage": 80, "results": {"standards_mastery": {}, "score": 8, "total_points": 10},
             "status": "graded"},
            {"id": "sub-1-B", "student_id": "stu-1", "content_id": "ct-2",
             "attempt_number": 1, "submitted_at": "2026-04-15T10:00:00Z",
             "percentage": 70, "results": {"standards_mastery": {}, "score": 14, "total_points": 20},
             "status": "graded"},
            {"id": "sub-2-A", "student_id": "stu-2", "content_id": "ct-1",
             "attempt_number": 1, "submitted_at": "2026-04-11T10:00:00Z",
             "percentage": 60, "results": {"standards_mastery": {}, "score": 6, "total_points": 10},
             "status": "graded"},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'Period 3', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'class_id': 'cls-1', 'student_id': 'stu-1'},
                                {'class_id': 'cls-1', 'student_id': 'stu-2'}],
            'students': [
                {'id': 'stu-1', 'first_name': 'Alice', 'last_name': 'Anderson'},
                {'id': 'stu-2', 'first_name': 'Bob', 'last_name': 'Brown'},
            ],
            'published_content': [
                {'id': 'ct-1', 'class_id': 'cls-1', 'title': 'Quiz 1', 'content_type': 'assessment',
                 'publish_date': '2026-04-01T00:00:00Z', 'due_date': None},
                {'id': 'ct-2', 'class_id': 'cls-1', 'title': 'Quiz 2', 'content_type': 'assessment',
                 'publish_date': '2026-04-08T00:00:00Z', 'due_date': None},
            ],
            'student_submissions': subs,
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # Students sorted alphabetically
        assert [s['student_id'] for s in body['students']] == ['stu-1', 'stu-2']
        # Assessments sorted by publish_date ASC
        assert [a['content_id'] for a in body['assessments']] == ['ct-1', 'ct-2']
        # Grades populated for the 3 (student, content) pairs
        assert body['grades']['stu-1']['ct-1']['percentage'] == 80
        assert body['grades']['stu-1']['ct-2']['percentage'] == 70
        assert body['grades']['stu-2']['ct-1']['percentage'] == 60
        # stu-2 has no submission for ct-2 → absent from map
        assert 'ct-2' not in body['grades'].get('stu-2', {})
        # total_attempts = 1 for each (each was a single attempt)
        assert body['grades']['stu-1']['ct-1']['total_attempts'] == 1

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_empty_class_returns_empty_arrays(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [],
            'students': [],
            'published_content': [],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['students'] == []
        assert body['assessments'] == []
        assert body['grades'] == {}

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_class_with_no_submissions_returns_empty_grades(self, mock_sb_fn, client, teacher_headers):
        """Class has students AND assessments, but no submissions yet.
        Distinct from the empty-class case: students/assessments arrays are
        populated; only the grades map is empty."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'class_id': 'cls-1', 'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [{'id': 'ct-1', 'class_id': 'cls-1', 'title': 'Q1',
                                    'content_type': 'assessment',
                                    'publish_date': '2026-04-01T00:00:00Z'}],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body['students']) == 1
        assert len(body['assessments']) == 1
        assert body['grades'] == {}

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_class_with_no_assessments_returns_empty_assessments(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'class_id': 'cls-1', 'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body['students']) == 1
        assert body['assessments'] == []
        assert body['grades'] == {}

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_assessments_sorted_by_publish_date_asc(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'class_id': 'cls-1', 'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [
                # Inserted out-of-order on purpose
                {'id': 'ct-late', 'class_id': 'cls-1', 'title': 'Z-Late', 'content_type': 'assessment',
                 'publish_date': '2026-04-20T00:00:00Z'},
                {'id': 'ct-early', 'class_id': 'cls-1', 'title': 'A-Early', 'content_type': 'assessment',
                 'publish_date': '2026-04-01T00:00:00Z'},
                {'id': 'ct-mid', 'class_id': 'cls-1', 'title': 'M-Mid', 'content_type': 'assessment',
                 'publish_date': '2026-04-10T00:00:00Z'},
            ],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # Sorted ASC by publish_date
        assert [a['content_id'] for a in body['assessments']] == ['ct-early', 'ct-mid', 'ct-late']


class TestGradebookAttemptModes:
    """attempt_mode: latest / best / average / invalid fallback."""

    def _setup_three_attempts(self, mock_sb_fn):
        """One student × one assessment, 3 attempts: 50%, 90%, 70%."""
        subs = [
            {"id": "sub-1", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 1, "submitted_at": "2026-04-11T10:00:00Z", "percentage": 50,
             "results": {"standards_mastery": {}, "score": 5, "total_points": 10},
             "status": "graded"},
            {"id": "sub-2", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 2, "submitted_at": "2026-04-12T10:00:00Z", "percentage": 90,
             "results": {"standards_mastery": {}, "score": 9, "total_points": 10},
             "status": "graded"},
            {"id": "sub-3", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 3, "submitted_at": "2026-04-13T10:00:00Z", "percentage": 70,
             "results": {"standards_mastery": {}, "score": 7, "total_points": 10},
             "status": "graded"},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'class_id': 'cls-1', 'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [{'id': 'ct-1', 'class_id': 'cls-1', 'title': 'Q',
                                    'content_type': 'assessment',
                                    'publish_date': '2026-04-10T00:00:00Z'}],
            'student_submissions': subs,
        })

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_attempt_mode_latest_picks_most_recent_per_pair(self, mock_sb_fn, client, teacher_headers):
        self._setup_three_attempts(mock_sb_fn)
        resp = client.get(
            '/api/teacher/class/cls-1/gradebook?attempt_mode=latest',
            headers=teacher_headers,
        )
        body = resp.get_json()
        cell = body['grades']['stu-1']['ct-1']
        assert cell['submission_id'] == 'sub-3'
        assert cell['percentage'] == 70
        assert cell['attempt_number'] == 3
        assert cell['total_attempts'] == 3

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_attempt_mode_best_picks_highest_per_pair(self, mock_sb_fn, client, teacher_headers):
        self._setup_three_attempts(mock_sb_fn)
        resp = client.get(
            '/api/teacher/class/cls-1/gradebook?attempt_mode=best',
            headers=teacher_headers,
        )
        body = resp.get_json()
        cell = body['grades']['stu-1']['ct-1']
        assert cell['submission_id'] == 'sub-2'  # 90% is best
        assert cell['percentage'] == 90
        assert cell['attempt_number'] == 2

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_attempt_mode_average_aggregates(self, mock_sb_fn, client, teacher_headers):
        self._setup_three_attempts(mock_sb_fn)
        resp = client.get(
            '/api/teacher/class/cls-1/gradebook?attempt_mode=average',
            headers=teacher_headers,
        )
        body = resp.get_json()
        cell = body['grades']['stu-1']['ct-1']
        # Average of 50, 90, 70 = 70.0
        assert cell['percentage'] == 70.0
        # submission_id anchor = LATEST (sub-3) so drilldown opens most recent
        assert cell['submission_id'] == 'sub-3'
        assert cell['attempt_number'] == 3
        assert cell['total_attempts'] == 3

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_invalid_attempt_mode_falls_back_to_latest(self, mock_sb_fn, client, teacher_headers):
        self._setup_three_attempts(mock_sb_fn)
        resp = client.get(
            '/api/teacher/class/cls-1/gradebook?attempt_mode=garbage',
            headers=teacher_headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['attempt_mode'] == 'latest'
        cell = body['grades']['stu-1']['ct-1']
        assert cell['submission_id'] == 'sub-3'


class TestGradebookEdgeCases:
    """Orphan enrollment, missing pairs, malformed mastery."""

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_orphan_enrollment_skipped_silently(self, mock_sb_fn, client, teacher_headers):
        # class_students lists stu-orphan but students table doesn't have that row
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'class_id': 'cls-1', 'student_id': 'stu-1'},
                                {'class_id': 'cls-1', 'student_id': 'stu-orphan'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            # NO row for stu-orphan
            'published_content': [],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # Orphan dropped; only stu-1 appears
        assert [s['student_id'] for s in body['students']] == ['stu-1']

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_missing_pair_absent_from_grades_map(self, mock_sb_fn, client, teacher_headers):
        # stu-1 submits ct-1 only; stu-2 submits nothing.
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'class_id': 'cls-1', 'student_id': 'stu-1'},
                                {'class_id': 'cls-1', 'student_id': 'stu-2'}],
            'students': [
                {'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'},
                {'id': 'stu-2', 'first_name': 'C', 'last_name': 'D'},
            ],
            'published_content': [
                {'id': 'ct-1', 'class_id': 'cls-1', 'title': 'Q1', 'content_type': 'assessment',
                 'publish_date': '2026-04-01T00:00:00Z'},
                {'id': 'ct-2', 'class_id': 'cls-1', 'title': 'Q2', 'content_type': 'assessment',
                 'publish_date': '2026-04-08T00:00:00Z'},
            ],
            'student_submissions': [
                {"id": "sub-1", "student_id": "stu-1", "content_id": "ct-1",
                 "attempt_number": 1, "submitted_at": "2026-04-10T10:00:00Z", "percentage": 80,
                 "results": {"standards_mastery": {}, "score": 8, "total_points": 10},
                 "status": "graded"},
            ],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        body = resp.get_json()
        # stu-1 has ct-1 only; ct-2 absent from inner map
        assert 'ct-1' in body['grades']['stu-1']
        assert 'ct-2' not in body['grades']['stu-1']
        # stu-2 absent from outer map entirely
        assert 'stu-2' not in body['grades']

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_malformed_standards_mastery_does_not_500(self, mock_sb_fn, client, teacher_headers):
        # One submission has a list-shape standards_mastery — would 500
        # without _sanitize_standards_mastery.
        subs = [
            {"id": "sub-bad", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 1, "submitted_at": "2026-04-10T10:00:00Z", "percentage": 60,
             "results": {"standards_mastery": ["malformed"], "score": 6, "total_points": 10},
             "status": "graded"},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'class_id': 'cls-1', 'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [
                {'id': 'ct-1', 'class_id': 'cls-1', 'title': 'Q', 'content_type': 'assessment',
                 'publish_date': '2026-04-01T00:00:00Z'},
            ],
            'student_submissions': subs,
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        # 200 not 500. The sanitize step replaced the list with {} so the rest of
        # the pipeline works. The student's grade is still populated.
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['grades']['stu-1']['ct-1']['percentage'] == 60


# ============ Phase 4.2 #7 — Remediation badge fields ============
# Spec: docs/superpowers/specs/2026-04-29-phase4.2-gradebook-remediation-badge-design.md

class TestGradebookRemediationFields:
    """Response surfaces is_active and target_student_ids per assessment so
    the frontend can render the remediation badge under each column header."""

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_regular_assessment_returns_null_target_and_active_true(
        self, mock_sb_fn, client, teacher_headers,
    ):
        """Class-wide assessment (non-remediation): target_student_ids is None,
        is_active is True. Frontend predicate isRemediation() returns false."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'P3', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'class_id': 'cls-1', 'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [{
                'id': 'ct-1', 'class_id': 'cls-1', 'title': 'Quiz 1',
                'content_type': 'assessment',
                'publish_date': '2026-04-01T00:00:00Z',
                'is_active': True,
                'target_student_ids': None,
            }],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        body = resp.get_json()
        assert len(body['assessments']) == 1
        a = body['assessments'][0]
        assert a['is_active'] is True
        assert a['target_student_ids'] is None

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_active_remediation_returns_target_array_and_active_true(
        self, mock_sb_fn, client, teacher_headers,
    ):
        """Active remediation: target_student_ids is a non-empty array,
        is_active is True. Frontend renders a single 'Remediation' pill."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'P3', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'class_id': 'cls-1', 'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [{
                'id': 'rem-1', 'class_id': 'cls-1', 'title': 'Remediation: MA.6.AR.1.2',
                'content_type': 'assessment',
                'publish_date': '2026-04-15T00:00:00Z',
                'is_active': True,
                'target_student_ids': ['stu-1'],
            }],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        body = resp.get_json()
        a = body['assessments'][0]
        assert a['target_student_ids'] == ['stu-1']
        assert a['is_active'] is True

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_recalled_remediation_returns_active_false(
        self, mock_sb_fn, client, teacher_headers,
    ):
        """Recalled remediation: target_student_ids set, is_active=False.
        Frontend renders BOTH 'Remediation' and 'Recalled' pills."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'P3', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'class_id': 'cls-1', 'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [{
                'id': 'rem-recalled', 'class_id': 'cls-1', 'title': 'Recalled rem',
                'content_type': 'assessment',
                'publish_date': '2026-04-15T00:00:00Z',
                'is_active': False,
                'target_student_ids': ['stu-1'],
            }],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        body = resp.get_json()
        a = body['assessments'][0]
        assert a['target_student_ids'] == ['stu-1']
        assert a['is_active'] is False, (
            "Recalled remediation must surface is_active=False so the "
            "Recalled pill renders alongside the Remediation pill"
        )


# ============ Phase 4.3 Sprint 1: assessment_dok ============
# Spec: docs/superpowers/specs/2026-05-01-phase4.3-sprint1-dok-display-design.md

class TestGradebookAssessmentDok:
    """Per-row assessment_dok is derived from each remediation's
    content.questions via _derive_uniform_dok. Non-remediation rows always
    return None (no DOK badge). The metadata SELECT intentionally omits the
    bulk `content` JSONB; remediation content is fetched in a focused
    second query keyed by id."""

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_remediation_with_uniform_dok_returns_assessment_dok(
        self, mock_sb_fn, client, teacher_headers,
    ):
        """Remediation with all questions at DOK 3 → assessment_dok=3.

        The route does TWO published_content queries: a metadata SELECT
        (id, title, content_type, ..., target_student_ids — no `content`)
        and a focused content fetch for remediation rows. With the shared
        _make_chain mock both queries return the same fixture rows; the
        derivation extracts dok from the `content` field on the same row.
        """
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'P3', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'class_id': 'cls-1', 'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [{
                'id': 'rem-dok3', 'class_id': 'cls-1', 'title': 'Remediation: DOK 3',
                'content_type': 'assessment',
                'publish_date': '2026-04-15T00:00:00Z',
                'is_active': True,
                'target_student_ids': ['stu-1'],
                'content': {'questions': [{'dok': 3}, {'dok': 3}, {'dok': 3}]},
            }],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        body = resp.get_json()
        a = body['assessments'][0]
        assert a['assessment_dok'] == 3

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_remediation_with_mixed_dok_returns_null(
        self, mock_sb_fn, client, teacher_headers,
    ):
        """Remediation with mixed DOK across questions → assessment_dok=null
        (no badge). Frontend predicate _validDok(null) is false."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'P3', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'class_id': 'cls-1', 'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [{
                'id': 'rem-mixed', 'class_id': 'cls-1', 'title': 'Mixed DOK',
                'content_type': 'assessment',
                'publish_date': '2026-04-15T00:00:00Z',
                'is_active': True,
                'target_student_ids': ['stu-1'],
                'content': {'questions': [{'dok': 1}, {'dok': 2}, {'dok': 3}]},
            }],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        body = resp.get_json()
        a = body['assessments'][0]
        assert a['assessment_dok'] is None

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_non_remediation_row_skips_content_fetch_and_returns_null(
        self, mock_sb_fn, client, teacher_headers,
    ):
        """Regular (non-remediation) Planner assessment → assessment_dok=null
        regardless of its content's DOK distribution. The selective fetch
        deliberately skips non-remediation rows for payload-size reasons,
        and per the locked default Sprint 1 only badges remediation rows."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'P3', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'class_id': 'cls-1', 'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [{
                'id': 'planner-1', 'class_id': 'cls-1', 'title': 'Planner Quiz',
                'content_type': 'assessment',
                'publish_date': '2026-04-01T00:00:00Z',
                'is_active': True,
                'target_student_ids': None,  # NOT a remediation
                'content': {'questions': [{'dok': 2}, {'dok': 2}, {'dok': 2}]},
            }],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        body = resp.get_json()
        a = body['assessments'][0]
        assert a['assessment_dok'] is None, (
            "Non-remediation rows must return assessment_dok=null even if "
            "their content has uniform DOK — Sprint 1 scope is remediation-only"
        )
