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

---

### Fix 4: Fuzzy Match Transparency + Disambiguation

**File:** `backend/services/assistant_tools_reports.py` (~line 1517, return block of `lookup_student_info`)

**Problem:** `lookup_student_info` silently returns fuzzy matches without telling the model which record was chosen. If "Sam" matches "Samuel Smith" and "Samantha Jones", the model picks one arbitrarily.

**What it does now:**

1. **Multiple matches → disambiguation required:** If a name search matches multiple students, the response includes `disambiguation_required: true` and a message listing all matches with their periods. The model must ask the teacher to clarify.

2. **Fuzzy match warning:** If the matched name differs from the searched name (e.g., searched "Sam", matched "Samuel Smith"), the response includes `fuzzy_matched: true` with both names visible.

3. **Exact match → no warning:** If the name matches exactly, no extra fields are added.

**Code added** (replacing the simple return):

```python
result = {
    "students": students,
    "total_found": len(students),
}

if student_name:
    result["searched_name"] = student_name
    result["matched_names"] = [s["name"] for s in students]

    if len(students) > 1:
        result["disambiguation_required"] = True
        result["message"] = (
            f"Multiple students match '{student_name}': "
            + ", ".join(f"{s['name']} ({s['period']})" for s in students)
            + ". Specify which student you mean before proceeding."
        )
    elif len(students) == 1 and student_name.lower().strip() != students[0]["name"].lower().strip():
        result["fuzzy_matched"] = True
        result["message"] = (
            f"Searched for '{student_name}', matched to '{students[0]['name']}' "
            f"in {students[0]['period']}. Verify this is the correct student."
        )

return result
```

**Effect:** Model sees "Multiple students match 'Sam': Samuel Smith (Period 1), Samantha Jones (Period 3). Specify which student you mean." — must disambiguate before proceeding.

---

### Fix 5: Cross-Tool State — Initialization Clarification

**File:** `backend/routes/assistant_routes.py` (~line 1550)

`_resolved_students` is initialized as `[]` **before** the `for tb in tool_use_blocks` loop, at the start of each tool batch. This means:
- Fresh per conversation round (no stale state from prior teacher messages)
- Populated when `lookup_student_info` runs
- Checked when send tools run in the same batch
- Reset automatically on the next user message (new tool batch)

```python
tool_results = []
_resolved_students = []  # Reset per tool batch — no state leakage
for tb in tool_use_blocks:
    ...
```

Also fixed: the result key path was `result.get("data", {}).get("students", [])` but `lookup_student_info` returns `result.get("students", [])` directly (no `data` wrapper). Corrected to match actual return format.

---

## Phase 2 Guardrails (Future)

| Guardrail | Description | Complexity |
|-----------|-------------|------------|
| User message entity extraction | Parse student names from teacher's message before model processes it, inject as constraint | Medium |
| Tool call dry-run simulation | Validate all tool calls in a batch before executing any | High |
| Fuzzy match strictness mode | Add exact-first matching to `_fuzzy_name_match` | Low |
