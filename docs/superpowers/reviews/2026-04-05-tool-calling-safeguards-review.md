# Tool-Calling Safeguards — Review & Fixes

## Bug Report

The AI assistant was claiming it sent emails without actually triggering the Playwright automation. When a teacher confirmed "yes send it," the AI would:
1. Call `send_behavior_email` (which sent immediately with no preview)
2. OR skip the tool call entirely and just say "email sent" in text
3. OR call both the preview tool and `confirm_and_send` in the same tool round, bypassing teacher confirmation

## Root Causes Found

| Issue | Severity | Root Cause |
|-------|----------|------------|
| `send_behavior_email` sends immediately | Critical | No forced `dry_run` — unlike `send_focus_comms` which forces preview |
| AI claims "sent" without calling tool | Critical | No code-level enforcement — only prompt instructions |
| AI chains preview + confirm in one round | Critical | No blocking between preview and confirmation tools in same turn |
| `remove_student_from_roster` deletes immediately | Critical | No confirmation gate — permanent data loss with no undo |
| AI fabricates tool success | Medium | No post-response validation of claims vs actual tool results |

## Fixes Applied

### 1. Guarded Action Registry (`backend/services/assistant_tool_guards.py`)

New file. Declares which tools need verification:

- **`preview_confirm` tools**: `send_focus_comms`, `send_parent_emails`, `send_behavior_email`, `remove_student_from_roster` — must show preview, wait for confirmation
- **`verify_result` tools**: `confirm_and_send`, `confirm_student_removal`, `create_focus_assignment` — must return specific success status

Helpers:
- `get_verification_message(tool_name, result)` — builds injection message based on actual result
- `check_false_claims(response_text, executed_tools)` — scans AI text for claim phrases using word-boundary regex

### 2. Tool Result Verification Injection (`backend/routes/assistant_routes.py`)

After every guarded tool executes, a verification message is appended to the tool result:
- Preview tools get: "The action has NOT been executed yet. Show the preview and ask for confirmation."
- Verify tools with success get: "Completed successfully. You may report this."
- Verify tools with failure get: "FAILED. Do NOT claim the action succeeded."

The AI sees this before generating its next response.

### 3. Post-Response False Claim Detection (`backend/routes/assistant_routes.py`)

After the AI's final text response, scans for claim phrases (e.g., "has been sent", "was removed") and cross-references against which tools were actually called and whether they succeeded. If a false claim is detected, appends a correction to the streamed response.

### 4. Same-Turn Confirmation Blocking (`backend/routes/assistant_routes.py`)

**The key fix.** Confirmation tools (`confirm_and_send`, `confirm_student_removal`) are blocked from executing if any preview tool was called earlier in the same turn. The AI gets an error: "Cannot confirm in the same turn as the preview. Show the preview and wait for teacher confirmation."

The set of confirmation tools is derived from the registry automatically — adding a new preview-confirm pair to the registry automatically extends the blocking.

### 5. `send_behavior_email` → Preview-Confirm (`backend/services/assistant_tools_behavior.py`)

Rewritten to match `send_focus_comms` pattern:
- Forces preview only — returns `NOT_SENT: True`
- Saves pending payload to keyed storage (`pending_send:send_behavior_email`)
- Actual send logic moved to `confirm_and_send` (new `elif action == "send_behavior_email"` block)

### 6. `remove_student_from_roster` → Preview-Confirm (`backend/services/assistant_tools_student.py`)

Split into two tools:
- `remove_student_from_roster` — looks up student, counts data, returns summary with `PENDING_CONFIRMATION: True`. Does NOT delete.
- `confirm_student_removal` (new) — loads pending, calls the actual deletion, returns `status: "removed"`

### 7. Keyed Storage Fix (`backend/services/assistant_tools_reports.py`)

- `confirm_and_send` now searches keyed storage (`pending_send:send_behavior_email`, etc.) as fallback
- `remove_student` removed from `confirm_and_send`'s search (it has its own `confirm_student_removal`)

## Test Coverage

13 tests in `tests/test_assistant_tool_guards.py`:
- Registry completeness (3 tests)
- Verification message generation (5 tests)
- False claim detection (5 tests)

## Defense Layers Summary

```
Layer 1: Preview-Confirm Flow
  send_behavior_email → returns preview, NOT_SENT: True
  remove_student_from_roster → returns summary, PENDING_CONFIRMATION: True
  Code physically cannot send/delete without confirmation tool

Layer 2: Same-Turn Blocking
  confirm_and_send blocked if preview tool called this turn
  confirm_student_removal blocked if preview tool called this turn
  Forces a new user message (new turn) between preview and confirm

Layer 3: Verification Injection
  After each guarded tool, injects "TOOL VERIFICATION: ..." into result
  AI sees actual outcome before generating response

Layer 4: Post-Response Claim Check
  Scans final AI text for claim phrases
  Cross-references against actual tool calls and results
  Appends correction if false claim detected
```

## Remaining Recommendations (From Code Review)

1. **Pending payload frontend leak** — `assistant_routes.py` lines 1656-1665 reads `pending_send.json` from filesystem and attaches to SSE events. In multi-tenant production, this could leak across teachers. Low priority since confirmation goes through the AI tool flow.
2. **No test for same-turn blocking** — The blocking logic in `assistant_routes.py` is untested. Would need integration test or extraction to testable function.
3. **Legacy dual-write** — `send_behavior_email` writes to both keyed and legacy storage. Consider removing legacy write once old tools are migrated.
