"""
Tests for _sync_classes_to_db() in clever_routes.py.

Covers:
- Happy path: sections + students upserted and enrolled correctly
- Supabase not configured (returns None) → silently skips, no crash
- Section missing 'id' field → skipped gracefully
- Student not in student_map (no roster entry) → enrollment skipped
- Upsert failure for class batch → all sections skipped, function returns early
- Upsert failure for student batch → enrollments skipped, function returns early
- Enrollment batch upsert failure → logged but no crash
- Multiple sections with same student → student upserted once, enrolled in each class

Zero network calls — all Supabase interactions are mocked.
"""
import logging
from unittest.mock import MagicMock, patch, call

import pytest

# Import the function under test
from backend.routes.clever_routes import _sync_classes_to_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_section(sec_id, name="Test Class", subject="math", grade="9", students=None):
    return {
        "data": {
            "id": sec_id,
            "name": name,
            "subject": subject,
            "grade": grade,
            "teachers": ["t1"],
            "students": students or [],
            "period": "1",
        }
    }


def _make_student(stu_id, first="Jane", last="Doe", email=None):
    return {
        "data": {
            "id": stu_id,
            "name": {"first": first, "last": last},
            "email": email or f"{stu_id}@school.edu",
            "roles": {"student": {"grade": "9"}},
        }
    }


def _make_supabase_mock(class_rows=None, student_rows=None):
    """Return a fully wired mock Supabase client for batch upserts.

    The batch implementation expects:
    - classes.upsert returns rows that include 'clever_section_id' and 'id'
    - students.upsert returns rows that include 'student_id_number' and 'id'

    Args:
        class_rows: list of dicts returned by classes.upsert().execute().data
        student_rows: list of dicts returned by students.upsert().execute().data
    """
    if class_rows is None:
        class_rows = [{"id": "cls-001", "clever_section_id": "sec1"}]
    if student_rows is None:
        student_rows = [{"id": "stu-db-001", "student_id_number": "s1"}]

    table_mocks = {}

    def _table(name):
        if name not in table_mocks:
            table_mocks[name] = MagicMock()
        return table_mocks[name]

    sb = MagicMock()
    sb.table.side_effect = _table

    # classes upsert chain
    class_upsert_result = MagicMock()
    class_upsert_result.data = class_rows
    _table("classes").upsert.return_value.execute.return_value = class_upsert_result

    # students upsert chain
    stu_upsert_result = MagicMock()
    stu_upsert_result.data = student_rows
    _table("students").upsert.return_value.execute.return_value = stu_upsert_result

    # class_students upsert chain
    enroll_result = MagicMock()
    enroll_result.data = [{}]
    _table("class_students").upsert.return_value.execute.return_value = enroll_result

    return sb


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSyncClassesToDbNoSupabase:
    def test_skips_silently_when_supabase_none(self):
        """If Supabase is not configured, function returns without error."""
        sections = [_make_section("sec1", students=["s1"])]
        students = [_make_student("s1")]

        with patch("backend.supabase_client.get_supabase", return_value=None):
            # Must not raise
            _sync_classes_to_db(sections, students, teacher_id="teacher-001")


class TestSyncClassesToDbHappyPath:
    def test_upserts_class_student_and_enrollment(self):
        """Full happy-path: one section with one student → one class, one student, one enrollment."""
        sb = _make_supabase_mock(
            class_rows=[{"id": "cls-001", "clever_section_id": "sec1"}],
            student_rows=[{"id": "stu-db-001", "student_id_number": "s1"}],
        )
        sections = [_make_section("sec1", name="Algebra I", subject="math", grade="9", students=["s1"])]
        students = [_make_student("s1", first="Jane", last="Doe", email="jane@school.edu")]

        with patch("backend.supabase_client.get_supabase", return_value=sb):
            _sync_classes_to_db(sections, students, teacher_id="teacher-001")

        # Verify class upsert called once with a list payload
        classes_table = sb.table("classes")
        classes_table.upsert.assert_called_once()
        class_payloads = classes_table.upsert.call_args[0][0]
        assert isinstance(class_payloads, list)
        assert len(class_payloads) == 1
        cp = class_payloads[0]
        assert cp["teacher_id"] == "teacher-001"
        assert cp["clever_section_id"] == "sec1"
        assert cp["name"] == "Algebra I"
        assert cp["subject"] == "math"
        assert cp["grade_level"] == "9"
        assert cp["is_active"] is True

        # Verify student upsert called once with a list payload
        students_table = sb.table("students")
        students_table.upsert.assert_called_once()
        stu_payloads = students_table.upsert.call_args[0][0]
        assert isinstance(stu_payloads, list)
        assert len(stu_payloads) == 1
        sp = stu_payloads[0]
        assert sp["teacher_id"] == "teacher-001"
        assert sp["student_id_number"] == "s1"
        assert sp["first_name"] == "Jane"
        assert sp["last_name"] == "Doe"
        assert sp["email"] == "jane@school.edu"
        assert sp["is_active"] is True

        # Verify enrollment upsert called once with a list payload
        cs_table = sb.table("class_students")
        cs_table.upsert.assert_called_once()
        enroll_payloads = cs_table.upsert.call_args[0][0]
        assert isinstance(enroll_payloads, list)
        assert len(enroll_payloads) == 1
        ep = enroll_payloads[0]
        assert ep["class_id"] == "cls-001"
        assert ep["student_id"] == "stu-db-001"

    def test_upsert_conflict_params(self):
        """Upserts must pass on_conflict matching the table constraints."""
        sb = _make_supabase_mock()
        sections = [_make_section("sec1", students=["s1"])]
        students = [_make_student("s1")]

        with patch("backend.supabase_client.get_supabase", return_value=sb):
            _sync_classes_to_db(sections, students, teacher_id="teacher-001")

        classes_table = sb.table("classes")
        _, class_kwargs = classes_table.upsert.call_args
        assert class_kwargs.get("on_conflict") == "teacher_id,clever_section_id"

        students_table = sb.table("students")
        _, stu_kwargs = students_table.upsert.call_args
        assert stu_kwargs.get("on_conflict") == "teacher_id,student_id_number"

        cs_table = sb.table("class_students")
        _, enroll_kwargs = cs_table.upsert.call_args
        assert enroll_kwargs.get("on_conflict") == "class_id,student_id"

    def test_multiple_sections_and_students(self):
        """Multiple sections each get a class entry; student shared across sections
        is upserted once but enrolled in each class."""
        sb = _make_supabase_mock(
            class_rows=[
                {"id": "cls-001", "clever_section_id": "sec1"},
                {"id": "cls-002", "clever_section_id": "sec2"},
            ],
            student_rows=[{"id": "stu-db-001", "student_id_number": "s1"}],
        )

        sections = [
            _make_section("sec1", students=["s1"]),
            _make_section("sec2", students=["s1"]),
        ]
        students = [_make_student("s1")]

        with patch("backend.supabase_client.get_supabase", return_value=sb):
            _sync_classes_to_db(sections, students, teacher_id="teacher-001")

        # Batched: one call each for classes, students, enrollments
        assert sb.table("classes").upsert.call_count == 1
        class_payloads = sb.table("classes").upsert.call_args[0][0]
        assert len(class_payloads) == 2

        # s1 is unique — only one student upsert call
        assert sb.table("students").upsert.call_count == 1
        stu_payloads = sb.table("students").upsert.call_args[0][0]
        assert len(stu_payloads) == 1

        # But s1 is enrolled in both classes — two enrollment rows in the single call
        assert sb.table("class_students").upsert.call_count == 1
        enroll_payloads = sb.table("class_students").upsert.call_args[0][0]
        assert len(enroll_payloads) == 2
        class_ids_enrolled = {ep["class_id"] for ep in enroll_payloads}
        assert class_ids_enrolled == {"cls-001", "cls-002"}


class TestSyncClassesToDbEdgeCases:
    def test_section_missing_id_is_skipped(self):
        """Sections without an id are skipped — no upsert attempted."""
        sb = _make_supabase_mock()
        sections = [{"data": {"name": "No ID Section", "students": []}}]
        students = []

        with patch("backend.supabase_client.get_supabase", return_value=sb):
            _sync_classes_to_db(sections, students, teacher_id="teacher-001")

        sb.table("classes").upsert.assert_not_called()

    def test_student_not_in_map_is_skipped(self):
        """Student IDs listed in section but absent from students list are skipped."""
        sb = _make_supabase_mock(
            class_rows=[{"id": "cls-001", "clever_section_id": "sec1"}],
            student_rows=[],
        )
        sections = [_make_section("sec1", students=["unknown_id"])]
        students = []  # no matching student

        with patch("backend.supabase_client.get_supabase", return_value=sb):
            _sync_classes_to_db(sections, students, teacher_id="teacher-001")

        # Class should still be upserted
        sb.table("classes").upsert.assert_called_once()
        # But no student or enrollment upserts since student_map is empty
        sb.table("students").upsert.assert_not_called()
        sb.table("class_students").upsert.assert_not_called()

    def test_empty_sections_no_ops(self):
        """Empty sections list → no DB calls."""
        sb = _make_supabase_mock()

        with patch("backend.supabase_client.get_supabase", return_value=sb):
            _sync_classes_to_db([], [], teacher_id="teacher-001")

        sb.table("classes").upsert.assert_not_called()
        sb.table("students").upsert.assert_not_called()
        sb.table("class_students").upsert.assert_not_called()

    def test_section_with_no_students(self):
        """Section with empty student list still upserts class but no enrollments."""
        sb = _make_supabase_mock(
            class_rows=[{"id": "cls-001", "clever_section_id": "sec1"}],
            student_rows=[],
        )
        sections = [_make_section("sec1", students=[])]

        with patch("backend.supabase_client.get_supabase", return_value=sb):
            _sync_classes_to_db(sections, [], teacher_id="teacher-001")

        sb.table("classes").upsert.assert_called_once()
        sb.table("students").upsert.assert_not_called()
        sb.table("class_students").upsert.assert_not_called()

    def test_unwrapped_section_and_student(self):
        """Sections/students without 'data' wrapper are handled."""
        sb = _make_supabase_mock(
            class_rows=[{"id": "cls-001", "clever_section_id": "sec1"}],
            student_rows=[{"id": "stu-db-001", "student_id_number": "s1"}],
        )
        sections = [{"id": "sec1", "name": "Raw Section", "subject": "math", "grade": "9", "students": ["s1"]}]
        students = [{"id": "s1", "name": {"first": "Jane", "last": "Doe"}, "email": "jane@school.edu"}]

        with patch("backend.supabase_client.get_supabase", return_value=sb):
            _sync_classes_to_db(sections, students, teacher_id="teacher-001")

        sb.table("classes").upsert.assert_called_once()
        sb.table("students").upsert.assert_called_once()
        sb.table("class_students").upsert.assert_called_once()


class TestSyncClassesToDbFailureHandling:
    def test_class_upsert_exception_skips_all_sections(self, caplog):
        """If the batch class upsert raises, the entire sync is aborted (no students/enrollments)."""
        sb = _make_supabase_mock()
        sb.table("classes").upsert.side_effect = Exception("DB write error")

        sections = [
            _make_section("sec1", students=["s1"]),
            _make_section("sec2", students=["s1"]),
        ]
        students = [_make_student("s1")]

        with caplog.at_level(logging.WARNING, logger="backend.roster_sync"):
            with patch("backend.supabase_client.get_supabase", return_value=sb):
                _sync_classes_to_db(sections, students, teacher_id="teacher-001")

        # Batch class upsert failed → no student or enrollment calls
        sb.table("students").upsert.assert_not_called()
        assert "DB write error" in caplog.text

    def test_class_upsert_returns_no_data_aborts(self):
        """If the batch class upsert returns empty data, function aborts early."""
        sb = _make_supabase_mock()
        sb.table("classes").upsert.return_value.execute.return_value = MagicMock(data=[])

        sections = [_make_section("sec1", students=["s1"])]
        students = [_make_student("s1")]

        with patch("backend.supabase_client.get_supabase", return_value=sb):
            _sync_classes_to_db(sections, students, teacher_id="teacher-001")

        sb.table("students").upsert.assert_not_called()

    def test_student_upsert_exception_skips_enrollments(self, caplog):
        """If the batch student upsert raises, no enrollment upserts are made."""
        sb = _make_supabase_mock(
            class_rows=[{"id": "cls-001", "clever_section_id": "sec1"}],
        )
        sb.table("students").upsert.side_effect = Exception("student write error")

        sections = [_make_section("sec1", students=["s1"])]
        students = [_make_student("s1")]

        with caplog.at_level(logging.WARNING, logger="backend.roster_sync"):
            with patch("backend.supabase_client.get_supabase", return_value=sb):
                _sync_classes_to_db(sections, students, teacher_id="teacher-001")

        sb.table("class_students").upsert.assert_not_called()
        assert "student write error" in caplog.text

    def test_enrollment_upsert_exception_does_not_crash(self, caplog):
        """If the batch enrollment upsert raises, function continues without crashing."""
        sb = _make_supabase_mock(
            class_rows=[{"id": "cls-001", "clever_section_id": "sec1"}],
            student_rows=[{"id": "stu-db-001", "student_id_number": "s1"}],
        )
        sb.table("class_students").upsert.side_effect = Exception("enrollment error")

        sections = [_make_section("sec1", students=["s1"])]
        students = [_make_student("s1")]

        with caplog.at_level(logging.WARNING, logger="backend.roster_sync"):
            with patch("backend.supabase_client.get_supabase", return_value=sb):
                # Must not raise
                _sync_classes_to_db(sections, students, teacher_id="teacher-001")

        assert "enrollment error" in caplog.text

    def test_student_upsert_returns_no_rows_skips_enrollments(self):
        """If student batch upsert returns empty data, enrollment is skipped."""
        sb = _make_supabase_mock(
            class_rows=[{"id": "cls-001", "clever_section_id": "sec1"}],
            student_rows=[],
        )
        # Override: return empty data from students
        sb.table("students").upsert.return_value.execute.return_value = MagicMock(data=[])

        sections = [_make_section("sec1", students=["s1"])]
        students = [_make_student("s1")]

        with patch("backend.supabase_client.get_supabase", return_value=sb):
            _sync_classes_to_db(sections, students, teacher_id="teacher-001")

        sb.table("class_students").upsert.assert_not_called()

    def test_student_row_missing_id_excluded_from_enrollments(self):
        """Student rows without 'id' key are excluded from the enrollment batch."""
        sb = _make_supabase_mock(
            class_rows=[{"id": "cls-001", "clever_section_id": "sec1"}],
            # Row has student_id_number but no 'id' — cannot enroll
            student_rows=[{"student_id_number": "s1"}],
        )

        sections = [_make_section("sec1", students=["s1"])]
        students = [_make_student("s1")]

        with patch("backend.supabase_client.get_supabase", return_value=sb):
            _sync_classes_to_db(sections, students, teacher_id="teacher-001")

        sb.table("class_students").upsert.assert_not_called()


class TestBackgroundRosterSyncCallsSyncClassesToDb:
    """Verify that _background_roster_sync calls _sync_classes_to_db when sections exist."""

    def test_calls_sync_classes_to_db_when_sections_present(self):
        """_background_roster_sync should call _sync_classes_to_db after persist_sections_as_periods.

        Post-2026-05-14 tenancy filter: teacher_id must resolve a Clever ID
        owning the section. _make_section uses teachers=["t1"], so we pass
        teacher_id="clever:t1". The filter creates new lists with the same
        items — assertion checks contents (not identity) for that reason."""
        roster = {
            "students": [_make_student("s1")],
            "sections": [_make_section("sec1", students=["s1"])],
            "contacts": [],
        }

        with patch("backend.routes.clever_routes._run_async", return_value=roster), \
             patch("backend.routes.clever_routes.persist_roster_as_csv"), \
             patch("backend.routes.clever_routes.persist_sections_as_periods"), \
             patch("backend.routes.clever_routes._sync_classes_to_db") as mock_sync:
            from backend.routes.clever_routes import _background_roster_sync
            _background_roster_sync("district_token_xyz", "clever:t1")

        assert mock_sync.call_count == 1
        call_args = mock_sync.call_args[0]
        # Same content, different list identity (post-filter)
        assert call_args[0] == roster["sections"]
        assert call_args[1] == roster["students"]
        assert call_args[2] == "clever:t1"

    def test_does_not_call_sync_when_no_sections(self):
        """_background_roster_sync should not call _sync_classes_to_db when sections list is empty."""
        roster = {
            "students": [_make_student("s1")],
            "sections": [],
            "contacts": [],
        }

        with patch("backend.routes.clever_routes._run_async", return_value=roster), \
             patch("backend.routes.clever_routes.persist_roster_as_csv"), \
             patch("backend.routes.clever_routes._sync_classes_to_db") as mock_sync:
            from backend.routes.clever_routes import _background_roster_sync
            _background_roster_sync("district_token_xyz", "teacher-001")

        mock_sync.assert_not_called()
