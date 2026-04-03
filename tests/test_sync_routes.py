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
