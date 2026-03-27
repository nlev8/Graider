# Assistant Tool Guardrails — Code Fixes

## Problem

The AI assistant sometimes calls tools with wrong parameters — e.g., teacher asks about "London Samuel" but assistant drafts email to "Cayden Chambers" (from earlier in the conversation). Prompt-only fixes are unreliable because the model can ignore instructions.

## Root Causes

1. **No cross-tool validation** — `lookup_student_info` resolves the correct student, but `send_focus_comms` is called independently with whatever name the model picks. No check that they match.
2. **Preview hides recipients** — `send_focus_comms` only showed first 3 message previews. If the wrong student was selected, the teacher might not notice.
3. **Fuzzy matching is silent** — Partial name matches succeed without warning the teacher which student was matched.

## Fixes Applied (3 changes, 2 files)

---

### Fix 1: Cross-Tool State Tracking

**File:** `backend/routes/assistant_routes.py` (tool call loop, ~line 1546)

**What it does:** Tracks which students `lookup_student_info` resolved. When a send tool (`send_focus_comms`, `send_behavior_email`, `send_parent_emails`) is called in the same conversation round, validates that the student name matches a resolved student. If not, blocks the call with an error.

**Code added** (after `result = execute_tool(tb["name"], tool_input)`):

```python
# Cross-tool guardrail: track students from lookup calls
if tb["name"] == "lookup_student_info" and isinstance(result, dict):
    students = result.get("data", {}).get("students", [])
    if isinstance(students, list):
        _resolved_students = [
            {"name": s.get("name", ""), "student_id": s.get("student_id", "")}
            for s in students
        ]

# Cross-tool guardrail: warn if send tools reference students
# that weren't in the most recent lookup result
if tb["name"] in ("send_focus_comms", "send_behavior_email", "send_parent_emails") \
   and _resolved_students:
    tool_student_names = tool_input.get("student_names") or []
    if isinstance(tool_student_names, str):
        tool_student_names = [tool_student_names]
    tool_student_name = tool_input.get("student_name", "")
    if tool_student_name:
        tool_student_names.append(tool_student_name)
    if tool_student_names:
        resolved_names = [s["name"].lower().strip() for s in _resolved_students]
        for sn in tool_student_names:
            sn_lower = sn.lower().strip()
            match_found = any(
                sn_lower in rn or rn in sn_lower
                for rn in resolved_names
            )
            if not match_found and resolved_names:
                logger.warning(
                    "Cross-tool mismatch: %s called with student '%s' "
                    "but lookup_student_info resolved: %s",
                    tb["name"], sn, [s["name"] for s in _resolved_students]
                )
                result = {
                    "error": f"Student name mismatch: you are trying to send to "
                    f"'{sn}' but the most recent lookup resolved "
                    f"'{_resolved_students[0]['name']}'. "
                    f"Please call lookup_student_info for '{sn}' first "
                    f"to verify the correct student."
                }
```

**Effect:** If the model calls `lookup_student_info("London Samuel")` → resolves to "London Samuel", then calls `send_focus_comms(student_names=["Cayden Chambers"])`, the send is blocked with: *"Student name mismatch: you are trying to send to 'Cayden Chambers' but the most recent lookup resolved 'London Samuel'."*

---

### Fix 2: Full Recipient Preview

**File:** `backend/services/assistant_tools_reports.py` (~line 2436)

**Before:**
```python
for m in messages[:3]:  # Only first 3 previews shown
```

**After:**
```python
for m in messages:  # ALL previews shown
```

**Also added `recipient_names` to response:**

**Before:**
```python
return {
    "dry_run": True,
    "NOT_SENT": True,
    "preview_count": len(previews),
    "total_messages": len(messages),
    "previews": previews,
    "message": "PREVIEW ONLY — messages have NOT been sent yet. ...",
}
```

**After:**
```python
return {
    "dry_run": True,
    "NOT_SENT": True,
    "preview_count": len(previews),
    "total_messages": len(messages),
    "recipient_names": [m["student_name"] for m in messages],
    "previews": previews,
    "message": "PREVIEW ONLY — messages have NOT been sent yet. "
               "VERIFY the recipient names are correct before asking "
               "the teacher to confirm. If they confirm, call confirm_and_send.",
}
```

**Effect:** Teacher sees every recipient name before confirming. Model is instructed to verify names are correct.

---

### Fix 3: System Prompt Reinforcement

**File:** `backend/routes/assistant_routes.py` (~line 902)

**Added:**
```
CRITICAL: Always use the student name from the CURRENT message. If the
teacher previously discussed Cayden but now asks about London, the student
is LONDON — not Cayden. Do NOT carry over student names from earlier messages.
```

And updated Step 1:
```
Step 1: Extract the EXACT student name from the teacher's CURRENT message —
not from earlier in the conversation. If the teacher says "email London
Samuel's parents", the student is "London Samuel", NOT any student mentioned
previously. Call lookup_student_info with this exact name.
```

**Effect:** Reinforces correct behavior at the prompt level. Not deterministic alone, but combined with Fix 1 (which IS deterministic), covers both layers.

---

## Phase 2 Guardrails (Future)

| Guardrail | Description | Complexity |
|-----------|-------------|------------|
| Ambiguous name rejection | If `lookup_student_info` fuzzy-matches multiple students, return error asking model to disambiguate | Medium |
| User message entity extraction | Parse student names from teacher's message before model processes it, inject as constraint | Medium |
| Tool call dry-run simulation | Validate all tool calls in a batch before executing any | High |
| Fuzzy match strictness mode | Add exact-first matching to `_fuzzy_name_match` | Low |
