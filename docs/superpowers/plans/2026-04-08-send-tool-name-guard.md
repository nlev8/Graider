# Send Tool User-Message Name Guard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent send tools (`send_focus_comms`, `send_behavior_email`, `send_parent_emails`) from targeting a student the user never mentioned, by cross-checking tool parameters against the user's current message.

**Architecture:** Extract the last user message text inside the streaming generator. When a send tool is called with `student_names`, check each name against the user message using word-overlap matching. If the user message contains name-like words (2+ capitalized words) but none overlap with the tool's target student, block the call. Skip the check when the user message has no discernible student name (e.g. "yes", "send it", confirmations).

**Tech Stack:** Python, existing `_fuzzy_name_match` from `backend/services/assistant_tools.py`

**Spec:** Bug report — LLM carried "Troy Jaxson Mikell" from prior conversation context when user asked about "Charles Cavanaugh". Existing cross-tool guard only fires after `lookup_student_info`; this adds a second layer using the raw user message.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/routes/assistant_routes.py` | **Modify** | Add user-message name extraction + cross-check in tool dispatch loop (lines ~1612-1627) |
| `tests/test_assistant_name_guard.py` | **Create** | Unit tests for name extraction and the guard logic |

---

### Task 1: Add user-message student name guard

**Files:**
- Create: `tests/test_assistant_name_guard.py`
- Modify: `backend/routes/assistant_routes.py:1228-1232` (capture last user text)
- Modify: `backend/routes/assistant_routes.py:1612-1627` (add message-based guard)

- [ ] **Step 1: Write failing tests**

Create `tests/test_assistant_name_guard.py`:

```python
"""Tests for send-tool user-message name guard."""

import pytest


class TestExtractUserMessageNames:
    """Tests for _extract_message_names — pulling potential student names from user text."""

    def test_extracts_full_name(self):
        from backend.routes.assistant_routes import _extract_message_names
        names = _extract_message_names("draft an email to Charles Cavanaugh's parents about his behavior")
        assert any("charles" in n for n in names)
        assert any("cavanaugh" in n for n in names)

    def test_extracts_name_with_possessive(self):
        from backend.routes.assistant_routes import _extract_message_names
        names = _extract_message_names("email Troy Mikell's mother")
        assert any("troy" in n for n in names)
        assert any("mikell" in n for n in names)

    def test_returns_empty_for_no_names(self):
        from backend.routes.assistant_routes import _extract_message_names
        names = _extract_message_names("yes send it")
        assert names == []

    def test_returns_empty_for_generic_confirmation(self):
        from backend.routes.assistant_routes import _extract_message_names
        names = _extract_message_names("looks good, send now")
        assert names == []

    def test_ignores_common_words(self):
        from backend.routes.assistant_routes import _extract_message_names
        # "Dear" and "Please" are capitalized but not student names
        names = _extract_message_names("Dear teacher, Please send the email")
        assert "dear" not in names
        assert "please" not in names

    def test_extracts_name_after_preposition(self):
        from backend.routes.assistant_routes import _extract_message_names
        names = _extract_message_names("send a message to London Samuel about missing work")
        assert any("london" in n for n in names)
        assert any("samuel" in n for n in names)

    def test_handles_multiple_names(self):
        from backend.routes.assistant_routes import _extract_message_names
        names = _extract_message_names("email Charles Cavanaugh and London Samuel's parents")
        assert any("charles" in n for n in names)
        assert any("london" in n for n in names)


class TestNameOverlapCheck:
    """Tests for _student_name_in_message — checking if a tool's student name overlaps with user message names."""

    def test_matching_name_returns_true(self):
        from backend.routes.assistant_routes import _student_name_in_message
        assert _student_name_in_message("Charles Cavanaugh", "email Charles Cavanaugh's parents about defiance") is True

    def test_mismatched_name_returns_false(self):
        from backend.routes.assistant_routes import _student_name_in_message
        assert _student_name_in_message("Troy Jaxson Mikell", "email Charles Cavanaugh's parents about defiance") is False

    def test_partial_name_match(self):
        from backend.routes.assistant_routes import _student_name_in_message
        # User says "Charles" only, tool has full name
        assert _student_name_in_message("Charles Cavanaugh", "email Charles about his behavior") is True

    def test_skips_check_for_confirmations(self):
        from backend.routes.assistant_routes import _student_name_in_message
        # "yes" / "send it" — no names in message, should return True (skip check)
        assert _student_name_in_message("Troy Mikell", "yes send it") is True

    def test_skips_check_for_short_messages(self):
        from backend.routes.assistant_routes import _student_name_in_message
        assert _student_name_in_message("Troy Mikell", "looks good") is True

    def test_case_insensitive(self):
        from backend.routes.assistant_routes import _student_name_in_message
        assert _student_name_in_message("charles cavanaugh", "Email CHARLES CAVANAUGH's parents") is True

    def test_name_with_middle_name(self):
        from backend.routes.assistant_routes import _student_name_in_message
        # User says "Troy Mikell", tool uses full "Troy Jaxson Mikell"
        assert _student_name_in_message("Troy Jaxson Mikell", "email Troy Mikell's parents") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assistant_name_guard.py -v`
Expected: FAIL — `_extract_message_names` and `_student_name_in_message` do not exist

- [ ] **Step 3: Implement the two helper functions**

In `backend/routes/assistant_routes.py`, add these functions above the `assistant_chat` endpoint (before `@assistant_bp.route('/api/assistant/chat', ...)`). Place them after the existing helper functions, around line 1145:

```python
# ── Send-tool user-message name guard ──────────────────────

# Words that are commonly capitalized but are NOT student names.
_IGNORE_WORDS = frozenset([
    "dear", "please", "hello", "hi", "hey", "good", "morning", "afternoon",
    "evening", "send", "email", "message", "text", "draft", "write", "contact",
    "parents", "parent", "mother", "father", "mom", "dad", "guardian",
    "about", "regarding", "concerning", "class", "period", "grade", "school",
    "behavior", "assignment", "homework", "classwork", "test", "quiz",
    "mr", "mrs", "ms", "miss", "dr", "teacher", "student", "focus",
    "the", "and", "his", "her", "their", "from", "with", "for", "that",
    "this", "have", "has", "been", "was", "are", "will", "can", "would",
    "should", "could", "also", "still", "just", "now", "today", "tomorrow",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "during", "after", "before", "since", "into", "like", "not", "but",
    "insistence", "constant", "refusal", "talking", "back", "silent", "remain",
    "defiance", "disrespect", "loud", "rowdy", "playing", "games",
])


def _extract_message_names(text):
    """Extract potential student name words from a user message.

    Returns a list of lowercased words that look like name parts
    (capitalized words not in the ignore list). Returns [] if none found.
    """
    import re
    # Strip possessives and punctuation, split into words
    cleaned = re.sub(r"'s\b", "", text)
    words = re.findall(r"[A-Za-z]+", cleaned)

    name_words = []
    for w in words:
        low = w.lower()
        # Keep words that: (a) start with uppercase OR (b) are in a sequence after a name word,
        # AND are not in the ignore list, AND are at least 2 chars
        if len(w) >= 2 and low not in _IGNORE_WORDS:
            # Must start with uppercase (proper noun) in original text
            if w[0].isupper():
                name_words.append(low)
    return name_words


def _student_name_in_message(student_name, user_message):
    """Check if a student name from a tool call has word overlap with the user message.

    Returns True if:
      - The user message contains no extractable names (confirmation like "yes", "send it")
      - At least one word from student_name appears in the extracted message names

    Returns False if:
      - The user message has extractable names but NONE overlap with student_name
    """
    message_names = _extract_message_names(user_message)
    if not message_names:
        # No names detected — user is confirming or giving a generic instruction
        return True

    import re
    student_words = [w.lower() for w in re.findall(r"[A-Za-z]+", student_name) if len(w) >= 2]
    if not student_words:
        return True

    # Check if ANY student name word appears in the message names
    return any(sw in message_names for sw in student_words)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assistant_name_guard.py -v`
Expected: All 14 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/routes/assistant_routes.py tests/test_assistant_name_guard.py
git commit -m "feat: add name extraction helpers for send-tool user-message guard"
```

---

### Task 2: Wire guard into tool dispatch loop

**Files:**
- Modify: `backend/routes/assistant_routes.py:1228-1232` (capture last user text)
- Modify: `backend/routes/assistant_routes.py:1612-1627` (add message-based guard)

- [ ] **Step 1: Capture last user message text in the streaming generator**

In `backend/routes/assistant_routes.py`, inside `generate()` (line 1228), after `messages = list(conv["messages"])` (line 1232), add:

```python
        # Extract the last user message text for send-tool name guard
        _last_user_text = ""
        for _msg in reversed(messages):
            if isinstance(_msg, dict) and _msg.get("role") == "user":
                _content = _msg.get("content", "")
                if isinstance(_content, str):
                    _last_user_text = _content
                elif isinstance(_content, list):
                    # Multimodal: find text block
                    for _block in _content:
                        if isinstance(_block, dict) and _block.get("type") == "text":
                            _last_user_text = _block.get("text", "")
                            break
                break
```

- [ ] **Step 2: Add the user-message name check in the guard block**

In `backend/routes/assistant_routes.py`, find the existing new guard (the block starting with `# Cross-tool guardrail: require lookup before sending to specific students`, around line 1612). Insert the user-message check **after** the existing `_resolved_students` empty check and **before** the existing mismatch check. The full block should read:

```python
                    # Cross-tool guardrail: require lookup before sending to specific students
                    if tb["name"] in ("send_focus_comms", "send_behavior_email", "send_parent_emails"):
                        _send_student_names = tool_input.get("student_names") or []
                        if isinstance(_send_student_names, str):
                            _send_student_names = [_send_student_names]
                        _send_student_name = tool_input.get("student_name", "")
                        if _send_student_name:
                            _send_student_names.append(_send_student_name)
                        if _send_student_names and not _resolved_students:
                            # LLM skipped lookup_student_info — block and force lookup first
                            result = {
                                "error": "You must call lookup_student_info before sending messages. "
                                "Call lookup_student_info for '" + _send_student_names[0] + "' first to verify the correct student, "
                                "then call " + tb["name"] + " again."
                            }
                        # User-message name guard: check if tool's student matches the user's request
                        if _send_student_names and _last_user_text and not result.get("error"):
                            for _sn in _send_student_names:
                                if not _student_name_in_message(_sn, _last_user_text):
                                    logger.warning(
                                        "User-message name mismatch: %s targets '%s' but user message doesn't mention this student",
                                        tb["name"], _sn
                                    )
                                    result = {
                                        "error": "Student name mismatch: you are trying to send to '" + _sn + "' but the user's message "
                                        "does not mention this student. Re-read the user's CURRENT message, extract the correct student name, "
                                        "call lookup_student_info with that name, then try again."
                                    }
                                    break
```

Note: This replaces the entire first guard block (lines 1612-1626). The second guard block (`if ... and _resolved_students:`) remains unchanged after this.

- [ ] **Step 3: Run all tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assistant_name_guard.py tests/test_correction_patterns.py -v`
Expected: All pass

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -5`
Expected: All pass, no regressions

- [ ] **Step 4: Commit**

```bash
git add backend/routes/assistant_routes.py
git commit -m "feat: guard send tools against student name mismatch with user message"
```

---

## Summary

| Task | What | Files | Risk |
|------|------|-------|------|
| 1 | Name extraction helpers + 14 tests | `assistant_routes.py`, `test_assistant_name_guard.py` | Low — pure functions, no side effects |
| 2 | Wire guard into tool dispatch | `assistant_routes.py` | Low — adds early-return error before tool execution |

**Total: 1 modified file, 1 new test file, 14 tests.**

**Three layers of defense after this:**
1. **User-message guard (new):** Tool's student name must appear in the user's current message (or message has no names)
2. **Lookup-required guard (added earlier today):** `lookup_student_info` must be called before any send tool
3. **Cross-tool mismatch guard (existing):** Send tool's student must match the most recent lookup result
