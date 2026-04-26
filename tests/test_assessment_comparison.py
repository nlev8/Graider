"""Tests for the assessment comparison endpoint.

Spec: docs/superpowers/specs/2026-04-26-phase3b-assessment-comparison-design.md
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


# ============ Test fixtures ============

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
    """Minimal Flask app WITHOUT the dev-mode before_request hook so
    require_teacher can return 401."""
    from flask import Flask
    from backend.routes.student_portal_routes import student_portal_bp
    isolated = Flask(__name__)
    isolated.config['TESTING'] = True
    isolated.config['SECRET_KEY'] = 'test'
    isolated.register_blueprint(student_portal_bp)
    return isolated.test_client()


def _make_chain(execute_data=None):
    """Filter-aware Supabase mock — applies .eq() / .in_() / .neq() filters at .execute() time.

    Required: tests must observe `.in_()` (used for student_id/content_id IN ...) and
    `.neq()` (used for status != 'draft'). A no-op mock would mask draft-exclusion bugs.
    """
    data = list(execute_data) if execute_data else []
    chain = MagicMock()
    chain.select.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.range.return_value = chain
    filters = []

    def _eq(field, value):
        filters.append(('eq', field, value))
        return chain
    chain.eq.side_effect = _eq

    def _in(field, values):
        filters.append(('in', field, list(values)))
        return chain
    chain.in_.side_effect = _in

    def _neq(field, value):
        filters.append(('neq', field, value))
        return chain
    chain.neq.side_effect = _neq

    def _execute():
        result = data
        for op, field, value in filters:
            if op == 'eq':
                result = [r for r in result if r.get(field) == value]
            elif op == 'in':
                result = [r for r in result if r.get(field) in value]
            elif op == 'neq':
                result = [r for r in result if r.get(field) != value]
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


CLS_OWNED = [{'id': 'cls-1', 'name': 'Period 3', 'teacher_id': 'test-teacher-001'}]


# ============ Validation tests ============

class TestAssessmentComparisonValidation:
    """Auth + content_ids validation."""

    def test_unauthenticated_returns_401(self, client_no_auth):
        resp = client_no_auth.get('/api/teacher/class/cls-1/compare?content_ids=a,b')
        assert resp.status_code == 401

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_other_teacher_class_returns_403(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'OTHER'}],
        })
        resp = client.get('/api/teacher/class/cls-1/compare?content_ids=11111111-1111-1111-1111-111111111111,22222222-2222-2222-2222-222222222222', headers=teacher_headers)
        assert resp.status_code == 403

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_missing_content_ids_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({'classes': CLS_OWNED})
        resp = client.get('/api/teacher/class/cls-1/compare', headers=teacher_headers)
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'content_ids is required' in body.get('detail', body.get('error', ''))

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_one_content_id_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({'classes': CLS_OWNED})
        resp = client.get('/api/teacher/class/cls-1/compare?content_ids=11111111-1111-1111-1111-111111111111', headers=teacher_headers)
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'at least 2' in body.get('detail', body.get('error', ''))

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_seven_content_ids_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({'classes': CLS_OWNED})
        seven = ','.join('1' * 8 + '-' + '1' * 4 + '-' + '1' * 4 + '-' + '1' * 4 + '-' + '1' * 12 for _ in range(7))
        resp = client.get('/api/teacher/class/cls-1/compare?content_ids=' + seven, headers=teacher_headers)
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'at most 6' in body.get('detail', body.get('error', ''))

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_malformed_uuid_returns_400(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({'classes': CLS_OWNED})
        resp = client.get('/api/teacher/class/cls-1/compare?content_ids=not-a-uuid,11111111-1111-1111-1111-111111111111', headers=teacher_headers)
        assert resp.status_code == 400
        body = resp.get_json()
        assert 'Invalid content_id' in body.get('detail', body.get('error', ''))

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_content_id_outside_class_returns_403(self, mock_sb_fn, client, teacher_headers):
        # Both ids are valid UUIDs, but only one is in this class.
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [],
            'students': [],
            'published_content': [
                {'id': '11111111-1111-1111-1111-111111111111', 'title': 'Q1',
                 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
                # 22222222... is NOT in this class
            ],
        })
        resp = client.get('/api/teacher/class/cls-1/compare?content_ids=11111111-1111-1111-1111-111111111111,22222222-2222-2222-2222-222222222222', headers=teacher_headers)
        assert resp.status_code == 403

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_content_id_is_assignment_not_assessment_returns_403(self, mock_sb_fn, client, teacher_headers):
        """Both ids exist in this class, but one has content_type='assignment'.
        Comparison is assessment-only — assignments must be rejected even if owned."""
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [],
            'students': [],
            'published_content': [
                {'id': '11111111-1111-1111-1111-111111111111', 'title': 'Q1',
                 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
                {'id': '22222222-2222-2222-2222-222222222222', 'title': 'HW1',
                 'class_id': 'cls-1', 'content_type': 'assignment', 'max_points': 10},
            ],
        })
        resp = client.get('/api/teacher/class/cls-1/compare?content_ids=11111111-1111-1111-1111-111111111111,22222222-2222-2222-2222-222222222222', headers=teacher_headers)
        assert resp.status_code == 403


class TestAssessmentComparisonRoster:
    """Valid-roster definition + orphan handling."""

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_class_roster_size_skips_orphan_enrollments(self, mock_sb_fn, client, teacher_headers):
        # class_students has 2 ids; students table has only 1 (orphan = stu-orphan).
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': 'stu-1'},
                               {'class_id': 'cls-1', 'student_id': 'stu-orphan'}],
            'students': [{'id': 'stu-1'}],  # stu-orphan missing
            'published_content': [
                {'id': '11111111-1111-1111-1111-111111111111', 'title': 'Q1',
                 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
                {'id': '22222222-2222-2222-2222-222222222222', 'title': 'Q2',
                 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
            ],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/compare?content_ids=11111111-1111-1111-1111-111111111111,22222222-2222-2222-2222-222222222222', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # Orphan dropped — roster size = 1
        assert body['class_roster_size'] == 1

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_empty_class_returns_zero_roster(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [],
            'students': [],
            'published_content': [
                {'id': '11111111-1111-1111-1111-111111111111', 'title': 'Q1',
                 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
                {'id': '22222222-2222-2222-2222-222222222222', 'title': 'Q2',
                 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
            ],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/compare?content_ids=11111111-1111-1111-1111-111111111111,22222222-2222-2222-2222-222222222222', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['class_roster_size'] == 0
        # Both assessments should still appear with n=0
        assert len(body['assessments']) == 2
        assert all(a['n'] == 0 for a in body['assessments'])
        assert all(a['submission_rate'] == 0.0 for a in body['assessments'])

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_former_student_with_submission_excluded(self, mock_sb_fn, client, teacher_headers):
        """A submission from a student_id NOT in the current valid roster (former student
        whose enrollment was removed but whose submission row still exists) must not
        affect distribution stats — class roster scoping is the source of truth.
        Tests that the route's `for sid in valid_student_ids` iteration drops orphan submissions."""
        cid_q1 = '11111111-1111-1111-1111-111111111111'
        cid_q2 = '22222222-2222-2222-2222-222222222222'
        # Roster: stu-1 only. ex-stu submitted Q1 but is no longer enrolled.
        subs = [
            {'id': 'sub-current', 'student_id': 'stu-1', 'content_id': cid_q1,
             'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
             'percentage': 90,
             'results': {'standards_mastery': {}, 'score': 9, 'total_points': 10},
             'status': 'graded'},
            {'id': 'sub-former', 'student_id': 'ex-stu', 'content_id': cid_q1,
             'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
             'percentage': 30,  # Would drag the mean down if included.
             'results': {'standards_mastery': {}, 'score': 3, 'total_points': 10},
             'status': 'graded'},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1'}],
            'published_content': [
                {'id': cid_q1, 'title': 'Q1', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
                {'id': cid_q2, 'title': 'Q2', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
            ],
            'student_submissions': subs,
        })
        resp = client.get(f'/api/teacher/class/cls-1/compare?content_ids={cid_q1},{cid_q2}', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        a_q1 = next(a for a in body['assessments'] if a['content_id'] == cid_q1)
        # Only stu-1's 90 must count; ex-stu's 30 must NOT affect distribution.
        assert a_q1['n'] == 1
        assert a_q1['mean'] == 90
        assert 30 not in a_q1['percentages']
