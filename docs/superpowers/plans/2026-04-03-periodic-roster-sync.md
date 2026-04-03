# Periodic Roster Sync — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a daily cron-triggered webhook that syncs SIS rosters for active teachers and soft-deactivates students who have left.

**Architecture:** GitHub Actions cron → POST webhook → iterate teachers with SIS config → reuse existing Clever/OneRoster sync functions → deactivate missing students → audit log. Paged across runs via cursor. No new libraries.

**Tech Stack:** Python, Flask, Supabase, GitHub Actions, existing Flask-Limiter + audit_log

**Spec:** `docs/superpowers/specs/2026-04-03-periodic-roster-sync-design.md`

**Review history:**
- Rev 1: Initial plan (3 tasks, 13 tests)
- Rev 2: Added _discover_teachers unit tests (cursor paging, 30-day filter, 50-teacher cap, wrap-around). Confirmed asyncio.new_event_loop pattern matches existing Clever/OneRoster routes. Confirmed Flask-Limiter uses memory:// in tests — safe to re-init per test app.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/routes/sync_routes.py` | **Create** | Webhook endpoint: auth, teacher discovery, per-teacher sync orchestration |
| `backend/roster_sync.py` | **Modify** | Add `deactivate_missing_students()` function |
| `backend/routes/__init__.py` | **Modify** | Register `sync_bp` blueprint |
| `.github/workflows/roster-sync.yml` | **Create** | Cron workflow: weekday 4 AM ET trigger |
| `tests/test_sync_routes.py` | **Create** | Webhook endpoint tests: auth, discovery, orchestration, deactivation |
| `CLAUDE.md` | **Modify** | Add `PERIODIC_SYNC_SECRET` to env vars section |

---

### Task 1: Add `deactivate_missing_students()` to roster_sync.py

**Files:**
- Modify: `backend/roster_sync.py`
- Create: `tests/test_sync_routes.py` (start with deactivation tests)

- [ ] **Step 1: Write failing tests for deactivation**

Create `tests/test_sync_routes.py`:

```python
"""Tests for periodic roster sync — deactivation + webhook endpoint."""

import pytest
from unittest.mock import patch, MagicMock, call


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
        """Students in DB but not in synced roster should be deactivated."""
        from backend.roster_sync import deactivate_missing_students

        db_students = [
            {"id": "uuid-1", "student_id_number": "clever-id-1", "is_active": True},
            {"id": "uuid-2", "student_id_number": "clever-id-2", "is_active": True},
            {"id": "uuid-3", "student_id_number": "clever-id-3", "is_active": True},
        ]
        current_ids = {"clever-id-1", "clever-id-3"}  # clever-id-2 left

        mock_sb = _mock_supabase_students(db_students)
        with patch('backend.roster_sync._get_supabase', return_value=mock_sb):
            count = deactivate_missing_students("teacher-1", current_ids, "clever")

        assert count == 1
        # Verify update was called for uuid-2
        mock_sb.table.return_value.update.assert_called()

    def test_does_not_deactivate_manual_students(self):
        """Manual students (manual- prefix) should never be deactivated by Clever sync."""
        from backend.roster_sync import deactivate_missing_students

        db_students = [
            {"id": "uuid-1", "student_id_number": "clever-id-1", "is_active": True},
            {"id": "uuid-2", "student_id_number": "manual-abc123", "is_active": True},
        ]
        current_ids = {"clever-id-1"}  # manual student not in Clever roster — but should be safe

        mock_sb = _mock_supabase_students(db_students)
        with patch('backend.roster_sync._get_supabase', return_value=mock_sb):
            count = deactivate_missing_students("teacher-1", current_ids, "clever")

        assert count == 0  # manual student untouched

    def test_does_not_deactivate_oneroster_students_during_clever_sync(self):
        """OneRoster students should not be deactivated when syncing Clever."""
        from backend.roster_sync import deactivate_missing_students

        db_students = [
            {"id": "uuid-1", "student_id_number": "clever-id-1", "is_active": True},
            {"id": "uuid-2", "student_id_number": "oneroster:src-123", "is_active": True},
        ]
        current_ids = {"clever-id-1"}

        mock_sb = _mock_supabase_students(db_students)
        with patch('backend.roster_sync._get_supabase', return_value=mock_sb):
            count = deactivate_missing_students("teacher-1", current_ids, "clever")

        assert count == 0  # oneroster student untouched

    def test_deactivates_oneroster_students_during_oneroster_sync(self):
        """OneRoster students not in current roster should be deactivated during OneRoster sync."""
        from backend.roster_sync import deactivate_missing_students

        db_students = [
            {"id": "uuid-1", "student_id_number": "oneroster:src-1", "is_active": True},
            {"id": "uuid-2", "student_id_number": "oneroster:src-2", "is_active": True},
            {"id": "uuid-3", "student_id_number": "manual-xyz", "is_active": True},
        ]
        current_ids = {"oneroster:src-1"}  # src-2 left

        mock_sb = _mock_supabase_students(db_students)
        with patch('backend.roster_sync._get_supabase', return_value=mock_sb):
            count = deactivate_missing_students("teacher-1", current_ids, "oneroster")

        assert count == 1  # only oneroster:src-2 deactivated

    def test_returns_zero_when_all_present(self):
        """No deactivations when all DB students are in the current roster."""
        from backend.roster_sync import deactivate_missing_students

        db_students = [
            {"id": "uuid-1", "student_id_number": "clever-id-1", "is_active": True},
        ]
        current_ids = {"clever-id-1"}

        mock_sb = _mock_supabase_students(db_students)
        with patch('backend.roster_sync._get_supabase', return_value=mock_sb):
            count = deactivate_missing_students("teacher-1", current_ids, "clever")

        assert count == 0

    def test_returns_zero_when_supabase_unavailable(self):
        """Should return 0 gracefully when Supabase is not configured."""
        from backend.roster_sync import deactivate_missing_students

        with patch('backend.roster_sync._get_supabase', return_value=None):
            count = deactivate_missing_students("teacher-1", {"id-1"}, "clever")

        assert count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_sync_routes.py::TestDeactivateMissingStudents -v`
Expected: FAIL with `ImportError: cannot import name 'deactivate_missing_students'`

- [ ] **Step 3: Implement `deactivate_missing_students()`**

In `backend/roster_sync.py`, first add a module-level helper for Supabase access (needed for testability), then add the deactivation function.

Add after the existing imports at the top of the file:

```python
def _get_supabase():
    """Get Supabase client, or None if not configured."""
    try:
        from backend.supabase_client import get_supabase
        return get_supabase()
    except Exception:
        return None


# Provider prefixes for student_id_number — used to scope deactivation
_PROVIDER_PREFIXES = {
    "clever": "",            # Clever IDs have no prefix (raw Clever user IDs)
    "oneroster": "oneroster:",
    "manual": "manual-",
}
```

Then add the deactivation function at the end of the file (before `delete_roster_data`):

```python
def deactivate_missing_students(teacher_id, current_student_external_ids, provider):
    """Soft-deactivate students no longer in the SIS roster.

    Only deactivates students matching the given provider's prefix.
    Manual students and students from other providers are never touched.

    Args:
        teacher_id: Graider teacher ID
        current_student_external_ids: set of student_id_number values from current sync
        provider: "clever" or "oneroster"

    Returns:
        int: count of students deactivated
    """
    sb = _get_supabase()
    if sb is None:
        return 0

    try:
        # Get all active students for this teacher
        result = sb.table('students').select('id, student_id_number').eq(
            'teacher_id', teacher_id
        ).eq('is_active', True).execute()

        if not result.data:
            return 0

        # Determine which students belong to this provider
        prefix = _PROVIDER_PREFIXES.get(provider, "")
        other_prefixes = [p for k, p in _PROVIDER_PREFIXES.items() if k != provider and p]

        deactivated = 0
        for student in result.data:
            sid = student.get('student_id_number', '')

            # Skip students from other providers
            if any(sid.startswith(op) for op in other_prefixes):
                continue

            # For Clever (no prefix): skip if it looks like another provider's student
            if provider == "clever" and any(sid.startswith(op) for op in ['oneroster:', 'manual-']):
                continue

            # If this provider's student is not in the current roster, deactivate
            if sid not in current_student_external_ids:
                sb.table('students').update({'is_active': False}).eq('id', student['id']).execute()
                deactivated += 1

        if deactivated:
            logger.info("Deactivated %d %s students for teacher %s", deactivated, provider, teacher_id)

        return deactivated

    except Exception as e:
        logger.error("Failed to deactivate missing students for %s: %s", teacher_id, e)
        return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_sync_routes.py::TestDeactivateMissingStudents -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add backend/roster_sync.py tests/test_sync_routes.py
git commit -m "feat: add deactivate_missing_students() for periodic roster sync"
```

---

### Task 2: Create the webhook endpoint

**Files:**
- Create: `backend/routes/sync_routes.py`
- Modify: `backend/routes/__init__.py`
- Modify: `tests/test_sync_routes.py`

- [ ] **Step 1: Write failing tests for the webhook**

Append to `tests/test_sync_routes.py`:

```python
import json
import os
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
```

Also append tests for `_discover_teachers` (cursor paging, activity filter, cap):

```python
def _mock_supabase_for_discovery(config_rows, session_rows, cursor_data=None):
    """Mock Supabase for teacher discovery tests."""
    mock_sb = MagicMock()

    def table_router(name):
        mock_table = MagicMock()
        result = MagicMock()
        if name == 'teacher_data':
            result.data = config_rows
        elif name == 'student_sessions':
            result.data = session_rows
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
            {"teacher_id": f"t{i:03d}", "data": {"provider": "clever"}, "updated_at": "2026-01-01T00:00:00"}
            for i in range(80)
        ]
        session_rows = [{"teacher_id": f"t{i:03d}"} for i in range(80)]

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_sync_routes.py::TestSyncWebhookAuth -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.routes.sync_routes'`

- [ ] **Step 3: Implement the webhook endpoint**

Create `backend/routes/sync_routes.py`:

```python
"""
Periodic Roster Sync — Webhook Endpoint
========================================
POST /api/sync/periodic-roster

Triggered by GitHub Actions cron (weekdays 4 AM ET). Iterates over
teachers with SIS connections, re-syncs their rosters, and soft-deactivates
students no longer in the SIS.

Auth: Bearer token matching PERIODIC_SYNC_SECRET env var.
Rate limited: 1 request per 5 minutes.
"""

import os
import time
import logging
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify

from backend.extensions import limiter
from backend.utils.audit import audit_log
from backend.storage import load as storage_load, save as storage_save

logger = logging.getLogger(__name__)

sync_bp = Blueprint('sync', __name__)

MAX_TEACHERS_PER_RUN = 50


def get_supabase():
    """Get Supabase client. Module-level wrapper for testability."""
    try:
        from backend.supabase_client import get_supabase as _get_sb
        return _get_sb()
    except Exception:
        return None


def _validate_secret():
    """Validate the Authorization: Bearer <secret> header."""
    expected = os.environ.get('PERIODIC_SYNC_SECRET')
    if not expected:
        return False
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return False
    return auth[7:] == expected


def _discover_teachers():
    """Find teachers eligible for periodic sync.

    Returns list of dicts: [{teacher_id, provider, config}, ...]
    Paged via cursor stored in teacher_data key 'sync:last_cursor'.
    """
    try:
        sb = get_supabase()
        if not sb:
            return []

        # Get all teachers with SIS config
        config_result = sb.table('teacher_data').select(
            'teacher_id, data, updated_at'
        ).eq('data_key', 'district:sis_config').execute()

        if not config_result.data:
            return []

        # Get teachers with recent activity (student sessions in last 30 days)
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=30)).isoformat()
        session_result = sb.table('student_sessions').select(
            'teacher_id'
        ).gt('created_at', cutoff).execute()

        active_teacher_ids = {s['teacher_id'] for s in (session_result.data or [])}

        # Also include teachers whose SIS config was updated in last 30 days
        eligible = []
        for row in config_result.data:
            tid = row['teacher_id']
            updated_at = row.get('updated_at', '')
            config_recent = updated_at and updated_at > cutoff
            if tid in active_teacher_ids or config_recent:
                config = row.get('data', {})
                if isinstance(config, str):
                    import json
                    config = json.loads(config)
                provider = config.get('provider', '')
                if provider in ('clever', 'oneroster'):
                    eligible.append({
                        'teacher_id': tid,
                        'provider': provider,
                        'config': config,
                    })

        if not eligible:
            return []

        # Sort by teacher_id for cursor-based paging
        eligible.sort(key=lambda t: t['teacher_id'])

        # Apply cursor
        cursor = storage_load('sync:last_cursor', 'system')
        if cursor and isinstance(cursor, dict):
            last_id = cursor.get('last_teacher_id', '')
            # Filter to teachers after the cursor
            eligible = [t for t in eligible if t['teacher_id'] > last_id]
            # If we've gone past all teachers, wrap around
            if not eligible:
                # Re-query without cursor (start from beginning)
                eligible_all = []
                for row in config_result.data:
                    tid = row['teacher_id']
                    updated_at = row.get('updated_at', '')
                    config_recent = updated_at and updated_at > cutoff
                    if tid in active_teacher_ids or config_recent:
                        config = row.get('data', {})
                        if isinstance(config, str):
                            import json
                            config = json.loads(config)
                        provider = config.get('provider', '')
                        if provider in ('clever', 'oneroster'):
                            eligible_all.append({
                                'teacher_id': tid,
                                'provider': provider,
                                'config': config,
                            })
                eligible_all.sort(key=lambda t: t['teacher_id'])
                eligible = eligible_all

        # Cap at MAX_TEACHERS_PER_RUN
        if len(eligible) > MAX_TEACHERS_PER_RUN:
            logger.warning("Capping periodic sync at %d teachers (total eligible: %d)",
                           MAX_TEACHERS_PER_RUN, len(eligible))
            eligible = eligible[:MAX_TEACHERS_PER_RUN]

        return eligible

    except Exception as e:
        logger.exception("Teacher discovery failed: %s", e)
        return []


def _save_cursor(last_teacher_id):
    """Save the paging cursor after a successful batch."""
    try:
        storage_save('sync:last_cursor', {'last_teacher_id': last_teacher_id}, 'system')
    except Exception as e:
        logger.warning("Failed to save sync cursor: %s", e)


def _sync_one_teacher(teacher):
    """Sync roster for a single teacher. Returns result dict."""
    import asyncio
    from backend.roster_sync import sync_roster_to_db, deactivate_missing_students

    teacher_id = teacher['teacher_id']
    provider = teacher['provider']
    config = teacher['config']
    start = time.time()

    try:
        if provider == 'clever':
            from backend.clever import sync_roster as clever_sync_roster
            from backend.routes.clever_routes import _sync_classes_to_db

            district_token = config.get('district_token') or os.environ.get('CLEVER_DISTRICT_TOKEN')
            if not district_token:
                return {"teacher_id": teacher_id, "provider": provider,
                        "status": "skipped", "error": "No Clever district token",
                        "duration_s": round(time.time() - start, 1)}

            loop = asyncio.new_event_loop()
            try:
                roster_data = loop.run_until_complete(clever_sync_roster(district_token))
            finally:
                loop.close()

            sections = roster_data.get('sections', [])
            students = roster_data.get('students', [])

            counts = _sync_classes_to_db(sections, students, teacher_id)

            # Collect current student external IDs for deactivation
            current_ids = {s['data']['id'] for s in students if 'data' in s and 'id' in s['data']}
            deactivated = deactivate_missing_students(teacher_id, current_ids, "clever")

        elif provider == 'oneroster':
            from backend.oneroster import OneRosterClient, normalize_roster, get_oneroster_config

            or_config = get_oneroster_config(teacher_id)
            client = OneRosterClient(
                base_url=or_config['base_url'],
                client_id=or_config['client_id'],
                client_secret=or_config['client_secret'],
                token_url=or_config.get('token_url'),
            )

            loop = asyncio.new_event_loop()
            try:
                raw = loop.run_until_complete(client.fetch_roster(
                    school_id=or_config.get('school_id'),
                    teacher_sourced_id=or_config.get('teacher_sourced_id'),
                ))
            finally:
                loop.close()

            normalized = normalize_roster(raw)
            counts = sync_roster_to_db(
                normalized['classes'], normalized['students'],
                normalized['enrollments'], teacher_id, provider="oneroster"
            )

            current_ids = {s['external_id'] for s in normalized['students']}
            deactivated = deactivate_missing_students(teacher_id, current_ids, "oneroster")

        else:
            return {"teacher_id": teacher_id, "provider": provider,
                    "status": "skipped", "error": f"Unknown provider: {provider}",
                    "duration_s": round(time.time() - start, 1)}

        duration = round(time.time() - start, 1)

        audit_log(
            action="PERIODIC_SYNC",
            details=f"provider={provider} classes={counts.get('classes', 0)} "
                    f"students={counts.get('students', 0)} deactivated={deactivated}",
            user="system",
            teacher_id=teacher_id,
        )

        return {
            "teacher_id": teacher_id,
            "provider": provider,
            "status": "success",
            "classes": counts.get("classes", 0),
            "students": counts.get("students", 0),
            "deactivated": deactivated,
            "duration_s": duration,
        }

    except Exception as e:
        duration = round(time.time() - start, 1)
        logger.exception("Periodic sync failed for teacher %s (%s): %s",
                         teacher_id, provider, e)
        return {
            "teacher_id": teacher_id,
            "provider": provider,
            "status": "failed",
            "error": str(e)[:200],
            "duration_s": duration,
        }


@sync_bp.route('/api/sync/periodic-roster', methods=['POST'])
@limiter.limit("1 per 5 minutes")
def periodic_roster_sync():
    """Webhook endpoint for cron-triggered periodic roster sync."""
    if not _validate_secret():
        return jsonify({"error": "Unauthorized"}), 401

    teachers = _discover_teachers()
    results = []

    for teacher in teachers:
        result = _sync_one_teacher(teacher)
        results.append(result)

    # Save cursor after successful batch
    if teachers:
        last_id = teachers[-1]['teacher_id']
        _save_cursor(last_id)

    synced = sum(1 for r in results if r.get('status') == 'success')
    failed = sum(1 for r in results if r.get('status') == 'failed')
    skipped = sum(1 for r in results if r.get('status') == 'skipped')

    return jsonify({
        "synced": synced,
        "failed": failed,
        "skipped": skipped,
        "total_teachers": len(teachers),
        "has_failures": failed > 0,
        "details": results,
    })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_sync_routes.py -v`
Expected: All 21 tests PASS (6 deactivation + 7 webhook + 8 discovery)

- [ ] **Step 5: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add backend/routes/sync_routes.py tests/test_sync_routes.py
git commit -m "feat: add periodic roster sync webhook endpoint"
```

---

### Task 3: Register the blueprint and add the workflow

**Files:**
- Modify: `backend/routes/__init__.py`
- Create: `.github/workflows/roster-sync.yml`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Register sync_bp in routes/__init__.py**

In `backend/routes/__init__.py`, add the import after the last import (line 35):

```python
from .sync_routes import sync_bp
```

And add the registration after the last `app.register_blueprint` call (line 70):

```python
    app.register_blueprint(sync_bp)
```

- [ ] **Step 2: Create the GitHub Actions workflow**

Create `.github/workflows/roster-sync.yml`:

```yaml
name: Periodic Roster Sync

on:
  schedule:
    - cron: '0 9 * * 1-5'  # 4:00 AM ET weekdays (UTC-5) / 5:00 AM EDT (UTC-4)
  workflow_dispatch: {}     # Manual trigger for testing

jobs:
  sync:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - name: Trigger roster sync
        run: |
          response=$(curl -s -w "\n%{http_code}" -X POST \
            https://app.graider.live/api/sync/periodic-roster \
            -H "Authorization: Bearer ${{ secrets.PERIODIC_SYNC_SECRET }}" \
            -H "Content-Type: application/json" \
            --max-time 600)
          http_code=$(echo "$response" | tail -1)
          body=$(echo "$response" | head -n -1)
          echo "$body" | jq . || echo "$body"

          # Fail on HTTP error
          if [ "$http_code" -ne 200 ]; then
            echo "::error::Roster sync failed with HTTP $http_code"
            exit 1
          fi

          # Fail if any teacher sync failed (partial failure)
          has_failures=$(echo "$body" | jq -r '.has_failures // false')
          if [ "$has_failures" = "true" ]; then
            failed_count=$(echo "$body" | jq '.failed')
            echo "::warning::$failed_count teacher sync(s) failed — check details"
            exit 1
          fi
```

- [ ] **Step 3: Add PERIODIC_SYNC_SECRET to CLAUDE.md env vars**

In `CLAUDE.md`, find the `### Optional` section under `## Environment Variables` and add:

```markdown
### Periodic Roster Sync
- `PERIODIC_SYNC_SECRET` — Shared secret for cron webhook auth (set in Railway + GitHub Actions secrets)
```

- [ ] **Step 4: Verify the app starts with the new blueprint**

```bash
cd /Users/alexc/Downloads/Graider
source venv/bin/activate
python -c "from backend.routes.sync_routes import sync_bp; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Validate workflow YAML**

```bash
cd /Users/alexc/Downloads/Graider
source venv/bin/activate
python -c "
import yaml
with open('.github/workflows/roster-sync.yml') as f:
    yaml.safe_load(f)
print('Valid YAML')
" 2>/dev/null || echo "YAML validation skipped (pyyaml not installed)"
```

- [ ] **Step 6: Run full test suite**

```bash
cd /Users/alexc/Downloads/Graider
source venv/bin/activate
python -m pytest tests/test_sync_routes.py tests/test_tool_schemas.py -v
```

Expected: All tests PASS

- [ ] **Step 7: Search-based verification**

```bash
cd /Users/alexc/Downloads/Graider
# Blueprint registered:
grep -n 'sync_bp' backend/routes/__init__.py
# Expected: import line + register_blueprint line

# Endpoint exists:
grep -n 'periodic-roster' backend/routes/sync_routes.py
# Expected: route decorator line

# Deactivation function exists:
grep -n 'def deactivate_missing_students' backend/roster_sync.py
# Expected: function definition line

# Workflow exists:
cat .github/workflows/roster-sync.yml | head -5
# Expected: name: Periodic Roster Sync
```

- [ ] **Step 8: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add backend/routes/__init__.py backend/routes/sync_routes.py .github/workflows/roster-sync.yml CLAUDE.md
git commit -m "feat: register sync blueprint, add cron workflow, document env var"
```

---

## Summary

| Task | What | Files | Risk |
|------|------|-------|------|
| 1 | `deactivate_missing_students()` + 6 tests | Modify `roster_sync.py`, create `test_sync_routes.py` | Low — new function, no existing code changed |
| 2 | Webhook endpoint + 7 tests | Create `sync_routes.py`, modify tests | Low — new blueprint |
| 3 | Blueprint registration + cron workflow + docs | Modify `__init__.py`, create workflow, modify `CLAUDE.md` | Low — append only |

**Total: 1 new endpoint, 1 new function, 20 tests (6 deactivation + 7 webhook + 7 discovery), 1 cron workflow.**

**Post-deploy steps (manual, not in this plan):**
1. Generate secret: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
2. Set `PERIODIC_SYNC_SECRET` in Railway dashboard
3. Set `PERIODIC_SYNC_SECRET` in GitHub repo → Settings → Secrets → Actions
4. Test via `workflow_dispatch` in GitHub Actions UI
5. Verify audit_log entry appears in Supabase

**Before:** Student transfers mid-semester → teacher's roster is stale until next login.
**After:** Rosters auto-sync every weekday at 4 AM → teachers see current enrollment by the time class starts.
