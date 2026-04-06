"""Tests for question mix — per-type count instructions in prompt."""

import pytest


class TestBuildSectionCategoriesPromptWithCounts:
    def test_includes_exact_count_per_type(self):
        """When questionTypeCounts provided, prompt should say 'exactly N' per type."""
        from backend.routes.planner_routes import _build_section_categories_prompt

        categories = {"multiple_choice": True, "short_answer": True, "true_false": True}
        counts = {"multiple_choice": 4, "short_answer": 2, "true_false": 1}

        prompt = _build_section_categories_prompt(categories, subject="US History", question_type_counts=counts)

        assert "exactly 4" in prompt.lower() or "4 multiple choice" in prompt.lower()
        assert "exactly 2" in prompt.lower() or "2 short answer" in prompt.lower()
        assert "exactly 1" in prompt.lower() or "1 true" in prompt.lower()

    def test_no_counts_uses_existing_behavior(self):
        """Without counts, should use existing behavior (no exact count instructions)."""
        from backend.routes.planner_routes import _build_section_categories_prompt

        categories = {"multiple_choice": True, "short_answer": True}

        prompt = _build_section_categories_prompt(categories, subject="Math")

        assert "Multiple Choice" in prompt
        assert "Short Answer" in prompt
        # Should NOT have exact count instructions
        assert "exactly" not in prompt.lower()

    def test_zero_count_type_not_included(self):
        """Types with count=0 should not appear in the prompt."""
        from backend.routes.planner_routes import _build_section_categories_prompt

        categories = {"multiple_choice": True, "short_answer": False}
        counts = {"multiple_choice": 5, "short_answer": 0}

        prompt = _build_section_categories_prompt(categories, subject="Science", question_type_counts=counts)

        assert "Multiple Choice" in prompt
        # short_answer has count 0 and is False in categories — should not appear in enabled list

    def test_empty_counts_dict(self):
        """Empty counts dict should use existing behavior."""
        from backend.routes.planner_routes import _build_section_categories_prompt

        categories = {"multiple_choice": True}

        prompt = _build_section_categories_prompt(categories, subject="ELA", question_type_counts={})

        assert "Multiple Choice" in prompt
        assert "exactly" not in prompt.lower()
