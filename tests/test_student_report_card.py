"""Tests for the student report card endpoint and bridge helper.

Spec: docs/superpowers/specs/2026-04-25-phase2b-student-report-card-design.md
"""
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


# ============ Bridge helper unit tests ============

class TestBuildStandardsBreakdownForStudent:
    """_build_standards_breakdown_for_student: dict → sorted array + enrichment."""

    def test_empty_input_returns_empty_array(self):
        from backend.routes.student_portal_routes import _build_standards_breakdown_for_student
        result = _build_standards_breakdown_for_student({}, {})
        assert result == []

    def test_single_standard_passes_through_with_code(self):
        from backend.routes.student_portal_routes import _build_standards_breakdown_for_student
        mastery_by_code = {
            "MA.6.AR.1.1": {
                "percentage": 75,
                "points_earned": 15,
                "points_possible": 20,
                "question_count": 4,
                "contributing_submissions": [
                    {"submission_id": "sub-1", "title": "Quiz 1",
                     "points_earned": 15, "points_possible": 20, "attempt_number": 1},
                ],
            },
        }
        submission_lookup = {
            "sub-1": {"submitted_at": "2026-04-12T15:30:00Z", "percentage": 70},
        }
        result = _build_standards_breakdown_for_student(mastery_by_code, submission_lookup)
        assert len(result) == 1
        assert result[0]["code"] == "MA.6.AR.1.1"
        assert result[0]["percentage"] == 75
        assert result[0]["points_earned"] == 15
        # contributing_submission enriched with submitted_at + percentage
        cs = result[0]["contributing_submissions"][0]
        assert cs["submission_id"] == "sub-1"
        assert cs["submitted_at"] == "2026-04-12T15:30:00Z"
        assert cs["percentage"] == 75.0  # 15/20 * 100

    def test_multiple_standards_sorted_worst_first(self):
        from backend.routes.student_portal_routes import _build_standards_breakdown_for_student
        mastery_by_code = {
            "MA.6.AR.1.1": {"percentage": 90, "points_earned": 18, "points_possible": 20,
                            "question_count": 4, "contributing_submissions": []},
            "MA.6.AR.2.1": {"percentage": 50, "points_earned": 5, "points_possible": 10,
                            "question_count": 2, "contributing_submissions": []},
            "MA.6.AR.3.1": {"percentage": 75, "points_earned": 15, "points_possible": 20,
                            "question_count": 4, "contributing_submissions": []},
        }
        result = _build_standards_breakdown_for_student(mastery_by_code, {})
        # ASC by percentage (worst first)
        assert [r["code"] for r in result] == ["MA.6.AR.2.1", "MA.6.AR.3.1", "MA.6.AR.1.1"]

    def test_contributing_submission_missing_in_lookup_keeps_existing_fields(self):
        """If submission_lookup doesn't have an entry for a contributor, the
        contributor still appears with its original fields (no submitted_at/
        percentage enrichment, but not dropped)."""
        from backend.routes.student_portal_routes import _build_standards_breakdown_for_student
        mastery_by_code = {
            "MA.6.AR.1.1": {
                "percentage": 75, "points_earned": 15, "points_possible": 20,
                "question_count": 4,
                "contributing_submissions": [
                    {"submission_id": "sub-missing", "title": "Quiz 1",
                     "points_earned": 15, "points_possible": 20, "attempt_number": 1},
                ],
            },
        }
        result = _build_standards_breakdown_for_student(mastery_by_code, {})
        cs = result[0]["contributing_submissions"][0]
        assert cs["submission_id"] == "sub-missing"
        # No submitted_at because lookup miss; percentage still computed
        assert "submitted_at" not in cs or cs["submitted_at"] is None
        assert cs["percentage"] == 75.0  # 15/20 — computed from points, not lookup


class TestBuildTrajectoryForStudent:
    """_build_trajectory_for_student: list[submission] → chronological list."""

    def test_empty_input_returns_empty_array(self):
        from backend.routes.student_portal_routes import _build_trajectory_for_student
        assert _build_trajectory_for_student([], {}) == []

    def test_orders_ascending_by_submitted_at(self):
        from backend.routes.student_portal_routes import _build_trajectory_for_student
        subs = [
            {"id": "s2", "content_id": "c1", "submitted_at": "2026-04-15T10:00:00Z",
             "percentage": 80, "attempt_number": 1, "results": {"points_earned": 8, "points_possible": 10}},
            {"id": "s1", "content_id": "c1", "submitted_at": "2026-04-10T10:00:00Z",
             "percentage": 60, "attempt_number": 1, "results": {"points_earned": 6, "points_possible": 10}},
            {"id": "s3", "content_id": "c1", "submitted_at": "2026-04-20T10:00:00Z",
             "percentage": 90, "attempt_number": 2, "results": {"points_earned": 9, "points_possible": 10}},
        ]
        content_titles = {"c1": "Quiz 1"}
        result = _build_trajectory_for_student(subs, content_titles)
        assert [r["submission_id"] for r in result] == ["s1", "s2", "s3"]
        assert result[0]["title"] == "Quiz 1"
        assert result[0]["percentage"] == 60
        assert result[0]["points_earned"] == 6
        assert result[0]["points_possible"] == 10

    def test_null_submitted_at_sorted_to_end(self):
        from backend.routes.student_portal_routes import _build_trajectory_for_student
        subs = [
            {"id": "s_null", "content_id": "c1", "submitted_at": None,
             "percentage": 50, "attempt_number": 1, "results": {}},
            {"id": "s_dated", "content_id": "c1", "submitted_at": "2026-04-10T10:00:00Z",
             "percentage": 70, "attempt_number": 1, "results": {}},
        ]
        result = _build_trajectory_for_student(subs, {"c1": "Q"})
        # Null sorts to END
        assert [r["submission_id"] for r in result] == ["s_dated", "s_null"]

    def test_missing_content_title_uses_empty_string(self):
        from backend.routes.student_portal_routes import _build_trajectory_for_student
        subs = [
            {"id": "s1", "content_id": "c-missing", "submitted_at": "2026-04-10T10:00:00Z",
             "percentage": 70, "attempt_number": 1, "results": {}},
        ]
        result = _build_trajectory_for_student(subs, {})
        assert result[0]["title"] == ""

    def test_mixed_iso_formats_sort_chronologically(self):
        """Submitted_at with 'Z' vs '+00:00' suffix must sort by actual
        instant, not lexicographically. Z (0x5A) > + (0x2B) in ASCII so
        a naive string sort would put '+00:00' before 'Z' even when the
        '+00:00' instant is later."""
        from backend.routes.student_portal_routes import _build_trajectory_for_student
        subs = [
            # Z form, 15:30:00
            {"id": "z-earlier", "content_id": "c1", "submitted_at": "2026-04-12T15:30:00Z",
             "percentage": 80, "attempt_number": 1, "results": {}},
            # +00:00 form, 15:30:01 (one second LATER)
            {"id": "plus-later", "content_id": "c1", "submitted_at": "2026-04-12T15:30:01+00:00",
             "percentage": 80, "attempt_number": 1, "results": {}},
        ]
        result = _build_trajectory_for_student(subs, {"c1": "Q"})
        # Chronological order: Z-earlier first (15:30:00), then plus-later (15:30:01).
        # If the sort uses raw strings, "+" sorts before "Z" so plus-later would
        # come first — that's the regression we're guarding against.
        assert [r["submission_id"] for r in result] == ["z-earlier", "plus-later"]


# ============ Route handler tests ============

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
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.neq.return_value = chain
    chain.in_.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = MagicMock(data=execute_data if execute_data is not None else [])
    return chain


def _multi_table_sb(table_map):
    """Mock supabase that returns different chains per table name."""
    mock_sb = MagicMock()
    def table_side_effect(name):
        val = table_map.get(name)
        if val is None:
            return _make_chain([])
        return _make_chain(val)
    mock_sb.table.side_effect = table_side_effect
    return mock_sb


@pytest.fixture
def client_no_auth():
    """Minimal Flask client with the student_portal blueprint but NO auth
    middleware — g.user_id is never set, so @require_teacher returns 401.
    Matches the pattern in test_sso_contracts.py."""
    from flask import Flask
    from backend.routes.student_portal_routes import student_portal_bp
    minimal = Flask(__name__)
    minimal.config['TESTING'] = True
    minimal.secret_key = 'test-secret'
    minimal.register_blueprint(student_portal_bp)
    return minimal.test_client()


class TestReportCardAuthz:
    """Auth + class-ownership + student-in-class checks."""

    def test_unauthenticated_returns_401(self, client_no_auth):
        # No auth middleware → g.user_id never set → require_teacher rejects
        resp = client_no_auth.get('/api/teacher/class/cls-1/student/stu-1/report-card')
        assert resp.status_code == 401

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_other_teacher_class_returns_403(self, mock_sb_fn, client, teacher_headers):
        # Class belongs to a different teacher
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'OTHER-teacher'}],
        })
        resp = client.get('/api/teacher/class/cls-1/student/stu-1/report-card',
                          headers=teacher_headers)
        assert resp.status_code == 403
        body = resp.get_json()
        # RFC 7807 envelope (Phase 5d PR 1)
        assert body.get('type') == 'https://graider.live/errors/forbidden'
        assert body.get('status') == 403
        # Backward-compat error field still present
        assert 'error' in body

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_student_not_in_class_returns_404(self, mock_sb_fn, client, teacher_headers):
        # Class is owned but class_students has no enrollment for stu-X
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [],  # not enrolled
        })
        resp = client.get('/api/teacher/class/cls-1/student/stu-X/report-card',
                          headers=teacher_headers)
        assert resp.status_code == 404
        body = resp.get_json()
        assert body.get('type') == 'https://graider.live/errors/not-found'
        assert body.get('status') == 404

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_orphan_enrollment_returns_404(self, mock_sb_fn, client, teacher_headers):
        # class_students lists the student but students row is gone
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-orphan'}],
            'students': [],  # row missing
        })
        resp = client.get('/api/teacher/class/cls-1/student/stu-orphan/report-card',
                          headers=teacher_headers)
        assert resp.status_code == 404


class TestReportCardHappyPath:
    """Happy-path data assembly: trajectory + breakdown."""

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_happy_path_returns_trajectory_and_breakdown(self, mock_sb_fn, client, teacher_headers):
        # Two assessments, two submissions for our student
        mastery_a = {
            "MA.6.AR.1.1": {"points_earned": 8, "points_possible": 10, "question_count": 2},
        }
        mastery_b = {
            "MA.6.AR.1.1": {"points_earned": 5, "points_possible": 10, "question_count": 2},
            "MA.6.AR.2.1": {"points_earned": 2, "points_possible": 10, "question_count": 2},
        }
        subs = [
            {"id": "sub-1", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 1, "submitted_at": "2026-04-10T10:00:00Z",
             "percentage": 80, "results": {"standards_mastery": mastery_a,
                                            "points_earned": 8, "points_possible": 10},
             "status": "graded"},
            {"id": "sub-2", "student_id": "stu-1", "content_id": "ct-2",
             "attempt_number": 1, "submitted_at": "2026-04-15T10:00:00Z",
             "percentage": 35, "results": {"standards_mastery": mastery_b,
                                            "points_earned": 7, "points_possible": 20},
             "status": "graded"},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'Period 3', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'Jane', 'last_name': 'Doe'}],
            'published_content': [
                {'id': 'ct-1', 'title': 'Quiz 1', 'content_type': 'assessment'},
                {'id': 'ct-2', 'title': 'Quiz 2', 'content_type': 'assessment'},
            ],
            'student_submissions': subs,
        })
        resp = client.get('/api/teacher/class/cls-1/student/stu-1/report-card',
                          headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['student_id'] == 'stu-1'
        assert body['student_name'] == 'Jane Doe'
        assert body['class_id'] == 'cls-1'
        assert body['class_name'] == 'Period 3'
        assert body['attempt_mode'] == 'latest'
        # Trajectory is ASC by submitted_at (oldest first)
        assert [t['submission_id'] for t in body['trajectory']] == ['sub-1', 'sub-2']
        # Each trajectory entry includes full shape per spec
        assert body['trajectory'][0]['title'] == 'Quiz 1'
        assert body['trajectory'][0]['percentage'] == 80
        # standards_breakdown sorted worst-first
        codes = [s['code'] for s in body['standards_breakdown']]
        assert codes[0] == 'MA.6.AR.2.1'  # 20% — worst
        # contributing_submissions enriched with submitted_at + percentage + submission_id
        cs = body['standards_breakdown'][0]['contributing_submissions'][0]
        assert cs['submission_id'] == 'sub-2'
        assert cs['submitted_at'] == '2026-04-15T10:00:00Z'
        assert 'percentage' in cs

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_no_submissions_returns_empty_arrays_with_200(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'Jane', 'last_name': 'Doe'}],
            'published_content': [],
            'student_submissions': [],
        })
        resp = client.get('/api/teacher/class/cls-1/student/stu-1/report-card',
                          headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['trajectory'] == []
        assert body['standards_breakdown'] == []


class TestReportCardAttemptModes:
    """Verify attempt_mode latest/best/average are honored end-to-end."""

    def _setup_three_attempts(self, mock_sb_fn):
        """One assessment, three attempts: 50%, 90%, 70%."""
        masteries = [
            {"MA.6.AR.1.1": {"points_earned": 5, "points_possible": 10, "question_count": 2}},
            {"MA.6.AR.1.1": {"points_earned": 9, "points_possible": 10, "question_count": 2}},
            {"MA.6.AR.1.1": {"points_earned": 7, "points_possible": 10, "question_count": 2}},
        ]
        subs = []
        for i, (pct, mast) in enumerate(zip([50, 90, 70], masteries), start=1):
            subs.append({
                "id": f"sub-{i}", "student_id": "stu-1", "content_id": "ct-1",
                "attempt_number": i, "submitted_at": f"2026-04-{10+i}T10:00:00Z",
                "percentage": pct, "results": {"standards_mastery": mast,
                                                "points_earned": pct/10,
                                                "points_possible": 10},
                "status": "graded",
            })
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [{'id': 'ct-1', 'title': 'Q', 'content_type': 'assessment'}],
            'student_submissions': subs,
        })

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_attempt_mode_latest_picks_most_recent_per_content(self, mock_sb_fn, client, teacher_headers):
        self._setup_three_attempts(mock_sb_fn)
        resp = client.get(
            '/api/teacher/class/cls-1/student/stu-1/report-card?attempt_mode=latest',
            headers=teacher_headers,
        )
        body = resp.get_json()
        # Latest attempt #3 had 70% on the standard (7/10)
        assert body['standards_breakdown'][0]['percentage'] == 70.0

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_attempt_mode_best_picks_highest_per_content(self, mock_sb_fn, client, teacher_headers):
        self._setup_three_attempts(mock_sb_fn)
        resp = client.get(
            '/api/teacher/class/cls-1/student/stu-1/report-card?attempt_mode=best',
            headers=teacher_headers,
        )
        body = resp.get_json()
        # Best attempt #2 had 90% on the standard (9/10)
        assert body['standards_breakdown'][0]['percentage'] == 90.0

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_attempt_mode_average_aggregates_attempts(self, mock_sb_fn, client, teacher_headers):
        self._setup_three_attempts(mock_sb_fn)
        resp = client.get(
            '/api/teacher/class/cls-1/student/stu-1/report-card?attempt_mode=average',
            headers=teacher_headers,
        )
        body = resp.get_json()
        # Average across 50/90/70 = 70.0
        assert body['standards_breakdown'][0]['percentage'] == 70.0

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_invalid_attempt_mode_falls_back_to_latest(self, mock_sb_fn, client, teacher_headers):
        self._setup_three_attempts(mock_sb_fn)
        resp = client.get(
            '/api/teacher/class/cls-1/student/stu-1/report-card?attempt_mode=garbage',
            headers=teacher_headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        # Should behave as 'latest'
        assert body['attempt_mode'] == 'latest'
        assert body['standards_breakdown'][0]['percentage'] == 70.0


class TestReportCardEdgeCases:
    """Malformed mastery, null submitted_at, etc."""

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_malformed_standards_mastery_skips_submission(self, mock_sb_fn, client, teacher_headers, caplog):
        # results.standards_mastery is a list (not dict) — should NOT 500
        import logging
        caplog.set_level(logging.WARNING, logger="backend.routes.student_portal_routes")
        subs = [
            {"id": "sub-good", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 1, "submitted_at": "2026-04-10T10:00:00Z", "percentage": 80,
             "results": {"standards_mastery": {"MA.6.AR.1.1": {"points_earned": 8, "points_possible": 10, "question_count": 2}},
                         "points_earned": 8, "points_possible": 10},
             "status": "graded"},
            {"id": "sub-bad", "student_id": "stu-1", "content_id": "ct-2",
             "attempt_number": 1, "submitted_at": "2026-04-12T10:00:00Z", "percentage": 60,
             "results": {"standards_mastery": ["malformed", "list"],  # WRONG TYPE
                         "points_earned": 6, "points_possible": 10},
             "status": "graded"},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [
                {'id': 'ct-1', 'title': 'Q1', 'content_type': 'assessment'},
                {'id': 'ct-2', 'title': 'Q2', 'content_type': 'assessment'},
            ],
            'student_submissions': subs,
        })
        resp = client.get('/api/teacher/class/cls-1/student/stu-1/report-card',
                          headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # Both submissions in trajectory (trajectory uses submitted_at + percentage,
        # not standards_mastery — so malformed mastery doesn't drop them here).
        assert {t['submission_id'] for t in body['trajectory']} == {'sub-good', 'sub-bad'}
        # Only sub-good's mastery contributes to breakdown — sub-bad's
        # malformed standards_mastery sanitized to empty.
        assert len(body['standards_breakdown']) == 1
        assert body['standards_breakdown'][0]['code'] == 'MA.6.AR.1.1'
        # WARNING was logged with the submission id
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any('malformed standards_mastery' in r.getMessage() and 'sub-bad' in r.getMessage()
                   for r in warnings), \
            "expected a WARNING log mentioning malformed standards_mastery and sub-bad"

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_latest_malformed_does_not_fall_back_to_older_mastery(self, mock_sb_fn, client, teacher_headers):
        """attempt_mode=latest must still pick the genuinely latest attempt
        even when its mastery is malformed (sanitized to empty), NOT silently
        revert to an older attempt's good mastery."""
        good_mastery = {"MA.6.AR.1.1": {"points_earned": 9, "points_possible": 10, "question_count": 2}}
        subs = [
            # Earlier attempt with GOOD mastery
            {"id": "sub-old", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 1, "submitted_at": "2026-04-10T10:00:00Z", "percentage": 90,
             "results": {"standards_mastery": good_mastery,
                         "points_earned": 9, "points_possible": 10},
             "status": "graded"},
            # LATEST attempt with malformed mastery
            {"id": "sub-latest", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 2, "submitted_at": "2026-04-15T10:00:00Z", "percentage": 30,
             "results": {"standards_mastery": "broken",  # WRONG TYPE
                         "points_earned": 3, "points_possible": 10},
             "status": "graded"},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [{'id': 'ct-1', 'title': 'Q', 'content_type': 'assessment'}],
            'student_submissions': subs,
        })
        resp = client.get(
            '/api/teacher/class/cls-1/student/stu-1/report-card?attempt_mode=latest',
            headers=teacher_headers,
        )
        assert resp.status_code == 200
        body = resp.get_json()
        # 'latest' selected sub-latest (attempt 2), whose mastery sanitized
        # to {}; therefore standards_breakdown is EMPTY — NOT showing the
        # older attempt's 90% mastery on MA.6.AR.1.1.
        assert body['standards_breakdown'] == []
        # Both submissions still appear in trajectory
        assert len(body['trajectory']) == 2

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_individual_malformed_standard_value_skipped(self, mock_sb_fn, client, teacher_headers, caplog):
        """A submission whose standards_mastery dict is well-formed at the
        outer level but has a non-dict value for one entry: that one entry
        is dropped, the rest of the dict is preserved."""
        import logging
        caplog.set_level(logging.WARNING, logger="backend.routes.student_portal_routes")
        mixed = {
            "MA.6.AR.1.1": {"points_earned": 8, "points_possible": 10, "question_count": 2},
            "MA.6.AR.2.1": "not-a-dict-broken",  # WRONG TYPE on this entry
        }
        subs = [{
            "id": "sub-mixed", "student_id": "stu-1", "content_id": "ct-1",
            "attempt_number": 1, "submitted_at": "2026-04-10T10:00:00Z", "percentage": 80,
            "results": {"standards_mastery": mixed, "points_earned": 8, "points_possible": 10},
            "status": "graded",
        }]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [{'id': 'ct-1', 'title': 'Q', 'content_type': 'assessment'}],
            'student_submissions': subs,
        })
        resp = client.get('/api/teacher/class/cls-1/student/stu-1/report-card',
                          headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # Only the well-formed standard appears
        codes = [s['code'] for s in body['standards_breakdown']]
        assert codes == ['MA.6.AR.1.1']
        # WARNING mentions the malformed entry's code
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any('MA.6.AR.2.1' in r.getMessage() for r in warnings), \
            "expected a WARNING mentioning the malformed entry's standard code"

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_null_submitted_at_sorted_to_end_of_trajectory(self, mock_sb_fn, client, teacher_headers):
        subs = [
            {"id": "sub-null", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 1, "submitted_at": None, "percentage": 50,
             "results": {"standards_mastery": {}, "points_earned": 5, "points_possible": 10},
             "status": "graded"},
            {"id": "sub-dated", "student_id": "stu-1", "content_id": "ct-1",
             "attempt_number": 2, "submitted_at": "2026-04-10T10:00:00Z", "percentage": 70,
             "results": {"standards_mastery": {}, "points_earned": 7, "points_possible": 10},
             "status": "graded"},
        ]
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'test-teacher-001'}],
            'class_students': [{'student_id': 'stu-1'}],
            'students': [{'id': 'stu-1', 'first_name': 'A', 'last_name': 'B'}],
            'published_content': [{'id': 'ct-1', 'title': 'Q', 'content_type': 'assessment'}],
            'student_submissions': subs,
        })
        resp = client.get('/api/teacher/class/cls-1/student/stu-1/report-card',
                          headers=teacher_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        # Null submitted_at must be LAST in trajectory
        assert [t['submission_id'] for t in body['trajectory']] == ['sub-dated', 'sub-null']

