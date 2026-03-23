# Assistant Tools FERPA/Clever Compliance — Design Spec

## Goal

Make all 80 assistant tools fully FERPA and Clever compliant by enforcing teacher-scoped data access, adding audit logging for sensitive operations, anonymizing student PII before external AI calls, eliminating local file writes containing student data, and scoping survey data to the creating teacher.

## Architecture

Introduce a centralized compliance module (`backend/utils/compliance.py`) that provides reusable primitives for audit logging, PII anonymization, and teacher_id enforcement. Extract `audit_log()` from `app.py` into `backend/utils/audit.py` to avoid circular imports. All 14 assistant tool files are updated to use these primitives. No new database tables — leverages existing `audit_log` table and `teacher_data` storage abstraction.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| External AI PII handling | Anonymize before sending | FERPA requires data minimization; strip names, keep accommodation types for context |
| Local file writes with PII | Eliminate entirely | Railway containers are ephemeral; return in-memory responses or use Supabase |
| Survey scoping | Strict teacher-only | Each teacher sees only their own surveys |
| Compliance pattern | Centralized module | Single auditable source of truth vs. duplicated logic across 14 files |
| `_load_master_csv` data source | Replace with `storage.load('results', teacher_id)` | Current CSV reads from shared filesystem — the biggest cross-teacher leakage vector |

---

## Component 1: Compliance Module (`backend/utils/compliance.py`)

New module with three core functions.

### `audit_tool_action(teacher_id, tool_name, action, details=None)`

Standardized audit logging for all assistant tool operations.

- Calls `audit_log()` from `backend/utils/audit.py` (extracted from `app.py` to avoid circular imports) with format: `TOOL_{tool_name}_{action}`
- Supported actions: `INVOKE`, `EXPORT`, `DELETE`, `SEND_EMAIL`, `SEND_AI`, `MODIFY_DATA`
- `INVOKE` logged for ALL tools that access student data (done once in `execute_tool()` for tools marked as data-accessing, not in each handler)
- Details auto-truncated to 500 chars
- PII auto-stripped from details (student names replaced with `student_***`)
- Always includes teacher_id for attribution
- Note: the existing `audit_log()` Supabase insert is synchronous (~50ms), not async

### `anonymize_for_ai(text, roster)`

Strips student PII from text before sending to external AI services.

- `roster` is a **required** parameter — raises `ValueError` if `None` in production mode (when Supabase is configured). In dev mode, falls back to regex-based detection with a logged warning.
- Returns `(anonymized_text, mapping_dict)`
- Replaces student names with tokens: `[STUDENT_1]`, `[STUDENT_2]`, etc.
- Uses exact name matching from roster (handles "Last, First", "First Last", "First L." formats)
- IEP/504 accommodation *types* preserved (needed for AI context); student identifiers stripped
- Also anonymizes free-text fields (e.g., accommodation `notes` that may contain names like "Maria's mother requested...")
- `deanonymize(text, mapping_dict)` reverses the mapping for the response back to the teacher
- Note: if Claude paraphrases or drops `[STUDENT_N]` tokens, deanonymization silently passes through — manual QA should verify this in practice

### `require_teacher_id(teacher_id)`

Guard function for data access.

- Raises `ValueError` if teacher_id is `None`, empty string, or `'local-dev'` when Supabase is configured
- In dev mode (no Supabase), allows `'local-dev'` as valid
- Called at the top of every tool that accesses student data

---

## Component 1b: Extract `audit_log()` (`backend/utils/audit.py`)

Move the existing `audit_log()` function from `app.py` (lines 216-245) into `backend/utils/audit.py` to prevent circular imports. `app.py` imports from `audit.py`; `compliance.py` imports from `audit.py`. The function signature, dual-write behavior (local file + Supabase), and truncation logic remain unchanged.

---

## Component 2: Fix `_load_master_csv` Data Source (CRITICAL)

### Problem

`_load_master_csv()` in `assistant_tools.py` (line 246) reads directly from `{output_folder}/master_grades.csv` via `_get_output_folder()` — a shared local filesystem path. In multi-teacher production, all teachers share the same `output_folder`, so one teacher's assistant queries return another teacher's grades. This is the most-used data path across all grading/analytics tools.

Additionally, `_load_master_csv` internally calls `_load_results()` to merge JSON results. If `_load_results()` is updated to accept teacher_id but `_load_master_csv` doesn't pass it through, the merge step still loads unscoped results.

### Fix

Replace `_load_master_csv(teacher_id)` implementation:
1. Load results via `storage.load('results', teacher_id)` (Supabase-scoped) instead of reading from shared CSV
2. Convert the loaded JSON results into the same DataFrame format the current callers expect
3. Pass `teacher_id` through to internal `_load_results()` call for the merge step
4. Keep the CSV fallback only in dev mode (no Supabase) for backward compatibility

This is a single function change, but it's the highest-impact fix because 15+ downstream tools all call `_load_master_csv`.

---

## Component 3: Tool Handler Updates (14 files)

### Pattern applied to every tool accessing student data

1. Add `teacher_id='local-dev'` to function signature (prevents `execute_tool()` from stripping it)
2. Call `require_teacher_id(teacher_id)` at entry
3. Pass `teacher_id` to all data-loading helpers: `_load_master_csv()`, `_load_results()`, `_load_roster()`, `_load_settings()`, `_load_accommodations()`
4. Call `audit_tool_action()` for sensitive operations (exports, deletions, emails, AI calls)

### File-by-file changes

| File | Tools | Change |
|------|-------|--------|
| `assistant_tools.py` (shared helpers) | `_load_master_csv`, `_load_roster`, `_load_results`, `_load_settings`, `_load_accommodations` | Accept `teacher_id` param, pass to `storage.load()`. `_load_master_csv` replaced to use Supabase-scoped results (see Component 2). |
| `assistant_tools_grading.py` | `query_grades`, `get_student_summary`, `get_class_analytics`, `get_assignment_stats`, `analyze_grade_causes`, `get_feedback_patterns`, `compare_periods`, `get_missing_assignments`, `scan_submissions_folder` | Add `teacher_id` param, pass to data loaders |
| `assistant_tools_analytics.py` | `get_grade_trends`, `get_rubric_weakness`, `flag_at_risk_students`, `compare_assignments`, `get_grade_distribution`, `detect_score_outliers` | Add `teacher_id` param, pass to data loaders |
| `assistant_tools_communication.py` | `draft_student_feedback`, `generate_parent_conference_notes`, `generate_report_card_comments` | Add `teacher_id`, audit sensitive data access |
| `assistant_tools_planning.py` | `suggest_remediation`, `suggest_grouping`, `generate_bell_ringer`, `generate_exit_ticket`, `generate_sub_plans`, `get_pacing_status`, `recommend_next_lesson`, `get_calendar`, `schedule_lesson_tool`, `unschedule_lesson_tool`, `add_calendar_holiday`, `create_focus_assignment` | Add `teacher_id`, pass to loaders + calendar storage |
| `assistant_tools_reports.py` | `generate_progress_report`, `export_grades_csv`, `lookup_student_info`, `send_parent_emails`, `send_focus_comms`, `confirm_and_send`, `create_focus_assignment`, `recommend_next_lesson` | Add `teacher_id`, eliminate local file writes, audit exports + sends. `confirm_and_send` already accepts `teacher_id` but reads from local `pending_send.json` — switch read to `storage.load('pending_send', teacher_id)`. |
| `assistant_tools_student.py` | `get_student_accommodations`, `get_student_streak`, `remove_student_from_roster`, `export_student_data`, `import_student_data` | Add `teacher_id`, eliminate local exports, audit deletions. `export_student_data` reads must also be converted from local files to `storage.load()` — currently reads from `~/.graider_results.json`, `~/.graider_data/student_history/`, `~/.graider_data/accommodations/`, `~/.graider_data/ell_students.json`, `~/.graider_data/parent_contacts.json` directly. All must use `storage.load(key, teacher_id)`. |
| `assistant_tools_data.py` | `save_memory` | Add `teacher_id`, scope memory to teacher via `storage.save()` |
| `assistant_tools_ai.py` | `generate_iep_progress_notes` | Add `teacher_id`, anonymize before Claude API call (including free-text accommodation `notes` fields), audit AI send |
| `assistant_tools_behavior.py` | Already has `teacher_id` | Add audit logging for `send_behavior_email`, anonymize `_generate_email_ai` before Claude call (including behavior notes/transcripts). Switch `_load_parent_contacts()` and `_load_settings()` to use `storage.load()` with teacher_id. |
| `assistant_tools_survey.py` | `create_parent_survey`, `get_survey_results`, `compile_survey_report` | Add `teacher_id`, store in survey record, filter queries by teacher |
| `assistant_tools_automation.py` | `list_automations_tool`, `create_automation_tool`, `run_automation_tool` | Add `teacher_id`, scope automation storage to teacher |
| `assistant_tools_edtech.py` | — | No changes (generates content from standards, no student data) |
| `assistant_tools_stem.py` | — | No changes (stateless math computation) |

---

## Component 4: Eliminate Local File Writes

All tools that currently write student PII to disk are converted to in-memory responses or Supabase storage. **Both reads and writes** are converted — not just writes.

| Current path | Current content | Replacement |
|-------------|----------------|-------------|
| `~/.graider_exports/student/*.json` | Student PII: IEP/504, ELL, parent contacts, grades | Return base64 JSON in tool response body, no disk write. All reads in `export_student_data` also converted to `storage.load()`. |
| `~/.graider_exports/focus/*.csv` | Student IDs and scores | Return CSV as base64 string in tool response body |
| `~/.graider_data/pending_send.json` | Parent emails, student names | Supabase `teacher_data` with key `pending_send` scoped by teacher_id. Both write (`send_parent_emails`) AND read (`confirm_and_send`) converted. |
| `~/.graider_data/assistant_memory.json` | Teacher memories (may reference students) | Supabase `teacher_data` with key `assistant_memory` scoped by teacher_id. Already synced by `sync_all_to_cloud()` in `storage.py`. |
| `~/.graider_data/automations/` | Automation workflow configs | Supabase `teacher_data` with key `automations` scoped by teacher_id. NOT currently synced by `sync_all_to_cloud()` — must extend it. |

**Migration:** `sync_all_to_cloud()` in `storage.py` currently handles `assistant_memory`. Must be extended to also sync `pending_send` and `automations` keys for existing local data migration.

**Temporary files** (e.g., PDF generation in `/tmp`) are acceptable if cleaned up immediately after streaming the response.

---

## Component 5: Anonymization for External AI

Two tools send student PII to external AI APIs:

### `generate_iep_progress_notes` (assistant_tools_ai.py)

**Current:** Sends student name, grade history, IEP accommodation details (including free-text `notes` field) to Claude API.

**Fix:**
1. Load roster via `_load_roster(teacher_id)`
2. Build prompt as usual
3. Call `anonymize_for_ai(prompt, roster)` → strips names from all fields including accommodation notes
4. Send anonymized prompt to Claude
5. Call `deanonymize(response, mapping)` → restore names
6. `audit_tool_action(teacher_id, 'generate_iep_progress_notes', 'SEND_AI', 'anonymized prompt sent to Claude')`

### `_generate_email_ai` (assistant_tools_behavior.py)

**Current:** Sends student name and behavior notes (including correction notes, STT transcripts) to Claude API.

**Fix:** Same pattern — load roster, anonymize all PII (name + behavior notes content), send to Claude, deanonymize response, audit the call.

---

## Component 6: Survey Scoping

### `create_parent_survey`
- Add `teacher_id` field to the Supabase insert

### `get_survey_results`
- Add `.eq('teacher_id', teacher_id)` to all queries
- Remove the fallback that returns all surveys when no join_code provided

### `compile_survey_report`
- Same teacher_id filter on survey lookup

---

## Component 7: Testing

### Backend pytest — compliance module
- `test_audit_tool_action`: Verifies log entries written with correct format
- `test_anonymize_deanonymize_roundtrip`: Names stripped → restored correctly
- `test_anonymize_preserves_accommodation_types`: IEP/504 types kept, names stripped
- `test_anonymize_handles_free_text_notes`: Accommodation notes with embedded names are anonymized
- `test_anonymize_requires_roster_in_prod`: Raises ValueError without roster when Supabase configured
- `test_require_teacher_id_blocks_missing`: Raises ValueError for None/empty
- `test_require_teacher_id_blocks_local_dev_in_prod`: Blocks 'local-dev' when Supabase configured
- `test_require_teacher_id_allows_local_dev_in_dev`: Allows 'local-dev' when no Supabase

### Backend pytest — tool handler signatures
- Extend `test_tool_schemas.py`: verify every tool handler that accesses student data accepts `teacher_id` parameter
- List of tools that MUST accept teacher_id (all except edtech + stem tools)

### Backend pytest — no local PII writes
- Test that `export_student_data` returns base64 content, not a file path
- Test that `export_grades_csv` returns base64 content, not a file path
- Verify no tool function calls `open()` or `os.makedirs` on PII-specific export paths (`~/.graider_exports/`, `~/.graider_data/pending_send`) — scoped to export paths only, not all `open()` usage

### Backend pytest — data scoping
- Test that `_load_master_csv(teacher_id='teacher-A')` does not return results belonging to `teacher-B`
- Test that `get_survey_results(teacher_id='teacher-A')` does not return surveys created by `teacher-B`

---

## Out of Scope

- Consent management UI for AI data processing (future feature)
- Encryption at rest for Supabase data (handled by Supabase platform)
- FERPA deletion endpoint expansion (separate task in remaining work backlog)
- Frontend changes (this is entirely backend)

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Breaking existing tool behavior | Every tool handler change is additive (new param with default). Existing callers unaffected. |
| Missing a tool handler | `test_tool_schemas.py` extension catches any tool that doesn't accept teacher_id |
| Anonymization quality | Roster required in production; exact name matching handles "Last, First" and "First Last" formats |
| Deanonymization failure | If Claude drops `[STUDENT_N]` tokens, text passes through unchanged — logged warning, manual QA during rollout |
| Performance overhead | `audit_tool_action` uses synchronous Supabase insert (~50ms) + local file append — same as existing `audit_log` pattern |
| Circular imports | `audit_log()` extracted to `backend/utils/audit.py` — both `app.py` and `compliance.py` import from it |
| `_load_master_csv` migration | Dev-mode fallback to local CSV preserved; Supabase path returns same DataFrame format; downstream callers unchanged |
