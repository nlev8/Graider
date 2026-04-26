# Phase 4 — Quick-Click Remediation (Design)

**Status:** approved after 2 Codex review rounds (4 MAJOR + 2 MINOR + 1 NIT round 1; 4 MAJOR + 3 MINOR + 1 NIT round 2 — all reconciled).
**Decomposed from:** Plan B Phase 4 in `project_progress_tracking_roadmap.md`.
**Differentiator vs Progress Learning:** they ship static remediation banks; Graider generates targeted practice on-demand from each red-tier mastery gap.

## Goal

From the Phase 2 Progress Rank grid, a teacher clicks a red mastery cell or a column header → AI generates 8 practice questions for that standard at grade level → teacher reviews/edits in a drawer → publishes to either one student (cell click) or all current red-tier students on that standard (column click). Mastery rollup updates after each submission, closing the loop.

## Locked decisions (from brainstorming, 2026-04-26)

- **Q1 → A.** Remediation = a 5-10 question practice mini-assessment (fixed at 8). Published as `content_type='assessment'` so existing rollup + Gradebook + Comparison views pick it up automatically.
- **Q2 → C.** Two trigger paths in `ProgressRankGrid.jsx`: cell-click popover (single-student) + column-header reveal (class-wide red-tier). StudentReportCard and Phase 3b heatmap deferred to 4.2.
- **Q3 → B.** Preview-then-publish drawer (Planner-style). NOT auto-publish — teacher gates content before students see it.
- **Q4 → A.** Fixed defaults: 8 questions, 5 multiple choice + 3 short answer, grade level inferred from `classes` metadata. No pre-generation config dialog.
- **Q5 → B.** Single-student honors accommodations (via existing helper, with try/except fall-through to grade level on failure). Class-wide stays grade-level only.
- **Architecture → Approach 2.** Dedicated `POST /api/teacher/remediate` route wrapping the existing `_post_process_assignment` pipeline. NOT extending the planner blueprint.

## Non-goals (Phase 4.2 backlog — see `project_phase4.2_backlog.md`)

- Lesson-text remediation (mini-lesson + practice combo)
- Per-student generation in class-wide mode (N AI calls)
- Pre-generation config dialog or full Planner config
- Recall / "undelete" UX (manual `is_active=false` flip is the escape hatch)
- Remediation audit trail / "did it work" dashboard
- Remediation badge / grouping in Gradebook
- Per-student weekly cap
- Pure auto-publish path
- AssessmentComparison heatmap as third trigger surface
- Per-question regenerate (full-batch only in MVP)

---

## Architecture

### Backend — one new route + one shared helper + one route hardening

**New route:** `POST /api/teacher/remediate` in `backend/routes/student_portal_routes.py` (analytics surface, alongside Phase 2/2b/3a/3b endpoints). Wraps existing `_post_process_assignment` from `backend/services/assignment_post_processing.py`.

**New shared helper:** `_content_visible_to_student(db, content_id, student_id, class_id) -> bool` — module-level helper added to `backend/routes/student_account_routes.py`. Centralizes the targeting check so all student-facing read AND write paths apply it consistently.

**Hardening of existing route:** `publish_to_class` (in `student_account_routes.py`) currently does NOT verify `g.teacher_id` owns `class_id`. Phase 4 closes that gap as part of extending the route with `target_student_ids` support — the validation is required regardless of whether the publish is targeted.

### Schema — one column

```sql
ALTER TABLE published_content
  ADD COLUMN target_student_ids JSONB NULL;
```

Semantics:
- `NULL` → publish to whole class (existing behavior; zero-impact migration).
- Non-empty JSONB array of student UUIDs → visible only to those students.
- Empty array `[]` → invalid degenerate state. Validated against at write time (publish endpoint rejects 400). NEVER stored.

No GIN index in MVP (deferred until EXPLAIN justifies it; see Phase 4.2 backlog if scale grows). Existing `idx_published_class` on `(class_id, is_active)` filters down before the JSONB containment check matters.

### Frontend — one new component + 2 attach points

**New component:** `frontend/src/tabs/RemediationDrawer.jsx` (~250 LOC). Side drawer at z-index 9500 (matches Phase 2b/3a precedent). Owns its own fetch lifecycle, edit state, and pre-publish validation.

**Attach points** (both in `frontend/src/tabs/ProgressRankGrid.jsx`):
1. Cell-click popover gets a "Generate remediation" button.
2. Standard column header gets a "Remediate" affordance, revealed on hover/focus to avoid clutter on wide grids.

### Lifecycle

1. Teacher clicks → frontend opens drawer with `{class_id, standard_code, target_mode, target_student_id?}`.
2. Drawer POSTs to `/api/teacher/remediate`. Backend validates, generates, returns generated questions + the resolved `target_student_ids` list (NOT yet published).
3. Drawer renders editable cards in `preview` state. Teacher can edit text, edit MC choices, regenerate the full batch, or publish.
4. On Publish: drawer runs **frontend pre-publish validation**, then POSTs to `/api/publish-to-class` with the EXACT `target_student_ids` list returned at generate time. Publish endpoint validates ownership + targeting, inserts row.
5. Drawer shows success toast, closes after 2s. Parent `ProgressRankGrid` re-fetches mastery so cell colors update once students submit.

---

## Backend endpoint contract

### `POST /api/teacher/remediate`

**Decorators:** `@require_teacher`, `@handle_route_errors`, `@limiter.limit("10 per minute")` (explicit — does NOT inherit the planner blueprint's limit).

**Request body:**
```json
{
  "class_id": "uuid",
  "standard_code": "MA.6.AR.1.2",
  "target_mode": "single_student" | "red_tier_in_class",
  "target_student_id": "uuid"
}
```

`target_student_id` required iff `target_mode == "single_student"`; otherwise rejected.

**Validation order (6 steps; matches Phase 3b precedent):**

1. **Class ownership.** `classes.teacher_id == g.teacher_id` → 403 via `error_response`.
2. **target_mode.** Must be one of the two literals → 400.
3. **target_student_id (single_student only).** UUID-validate, must be in `class_students JOIN students` for this class → 400 / 403.
4. **standard_code.** Non-empty string → 400.
5. **Historical evidence (single_student only).** That student's most recent submission must contain `standard_code` in `results.standards_mastery`. If none → 400 with detail "No prior assessment data on this standard for {student}". Logged as `remediation.no_historical_evidence`.
6. **Red-tier resolution (red_tier_in_class only).** Compute current mastery on `standard_code` for every enrolled student via existing `_aggregate_mastery_for_student(..., 'latest')`. Take the set whose mastery <70%. If empty → 400 with detail "No red-tier students on this standard". Logged as `remediation.no_red_tier_students`.

### Generation (after validation)

- Resolve `grade_level` and `subject` from `classes.grade_level` / `classes.subject` (existing columns).
- Build remediation prompt:
  > "Generate 8 grade-{N} {subject} practice questions targeting standard {standard_code}. Mix: 5 multiple-choice questions (4 choices each, exactly 1 correct) and 3 short-answer questions. Difficulty: grade-level review. Each question must include a `standard` field equal to `{standard_code}`."
- **Single-student path:** call whatever accommodation helper portal grading uses, wrapped in `try/except` → on failure log `remediation.accommodations_helper_failed` (warning) and fall through to grade-level. On success, append the returned segment to the prompt. Implementer pins the exact API surface in Bundle 1; FERPA contract (no student name leaks to AI) is preserved by the existing helper.
- **Class-wide path:** no accommodation injection.
- Call `_post_process_assignment(...)` orchestrator.
- `_record_planner_cost` runs automatically inside the orchestrator (existing infra).

### Response

```json
{
  "questions": [...],
  "target_mode": "single_student" | "red_tier_in_class",
  "target_student_ids": ["uuid", ...],
  "standard_code": "MA.6.AR.1.2",
  "generated_at": "2026-04-26T17:30:00Z"
}
```

`target_student_ids` is the resolved list (single-student → 1 element; red-tier → N elements). The drawer round-trips this exact list to publish — no re-resolution.

### Error contract (RFC 7807 via `error_response`)

| Status | When |
|---|---|
| 400 | Missing/invalid input; no historical evidence; no red-tier students |
| 403 | Wrong teacher; cross-class injection; target_student_id not in class |
| 422 | Generation produced fewer than 3 valid questions after post-processing (AI refused or returned malformed shapes) |
| 500 | Uncaught (handled by `@handle_route_errors`) |

Plus 401 plain JSON via `@require_teacher` (pre-existing decorator behavior).

### Cost & observability

- Costs land in `~/.graider_data/planner_costs.json` via existing `_record_planner_cost`. No source tag (Phase 4.2 backlog).
- 3 structured log events ride Phase 5a infra → Better Stack:
  - `remediation.generated` (info) — `class_id`, `mode`, `standard`, `target_count`, `cost_tokens`
  - `remediation.no_red_tier_students` (warning) — paired with 400
  - `remediation.no_historical_evidence` (warning) — paired with 400
- Plus the conditional `remediation.accommodations_helper_failed` (warning) when the helper raises.

---

## Schema migration + visibility model

### Migration file

`backend/database/migration_2026_04_26_phase4_target_student_ids.sql`:

```sql
-- Phase 4 — Quick-Click Remediation: target_student_ids column
ALTER TABLE published_content
  ADD COLUMN IF NOT EXISTS target_student_ids JSONB NULL;
```

Companion rollback: `rollback_2026_04_26_phase4_target_student_ids.sql`:

```sql
ALTER TABLE published_content
  DROP COLUMN IF EXISTS target_student_ids;
```

### Migration safety

- `ADD COLUMN ... NULL` on Postgres ≥11 is metadata-only (no table rewrite, no row locks beyond the brief catalog write). Safe online.
- Pre-existing rows get `NULL` → preserve existing class-wide visibility unchanged.
- Run via the manual operator step (per `bug_alembic_bootstrap_prod_outage.md`); no Railway boot-hook.

### Canonical visibility rule

> A student sees a `published_content` row iff:
> 1. They're enrolled in `published_content.class_id` AND `class_students` is current (re-checked, not session-cached), AND
> 2. The row is `is_active = true`, AND
> 3. `target_student_ids IS NULL` OR `target_student_ids @> jsonb_build_array(student_id)`.

### Shared helper

`_content_visible_to_student(db, content_id, student_id, class_id) -> bool` — added at module scope in `student_account_routes.py`. Single source of truth for the visibility rule. Returns False on any rule failure. Logs `student.access.denied` (debug) when False so prod can audit unexpected denials.

### Endpoints requiring visibility-helper application

All six exist in `backend/routes/student_account_routes.py`:

| Endpoint | Path | Type | Notes |
|---|---|---|---|
| `student_dashboard` | `GET /api/student/dashboard` | read (list) | filter `target_student_ids.is.null,target_student_ids.cs.[<student_id>]` in the existing list query |
| `list_student_resources` | `GET /api/student/resources` | read (list) | same |
| `get_student_resource` | `GET /api/student/resource/<content_id>` | read (single) | call helper; 404 on deny |
| `get_student_content` | `GET /api/student/content/<content_id>` | read (single) | call helper; 404 on deny |
| `submit_student_work` | `POST /api/student/submit/<content_id>` | **write** | call helper; 404 on deny — prevents direct-URL submit bypass |
| `save_submission_draft` | `POST /api/student/submission/<content_id>/draft` | **write** | call helper; 404 on deny |
| `get_submission_draft` | `GET /api/student/submission/<content_id>/draft` | read (single) | call helper; 404 on deny |

Plus `_validate_student_session` re-checks `class_students` enrollment via the helper (rather than trusting the session-cached class_id).

### PostgREST list query update

In endpoints that fetch lists, the existing query gets one additional `.or_()` clause:

```python
needle = json.dumps([student_id])  # student_id pre-validated as UUID
db.table('published_content').select(...) \
  .in_('class_id', enrolled_class_ids) \
  .eq('is_active', True) \
  .or_(f'target_student_ids.is.null,target_student_ids.cs.{needle}') \
  .execute()
```

The `cs` operator maps to JSONB `@>` containment.

### `publish_to_class` hardening

Pre-existing endpoint at `student_account_routes.py::publish_to_class`. Three changes:

1. **Class ownership** (NEW). Before insert, validate `classes.teacher_id == g.teacher_id` for the supplied `class_id` → 403 if not.
2. **target_student_ids accepted** (NEW). If the request body includes a non-empty array:
   - Each entry must UUID-validate → 400.
   - Each entry must be in `class_students JOIN students` for this class → 400.
   - Empty array `[]` rejected → 400. Use `NULL` (or omit field) for class-wide.
3. **Backwards-compat preserved.** If `target_student_ids` is absent or `null`, insert with `NULL` → existing class-wide behavior unchanged.

This hardening would land in Phase 4 even if no other route used it — the ownership gap is a real pre-existing bug.

---

## Frontend — triggers, drawer, validation

### Triggers in `ProgressRankGrid.jsx`

**Trigger A — cell-click popover (single-student):**
- Existing popover already shows student name, standard, mastery%, contributing submissions.
- Add a "Generate remediation" button below the contributing-submissions list.
- Disabled when `mastery_percentage >= 85` (red and yellow cells eligible; greens never need remediation).
- On click: close popover, open `RemediationDrawer` with `{class_id, standard_code, target_mode: 'single_student', target_student_id}`.

**Trigger B — column-header (class-wide red-tier):**
- Each standard column header gets a small "Remediate" link as a sibling element.
- **Hover/focus reveal** (not always-visible) to avoid clutter on 30-column grids. Keyboard-accessible: visible on focus, dismissable via Tab-out.
- Hidden entirely if zero red-tier students in that column (the grid already has the cell data; computing red counts at 30×30 is fine without memoization).
- On click: open `RemediationDrawer` with `{class_id, standard_code, target_mode: 'red_tier_in_class'}` (no `target_student_id`).
- Sibling element placement preserves a future click-to-sort affordance on the header itself (Phase 3a.4 backlog).

### `RemediationDrawer.jsx`

**Lifecycle states:**

| State | Description |
|---|---|
| `idle` | Drawer opened; no fetch yet |
| `generating` | POST in flight; skeleton mirroring final card layout. **All controls disabled.** |
| `preview` | Questions returned; cards editable; Publish/Regenerate/Cancel enabled |
| `regenerating` | Re-POST in flight; previous draft kept behind translucent overlay for compare. **All controls disabled.** |
| `publishing` | Publish POST in flight. **All controls disabled.** |
| `success` | Toast + drawer auto-closes after 2s; parent re-fetches Progress Rank |
| `error` | RFC 7807 `detail` rendered inline; "Retry" button |

**Async cleanup** (mirrors `StudentReportCard.jsx` precedent):
- `useEffect` with `cancelled` flag — late responses after drawer close are ignored.
- 2s success-close `setTimeout` cleared on unmount.
- "Regenerate all" replaces local state entirely; if there are unsaved edits, show confirm dialog first.

**Layout:**

- **Header:** "Remediation: {standard_code}" + target subtitle.
  - Single-student: "for {student.name}".
  - Red-tier with ≤3 students: "for {name1}, {name2}, {name3}".
  - Red-tier with >3: "for {N} red-tier students".
- **Body:** scrollable editable question cards. Each card includes:
  - Question text (textarea, editable).
  - Type badge: "MC" or "SA".
  - For MC: 4 choice rows (each editable text + radio for correct-answer).
  - For SA: a single textarea for the model answer.
- **Footer (sticky):** Cancel / Regenerate all / Publish to {N}.

**Pre-publish validation** (runs on Publish click before the POST):

| Check | Failure UX |
|---|---|
| At least 1 question | Toast "At least one question required"; abort publish |
| Every question has non-empty `text` | Inline error on the offending card; abort |
| MC questions have ≥2 non-empty choices | Inline error on the offending card; abort |
| MC questions have exactly one correct answer marker | Inline error; abort |
| Correct-answer marker references a non-empty existing choice | Inline error; abort |

These checks are pure-frontend. The publish endpoint also validates `content_type` + `content` presence (existing behavior); the frontend gate prevents most footguns from reaching the backend.

**Editor reuse:** there is NO existing reusable `QuestionEditor` (only Planner-specific `QuestionEditOverlay`). Phase 4 ships a slim local editor inside `RemediationDrawer.jsx`.

**Drawer chrome:** Esc-to-close, click-outside-to-close, slide-in animation, z-index 9500 — mirrors `StudentReportCard.jsx` and `SubmissionDetail.jsx` precedent.

### Wire contract — generate vs publish

`/api/teacher/remediate` returns `target_student_ids: [...]` resolved at generate time. The drawer holds this list in local state and sends it VERBATIM to `/api/publish-to-class`. **Publish does NOT recompute red-tier.** Rationale: between generate and publish, mastery could change (e.g., a student submits a fresh attempt and crosses 70%); preserving the generate-time list keeps teacher intent stable.

---

## Accommodations integration

**Single-student path only** (per locked Q5).

After validation step 5 (historical evidence confirmed), the route attempts to enrich the prompt with the targeted student's accommodation profile.

**Implementer guidance** (NOT a rigid signature):
- Use whatever accommodation helper `portal_grading` uses for its per-submission grading flow. The Phase 4 implementer pins the exact API surface in Bundle 1 by reading the existing portal-grading call site.
- Wrap the call in `try / except`. On any exception (corrupt profile JSON, missing keys, helper signature mismatch): log `remediation.accommodations_helper_failed` (warning) and fall through to grade-level generation. **Never** 500 the route on accommodation failure.
- If the call returns an empty/empty-ish segment (no presets, no notes), skip appending it. Generation proceeds at grade level. No 400 or warning.

**FERPA guard:** the existing helper does NOT pass student name to the AI — it builds the segment in terms of accommodation behaviors only. Phase 4 inherits this contract; the route MUST NOT log or pass `student_name` to any prompt-construction step that doesn't already strip it.

**Audit log:** `_logger.info("remediation.accommodations_applied teacher=%s presets=%d", g.teacher_id, len(presets))` after successful append.

**Class-wide path:** no accommodations injection. Generation runs at grade level. Phase 4.2 backlog item: per-student generation in class-wide mode (would be N AI calls).

---

## Testing strategy

### New test file: `tests/test_remediation.py`

| Class | Count | Coverage |
|---|---|---|
| `TestRemediateValidation` | 10 | 401 unauth, 403 wrong teacher, 400 bogus target_mode, 400 missing target_student_id (single), 400 malformed UUID, 400 empty standard, 400 no historical evidence (single), 400 zero red-tier (class-wide), 403 cross-class injection, 403 target_student_id not in class |
| `TestRemediateGeneration` | 5 | happy single-student, happy red_tier, AI returns 0 questions → 422, missing grade metadata fallback, accommodations helper called (mocked) |
| `TestRemediateAccommodations` | 3 | helper success path, helper raises → 200 + grade-level fallback + warning log, empty profile → no segment + no warning |
| `TestRemediateRedTierResolution` | 3 | red_tier <70 included, no-submission students excluded, improved-past-70 excluded |
| `TestPublishToClassHardening` | 5 | 403 without ownership, 400 with non-enrolled target, 400 with empty array, NULL = class-wide preserved, edited-question round-trip integration test |
| `TestVisibilityHelper` | 3 | class-wide visible; targeted visible to listed; targeted invisible to non-listed |

**Total new in this file:** ~29 tests.

### Sibling-test additions (existing files; piggyback on existing mocks)

- `tests/test_student_account_coverage.py` — add 1 list-filter test per read endpoint (dashboard, resources). +2 tests.
- `tests/test_student_resources.py` — add 1 list-filter test for the resources path. +1 test.
- New `tests/test_student_content_visibility.py` (small, dedicated) — for the 5 single-row endpoints (resource content, content, submit, draft GET, draft POST). Each gets a "non-targeted student → 404" test asserting denial. **The 3 write paths (submit, draft GET, draft POST) get an explicit deny test, not just list-filter coverage.** +5 tests.

**Total new sibling tests:** ~8.

### Migration test

`tests/test_migration_target_student_ids.py` — runs the migration against a test schema, asserts `target_student_ids` column exists with `NULL` allowed, JSONB type. Mirrors the precedent (if any) from `tests/test_rls_migration_applies.py`.

### Sibling regression contract

The following test suites must continue passing post-Phase-4 (no behavior changes expected):

- `tests/test_gradebook.py`
- `tests/test_submission_detail.py`
- `tests/test_student_report_card.py`
- `tests/test_assessment_comparison.py`
- `tests/test_progress_rank.py` (if extant — implementer confirms during Bundle 1)
- All Clever / ClassLink / OneRoster / LTI suites

### Frontend testing

Build verification via `cd frontend && npm run build` only (project precedent). Manual smoke checklist included in implementation plan covers ~15 click paths.

---

## Edge cases & invariants

| Case | Expected behavior |
|---|---|
| Single-student remediation for a student whose mastery is 70% (yellow, not red) | Allowed. The cell-click trigger only requires <85; class-wide trigger requires <70. Single-student is teacher discretion. |
| Class-wide remediation when only 1 student is red-tier | Allowed. Generates one assessment, targets one student. Identical effect to clicking that cell. |
| Generate succeeds, AI returns 8 questions, but 6 fail post-processing validation | Returns 422 if final count < 3. The route's spec floor is 3 valid questions to be meaningful as a remediation quiz. |
| Teacher has 12 chips selected and clicks Publish, then closes the drawer mid-publish | The publish POST has already gone out; backend completes regardless. Frontend success state is suppressed (cancellation flag). On next visit, the targeted students see the assessment. |
| Network error mid-generation | `error` state with retry button; no partial state. |
| Network error mid-publish | `error` state. The publish endpoint is idempotent only if the frontend supplies the same payload — no server-side dedupe in MVP. Teacher can retry. |
| Student is removed from `class_students` after a remediation is published to them | They lose visibility immediately (`_validate_student_session` re-checks enrollment via helper). |
| Two different teachers each generate a remediation for the same standard at roughly the same time for overlapping students | Both publish independently. Each `published_content` row is teacher-owned (by class). Students see both as separate assessments. No conflict. |

---

## Compliance

Reads only `classes`, `class_students`, `students`, `published_content`, `student_submissions`. Writes only `published_content` (one new column). Zero touch to Clever / ClassLink / OneRoster / LTI surfaces. Standards codes are public curriculum identifiers (no PII). Accommodations helper preserves its existing FERPA contract — student name is NOT sent to the AI. The route emits structured log events but does NOT log accommodation contents.

## Sequencing

This spec maps to **one PR** with the following bundles (detailed in the implementation plan):

1. **Backend route + tests** — new route handler, validation, generation, accommodations integration, ~29 backend tests.
2. **Migration + visibility helper + publish hardening** — migration file, `_content_visible_to_student` helper, `publish_to_class` ownership + targeting, 5 student-facing route updates, +8 sibling tests.
3. **Frontend triggers + drawer** — `ProgressRankGrid.jsx` triggers, new `RemediationDrawer.jsx`, slim local editor, pre-publish validation. Build verification.

Total estimated scope: ~600 LOC backend (route + helper + hardening) + ~400 LOC frontend + ~700 LOC tests + 1 migration. ~3 implementation days.
