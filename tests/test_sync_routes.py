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

    def test_validate_secret_uses_only_constant_time_compare(self):
        """_validate_secret must not contain any `==`/`!=` against the
        secret — only hmac.compare_digest. Prevents both the original
        timing bug and the 'length leak' refactor pitfall caught by
        Gemini-proxy plan review (2026-05-14)."""
        import inspect
        import ast
        from backend.routes.sync_routes import _validate_secret
        src = inspect.getsource(_validate_secret)
        assert "hmac.compare_digest" in src, (
            "_validate_secret must call hmac.compare_digest"
        )
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                for op in node.ops:
                    assert not isinstance(op, (ast.Eq, ast.NotEq)), (
                        f"_validate_secret contains a == or != compare at "
                        f"line {node.lineno}; use hmac.compare_digest only "
                        f"(2026-05-14 dimensional review S1)"
                    )

    def test_validate_secret_rejects_wrong_secret_with_correct_length(self):
        """Behavioral test: equal-length wrong secret must still be rejected.
        Catches a length-only check that would pass the AST test above."""
        app = _make_sync_app(sync_secret="abcdef12345")
        with app.test_client() as client:
            resp = client.post('/api/sync/periodic-roster',
                               headers={"Authorization": "Bearer xyzwvu67890"})
        assert resp.status_code == 401


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


# ----------------------------------------------------------------------
# Regression tests for _sync_one_teacher runtime (PR #214 — closes Codex
# post-sprint audit FAIL #7). The Clever path was crashing with
# 'NoneType has no attribute get' because _sync_classes_to_db returned
# nothing; the OneRoster path was crashing with 'tuple indices must be
# integers' because normalize_roster() returns a 4-tuple but the
# consumer indexed it as a dict.
# ----------------------------------------------------------------------


class TestSyncClassesToDbReturnsCounts:
    """PR #214: _sync_classes_to_db must return the counts dict from
    sync_roster_to_db so _sync_one_teacher can attribute counts to the
    audit-log line and the response payload."""

    def test_returns_counts_from_shared_sync(self):
        from backend.routes.clever_routes import _sync_classes_to_db

        counts = {"classes": 3, "students": 7, "enrollments": 12}
        with patch(
            'backend.routes.clever_routes._shared_sync_roster_to_db',
            return_value=counts,
        ):
            result = _sync_classes_to_db([], [], "teacher_x")

        assert result == counts


class TestSyncOneTeacherRuntime:
    """PR #214: _sync_one_teacher must not crash on either provider path."""

    def test_clever_path_returns_success_with_counts(self):
        from backend.routes.sync_routes import _sync_one_teacher

        # teacher_id must be clever:-prefixed (or in clever_links) for the
        # post-2026-05-14 tenancy filter to resolve a Clever ID. Section
        # must list this teacher as an owner for the filter to keep it.
        async def fake_clever_sync(token):
            return {
                'sections': [{'data': {'id': 's1', 'name': 'Algebra',
                                       'teachers': ['t1'],
                                       'students': ['st1']}}],
                'students': [{'data': {'id': 'st1', 'email': 'a@x.com'}}],
            }

        counts = {"classes": 1, "students": 1, "enrollments": 0}

        with patch('backend.clever.sync_roster', fake_clever_sync), \
             patch(
                 'backend.routes.clever_routes._sync_classes_to_db',
                 return_value=counts,
             ), \
             patch(
                 'backend.roster_sync.deactivate_missing_students',
                 return_value=0,
             ), \
             patch('backend.routes.sync_routes.audit_log'), \
             patch.dict('os.environ', {'CLEVER_DISTRICT_TOKEN': 'x'}):
            result = _sync_one_teacher({
                'teacher_id': 'clever:t1',
                'provider': 'clever',
                'config': {},
            })

        assert result['status'] == 'success'
        assert result['classes'] == 1
        assert result['students'] == 1
        assert result['provider'] == 'clever'

    def test_oneroster_path_returns_success_with_counts(self):
        from backend.routes.sync_routes import _sync_one_teacher

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def fetch_roster(self, **kwargs):
                return {
                    'classes': [],
                    'students': [],
                    'enrollments': [],
                    'demographics': [],
                }

        # normalize_roster returns a 4-tuple; sync_roster_to_db returns counts
        normalized_tuple = (
            [{'external_id': 'oneroster:c1', 'name': 'X', 'subject': 'M', 'grade_level': '7'}],
            [{'external_id': 'oneroster:s1', 'first_name': 'A', 'last_name': 'B', 'email': 'a@x.com'}],
            [{'class_external_id': 'oneroster:c1', 'student_external_id': 'oneroster:s1'}],
            [],
        )
        counts = {"classes": 1, "students": 1, "enrollments": 1}

        with patch(
                 'backend.oneroster.get_oneroster_config',
                 return_value={
                     'base_url': 'https://example.test',
                     'client_id': 'id',
                     'client_secret': 'secret',
                 },
             ), \
             patch('backend.oneroster.OneRosterClient', FakeClient), \
             patch(
                 'backend.oneroster.normalize_roster',
                 return_value=normalized_tuple,
             ), \
             patch(
                 'backend.roster_sync.sync_roster_to_db',
                 return_value=counts,
             ) as mock_sync, \
             patch(
                 'backend.roster_sync.deactivate_missing_students',
                 return_value=0,
             ), \
             patch('backend.routes.sync_routes.audit_log'):
            result = _sync_one_teacher({
                'teacher_id': 't1',
                'provider': 'oneroster',
                'config': {},
            })

        assert result['status'] == 'success'
        assert result['classes'] == 1
        assert result['students'] == 1
        assert result['provider'] == 'oneroster'

        # Verify enrollments were converted to tuples (not passed as dicts).
        # sync_roster_to_db iterates `for class_ext, student_ext in enrollments`
        # so dicts would unpack to keys "class_external_id"/"student_external_id"
        # instead of the actual IDs — silent data corruption.
        sync_args = mock_sync.call_args
        passed_enrollments = sync_args[0][2]  # 3rd positional arg
        assert len(passed_enrollments) == 1
        assert isinstance(passed_enrollments[0], tuple), (
            f"enrollments must be tuples, got {type(passed_enrollments[0]).__name__}"
        )
        assert passed_enrollments[0] == ('oneroster:c1', 'oneroster:s1')


class TestSyncOneTeacherPIIRedaction:
    """PR #214: ClassLink login audit_log detail string must not contain
    raw email — was logged as `f"ClassLink SSO login: {email}"`,
    fixed to wrap with redact_email()."""

    def test_classlink_login_audit_redacts_email(self):
        # Static-source check that the audit detail uses redact_email().
        # Behavioral test would require booting the full ClassLink callback
        # mock chain; this pin keeps the redaction wrapper from drifting.
        from pathlib import Path

        src = Path(__file__).resolve().parent.parent / "backend/routes/classlink_routes.py"
        text = src.read_text()
        assert 'redact_email(email)' in text, (
            "ClassLink login audit must wrap email with redact_email()"
        )
        assert 'f"ClassLink SSO login: {email}"' not in text, (
            "Bare email in ClassLink SSO login audit detail string"
        )


class TestCleverArchiveLogsHashStudentId:
    """PR #214: clever.py archive/restore log lines must hash the student
    id, not log it raw — was `logger.info(..., sid)`, fixed to use
    sha256(sid)[:8]."""

    def test_archive_and_restore_logs_hash_student_id(self):
        from pathlib import Path

        src = Path(__file__).resolve().parent.parent / "backend/clever.py"
        text = src.read_text()

        # Both call sites must hash the sid — bare `, sid)` after either
        # log message is the leaking pattern.
        assert 'Restored previously archived Clever student: %s",\n                    hashlib.sha256(str(sid)' in text \
               or 'Restored previously archived Clever student: %s", hashlib.sha256(str(sid)' in text, (
            "Restored-archive log must hash sid"
        )
        assert 'Archived Clever student no longer in roster: %s",\n                    hashlib.sha256(str(sid)' in text \
               or 'Archived Clever student no longer in roster: %s", hashlib.sha256(str(sid)' in text, (
            "Archived-out log must hash sid"
        )


class TestAuditLocalFileFormatContract:
    """PR #214: audit.py local-file format change must remain compatible
    with the reader at backend/app.py:_get_audit_logs (PR #214 round-2
    Codex review found the previous format `timestamp | teacher=X | user
    | action | details` would cause the existing reader to mis-parse
    `user` as `teacher=X`. Fixed by appending teacher_id LAST instead.)
    """

    def test_audit_log_line_parses_with_existing_reader(self, tmp_path, monkeypatch):
        # Redirect AUDIT_LOG_FILE to a temp path for both writer and reader
        log_path = str(tmp_path / "audit.log")
        monkeypatch.setattr("backend.utils.audit.AUDIT_LOG_FILE", log_path)
        monkeypatch.setattr("backend.app.AUDIT_LOG_FILE", log_path)

        from backend.utils.audit import audit_log
        from backend.app import get_audit_logs

        audit_log(
            action="PERIODIC_SYNC",
            details="provider=clever classes=5 students=12",
            user="system",
            teacher_id="t-abc-123",
        )

        logs = get_audit_logs(limit=10)
        assert len(logs) == 1
        entry = logs[0]
        # The first 4 fields MUST be readable in their original semantic
        # positions (existing 4-field reader contract).
        assert entry['user'] == 'system'
        assert entry['action'] == 'PERIODIC_SYNC'
        assert entry['details'] == 'provider=clever classes=5 students=12'
        # The new 5th field carries teacher_id (added in PR #214).
        assert entry.get('teacher_id') == 't-abc-123'



def _make_async_returning(value):
    """Build an async function that returns the given value, for mocking
    async functions like backend.clever.sync_roster."""
    async def _f(*args, **kwargs):
        return value
    return _f


class TestPeriodicSyncTenancy:
    """Regression for the periodic-sync district-roster leak.
    Same bug shape as the manual /api/clever/sync-roster path (Task 3
    in 2026-05-14-security-quintet plan) but ships daily via
    .github/workflows/roster-sync.yml. Sourced from Gemini-proxy plan
    review."""

    def test_periodic_sync_filters_to_teachers_own_sections(self):
        from backend.routes.sync_routes import _sync_one_teacher

        # Teacher T owns S1 (students A, B); other teacher owns S2 (C, D)
        roster = {
            "sections": [
                {"data": {"id": "S1", "teachers": ["T"],
                          "students": ["A", "B"], "name": "Pd 1"}},
                {"data": {"id": "S2", "teachers": ["OTHER"],
                          "students": ["C", "D"], "name": "Pd 2"}},
            ],
            "students": [
                {"data": {"id": x, "name": x}} for x in ["A", "B", "C", "D"]
            ],
        }

        captured = {"sections": None, "students": None}
        def fake_sync_classes(sections, students, teacher_id):
            captured["sections"] = sections
            captured["students"] = students
            return {"classes": 1, "students": 2, "enrollments": 2}

        teacher = {
            "teacher_id": "clever:T",  # prefix form — Clever ID = T
            "provider": "clever",
            "config": {"district_token": "tok"},
        }

        with patch('backend.clever.sync_roster',
                   new=_make_async_returning(roster)), \
             patch('backend.routes.clever_routes._sync_classes_to_db',
                   side_effect=fake_sync_classes), \
             patch('backend.roster_sync.deactivate_missing_students',
                   return_value=0), \
             patch('backend.routes.sync_routes.audit_log'):
            result = _sync_one_teacher(teacher)

        assert result["status"] != "skipped", f"Sync was skipped: {result}"
        assert captured["sections"] is not None, "sections were never passed"
        section_ids = [s.get("data", s).get("id") for s in captured["sections"]]
        student_ids = sorted(s.get("data", s).get("id") for s in captured["students"])
        assert section_ids == ["S1"], (
            f"Periodic sync passed cross-teacher sections to _sync_classes_to_db. "
            f"Got: {section_ids}; expected [S1] (T's only own section)."
        )
        assert student_ids == ["A", "B"], (
            f"District-roster leak in periodic sync. Got students: "
            f"{student_ids}; expected [A, B]."
        )
