# Assistant Tool-Calling Safeguards — Design Spec

## Problem

The AI assistant can claim it performed an action (sent an email, removed a student) without actually calling the tool, or after the tool returned an error. This is a hallucination problem that prompt instructions alone cannot solve. Additionally, destructive tools like `remove_student_from_roster` execute immediately with no confirmation, and `send_behavior_email` sends immediately with no preview step.

## Solution

Three-layer defense:

1. **Guarded Action Registry** — a declarative registry of tools that require verification. Each entry defines what success looks like and what false-claim phrases to watch for.
2. **Tool Result Injection** — after each guarded tool executes, inject a system message into the conversation with the actual result and explicit instructions tied to that result. The AI can only respond based on what actually happened.
3. **Post-Response Claim Check** — after the AI's final text response, scan for claim phrases that don't match actual tool results. Append a correction if the AI hallucinated.

Plus two tool conversions:
- `send_behavior_email` converted to preview-confirm flow (matches `send_focus_comms` pattern)
- `remove_student_from_roster` split into preview + `confirm_student_removal`

## Guarded Action Registry

New file: `backend/services/assistant_tool_guards.py`

```python
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
        "claim_phrases": ["sent", "delivered", "message sent", "email sent",
                          "has been sent", "was sent", "successfully sent"],
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
        "claim_phrases": ["removed", "deleted", "data cleared", "has been removed",
                          "was removed", "successfully removed"],
    },
    "create_focus_assignment": {
        "type": "verify_result",
        "success_key": "status",
        "success_value": "launched",
        "claim_phrases": ["created assignment", "assignment created",
                          "has been created"],
    },
}
```

### Helper Functions

`get_verification_message(tool_name, tool_result)` — given a tool name and its result dict, returns the verification message to inject into the conversation. Returns None if the tool is not guarded.

For `type: "preview_confirm"`:
> "TOOL VERIFICATION: {tool_name} returned a preview. The action has NOT been executed. Show the preview to the teacher and ask for confirmation. Do not claim the action was completed."

For `type: "verify_result"`:
- If result contains the success key with the success value:
  > "TOOL VERIFICATION: {tool_name} completed successfully (status={value}). You may report this success to the teacher."
- If result contains an error or the success key is missing/wrong:
  > "TOOL VERIFICATION: {tool_name} FAILED. Error: {error}. Report this failure to the teacher. Do NOT claim the action succeeded."

`check_false_claims(response_text, tool_calls_this_turn, tool_results_this_turn)` — scans the AI's final response text for claim phrases. Returns a correction string if a false claim is detected, or None if clean.

Logic:
1. For each guarded action with `claim_phrases`, check if any phrase appears in `response_text` (case-insensitive).
2. If a claim phrase is found, check if the corresponding tool was called this turn AND returned the expected success result.
3. If the tool was not called, or it returned an error, return a correction message.

## Tool Result Injection Point

In `backend/routes/assistant_routes.py`, after tool execution (~line 1574):

```python
result = execute_tool(tb["name"], tool_input)

# Inject verification for guarded tools
from backend.services.assistant_tool_guards import get_verification_message
verification = get_verification_message(tb["name"], result)
if verification:
    # Append as system message so AI sees it before generating response
    tool_results.append({
        "type": "tool_result",
        "tool_use_id": tb["id"],
        "content": json.dumps(result) + "\n\n" + verification,
    })
```

The verification message is appended to the tool result content, so the AI sees both the actual result and the enforcement instruction in one message.

## Post-Response Claim Check

After the AI's final text response is assembled (after all tool rounds), before yielding the final SSE events:

```python
from backend.services.assistant_tool_guards import check_false_claims

correction = check_false_claims(
    response_text=full_response_text,
    tool_calls_this_turn=executed_tools,    # [{name, result}, ...]
    tool_results_this_turn=tool_results,
)
if correction:
    # Append correction to the streamed response
    yield f"data: {json.dumps({'type': 'text', 'content': correction})}\n\n"
```

## send_behavior_email Conversion

Current: calls `launch_focus_comms()` or `email_svc.send_email()` immediately.

Change to:
1. Build preview payload (recipient, subject, body, method)
2. Store in `pending_send` with `action: "send_behavior_email"`
3. Return preview dict with `NOT_SENT: True`, preview text, and instruction to confirm
4. Add `"send_behavior_email"` as a handled action in `confirm_and_send`

The actual send logic moves from `send_behavior_email` into `confirm_and_send`'s action handler.

## remove_student_from_roster Conversion

Current: deletes all student data immediately.

Split into:
1. **`remove_student_from_roster`** (modified) — looks up the student, counts their data (submissions, classes, accommodations). Returns a summary: "About to permanently delete: Troy Thomas — 3 classes, 12 submissions, IEP accommodations. This cannot be undone." Stores pending removal in `pending_send` with `action: "remove_student"`. Returns `PENDING_CONFIRMATION: True`.
2. **`confirm_student_removal`** (new) — reads pending payload, executes the actual deletion (existing delete logic), clears pending, returns `status: "removed"`.

Register `confirm_student_removal` in the tool definitions and handler map.

## Tracking Executed Tools

The tool loop in `assistant_routes.py` needs to track which tools were called and their results across all rounds. Add:

```python
executed_tools_this_turn = []  # populated in tool loop
# After each tool execution:
executed_tools_this_turn.append({"name": tb["name"], "result": result})
```

This list is passed to `check_false_claims` after the final response.

## What This Does NOT Include

- No changes to `send_focus_comms` or `send_parent_emails` — already correctly enforced
- No frontend changes — all backend enforcement
- No changes to non-destructive tools (calendar, surveys, document generation, CSV exports)
- No changes to the existing `confirm_and_send` logic — only adding new action types to its switch

## Files Changed

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/services/assistant_tool_guards.py` | **Create** | Registry, verification message builder, false claim checker |
| `backend/routes/assistant_routes.py` | **Modify** | Inject verification after tool execution, post-response claim check, track executed tools |
| `backend/services/assistant_tools_behavior.py` | **Modify** | Convert `send_behavior_email` to preview-confirm |
| `backend/services/assistant_tools_student.py` | **Modify** | Convert `remove_student_from_roster` to preview, add `confirm_student_removal` tool definition + handler |
| `backend/services/assistant_tools_reports.py` | **Modify** | Add `send_behavior_email` and `remove_student` actions to `confirm_and_send` |
| `tests/test_assistant_tool_guards.py` | **Create** | Tests for registry, verification messages, false claim detection |
