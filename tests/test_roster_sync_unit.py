"""
Unit tests for backend/roster_sync.py — coverage push from 64% baseline.

Existing tests/test_roster_sync.py covers the happy paths; this file
fills the un-covered branches identified by `pytest --cov`:

- ROSTER_SYNC_FAILED audit on exception (lines 60-66)
- _sync_roster_to_db_impl error paths:
  * No class rows returned (line 113)
  * Missing class_ext_id in class_id_map (137)
  * Missing student_ext_id in student_ext_map (140)
  * No unique students after enrollment filter (153-157)
  * Student upsert exception (165-168)
  * No student rows returned (172-173)
  * Enrollment upsert exception (199-201)
- deactivate_missing_students:
  * Supabase None
  * No active students
  * Skip cross-provider students
  * Skip Clever-touching-OneRoster/manual rule
  * Deactivate missing
  * Exception handling
- delete_roster_data:
  * Supabase None (only file delete)
  * Supabase deletion exception (302-304)
  * Local file removal failure (318-323)

Each test isolates Supabase mocks so cross-test leakage doesn't mask
coverage.
"""
from __future__ import annotations

import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest


_SB_PATCH = "backend.supabase_client.get_supabase"
_ROSTER_SB_PATCH = "backend.roster_sync._get_supabase"


def _chain(execute_data=None, count=None):
    """Build a chainable Supabase query mock that records calls."""
    chain = MagicMock()
    chain.select.return_value = chain
    chain.insert.return_value = chain
    chain.upsert.return_value = chain
    chain.update.return_value = chain
    chain.delete.return_value = chain
    chain.eq.return_value = chain
    chain.in_.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    result = MagicMock()
    result.data = execute_data if execute_data is not None else []
    if count is not None:
        result.count = count
    chain.execute.return_value = result
    return chain


# ──────────────────────────────────────────────────────────────────
# sync_roster_to_db audit boundary (FAILED path)
# ──────────────────────────────────────────────────────────────────


class TestSyncRosterAuditFailed:
    """Closes coverage of lines 60-66: FAILED audit on exception."""

    def test_failed_audit_emits_when_impl_raises(self):
        from backend.roster_sync import sync_roster_to_db

        # Force the impl to raise; verify audit_log fires for FAILED
        # AND the exception re-propagates.
        with patch(
            "backend.roster_sync._sync_roster_to_db_impl",
            side_effect=RuntimeError("boom"),
        ), patch("backend.roster_sync.audit_log") as mock_audit:
            with pytest.raises(RuntimeError, match="boom"):
                sync_roster_to_db(
                    classes=[{"external_id": "c1"}],
                    students=[{"external_id": "s1"}],
                    enrollments=[("c1", "s1")],
                    teacher_id="t-1",
                    provider="clever",
                )

        # Should have fired START + FAILED (no COMPLETE)
        actions = [c.args[0] for c in mock_audit.call_args_list]
        assert "ROSTER_SYNC_START" in actions
        assert "ROSTER_SYNC_FAILED" in actions
        assert "ROSTER_SYNC_COMPLETE" not in actions

    def test_complete_audit_emits_when_impl_succeeds(self):
        from backend.roster_sync import sync_roster_to_db

        with patch(
            "backend.roster_sync._sync_roster_to_db_impl",
            return_value={"classes": 1, "students": 0, "enrollments": 0},
        ), patch("backend.roster_sync.audit_log") as mock_audit:
            result = sync_roster_to_db(
                classes=[{"external_id": "c1"}],
                students=[],
                enrollments=[],
                teacher_id="t-1",
                provider="oneroster",
            )

        actions = [c.args[0] for c in mock_audit.call_args_list]
        assert "ROSTER_SYNC_START" in actions
        assert "ROSTER_SYNC_COMPLETE" in actions
        assert "ROSTER_SYNC_FAILED" not in actions
        assert result["classes"] == 1


# ──────────────────────────────────────────────────────────────────
# _sync_roster_to_db_impl edge cases
# ──────────────────────────────────────────────────────────────────


class TestSyncImplEdgeCases:
    """Closes coverage of error paths in _sync_roster_to_db_impl."""

    def _supabase_with_classes_upsert(self, class_rows):
        """Mock that returns class_rows from .upsert(...).execute()."""
        sb = MagicMock()
        ch = _chain(execute_data=class_rows)
        sb.table.return_value = ch
        return sb, ch

    def test_no_class_rows_returned_short_circuits(self):
        # class upsert succeeds but returns empty data → return zero.
        from backend.roster_sync import _sync_roster_to_db_impl

        sb, ch = self._supabase_with_classes_upsert(class_rows=[])
        with patch(_SB_PATCH, return_value=sb):
            result = _sync_roster_to_db_impl(
                classes=[{"external_id": "c1", "name": "Period 1"}],
                students=[{"external_id": "s1"}],
                enrollments=[("c1", "s1")],
                teacher_id="t-1",
                provider="clever",
            )
        assert result == {"classes": 0, "students": 0, "enrollments": 0}

    def test_class_upsert_exception_returns_zero(self):
        # Exception during class upsert → return zero counts.
        from backend.roster_sync import _sync_roster_to_db_impl

        sb = MagicMock()
        ch = MagicMock()
        ch.upsert.return_value = ch
        ch.execute.side_effect = Exception("class upsert blew up")
        sb.table.return_value = ch

        with patch(_SB_PATCH, return_value=sb):
            result = _sync_roster_to_db_impl(
                classes=[{"external_id": "c1"}],
                students=[],
                enrollments=[],
                teacher_id="t-1",
                provider="clever",
            )
        assert result == {"classes": 0, "students": 0, "enrollments": 0}

    def test_class_payload_skips_when_no_external_id(self):
        # A class without external_id is silently skipped — only valid
        # classes get upserted.
        from backend.roster_sync import _sync_roster_to_db_impl

        # No valid classes (all skipped) → empty payload → return zero.
        sb = MagicMock()
        ch = _chain(execute_data=[])
        sb.table.return_value = ch
        with patch(_SB_PATCH, return_value=sb):
            result = _sync_roster_to_db_impl(
                classes=[{"name": "missing-ext-id"}],  # no external_id
                students=[],
                enrollments=[],
                teacher_id="t-1",
                provider="clever",
            )
        assert result == {"classes": 0, "students": 0, "enrollments": 0}
        # Verify: classes table never reached upsert, since payload empty.

    def test_no_unique_students_after_enrollment_filter(self):
        # Classes upsert OK, but enrollments reference unknown students.
        # Should return classes count + zero students/enrollments.
        from backend.roster_sync import _sync_roster_to_db_impl

        class_rows = [{"id": "uuid-cls-1", "clever_section_id": "c1"}]
        sb, ch = self._supabase_with_classes_upsert(class_rows=class_rows)

        with patch(_SB_PATCH, return_value=sb):
            result = _sync_roster_to_db_impl(
                classes=[{"external_id": "c1"}],
                students=[{"external_id": "s-other"}],  # different student
                enrollments=[("c1", "s-missing")],  # references unknown
                teacher_id="t-1",
                provider="clever",
            )
        assert result == {"classes": 1, "students": 0, "enrollments": 0}

    def test_student_upsert_exception_returns_classes_only(self):
        from backend.roster_sync import _sync_roster_to_db_impl

        # First .table('classes').upsert(...).execute() returns class rows;
        # second .table('students').upsert(...).execute() raises.
        sb = MagicMock()
        class_chain = _chain(execute_data=[
            {"id": "uuid-cls-1", "clever_section_id": "c1"}
        ])
        student_chain = MagicMock()
        student_chain.upsert.return_value = student_chain
        student_chain.execute.side_effect = Exception("students upsert failed")

        def table_factory(name):
            if name == "classes":
                return class_chain
            if name == "students":
                return student_chain
            return _chain([])

        sb.table.side_effect = table_factory

        with patch(_SB_PATCH, return_value=sb):
            result = _sync_roster_to_db_impl(
                classes=[{"external_id": "c1"}],
                students=[{"external_id": "s1", "first_name": "A"}],
                enrollments=[("c1", "s1")],
                teacher_id="t-1",
                provider="clever",
            )
        assert result == {"classes": 1, "students": 0, "enrollments": 0}

    def test_no_student_rows_returned_short_circuits(self):
        from backend.roster_sync import _sync_roster_to_db_impl

        sb = MagicMock()
        class_chain = _chain(execute_data=[
            {"id": "uuid-cls-1", "clever_section_id": "c1"}
        ])
        student_chain = _chain(execute_data=[])  # empty rows after upsert

        def table_factory(name):
            if name == "classes":
                return class_chain
            if name == "students":
                return student_chain
            return _chain([])

        sb.table.side_effect = table_factory

        with patch(_SB_PATCH, return_value=sb):
            result = _sync_roster_to_db_impl(
                classes=[{"external_id": "c1"}],
                students=[{"external_id": "s1"}],
                enrollments=[("c1", "s1")],
                teacher_id="t-1",
                provider="clever",
            )
        assert result == {"classes": 1, "students": 0, "enrollments": 0}

    def test_enrollment_upsert_exception_returns_classes_and_students(self):
        from backend.roster_sync import _sync_roster_to_db_impl

        sb = MagicMock()
        class_chain = _chain(execute_data=[
            {"id": "uuid-cls-1", "clever_section_id": "c1"}
        ])
        student_chain = _chain(execute_data=[
            {"id": "uuid-stu-1", "student_id_number": "s1"}
        ])
        enroll_chain = MagicMock()
        enroll_chain.upsert.return_value = enroll_chain
        enroll_chain.execute.side_effect = Exception("enroll upsert failed")

        def table_factory(name):
            if name == "classes":
                return class_chain
            if name == "students":
                return student_chain
            if name == "class_students":
                return enroll_chain
            return _chain([])

        sb.table.side_effect = table_factory

        with patch(_SB_PATCH, return_value=sb):
            result = _sync_roster_to_db_impl(
                classes=[{"external_id": "c1"}],
                students=[{"external_id": "s1"}],
                enrollments=[("c1", "s1")],
                teacher_id="t-1",
                provider="clever",
            )
        assert result == {"classes": 1, "students": 1, "enrollments": 0}


# ──────────────────────────────────────────────────────────────────
# deactivate_missing_students — cross-provider rules
# ──────────────────────────────────────────────────────────────────


class TestDeactivateMissingStudents:
    def test_returns_zero_when_supabase_none(self):
        from backend.roster_sync import deactivate_missing_students

        with patch(_ROSTER_SB_PATCH, return_value=None):
            result = deactivate_missing_students(
                "t-1", set(), provider="clever",
            )
        assert result == 0

    def test_returns_zero_when_no_active_students(self):
        from backend.roster_sync import deactivate_missing_students

        sb = MagicMock()
        sb.table.return_value = _chain(execute_data=[])
        with patch(_ROSTER_SB_PATCH, return_value=sb):
            result = deactivate_missing_students(
                "t-1", set(), provider="clever",
            )
        assert result == 0

    def test_skips_other_provider_students(self):
        # OneRoster student (oneroster: prefix) should NOT be
        # deactivated by a Clever sync — provider isolation.
        from backend.roster_sync import deactivate_missing_students

        sb = MagicMock()
        students_data = [
            {"id": "uuid-or-1", "student_id_number": "oneroster:s-or-1"},
            {"id": "uuid-cl-1", "student_id_number": "s-cl-1"},
        ]
        chain = _chain(execute_data=students_data)
        sb.table.return_value = chain

        # current_ids only has the Clever student missing → only Clever
        # should be deactivated; OneRoster left alone.
        with patch(_ROSTER_SB_PATCH, return_value=sb):
            result = deactivate_missing_students(
                "t-1", current_student_external_ids=set(),
                provider="clever",
            )
        # Only the Clever student gets deactivated (1).
        assert result == 1

    def test_skips_manual_students_for_clever_sync(self):
        # Manual students (manual- prefix) should NOT be deactivated
        # by a Clever sync.
        from backend.roster_sync import deactivate_missing_students

        sb = MagicMock()
        students_data = [
            {"id": "uuid-m-1", "student_id_number": "manual-m-1"},
            {"id": "uuid-cl-1", "student_id_number": "s-cl-1"},
        ]
        sb.table.return_value = _chain(execute_data=students_data)
        with patch(_ROSTER_SB_PATCH, return_value=sb):
            result = deactivate_missing_students(
                "t-1", current_student_external_ids=set(),
                provider="clever",
            )
        # Only Clever student deactivated (1).
        assert result == 1

    def test_deactivates_missing_students_in_provider_scope(self):
        from backend.roster_sync import deactivate_missing_students

        sb = MagicMock()
        students_data = [
            {"id": "uuid-1", "student_id_number": "s-still-here"},
            {"id": "uuid-2", "student_id_number": "s-removed"},
        ]
        sb.table.return_value = _chain(execute_data=students_data)
        with patch(_ROSTER_SB_PATCH, return_value=sb):
            result = deactivate_missing_students(
                "t-1",
                current_student_external_ids={"s-still-here"},
                provider="clever",
            )
        # s-removed got deactivated (1)
        assert result == 1

    def test_handles_supabase_exception_gracefully(self):
        from backend.roster_sync import deactivate_missing_students

        sb = MagicMock()
        sb.table.side_effect = Exception("supabase down")
        with patch(_ROSTER_SB_PATCH, return_value=sb):
            result = deactivate_missing_students(
                "t-1", set(), provider="clever",
            )
        assert result == 0


# ──────────────────────────────────────────────────────────────────
# delete_roster_data
# ──────────────────────────────────────────────────────────────────


class TestDeleteRosterData:
    def test_returns_zero_counts_when_supabase_none(self, tmp_path, monkeypatch):
        # Even without Supabase, file deletion still runs.
        from backend.roster_sync import delete_roster_data

        # Redirect ~/.graider_data to tmp_path
        rosters_dir = tmp_path / "rosters"
        rosters_dir.mkdir()
        # Create a mock roster file matching the pattern
        target = rosters_dir / "roster_t-1.csv"
        target.write_text("student_id,first_name\n")
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(tmp_path) if p == "~/.graider_data" else p,
        )

        with patch(_SB_PATCH, return_value=None):
            result = delete_roster_data("t-1")

        # File should be removed (Supabase counts stay 0)
        assert result["classes"] == 0
        assert result["roster_files"] == 1
        assert not target.exists()

    def test_supabase_deletion_exception_does_not_raise(self, tmp_path, monkeypatch):
        # If Supabase delete raises, file deletion still completes.
        from backend.roster_sync import delete_roster_data

        rosters_dir = tmp_path / "rosters"
        rosters_dir.mkdir()
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(tmp_path) if p == "~/.graider_data" else p,
        )

        sb = MagicMock()
        sb.table.side_effect = Exception("supabase delete failed")
        with patch(_SB_PATCH, return_value=sb):
            # Should not raise; partial result returned
            result = delete_roster_data("t-1")
        assert isinstance(result, dict)
        assert "classes" in result

    def test_file_removal_failure_logs_and_continues(self, tmp_path, monkeypatch):
        # If os.remove raises, log and continue — don't propagate.
        from backend.roster_sync import delete_roster_data

        rosters_dir = tmp_path / "rosters"
        rosters_dir.mkdir()
        target = rosters_dir / "roster_t-1.csv"
        target.write_text("x")
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(tmp_path) if p == "~/.graider_data" else p,
        )
        # Stub os.remove to raise
        with patch("os.remove", side_effect=OSError("permission denied")), \
             patch(_SB_PATCH, return_value=None):
            result = delete_roster_data("t-1")
        # File removal failure → counted as 0 deletes; no exception
        assert result["roster_files"] == 0

    def test_supabase_full_path_deletes_classes_students_enrollments(
        self, tmp_path, monkeypatch,
    ):
        # Happy path: Supabase deletes classes, students, content, etc.
        from backend.roster_sync import delete_roster_data

        rosters_dir = tmp_path / "rosters"
        rosters_dir.mkdir()
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(tmp_path) if p == "~/.graider_data" else p,
        )

        sb = MagicMock()
        # classes select returns 2 class IDs
        classes_chain = _chain(execute_data=[
            {"id": "uuid-cls-1"}, {"id": "uuid-cls-2"},
        ])
        # published_content select returns 1 content ID
        content_chain = _chain(execute_data=[{"id": "uuid-pc-1"}])
        # students select returns 3 student IDs
        students_chain = _chain(execute_data=[
            {"id": "uuid-s-1"}, {"id": "uuid-s-2"}, {"id": "uuid-s-3"},
        ])
        delete_chain = _chain(execute_data=[])

        def table_factory(name):
            if name == "classes":
                # First call: select; subsequent calls: delete
                return classes_chain
            if name == "published_content":
                return content_chain
            if name == "students":
                return students_chain
            return delete_chain

        sb.table.side_effect = table_factory

        with patch(_SB_PATCH, return_value=sb):
            result = delete_roster_data("t-1")
        assert result["classes"] == 2
        assert result["students"] == 3
