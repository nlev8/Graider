"""Tests for periodic roster sync — deactivation + webhook endpoint."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timezone


def _mock_supabase_students(active_students):
    """Create a mock Supabase that returns active students for a teacher."""
    mock_sb = MagicMock()
    mock_table = MagicMock()
    mock_result = MagicMock()
    mock_result.data = active_students
    for method in ('select', 'eq', 'neq', 'ilike', 'like', 'order',
                   'limit', 'offset', 'gt', 'gte', 'lt', 'lte', 'in_'):
        getattr(mock_table, method).return_value = mock_table
    mock_table.execute.return_value = mock_result
    mock_sb.table.return_value = mock_table
    return mock_sb


class TestDeactivateMissingStudents:
    def test_deactivates_students_not_in_current_roster(self):
        from backend.roster_sync import deactivate_missing_students
        db_students = [
            {"id": "uuid-1", "student_id_number": "clever-id-1", "is_active": True},
            {"id": "uuid-2", "student_id_number": "clever-id-2", "is_active": True},
            {"id": "uuid-3", "student_id_number": "clever-id-3", "is_active": True},
        ]
        current_ids = {"clever-id-1", "clever-id-3"}
        mock_sb = _mock_supabase_students(db_students)
        with patch('backend.roster_sync._get_supabase', return_value=mock_sb):
            count = deactivate_missing_students("teacher-1", current_ids, "clever")
        assert count == 1

    def test_does_not_deactivate_manual_students(self):
        from backend.roster_sync import deactivate_missing_students
        db_students = [
            {"id": "uuid-1", "student_id_number": "clever-id-1", "is_active": True},
            {"id": "uuid-2", "student_id_number": "manual-abc123", "is_active": True},
        ]
        current_ids = {"clever-id-1"}
        mock_sb = _mock_supabase_students(db_students)
        with patch('backend.roster_sync._get_supabase', return_value=mock_sb):
            count = deactivate_missing_students("teacher-1", current_ids, "clever")
        assert count == 0

    def test_does_not_deactivate_oneroster_students_during_clever_sync(self):
        from backend.roster_sync import deactivate_missing_students
        db_students = [
            {"id": "uuid-1", "student_id_number": "clever-id-1", "is_active": True},
            {"id": "uuid-2", "student_id_number": "oneroster:src-123", "is_active": True},
        ]
        current_ids = {"clever-id-1"}
        mock_sb = _mock_supabase_students(db_students)
        with patch('backend.roster_sync._get_supabase', return_value=mock_sb):
            count = deactivate_missing_students("teacher-1", current_ids, "clever")
        assert count == 0

    def test_deactivates_oneroster_students_during_oneroster_sync(self):
        from backend.roster_sync import deactivate_missing_students
        db_students = [
            {"id": "uuid-1", "student_id_number": "oneroster:src-1", "is_active": True},
            {"id": "uuid-2", "student_id_number": "oneroster:src-2", "is_active": True},
            {"id": "uuid-3", "student_id_number": "manual-xyz", "is_active": True},
        ]
        current_ids = {"oneroster:src-1"}
        mock_sb = _mock_supabase_students(db_students)
        with patch('backend.roster_sync._get_supabase', return_value=mock_sb):
            count = deactivate_missing_students("teacher-1", current_ids, "oneroster")
        assert count == 1

    def test_returns_zero_when_all_present(self):
        from backend.roster_sync import deactivate_missing_students
        db_students = [{"id": "uuid-1", "student_id_number": "clever-id-1", "is_active": True}]
        current_ids = {"clever-id-1"}
        mock_sb = _mock_supabase_students(db_students)
        with patch('backend.roster_sync._get_supabase', return_value=mock_sb):
            count = deactivate_missing_students("teacher-1", current_ids, "clever")
        assert count == 0

    def test_returns_zero_when_supabase_unavailable(self):
        from backend.roster_sync import deactivate_missing_students
        with patch('backend.roster_sync._get_supabase', return_value=None):
            count = deactivate_missing_students("teacher-1", {"id-1"}, "clever")
        assert count == 0


# ---------------------------------------------------------------------------
# Webhook endpoint tests
# ---------------------------------------------------------------------------

from flask import Flask


def _make_sync_app(sync_secret="test-secret-123"):
    """Create a minimal Flask app with sync routes for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test'

    os.environ['PERIODIC_SYNC_SECRET'] = sync_secret

    from backend.extensions import limiter
    limiter.init_app(app)

    from backend.routes.sync_routes import sync_bp
    app.register_blueprint(sync_bp)
    return app


class TestSyncWebhookAuth:
    def test_rejects_missing_auth(self):
        """Request without Authorization header should return 401."""
        app = _make_sync_app()
        with app.test_client() as client:
            resp = client.post('/api/sync/periodic-roster')
        assert resp.status_code == 401

    def test_rejects_wrong_secret(self):
        """Request with wrong secret should return 401."""
        app = _make_sync_app()
        with app.test_client() as client:
            resp = client.post('/api/sync/periodic-roster',
                               headers={"Authorization": "Bearer wrong-secret"})
        assert resp.status_code == 401

    def test_rejects_missing_env_var(self):
        """Should return 401 when PERIODIC_SYNC_SECRET is not set."""
        app = _make_sync_app()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('PERIODIC_SYNC_SECRET', None)
            with app.test_client() as client:
                resp = client.post('/api/sync/periodic-roster',
                                   headers={"Authorization": "Bearer test-secret-123"})
        assert resp.status_code == 401

    def test_accepts_valid_secret(self):
        """Request with correct secret should not return 401."""
        app = _make_sync_app()
        with app.test_client() as client:
            with patch('backend.routes.sync_routes._discover_teachers', return_value=[]):
                resp = client.post('/api/sync/periodic-roster',
                                   headers={"Authorization": "Bearer test-secret-123"})
        assert resp.status_code == 200


class TestSyncWebhookOrchestration:
    def test_returns_summary_with_zero_teachers(self):
        """When no teachers found, return success with zero counts."""
        app = _make_sync_app()
        with app.test_client() as client:
            with patch('backend.routes.sync_routes._discover_teachers', return_value=[]):
                resp = client.post('/api/sync/periodic-roster',
                                   headers={"Authorization": "Bearer test-secret-123"})
        data = resp.get_json()
        assert data["synced"] == 0
        assert data["failed"] == 0
        assert data["has_failures"] is False

    def test_reports_teacher_sync_failure(self):
        """When a teacher sync fails, has_failures should be True."""
        app = _make_sync_app()
        teachers = [{"teacher_id": "t1", "provider": "clever", "config": {}}]
        with app.test_client() as client:
            with patch('backend.routes.sync_routes._discover_teachers', return_value=teachers), \
                 patch('backend.routes.sync_routes._sync_one_teacher',
                       return_value={"teacher_id": "t1", "provider": "clever",
                                     "status": "failed", "error": "Connection timeout",
                                     "duration_s": 5.0}), \
                 patch('backend.routes.sync_routes._save_cursor'):
                resp = client.post('/api/sync/periodic-roster',
                                   headers={"Authorization": "Bearer test-secret-123"})
        data = resp.get_json()
        assert data["has_failures"] is True
        assert data["failed"] == 1

    def test_isolates_teacher_failures(self):
        """One teacher failing should not stop other teachers from syncing."""
        app = _make_sync_app()
        teachers = [
            {"teacher_id": "t1", "provider": "clever", "config": {}},
            {"teacher_id": "t2", "provider": "clever", "config": {}},
        ]
        results = [
            {"teacher_id": "t1", "status": "failed", "provider": "clever",
             "error": "timeout", "duration_s": 5.0},
            {"teacher_id": "t2", "status": "success", "provider": "clever",
             "classes": 3, "students": 20, "deactivated": 0, "duration_s": 2.0},
        ]
        with app.test_client() as client:
            with patch('backend.routes.sync_routes._discover_teachers', return_value=teachers), \
                 patch('backend.routes.sync_routes._sync_one_teacher', side_effect=results), \
                 patch('backend.routes.sync_routes._save_cursor'):
                resp = client.post('/api/sync/periodic-roster',
                                   headers={"Authorization": "Bearer test-secret-123"})
        data = resp.get_json()
        assert data["synced"] == 1
        assert data["failed"] == 1
        assert data["total_teachers"] == 2


# ---------------------------------------------------------------------------
# Teacher discovery tests
# ---------------------------------------------------------------------------

def _mock_supabase_for_discovery(config_rows, session_rows, cursor_data=None):
    """Mock Supabase for teacher discovery tests.

    Test inputs are kept stable across the 2026-05-02 schema-audit fix
    that switched _discover_teachers from a single bad query
    (student_sessions.teacher_id, which doesn't exist as a column) to a
    two-step hop: student_sessions.student_id → students.teacher_id.

    `session_rows` is still expressed as `[{"teacher_id": ...}]` for
    test readability ("teachers who had a recent session"). Internally
    we synthesize:
      - student_sessions rows with `student_id = "stu_{teacher_id}"`
      - students rows mapping each synthetic student_id back to teacher_id
    so the new two-step query resolves to the same teacher_id set.
    """
    mock_sb = MagicMock()

    synthetic_session_rows = [
        {"student_id": f"stu_{r['teacher_id']}"} for r in session_rows
    ]
    synthetic_student_rows = [
        {"teacher_id": r["teacher_id"]} for r in session_rows
    ]

    def table_router(name):
        mock_table = MagicMock()
        result = MagicMock()
        if name == 'teacher_data':
            result.data = config_rows
        elif name == 'student_sessions':
            result.data = synthetic_session_rows
        elif name == 'students':
            result.data = synthetic_student_rows
        else:
            result.data = []
        for method in ('select', 'eq', 'neq', 'gt', 'gte', 'lt', 'lte',
                       'ilike', 'like', 'order', 'limit', 'offset', 'in_'):
            getattr(mock_table, method).return_value = mock_table
        mock_table.execute.return_value = result
        return mock_table

    mock_sb.table = table_router
    return mock_sb


class TestDiscoverTeachers:
    def test_finds_teachers_with_sis_config_and_activity(self):
        """Should return teachers that have SIS config + recent session activity."""
        from backend.routes.sync_routes import _discover_teachers

        config_rows = [
            {"teacher_id": "t1", "data": {"provider": "clever"}, "updated_at": "2026-01-01T00:00:00"},
            {"teacher_id": "t2", "data": {"provider": "oneroster"}, "updated_at": "2026-01-01T00:00:00"},
        ]
        session_rows = [{"teacher_id": "t1"}, {"teacher_id": "t2"}]

        with patch('backend.routes.sync_routes.get_supabase') as mock_get, \
             patch('backend.routes.sync_routes.storage_load', return_value=None):
            mock_get.return_value = _mock_supabase_for_discovery(config_rows, session_rows)
            teachers = _discover_teachers()

        assert len(teachers) == 2
        assert teachers[0]["teacher_id"] == "t1"
        assert teachers[0]["provider"] == "clever"

    def test_filters_out_inactive_teachers(self):
        """Teachers with SIS config but no recent activity should be excluded."""
        from backend.routes.sync_routes import _discover_teachers

        config_rows = [
            {"teacher_id": "t1", "data": {"provider": "clever"}, "updated_at": "2026-01-01T00:00:00"},
            {"teacher_id": "t2", "data": {"provider": "oneroster"}, "updated_at": "2026-01-01T00:00:00"},
        ]
        session_rows = [{"teacher_id": "t1"}]  # t2 has no recent sessions

        with patch('backend.routes.sync_routes.get_supabase') as mock_get, \
             patch('backend.routes.sync_routes.storage_load', return_value=None):
            mock_get.return_value = _mock_supabase_for_discovery(config_rows, session_rows)
            teachers = _discover_teachers()

        assert len(teachers) == 1
        assert teachers[0]["teacher_id"] == "t1"

    def test_includes_recently_configured_without_sessions(self):
        """Teachers whose SIS config was updated recently should be included even without sessions."""
        from backend.routes.sync_routes import _discover_teachers
        from datetime import datetime, timezone

        recent = datetime.now(tz=timezone.utc).isoformat()
        config_rows = [
            {"teacher_id": "t1", "data": {"provider": "clever"}, "updated_at": recent},
        ]
        session_rows = []  # No student sessions at all

        with patch('backend.routes.sync_routes.get_supabase') as mock_get, \
             patch('backend.routes.sync_routes.storage_load', return_value=None):
            mock_get.return_value = _mock_supabase_for_discovery(config_rows, session_rows)
            teachers = _discover_teachers()

        assert len(teachers) == 1

    def test_caps_at_50_teachers(self):
        """Should never return more than 50 teachers per run."""
        from backend.routes.sync_routes import _discover_teachers

        config_rows = [
            {"teacher_id": "t" + str(i).zfill(3), "data": {"provider": "clever"}, "updated_at": "2026-01-01T00:00:00"}
            for i in range(80)
        ]
        session_rows = [{"teacher_id": "t" + str(i).zfill(3)} for i in range(80)]

        with patch('backend.routes.sync_routes.get_supabase') as mock_get, \
             patch('backend.routes.sync_routes.storage_load', return_value=None):
            mock_get.return_value = _mock_supabase_for_discovery(config_rows, session_rows)
            teachers = _discover_teachers()

        assert len(teachers) == 50

    def test_cursor_skips_already_processed(self):
        """Cursor should skip teachers already processed in previous runs."""
        from backend.routes.sync_routes import _discover_teachers

        config_rows = [
            {"teacher_id": "t1", "data": {"provider": "clever"}, "updated_at": "2026-01-01T00:00:00"},
            {"teacher_id": "t2", "data": {"provider": "clever"}, "updated_at": "2026-01-01T00:00:00"},
            {"teacher_id": "t3", "data": {"provider": "clever"}, "updated_at": "2026-01-01T00:00:00"},
        ]
        session_rows = [{"teacher_id": "t1"}, {"teacher_id": "t2"}, {"teacher_id": "t3"}]
        cursor = {"last_teacher_id": "t1"}  # Already processed t1

        with patch('backend.routes.sync_routes.get_supabase') as mock_get, \
             patch('backend.routes.sync_routes.storage_load', return_value=cursor):
            mock_get.return_value = _mock_supabase_for_discovery(config_rows, session_rows)
            teachers = _discover_teachers()

        teacher_ids = [t["teacher_id"] for t in teachers]
        assert "t1" not in teacher_ids
        assert "t2" in teacher_ids
        assert "t3" in teacher_ids

    def test_cursor_wraps_around(self):
        """When cursor is past the last teacher, should wrap to beginning."""
        from backend.routes.sync_routes import _discover_teachers

        config_rows = [
            {"teacher_id": "t1", "data": {"provider": "clever"}, "updated_at": "2026-01-01T00:00:00"},
            {"teacher_id": "t2", "data": {"provider": "clever"}, "updated_at": "2026-01-01T00:00:00"},
        ]
        session_rows = [{"teacher_id": "t1"}, {"teacher_id": "t2"}]
        cursor = {"last_teacher_id": "t9"}  # Past all teachers

        with patch('backend.routes.sync_routes.get_supabase') as mock_get, \
             patch('backend.routes.sync_routes.storage_load', return_value=cursor):
            mock_get.return_value = _mock_supabase_for_discovery(config_rows, session_rows)
            teachers = _discover_teachers()

        assert len(teachers) == 2  # Wrapped around to beginning

    def test_returns_empty_when_no_supabase(self):
        """Should return empty list when Supabase is not configured."""
        from backend.routes.sync_routes import _discover_teachers

        with patch('backend.routes.sync_routes.get_supabase', return_value=None):
            teachers = _discover_teachers()

        assert teachers == []
