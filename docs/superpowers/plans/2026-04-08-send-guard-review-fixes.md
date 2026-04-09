# Send Guard Review Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Unicode regex mismatch in `_student_name_in_message` and add dispatch-level guard tests by extracting guard logic into a testable pure function.

**Architecture:** Fix the `[A-Za-z]+` regex on line 1211 to match the Unicode-aware regex used in `_extract_message_names`. Extract the send-tool guard block (lines 1687-1737) into a pure function `_check_send_tool_guard()` that returns `None` (proceed) or an error dict (blocked). Call it from the dispatch loop. Test all three guard scenarios against the extracted function.

**Tech Stack:** Python, pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/routes/assistant_routes.py` | **Modify** | Fix regex (line 1211), extract guard into `_check_send_tool_guard()`, call it from dispatch loop |
| `tests/test_assistant_name_guard.py` | **Modify** | Add Unicode fix test, add dispatch-level guard tests |

---

### Task 1: Fix Unicode regex in `_student_name_in_message`

**Files:**
- Modify: `backend/routes/assistant_routes.py:1210-1211`
- Modify: `tests/test_assistant_name_guard.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_assistant_name_guard.py` inside `TestNameOverlapCheck`:

```python
    def test_unicode_name_matches(self):
        from backend.routes.assistant_routes import _student_name_in_message
        # Roster has "Ángela Ruiz", teacher types "email Ángela Ruiz's parents"
        # Both sides must tokenize the accent correctly
        assert _student_name_in_message("Ángela Ruiz", "email Ángela Ruiz's parents about her grades") is True

    def test_unicode_name_blocks_mismatch(self):
        from backend.routes.assistant_routes import _student_name_in_message
        assert _student_name_in_message("Ángela Ruiz", "email Charles Cavanaugh's parents") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assistant_name_guard.py::TestNameOverlapCheck::test_unicode_name_matches -v`
Expected: FAIL — `_student_name_in_message("Ángela Ruiz", ...)` tokenizes to `["ngela", "ruiz"]` missing the `á`, so "ángela" from the message doesn't match "ngela" from the student name

- [ ] **Step 3: Fix the regex**

In `backend/routes/assistant_routes.py`, find `_student_name_in_message` (line 1210-1211):

Change:
```python
    student_words = [w.lower() for w in re.findall(r"[A-Za-z]+", student_name) if len(w) >= 2]
```

To:
```python
    student_words = [w.lower() for w in re.findall(r"[A-Za-z\u00C0-\u024F]+", student_name) if len(w) >= 2]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assistant_name_guard.py -v`
Expected: All 21 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/routes/assistant_routes.py tests/test_assistant_name_guard.py
git commit -m "fix: match Unicode regex in _student_name_in_message to _extract_message_names"
```

---

### Task 2: Extract guard into testable function + dispatch-level tests

**Files:**
- Modify: `backend/routes/assistant_routes.py:1146-1215` (add `_check_send_tool_guard`)
- Modify: `backend/routes/assistant_routes.py:1687-1741` (replace inline guard with function call)
- Modify: `tests/test_assistant_name_guard.py` (add `TestSendToolGuard` class)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_assistant_name_guard.py`:

```python
class TestSendToolGuard:
    """Dispatch-level tests for _check_send_tool_guard — proves execute_tool would not run."""

    def test_blocks_when_no_lookup(self):
        from backend.routes.assistant_routes import _check_send_tool_guard
        result = _check_send_tool_guard(
            tool_name="send_focus_comms",
            tool_input={"student_names": ["Troy Mikell"]},
            resolved_students=[],
            last_user_text="email Troy Mikell's parents",
        )
        assert result is not None
        assert "lookup_student_info" in result["error"]

    def test_blocks_when_user_message_mismatch(self):
        from backend.routes.assistant_routes import _check_send_tool_guard
        result = _check_send_tool_guard(
            tool_name="send_focus_comms",
            tool_input={"student_names": ["Troy Mikell"]},
            resolved_students=[{"name": "Troy Mikell", "student_id": "123"}],
            last_user_text="email Charles Cavanaugh's parents about defiance",
        )
        assert result is not None
        assert "does not mention this student" in result["error"]

    def test_blocks_when_cross_tool_mismatch(self):
        from backend.routes.assistant_routes import _check_send_tool_guard
        result = _check_send_tool_guard(
            tool_name="send_focus_comms",
            tool_input={"student_names": ["Troy Mikell"]},
            resolved_students=[{"name": "Charles Cavanaugh", "student_id": "456"}],
            last_user_text="email Troy Mikell's parents",
        )
        assert result is not None
        assert "most recent lookup resolved" in result["error"]

    def test_passes_when_all_checks_match(self):
        from backend.routes.assistant_routes import _check_send_tool_guard
        result = _check_send_tool_guard(
            tool_name="send_focus_comms",
            tool_input={"student_names": ["Charles Cavanaugh"]},
            resolved_students=[{"name": "Charles Cavanaugh", "student_id": "456"}],
            last_user_text="email Charles Cavanaugh's parents about defiance",
        )
        assert result is None

    def test_passes_for_non_send_tool(self):
        from backend.routes.assistant_routes import _check_send_tool_guard
        result = _check_send_tool_guard(
            tool_name="query_grades",
            tool_input={"student_name": "Troy Mikell"},
            resolved_students=[],
            last_user_text="show Troy's grades",
        )
        assert result is None

    def test_passes_for_period_send_without_student_names(self):
        from backend.routes.assistant_routes import _check_send_tool_guard
        result = _check_send_tool_guard(
            tool_name="send_focus_comms",
            tool_input={"period": "3"},
            resolved_students=[],
            last_user_text="email all parents in period 3",
        )
        assert result is None

    def test_passes_for_confirmation_message(self):
        from backend.routes.assistant_routes import _check_send_tool_guard
        result = _check_send_tool_guard(
            tool_name="send_focus_comms",
            tool_input={"student_names": ["Troy Mikell"]},
            resolved_students=[{"name": "Troy Mikell", "student_id": "123"}],
            last_user_text="yes send it",
        )
        assert result is None

    def test_handles_student_name_param(self):
        """Tools use either student_names (list) or student_name (string)."""
        from backend.routes.assistant_routes import _check_send_tool_guard
        result = _check_send_tool_guard(
            tool_name="send_behavior_email",
            tool_input={"student_name": "Troy Mikell"},
            resolved_students=[],
            last_user_text="email Troy Mikell's parents about behavior",
        )
        assert result is not None
        assert "lookup_student_info" in result["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assistant_name_guard.py::TestSendToolGuard -v`
Expected: FAIL — `_check_send_tool_guard` does not exist

- [ ] **Step 3: Create `_check_send_tool_guard` function**

In `backend/routes/assistant_routes.py`, add this function after `_student_name_in_message` (after line 1215), before the `# CHAT ENDPOINT` comment block:

```python
_SEND_TOOL_NAMES = frozenset(["send_focus_comms", "send_behavior_email", "send_parent_emails"])


def _check_send_tool_guard(tool_name, tool_input, resolved_students, last_user_text):
    """Pre-execution guard for send tools. Returns None to proceed or an error dict to block.

    Three layers:
      1. Require lookup_student_info before sending to specific students
      2. Tool's student name must appear in the user's current message
      3. Tool's student name must match the most recent lookup result
    """
    if tool_name not in _SEND_TOOL_NAMES:
        return None

    # Normalize student names from both parameter formats
    student_names = tool_input.get("student_names") or []
    if isinstance(student_names, str):
        student_names = [student_names]
    single_name = tool_input.get("student_name", "")
    if single_name:
        student_names.append(single_name)

    if not student_names:
        return None

    # Layer 1: Require lookup
    if not resolved_students:
        return {
            "error": "You must call lookup_student_info before sending messages. "
            "Call lookup_student_info for '" + student_names[0] + "' first to verify the correct student, "
            "then call " + tool_name + " again."
        }

    # Layer 2: User-message name match
    if last_user_text:
        for sn in student_names:
            if not _student_name_in_message(sn, last_user_text):
                return {
                    "error": "Student name mismatch: you are trying to send to '" + sn + "' but the user's message "
                    "does not mention this student. Re-read the user's CURRENT message, extract the correct student name, "
                    "call lookup_student_info with that name, then try again."
                }

    # Layer 3: Cross-tool mismatch
    resolved_names = [s["name"].lower().strip() for s in resolved_students]
    for sn in student_names:
        sn_lower = sn.lower().strip()
        match_found = any(sn_lower in rn or rn in sn_lower for rn in resolved_names)
        if not match_found and resolved_names:
            return {
                "error": "Student name mismatch: you are trying to send to '" + sn + "' but the most recent lookup resolved '" + resolved_students[0]["name"] + "'. "
                "Please call lookup_student_info for '" + sn + "' first to verify the correct student."
            }

    return None
```

- [ ] **Step 4: Replace inline guard in dispatch loop**

In `backend/routes/assistant_routes.py`, find the inline guard block (starting at the comment `# Send-tool guards: require lookup + user-message name match`, around line 1687). Replace the entire block from that comment through line 1737 (just before `# ── Execute tool`) with:

```python
                    # Send-tool guards: require lookup + user-message name match
                    if result is None:
                        result = _check_send_tool_guard(
                            tb["name"], tool_input, _resolved_students, _last_user_text
                        )
```

The surrounding code stays the same — the confirmation-tool guard above it (lines 1677-1685) and the `if result is None: result = execute_tool(...)` below it (line 1739-1741).

- [ ] **Step 5: Run all tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assistant_name_guard.py -v`
Expected: All 29 tests PASS (19 existing + 2 from Task 1 + 8 new)

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -5`
Expected: All pass, no regressions

- [ ] **Step 6: Commit**

```bash
git add backend/routes/assistant_routes.py tests/test_assistant_name_guard.py
git commit -m "refactor: extract send-tool guard into testable function with dispatch-level tests"
```

---

## Summary

| Task | What | Risk |
|------|------|------|
| 1 | Fix `[A-Za-z]+` → `[A-Za-z\u00C0-\u024F]+` in `_student_name_in_message` | Trivial — one regex change |
| 2 | Extract guard into `_check_send_tool_guard()`, replace inline block, add 8 dispatch-level tests | Low — pure refactor, behavior unchanged |

**Total: 1 modified file, 1 modified test file, 10 new tests.**

**After this:**
- Unicode names work correctly on both sides of the comparison
- 8 dispatch-level tests prove the guard blocks `execute_tool` for all three failure scenarios
- Guard logic is a pure function: easy to test, easy to reason about, no SSE plumbing needed
