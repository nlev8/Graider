"""
Tests for _create_clever_student_session() in clever_routes.py.

Covers:
- Student found by Clever ID + enrolled → returns token + student + class info
- Student not found by Clever ID or email → returns None
- Supabase not configured (returns None) → returns None gracefully

Zero network calls — all Supabase interactions are mocked.
"""
from unittest.mock import MagicMock, patch

import pytest

from backend.routes.clever_routes import _create_clever_student_session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sb(student_row=None, enroll_rows=None, insert_ok=True):
    """Build a mock Supabase client wired for _create_clever_student_session."""

    sb = MagicMock()

    # students table
    students_q = MagicMock()
    students_q.select.return_value = students_q
    students_q.eq.return_value = students_q
    students_q.execute.return_value = MagicMock(data=[student_row] if student_row else [])
    sb.table.return_value = students_q

    def _table(name):
        if name == "students":
            return students_q
        if name == "class_students":
            enroll_q = MagicMock()
            enroll_q.select.return_value = enroll_q
            enroll_q.eq.return_value = enroll_q
            enroll_q.limit.return_value = enroll_q
            enroll_q.execute.return_value = MagicMock(data=enroll_rows or [])
            return enroll_q
        if name == "student_sessions":
            sess_q = MagicMock()
            sess_q.insert.return_value = sess_q
            sess_q.execute.return_value = MagicMock(data=[{"id": "sess-001"}])
            return sess_q
        return MagicMock()

    sb.table.side_effect = _table
    return sb


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCreateCleverStudentSession:

    def test_found_by_clever_id_returns_token_and_info(self):
        """Happy path: student found by clever_id, enrolled in a class."""
        student_row = {
            "id": "db-stu-001",
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane@school.edu",
            "student_id_number": "clever-abc",
            "period": "3",
        }
        enroll_rows = [
            {
                "class_id": "cls-001",
                "classes": {
                    "id": "cls-001",
                    "name": "Math 9",
                    "subject": "math",
                },
            }
        ]
        sb = _make_sb(student_row=student_row, enroll_rows=enroll_rows)

        with patch("backend.routes.clever_routes._get_supabase_safe", return_value=sb):
            result = _create_clever_student_session("clever-abc", "jane@school.edu")

        assert result is not None
        assert "token" in result
        assert len(result["token"]) > 20  # raw urlsafe token
        assert result["student"]["first_name"] == "Jane"
        assert result["student"]["last_name"] == "Doe"
        assert result["student"]["email"] == "jane@school.edu"
        assert result["class"]["name"] == "Math 9"

    def test_not_found_by_clever_id_or_email_returns_none(self):
        """Student not in DB at all → returns None."""
        # students table returns no rows for either lookup
        sb = MagicMock()

        def _table(name):
            q = MagicMock()
            q.select.return_value = q
            q.eq.return_value = q
            q.execute.return_value = MagicMock(data=[])
            return q

        sb.table.side_effect = _table

        with patch("backend.routes.clever_routes._get_supabase_safe", return_value=sb):
            result = _create_clever_student_session("unknown-clever-id", "nobody@school.edu")

        assert result is None

    def test_supabase_not_configured_returns_none(self):
        """If Supabase is not configured, return None gracefully."""
        with patch("backend.routes.clever_routes._get_supabase_safe", return_value=None):
            result = _create_clever_student_session("clever-xyz", "student@school.edu")

        assert result is None

    def test_student_found_but_not_enrolled_returns_none(self):
        """Student exists in DB but has no class enrollment → returns None."""
        student_row = {
            "id": "db-stu-002",
            "first_name": "Bob",
            "last_name": "Smith",
            "email": "bob@school.edu",
            "student_id_number": "clever-bbb",
            "period": "",
        }
        # No enrollment rows
        sb = _make_sb(student_row=student_row, enroll_rows=[])

        with patch("backend.routes.clever_routes._get_supabase_safe", return_value=sb):
            result = _create_clever_student_session("clever-bbb", "bob@school.edu")

        assert result is None

    def test_no_email_fallback_when_clever_id_not_found(self):
        """VB12 (SSO-parity): if the clever_id lookup misses, we FAIL CLOSED —
        we do NOT fall back to a global, unscoped email match (which could land
        the student in a different teacher's class on a shared/reused email).
        The student-table query must therefore never be re-run filtered by
        email, and no session is minted."""
        student_row = {
            "id": "db-stu-003",
            "first_name": "Alice",
            "last_name": "Wonder",
            "email": "alice@school.edu",
            "student_id_number": "clever-ccc",
            "period": "1",
        }
        enroll_rows = [
            {
                "class_id": "cls-002",
                "classes": {
                    "id": "cls-002",
                    "name": "English 10",
                    "subject": "english",
                },
            }
        ]

        sb = MagicMock()
        eq_cols = []

        def _table(name):
            if name == "students":
                q = MagicMock()
                q.select.return_value = q

                def _eq(col, val):
                    eq_cols.append(col)
                    # clever_id misses; an email match WOULD find Alice — but the
                    # fixed code must never issue the email query.
                    if col == "student_id_number":
                        q.execute.return_value = MagicMock(data=[])
                    else:
                        q.execute.return_value = MagicMock(data=[student_row])
                    return q

                q.eq.side_effect = _eq
                return q

            if name == "class_students":
                enroll_q = MagicMock()
                enroll_q.select.return_value = enroll_q
                enroll_q.eq.return_value = enroll_q
                enroll_q.limit.return_value = enroll_q
                enroll_q.execute.return_value = MagicMock(data=enroll_rows)
                return enroll_q

            if name == "student_sessions":
                sess_q = MagicMock()
                sess_q.insert.return_value = sess_q
                sess_q.execute.return_value = MagicMock(data=[{"id": "sess-999"}])
                return sess_q

            return MagicMock()

        sb.table.side_effect = _table

        with patch("backend.routes.clever_routes._get_supabase_safe", return_value=sb):
            result = _create_clever_student_session("wrong-clever-id", "alice@school.edu")

        assert result is None, "fell back to an unscoped email match (cross-tenant)"
        assert "email" not in eq_cols, "must not query the students table by email"
