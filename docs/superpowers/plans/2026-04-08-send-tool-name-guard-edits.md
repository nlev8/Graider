# Send Tool Name Guard — Code Edits

## Bug

When a teacher asks "draft an email to Charles Cavanaugh's parents about his defiance," the LLM carries over a student name (Troy Jaxson Mikell) from earlier in the conversation and sends the email to the wrong student.

## Fix: Three guard layers in a pure function, all before `execute_tool`

All guards live in `_check_send_tool_guard()` — a pure function that returns `None` (proceed) or an error dict (blocked). The dispatch loop calls it before `execute_tool()`, so blocked tools never execute.

| Layer | What it checks | When it fires |
|-------|---------------|---------------|
| 1. Lookup required | `resolved_students` is empty | LLM skipped `lookup_student_info` |
| 2. User-message match | Tool's student name not in user's current message | LLM carried over wrong name from context |
| 3. Cross-tool match | Tool's student doesn't match lookup result | LLM looked up one student, sent to another |

---

## Edit 1: Helper functions (`assistant_routes.py:1146-1215`)

**Location:** After `_cleanup_stale_sessions()`, before `_check_send_tool_guard()`

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
    "yes", "no", "ok", "okay", "sure", "looks", "it", "do", "go", "so",
    "got", "get", "let", "me", "my", "an", "on", "up", "at", "to", "of",
    "is", "am", "be", "by", "or", "if", "as", "we", "us", "all", "any",
    "out", "off", "did", "does", "done", "need", "want", "make", "take",
    "them", "they", "she", "he", "who", "what", "when", "how", "why",
    "new", "old", "one", "two", "three", "more", "much", "very", "too",
    "then", "than", "here", "there", "some", "each", "every", "only",
    "well", "real", "really", "right", "wrong", "way", "thing", "things",
    "work", "working", "missing", "late", "report", "note", "notes",
    "being", "keep", "kept", "stop", "stopped", "see", "saw", "come",
    "came", "know", "knew", "tell", "told", "think", "thought", "try",
])


def _extract_message_names(text):
    """Extract potential student name words from a user message.

    Returns a list of lowercased words that look like name parts
    (words not in the ignore list, any casing). Returns [] if none found.
    """
    import re
    # Strip possessives and punctuation, split into words (Unicode-aware)
    cleaned = re.sub(r"['\u2019]s\b", "", text)
    words = re.findall(r"[A-Za-z\u00C0-\u024F]+", cleaned)

    name_words = []
    for w in words:
        low = w.lower()
        if len(w) >= 2 and low not in _IGNORE_WORDS:
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
        return True

    import re
    student_words = [w.lower() for w in re.findall(r"[A-Za-z\u00C0-\u024F]+", student_name) if len(w) >= 2]
    if not student_words:
        return True

    return any(sw in message_names for sw in student_words)
```

**Design notes:**
- No uppercase requirement — works with "email charles cavanaugh", "EMAIL CHARLES", etc.
- Unicode-aware regex (`\u00C0-\u024F`) on **both** sides — handles accented names (Ángela, José, Ñoño)
- Ignore list filters common English words to avoid false positives on confirmations
- Returns `[]` for messages with no name-like words → guard skips (allows "yes", "looks good")

---

## Edit 2: Guard function (`assistant_routes.py:1218-1272`)

**Location:** After `_student_name_in_message`, before the `# CHAT ENDPOINT` comment block

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

**Design notes:**
- Pure function — no side effects, no imports, no global state
- Handles both `student_names` (list) and `student_name` (string) parameter formats
- Returns early at each layer — first failure wins
- Non-send tools and period-based sends (no student names) pass through immediately

---

## Edit 3: Capture last user message text (`assistant_routes.py:1362-1374`)

**Location:** Inside `generate()`, after `messages = list(conv["messages"])`

```python
        # Extract the last user message text for send-tool name guard
        _last_user_text = ""
        for _msg in reversed(messages):
            if isinstance(_msg, dict) and _msg.get("role") == "user":
                _content = _msg.get("content", "")
                if isinstance(_content, str):
                    _last_user_text = _content
                elif isinstance(_content, list):
                    for _block in _content:
                        if isinstance(_block, dict) and _block.get("type") == "text":
                            _last_user_text = _block.get("text", "")
                            break
                break
```

---

## Edit 4: Dispatch loop call site (`assistant_routes.py:1744-1752`)

**Location:** In the tool dispatch loop, after the confirmation-tool guard, before `execute_tool()`

```python
                    # Send-tool guards: require lookup + user-message name match
                    if result is None:
                        result = _check_send_tool_guard(
                            tb["name"], tool_input, _resolved_students, _last_user_text
                        )

                    # ── Execute tool (only if no guard blocked it) ──
                    if result is None:
                        result = execute_tool(tb["name"], tool_input)
```

**Design notes:**
- `result = None` is set at the top of the guard block (line 1731)
- Confirmation-tool guard may set `result` to an error before this
- `_check_send_tool_guard` only runs if `result is None` (no prior guard fired)
- `execute_tool` only runs if `result` is still `None` after all guards

---

## Tests (`tests/test_assistant_name_guard.py`) — 29 total

### TestExtractUserMessageNames (10 tests)

| Test | What it verifies |
|------|-----------------|
| `test_extracts_full_name` | "Charles Cavanaugh" extracted from normal message |
| `test_extracts_name_with_possessive` | "Troy Mikell" extracted despite possessive 's |
| `test_returns_empty_for_no_names` | "yes send it" → [] (all in ignore list) |
| `test_returns_empty_for_generic_confirmation` | "looks good, send now" → [] |
| `test_ignores_common_words` | "Dear", "Please" filtered by ignore list |
| `test_extracts_name_after_preposition` | "London Samuel" extracted from "send a message to..." |
| `test_handles_multiple_names` | Both "Charles" and "London" from one message |
| `test_extracts_lowercase_names` | "charles cavanaugh" from all-lowercase input |
| `test_extracts_allcaps_names` | "CHARLES CAVANAUGH" from all-caps input |
| `test_extracts_unicode_names` | "José", "Ángela" from Unicode input |

### TestNameOverlapCheck (11 tests)

| Test | What it verifies |
|------|-----------------|
| `test_matching_name_returns_true` | Correct name matches |
| `test_mismatched_name_returns_false` | Wrong name blocked |
| `test_partial_name_match` | "Charles" matches "Charles Cavanaugh" |
| `test_skips_check_for_confirmations` | "yes send it" → True (skip) |
| `test_skips_check_for_short_messages` | "looks good" → True (skip) |
| `test_case_insensitive` | "charles" matches "CHARLES" |
| `test_name_with_middle_name` | "Troy Jaxson Mikell" matches "Troy Mikell" |
| `test_lowercase_message_blocks_wrong_student` | Lowercase "charles" blocks "Troy" |
| `test_lowercase_message_allows_correct_student` | Lowercase "charles" allows "Charles" |
| `test_unicode_name_matches` | "Ángela Ñoño" matches on both sides |
| `test_unicode_name_blocks_mismatch` | "Ángela Ñoño" blocked when message says "Charles" |

### TestSendToolGuard (8 tests) — dispatch-level

| Test | What it verifies |
|------|-----------------|
| `test_blocks_when_no_lookup` | Layer 1: no `lookup_student_info` called → blocked |
| `test_blocks_when_user_message_mismatch` | Layer 2: tool targets "Troy" but message says "Charles" → blocked |
| `test_blocks_when_cross_tool_mismatch` | Layer 3: tool targets "Troy" but lookup resolved "Charles" → blocked |
| `test_passes_when_all_checks_match` | All three layers pass → `None` (proceed) |
| `test_passes_for_non_send_tool` | `query_grades` skips all guards → `None` |
| `test_passes_for_period_send_without_student_names` | Period-based send with no names → `None` |
| `test_passes_for_confirmation_message` | "yes send it" has no names → Layer 2 skips → `None` |
| `test_handles_student_name_param` | `student_name` (string) handled same as `student_names` (list) |

---

## End-to-end flow

```
User: "draft an email to charles cavanaugh's parents about his defiance"

LLM calls send_focus_comms(student_names=["Troy Jaxson Mikell"], ...)

  _check_send_tool_guard():
    Layer 1: resolved_students is empty
             → returns error: "You must call lookup_student_info first"
  execute_tool NEVER RUNS

LLM retries: lookup_student_info("Troy Jaxson Mikell")
LLM calls send_focus_comms(student_names=["Troy Jaxson Mikell"], ...)

  _check_send_tool_guard():
    Layer 1: resolved_students has Troy → passes
    Layer 2: _student_name_in_message("Troy Jaxson Mikell", "...charles cavanaugh...") → False
             → returns error: "user's message does not mention this student"
  execute_tool NEVER RUNS

LLM re-reads message, calls lookup_student_info("Charles Cavanaugh")
LLM calls send_focus_comms(student_names=["Charles Cavanaugh"], ...)

  _check_send_tool_guard():
    Layer 1: resolved_students has Charles → passes
    Layer 2: _student_name_in_message("Charles Cavanaugh", "...charles cavanaugh...") → True
    Layer 3: "charles cavanaugh" matches resolved lookup → True
             → returns None
  execute_tool RUNS — correct student ✓
```

---

## Commits

| SHA | Description |
|-----|-------------|
| `322b19b` | feat: add name extraction helpers for send-tool user-message guard |
| `eec7d1e` | feat: guard send tools against student name mismatch with user message |
| `a61ae55` | fix: move send-tool guards before execute_tool, harden name extraction |
| `374eafd` | fix: match Unicode regex in _student_name_in_message to _extract_message_names |
| `88e344b` | refactor: extract send-tool guard into testable function with dispatch-level tests |
