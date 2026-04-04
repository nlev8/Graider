# Assignment Type Differentiation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix "Create Essay from Lesson" and "Create Project from Lesson" so they generate the correct output — a single essay prompt with rubric, or a project brief with deliverables — instead of a multi-section worksheet with vocab/MC/short answer tacked on.

**Architecture:** Modify the `generate_assignment_from_lesson` endpoint in `planner_routes.py` to skip section category injection when `assignment_type` is `"essay"` or `"project"`. Replace the generic prompt structure with type-specific prompts and JSON output schemas. The essay type returns a single essay prompt + rubric. The project type returns a project brief + milestones + rubric. The assignment type keeps current behavior (multi-section worksheet).

**Tech Stack:** Python, Flask, OpenAI API (existing endpoint)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/routes/planner_routes.py` | **Modify** | Type-specific prompt branching + JSON schemas for essay and project |
| `tests/test_assignment_types.py` | **Create** | Tests verifying each type generates correct structure |

---

### Task 1: Backend — type-specific prompt branching

**Files:**
- Modify: `backend/routes/planner_routes.py:3354-3373` and `3554-3565`
- Create: `tests/test_assignment_types.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_assignment_types.py`:

```python
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
    def test_assignment_keeps_section_categories(self):
        """Assignment type should still include section categories (current behavior)."""
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
        # Should contain section category instructions
        assert "Multiple Choice" in prompt or "multiple choice" in prompt.lower()

    def test_assignment_includes_question_types(self):
        """Assignment should include the question type guidance block."""
        from backend.routes.planner_routes import _build_assignment_prompt

        prompt = _build_assignment_prompt(
            lesson_plan=MOCK_LESSON_PLAN,
            config={"subject": "US History", "grade": "8"},
            assignment_type="assignment",
        )
        assert "question_type" in prompt.lower() or "sections" in prompt.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assignment_types.py -v`
Expected: FAIL with `ImportError: cannot import name '_build_assignment_prompt'`

- [ ] **Step 3: Extract prompt building into a testable function**

In `backend/routes/planner_routes.py`, find the `generate_assignment_from_lesson` function (~line 3290). Extract the prompt building logic into a new function `_build_assignment_prompt` that can be called from both the endpoint and tests.

Add this function BEFORE the endpoint (around line 3280):

```python
def _build_assignment_prompt(lesson_plan, config, assignment_type='assignment'):
    """Build the AI prompt for generating an assignment from a lesson plan.

    Returns the full prompt string. Extracted for testability.
    Assignment type determines the structure:
    - 'assignment': multi-section worksheet (vocab, MC, short answer, etc.)
    - 'essay': single essay prompt with thesis question + rubric
    - 'project': project brief with milestones, deliverables + rubric
    """
    lesson_title = lesson_plan.get('title', 'Untitled Lesson')
    lesson_overview = lesson_plan.get('overview', '')
    essential_questions = lesson_plan.get('essential_questions', [])
    days = lesson_plan.get('days', [])

    all_vocabulary = []
    all_objectives = []
    all_key_points = []

    for day in days:
        vocab = day.get('vocabulary', [])
        for v in vocab:
            if isinstance(v, dict):
                all_vocabulary.append(v.get('term', '') + ": " + v.get('definition', ''))
            else:
                all_vocabulary.append(str(v))
        if day.get('objective'):
            all_objectives.append(day['objective'])
        di = day.get('direct_instruction', {})
        if isinstance(di, dict) and di.get('key_points'):
            all_key_points.extend(di['key_points'])

    _subject = config.get('subject', '')
    _grade = config.get('grade', '7')
    global_ai_notes = config.get('globalAINotes', '')

    # Lesson context block (shared by all types)
    lesson_block = "LESSON PLAN DETAILS:" + chr(10)
    lesson_block += "Title: " + lesson_title + chr(10)
    lesson_block += "Overview: " + lesson_overview + chr(10)
    lesson_block += chr(10) + "Essential Questions:" + chr(10)
    lesson_block += (chr(10).join("- " + q for q in essential_questions) if essential_questions else "None specified") + chr(10)
    lesson_block += chr(10) + "Learning Objectives:" + chr(10)
    lesson_block += (chr(10).join("- " + obj for obj in all_objectives) if all_objectives else "None specified") + chr(10)
    lesson_block += chr(10) + "Key Content Points:" + chr(10)
    lesson_block += (chr(10).join("- " + kp for kp in all_key_points[:10]) if all_key_points else "None specified") + chr(10)
    lesson_block += chr(10) + "Vocabulary:" + chr(10)
    lesson_block += (chr(10).join("- " + v for v in all_vocabulary[:15]) if all_vocabulary else "None specified") + chr(10)

    global_notes_block = ""
    if global_ai_notes:
        global_notes_block = chr(10) + "=== TEACHER INSTRUCTIONS (MUST FOLLOW) ===" + chr(10) + global_ai_notes + chr(10) + "=== END TEACHER INSTRUCTIONS ===" + chr(10)

    # ── ESSAY TYPE ──────────────────────────────────────────────
    if assignment_type == 'essay':
        return (
            "You are an expert " + _subject + " teacher creating an essay assignment for grade " + _grade + " students." + chr(10)
            + global_notes_block + chr(10)
            + lesson_block + chr(10)
            + "Create a SINGLE essay assignment based on this lesson plan. Do NOT create multiple sections, " + chr(10)
            + "vocabulary matching, multiple choice, or short answer questions. This is an ESSAY ONLY." + chr(10)
            + chr(10)
            + "The essay should:" + chr(10)
            + "- Have a clear, thought-provoking thesis prompt that connects to the lesson objectives" + chr(10)
            + "- Specify required length (number of paragraphs or word count)" + chr(10)
            + "- Include pre-writing guidance (what to consider, key terms to use)" + chr(10)
            + "- Include a detailed rubric with 4-5 categories and point values" + chr(10)
            + chr(10)
            + "Return JSON with this structure:" + chr(10)
            + '{' + chr(10)
            + '  "title": "Essay title",' + chr(10)
            + '  "type": "essay",' + chr(10)
            + '  "instructions": "Brief instructions for the student",' + chr(10)
            + '  "time_estimate": "Estimated completion time",' + chr(10)
            + '  "total_points": 100,' + chr(10)
            + '  "essay_prompt": "The full essay question/thesis prompt",' + chr(10)
            + '  "required_length": "e.g., 3-5 paragraphs or 500-750 words",' + chr(10)
            + '  "prewriting_guidance": ["Key point to address 1", "Key point 2", ...],' + chr(10)
            + '  "vocabulary_to_use": ["term1", "term2", ...],' + chr(10)
            + '  "rubric": [' + chr(10)
            + '    {"category": "Thesis & Argument", "points": 25, "description": "Clear thesis supported by evidence"},' + chr(10)
            + '    {"category": "Content & Evidence", "points": 25, "description": "Uses specific examples from lesson content"},' + chr(10)
            + '    {"category": "Organization", "points": 20, "description": "Logical structure with intro, body, conclusion"},' + chr(10)
            + '    {"category": "Writing Quality", "points": 20, "description": "Grammar, spelling, academic language"},' + chr(10)
            + '    {"category": "Vocabulary Use", "points": 10, "description": "Uses key terms correctly"}' + chr(10)
            + '  ]' + chr(10)
            + '}' + chr(10)
            + chr(10)
            + "Return ONLY valid JSON. No markdown, no code fences."
        )

    # ── PROJECT TYPE ────────────────────────────────────────────
    if assignment_type == 'project':
        return (
            "You are an expert " + _subject + " teacher creating a multi-day project for grade " + _grade + " students." + chr(10)
            + global_notes_block + chr(10)
            + lesson_block + chr(10)
            + "Create a PROJECT assignment based on this lesson plan. Do NOT create multiple choice questions, " + chr(10)
            + "vocabulary matching, or short answer sections. This is a PROJECT with deliverables and milestones." + chr(10)
            + chr(10)
            + "The project should:" + chr(10)
            + "- Have a clear, engaging project description" + chr(10)
            + "- Include 3-5 milestones with due dates (Day 1, Day 2, etc.)" + chr(10)
            + "- Specify concrete deliverables (what the student turns in)" + chr(10)
            + "- Include a detailed rubric with categories and point values" + chr(10)
            + "- Be achievable within the lesson timeframe" + chr(10)
            + chr(10)
            + "Return JSON with this structure:" + chr(10)
            + '{' + chr(10)
            + '  "title": "Project title",' + chr(10)
            + '  "type": "project",' + chr(10)
            + '  "instructions": "Project overview and goals for the student",' + chr(10)
            + '  "time_estimate": "Total project duration",' + chr(10)
            + '  "total_points": 100,' + chr(10)
            + '  "project_description": "Detailed description of what students will create",' + chr(10)
            + '  "deliverables": ["Final essay/presentation/model", "Research notes", ...],' + chr(10)
            + '  "milestones": [' + chr(10)
            + '    {"day": 1, "task": "Research and gather sources", "deliverable": "Annotated bibliography"},' + chr(10)
            + '    {"day": 2, "task": "Create outline", "deliverable": "Project outline"},' + chr(10)
            + '    {"day": 3, "task": "Build/write draft", "deliverable": "Draft submission"},' + chr(10)
            + '    {"day": 4, "task": "Revise and finalize", "deliverable": "Final product"}' + chr(10)
            + '  ],' + chr(10)
            + '  "rubric": [' + chr(10)
            + '    {"category": "Content & Accuracy", "points": 30, "description": "Demonstrates understanding of lesson content"},' + chr(10)
            + '    {"category": "Creativity & Effort", "points": 25, "description": "Original thinking and thorough work"},' + chr(10)
            + '    {"category": "Organization", "points": 20, "description": "Clear structure and logical flow"},' + chr(10)
            + '    {"category": "Presentation", "points": 15, "description": "Professional quality of final deliverable"},' + chr(10)
            + '    {"category": "Timeliness", "points": 10, "description": "Met milestone deadlines"}' + chr(10)
            + '  ]' + chr(10)
            + '}' + chr(10)
            + chr(10)
            + "Return ONLY valid JSON. No markdown, no code fences."
        )

    # ── ASSIGNMENT TYPE (default — multi-section worksheet) ─────
    # Returns None to signal the caller to use the existing prompt logic
    return None
```

- [ ] **Step 4: Modify the endpoint to use the new function**

In the `generate_assignment_from_lesson` function (~line 3290), after building `all_vocabulary`, `all_objectives`, `all_key_points` (around line 3353), add:

```python
        # Check for essay/project — use dedicated prompts (no section categories)
        dedicated_prompt = _build_assignment_prompt(lesson_plan, config, assignment_type)
        if dedicated_prompt is not None:
            completion = with_retry(
                lambda: client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are an expert teacher. Return valid JSON only."},
                        {"role": "user", "content": dedicated_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7,
                ),
                label="generate_essay_or_project",
            )

            content = completion.choices[0].message.content
            result = json.loads(content)

            # Wrap essay/project in sections format for frontend compatibility
            if assignment_type == 'essay':
                result['sections'] = [{
                    'name': 'Essay Response',
                    'type': 'essay',
                    'questions': [{
                        'question': result.get('essay_prompt', ''),
                        'answer': 'See rubric for grading criteria.',
                        'points': result.get('total_points', 100),
                        'type': 'extended_response',
                    }],
                }]
            elif assignment_type == 'project':
                result['sections'] = [{
                    'name': 'Project Requirements',
                    'type': 'project',
                    'questions': [{
                        'question': result.get('project_description', ''),
                        'answer': 'See rubric and milestones for grading criteria.',
                        'points': result.get('total_points', 100),
                        'type': 'extended_response',
                    }],
                }]

            return jsonify({"assignment": result})
```

Place this BEFORE the existing prompt building code (before `type_instructions = {` at line 3358). Add an early return so the existing code is only reached for `assignment_type == 'assignment'`.

Also add a comment at the early return point to prevent future regressions:

```python
        # IMPORTANT: Essay and project types use dedicated prompts above and return early.
        # The code below (section categories, question types, multi-section JSON schema)
        # only applies to assignment_type == 'assignment'. Do NOT remove this early return
        # or essay/project will revert to generating multi-section worksheets.
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assignment_types.py -v`
Expected: All 6 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add backend/routes/planner_routes.py tests/test_assignment_types.py
git commit -m "fix: essay and project types generate dedicated prompts, not multi-section worksheets"
```

---

## Summary

| Task | What | Files | Risk |
|------|------|-------|------|
| 1 | Type-specific prompts + 6 tests | Modify `planner_routes.py`, create `test_assignment_types.py` | Low — adds early return path, existing assignment flow untouched |

**Total: 1 extracted function, 1 endpoint modification, 6 tests.**

**Before:**
- "Create Essay from Lesson" → generates Vocab (Part A) + MC (Part B) + Short Answer (Part C) + Essay (Part D)
- "Create Project from Lesson" → same multi-section worksheet

**After:**
- "Create Essay from Lesson" → single essay prompt with thesis question, required length, pre-writing guidance, vocabulary to use, and detailed 5-category rubric
- "Create Project from Lesson" → project brief with description, deliverables, milestones (Day 1-4), and detailed 5-category rubric
- "Create Assignment from Lesson" → unchanged (multi-section worksheet with section categories)

**Frontend compatibility:** Essay and project results are wrapped in a `sections` array with a single `extended_response` question so the existing frontend rendering works without changes.
