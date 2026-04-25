# Phase 3a — Gradebook Design

**Status:** Approved by user 2026-04-25 (deferred-to-AI sign-off after 9-question design loop).

**Goal:** A class-scoped gradebook sub-tab that lets teachers see every student's canonical grade for every assessment in the class, click any cell to drill into per-question detail + AI feedback + attempt history.

**Plan:** Plan B (Progress Tracking Roadmap), Phase 3a. First half of the originally-bundled "Phase 3 — Assessment Comparison + Gradebook"; the Comparison view is Phase 3b (separate spec/plan/PR).

---

## Architecture

A second sub-tab inside the existing Analytics tab, alongside the Phase 2 "Progress Rank" sub-tab. Both views share the same class selector (introduced in Phase 2). Each sub-tab owns its own local `attemptMode` state (matching Phase 2's pattern). The gradebook reuses the foundation from Phase 1 (`student_submissions.results`), Phase 2 (`_select_submissions_by_mode` only — NOT the mastery-specific `_aggregate_mastery_for_student`), and Phase 2b (`_sanitize_standards_mastery`) without modification. Phase 2b's bridge helpers (`_build_standards_breakdown_for_student`, `_build_trajectory_for_student`) are NOT used — gradebook is per-cell-percentage, not mastery-or-trajectory.

The gradebook is read-only. Manual grade overrides, re-grade buttons, and grade-passback wiring are explicitly Phase 3a.2 territory; this spec ships the view-and-drill experience first.

---

## Backend — two new endpoints

### `GET /api/teacher/class/<class_id>/gradebook?attempt_mode=latest|best|average`

**Auth & authorization:**
- `@require_teacher` (existing decorator). 401 plain JSON for unauthenticated, matching dashboard convention.
- `@handle_route_errors` for the 500 path (catches uncaught exceptions, returns RFC 7807 envelope).
- Class-ownership check: `classes.teacher_id == g.teacher_id` or return `error_response("Not authorized", 403)`.

**Query parameter:**
- `attempt_mode`: one of `latest` (default), `best`, `average`. Invalid values silently fall back to `latest`, matching the Phase 2 grid endpoint.

**Implementation:**
- Add the route handler to `backend/routes/student_portal_routes.py` (after `get_student_report_card`).
- Reuses `_select_submissions_by_mode` (line 111) and `_sanitize_standards_mastery` (module-level after Phase 2b's extraction). Does NOT use `_aggregate_mastery_for_student` or any of Phase 2b's bridge helpers — gradebook is per-cell-percentage only, no mastery rollup.
- Fetch path:
  1. Verify class ownership via `error_response`-based 403.
  2. Fetch class roster: `class_students` rows + `students` rows. **Orphan-enrollment handling:** if a `class_students.student_id` has no matching `students` row, skip the student silently (matches Phase 2's grid behavior at `student_portal_routes.py:1231`). Log a debug-level message; do NOT 500. Sort surviving students alphabetically by full name (`(first_name + ' ' + last_name).strip()`).
  3. Fetch all `published_content` for the class with `content_type IN ('assessment', 'assignment')`. Sort assessments ASC by `publish_date` (oldest-first; left-to-right scanning matches term progression). Tie-break by `id` for stability.
  4. Fetch all non-draft `student_submissions` for those contents. Sanitize-in-place via `_sanitize_standards_mastery` (defensive — gradebook doesn't render mastery directly but uses the same submission rows that other endpoints do).
  5. Group submissions by `(student_id, content_id)` into `subs_by_student_content`.
  6. For each `(student_id, content_id)` pair, run `_select_submissions_by_mode({content_id: subs}, attempt_mode)`. The helper returns:
     - For `latest` / `best`: a list with one selected submission. The cell's `percentage` is that submission's `percentage`, and `submission_id` / `attempt_number` / `submitted_at` come from it.
     - For `average`: a list of ALL submissions (no selection). The cell's `percentage` is the mean of `[s['percentage'] for s in subs]` rounded to 1 decimal. For drilldown anchoring, pick the LATEST attempt as `submission_id` / `attempt_number` / `submitted_at` (so clicking an averaged cell opens the most-recent attempt's detail). Document this in the response shape's `attempt_mode=average` note.
  7. `total_attempts` is `len(subs_by_student_content[student_id][content_id])` regardless of attempt_mode.
  8. Build the `grades` map only for pairs where at least one submission exists. Missing pairs are absent from the map (frontend renders `—`).

**Response shape:**

```json
{
  "class_id": "uuid",
  "class_name": "string",
  "attempt_mode": "latest",
  "students": [
    {"student_id": "uuid", "student_name": "Lastname, Firstname or 'Firstname Lastname'"}
  ],
  "assessments": [
    {
      "content_id": "uuid",
      "title": "Quiz 3 — Equations",
      "content_type": "assessment",
      "publish_date": "ISO-8601 or null",
      "due_date": "ISO-8601 or null"
    }
  ],
  "grades": {
    "<student_id>": {
      "<content_id>": {
        "submission_id": "uuid",
        "percentage": 87,
        "attempt_number": 2,
        "total_attempts": 3,
        "submitted_at": "ISO-8601"
      }
    }
  }
}
```

Match the existing Phase 2b convention for `student_name` formatting (currently `(first_name + ' ' + last_name).strip()` — "Firstname Lastname"). Do not invent a new format.

**Empty-state handling:**
- Class has no enrolled students → `"students": []`, empty grades map, 200.
- Class has students but no published content → `"assessments": []`, empty grades map, 200.
- Class has both but no submissions yet → both lists populated, `"grades": {}`, 200.

**Malformed `standards_mastery` defensive note:**
The gradebook endpoint doesn't render `standards_mastery` directly, but it fetches the same submission rows that other endpoints rely on. Calling `_sanitize_standards_mastery` once before any aggregation step prevents an in-flight bug from elsewhere (e.g., a buggy grader writing a non-dict value) from 500-ing the endpoint.

### `GET /api/teacher/submission/<submission_id>/detail`

**Auth & authorization:**
- `@require_teacher` + `@handle_route_errors`.
- Ownership chain check: load the submission → its `content_id` → `published_content.class_id` → `classes.teacher_id`. If any link is missing OR the final `teacher_id` mismatches `g.teacher_id`, return `error_response("Not authorized", 403)`.
- If the submission row itself doesn't exist, return `error_response("Submission not found", 404)`.

**Implementation:**
- Add the route handler to `backend/routes/student_portal_routes.py` (after `get_class_gradebook`).
- Fetch path:
  1. Look up the submission by id (`student_submissions.select('*').eq('id', submission_id)`).
  2. If missing, return `error_response("Submission not found", 404)`.
  3. Look up the `published_content` row to get `title` and `class_id`. If the content row is missing (e.g., deleted after submission), return `error_response("Submission's content no longer exists", 404)` — distinct from the ownership 403 to avoid leaking whether a deleted content was OWNED by the requester.
  4. Verify class ownership: `classes.teacher_id == g.teacher_id`. If mismatched, return `error_response("Not authorized", 403)`.
  5. Look up the student row for the `student_name`. If missing (orphan), 404 with `error_response("Student not found", 404)` — same pattern as Phase 2b.
  6. Fetch all sibling submissions (`.eq('student_id', sub.student_id).eq('content_id', sub.content_id)`) for the attempt selector. Sort ASC by `attempt_number`, then by `submitted_at`.
  7. Read `results.questions` for the per-question breakdown. Field-name normalization (the existing graders write inconsistent keys — verified during spec authoring; rules below).

**Top-level score field mapping:**
The existing graders write `score` and `total_points` (NOT `points_earned` and `points_possible`) at the top level of `results`. There is also a `score` column on the `student_submissions` row itself. Normalize:
- `points_earned = results.get('score') or row.get('score') or 0`
- `points_possible = results.get('total_points') or row.get('total_points') or 0`
- `percentage = row.percentage` (already populated by graders)

**Per-question field normalization:**
The instant grader and multipass grader write different keys. Apply these fallback rules per question entry (where each `q` is the entry from `results.questions[i]`):
- `question_text = q.get('question') or q.get('question_text') or ''`
- `question_type = q.get('type') or q.get('question_type') or 'unknown'`
- `student_answer = q.get('student_answer') or q.get('answer') or ''`
- `correct_answer = q.get('correct_answer')` — may be `None` (e.g., free-response). Pass through.
- `is_correct = q.get('is_correct')` — may be `None` for written/free-response. Pass through.
- `ai_feedback = q.get('feedback') or q.get('reasoning') or q.get('quality') or ''`
- `points_earned = q.get('points_earned') or q.get('score') or 0`
- `points_possible = q.get('points_possible') or q.get('points') or 0`
- If a question entry is non-dict, skip it and log a WARNING (do NOT 500).

If `results.questions` itself is missing or non-list, return `questions: []` — do NOT 500. Log a WARNING.

**Response shape:**

```json
{
  "submission_id": "uuid",
  "student_id": "uuid",
  "student_name": "Firstname Lastname",
  "content_id": "uuid",
  "content_title": "Quiz 3 — Equations",
  "attempt_number": 2,
  "total_attempts": 3,
  "submitted_at": "ISO-8601",
  "percentage": 87,
  "points_earned": 26,
  "points_possible": 30,
  "questions": [
    {
      "question_text": "What is 2+2?",
      "question_type": "multiple_choice",
      "student_answer": "4",
      "correct_answer": "4",
      "is_correct": true,
      "ai_feedback": "...",
      "points_earned": 5,
      "points_possible": 5
    }
  ],
  "sibling_attempts": [
    {
      "submission_id": "uuid",
      "attempt_number": 1,
      "submitted_at": "ISO-8601",
      "percentage": 70
    }
  ]
}
```

`sibling_attempts` includes the current submission so the frontend's attempt selector can render the active attempt highlighted. Don't filter it out client-side; let the frontend match by `submission_id` to highlight.

**Field semantics:**

| Field | Notes |
|---|---|
| `attempt_number` | From the submission row. |
| `total_attempts` | `len(sibling_attempts)`. |
| `questions[i].question_text` | From `results.questions[i].question` (or `results.questions[i].question_text` — match what the existing grader writes; verify by reading `assignment_grader.py` before implementing). |
| `questions[i].student_answer` | From `results.questions[i].student_answer` (or equivalent). |
| `questions[i].correct_answer` | Optional — only present for question types where it's known (multiple_choice, fitb). May be `null` for free-response. |
| `questions[i].is_correct` | Optional — present for auto-graded types. |
| `questions[i].ai_feedback` | From `results.questions[i].feedback` (or whatever key the grader writes). Verify before implementation. |
| `points_earned` / `points_possible` | Per-question. From `results.questions[i]`. |

The exact key names in `results.questions[i]` need to be verified during Task 1 implementation by reading `assignment_grader.py` and `backend/routes/student_portal_routes.py::grade_instant_only` (the join-code grading path) and `backend/grading/pipeline.py` (the class-based grading path). The implementation must adapt to whatever the existing grader writes — no schema migration.

---

## Frontend

### New components

**`frontend/src/tabs/Gradebook.jsx`** (~220 LOC, mirrors `ProgressRankGrid.jsx` patterns)

**Props:** `{ classId }`

**Behavior:**
- On mount and when `classId` changes, fetch via `api.getClassGradebook(classId, attemptMode)`.
- Local state: `data`, `loading`, `error`, `attemptMode` (default `'latest'`), `missingOnly` (boolean), `selectedSubmissionId` (or `null`).
- Loading and error patterns mirror `ProgressRankGrid.jsx`.

**Sections:**
1. Header: class name + counts ("X students × Y assessments").
2. Controls row: attempt mode buttons (Latest / Best / Average) + "Missing only" toggle.
3. Table:
   - Sticky student-name column (left).
   - Sticky assessment-header row (top), showing assessment title + small subtitle (publish date or `—`).
   - Cells: percentage with 3-tier color (`>= 85` green / `>= 70` yellow / `< 70` red), or `—` muted gray for absent grades.
   - Click cell → if a `submission_id` exists, set `selectedSubmissionId` (opens drawer).
   - Empty cells (missing grades) are NOT clickable; cursor is default.
4. Empty states:
   - `students.length === 0`: "No students enrolled in this class yet."
   - `assessments.length === 0`: "No assessments published to this class yet."
   - `missingOnly` filter eliminates everyone: "All students have submitted everything. ✓"

**Filter logic:**
`missingOnly = true` shows only students who have at least one assessment with no grade (i.e., the `grades[student_id][content_id]` is missing for at least one `content_id`).

**Drawer render:**
```javascript
{selectedSubmissionId && (
  <SubmissionDetail
    submissionId={selectedSubmissionId}
    onClose={function() { setSelectedSubmissionId(null); }}
  />
)}
```

---

**`frontend/src/tabs/SubmissionDetail.jsx`** (~250 LOC, mirrors `StudentReportCard.jsx`'s overlay pattern)

**Props:** `{ submissionId, onClose }` — `submissionId` is the INITIAL submission to display; the attempt selector mutates LOCAL state, not the prop.

**Behavior:**
- Local state: `activeSubmissionId` initialized from prop on mount, then updated by the attempt selector. `data`, `loading`, `error`, `expandedQuestionIndex` (or `null`).
- On mount and when `activeSubmissionId` changes, fetch via `api.getSubmissionDetail(activeSubmissionId)`.
- The parent (`Gradebook.jsx`) does NOT re-render the drawer when the user picks a different attempt — only the drawer's internal `activeSubmissionId` changes, triggering a re-fetch within the same drawer instance. This keeps the drawer mounted (no flicker) and preserves `expandedQuestionIndex`.
- z-index `9500`, same as `StudentReportCard.jsx`. The two drawers can't be open simultaneously because the parent sub-tab switcher (`Progress Rank` ↔ `Gradebook`) **conditionally unmounts the inactive sub-tab's component tree**, dropping any open drawer with it. Document this in the wire-up section's switcher implementation.
- Esc key closes the drawer (same `useEffect` pattern as `StudentReportCard.jsx`).
- Click backdrop or `×` closes; click drawer panel calls `e.stopPropagation()`.

**Sections:**
1. Header: student name + assessment title + score line ("87% — 26 of 30 pts — attempt 2 of 3 — submitted MM/DD").
2. Attempt selector: row of small buttons, one per `sibling_attempts` entry. Click → updates `submissionId` to that attempt's id (re-fetches). Active attempt highlighted.
3. Per-question accordion:
   - Each row collapsed by default. Shows question text + per-question score badge (color-coded same as gradebook cells).
   - Click row to expand. Expanded view shows: student answer, correct answer (if present), `is_correct` icon (if present), AI feedback.
   - Empty `questions` array → "Per-question detail not available for this submission."
4. Footer note: "Read-only view. Manual grade overrides will arrive in a future phase."

**Attempt selector implementation:**
```javascript
function pickAttempt(submId) { setActiveSubmissionId(submId); }
// In the selector row:
{data.sibling_attempts.map(function(a) {
  var isActive = a.submission_id === activeSubmissionId;
  return (
    <button key={a.submission_id} onClick={function() { pickAttempt(a.submission_id); }}
            disabled={isActive} ...>
      Attempt {a.attempt_number} ({a.percentage}%)
    </button>
  );
})}
```

### Wire-up — `AnalyticsTab.jsx`

- Add a sub-tab switcher above the existing class-scoped content. State: `var [classView, setClassView] = useState('progressRank');` with values `'progressRank' | 'gradebook'`.
- When `selectedClassForGrid !== 'all'`, render the sub-tab switcher (two buttons: "Progress Rank" / "Gradebook") plus **only the active sub-tab's component** (conditional render with `{classView === 'progressRank' ? <ProgressRankGrid ...> : <Gradebook ...>}`). The inactive sub-tab is unmounted, which guarantees its drawer (`StudentReportCard` for Progress Rank, `SubmissionDetail` for Gradebook) cannot remain open across sub-tab switches.
- Default sub-tab: `'progressRank'` (preserves existing behavior).
- When `selectedClassForGrid === 'all'`, hide the sub-tab switcher entirely (only the existing all-classes analytics renders, no class-scoped views).
- Switching between sub-tabs preserves `selectedClassForGrid` (no re-fetch on class data unless class changes), but DOES unmount the inactive component (each sub-tab re-fetches on mount when re-selected — minor cost, simpler architecture).
- **Attempt mode toggle scope:** each sub-tab owns its OWN `attemptMode` state (Phase 2's `ProgressRankGrid` already does; the new `Gradebook` will too). They're not shared. Lifting state to `AnalyticsTab` is rejected because: (a) Phase 2 already shipped with local state, (b) sharing would force re-fetch of both sub-tabs on every toggle, (c) teachers may want different modes per view (e.g., latest in gradebook for grading-now, best in progress-rank for full-class-trend).

### API client — `frontend/src/services/api.js`

Add next to `getStudentReportCard`:

```javascript
export async function getClassGradebook(classId, attemptMode) {
  var mode = attemptMode || 'latest';
  var params = new URLSearchParams({ attempt_mode: mode });
  return fetchApi(
    '/api/teacher/class/' + encodeURIComponent(classId) +
    '/gradebook?' + params.toString()
  );
}

export async function getSubmissionDetail(submissionId) {
  return fetchApi('/api/teacher/submission/' + encodeURIComponent(submissionId) + '/detail');
}
```

---

## Error handling

| Failure mode | HTTP | Body shape | UX |
|---|---|---|---|
| Unauthenticated request | 401 | Plain `{"error": "Authentication required"}` | Frontend redirects to login (existing fetchApi behavior) |
| Class not owned (gradebook) | 403 | RFC 7807 via `error_response("Not authorized", 403)` | Gradebook shows error message |
| Submission not found | 404 | RFC 7807 via `error_response("Submission not found", 404)` | Drawer shows error message |
| Submission's content row deleted | 404 | RFC 7807 via `error_response("Submission's content no longer exists", 404)` | Drawer shows error message |
| Submission's student row missing (orphan) | 404 | RFC 7807 via `error_response("Student not found", 404)` | Drawer shows error message |
| Submission's class not owned | 403 | RFC 7807 via `error_response("Not authorized", 403)` | Drawer shows error message |
| Class roster orphan enrollment (in gradebook listing) | Skipped silently | (No response change) | Affected student row absent from gradebook; debug-level log |
| Empty class / no assessments / no submissions | 200 + empty arrays | Standard JSON | Gradebook shows empty-state message |
| Malformed `results.questions` for a submission | 200 with `questions: []` + WARNING log | Standard JSON | Drawer shows "Per-question detail not available" message |
| Backend exception | 500 with RFC 7807 envelope via `@handle_route_errors` | RFC 7807 | Gradebook/drawer shows generic error; teacher can retry by reopening |

The 401 from `require_teacher` is plain JSON; pre-existing dashboard behavior, NOT in scope to fix here.

---

## Testing

### Backend

**New file:** `tests/test_gradebook.py`
- `test_unauthenticated_returns_401` — no teacher session.
- `test_other_teacher_class_returns_403` — class belongs to different teacher; verify RFC 7807 fields.
- `test_empty_class_returns_empty_arrays` — no enrolled students.
- `test_class_with_no_assessments_returns_empty_assessments` — students enrolled, no published content.
- `test_class_with_no_submissions_returns_empty_grades` — content + students, but no submissions.
- `test_happy_path_returns_full_grid` — 2 students × 2 assessments × multiple attempts; verify `total_attempts`, ordering, sticky sort.
- `test_attempt_mode_latest_picks_most_recent_per_pair` — ensure each (student, content) cell uses the latest attempt under `attempt_mode=latest`.
- `test_attempt_mode_best_picks_highest_per_pair` — same setup, `attempt_mode=best`.
- `test_attempt_mode_average_aggregates` — same setup, `attempt_mode=average`. Verify the cell percentage is the mean of attempt percentages.
- `test_invalid_attempt_mode_falls_back_to_latest` — pass `attempt_mode=garbage`; verify it doesn't 400.
- `test_missing_pair_absent_from_grades_map` — student has submitted some assessments but not all; verify the absent pairs are NOT in the map (not `null`, not present at all).
- `test_malformed_standards_mastery_does_not_500` — one submission has list-shape mastery; gradebook returns 200 with the submission's grade still populated. (Sanitize-in-place runs.)
- `test_assessments_sorted_by_publish_date_asc` — verify oldest-first column order.

**New file:** `tests/test_submission_detail.py`
- `test_unauthenticated_returns_401`.
- `test_submission_not_found_returns_404`.
- `test_other_teacher_submission_returns_403` — submission's class is owned by a different teacher.
- `test_happy_path_returns_questions_and_siblings` — multi-attempt setup; verify `questions[]`, `sibling_attempts[]`, `total_attempts`, ordering.
- `test_no_sibling_attempts_returns_only_self` — single-attempt case.
- `test_malformed_results_questions_returns_empty_array_with_200` — `results.questions` is missing or non-list; endpoint 200s with `questions: []` and a WARNING is logged.
- `test_questions_field_normalization_handles_both_grader_paths` — fixture rows from join-code grader AND class-based grader; verify field extraction works for both shapes (this test is a research safeguard during Task 1 — the implementer must verify the actual grader output keys before writing it).

### Frontend
- Build verification only (consistent with Phase 2 / 2b — no unit tests, drawer behavior is covered by manual smoke).

### Manual smoke test
1. Pick a class with at least one assessment + multiple students with multiple attempts.
2. Switch to Gradebook sub-tab.
3. Toggle attempt mode (Latest / Best / Average) — cells update.
4. Click a cell → drawer opens, shows correct submission's per-question detail.
5. Switch attempts in the drawer — content updates.
6. Esc + backdrop + × all close the drawer.
7. Toggle "Missing only" filter — only students with at least one missing assessment remain visible.
8. Switch back to Progress Rank sub-tab — class context preserved.

---

## Out of scope (deferred)

- **Phase 3a.2** — Manual grade override field, re-grade button, audit log for grade changes, grade-passback to LMS via OneRoster / LTI AGS.
- **Phase 3a.3** — Per-assessment or per-cell attempt mode override (vs class-level only).
- **Phase 3a.4** — Click column header to sort by that assessment's grades.
- **Phase 3a.5** — Saved view preferences (server-persisted filter/sort per teacher).
- **Phase 3b** — Assessment Comparison view (separate spec/plan/PR).
- Bulk operations ("grade all 0 for missing", "send reminder").
- Export gradebook to CSV.
- Real-time updates (drawer + table fetch once on open / class-change).

---

## Compliance

- **Data sources:** Reads only from `classes`, `class_students`, `students`, `published_content`, `student_submissions`. No SSO, no roster sync, no Clever / ClassLink / OneRoster contracts touched. The 199 SIS contract tests untouched.
- **PII:** Student names are already exposed in Phase 2's grid endpoint; no new PII surface. Per-question student answers are read-only and visible only to the owning teacher (auth chain enforces this).
- **Auth model:** Both endpoints check `classes.teacher_id == g.teacher_id` (gradebook directly; submission-detail via the ownership chain `submission → content → class`).

---

## Files touched

**Created:**
- `frontend/src/tabs/Gradebook.jsx` — gradebook table component (~220 LOC).
- `frontend/src/tabs/SubmissionDetail.jsx` — submission-detail drawer (~250 LOC).
- `tests/test_gradebook.py` — 13 backend test cases.
- `tests/test_submission_detail.py` — 7 backend test cases.

**Modified:**
- `backend/routes/student_portal_routes.py` — add `get_class_gradebook` + `get_student_submission_detail` route handlers.
- `frontend/src/tabs/AnalyticsTab.jsx` — add sub-tab switcher (Progress Rank / Gradebook) inside the class-scoped section.
- `frontend/src/services/api.js` — add `getClassGradebook` + `getSubmissionDetail` clients.

**Not touched:**
- Any helper unrelated to the new routes. Reused: `_select_submissions_by_mode`, `_sanitize_standards_mastery`. NOT used: `_aggregate_mastery_for_student`, `_build_standards_breakdown_for_student`, `_build_trajectory_for_student` — those are mastery-specific and not relevant to per-cell percentage display.
- Any SIS / SSO / roster file.
- `mypy.ini` / `.github/workflows/ci.yml` / `setup.cfg` / `requirements*.{in,txt}`.
- `backend/services/grading_service.py` — verified read-only during research; no changes.
