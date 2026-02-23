# Implementation Edit Plan: 23 New Assistant Tools + Test Suite

## Overview
- **5 new submodule files** in `backend/services/`
- **1 edit** to `backend/services/assistant_tools.py` (merge imports at bottom)
- **1 edit** to `backend/routes/assistant_routes.py` (system prompt additions)
- **Test infrastructure**: `tests/` directory with fixtures and test files

---

## PART 1: New Files to Create

### File 1: `backend/services/assistant_tools_edtech.py`

**Purpose**: 6 EdTech quiz generator tools
**Tools**: `generate_kahoot_quiz`, `generate_blooket_set`, `generate_gimkit_kit`, `generate_quizlet_set`, `generate_nearpod_questions`, `generate_canvas_qti`

**Shared helper**: `_build_questions_from_source(topic, assignment_name, content, question_count, difficulty, period)` — generates questions deterministically from standards vocab, sample_assessments, and grade data. Zero AI calls.

**Key imports needed from main module**:
```python
from backend.services.assistant_tools import (
    _load_standards, _load_master_csv, _load_results, _load_settings,
    _normalize_period, _fuzzy_name_match, SETTINGS_FILE
)
```

---

### File 2: `backend/services/assistant_tools_analytics.py`

**Purpose**: 4 analytics tools
**Tools**: `get_grade_trends`, `get_rubric_weakness`, `flag_at_risk_students`, `compare_assignments`

**Key imports from main module**:
```python
from backend.services.assistant_tools import (
    _load_master_csv, _load_results, _normalize_period,
    _fuzzy_name_match, _safe_int_score, _normalize_assignment_name,
    _load_accommodations, RESULTS_FILE
)
```

---

### File 3: `backend/services/assistant_tools_planning.py`

**Purpose**: 7 planning & classroom tools
**Tools**: `suggest_remediation`, `align_to_standards`, `get_pacing_status`, `generate_bell_ringer`, `generate_exit_ticket`, `suggest_grouping`, `generate_sub_plans`

**Key imports from main module**:
```python
from backend.services.assistant_tools import (
    _load_standards, _load_master_csv, _load_settings, _load_calendar,
    _normalize_period, _fuzzy_name_match, _load_roster,
    _load_saved_lessons, CALENDAR_FILE, LESSONS_DIR, SETTINGS_FILE
)
```

---

### File 4: `backend/services/assistant_tools_communication.py`

**Purpose**: 4 communication & reporting tools
**Tools**: `generate_progress_report`, `generate_report_card_comments`, `draft_student_feedback`, `generate_parent_conference_notes`

**Key imports from main module**:
```python
from backend.services.assistant_tools import (
    _load_master_csv, _load_results, _load_settings, _load_roster,
    _load_accommodations, _fuzzy_name_match, _safe_int_score,
    _normalize_period, _extract_first_name, PARENT_CONTACTS_FILE
)
```

---

### File 5: `backend/services/assistant_tools_student.py`

**Purpose**: 2 student info tools
**Tools**: `get_student_accommodations`, `get_student_streak`

**Key imports from main module**:
```python
from backend.services.assistant_tools import (
    _load_master_csv, _load_accommodations, _load_roster,
    _fuzzy_name_match, _safe_int_score, ACCOMMODATIONS_DIR
)
```

---

## PART 2: Edit to `backend/services/assistant_tools.py`

**Location**: After the existing `TOOL_HANDLERS` dict (line ~3547) and before `execute_tool()` (line 3550)

**What to add**: Import and merge submodule definitions + handlers

```python
# ═══════════════════════════════════════════════════════
# MERGE SUBMODULE TOOLS
# ═══════════════════════════════════════════════════════
try:
    from backend.services.assistant_tools_edtech import EDTECH_TOOL_DEFINITIONS, EDTECH_TOOL_HANDLERS
    TOOL_DEFINITIONS.extend(EDTECH_TOOL_DEFINITIONS)
    TOOL_HANDLERS.update(EDTECH_TOOL_HANDLERS)
except ImportError:
    pass

try:
    from backend.services.assistant_tools_analytics import ANALYTICS_TOOL_DEFINITIONS, ANALYTICS_TOOL_HANDLERS
    TOOL_DEFINITIONS.extend(ANALYTICS_TOOL_DEFINITIONS)
    TOOL_HANDLERS.update(ANALYTICS_TOOL_HANDLERS)
except ImportError:
    pass

try:
    from backend.services.assistant_tools_planning import PLANNING_TOOL_DEFINITIONS, PLANNING_TOOL_HANDLERS
    TOOL_DEFINITIONS.extend(PLANNING_TOOL_DEFINITIONS)
    TOOL_HANDLERS.update(PLANNING_TOOL_HANDLERS)
except ImportError:
    pass

try:
    from backend.services.assistant_tools_communication import COMMUNICATION_TOOL_DEFINITIONS, COMMUNICATION_TOOL_HANDLERS
    TOOL_DEFINITIONS.extend(COMMUNICATION_TOOL_DEFINITIONS)
    TOOL_HANDLERS.update(COMMUNICATION_TOOL_HANDLERS)
except ImportError:
    pass

try:
    from backend.services.assistant_tools_student import STUDENT_TOOL_DEFINITIONS, STUDENT_TOOL_HANDLERS
    TOOL_DEFINITIONS.extend(STUDENT_TOOL_DEFINITIONS)
    TOOL_HANDLERS.update(STUDENT_TOOL_HANDLERS)
except ImportError:
    pass
```

---

## PART 3: System Prompt Edit in `assistant_routes.py`

**Location**: `_build_system_prompt()` — after the existing "Available tools:" section (line ~768, before the closing `"""`).

**Insert before the closing triple-quote** of the prompt string, after the STANDARDS & RESOURCES paragraph:

```
EDTECH QUIZ GENERATORS (zero-cost, no AI API calls):
- generate_kahoot_quiz: Create Kahoot-compatible .xlsx quiz from standards/grades/content
- generate_blooket_set: Create Blooket-compatible .csv question set
- generate_gimkit_kit: Create Gimkit-compatible .csv kit (Question, Correct Answer, Incorrect 1-3)
- generate_quizlet_set: Create Quizlet-compatible .txt flashcard set (tab-separated term/definition)
- generate_nearpod_questions: Create formatted .docx with questions for Nearpod copy-paste
- generate_canvas_qti: Create Canvas QTI 1.2 .xml for LMS import

When asked to create a quiz for Kahoot, Blooket, Gimkit, Quizlet, Nearpod, or Canvas, use the corresponding generate_* tool. These pull from standards vocabulary, sample assessments, and grade data — zero cost, no AI API needed.

ADVANCED ANALYTICS:
- get_grade_trends: Track student/class scores over time with direction (improving/declining/stable)
- get_rubric_weakness: Find consistently weakest rubric categories across ALL assignments
- flag_at_risk_students: Combine declining trends + missing work + low categories into risk scores. Use when asked "who should I be worried about?"
- compare_assignments: Side-by-side stats for two assignments (mean, median, distribution shifts)

PLANNING & CLASSROOM:
- suggest_remediation: Map weaknesses to activities using teacher's enabled edtech tools
- align_to_standards: Show which standards a topic covers and which remain unassessed
- get_pacing_status: Compare calendar progress vs total standards — ahead/behind/on-track
- generate_bell_ringer: Quick warm-up from yesterday's lesson vocab/standards
- generate_exit_ticket: 2-3 check questions from today's lesson/standard
- suggest_grouping: Create student groups by performance (heterogeneous or homogeneous)
- generate_sub_plans: Build substitute teacher plans from calendar + saved lessons → Word doc

COMMUNICATION & REPORTING:
- generate_progress_report: Printable student progress report → Word doc
- generate_report_card_comments: Template-based comments from score patterns (NOT AI-generated)
- draft_student_feedback: Structured feedback with strengths, growth areas, examples from history
- generate_parent_conference_notes: Conference agenda with data, talking points → Word doc

STUDENT INFO:
- get_student_accommodations: Pull specific IEP/504 presets, notes, grading impact for a student
- get_student_streak: Show consecutive improvement/decline streaks with assignment history
```

---

## PART 4: Test Infrastructure

### `tests/__init__.py`
Empty file.

### `tests/conftest.py`
Monkeypatches all file path constants to point to `tests/fixtures/` temp copies. Key fixtures:
- `mock_data_dir` — tmpdir with fixture copies
- `patch_paths` — monkeypatches RESULTS_FILE, SETTINGS_FILE, etc.
- `sample_grades` — returns parsed grade rows
- `sample_standards` — returns parsed standards list

### `tests/fixtures/`
- `master_grades.csv` — 20 fake students, 3 assignments, 3 periods
- `results.json` — matching detailed results
- `standards_fl_civics.json` — copy of real standards (no PII)
- `settings.json` — mock teacher config
- `roster_period_1.csv`, `roster_period_2.csv` — fake rosters
- `period_meta.json` — class level metadata
- `accommodations.json` — sample IEP/504 data
- `calendar.json` — sample teaching calendar
- `parent_contacts.json` — mock contacts
- `memories.json` — sample saved facts

### Test Files
- `test_tool_schemas.py` — validate TOOL_DEFINITIONS structure + handler coverage
- `test_helpers.py` — fuzzy matching, normalization, data loading
- `test_edtech_tools.py` — quiz generators produce valid output formats
- `test_analytics_tools.py` — trends, risk flags, comparisons
- `test_planning_tools.py` — bell ringers, exit tickets, grouping
- `test_communication_tools.py` — report generation, comments
- `test_student_tools.py` — accommodations, streaks
- `test_system_prompt.py` — all tools referenced in prompt

---

## Implementation Order

1. Create `tests/` skeleton + fixtures + conftest.py
2. Create `test_tool_schemas.py` + `test_helpers.py`
3. Create `assistant_tools_student.py` (simplest, 2 tools)
4. Create `assistant_tools_analytics.py` (4 tools)
5. Create `assistant_tools_edtech.py` (6 tools, most complex)
6. Create `assistant_tools_planning.py` (7 tools)
7. Create `assistant_tools_communication.py` (4 tools)
8. Edit `assistant_tools.py` — add merge imports
9. Edit `assistant_routes.py` — add system prompt tool descriptions
10. Create remaining test files
11. Run `pytest tests/ -v`
