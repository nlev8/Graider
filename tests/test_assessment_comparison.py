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


class TestAssessmentComparisonDistribution:
    """Distribution stats: n, mean, median, quartiles, min, max."""

    def _make_subs(self, content_pcts):
        """Build student_submissions list. content_pcts: dict[content_id, list[(student_id, percentage)]]."""
        subs = []
        sub_id = 0
        for cid, entries in content_pcts.items():
            for student_id, pct in entries:
                sub_id += 1
                subs.append({
                    'id': f'sub-{sub_id}', 'student_id': student_id, 'content_id': cid,
                    'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
                    'percentage': pct,
                    'results': {'standards_mastery': {}, 'score': pct / 10, 'total_points': 10},
                    'status': 'graded',
                })
        return subs

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_happy_path_two_assessments_returns_full_response(self, mock_sb_fn, client, teacher_headers):
        # Class roster: 4 students. Q1 has 4 submissions; Q2 has 3 (one student absent).
        student_ids = [f'stu-{i}' for i in range(1, 5)]
        cid_q1 = '11111111-1111-1111-1111-111111111111'
        cid_q2 = '22222222-2222-2222-2222-222222222222'
        subs = self._make_subs({
            cid_q1: [(student_ids[0], 50), (student_ids[1], 70), (student_ids[2], 80), (student_ids[3], 90)],
            cid_q2: [(student_ids[0], 60), (student_ids[1], 75), (student_ids[2], 85)],
        })
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': sid} for sid in student_ids],
            'students': [{'id': sid} for sid in student_ids],
            'published_content': [
                {'id': cid_q1, 'title': 'Q1', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
                {'id': cid_q2, 'title': 'Q2', 'class_id': 'cls-1', 'content_type': 'assessment', 'max_points': 10},
            ],
            'student_submissions': subs,
        })
        resp = client.get(f'/api/teacher/class/cls-1/compare?content_ids={cid_q1},{cid_q2}', headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['class_roster_size'] == 4
        a_q1 = next(a for a in body['assessments'] if a['content_id'] == cid_q1)
        a_q2 = next(a for a in body['assessments'] if a['content_id'] == cid_q2)
        # Q1: 4 submissions, mean 72.5, median 75, min 50, max 90
        assert a_q1['n'] == 4
        assert a_q1['submission_rate'] == 1.0
        assert a_q1['mean'] == 72.5
        assert a_q1['median'] == 75.0
        assert a_q1['min'] == 50
        assert a_q1['max'] == 90
        # Q2: 3 submissions, submission_rate = 0.75 (3/4)
        assert a_q2['n'] == 3
        assert a_q2['submission_rate'] == 0.75
        assert a_q2['mean'] == round((60 + 75 + 85) / 3, 2) or a_q2['mean'] == round((60 + 75 + 85) / 3, 1)

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_zero_submissions_assessment_returns_zero_stats(self, mock_sb_fn, client, teacher_headers):
        cid_q1 = '11111111-1111-1111-1111-111111111111'
        cid_q2 = '22222222-2222-2222-2222-222222222222'
        # Only Q1 has submissions; Q2 has none.
        subs = self._make_subs({cid_q1: [('stu-1', 80)]})
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
        body = resp.get_json()
        a_q2 = next(a for a in body['assessments'] if a['content_id'] == cid_q2)
        assert a_q2['n'] == 0
        assert a_q2['mean'] == 0
        assert a_q2['median'] == 0
        assert a_q2['q1'] == 0
        assert a_q2['q3'] == 0
        assert a_q2['percentages'] == []

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_attempt_mode_average_uses_mean_per_student(self, mock_sb_fn, client, teacher_headers):
        cid_q1 = '11111111-1111-1111-1111-111111111111'
        cid_q2 = '22222222-2222-2222-2222-222222222222'
        # Single student, 2 attempts at Q1: 50% and 90% → mean 70%
        subs = [
            {'id': 'sub-1', 'student_id': 'stu-1', 'content_id': cid_q1,
             'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
             'percentage': 50,
             'results': {'standards_mastery': {}, 'score': 5, 'total_points': 10},
             'status': 'graded'},
            {'id': 'sub-2', 'student_id': 'stu-1', 'content_id': cid_q1,
             'attempt_number': 2, 'submitted_at': '2026-04-12T10:00:00Z',
             'percentage': 90,
             'results': {'standards_mastery': {}, 'score': 9, 'total_points': 10},
             'status': 'graded'},
            {'id': 'sub-3', 'student_id': 'stu-1', 'content_id': cid_q2,
             'attempt_number': 1, 'submitted_at': '2026-04-15T10:00:00Z',
             'percentage': 80,
             'results': {'standards_mastery': {}, 'score': 8, 'total_points': 10},
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
        resp = client.get(f'/api/teacher/class/cls-1/compare?content_ids={cid_q1},{cid_q2}&attempt_mode=average', headers=teacher_headers)
        body = resp.get_json()
        a_q1 = next(a for a in body['assessments'] if a['content_id'] == cid_q1)
        # n=1 (one student); mean of [70.0] = 70.0
        assert a_q1['n'] == 1
        assert a_q1['mean'] == 70.0
        # n==1 → q1==q3==70.0
        assert a_q1['q1'] == 70.0
        assert a_q1['q3'] == 70.0

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_non_numeric_percentage_skipped(self, mock_sb_fn, client, teacher_headers, caplog):
        """Submission with string percentage is skipped from distribution; warning logged."""
        import logging
        caplog.set_level(logging.WARNING, logger='backend.routes.student_portal_routes')
        cid_q1 = '11111111-1111-1111-1111-111111111111'
        cid_q2 = '22222222-2222-2222-2222-222222222222'
        subs = [
            {'id': 'sub-good', 'student_id': 'stu-1', 'content_id': cid_q1,
             'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
             'percentage': 80,
             'results': {'standards_mastery': {}, 'score': 8, 'total_points': 10},
             'status': 'graded'},
            {'id': 'sub-bad', 'student_id': 'stu-2', 'content_id': cid_q1,
             'attempt_number': 1, 'submitted_at': '2026-04-11T10:00:00Z',
             'percentage': 'not-a-number',
             'results': {'standards_mastery': {}, 'score': 0, 'total_points': 10},
             'status': 'graded'},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': 'stu-1'},
                               {'class_id': 'cls-1', 'student_id': 'stu-2'}],
            'students': [{'id': 'stu-1'}, {'id': 'stu-2'}],
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
        # Only the good submission counted; n=1 for Q1
        assert a_q1['n'] == 1
        assert a_q1['mean'] == 80
        # Warning logged
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any('non-numeric percentage' in r.getMessage() for r in warnings)

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_numeric_string_percentage_coerced(self, mock_sb_fn, client, teacher_headers):
        """percentage='80' (numeric string) must be coerced to 80.0, not skipped.
        Some grading paths historically wrote percentage as a string — _safe_percentage
        must treat numeric strings as valid input."""
        cid_q1 = '11111111-1111-1111-1111-111111111111'
        cid_q2 = '22222222-2222-2222-2222-222222222222'
        subs = [
            {'id': 'sub-string', 'student_id': 'stu-1', 'content_id': cid_q1,
             'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
             'percentage': '80',  # string, not int — must coerce, not skip.
             'results': {'standards_mastery': {}, 'score': 8, 'total_points': 10},
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
        assert a_q1['n'] == 1
        assert a_q1['mean'] == 80.0

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_draft_submissions_excluded_from_distribution(self, mock_sb_fn, client, teacher_headers):
        """Submissions with status='draft' must be filtered out by `.neq('status', 'draft')`
        on the SQL query — they must not affect n / mean / median / percentages.
        Without proper SQL exclusion, the filter-aware `_make_chain` would include them
        and this test would fail."""
        cid_q1 = '11111111-1111-1111-1111-111111111111'
        cid_q2 = '22222222-2222-2222-2222-222222222222'
        subs = [
            {'id': 'sub-graded', 'student_id': 'stu-1', 'content_id': cid_q1,
             'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
             'percentage': 80,
             'results': {'standards_mastery': {}, 'score': 8, 'total_points': 10},
             'status': 'graded'},
            {'id': 'sub-draft', 'student_id': 'stu-2', 'content_id': cid_q1,
             'attempt_number': 1, 'submitted_at': '2026-04-10T10:00:00Z',
             'percentage': 0,  # Would drag the mean to 40 if included.
             'results': {'standards_mastery': {}, 'score': 0, 'total_points': 10},
             'status': 'draft'},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': CLS_OWNED,
            'class_students': [{'class_id': 'cls-1', 'student_id': 'stu-1'},
                               {'class_id': 'cls-1', 'student_id': 'stu-2'}],
            'students': [{'id': 'stu-1'}, {'id': 'stu-2'}],
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
        # Only the graded submission counts.
        assert a_q1['n'] == 1
        assert a_q1['mean'] == 80
        assert 0 not in a_q1['percentages']
