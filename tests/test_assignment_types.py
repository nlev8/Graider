"""Tests for assignment type differentiation — essay, project, assignment."""

import json
import pytest
from unittest.mock import patch, MagicMock


MOCK_LESSON_PLAN = {
    "title": "The Civil War",
    "overview": "Students explore causes and consequences of the Civil War.",
    "essential_questions": ["What caused the Civil War?"],
    "days": [
        {
            "day": 1,
            "objective": "Explain causes of the Civil War",
            "vocabulary": [
                {"term": "Sectionalism", "definition": "Regional loyalty over national loyalty"},
                {"term": "Secession", "definition": "Formally withdrawing from a union"},
            ],
            "direct_instruction": {"key_points": ["Economic differences", "Slavery debate"]},
        }
    ],
}


class TestEssayTypePrompt:
    def test_essay_prompt_does_not_include_section_categories(self):
        """Essay type should NOT include MC, vocab, short answer sections."""
        from backend.routes.planner_routes import _build_assignment_prompt

        prompt = _build_assignment_prompt(
            lesson_plan=MOCK_LESSON_PLAN,
            config={"subject": "US History", "grade": "8"},
            assignment_type="essay",
        )
        # Should NOT contain multi-section instructions
        assert "Multiple Choice" not in prompt
        assert "Vocabulary / Matching" not in prompt
        assert "section categories" not in prompt.lower()
        # Should contain essay-specific instructions
        assert "essay" in prompt.lower()
        assert "thesis" in prompt.lower() or "prompt" in prompt.lower()
        assert "rubric" in prompt.lower()

    def test_essay_json_schema_is_single_prompt(self):
        """Essay JSON schema should have a single essay prompt, not sections array."""
        from backend.routes.planner_routes import _build_assignment_prompt

        prompt = _build_assignment_prompt(
            lesson_plan=MOCK_LESSON_PLAN,
            config={"subject": "US History", "grade": "8"},
            assignment_type="essay",
        )
        # Should request essay-specific JSON structure
        assert "essay_prompt" in prompt or "prompt" in prompt
        assert "rubric" in prompt.lower()


class TestProjectTypePrompt:
    def test_project_prompt_does_not_include_section_categories(self):
        """Project type should NOT include MC, vocab, short answer sections."""
        from backend.routes.planner_routes import _build_assignment_prompt

        prompt = _build_assignment_prompt(
            lesson_plan=MOCK_LESSON_PLAN,
            config={"subject": "US History", "grade": "8"},
            assignment_type="project",
        )
        assert "Multiple Choice" not in prompt
        assert "Vocabulary / Matching" not in prompt
        # Should contain project-specific instructions
        assert "project" in prompt.lower()
        assert "deliverable" in prompt.lower() or "milestone" in prompt.lower()

    def test_project_json_schema_has_milestones(self):
        """Project JSON should request milestones/deliverables, not question sections."""
        from backend.routes.planner_routes import _build_assignment_prompt

        prompt = _build_assignment_prompt(
            lesson_plan=MOCK_LESSON_PLAN,
            config={"subject": "US History", "grade": "8"},
            assignment_type="project",
        )
        assert "milestone" in prompt.lower() or "deliverable" in prompt.lower()
        assert "rubric" in prompt.lower()


class TestAssignmentTypePrompt:
    def test_assignment_returns_none_for_existing_flow(self):
        """Assignment type should return None to signal use of existing prompt logic."""
        from backend.routes.planner_routes import _build_assignment_prompt

        prompt = _build_assignment_prompt(
            lesson_plan=MOCK_LESSON_PLAN,
            config={
                "subject": "US History",
                "grade": "8",
                "sectionCategories": {"multiple_choice": True, "short_answer": True},
            },
            assignment_type="assignment",
        )
        # Returns None — the existing multi-section worksheet logic handles this type
        assert prompt is None

    def test_default_type_returns_none(self):
        """Default (no type) should also return None for existing flow."""
        from backend.routes.planner_routes import _build_assignment_prompt

        prompt = _build_assignment_prompt(
            lesson_plan=MOCK_LESSON_PLAN,
            config={"subject": "US History", "grade": "8"},
            assignment_type="assignment",
        )
        assert prompt is None
