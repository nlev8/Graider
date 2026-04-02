# Assessment Results in Assistant — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `query_assessment_results` assistant tool that lets teachers ask about portal assessment/assignment results (e.g., "How did my class do on the Unit 3 quiz?") by querying the `published_assessments` and `submissions` Supabase tables.

**Architecture:** Create a new tool submodule `assistant_tools_assessments.py` following the existing pattern (exports `ASSESSMENT_TOOL_DEFINITIONS` + `ASSESSMENT_TOOL_HANDLERS`). Register it in `_merge_submodules()`. The tool queries Supabase directly (same pattern as `assistant_tools_survey.py` and `assistant_tools_behavior.py`) rather than going through `_load_results()`, which only covers file-graded results. Two tools: `query_assessment_results` (list/filter/summarize published assessment submissions) and `list_published_assessments` (list teacher's published assessments with submission counts).

**Tech Stack:** Python, Supabase client (`backend/supabase_client.py`), existing assistant tool framework

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/services/assistant_tools_assessments.py` | **Create** | Two tools: `list_published_assessments_tool`, `query_assessment_results` + definitions/handlers |
| `backend/services/assistant_tools.py` | **Modify** | Register new submodule in `_merge_submodules()` |
| `tests/test_assessment_tools.py` | **Create** | Unit tests for both tools (mocked Supabase) |
| `tests/test_tool_schemas.py` | **Modify** | Update expected tool count |

---

### Task 1: Create the assessment tools submodule with `list_published_assessments_tool`

**Files:**
- Create: `backend/services/assistant_tools_assessments.py`
- Create: `tests/test_assessment_tools.py`

- [ ] **Step 1: Write the failing test for `list_published_assessments_tool`**

Create `tests/test_assessment_tools.py`:

```python
"""Tests for backend/services/assistant_tools_assessments.py — portal assessment tools."""

import pytest
from unittest.mock import patch, MagicMock


def _mock_supabase_with_assessments(assessments_data):
    """Create a mock Supabase client that returns the given assessments."""
    mock_sb = MagicMock()
    mock_result = MagicMock()
    mock_result.data = assessments_data
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_result
    return mock_sb


class TestListPublishedAssessments:
    def test_returns_assessments_list(self):
        """Should return formatted list of teacher's published assessments."""
        from backend.services.assistant_tools_assessments import list_published_assessments_tool

        mock_data = [
            {
                "id": "uuid-1",
                "join_code": "ABC123",
                "title": "Unit 3 Quiz",
                "created_at": "2026-03-20T10:00:00",
                "submission_count": 25,
                "is_active": True,
                "settings": {"content_type": "assessment", "period": "Period 2"},
            },
            {
                "id": "uuid-2",
                "join_code": "DEF456",
                "title": "Chapter 5 Test",
                "created_at": "2026-03-15T10:00:00",
                "submission_count": 0,
                "is_active": False,
                "settings": {"content_type": "assessment"},
            },
        ]

        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_assessments(mock_data)
            result = list_published_assessments_tool(teacher_id="teacher-1")

        assert "assessments" in result
        assert len(result["assessments"]) == 2
        assert result["assessments"][0]["title"] == "Unit 3 Quiz"
        assert result["assessments"][0]["join_code"] == "ABC123"
        assert result["assessments"][0]["submission_count"] == 25
        assert result["assessments"][0]["is_active"] is True
        assert result["assessments"][0]["content_type"] == "assessment"
        assert result["assessments"][1]["submission_count"] == 0

    def test_returns_empty_when_no_assessments(self):
        """Should return empty list when teacher has no assessments."""
        from backend.services.assistant_tools_assessments import list_published_assessments_tool

        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_assessments([])
            result = list_published_assessments_tool(teacher_id="teacher-1")

        assert result["assessments"] == []
        assert result["total"] == 0

    def test_returns_error_when_supabase_unavailable(self):
        """Should return error dict when Supabase is not configured."""
        from backend.services.assistant_tools_assessments import list_published_assessments_tool

        with patch('backend.services.assistant_tools_assessments._get_supabase', return_value=None):
            result = list_published_assessments_tool(teacher_id="teacher-1")

        assert "error" in result

    def test_filters_by_content_type(self):
        """Should filter by content_type when provided."""
        from backend.services.assistant_tools_assessments import list_published_assessments_tool

        mock_data = [
            {
                "id": "uuid-1", "join_code": "ABC123", "title": "Quiz 1",
                "created_at": "2026-03-20T10:00:00", "submission_count": 10,
                "is_active": True, "settings": {"content_type": "assessment"},
            },
            {
                "id": "uuid-2", "join_code": "DEF456", "title": "Homework 1",
                "created_at": "2026-03-15T10:00:00", "submission_count": 5,
                "is_active": True, "settings": {"content_type": "assignment"},
            },
        ]

        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_assessments(mock_data)
            result = list_published_assessments_tool(content_type="assignment", teacher_id="teacher-1")

        assert len(result["assessments"]) == 1
        assert result["assessments"][0]["title"] == "Homework 1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assessment_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services.assistant_tools_assessments'`

- [ ] **Step 3: Implement `list_published_assessments_tool` and module skeleton**

Create `backend/services/assistant_tools_assessments.py`:

```python
"""
Assistant Tools — Portal Assessment Results
============================================
Tools for querying published assessment/assignment results from the
student portal (Supabase: published_assessments + submissions tables).

These are SEPARATE from file-graded results in _load_results() which
only cover documents graded via the Grading tab. This module covers
content published via join codes or class-based publishing.
"""

import logging
from backend.utils.compliance import require_teacher_id

logger = logging.getLogger(__name__)


def _get_supabase():
    """Get Supabase client, or None if not configured."""
    try:
        from backend.supabase_client import get_supabase
        return get_supabase()
    except Exception:
        return None


# ═══════════════════════════════════════════════════════
# TOOL: list_published_assessments
# ═══════════════════════════════════════════════════════

def list_published_assessments_tool(content_type=None, teacher_id='local-dev'):
    """List all published assessments/assignments for this teacher.

    Args:
        content_type: Optional filter — 'assessment' or 'assignment'.
        teacher_id: Injected by assistant routes.

    Returns:
        dict with 'assessments' list and 'total' count, or 'error'.
    """
    require_teacher_id(teacher_id)
    sb = _get_supabase()
    if not sb:
        return {"error": "Assessment results require Supabase. Not available in local-dev mode."}

    try:
        result = sb.table('published_assessments').select(
            'id, join_code, title, created_at, submission_count, is_active, settings'
        ).eq('teacher_id', teacher_id).order('created_at', desc=True).execute()

        assessments = []
        for a in (result.data or []):
            settings = a.get('settings') or {}
            a_type = settings.get('content_type', 'assessment')

            if content_type and a_type != content_type:
                continue

            assessments.append({
                "title": a.get('title', ''),
                "join_code": a.get('join_code', ''),
                "created_at": a.get('created_at', ''),
                "submission_count": a.get('submission_count', 0),
                "is_active": a.get('is_active', True),
                "content_type": a_type,
                "period": settings.get('period', ''),
            })

        return {"assessments": assessments, "total": len(assessments)}

    except Exception as e:
        logger.exception("list_published_assessments_tool failed")
        return {"error": f"Failed to load assessments: {e}"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assessment_tools.py::TestListPublishedAssessments -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add backend/services/assistant_tools_assessments.py tests/test_assessment_tools.py
git commit -m "feat: add list_published_assessments assistant tool for portal results"
```

---

### Task 2: Add `query_assessment_results` tool

**Files:**
- Modify: `backend/services/assistant_tools_assessments.py`
- Modify: `tests/test_assessment_tools.py`

- [ ] **Step 1: Write failing tests for `query_assessment_results`**

Append to `tests/test_assessment_tools.py`:

```python
def _mock_supabase_with_submissions(assessments_data, submissions_data):
    """Create a mock Supabase that returns assessments then submissions."""
    mock_sb = MagicMock()

    # First call: published_assessments query
    mock_assessments_result = MagicMock()
    mock_assessments_result.data = assessments_data

    # Second call: submissions query
    mock_submissions_result = MagicMock()
    mock_submissions_result.data = submissions_data

    # Chain: table('published_assessments').select().eq().execute()
    # then:  table('submissions').select().eq().order().execute()
    call_count = {"n": 0}
    original_table = mock_sb.table

    def table_router(name):
        mock_table = MagicMock()
        if name == 'published_assessments':
            mock_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_assessments_result
            # Also handle .ilike chain
            mock_table.select.return_value.eq.return_value.ilike.return_value.execute.return_value = mock_assessments_result
        elif name == 'submissions':
            mock_table.select.return_value.eq.return_value.order.return_value.execute.return_value = mock_submissions_result
        return mock_table

    mock_sb.table = table_router
    return mock_sb


class TestQueryAssessmentResults:
    def test_returns_summary_for_assessment(self):
        """Should return score summary and submission list for a named assessment."""
        from backend.services.assistant_tools_assessments import query_assessment_results

        assessments = [
            {"id": "uuid-1", "join_code": "ABC123", "title": "Unit 3 Quiz",
             "settings": {"content_type": "assessment"}},
        ]
        submissions = [
            {"id": "s1", "student_name": "Alice Smith", "score": 85,
             "total_points": 100, "percentage": 85.0,
             "submitted_at": "2026-03-20T10:00:00", "results": None},
            {"id": "s2", "student_name": "Bob Jones", "score": 72,
             "total_points": 100, "percentage": 72.0,
             "submitted_at": "2026-03-20T10:05:00", "results": None},
            {"id": "s3", "student_name": "Carol Davis", "score": 95,
             "total_points": 100, "percentage": 95.0,
             "submitted_at": "2026-03-20T10:10:00", "results": None},
        ]

        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_submissions(assessments, submissions)
            result = query_assessment_results(assessment_name="Unit 3", teacher_id="teacher-1")

        assert "assessment" in result
        assert result["assessment"]["title"] == "Unit 3 Quiz"
        assert result["summary"]["total_submissions"] == 3
        assert result["summary"]["average_score"] == 84.0
        assert result["summary"]["highest_score"] == 95.0
        assert result["summary"]["lowest_score"] == 72.0
        assert len(result["submissions"]) == 3

    def test_returns_error_when_not_found(self):
        """Should return error when no matching assessment exists."""
        from backend.services.assistant_tools_assessments import query_assessment_results

        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_submissions([], [])
            result = query_assessment_results(assessment_name="Nonexistent", teacher_id="teacher-1")

        assert "error" in result

    def test_returns_by_join_code(self):
        """Should accept join_code as an alternative to assessment_name."""
        from backend.services.assistant_tools_assessments import query_assessment_results

        assessments = [
            {"id": "uuid-1", "join_code": "XYZ789", "title": "Pop Quiz",
             "settings": {}},
        ]
        submissions = [
            {"id": "s1", "student_name": "Alice", "score": 90,
             "total_points": 100, "percentage": 90.0,
             "submitted_at": "2026-03-20T10:00:00", "results": None},
        ]

        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_submissions(assessments, submissions)
            result = query_assessment_results(join_code="XYZ789", teacher_id="teacher-1")

        assert result["assessment"]["join_code"] == "XYZ789"
        assert result["summary"]["total_submissions"] == 1

    def test_filters_by_min_score(self):
        """Should filter submissions by min_score."""
        from backend.services.assistant_tools_assessments import query_assessment_results

        assessments = [
            {"id": "uuid-1", "join_code": "ABC123", "title": "Test",
             "settings": {}},
        ]
        submissions = [
            {"id": "s1", "student_name": "Alice", "score": 90,
             "total_points": 100, "percentage": 90.0,
             "submitted_at": "2026-03-20T10:00:00", "results": None},
            {"id": "s2", "student_name": "Bob", "score": 60,
             "total_points": 100, "percentage": 60.0,
             "submitted_at": "2026-03-20T10:00:00", "results": None},
        ]

        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_submissions(assessments, submissions)
            result = query_assessment_results(
                assessment_name="Test", min_score=70, teacher_id="teacher-1"
            )

        assert len(result["submissions"]) == 1
        assert result["submissions"][0]["student_name"] == "Alice"

    def test_handles_no_submissions(self):
        """Should return zero-submission summary when assessment has no submissions."""
        from backend.services.assistant_tools_assessments import query_assessment_results

        assessments = [
            {"id": "uuid-1", "join_code": "ABC123", "title": "Empty Test",
             "settings": {}},
        ]

        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_submissions(assessments, [])
            result = query_assessment_results(assessment_name="Empty", teacher_id="teacher-1")

        assert result["summary"]["total_submissions"] == 0
        assert result["summary"]["average_score"] is None

    def test_grade_distribution(self):
        """Should compute letter grade distribution from percentages."""
        from backend.services.assistant_tools_assessments import query_assessment_results

        assessments = [
            {"id": "uuid-1", "join_code": "ABC123", "title": "Test",
             "settings": {}},
        ]
        submissions = [
            {"id": "s1", "student_name": "A-student", "score": 95,
             "total_points": 100, "percentage": 95.0,
             "submitted_at": "2026-03-20T10:00:00", "results": None},
            {"id": "s2", "student_name": "B-student", "score": 85,
             "total_points": 100, "percentage": 85.0,
             "submitted_at": "2026-03-20T10:00:00", "results": None},
            {"id": "s3", "student_name": "C-student", "score": 75,
             "total_points": 100, "percentage": 75.0,
             "submitted_at": "2026-03-20T10:00:00", "results": None},
            {"id": "s4", "student_name": "F-student", "score": 50,
             "total_points": 100, "percentage": 50.0,
             "submitted_at": "2026-03-20T10:00:00", "results": None},
        ]

        with patch('backend.services.assistant_tools_assessments._get_supabase') as mock_get:
            mock_get.return_value = _mock_supabase_with_submissions(assessments, submissions)
            result = query_assessment_results(assessment_name="Test", teacher_id="teacher-1")

        dist = result["summary"]["grade_distribution"]
        assert dist["A"] == 1
        assert dist["B"] == 1
        assert dist["C"] == 1
        assert dist["F"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assessment_tools.py::TestQueryAssessmentResults -v`
Expected: FAIL with `ImportError: cannot import name 'query_assessment_results'`

- [ ] **Step 3: Implement `query_assessment_results`**

Append to `backend/services/assistant_tools_assessments.py`:

```python
# ═══════════════════════════════════════════════════════
# TOOL: query_assessment_results
# ═══════════════════════════════════════════════════════

def _pct_to_letter(pct):
    """Convert a percentage to a letter grade."""
    if pct is None:
        return "N/A"
    if pct >= 90:
        return "A"
    if pct >= 80:
        return "B"
    if pct >= 70:
        return "C"
    if pct >= 60:
        return "D"
    return "F"


def query_assessment_results(assessment_name=None, join_code=None,
                              min_score=None, max_score=None,
                              student_name=None,
                              teacher_id='local-dev'):
    """Query results for a published assessment/assignment.

    Looks up the assessment by name (fuzzy) or join code, then fetches
    all submissions and computes summary statistics.

    Args:
        assessment_name: Assessment title to search for (partial match, case-insensitive).
        join_code: Exact 6-character join code (alternative to assessment_name).
        min_score: Only include submissions with percentage >= this value.
        max_score: Only include submissions with percentage <= this value.
        student_name: Filter to a specific student (partial match, case-insensitive).
        teacher_id: Injected by assistant routes.

    Returns:
        dict with 'assessment' info, 'summary' stats, and 'submissions' list.
    """
    require_teacher_id(teacher_id)
    sb = _get_supabase()
    if not sb:
        return {"error": "Assessment results require Supabase. Not available in local-dev mode."}

    if not assessment_name and not join_code:
        return {"error": "Provide either assessment_name or join_code to look up results."}

    try:
        # ── Find the assessment ──
        if join_code:
            query = sb.table('published_assessments').select(
                'id, join_code, title, settings'
            ).eq('teacher_id', teacher_id).eq('join_code', join_code.upper())
        else:
            query = sb.table('published_assessments').select(
                'id, join_code, title, settings'
            ).eq('teacher_id', teacher_id).ilike('title', f'%{assessment_name}%')

        assessment_result = query.execute()

        if not assessment_result.data:
            search_term = join_code or assessment_name
            return {"error": f"No published assessment found matching '{search_term}'."}

        # Use first match
        assessment = assessment_result.data[0]
        code = assessment['join_code']

        # ── Fetch submissions ──
        subs_result = sb.table('submissions').select(
            'id, student_name, score, total_points, percentage, submitted_at, results'
        ).eq('join_code', code).order('submitted_at', desc=True).execute()

        submissions = subs_result.data or []

        # ── Apply filters ──
        if student_name:
            student_lower = student_name.lower()
            submissions = [s for s in submissions if student_lower in (s.get('student_name') or '').lower()]

        if min_score is not None:
            submissions = [s for s in submissions if (s.get('percentage') or 0) >= min_score]

        if max_score is not None:
            submissions = [s for s in submissions if (s.get('percentage') or 0) <= max_score]

        # ── Compute summary stats ──
        percentages = [s['percentage'] for s in submissions if s.get('percentage') is not None]

        if percentages:
            avg = round(sum(percentages) / len(percentages), 1)
            highest = max(percentages)
            lowest = min(percentages)
        else:
            avg = None
            highest = None
            lowest = None

        # Grade distribution
        grade_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        for pct in percentages:
            grade_dist[_pct_to_letter(pct)] += 1

        # ── Format submissions ──
        formatted = []
        for s in submissions:
            formatted.append({
                "student_name": s.get('student_name', ''),
                "score": s.get('score'),
                "total_points": s.get('total_points'),
                "percentage": s.get('percentage'),
                "letter_grade": _pct_to_letter(s.get('percentage')),
                "submitted_at": s.get('submitted_at', ''),
            })

        settings = assessment.get('settings') or {}

        return {
            "assessment": {
                "title": assessment.get('title', ''),
                "join_code": code,
                "content_type": settings.get('content_type', 'assessment'),
                "period": settings.get('period', ''),
            },
            "summary": {
                "total_submissions": len(submissions),
                "average_score": avg,
                "highest_score": highest,
                "lowest_score": lowest,
                "grade_distribution": grade_dist,
            },
            "submissions": formatted,
        }

    except Exception as e:
        logger.exception("query_assessment_results failed")
        return {"error": f"Failed to query assessment results: {e}"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assessment_tools.py -v`
Expected: All 10 tests PASS (4 from Task 1 + 6 new)

- [ ] **Step 5: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add backend/services/assistant_tools_assessments.py tests/test_assessment_tools.py
git commit -m "feat: add query_assessment_results assistant tool with stats and filtering"
```

---

### Task 3: Add tool definitions and register the submodule

**Files:**
- Modify: `backend/services/assistant_tools_assessments.py`
- Modify: `backend/services/assistant_tools.py:884-898`
- Modify: `tests/test_tool_schemas.py:48-50`

- [ ] **Step 1: Add tool definitions and handlers export**

Append to `backend/services/assistant_tools_assessments.py`:

```python
# ═══════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════

ASSESSMENT_TOOL_DEFINITIONS = [
    {
        "name": "list_published_assessments",
        "description": "List all published assessments and assignments from the student portal. Shows title, join code, submission count, active status, and content type. Use when the teacher asks 'what assessments have I published?' or 'show my portal assignments'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content_type": {
                    "type": "string",
                    "description": "Filter by type: 'assessment' or 'assignment' (omit for both)"
                }
            }
        }
    },
    {
        "name": "query_assessment_results",
        "description": "Get results and statistics for a published assessment or assignment from the student portal. Shows per-student scores, class average, grade distribution, highest/lowest scores. Search by title (partial match) or join code. Optionally filter by student name or score range. Use when the teacher asks 'how did my class do on X?', 'who failed the quiz?', 'what was the average on the test?'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "assessment_name": {
                    "type": "string",
                    "description": "Assessment/assignment title to search for (partial match, case-insensitive)"
                },
                "join_code": {
                    "type": "string",
                    "description": "Exact 6-character join code (alternative to assessment_name)"
                },
                "min_score": {
                    "type": "number",
                    "description": "Only include submissions with percentage >= this value"
                },
                "max_score": {
                    "type": "number",
                    "description": "Only include submissions with percentage <= this value"
                },
                "student_name": {
                    "type": "string",
                    "description": "Filter to a specific student (partial match)"
                }
            }
        }
    },
]


# ═══════════════════════════════════════════════════════
# TOOL HANDLERS
# ═══════════════════════════════════════════════════════

ASSESSMENT_TOOL_HANDLERS = {
    "list_published_assessments": list_published_assessments_tool,
    "query_assessment_results": query_assessment_results,
}
```

- [ ] **Step 2: Register the submodule in `_merge_submodules()`**

In `backend/services/assistant_tools.py`, find the `submodules` list inside `_merge_submodules()` (~line 884-898) and add this entry after the last item (`assistant_tools_survey`):

```python
        ("backend.services.assistant_tools_assessments", "ASSESSMENT_TOOL_DEFINITIONS", "ASSESSMENT_TOOL_HANDLERS"),
```

The full line in context:

```python
        ("backend.services.assistant_tools_survey", "SURVEY_TOOL_DEFINITIONS", "SURVEY_TOOL_HANDLERS"),
        ("backend.services.assistant_tools_assessments", "ASSESSMENT_TOOL_DEFINITIONS", "ASSESSMENT_TOOL_HANDLERS"),
    ]
```

- [ ] **Step 3: Update expected tool count in test_tool_schemas.py**

In `tests/test_tool_schemas.py`, find `test_tool_count` (~line 48-50) and update the expected count:

```python
def test_tool_count():
    """Verify we have the expected number of tools (previous + 2 assessment tools)."""
    assert len(at.TOOL_DEFINITIONS) >= 56, f"Expected >= 56 tools, got {len(at.TOOL_DEFINITIONS)}"
```

- [ ] **Step 4: Run the schema validation tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_tool_schemas.py -v`
Expected: All 6 tests PASS (including updated tool count)

- [ ] **Step 5: Run full assessment tools test suite**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assessment_tools.py tests/test_tool_schemas.py -v`
Expected: All tests PASS

- [ ] **Step 6: Search-based verification — tools are registered**

```bash
cd /Users/alexc/Downloads/Graider
source venv/bin/activate
python -c "
from backend.services.assistant_tools import TOOL_DEFINITIONS, TOOL_HANDLERS
names = [t['name'] for t in TOOL_DEFINITIONS]
assert 'list_published_assessments' in names, 'list_published_assessments not registered'
assert 'query_assessment_results' in names, 'query_assessment_results not registered'
assert 'list_published_assessments' in TOOL_HANDLERS, 'list_published_assessments handler missing'
assert 'query_assessment_results' in TOOL_HANDLERS, 'query_assessment_results handler missing'
print(f'OK — {len(TOOL_DEFINITIONS)} tools registered, both assessment tools present')
"
```

- [ ] **Step 7: Commit**

```bash
cd /Users/alexc/Downloads/Graider
git add backend/services/assistant_tools_assessments.py backend/services/assistant_tools.py tests/test_tool_schemas.py
git commit -m "feat: register assessment tools in assistant tool framework"
```

---

## Summary

| Task | What | Files | Risk |
|------|------|-------|------|
| 1 | `list_published_assessments_tool` + 4 tests | Create 2 new files | None — new files only |
| 2 | `query_assessment_results` + 6 tests | Modify new file | None — new file only |
| 3 | Tool definitions + registration | Modify `assistant_tools.py` (1 line), `test_tool_schemas.py` (1 line) | Very low — append only |

**Total: 2 new tools, 10 tests, 1 new file, 2 modified files.**

**Before:** Teacher asks "How did my class do on the Unit 3 quiz?" → assistant has no tool to answer.
**After:** Assistant calls `query_assessment_results(assessment_name="Unit 3")` → returns average 84%, grade distribution, per-student scores.

**What teachers can now ask:**
- "How did my class do on the Unit 3 quiz?"
- "Who failed the Chapter 5 test?"
- "What was the average on the pop quiz?"
- "Show me all my published assessments"
- "How did Alice do on the vocabulary test?"
- "Which students scored below 70 on the final?"
