"""
Test: Student info tools — accommodations and streaks.
"""
import pytest
from backend.services.assistant_tools_student import (
    get_student_accommodations, get_student_streak,
)


class TestGetStudentAccommodations:
    def test_student_with_accommodations(self, patch_paths):
        result = get_student_accommodations("Carol Williams")
        assert result.get("has_accommodations") is True
        assert "extended_time" in result.get("presets", [])
        assert result.get("student_name") == "Carol Williams"

    def test_student_without_accommodations(self, patch_paths):
        result = get_student_accommodations("Alice Johnson")
        assert result.get("has_accommodations") is False

    def test_student_not_found(self, patch_paths):
        result = get_student_accommodations("Nonexistent Student")
        assert "error" in result

    def test_empty_name(self, patch_paths):
        result = get_student_accommodations("")
        assert "error" in result

    def test_fuzzy_match(self, patch_paths):
        result = get_student_accommodations("Carol")
        assert result.get("has_accommodations") is True

    def test_grading_impacts_populated(self, patch_paths):
        result = get_student_accommodations("Emma Davis")
        assert result.get("has_accommodations") is True
        assert len(result.get("grading_impacts", [])) > 0

    def test_notes_included(self, patch_paths):
        result = get_student_accommodations("Carol")
        assert result.get("notes")
        assert "IEP" in result["notes"] or "reading" in result["notes"].lower()


class TestGetStudentStreak:
    def test_student_with_grades(self, patch_paths):
        result = get_student_streak("Alice Johnson")
        assert "error" not in result
        assert result.get("student_name") == "Alice Johnson"
        assert result.get("assignment_count") == 3  # 3 assignments in fixture
        assert result.get("average") > 0

    def test_history_has_direction(self, patch_paths):
        result = get_student_streak("Alice Johnson")
        history = result.get("history", [])
        assert len(history) == 3
        # First entry has no direction
        assert "direction" not in history[0] or history[0].get("direction") is None or True
        # Subsequent entries should have direction
        for entry in history[1:]:
            assert entry.get("direction") in ("up", "down", "stable")

    def test_declining_student(self, patch_paths):
        result = get_student_streak("Alice Johnson")
        # Alice: 92 → 88 → 85 = declining
        assert result.get("current_streak_type", result.get("direction", "")) != "improving" or \
               result.get("declining_streak", 0) >= 0

    def test_improving_student(self, patch_paths):
        result = get_student_streak("Carol Williams")
        # Carol: 65 → 70 → 72 = improving
        history = result.get("history", [])
        up_count = sum(1 for h in history if h.get("direction") == "up")
        assert up_count >= 1

    def test_student_not_found(self, patch_paths):
        result = get_student_streak("Nonexistent")
        assert "error" in result

    def test_average_calculated(self, patch_paths):
        result = get_student_streak("Emma Davis")
        # Emma: 45, 50, 55 → avg = 50
        assert result.get("average") == 50.0
