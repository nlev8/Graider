"""Coverage backfill tests for student_portal_routes.py.

Covers: /api/publish-assessment, /api/teacher/assessments (list/results/toggle/delete),
/api/student/join/<code>, /api/student/submit/<code>, plus helpers.

All Supabase calls are mocked — zero network traffic.
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

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


def _make_chain(execute_data=None):
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
    chain.ilike.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = MagicMock(
        data=execute_data if execute_data is not None else []
    )
    return chain


def _multi_table_sb(table_map):
    """Return a Supabase mock where .table(name) yields different data per call."""
    mock_sb = MagicMock()

    def table_side(name):
        val = table_map.get(name)
        if val is None:
            return _make_chain([])
        if isinstance(val, MagicMock):
            return val
        return _make_chain(val)

    mock_sb.table.side_effect = table_side
    return mock_sb


# ============ PUBLISH ASSESSMENT ============

class TestPublishAssessment:
    # Phase 4.5: publish_assessment uses _get_teacher_supabase; the
    # generate_join_code helper (called inside) still uses get_supabase.
    # Tests that go past the early-return patch both; early-return only needs
    # the teacher patch.

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_no_assessment_returns_400(self, mock_get_teacher_sb, client, teacher_headers):
        mock_get_teacher_sb.return_value = _multi_table_sb({})
        resp = client.post('/api/publish-assessment', json={},
                           headers=teacher_headers)
        assert resp.status_code == 400

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    @patch('backend.routes.student_portal_routes.get_supabase')
    def test_publishes_assessment_returns_join_code(self, mock_get_sb,
                                                    mock_get_teacher_sb,
                                                    client, teacher_headers):
        # The table call for checking join-code uniqueness returns empty (code unused),
        # then upsert returns inserted row.
        mock_sb = MagicMock()
        insert_chain = _make_chain([{"id": "asm-1", "join_code": "ABC123"}])
        uniqueness_chain = _make_chain([])

        # Each call to .table returns a chain. generate_join_code polls until
        # empty result, then publish path upserts.
        call_count = {"n": 0}

        def table_side(name):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return uniqueness_chain
            return insert_chain

        mock_sb.table.side_effect = table_side
        mock_get_sb.return_value = mock_sb
        mock_get_teacher_sb.return_value = mock_sb

        payload = {
            "assessment": {"title": "Algebra Quiz", "total_points": 20},
            "settings": {
                "content_type": "assessment",
                "assessment_category": "summative",
                "time_limit_minutes": 30,
                "teacher_name": "Ms. Smith",
            },
        }
        resp = client.post('/api/publish-assessment', json=payload,
                           headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert 'join_code' in body
        assert 'join_link' in body

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    @patch('backend.routes.student_portal_routes.get_supabase')
    def test_publish_makeup_with_restricted_students(self, mock_get_sb, mock_get_teacher_sb,
                                                      client, teacher_headers):
        mock_sb = MagicMock()
        insert_chain = _make_chain([{"id": "asm-2"}])
        uniq = _make_chain([])
        mock_sb.table.side_effect = [uniq, insert_chain]
        mock_get_sb.return_value = mock_sb
        mock_get_teacher_sb.return_value = mock_sb

        payload = {
            "assessment": {"title": "Makeup"},
            "settings": {
                "restricted_students": ["Jane Doe", "John Smith"],
                "period": "3",
                "content_type": "assignment",
            },
        }
        resp = client.post('/api/publish-assessment', json=payload,
                           headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['restricted_students'] == ["Jane Doe", "John Smith"]
        assert body['period'] == '3'

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    @patch('backend.routes.student_portal_routes.get_supabase')
    def test_publish_upsert_returns_no_data_returns_500(self, mock_get_sb, mock_get_teacher_sb,
                                                         client, teacher_headers):
        mock_sb = MagicMock()
        uniq = _make_chain([])
        empty_upsert = _make_chain([])  # upsert returns empty data
        mock_sb.table.side_effect = [uniq, empty_upsert]
        mock_get_sb.return_value = mock_sb
        mock_get_teacher_sb.return_value = mock_sb

        resp = client.post('/api/publish-assessment',
                           json={"assessment": {"title": "X"}},
                           headers=teacher_headers)
        assert resp.status_code == 500


# ============ LIST PUBLISHED ASSESSMENTS ============

class TestListAssessments:

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_empty_list(self, mock_get_sb, client, teacher_headers):
        mock_get_sb.return_value = _multi_table_sb({'published_assessments': []})
        resp = client.get('/api/teacher/assessments', headers=teacher_headers)
        assert resp.status_code == 200
        assert resp.get_json() == {"assessments": []}

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_returns_assessments(self, mock_get_sb, client, teacher_headers):
        rows = [{
            "id": "a1", "join_code": "CODE01", "title": "Quiz 1",
            "created_at": "2026-04-01", "submission_count": 5,
            "is_active": True, "teacher_name": "Ms. S",
            "settings": {"content_type": "assessment", "period": "1",
                         "is_makeup": False, "restricted_students": [],
                         "unit_name": "Unit 1", "tags": ["algebra"]},
        }]
        mock_get_sb.return_value = _multi_table_sb({'published_assessments': rows})
        resp = client.get('/api/teacher/assessments', headers=teacher_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data['assessments']) == 1
        assert data['assessments'][0]['join_code'] == 'CODE01'
        assert data['assessments'][0]['tags'] == ['algebra']


# ============ ASSESSMENT RESULTS ============

class TestGetAssessmentResults:

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_not_found(self, mock_get_sb, client, teacher_headers):
        mock_get_sb.return_value = _multi_table_sb({'published_assessments': []})
        resp = client.get('/api/teacher/assessment/NONE99/results',
                          headers=teacher_headers)
        assert resp.status_code == 404

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_returns_submissions(self, mock_get_sb, client, teacher_headers):
        assessment_row = [{
            "id": "asm-1", "join_code": "ABC123", "title": "Quiz",
            "created_at": "2026-04-01", "is_active": True,
        }]
        submission_rows = [{
            "id": "sub-1", "student_name": "Jane",
            "score": 18, "total_points": 20, "percentage": 90,
            "time_taken_seconds": 600, "submitted_at": "2026-04-02",
            "results": {"score": 18},
        }]
        mock_get_sb.return_value = _multi_table_sb({
            'published_assessments': assessment_row,
            'submissions': submission_rows,
        })
        resp = client.get('/api/teacher/assessment/abc123/results',
                          headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['total_submissions'] == 1
        assert body['submissions'][0]['student_name'] == 'Jane'


# ============ TOGGLE ASSESSMENT ============

class TestToggleAssessment:

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_not_found(self, mock_get_sb, client, teacher_headers):
        mock_get_sb.return_value = _multi_table_sb({'published_assessments': []})
        resp = client.post('/api/teacher/assessment/BADCODE/toggle',
                           headers=teacher_headers)
        assert resp.status_code == 404

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_toggle_active_to_inactive(self, mock_get_sb, client, teacher_headers):
        mock_get_sb.return_value = _multi_table_sb({
            'published_assessments': [{"is_active": True}]
        })
        resp = client.post('/api/teacher/assessment/ABC123/toggle',
                           headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['active'] is False
        assert 'deactivated' in body['message']

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_toggle_inactive_to_active(self, mock_get_sb, client, teacher_headers):
        mock_get_sb.return_value = _multi_table_sb({
            'published_assessments': [{"is_active": False}]
        })
        resp = client.post('/api/teacher/assessment/ABC123/toggle',
                           headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['active'] is True
        assert 'activated' in body['message']


# ============ DELETE ASSESSMENT ============

class TestDeleteAssessment:

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_not_found(self, mock_get_sb, client, teacher_headers):
        mock_get_sb.return_value = _multi_table_sb({'published_assessments': []})
        resp = client.delete('/api/teacher/assessment/BADCODE',
                             headers=teacher_headers)
        assert resp.status_code == 404

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_delete_ok(self, mock_get_sb, client, teacher_headers):
        mock_get_sb.return_value = _multi_table_sb({
            'published_assessments': [{"id": "a1"}],
            'submissions': [],
        })
        resp = client.delete('/api/teacher/assessment/ABC123',
                             headers=teacher_headers)
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True


# ============ STUDENT JOIN ============

class TestStudentJoin:

    @patch('backend.routes.student_portal_routes.get_supabase')
    def test_not_found(self, mock_get_sb, client):
        mock_get_sb.return_value = _multi_table_sb({'published_assessments': []})
        resp = client.get('/api/student/join/BADCODE')
        assert resp.status_code == 404

    @patch('backend.routes.student_portal_routes.get_supabase')
    def test_inactive_assessment_returns_403(self, mock_get_sb, client):
        row = [{
            "id": "a1", "is_active": False,
            "assessment": {}, "settings": {},
        }]
        mock_get_sb.return_value = _multi_table_sb({'published_assessments': row})
        resp = client.get('/api/student/join/ABC123')
        assert resp.status_code == 403

    @patch('backend.routes.student_portal_routes.get_supabase')
    def test_returns_sanitized_assessment(self, mock_get_sb, client):
        row = [{
            "id": "a1", "is_active": True,
            "title": "Quiz", "teacher_name": "Ms. S",
            "assessment": {
                "title": "Quiz",
                "instructions": "Answer all",
                "total_points": 10,
                "time_estimate": "10 min",
                "sections": [{
                    "name": "Section 1",
                    "instructions": "Pick one",
                    "questions": [{
                        "number": 1,
                        "question": "2+2?",
                        "type": "multiple_choice",
                        "points": 5,
                        "options": ["A) 3", "B) 4"],
                        # Answer should NOT appear in response
                        "answer": "B",
                    }],
                }],
            },
            "settings": {"time_limit_minutes": 15, "require_name": True,
                         "period": "1"},
        }]
        mock_get_sb.return_value = _multi_table_sb({'published_assessments': row})
        resp = client.get('/api/student/join/ABC123')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['title'] == 'Quiz'
        # Verify answer stripped
        q = body['sections'][0]['questions'][0]
        assert 'answer' not in q
        assert q['options'] == ["A) 3", "B) 4"]

    @patch('backend.routes.student_portal_routes.get_supabase')
    def test_study_guide_material_response(self, mock_get_sb, client):
        row = [{
            "id": "sg1", "is_active": True, "title": "Chapter 7 Guide",
            "teacher_name": "Ms. S",
            "assessment": {"title": "Chapter 7 Guide",
                           "content": "# Chapter 7\n\nKey concepts..."},
            "settings": {"content_type": "study_guide"},
        }]
        mock_get_sb.return_value = _multi_table_sb({'published_assessments': row})
        resp = client.get('/api/student/join/STUDY1')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['content_type'] == 'study_guide'
        assert 'content' in body


# ============ STUDENT SUBMIT ============

class TestStudentSubmit:

    @patch('backend.routes.student_portal_routes.get_supabase')
    def test_assessment_not_found(self, mock_get_sb, client):
        mock_get_sb.return_value = _multi_table_sb({'published_assessments': []})
        resp = client.post('/api/student/submit/BADCODE',
                           json={"student_name": "Jane", "answers": {}})
        assert resp.status_code == 404

    @patch('backend.routes.student_portal_routes.get_supabase')
    def test_inactive_assessment(self, mock_get_sb, client):
        mock_get_sb.return_value = _multi_table_sb({
            'published_assessments': [{"is_active": False, "settings": {},
                                       "assessment": {}}]
        })
        resp = client.post('/api/student/submit/ABC123',
                           json={"student_name": "Jane", "answers": {}})
        assert resp.status_code == 403

    @patch('backend.routes.student_portal_routes.get_supabase')
    def test_duplicate_submission_blocked(self, mock_get_sb, client):
        assessment_row = [{
            "id": "a1", "is_active": True,
            "settings": {"allow_multiple_attempts": False,
                         "show_score_immediately": True,
                         "show_correct_answers": True},
            "assessment": {"sections": [{"questions": [
                {"type": "multiple_choice", "answer": "A",
                 "options": ["A) 1", "B) 2"], "points": 5}
            ]}]},
        }]
        existing_sub = [{"id": "old-sub", "results": {"score": 5}}]
        mock_get_sb.return_value = _multi_table_sb({
            'published_assessments': assessment_row,
            'submissions': existing_sub,
        })
        resp = client.post('/api/student/submit/ABC123',
                           json={"student_name": "Jane", "answers": {"0-0": "A"}})
        assert resp.status_code == 400
        assert 'already' in resp.get_json()['error'].lower()

    @patch('backend.routes.student_portal_routes.get_supabase')
    def test_happy_path_mc_only_submission(self, mock_get_sb, client):
        assessment_row = [{
            "id": "a1", "teacher_id": "t1", "is_active": True,
            "settings": {"allow_multiple_attempts": True,
                         "show_score_immediately": True,
                         "show_correct_answers": True},
            "assessment": {"sections": [{"questions": [
                {"type": "multiple_choice", "answer": "A",
                 "options": ["A) 1", "B) 2"], "points": 5},
            ]}]},
        }]
        mock_sb = MagicMock()
        chain_assessment = _make_chain(assessment_row)
        chain_insert = _make_chain([{"id": "new-sub"}])
        # Order: lookup assessment, insert submission
        mock_sb.table.side_effect = [chain_assessment, chain_insert]
        mock_get_sb.return_value = mock_sb

        resp = client.post('/api/student/submit/ABC123',
                           json={"student_name": "Jane",
                                 "answers": {"0-0": "A"},
                                 "time_taken_seconds": 120})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['student_name'] == 'Jane'

    @patch('backend.routes.student_portal_routes.get_supabase')
    def test_pending_review_mode(self, mock_get_sb, client):
        """When show_score + show_answers both false => pending_review status."""
        assessment_row = [{
            "id": "a1", "is_active": True,
            "settings": {"allow_multiple_attempts": True,
                         "show_score_immediately": False,
                         "show_correct_answers": False},
            "assessment": {"sections": [{"questions": [
                {"type": "multiple_choice", "answer": "A",
                 "options": ["A) 1", "B) 2"], "points": 5}
            ]}]},
        }]
        mock_sb = MagicMock()
        mock_sb.table.side_effect = [
            _make_chain(assessment_row),
            _make_chain([{"id": "new-sub"}]),
        ]
        mock_get_sb.return_value = mock_sb
        resp = client.post('/api/student/submit/ABC123',
                           json={"student_name": "Jane",
                                 "answers": {"0-0": "A"}})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['grading_status'] == 'pending_review'


# ============ HELPERS ============

class TestHelpers:

    def test_parse_ts_empty(self):
        from backend.routes.student_portal_routes import _parse_ts
        assert _parse_ts('') == datetime.min
        assert _parse_ts(None) == datetime.min

    def test_parse_ts_invalid(self):
        from backend.routes.student_portal_routes import _parse_ts
        assert _parse_ts('not-a-date') == datetime.min

    def test_parse_ts_iso_with_z(self):
        from backend.routes.student_portal_routes import _parse_ts
        result = _parse_ts('2026-04-01T12:00:00Z')
        assert result.year == 2026
        assert result.month == 4

    def test_select_submissions_latest(self):
        from backend.routes.student_portal_routes import _select_submissions_by_mode
        subs = {"c1": [
            {"id": "s1", "attempt_number": 1, "submitted_at": "2026-01-01"},
            {"id": "s2", "attempt_number": 2, "submitted_at": "2026-02-01"},
        ]}
        selected = _select_submissions_by_mode(subs, 'latest')
        assert selected["c1"][0]["id"] == "s2"

    def test_select_submissions_best(self):
        from backend.routes.student_portal_routes import _select_submissions_by_mode
        subs = {"c1": [
            {"id": "s1", "percentage": 70, "submitted_at": "2026-01-01"},
            {"id": "s2", "percentage": 90, "submitted_at": "2026-02-01"},
            {"id": "s3", "percentage": 80, "submitted_at": "2026-03-01"},
        ]}
        selected = _select_submissions_by_mode(subs, 'best')
        assert selected["c1"][0]["id"] == "s2"

    def test_select_submissions_average_passes_through(self):
        from backend.routes.student_portal_routes import _select_submissions_by_mode
        subs = {"c1": [
            {"id": "s1", "percentage": 70},
            {"id": "s2", "percentage": 90},
        ]}
        selected = _select_submissions_by_mode(subs, 'average')
        assert len(selected["c1"]) == 2

    def test_aggregate_mastery_empty(self):
        from backend.routes.student_portal_routes import _aggregate_mastery_for_student
        result = _aggregate_mastery_for_student({}, {}, 'latest')
        assert result == {}

    def test_aggregate_mastery_latest_mode(self):
        from backend.routes.student_portal_routes import _aggregate_mastery_for_student
        selected = {"c1": [{
            "id": "s1", "attempt_number": 1,
            "results": {"standards_mastery": {
                "CCSS.A1": {"points_earned": 8, "points_possible": 10,
                            "question_count": 2},
            }},
        }]}
        result = _aggregate_mastery_for_student(
            selected, {"c1": "Quiz 1"}, 'latest'
        )
        assert "CCSS.A1" in result
        assert result["CCSS.A1"]["percentage"] == 80.0

    def test_aggregate_mastery_average_mode(self):
        from backend.routes.student_portal_routes import _aggregate_mastery_for_student
        selected = {"c1": [
            {"id": "s1", "attempt_number": 1,
             "results": {"standards_mastery": {
                 "CCSS.A1": {"points_earned": 6, "points_possible": 10,
                             "question_count": 1},
             }}},
            {"id": "s2", "attempt_number": 2,
             "results": {"standards_mastery": {
                 "CCSS.A1": {"points_earned": 10, "points_possible": 10,
                             "question_count": 1},
             }}},
        ]}
        result = _aggregate_mastery_for_student(
            selected, {"c1": "Quiz"}, 'average'
        )
        # Average of 60% + 100% = 80% → 8 points out of 10
        assert result["CCSS.A1"]["percentage"] == 80.0
