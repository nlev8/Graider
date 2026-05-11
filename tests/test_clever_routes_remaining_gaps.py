"""Gap-fill tests for backend/routes/clever_routes.py.

Audit MAJOR #4 sprint follow-up to PR #332. Companion to existing
`tests/test_clever_routes_*.py`. Targets a subset of missing LOC:

* `_create_clever_student_session` outer-except + sentry (241-244)
* `_background_roster_sync` happy path with contacts persist (260-262)
* `_background_roster_sync` outer-except + sentry (265-267)

Deferred (require Flask test client + complex session/OAuth state
mocking — better covered by integration tests):

* OAuth callback user_fetch_failed redirect (line 332)
* OAuth callback threading.Thread roster sync trigger (421-426)

Per dual-rate-limit precedent: test-only PR merging on green CI.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


MODULE = "backend.routes.clever_routes"


# ──────────────────────────────────────────────────────────────────
# _create_clever_student_session exception path
# ──────────────────────────────────────────────────────────────────


class TestCreateCleverStudentSessionException:
    def test_inner_supabase_exception_returns_none(self):
        # Force a Supabase call WITHIN the try block to raise.
        # The function checks `sb = _get_supabase_safe()` first, then enters
        # try/except. The raise must happen inside the try (line 182+).
        from backend.routes.clever_routes import (
            _create_clever_student_session,
        )

        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.execute.side_effect = RuntimeError("query failed")

        with patch(f"{MODULE}._get_supabase_safe", return_value=sb), \
             patch(f"{MODULE}.sentry_sdk.capture_exception") as mock_sentry:
            result = _create_clever_student_session(
                "clever-uuid-1", "alice@example.com",
            )
        assert result is None
        mock_sentry.assert_called()

    def test_supabase_unconfigured_returns_none(self):
        # _get_supabase_safe returns None → early return None (NOT the
        # outer-except path, but a sibling early-exit branch)
        from backend.routes.clever_routes import (
            _create_clever_student_session,
        )

        with patch(f"{MODULE}._get_supabase_safe", return_value=None):
            result = _create_clever_student_session(
                "clever-uuid-1", "alice@example.com",
            )
        assert result is None


# ──────────────────────────────────────────────────────────────────
# _background_roster_sync happy + exception
# ──────────────────────────────────────────────────────────────────


class TestBackgroundRosterSync:
    def test_full_pipeline_with_contacts(self):
        from backend.routes.clever_routes import _background_roster_sync

        roster = {
            "students": [{"data": {"id": "s1"}}],
            "sections": [{"data": {"id": "sec1"}}],
            "contacts": [{"data": {"id": "c1"}}],
        }

        with patch(f"{MODULE}.sync_roster",
                   return_value=roster), \
             patch(f"{MODULE}._run_async",
                   side_effect=lambda c: roster), \
             patch(f"{MODULE}.persist_roster_as_csv") as mock_persist_r, \
             patch(f"{MODULE}.persist_sections_as_periods") as mock_persist_s, \
             patch(f"{MODULE}._sync_classes_to_db") as mock_sync, \
             patch(f"{MODULE}.extract_parent_contacts",
                   return_value={"s1": {"parent_emails": ["m@e.com"]}}), \
             patch(f"{MODULE}.persist_parent_contacts") as mock_persist_pc:
            _background_roster_sync("token", "teach-1")

        # All persist functions called
        mock_persist_r.assert_called_once()
        mock_persist_s.assert_called_once()
        mock_persist_pc.assert_called_once()
        mock_sync.assert_called_once()

    def test_outer_exception_swallowed_with_sentry(self):
        from backend.routes.clever_routes import _background_roster_sync

        # Patch sync_roster too so production's eager
        # `sync_roster(district_token)` call returns a plain value
        # instead of an unawaited coroutine (which mocked _run_async
        # would ignore → RuntimeWarning leak).
        with patch(f"{MODULE}.sync_roster", return_value={}), \
             patch(f"{MODULE}._run_async",
                   side_effect=RuntimeError("network down")), \
             patch(f"{MODULE}.sentry_sdk.capture_exception") as mock_sentry:
            # Should not raise
            _background_roster_sync("token", "teach-1")

        mock_sentry.assert_called()

    def test_no_students_skips_persist(self):
        from backend.routes.clever_routes import _background_roster_sync

        # Patch sync_roster too: production calls sync_roster(token)
        # eagerly, returning a coroutine; mocked _run_async would
        # accept and ignore it, leaking an unawaited coroutine.
        empty_roster = {"students": [], "sections": [], "contacts": []}
        with patch(f"{MODULE}.sync_roster", return_value=empty_roster), \
             patch(f"{MODULE}._run_async",
                   return_value=empty_roster), \
             patch(f"{MODULE}.persist_roster_as_csv") as mock_persist_r, \
             patch(f"{MODULE}.persist_sections_as_periods") as mock_persist_s, \
             patch(f"{MODULE}.persist_parent_contacts") as mock_persist_pc:
            _background_roster_sync("token", "teach-1")

        mock_persist_r.assert_not_called()
        mock_persist_s.assert_not_called()
        mock_persist_pc.assert_not_called()

    def test_contacts_but_no_students_skips_parent_persist(self):
        from backend.routes.clever_routes import _background_roster_sync

        # Contacts present but no students → parent contacts not persisted
        # (sync_roster patched to avoid unawaited-coroutine leak)
        roster = {"students": [], "sections": [],
                  "contacts": [{"data": {"id": "c1"}}]}
        with patch(f"{MODULE}.sync_roster", return_value=roster), \
             patch(f"{MODULE}._run_async", return_value=roster), \
             patch(f"{MODULE}.persist_parent_contacts") as mock_persist_pc:
            _background_roster_sync("token", "teach-1")

        mock_persist_pc.assert_not_called()

    def test_extract_parent_contacts_empty_skips_persist(self):
        from backend.routes.clever_routes import _background_roster_sync

        # Students + contacts present but extract returns empty dict
        # (sync_roster patched to avoid unawaited-coroutine leak)
        roster = {"students": [{"data": {"id": "s1"}}],
                  "sections": [],
                  "contacts": [{"data": {"id": "c1"}}]}
        with patch(f"{MODULE}.sync_roster", return_value=roster), \
             patch(f"{MODULE}._run_async", return_value=roster), \
             patch(f"{MODULE}.persist_roster_as_csv"), \
             patch(f"{MODULE}.extract_parent_contacts",
                   return_value={}), \
             patch(f"{MODULE}.persist_parent_contacts") as mock_persist_pc:
            _background_roster_sync("token", "teach-1")

        mock_persist_pc.assert_not_called()
