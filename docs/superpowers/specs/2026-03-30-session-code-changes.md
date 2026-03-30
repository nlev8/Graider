# Code Changes — March 29-30 Session

## 1. District Provider Switch (4 commits)

### `backend/routes/district_routes.py` — Auto-clear on provider switch
**Commit:** `3f8f1aa`

Added `_clear_old_provider_data(old_provider)` function that:
- Queries all classes from Supabase
- Identifies classes belonging to the old provider by `clever_section_id` pattern (`oneroster:` prefix = OneRoster, non-null no prefix = Clever, null = manual — KEEP)
- Deletes only provider-synced enrollments, classes, and orphaned students
- Preserves manually-created classes and CSV-imported data
- Cleans up local roster CSV files for affected teachers
- Returns count of affected teachers

Added provider switch detection in `POST /api/district/config` — runs AFTER new config saved:
```python
old_sis_type = existing_sis.get("sis_type")
if old_sis_type and old_sis_type != sis_type:
    cleared_count = _clear_old_provider_data(old_sis_type)
```

### `backend/routes/oneroster_routes.py` — Remove 409 block
**Commit:** `974338d`

Removed the 19-line provider exclusivity check from `sync_roster()` that returned 409 when Clever data existed. Replaced with comment explaining district-level enforcement.

### `frontend/src/tabs/SettingsTab.jsx` — Remove switch buttons
**Commit:** `00f7624`

Removed:
- "Switch to Clever" button (shown when OneRoster active)
- "Switch to OneRoster" button (shown when Clever active)
- Switch confirmation dialog
- `showSwitchProviderConfirm` state variable

95 lines deleted. All other OneRoster/Clever UI preserved.

### `tests/test_district_routes.py` — Provider switch tests
**Commit:** `8225c05`

Added `TestProviderSwitch` class with 2 tests:
- `test_provider_switch_triggers_cleanup` — switching clever→oneroster calls `_clear_old_provider_data("clever")`
- `test_same_provider_no_cleanup` — saving same type does NOT trigger cleanup

---

## 2. Student Data Fixes (5 commits)

### `backend/routes/settings_routes.py` — Auto-generate student_id
**Commit:** `5ae206c`

Added before the filepath check in `add_student()`:
```python
if not student_id:
    import uuid
    student_id = "manual-" + str(uuid.uuid4())[:8]
```
Parent contacts are keyed by student_id — without one, contact info was silently dropped.

### `backend/routes/settings_routes.py` — Save contacts to Supabase
**Commit:** `64f4ab1`

Changed `_save_parent_contacts()` from file-only to dual-write:
```python
def _save_parent_contacts(contacts, teacher_id=None):
    with open(PARENT_CONTACTS_FILE, 'w') as f:
        json.dump(contacts, f, indent=2)
    if teacher_id and storage_save:
        try:
            storage_save('parent_contacts', contacts, teacher_id)
        except Exception:
            pass
```
GET `/api/parent-contacts` reads from Supabase first — file-only saves were invisible to authenticated users.

### `frontend/src/tabs/SettingsTab.jsx` + `backend/routes/settings_routes.py` — Student Email field
**Commits:** `8966b13`, `d9d1b5e`

Added Student Email column to period student table between ID and Parent Emails:
- New `<th>` header
- Display mode: shows `student.student_email`
- Edit mode: editable `<input type="email">` field
- Add student form: new Student Email input
- Backend: `student_email` field saved in contacts dict and included in `update_student`

### `backend/routes/settings_routes.py` — Merge student emails from grading results
**Commit:** `b5b1955`

Added to `GET /api/parent-contacts` before returning:
```python
results = storage_load('results', teacher_id)
if results:
    for r in results:
        sid = r.get('student_id', '')
        email = r.get('student_email', '')
        if sid and email and sid in contacts:
            if not contacts[sid].get('student_email'):
                contacts[sid]['student_email'] = email
```
Students who have been graded now show their email in the period table without manual entry.

---

## 3. National Standards Coverage (6 commits)

### `backend/routes/planner_routes.py` — Fix science fallback
**Commit:** `564b23f`

Changed fallback condition from:
```python
if not standards and framework not in ('ccss', 'ngss'):
```
To:
```python
if not standards:
    fallback_fw = subject_fallbacks.get(subject)
    if fallback_fw and fallback_fw != framework:
```
CCSS states can now fall back to NGSS for science.

### Standards data files (4 commits)
**Commits:** `49616cf`, `c7fe74f`, `e99e3f1`, `85551f5`

Created 20 new standards files:

| Framework | Files | Standards |
|-----------|-------|-----------|
| CCSS (C3 Framework) | us_history, civics, geography, world_history | ~180 |
| TX TEKS | math, ela, science, social_studies, us_history, world_history, civics, geography | ~380 |
| VA SOLs | math, ela, science, social_studies, us_history, world_history, civics, geography | ~380 |

All with full 8-field schema: code, benchmark, topics, dok, item_specs, essential_questions, learning_targets, vocabulary, sample_assessment.

---

## 4. Export Formatting Fixes (3 commits)

### `backend/routes/planner_routes.py` — DOCX + PDF export fixes
**Commit:** `60104f2`

**Title formatting:**
```python
heading = doc.add_heading(title, 0)
for run in heading.runs:
    run.font.size = Pt(24)
    run.font.color.rgb = RGBColor(0, 0, 0)
doc.add_paragraph()  # Skip line after title
```

**Remove time limit** from both DOCX and PDF:
```python
# Before:
if time_estimate or total_points:
    meta_parts.append(f"Time: {time_estimate}")
# After:
if total_points:
    meta_para.add_run(f"Total Points: {total_points}")
```

**Black font on all questions** (prevents white-on-white from Graider table header styling):
```python
_nr = q_para.add_run(f"{q_number}. ")
_nr.bold = True
_nr.font.color.rgb = RGBColor(0, 0, 0)
_tr = q_para.add_run(q_text)
_tr.font.color.rgb = RGBColor(0, 0, 0)
```
Applied to all 5 question type blocks: MC/TF, data_table, matching, essay, coordinates.

**Remove Graider answer table for MC/TF** (bubbles are the answer):
```python
# Removed:
_add_graider_table(doc, f"Answer for Question {q_number}",
                   f"GRAIDER:QUESTION:{q_number}", q_points,
                   graider_style, 720)
```

**Section header spacing:**
```python
doc.add_heading(f"{section_name}{pts_text}", level=1)
doc.add_paragraph()  # Space between section header and questions
```

### `backend/routes/planner_routes.py` — Matching table crash fix
**Commit:** `72f6ba3`

Removed stale `run.italic = True` reference. The black font refactor renamed `run` to `_pr`, but this line was left behind, causing a `NameError` that crashed the matching question export (no table rendered).

---

## 5. Resource-Only Assignment Generation (1 commit)

### `backend/routes/planner_routes.py` — Questions from resources when no standards
**Commit:** `b0a5404`

Changed the reference docs prompt block based on whether standards are selected:

```python
if config_standards:
    # Standards active — docs are supplementary
    ref_docs_block = "=== REFERENCE DOCUMENTS (supplementary content) ===\n"
    ref_docs_block += "Use content from these documents while aligning to standards.\n"
else:
    # NO standards — create ALL questions from documents
    ref_docs_block = "=== SOURCE DOCUMENTS (create ALL questions from this content) ===\n"
    ref_docs_block += "CRITICAL: Generate ALL questions directly from the document content. "
    ref_docs_block += "Every question must be answerable using information in these documents.\n"
```

---

## 6. Settings Reorganization (1 commit)

### `frontend/src/tabs/SettingsTab.jsx` — Move State/Grade/Subject to General
**Commit:** `3857b45`

Cut State, Grade Level, and Subject dropdowns from Grading tab and added them to General tab between School Name and Email Signature. Grade options limited to 6-12 (removed K-5). Grading tab now starts with Grading Period.

---

## 7. Create Button Fix (1 commit)

### `frontend/src/tabs/PlannerTab.jsx` — Enable Create when resources uploaded
**Commit:** `9bb0993`

Changed disabled condition from:
```javascript
disabled={plannerLoading || selectedStandards.length === 0}
```
To:
```javascript
disabled={plannerLoading || (selectedStandards.length === 0 && uploadedDocs.length === 0)}
```
Applied to both Create and Generate Variations buttons. Teachers can now create assignments from uploaded resources without selecting standards.
