# FERPA/Clever Compliance for Assistant Tools — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all 80 assistant tools FERPA and Clever compliant with teacher-scoped data access, audit logging, PII anonymization for AI calls, and zero local PII file writes.

**Architecture:** Centralized compliance module (`backend/utils/compliance.py`) provides `audit_tool_action()`, `anonymize_for_ai()`, and `require_teacher_id()`. Extract `audit_log()` from `app.py` into `backend/utils/audit.py`. Fix `_load_master_csv()` and `_load_roster()` to use teacher-scoped storage. Update all tool handlers to accept and pass `teacher_id`.

**Tech Stack:** Python/Flask, Supabase (teacher_data table), existing storage.py abstraction

**Spec:** `docs/superpowers/specs/2026-03-22-assistant-tools-ferpa-compliance-design.md`

---

## File Structure

### New files
- `backend/utils/audit.py` — Extracted `audit_log()` function from `app.py`
- `backend/utils/compliance.py` — `require_teacher_id()`, `audit_tool_action()`, `anonymize_for_ai()`, `deanonymize()`
- `tests/test_compliance.py` — Tests for compliance module

### Modified files
- `backend/app.py` — Remove `audit_log()`, import from `backend/utils/audit.py`
- `backend/services/assistant_tools.py` — Fix `_load_master_csv()`, `_load_roster()`, add `INVOKE` audit in `execute_tool()`
- `backend/services/assistant_tools_grading.py` — Add `teacher_id` to 9 handlers
- `backend/services/assistant_tools_analytics.py` — Add `teacher_id` to 6 handlers
- `backend/services/assistant_tools_communication.py` — Add `teacher_id` to 3 handlers
- `backend/services/assistant_tools_planning.py` — Add `teacher_id` to 12 handlers
- `backend/services/assistant_tools_reports.py` — Add `teacher_id`, eliminate local file writes
- `backend/services/assistant_tools_student.py` — Add `teacher_id`, eliminate local exports
- `backend/services/assistant_tools_data.py` — Add `teacher_id` to `save_memory`
- `backend/services/assistant_tools_ai.py` — Add `teacher_id`, anonymize AI calls
- `backend/services/assistant_tools_behavior.py` — Add audit logging, anonymize AI calls
- `backend/services/assistant_tools_survey.py` — Add `teacher_id` scoping
- `backend/services/assistant_tools_automation.py` — Add `teacher_id` scoping
- `backend/storage.py` — Extend `sync_all_to_cloud()` for `pending_send` and `automations`
- `tests/test_tool_schemas.py` — Add teacher_id signature verification

---

### Task 1: Extract `audit_log()` into `backend/utils/audit.py`

**Files:**
- Create: `backend/utils/audit.py`
- Modify: `backend/app.py:217-246`
- Test: `tests/test_compliance.py`

- [ ] **Step 1: Create `backend/utils/audit.py`**

Move the `audit_log()` function from `app.py` (lines 217-246) into its own module. Preserve the exact same behavior including the `g.user_id` fallback.

**IMPORTANT:** Check which import form `app.py` currently uses for `supabase_client` — it uses `from supabase_client import get_supabase` (bare import, not `backend.supabase_client`). The extracted module must use a try/except to handle both import paths since it runs from `backend/utils/` not `backend/`.

**Behavioral note:** The local file write now truncates `details` to 500 chars (matching Supabase). The original `app.py` only truncated for Supabase — this is an intentional improvement for consistency.

```python
"""
FERPA Compliance Audit Logging
==============================
Dual-writes audit entries to local file + Supabase.
Extracted from app.py to avoid circular imports when used by compliance utilities.
"""

import os
import logging
from datetime import datetime

AUDIT_LOG_FILE = os.path.expanduser("~/.graider_audit.log")
logger = logging.getLogger(__name__)


def audit_log(action: str, details: str = "", user: str = "teacher", teacher_id: str = ""):
    """FERPA Compliance: Log all data access and modifications."""
    timestamp = datetime.now().isoformat()

    # Resolve teacher_id — prefer explicit, fall back to Flask g.user_id
    resolved_teacher_id = teacher_id
    if not resolved_teacher_id:
        try:
            from flask import g
            resolved_teacher_id = getattr(g, 'user_id', 'unknown')
        except (ImportError, RuntimeError):
            resolved_teacher_id = 'unknown'

    # Local file (immediate, always works)
    try:
        log_entry = f"{timestamp} | {user} | {action} | {details[:500]}\n"
        with open(AUDIT_LOG_FILE, 'a') as f:
            f.write(log_entry)
    except Exception:
        pass

    # Supabase (persistent across deploys)
    try:
        try:
            from backend.supabase_client import get_supabase
        except ImportError:
            from supabase_client import get_supabase
        sb = get_supabase()
        if sb:
            sb.table('audit_log').insert({
                'timestamp': timestamp,
                'teacher_id': resolved_teacher_id,
                'action': action,
                'details': details[:500],
                'user_type': user,
            }).execute()
    except Exception:
        pass
```

- [ ] **Step 2: Update `app.py` to import from `audit.py`**

Replace the inline `audit_log()` function in `app.py` (lines 217-246) with:

```python
from backend.utils.audit import audit_log
```

Keep the `AUDIT_LOG_FILE` constant and `get_audit_logs()` function in `app.py` (they're used for the FERPA data summary endpoint).

- [ ] **Step 3: Verify app still starts**

Run: `cd /Users/alexc/Downloads/Graider/backend && source /Users/alexc/Downloads/Graider/venv/bin/activate && python -c "import app; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Run existing tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_tool_schemas.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add backend/utils/audit.py backend/app.py
git commit -m "refactor: extract audit_log() to backend/utils/audit.py to avoid circular imports"
```

---

### Task 2: Create compliance module (`backend/utils/compliance.py`)

**Files:**
- Create: `backend/utils/compliance.py`
- Create: `tests/test_compliance.py`

- [ ] **Step 1: Write failing tests for `require_teacher_id`**

```python
"""Tests for backend/utils/compliance.py"""
import pytest
from unittest.mock import patch


class TestRequireTeacherId:
    def test_blocks_none(self):
        from backend.utils.compliance import require_teacher_id
        with pytest.raises(ValueError, match="teacher_id"):
            require_teacher_id(None)

    def test_blocks_empty(self):
        from backend.utils.compliance import require_teacher_id
        with pytest.raises(ValueError, match="teacher_id"):
            require_teacher_id("")

    @patch('backend.utils.compliance._is_supabase_configured', return_value=True)
    def test_blocks_local_dev_in_prod(self, mock_sb):
        from backend.utils.compliance import require_teacher_id
        with pytest.raises(ValueError, match="local-dev"):
            require_teacher_id("local-dev")

    @patch('backend.utils.compliance._is_supabase_configured', return_value=False)
    def test_allows_local_dev_in_dev(self, mock_sb):
        from backend.utils.compliance import require_teacher_id
        require_teacher_id("local-dev")  # Should not raise

    def test_allows_real_teacher_id(self):
        from backend.utils.compliance import require_teacher_id
        require_teacher_id("teacher-abc-123")  # Should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_compliance.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Write failing tests for `anonymize_for_ai` and `deanonymize`**

Add to `tests/test_compliance.py`:

```python
class TestAnonymizeForAi:
    def test_roundtrip(self):
        from backend.utils.compliance import anonymize_for_ai, deanonymize
        roster = [{"student_name": "Maria Garcia"}, {"student_name": "John Smith"}]
        text = "Maria Garcia scored 85%. John Smith needs improvement."
        anon, mapping = anonymize_for_ai(text, roster)
        assert "Maria Garcia" not in anon
        assert "John Smith" not in anon
        assert "[STUDENT_" in anon
        restored = deanonymize(anon, mapping)
        assert "Maria Garcia" in restored
        assert "John Smith" in restored

    def test_preserves_accommodation_types(self):
        from backend.utils.compliance import anonymize_for_ai
        roster = [{"student_name": "Maria Garcia"}]
        text = "Maria Garcia has IEP accommodations: extended time, large text."
        anon, _ = anonymize_for_ai(text, roster)
        assert "Maria Garcia" not in anon
        assert "extended time" in anon
        assert "large text" in anon

    def test_handles_last_first_format(self):
        from backend.utils.compliance import anonymize_for_ai
        roster = [{"student_name": "Garcia, Maria"}]
        text = "Garcia, Maria scored well. Maria Garcia improved."
        anon, _ = anonymize_for_ai(text, roster)
        assert "Garcia" not in anon
        assert "Maria" not in anon or "[STUDENT_" in anon

    def test_anonymizes_free_text_notes(self):
        from backend.utils.compliance import anonymize_for_ai
        roster = [{"student_name": "Maria Garcia"}]
        text = "Accommodation notes: Maria Garcia's mother requested extra time."
        anon, _ = anonymize_for_ai(text, roster)
        assert "Maria Garcia" not in anon

    @patch('backend.utils.compliance._is_supabase_configured', return_value=True)
    def test_requires_roster_in_prod(self, mock_sb):
        from backend.utils.compliance import anonymize_for_ai
        with pytest.raises(ValueError, match="roster"):
            anonymize_for_ai("Some text", roster=None)

    @patch('backend.utils.compliance._is_supabase_configured', return_value=False)
    def test_allows_no_roster_in_dev(self, mock_sb):
        from backend.utils.compliance import anonymize_for_ai
        anon, mapping = anonymize_for_ai("Some text with no names", roster=None)
        assert isinstance(anon, str)
        assert isinstance(mapping, dict)
```

- [ ] **Step 4: Write failing tests for `audit_tool_action`**

Add to `tests/test_compliance.py`:

```python
class TestAuditToolAction:
    @patch('backend.utils.compliance.audit_log')
    def test_formats_action_correctly(self, mock_audit):
        from backend.utils.compliance import audit_tool_action
        audit_tool_action("teacher-123", "query_grades", "INVOKE", "period=1st")
        mock_audit.assert_called_once()
        call_args = mock_audit.call_args
        assert "TOOL_query_grades_INVOKE" in call_args[0][0]
        assert call_args[1].get('teacher_id') == "teacher-123" or call_args[0][-1] == "teacher-123"

    @patch('backend.utils.compliance.audit_log')
    def test_strips_pii_from_details(self, mock_audit):
        from backend.utils.compliance import audit_tool_action
        audit_tool_action("teacher-123", "export", "EXPORT", "Exported data for Maria Garcia")
        call_args = mock_audit.call_args
        details = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get('details', '')
        assert "Maria Garcia" not in details
```

- [ ] **Step 5: Implement `backend/utils/compliance.py`**

```python
"""
FERPA/Clever Compliance Utilities
=================================
Centralized compliance primitives for assistant tools:
- require_teacher_id: Guard against unscoped data access
- audit_tool_action: Standardized audit logging for tool operations
- anonymize_for_ai / deanonymize: Strip/restore student PII for external AI calls
"""

import re
import os
import logging

logger = logging.getLogger(__name__)


def _is_supabase_configured():
    return bool(os.getenv('SUPABASE_URL') and os.getenv('SUPABASE_SERVICE_KEY'))


def require_teacher_id(teacher_id):
    """Guard: raise ValueError if teacher_id is missing or invalid in production."""
    if not teacher_id:
        raise ValueError("teacher_id is required for data access")
    if teacher_id == 'local-dev' and _is_supabase_configured():
        raise ValueError("local-dev teacher_id not allowed when Supabase is configured")


def audit_tool_action(teacher_id, tool_name, action, details=None):
    """Log a tool action to the FERPA audit trail.

    Actions: INVOKE, EXPORT, DELETE, SEND_EMAIL, SEND_AI, MODIFY_DATA
    """
    from backend.utils.audit import audit_log
    formatted_action = f"TOOL_{tool_name}_{action}"
    safe_details = _strip_pii_from_details(details or "")
    audit_log(formatted_action, safe_details, user="teacher", teacher_id=teacher_id)


def _strip_pii_from_details(details):
    """Remove potential student names from audit detail strings."""
    # Replace patterns like "for Maria Garcia" or "student Maria Garcia"
    # This is a best-effort strip — the audit log should never contain full names
    cleaned = re.sub(r'(?:for|student|name[=:])\s*[A-Z][a-z]+\s+[A-Z][a-z]+', 'student_***', details)
    return cleaned[:500]


def anonymize_for_ai(text, roster=None):
    """Replace student names with tokens before sending to external AI.

    Args:
        text: Text containing student PII
        roster: List of dicts with 'student_name' key. REQUIRED in production.

    Returns:
        (anonymized_text, mapping_dict) where mapping_dict maps tokens to real names
    """
    if roster is None:
        if _is_supabase_configured():
            raise ValueError("roster is required for anonymization in production mode")
        logger.warning("anonymize_for_ai called without roster in dev mode — limited anonymization")
        return text, {}

    mapping = {}
    anonymized = text
    counter = 1

    for student in roster:
        name = student.get('student_name', '')
        if not name:
            continue
        token = f"[STUDENT_{counter}]"

        # Handle "First Last" format
        if name in anonymized:
            anonymized = anonymized.replace(name, token)
            mapping[token] = name
            counter += 1
            continue

        # Handle "Last, First" format
        parts = [p.strip() for p in name.split(',')]
        if len(parts) == 2:
            reversed_name = f"{parts[1]} {parts[0]}"
            if reversed_name in anonymized:
                anonymized = anonymized.replace(reversed_name, token)
                mapping[token] = name
                counter += 1
                continue
            if name in anonymized:
                anonymized = anonymized.replace(name, token)
                mapping[token] = name
                counter += 1
                continue

        # Try individual name parts for possessives like "Maria's" or partial references
        name_parts = name.replace(',', '').split()
        found = False
        for part in name_parts:
            if len(part) > 2 and part in anonymized:
                anonymized = anonymized.replace(part, token)
                found = True
        if found and token not in mapping:
            mapping[token] = name
            counter += 1

    return anonymized, mapping


def deanonymize(text, mapping):
    """Restore student names from anonymization tokens."""
    result = text
    for token, name in mapping.items():
        result = result.replace(token, name)
    return result
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_compliance.py -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add backend/utils/compliance.py tests/test_compliance.py
git commit -m "feat: centralized FERPA compliance module — require_teacher_id, anonymize_for_ai, audit_tool_action"
```

---

### Task 3: Fix `_load_master_csv()` to use teacher-scoped storage

**Files:**
- Modify: `backend/services/assistant_tools.py:246-371`
- Test: `tests/test_compliance.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_compliance.py`:

```python
class TestLoadMasterCsvScoping:
    @patch('backend.services.assistant_tools.storage_load')
    def test_load_master_csv_passes_teacher_id(self, mock_load):
        mock_load.return_value = [{"student_name": "Test", "assignment": "Quiz", "score": 85}]
        from backend.services.assistant_tools import _load_master_csv
        _load_master_csv(teacher_id='teacher-abc')
        mock_load.assert_called()
        # Verify teacher_id was passed to storage_load
        calls = [c for c in mock_load.call_args_list if 'teacher' in str(c)]
        assert len(calls) > 0, "teacher_id not passed to storage_load"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_compliance.py::TestLoadMasterCsvScoping -v`
Expected: FAIL

- [ ] **Step 3: Update `_load_master_csv()` in `assistant_tools.py`**

Modify the function signature from `_load_master_csv(period_filter='all')` to `_load_master_csv(period_filter='all', teacher_id='local-dev')`.

In the function body:

**For the Supabase branch** (when `teacher_id != 'local-dev'` and Supabase is configured):
Skip the local CSV read entirely. Build the list of dicts from `_load_results(teacher_id)` with this field mapping:

```python
# _load_results returns dicts with these fields from the grading engine:
#   student_name, assignment_name, total_score, total_points, letter_grade,
#   sections, feedback, period, date, etc.
#
# Downstream callers expect these fields:
#   student_name, student_id, assignment, score, letter_grade, period,
#   quarter, date, content, completeness, writing, effort, first_name
#
# Field mapping:
results = _load_results(teacher_id)
rows = []
for r in results:
    rows.append({
        'student_name': r.get('student_name', ''),
        'student_id': r.get('student_id', r.get('student_name', '')[:6]),
        'first_name': r.get('student_name', '').split()[0] if r.get('student_name') else '',
        'assignment': r.get('assignment_name', r.get('title', '')),
        'score': _safe_int_score(r.get('total_score', 0)),
        'letter_grade': r.get('letter_grade', ''),
        'period': r.get('period', ''),
        'quarter': r.get('quarter', ''),
        'date': r.get('date', r.get('graded_at', '')),
        'content': _safe_int_score(r.get('content', 0)),
        'completeness': _safe_int_score(r.get('completeness', 0)),
        'writing': _safe_int_score(r.get('writing', 0)),
        'effort': _safe_int_score(r.get('effort', 0)),
    })
```

**For the dev-mode fallback** (when `teacher_id == 'local-dev'`):
Keep the existing CSV-reading logic, but fix the `_load_results()` merge call at line ~302 to pass `teacher_id`:
```python
# BEFORE (broken):
json_results = _load_results()
# AFTER (fixed):
json_results = _load_results(teacher_id)
```

Apply `period_filter` to both branches as the existing code does.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_compliance.py tests/test_tool_schemas.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add backend/services/assistant_tools.py tests/test_compliance.py
git commit -m "fix: _load_master_csv uses teacher-scoped storage instead of shared CSV"
```

---

### Task 4: Fix `_load_roster()` to use teacher-scoped storage

**Files:**
- Modify: `backend/services/assistant_tools.py:510-626`

- [ ] **Step 1: Update `_load_roster()`**

The function already accepts `teacher_id='local-dev'` but ignores it. Update the implementation:
1. When `_is_supabase_configured()` and `teacher_id != 'local-dev'`, load period data from `storage_load('period:*', teacher_id)` using `storage_list_keys('period:', teacher_id)`
2. Keep the local file fallback for dev mode
3. Pass `teacher_id` to any internal calls

- [ ] **Step 2: Verify all data loaders now accept and use teacher_id**

Manually verify these functions in `assistant_tools.py` pass `teacher_id` to `storage_load()`:
- `_load_results(teacher_id)` — line 230 ✅ already works
- `_load_accommodations(teacher_id)` — line 392 ✅ already works
- `_load_settings(teacher_id)` — line 418 ✅ already works
- `_load_parent_contacts(teacher_id)` — line 629 ✅ already works
- `_load_calendar(teacher_id)` — line 689 ✅ already works
- `_load_memories(teacher_id)` — line 716 ✅ already works
- `_load_master_csv(teacher_id=)` — Fixed in Task 3
- `_load_roster(teacher_id=)` — Fixed in this task

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/ -q --ignore=tests/load`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/services/assistant_tools.py
git commit -m "fix: _load_roster uses teacher-scoped storage instead of shared filesystem"
```

---

### Task 5: Add `teacher_id` to grading + analytics tool handlers

**Files:**
- Modify: `backend/services/assistant_tools_grading.py`
- Modify: `backend/services/assistant_tools_analytics.py`

- [ ] **Step 1: Update all grading tool handlers**

For each of the 9 functions in `assistant_tools_grading.py`, the pattern is the same. Most already accept `**kwargs`, so `teacher_id` flows through. The change is to **extract and pass it to data loaders**.

For each handler:
1. Add `teacher_id = kwargs.get('teacher_id', 'local-dev')` at the top (if using `**kwargs`) OR add `teacher_id='local-dev'` to the signature
2. Replace `_load_master_csv()` with `_load_master_csv(teacher_id=teacher_id)`
3. Replace `_load_results()` with `_load_results(teacher_id)`
4. Replace `_load_roster()` with `_load_roster(teacher_id)`

Functions to update: `query_grades`, `get_student_summary`, `get_class_analytics`, `get_assignment_stats`, `analyze_grade_causes`, `get_feedback_patterns`, `compare_periods`, `get_missing_assignments`, `scan_submissions_folder`

- [ ] **Step 2: Update all analytics tool handlers**

Same pattern for the 6 functions in `assistant_tools_analytics.py`:
`get_grade_trends`, `get_rubric_weakness`, `flag_at_risk_students`, `compare_assignments`, `get_grade_distribution`, `detect_score_outliers`

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/ -q --ignore=tests/load`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/services/assistant_tools_grading.py backend/services/assistant_tools_analytics.py
git commit -m "fix: pass teacher_id to data loaders in grading + analytics tools"
```

---

### Task 6: Add `teacher_id` to planning + communication + data tool handlers

**Files:**
- Modify: `backend/services/assistant_tools_planning.py`
- Modify: `backend/services/assistant_tools_communication.py`
- Modify: `backend/services/assistant_tools_data.py`

- [ ] **Step 1: Update planning tools (12 handlers)**

Same pattern — extract `teacher_id` from kwargs, pass to data loaders and calendar storage functions.

Functions: `suggest_remediation`, `suggest_grouping`, `generate_bell_ringer`, `generate_exit_ticket`, `generate_sub_plans`, `get_pacing_status`, `recommend_next_lesson`, `get_calendar`, `schedule_lesson_tool`, `unschedule_lesson_tool`, `add_calendar_holiday`, `create_focus_assignment`

- [ ] **Step 2: Update communication tools (3 handlers)**

Functions: `draft_student_feedback`, `generate_parent_conference_notes`, `generate_report_card_comments`

- [ ] **Step 3: Update `save_memory` in data tools**

Extract `teacher_id`, pass to `_save_memories(memories, teacher_id)`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/ -q --ignore=tests/load`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add backend/services/assistant_tools_planning.py backend/services/assistant_tools_communication.py backend/services/assistant_tools_data.py
git commit -m "fix: pass teacher_id to data loaders in planning, communication, and data tools"
```

---

### Task 7: Fix reports tools — eliminate local file writes + add teacher_id

**Files:**
- Modify: `backend/services/assistant_tools_reports.py`

- [ ] **Step 1: Fix `export_grades_csv`**

Currently writes CSV to `~/.graider_exports/focus/`. Change to:
1. Build CSV in-memory using `io.StringIO`
2. Return base64-encoded CSV string in the tool response dict
3. Add `audit_tool_action(teacher_id, 'export_grades_csv', 'EXPORT')`
4. No disk write

- [ ] **Step 2: Fix `send_parent_emails` / `send_focus_comms`**

Currently writes pending payloads to `~/.graider_data/pending_send.json`. Change to:
1. Use `storage_save('pending_send', payload, teacher_id)`
2. Add `audit_tool_action(teacher_id, tool_name, 'SEND_EMAIL')`

- [ ] **Step 3: Fix `confirm_and_send`**

Currently reads from `~/.graider_data/pending_send.json`. Change to:
1. Use `storage_load('pending_send', teacher_id)` for reads
2. Use `storage_save('pending_send', None, teacher_id)` to clear after send
3. Add `audit_tool_action(teacher_id, 'confirm_and_send', 'SEND_EMAIL')`

- [ ] **Step 4: Fix `lookup_student_info`**

Pass `teacher_id` to `_load_roster(teacher_id)` and `_load_parent_contacts(teacher_id)`.

- [ ] **Step 5: Add teacher_id to all remaining report handlers**

Pass `teacher_id` to all data loaders in: `generate_progress_report`, `recommend_next_lesson`, `create_focus_assignment`

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/ -q --ignore=tests/load`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add backend/services/assistant_tools_reports.py
git commit -m "fix: eliminate local PII file writes in reports tools, add teacher_id scoping"
```

---

### Task 8: Fix student tools — eliminate local exports + add teacher_id

**Files:**
- Modify: `backend/services/assistant_tools_student.py`

- [ ] **Step 1: Fix `export_student_data`**

Currently reads from 5 local files and writes to `~/.graider_exports/student/`. Change:
1. All reads converted to `storage_load(key, teacher_id)`:
   - Results: `storage_load('results', teacher_id)`
   - History: `load_student_history(teacher_id, student_id)` (already in storage.py)
   - Accommodations: `storage_load('accommodations', teacher_id)`
   - ELL: `storage_load('ell_students', teacher_id)`
   - Parent contacts: `storage_load('parent_contacts', teacher_id)`
2. Return base64 JSON in tool response instead of writing to disk
3. Add `audit_tool_action(teacher_id, 'export_student_data', 'EXPORT')`

- [ ] **Step 2: Fix `remove_student_from_roster`**

Add `audit_tool_action(teacher_id, 'remove_student_from_roster', 'DELETE', 'student_***')`.

- [ ] **Step 3: Add teacher_id to remaining student handlers**

`get_student_accommodations`, `get_student_streak`, `import_student_data` — extract and pass `teacher_id`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/ -q --ignore=tests/load`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add backend/services/assistant_tools_student.py
git commit -m "fix: eliminate local PII exports in student tools, add teacher_id + audit logging"
```

---

### Task 9: Anonymize AI calls + audit behavior tools

**Files:**
- Modify: `backend/services/assistant_tools_ai.py`
- Modify: `backend/services/assistant_tools_behavior.py`

- [ ] **Step 1: Fix `generate_iep_progress_notes` in `assistant_tools_ai.py`**

1. Extract `teacher_id` from `**kwargs`
2. Load roster: `roster = _load_roster(teacher_id)`
3. Build prompt as usual
4. Before Claude API call: `anon_prompt, mapping = anonymize_for_ai(prompt, roster)`
5. Send `anon_prompt` to Claude instead of `prompt`
6. After response: `result = deanonymize(response_text, mapping)`
7. `audit_tool_action(teacher_id, 'generate_iep_progress_notes', 'SEND_AI')`

- [ ] **Step 2: Fix `_generate_email_ai` in `assistant_tools_behavior.py`**

Same anonymization pattern. Also:
1. Add `audit_tool_action(teacher_id, 'generate_behavior_email', 'SEND_AI')` in `generate_behavior_email`
2. Add `audit_tool_action(teacher_id, 'send_behavior_email', 'SEND_EMAIL')` in `send_behavior_email`

- [ ] **Step 3: Pass teacher_id to `_load_settings()` and `_load_parent_contacts()` in behavior tools**

These already accept `teacher_id` but the behavior tools don't pass it.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/ -q --ignore=tests/load`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add backend/services/assistant_tools_ai.py backend/services/assistant_tools_behavior.py
git commit -m "fix: anonymize student PII before external AI calls, add audit logging"
```

---

### Task 10: Fix survey + automation scoping

**Files:**
- Modify: `backend/services/assistant_tools_survey.py`
- Modify: `backend/services/assistant_tools_automation.py`
- Modify: `backend/storage.py`

- [ ] **Step 1: Fix survey tools**

In `assistant_tools_survey.py`:
1. `create_parent_survey`: Add `teacher_id` to Supabase insert: `'teacher_id': teacher_id`
2. `get_survey_results`: Add `.eq('teacher_id', teacher_id)` to query. Remove unscoped fallback.
3. `compile_survey_report`: Same teacher_id filter.

All three: extract `teacher_id` from `**kwargs` or add to signature.

- [ ] **Step 2: Fix automation tools**

In `assistant_tools_automation.py`:
1. `list_automations_tool`: Load from `storage_load('automations', teacher_id)` instead of shared filesystem
2. `create_automation_tool`: Save to `storage_save('automations', data, teacher_id)` instead of shared filesystem
3. `run_automation_tool`: Load from `storage_load('automations', teacher_id)`

- [ ] **Step 3: Extend `sync_all_to_cloud()` in `storage.py`**

Add `pending_send` and `automations` to the list of single-key data items synced from local to Supabase.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/ -q --ignore=tests/load`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add backend/services/assistant_tools_survey.py backend/services/assistant_tools_automation.py backend/storage.py
git commit -m "fix: scope surveys + automations to teacher_id, extend cloud sync"
```

---

### Task 11: Add INVOKE audit to `execute_tool()` + teacher_id signature test

**Files:**
- Modify: `backend/services/assistant_tools.py:829-860`
- Modify: `tests/test_tool_schemas.py`

- [ ] **Step 1: Add INVOKE audit to `execute_tool()`**

After the handler is resolved but before calling it, add:

```python
# Audit all tool invocations that access student data
from backend.utils.compliance import audit_tool_action
DATA_TOOLS = {name for name in TOOL_HANDLERS if name not in _STATELESS_TOOLS}
if tool_name in DATA_TOOLS and 'teacher_id' in (tool_input or {}):
    audit_tool_action(tool_input['teacher_id'], tool_name, 'INVOKE')
```

Define `_STATELESS_TOOLS` as the set of edtech + stem tool names that don't access student data.

- [ ] **Step 2: Add teacher_id signature test to `test_tool_schemas.py`**

```python
import inspect

def test_data_tools_accept_teacher_id():
    """Every tool that accesses student data must accept teacher_id."""
    from backend.services.assistant_tools import TOOL_HANDLERS, _merge_submodules
    _merge_submodules()

    # Tools that DON'T need teacher_id (stateless, no student data)
    EXEMPT = {
        'check_math_equivalence', 'grade_math_question', 'grade_data_table',
        'grade_coordinates', 'grade_place_name',  # STEM tools
        'generate_kahoot_quiz', 'generate_blooket_set', 'generate_gimkit_kit',
        'generate_quizlet_set', 'generate_nearpod_questions', 'generate_canvas_qti',  # EdTech tools
    }

    for name, handler in TOOL_HANDLERS.items():
        if name in EXEMPT:
            continue
        sig = inspect.signature(handler)
        has_teacher_id = 'teacher_id' in sig.parameters
        has_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        assert has_teacher_id or has_var_keyword, (
            f"Tool '{name}' must accept teacher_id parameter or **kwargs"
        )
```

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -q --ignore=tests/load`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/services/assistant_tools.py tests/test_tool_schemas.py
git commit -m "feat: audit INVOKE for all data-accessing tools, verify teacher_id in test suite"
```

---

### Task 12: Final verification

**Files:** None (verification only)

- [ ] **Step 1: Run full backend test suite**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -q --ignore=tests/load`
Expected: All pass, 0 failures

- [ ] **Step 2: Start server and verify app loads**

Run: `cd /Users/alexc/Downloads/Graider/backend && FLASK_ENV=development PYTHONPATH=/Users/alexc/Downloads/Graider python app.py`
Expected: Server starts on port 3000

- [ ] **Step 3: Run Playwright E2E suite**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npx playwright test --reporter=dot --workers=1`
Expected: 267 passed

- [ ] **Step 4: Verify no local PII file paths remain in tool code**

Run: `grep -rn "graider_exports" backend/services/assistant_tools*.py`
Expected: No matches (all eliminated)

Run: `grep -rn "pending_send.json" backend/services/assistant_tools*.py`
Expected: No matches (moved to Supabase)

- [ ] **Step 5: Push to remote**

```bash
git push origin main
```
