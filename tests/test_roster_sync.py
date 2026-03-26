"""
Tests for backend/roster_sync.py — provider-agnostic roster sync logic.
"""
import unittest
from unittest.mock import patch, MagicMock

# Patch target: the function is imported inline via
# ``from backend.supabase_client import get_supabase as _get_supabase``
# so we patch at the source module.
_SB_PATCH = "backend.supabase_client.get_supabase"


class TestSyncRosterToDb(unittest.TestCase):
    """Tests for sync_roster_to_db()."""

    def test_empty_data_returns_zero_counts(self):
        """Empty input lists should return all-zero counts."""
        from backend.roster_sync import sync_roster_to_db

        with patch(_SB_PATCH, return_value=MagicMock()):
            result = sync_roster_to_db([], [], [], teacher_id="t1")

        self.assertEqual(result, {"classes": 0, "students": 0, "enrollments": 0})

    def test_returns_zero_when_supabase_none(self):
        """When Supabase is not configured, should return zero counts silently."""
        from backend.roster_sync import sync_roster_to_db

        with patch(_SB_PATCH, return_value=None):
            result = sync_roster_to_db(
                [{"external_id": "c1", "name": "Math"}],
                [{"external_id": "s1", "first_name": "A", "last_name": "B", "email": "a@b.com"}],
                [("c1", "s1")],
                teacher_id="t1",
            )

        self.assertEqual(result, {"classes": 0, "students": 0, "enrollments": 0})

    def test_valid_data_returns_correct_counts(self):
        """Valid classes, students, and enrollments should sync and return counts."""
        from backend.roster_sync import sync_roster_to_db

        mock_sb = MagicMock()

        def table_side_effect(name):
            mock_table = MagicMock()
            if name == "classes":
                result = MagicMock()
                result.data = [
                    {"id": "uuid-c1", "clever_section_id": "c1"},
                    {"id": "uuid-c2", "clever_section_id": "c2"},
                ]
                mock_table.upsert.return_value.execute.return_value = result
            elif name == "students":
                result = MagicMock()
                result.data = [
                    {"id": "uuid-s1", "student_id_number": "s1"},
                    {"id": "uuid-s2", "student_id_number": "s2"},
                ]
                mock_table.upsert.return_value.execute.return_value = result
            elif name == "class_students":
                result = MagicMock()
                result.data = []
                mock_table.upsert.return_value.execute.return_value = result
            return mock_table

        mock_sb.table.side_effect = table_side_effect

        with patch(_SB_PATCH, return_value=mock_sb):
            result = sync_roster_to_db(
                classes=[
                    {"external_id": "c1", "name": "Math 101", "subject": "Math", "grade_level": "6"},
                    {"external_id": "c2", "name": "Science", "subject": "Science", "grade_level": "7"},
                ],
                students=[
                    {"external_id": "s1", "first_name": "Alice", "last_name": "Smith", "email": "alice@test.com"},
                    {"external_id": "s2", "first_name": "Bob", "last_name": "Jones", "email": "bob@test.com"},
                ],
                enrollments=[("c1", "s1"), ("c1", "s2"), ("c2", "s1")],
                teacher_id="teacher-001",
                provider="test",
            )

        self.assertEqual(result["classes"], 2)
        self.assertEqual(result["students"], 2)
        self.assertEqual(result["enrollments"], 3)

    def test_skips_classes_without_external_id(self):
        """Classes missing external_id should be skipped."""
        from backend.roster_sync import sync_roster_to_db

        with patch(_SB_PATCH, return_value=MagicMock()):
            result = sync_roster_to_db(
                classes=[{"name": "No ID class"}],  # missing external_id
                students=[],
                enrollments=[],
                teacher_id="t1",
            )

        self.assertEqual(result, {"classes": 0, "students": 0, "enrollments": 0})


class TestDeleteRosterData(unittest.TestCase):
    """Tests for delete_roster_data()."""

    def test_calls_supabase_deletion(self):
        """Should query classes then delete enrollments, students, classes."""
        from backend.roster_sync import delete_roster_data

        mock_sb = MagicMock()

        # classes query returns one class
        classes_result = MagicMock()
        classes_result.data = [{"id": "uuid-c1"}]

        # published_content query returns empty
        content_result = MagicMock()
        content_result.data = []

        # students query returns one student
        students_result = MagicMock()
        students_result.data = [{"id": "uuid-s1"}]

        def table_side_effect(name):
            mock_table = MagicMock()
            if name == "classes":
                mock_table.select.return_value.eq.return_value.execute.return_value = classes_result
                mock_table.delete.return_value.eq.return_value.execute.return_value = MagicMock()
            elif name == "published_content":
                mock_table.select.return_value.in_.return_value.execute.return_value = content_result
            elif name == "students":
                mock_table.select.return_value.eq.return_value.execute.return_value = students_result
                mock_table.delete.return_value.eq.return_value.execute.return_value = MagicMock()
            elif name == "class_students":
                mock_table.delete.return_value.eq.return_value.execute.return_value = MagicMock()
            elif name == "student_sessions":
                mock_table.delete.return_value.eq.return_value.execute.return_value = MagicMock()
            return mock_table

        mock_sb.table.side_effect = table_side_effect

        with patch(_SB_PATCH, return_value=mock_sb):
            result = delete_roster_data("teacher-001")

        self.assertEqual(result["classes"], 1)
        self.assertEqual(result["students"], 1)

    def test_handles_no_supabase(self):
        """When Supabase is None, should still return counts (zeros) and not crash."""
        from backend.roster_sync import delete_roster_data

        with patch(_SB_PATCH, return_value=None):
            result = delete_roster_data("teacher-001")

        self.assertEqual(result["classes"], 0)
        self.assertEqual(result["students"], 0)


class TestCleverNormalization(unittest.TestCase):
    """Test that Clever data still produces correct results through the new wrapper."""

    def test_clever_wrapper_normalizes_and_delegates(self):
        """_sync_classes_to_db should normalise Clever data and call shared sync."""
        from backend.routes.clever_routes import _sync_classes_to_db

        sections = [
            {"data": {
                "id": "sec-1",
                "name": "Math Period 3",
                "subject": "Math",
                "grade": "8",
                "students": ["stu-1", "stu-2"],
            }},
        ]
        students = [
            {"data": {
                "id": "stu-1",
                "name": {"first": "Alice", "last": "Smith"},
                "email": "alice@school.edu",
            }},
            {"data": {
                "id": "stu-2",
                "name": {"first": "Bob", "last": "Jones"},
                "email": "bob@school.edu",
            }},
        ]

        with patch("backend.routes.clever_routes._shared_sync_roster_to_db") as mock_sync:
            mock_sync.return_value = {"classes": 1, "students": 2, "enrollments": 2}
            _sync_classes_to_db(sections, students, "clever:teacher-1")

        mock_sync.assert_called_once()
        args = mock_sync.call_args

        # Verify normalised classes
        norm_classes = args[0][0]
        self.assertEqual(len(norm_classes), 1)
        self.assertEqual(norm_classes[0]["external_id"], "sec-1")
        self.assertEqual(norm_classes[0]["name"], "Math Period 3")
        self.assertEqual(norm_classes[0]["subject"], "Math")
        self.assertEqual(norm_classes[0]["grade_level"], "8")

        # Verify normalised students
        norm_students = args[0][1]
        self.assertEqual(len(norm_students), 2)
        self.assertEqual(norm_students[0]["external_id"], "stu-1")
        self.assertEqual(norm_students[0]["first_name"], "Alice")
        self.assertEqual(norm_students[0]["last_name"], "Smith")
        self.assertEqual(norm_students[1]["external_id"], "stu-2")

        # Verify enrollment pairs
        enrollment_pairs = args[0][2]
        self.assertEqual(len(enrollment_pairs), 2)
        self.assertIn(("sec-1", "stu-1"), enrollment_pairs)
        self.assertIn(("sec-1", "stu-2"), enrollment_pairs)

        # Verify teacher_id and provider
        self.assertEqual(args[0][3], "clever:teacher-1")
        self.assertEqual(args[1]["provider"], "clever")

    def test_clever_wrapper_handles_unwrapped_data(self):
        """Clever sections without 'data' wrapper should still work."""
        from backend.routes.clever_routes import _sync_classes_to_db

        sections = [{"id": "sec-1", "name": "Test", "subject": "", "grade": "", "students": []}]
        students = []

        with patch("backend.routes.clever_routes._shared_sync_roster_to_db") as mock_sync:
            mock_sync.return_value = {"classes": 1, "students": 0, "enrollments": 0}
            _sync_classes_to_db(sections, students, "t1")

        norm_classes = mock_sync.call_args[0][0]
        self.assertEqual(norm_classes[0]["external_id"], "sec-1")


if __name__ == "__main__":
    unittest.main()
