# Assistant Tool-Calling Safeguards — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent the AI assistant from claiming it performed actions (sent emails, removed students) without actually calling the tool, and enforce preview-confirm flows on all destructive/send tools.

**Architecture:** A guarded action registry declares which tools need verification. After each guarded tool executes, a verification message is injected into the conversation. After the AI's final response, a claim checker scans for false claims. `send_behavior_email` and `remove_student_from_roster` are converted to preview-confirm flows matching the existing `send_focus_comms` pattern.

**Tech Stack:** Python/Flask (backend only)

**Spec:** `docs/superpowers/specs/2026-04-05-tool-calling-safeguards-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/services/assistant_tool_guards.py` | **Create** | Registry, verification message builder, false claim checker |
| `backend/routes/assistant_routes.py` | **Modify** | Inject verification after tool execution, post-response claim check, track executed tools |
| `backend/services/assistant_tools_behavior.py` | **Modify** | Convert `send_behavior_email` to preview-confirm |
| `backend/services/assistant_tools_student.py` | **Modify** | Convert `remove_student_from_roster` to preview, add `confirm_student_removal` |
| `backend/services/assistant_tools_reports.py` | **Modify** | Add `send_behavior_email` and `remove_student` actions to `confirm_and_send` |
| `tests/test_assistant_tool_guards.py` | **Create** | Tests for registry, verification messages, false claim detection |

---

### Task 1: Create the guarded action registry and helpers

**Files:**
- Create: `backend/services/assistant_tool_guards.py`
- Create: `tests/test_assistant_tool_guards.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_assistant_tool_guards.py`:

```python
"""Tests for assistant tool-calling safeguards."""

import re
import pytest

from backend.services.assistant_tool_guards import (
    GUARDED_ACTIONS,
    get_verification_message,
    check_false_claims,
)


class TestGuardedActionsRegistry:
    def test_registry_contains_all_guarded_tools(self):
        expected = [
            "send_focus_comms", "send_parent_emails", "send_behavior_email",
            "confirm_and_send", "remove_student_from_roster",
            "confirm_student_removal", "create_focus_assignment",
        ]
        for name in expected:
            assert name in GUARDED_ACTIONS, f"{name} missing from registry"

    def test_preview_confirm_entries_have_confirm_tool(self):
        for name, entry in GUARDED_ACTIONS.items():
            if entry["type"] == "preview_confirm":
                assert "confirm_tool" in entry, f"{name} missing confirm_tool"

    def test_verify_result_entries_have_claim_phrases(self):
        for name, entry in GUARDED_ACTIONS.items():
            if entry["type"] == "verify_result":
                assert "claim_phrases" in entry, f"{name} missing claim_phrases"
                assert len(entry["claim_phrases"]) > 0


class TestGetVerificationMessage:
    def test_preview_confirm_tool_returns_not_executed_message(self):
        result = {"NOT_SENT": True, "preview": "Email to parent..."}
        msg = get_verification_message("send_behavior_email", result)
        assert msg is not None
        assert "NOT been executed" in msg
        assert "confirmation" in msg.lower()

    def test_verify_result_success_returns_success_message(self):
        result = {"status": "started", "total_messages": 3}
        msg = get_verification_message("confirm_and_send", result)
        assert msg is not None
        assert "successfully" in msg.lower() or "completed" in msg.lower()

    def test_verify_result_failure_returns_failure_message(self):
        result = {"error": "SIS connection failed"}
        msg = get_verification_message("confirm_and_send", result)
        assert msg is not None
        assert "FAILED" in msg
        assert "Do NOT claim" in msg or "Do not claim" in msg

    def test_unguarded_tool_returns_none(self):
        result = {"data": "some query result"}
        msg = get_verification_message("query_grades", result)
        assert msg is None

    def test_verify_result_wrong_status_returns_failure(self):
        result = {"status": "error", "message": "timeout"}
        msg = get_verification_message("confirm_and_send", result)
        assert msg is not None
        assert "FAILED" in msg


class TestCheckFalseClaims:
    def test_detects_false_send_claim(self):
        response = "The email has been sent to Troy's mother."
        executed = []  # no tools called
        correction = check_false_claims(response, executed)
        assert correction is not None
        assert "not actually completed" in correction.lower() or "was not" in correction.lower()

    def test_no_false_positive_on_future_tense(self):
        response = "I plan to send the email once you confirm."
        executed = []
        correction = check_false_claims(response, executed)
        assert correction is None

    def test_no_correction_when_tool_succeeded(self):
        response = "The email has been sent to Troy's mother."
        executed = [{"name": "confirm_and_send", "result": {"status": "started"}}]
        correction = check_false_claims(response, executed)
        assert correction is None

    def test_detects_false_removal_claim(self):
        response = "Troy has been removed from all records."
        executed = []
        correction = check_false_claims(response, executed)
        assert correction is not None

    def test_no_correction_when_removal_succeeded(self):
        response = "Troy has been removed from all records."
        executed = [{"name": "confirm_student_removal", "result": {"status": "removed"}}]
        correction = check_false_claims(response, executed)
        assert correction is None

    def test_detects_claim_when_tool_failed(self):
        response = "The email has been sent successfully."
        executed = [{"name": "confirm_and_send", "result": {"error": "Focus portal timeout"}}]
        correction = check_false_claims(response, executed)
        assert correction is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assistant_tool_guards.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Create the registry and helpers**

Create `backend/services/assistant_tool_guards.py`:

```python
"""Guarded action registry and verification helpers for the AI assistant.

Prevents the AI from claiming it performed actions without actually calling
the tools, and provides post-response false claim detection.
"""

import re
import logging

logger = logging.getLogger(__name__)

GUARDED_ACTIONS = {
    "send_focus_comms": {
        "type": "preview_confirm",
        "success_key": "NOT_SENT",
        "confirm_tool": "confirm_and_send",
    },
    "send_parent_emails": {
        "type": "preview_confirm",
        "success_key": "NOT_SENT",
        "confirm_tool": "confirm_and_send",
    },
    "send_behavior_email": {
        "type": "preview_confirm",
        "success_key": "NOT_SENT",
        "confirm_tool": "confirm_and_send",
    },
    "confirm_and_send": {
        "type": "verify_result",
        "success_key": "status",
        "success_value": "started",
        "claim_phrases": [
            "has been sent", "was sent", "successfully sent",
            "email sent", "message sent", "email has been delivered",
            "messages were sent", "has been delivered",
        ],
    },
    "remove_student_from_roster": {
        "type": "preview_confirm",
        "success_key": "PENDING_CONFIRMATION",
        "confirm_tool": "confirm_student_removal",
    },
    "confirm_student_removal": {
        "type": "verify_result",
        "success_key": "status",
        "success_value": "removed",
        "claim_phrases": [
            "has been removed", "was removed", "successfully removed",
            "data cleared", "been deleted", "was deleted",
            "successfully deleted", "records removed",
        ],
    },
    "create_focus_assignment": {
        "type": "verify_result",
        "success_key": "status",
        "success_value": "launched",
        "claim_phrases": [
            "assignment created", "created assignment",
            "has been created in Focus",
        ],
    },
}


def get_verification_message(tool_name, tool_result):
    """Build a verification message to inject after a guarded tool executes.

    Returns a string to append to the tool result, or None if the tool
    is not guarded.
    """
    guard = GUARDED_ACTIONS.get(tool_name)
    if not guard:
        return None

    if not isinstance(tool_result, dict):
        return None

    if guard["type"] == "preview_confirm":
        return (
            "TOOL VERIFICATION: " + tool_name + " returned a preview. "
            "The action has NOT been executed yet. Show the preview to the "
            "teacher and ask for confirmation before proceeding. "
            "Do NOT claim the action was completed."
        )

    if guard["type"] == "verify_result":
        success_key = guard.get("success_key", "status")
        success_value = guard.get("success_value", "")
        actual_value = tool_result.get(success_key)

        if "error" in tool_result:
            return (
                "TOOL VERIFICATION: " + tool_name + " FAILED. "
                "Error: " + str(tool_result["error"]) + ". "
                "Report this failure to the teacher. "
                "Do NOT claim the action succeeded."
            )

        if str(actual_value) == str(success_value):
            return (
                "TOOL VERIFICATION: " + tool_name + " completed successfully "
                "(status=" + str(actual_value) + "). "
                "You may report this success to the teacher."
            )

        return (
            "TOOL VERIFICATION: " + tool_name + " returned unexpected status: "
            + str(actual_value) + " (expected " + str(success_value) + "). "
            "Do NOT claim the action succeeded. Report the actual result."
        )

    return None


def check_false_claims(response_text, executed_tools):
    """Scan the AI's response for claims about actions that didn't happen.

    Args:
        response_text: The AI's final text response
        executed_tools: List of dicts [{"name": str, "result": dict}, ...]

    Returns a correction string if a false claim is detected, or None.
    """
    if not response_text:
        return None

    response_lower = response_text.lower()

    for tool_name, guard in GUARDED_ACTIONS.items():
        if guard["type"] != "verify_result":
            continue

        phrases = guard.get("claim_phrases", [])
        claim_found = False
        for phrase in phrases:
            pattern = re.compile(r'\b' + re.escape(phrase) + r'\b', re.IGNORECASE)
            if pattern.search(response_text):
                claim_found = True
                break

        if not claim_found:
            continue

        # Check if the tool was called and succeeded
        tool_succeeded = False
        for executed in executed_tools:
            if executed["name"] == tool_name:
                result = executed.get("result", {})
                if isinstance(result, dict):
                    success_key = guard.get("success_key", "status")
                    success_value = guard.get("success_value", "")
                    if str(result.get(success_key)) == str(success_value) and "error" not in result:
                        tool_succeeded = True
                break

        if not tool_succeeded:
            logger.warning(
                "False claim detected: AI claimed '%s' action but tool %s was not called or failed",
                phrases[0], tool_name,
            )
            return (
                "\n\n**Note:** The action was not actually completed. "
                "Please try again or check the error above."
            )

    return None
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_assistant_tool_guards.py -v`
Expected: All 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/assistant_tool_guards.py tests/test_assistant_tool_guards.py
git commit -m "feat: guarded action registry with verification and false claim detection"
```

---

### Task 2: Inject verification into the tool loop

**Files:**
- Modify: `backend/routes/assistant_routes.py:1288-1660`

- [ ] **Step 1: Initialize executed tools tracker before the tool loop**

At line 1293 in `backend/routes/assistant_routes.py`, right before `for _round_idx in range(max_rounds):`, add:

```python
        executed_tools_this_turn = []  # Track all tool calls across rounds for claim checking
```

- [ ] **Step 2: Record executed tools and inject verification after each tool call**

After line 1574 (`result = execute_tool(tb["name"], tool_input)`), before the existing cross-tool guardrail at line 1576, add:

```python
                    # Record execution for post-response claim checking
                    executed_tools_this_turn.append({"name": tb["name"], "result": result})

                    # Inject verification message for guarded tools
                    from backend.services.assistant_tool_guards import get_verification_message
                    _verification_msg = get_verification_message(tb["name"], result)
```

Then modify the `result_str` construction at line 1610 to include the verification:

Find:
```python
                    result_str = json.dumps(result)
```

Change to:
```python
                    result_str = json.dumps(result)
                    if _verification_msg:
                        result_str = result_str + "\n\n" + _verification_msg
```

- [ ] **Step 3: Add post-response claim check when no tool calls remain**

At line 1521-1523, find:

```python
                if not tool_use_blocks:
                    conv["messages"].append({"role": "assistant", "content": full_response_text})
                    break
```

Change to:

```python
                if not tool_use_blocks:
                    # Post-response claim check: detect if AI claims actions it didn't perform
                    from backend.services.assistant_tool_guards import check_false_claims
                    _claim_correction = check_false_claims(full_response_text, executed_tools_this_turn)
                    if _claim_correction:
                        logger.warning("False claim detected in assistant response, appending correction")
                        yield f"data: {json.dumps({'type': 'text', 'content': _claim_correction})}\n\n"
                        full_response_text += _claim_correction
                    conv["messages"].append({"role": "assistant", "content": full_response_text})
                    break
```

- [ ] **Step 4: Also add claim check at the early-exit point**

Find line 1517-1518 (the other break point where no tool calls are found in the response):

```python
                    if full_response_text:
                        conv["messages"].append({"role": "assistant", "content": full_response_text})
```

This block is inside an `if` that checks `if not tool_use_blocks and not ...` — it's the first-round exit when the AI responds with text only. Add the same claim check here:

```python
                    if full_response_text:
                        from backend.services.assistant_tool_guards import check_false_claims
                        _claim_correction = check_false_claims(full_response_text, executed_tools_this_turn)
                        if _claim_correction:
                            logger.warning("False claim detected in assistant response, appending correction")
                            yield f"data: {json.dumps({'type': 'text', 'content': _claim_correction})}\n\n"
                            full_response_text += _claim_correction
                        conv["messages"].append({"role": "assistant", "content": full_response_text})
```

- [ ] **Step 5: Commit**

```bash
git add backend/routes/assistant_routes.py
git commit -m "feat: inject tool verification and post-response claim checking"
```

---

### Task 3: Convert send_behavior_email to preview-confirm

**Files:**
- Modify: `backend/services/assistant_tools_behavior.py:807-908`
- Modify: `backend/services/assistant_tools_reports.py:2525-2570`

- [ ] **Step 1: Rewrite send_behavior_email to save preview instead of sending**

In `backend/services/assistant_tools_behavior.py`, replace the `send_behavior_email` function (lines 807-896) with:

```python
def send_behavior_email(student_name, subject, body, method="focus", teacher_id='local-dev', **kwargs):
    """Generate a behavior email preview. Does NOT send — stores pending payload for confirm_and_send."""
    require_teacher_id(teacher_id)
    if not teacher_id or teacher_id == 'local-dev':
        teacher_id = _get_teacher_id() or 'local-dev'

    if not student_name or not subject or not body:
        return {"error": "student_name, subject, and body are all required."}

    # Build pending payload
    pending = {
        "action": "send_behavior_email",
        "student_name": student_name,
        "subject": subject,
        "body": body,
        "method": method,
    }

    # Find parent email for preview display
    parent_email = ""
    if method == "email":
        contacts_raw = _load_parent_contacts()
        contacts_list = contacts_raw.values() if isinstance(contacts_raw, dict) else contacts_raw
        for contact in contacts_list:
            if not isinstance(contact, dict):
                continue
            if _fuzzy_name_match(student_name, contact.get("student_name", "")):
                emails = contact.get("parent_emails", [])
                parent_email = emails[0] if isinstance(emails, list) and emails else contact.get("parent_email", "") or contact.get("email", "")
                break
        if not parent_email:
            roster = _load_roster(teacher_id)
            for s in roster:
                if _fuzzy_name_match(student_name, s.get("name", "")):
                    parent_email = s.get("parent_email", "") or s.get("guardian_email", "")
                    break
        if not parent_email:
            return {"error": "No parent email found for '" + student_name + "'. Add parent contacts in the student roster or parent contacts file."}
        pending["parent_email"] = parent_email

    # Store pending payload
    try:
        from backend.storage import save as storage_save
        storage_save("pending_send:send_behavior_email", pending, teacher_id)
    except Exception:
        pass
    # Also write to filesystem fallback
    import os, json as _json
    pending_dir = os.path.expanduser("~/.graider_data")
    os.makedirs(pending_dir, exist_ok=True)
    pending_path = os.path.join(pending_dir, "pending_send.json")
    try:
        with open(pending_path, 'w') as pf:
            _json.dump(pending, pf)
    except Exception:
        pass

    method_label = "Focus Communications portal" if method == "focus" else ("Resend API to " + parent_email)

    return {
        "NOT_SENT": True,
        "PREVIEW_ONLY": True,
        "preview": {
            "to": parent_email if method == "email" else student_name + "'s parents (via Focus)",
            "subject": subject,
            "body": body,
            "method": method_label,
        },
        "message": "PREVIEW — NOT YET SENT. The teacher must confirm before this email will be sent via " + method_label + ". Call confirm_and_send after teacher approval.",
    }
```

- [ ] **Step 2: Add send_behavior_email action to confirm_and_send**

In `backend/services/assistant_tools_reports.py`, find the `confirm_and_send` function (~line 2503). After the `elif action == "send_parent_emails":` block (around line 2566), add a new elif:

```python
        elif action == "send_behavior_email":
            student_name = pending.get("student_name", "")
            subject = pending.get("subject", "")
            body = pending.get("body", "")
            method = pending.get("method", "focus")

            if method == "focus":
                from backend.routes.email_routes import launch_focus_comms
                message = {
                    "student_name": student_name,
                    "subject": subject,
                    "email_body": body,
                    "sms_body": "",
                    "cc_emails": [],
                }
                result = launch_focus_comms([message], teacher_id=teacher_id)
                if "error" in result:
                    return result
                if storage_save:
                    storage_save('pending_send', None, teacher_id)
                    storage_save('pending_send:send_behavior_email', None, teacher_id)
                else:
                    try:
                        os.remove(os.path.join(os.path.expanduser("~/.graider_data"), "pending_send.json"))
                    except OSError:
                        pass
                audit_tool_action(teacher_id, 'confirm_and_send', 'SEND_EMAIL')
                return {
                    "status": "started",
                    "method": "focus",
                    "message": "Focus Communications sending to " + student_name + "'s parents.",
                }
            else:
                from backend.services.email_service import EmailService
                email_svc = EmailService()
                parent_email = pending.get("parent_email", "")
                if not parent_email:
                    return {"error": "No parent email in pending payload."}
                success = email_svc.send_email(
                    to_email=parent_email,
                    student_name=student_name,
                    subject=subject,
                    body=body,
                )
                if not success:
                    return {"error": "Failed to send email via Resend."}
                if storage_save:
                    storage_save('pending_send', None, teacher_id)
                    storage_save('pending_send:send_behavior_email', None, teacher_id)
                else:
                    try:
                        os.remove(os.path.join(os.path.expanduser("~/.graider_data"), "pending_send.json"))
                    except OSError:
                        pass
                audit_tool_action(teacher_id, 'confirm_and_send', 'SEND_EMAIL')
                return {
                    "status": "started",
                    "method": "email",
                    "message": "Email sent to " + parent_email,
                }
```

- [ ] **Step 3: Update confirm_and_send to check keyed pending storage**

In the `confirm_and_send` function, after the existing `pending = storage_load('pending_send', teacher_id)` line (~line 2513), add fallback checks for keyed storage:

```python
    if not pending:
        # Check keyed storage (new pattern)
        for action_key in ('send_behavior_email', 'send_focus_comms', 'send_parent_emails', 'remove_student'):
            keyed = storage_load('pending_send:' + action_key, teacher_id)
            if keyed:
                pending = keyed
                break
```

- [ ] **Step 4: Commit**

```bash
git add backend/services/assistant_tools_behavior.py backend/services/assistant_tools_reports.py
git commit -m "feat: convert send_behavior_email to preview-confirm flow"
```

---

### Task 4: Convert remove_student_from_roster to preview-confirm

**Files:**
- Modify: `backend/services/assistant_tools_student.py:30-65, 426-620, 914-920`
- Modify: `backend/services/assistant_tools_reports.py` (add action to confirm_and_send)

- [ ] **Step 1: Add confirm_student_removal tool definition**

In `backend/services/assistant_tools_student.py`, find the `STUDENT_TOOL_DEFINITIONS` list (line 30). Add a new tool definition after the existing `remove_student_from_roster` definition:

```python
    {
        "name": "confirm_student_removal",
        "description": "Execute a pending student removal after the teacher has confirmed. Call ONLY after remove_student_from_roster has shown a preview and the teacher has approved. Takes no parameters — reads the pending removal automatically.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
```

- [ ] **Step 2: Rename the existing remove logic to _execute_student_removal**

Rename the existing `remove_student_from_roster` function at line 426 to `_execute_student_removal`. Keep the entire body unchanged:

```python
def _execute_student_removal(student_name, teacher_id='local-dev', **kwargs):
    """Internal: actually remove a student from ALL records."""
    # ... entire existing body unchanged ...
```

- [ ] **Step 3: Write new remove_student_from_roster as preview-only**

Add a new `remove_student_from_roster` function that replaces the old one:

```python
def remove_student_from_roster(student_name, teacher_id='local-dev', **kwargs):
    """Preview student removal. Does NOT delete — stores pending for confirm_student_removal."""
    require_teacher_id(teacher_id)
    if not student_name:
        return {"error": "student_name is required."}

    teacher_id = teacher_id or kwargs.get('teacher_id', 'local-dev')
    if not teacher_id or teacher_id == 'local-dev':
        try:
            from flask import g
            teacher_id = getattr(g, 'user_id', 'local-dev')
        except Exception:
            teacher_id = 'local-dev'

    # Look up student to build preview
    roster = _load_roster(teacher_id)
    matched_name = None
    for entry in roster:
        rname = entry.get("student_name", "") or entry.get("name", "")
        if _fuzzy_name_match(student_name, rname):
            matched_name = rname
            break

    if not matched_name:
        # Check file-based rosters
        search_dirs = [
            (PERIODS_DIR, "periods"),
            (ROSTERS_DIR, "rosters"),
        ]
        matches = _find_all_student_files(student_name, search_dirs)
        if matches:
            matched_name = matches[0][0]

    if not matched_name:
        return {"error": "No student found matching '" + student_name + "' in any roster."}

    # Count data that will be deleted
    results_count = 0
    try:
        from backend.app import _get_state
        grading_state = _get_state(teacher_id)
        results_count = sum(
            1 for r in grading_state.get("results", [])
            if _fuzzy_name_match(student_name, r.get("student_name", ""))
        )
    except Exception:
        pass

    # Store pending removal
    pending = {
        "action": "remove_student",
        "student_name": matched_name,
        "teacher_id": teacher_id,
    }
    try:
        from backend.storage import save as storage_save
        storage_save("pending_send:remove_student", pending, teacher_id)
    except Exception:
        pass
    import os as _os, json as _json
    pending_dir = _os.path.expanduser("~/.graider_data")
    _os.makedirs(pending_dir, exist_ok=True)
    try:
        with open(_os.path.join(pending_dir, "pending_send.json"), 'w') as pf:
            _json.dump(pending, pf)
    except Exception:
        pass

    summary = "About to permanently delete ALL data for " + matched_name + ":"
    summary += " roster entries, grading results"
    if results_count > 0:
        summary += " (" + str(results_count) + " results)"
    summary += ", accommodations, parent contacts, ELL data, student history, and Supabase records."
    summary += " This cannot be undone."

    return {
        "PENDING_CONFIRMATION": True,
        "student_name": matched_name,
        "results_count": results_count,
        "message": summary,
        "instruction": "Show this summary to the teacher. Call confirm_student_removal ONLY after teacher confirms.",
    }
```

- [ ] **Step 4: Write confirm_student_removal function**

Add after the new `remove_student_from_roster`:

```python
def confirm_student_removal(teacher_id='local-dev', **kwargs):
    """Execute a pending student removal after teacher confirmation."""
    require_teacher_id(teacher_id)
    teacher_id = teacher_id or kwargs.get('teacher_id', 'local-dev')
    if not teacher_id or teacher_id == 'local-dev':
        try:
            from flask import g
            teacher_id = getattr(g, 'user_id', 'local-dev')
        except Exception:
            teacher_id = 'local-dev'

    # Load pending removal
    pending = None
    try:
        from backend.storage import load as storage_load, save as storage_save
        pending = storage_load("pending_send:remove_student", teacher_id)
    except Exception:
        pass
    if not pending:
        import os as _os, json as _json
        pending_path = _os.path.join(_os.path.expanduser("~/.graider_data"), "pending_send.json")
        if _os.path.exists(pending_path):
            try:
                with open(pending_path, 'r') as f:
                    pending = _json.load(f)
                if pending.get("action") != "remove_student":
                    pending = None
            except Exception:
                pass

    if not pending:
        return {"error": "No pending student removal. Call remove_student_from_roster first."}

    student_name = pending.get("student_name", "")
    if not student_name:
        return {"error": "No student name in pending removal."}

    # Execute the actual removal
    result = _execute_student_removal(student_name, teacher_id=teacher_id)

    # Clear pending
    try:
        from backend.storage import save as storage_save
        storage_save("pending_send:remove_student", None, teacher_id)
        storage_save("pending_send", None, teacher_id)
    except Exception:
        pass
    try:
        import os as _os
        _os.remove(_os.path.join(_os.path.expanduser("~/.graider_data"), "pending_send.json"))
    except OSError:
        pass

    result["status"] = "removed"
    return result
```

- [ ] **Step 5: Register confirm_student_removal in the handler map**

At line 914, update `STUDENT_TOOL_HANDLERS`:

```python
STUDENT_TOOL_HANDLERS = {
    "get_student_accommodations": get_student_accommodations,
    "get_student_streak": get_student_streak,
    "remove_student_from_roster": remove_student_from_roster,
    "confirm_student_removal": confirm_student_removal,
    "export_student_data": export_student_data,
    "import_student_data": import_student_data,
}
```

- [ ] **Step 6: Commit**

```bash
git add backend/services/assistant_tools_student.py
git commit -m "feat: convert remove_student_from_roster to preview-confirm with confirm_student_removal"
```

---

### Task 5: Update system prompt

**Files:**
- Modify: `backend/routes/assistant_routes.py:916-924`

- [ ] **Step 1: Update the behavior email instructions**

Find the behavior email section in the system prompt (~line 922). Replace:

```python
- send_behavior_email: Send a reviewed behavior email via Resend (direct email) or Focus portal automation. Always show the draft first and get teacher approval before sending. When the teacher confirms (e.g., "yes", "send it"), you MUST call send_behavior_email with the draft content. NEVER claim the email was sent without calling this tool and receiving a success response. The tool performs the actual send — your text response alone does nothing.
```

With:

```python
- send_behavior_email: Preview a behavior email via Resend or Focus portal. Returns a PREVIEW, does NOT send. After showing the preview and the teacher confirms, call confirm_and_send to actually send. NEVER claim the email was sent until confirm_and_send returns status "started".
```

- [ ] **Step 2: Update the remove_student_from_roster instructions**

Find the line mentioning `remove_student_from_roster` in the system prompt (~line 889). Add after it:

```python
  IMPORTANT: remove_student_from_roster returns a PREVIEW of what will be deleted. It does NOT delete anything. After showing the preview and the teacher confirms, call confirm_student_removal to execute. NEVER claim a student was removed without a successful confirm_student_removal response.
- confirm_student_removal: Execute a pending student removal after teacher confirmation. Takes no parameters. Call ONLY after remove_student_from_roster has shown a preview and the teacher has approved.
```

- [ ] **Step 3: Commit**

```bash
git add backend/routes/assistant_routes.py
git commit -m "feat: update system prompt for preview-confirm tool flows"
```

---

## Summary

| Task | What | Files | Risk |
|------|------|-------|------|
| 1 | Guarded action registry + helpers | New `assistant_tool_guards.py`, tests | Low — new file |
| 2 | Inject verification in tool loop | `assistant_routes.py` | Medium — modifying streaming loop |
| 3 | send_behavior_email preview-confirm | `assistant_tools_behavior.py`, `assistant_tools_reports.py` | Medium — rewriting tool |
| 4 | remove_student_from_roster preview-confirm | `assistant_tools_student.py` | Medium — splitting tool |
| 5 | Update system prompt | `assistant_routes.py` | Low — text change |

**Total: 1 new file, 4 modified files, 13 tests, 2 tool conversions.**

**Before:** AI can claim "email sent" or "student removed" without calling tools. `send_behavior_email` sends immediately. `remove_student_from_roster` deletes immediately.
**After:** Three-layer defense (verification injection, post-response claim check, registry). All send/delete tools require preview then confirmation. False claims are detected and corrected.
