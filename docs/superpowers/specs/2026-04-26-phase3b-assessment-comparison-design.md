# Phase 3b — Assessment Comparison Design

**Status:** Approved by user 2026-04-26 (8-question design loop).

**Goal:** Class-scoped Assessment Comparison sub-tab in Analytics. Teacher picks 2-6 assessments via clickable chips → backend returns per-assessment distribution stats + class-wide standards-coverage matrix → frontend renders side-by-side box plots + a standards heatmap.

**Plan:** Plan B (Progress Tracking Roadmap), Phase 3b. Second half of the originally-bundled "Phase 3 — Assessment Comparison + Gradebook"; the Gradebook half (Phase 3a) shipped 2026-04-26 in PR #135.

---

## Architecture

A third sub-tab inside the existing Analytics tab, alongside Phase 2's "Progress Rank" and Phase 3a's "Gradebook". The class selector (introduced in Phase 2) gates the whole tab. The sub-tab switcher in `AnalyticsTab.jsx` already conditionally unmounts inactive sub-tabs (Phase 3a's pattern); this phase adds a `'compare'` value to the existing `classView` enum.

The comparison reuses the foundation from earlier phases without modification:
- Phase 1: `student_submissions.results` + `standards_mastery` rollup populated by all 3 grading paths.
- Phase 2: `_select_submissions_by_mode` for canonical-grade selection per attempt mode.
- Phase 2: `_aggregate_mastery_for_student` for per-standard mastery rollup.
- Phase 2b: `_sanitize_standards_mastery` for defensive normalization.
- Phase 3a: `_coalesce` for first-non-None fallback chains. Pagination via `.range()` for large submission sets.

No new shared helpers. The new route handler glues these together for a per-assessment aggregate (vs the per-(student, content) cell view of Gradebook).

---

## Backend — one new endpoint

### `GET /api/teacher/class/<class_id>/compare?content_ids=<csv>&attempt_mode=latest|best|average`

**Auth & authorization:**
- `@require_teacher` — 401 plain JSON for unauthenticated (pre-existing dashboard behavior).
- `@handle_route_errors` for the 500 path.
- Class-ownership check: `classes.teacher_id == g.teacher_id` or `error_response("Not authorized", 403)`.

**Inputs:**
- Path: `class_id` (UUID).
- Query: `content_ids` — comma-separated list of UUIDs. Required.
- Query: `attempt_mode` — `latest` (default), `best`, `average`. Invalid values silently fall back to `latest` (matches existing endpoints).

**Validation (in order):**
1. Class ownership → 403 via `error_response("Not authorized", 403)`.
2. Parse `content_ids` (split on comma, strip whitespace, filter empties). If list is empty → 400 via `error_response("content_ids is required", 400)`.
3. If `len(content_ids) < 2` → 400 via `error_response("Pick at least 2 assessments to compare", 400)`.
4. If `len(content_ids) > 6` → 400 via `error_response("Compare at most 6 assessments at once", 400)`.
5. Fetch `published_content` rows where `id IN content_ids AND class_id == <class_id>`. If the count returned is less than `len(content_ids)` → 403 via `error_response("Not authorized", 403)` (one or more `content_ids` is not in this class — prevents cross-class injection).

**Implementation:**
1. Resolve `class_name` from the class row (already fetched for ownership check).
2. Resolve `assessments` (the 5 `published_content` rows) — keep `(id, title, max_points)` for the response. `max_points` may be on the row or in the content JSON; pull from whichever is available, default 0.
3. Fetch class roster size (count of `class_students` for the class) → store as `class_roster_size` for the `submission_rate` computation. Skip orphan-student-row checks here (we only need a count; orphan-skip would require fetching students which is wasteful for this endpoint).
4. Paginate `student_submissions` for `content_id IN content_ids AND status != 'draft'` via `.range()` (matches Phase 3a). SELECT only `id, student_id, content_id, attempt_number, submitted_at, percentage, results, status` — `results` is needed because `standards_mastery` lives there.
5. Sanitize-in-place via `_sanitize_standards_mastery`.
6. Group submissions by `(student_id, content_id)` → `subs_by_student_content`.
7. For each `content_id`:
   - Collect submissions for this `content_id` across all students.
   - For each student, run `_select_submissions_by_mode({content_id: subs}, attempt_mode)` to pick the canonical submission(s).
   - Build a `percentages: list[float]` where each entry is the canonical percentage for that student.
     - For `attempt_mode='average'`: percentage = mean of attempt percentages for that student-content pair (using `_coalesce` for null safety).
     - For `latest`/`best`: percentage = the selected submission's `percentage`.
   - Compute distribution stats: `n` (length of percentages), `mean`, `median`, `q1`, `q3`, `min`, `max`.
   - `submission_rate` = `n / class_roster_size` (rounded to 2dp). 0.0 if `class_roster_size == 0`.
   - Build per-student aggregated `standards_mastery` for THIS content_id only by passing the selected submissions to `_aggregate_mastery_for_student({content_id: selected}, content_titles, attempt_mode)` and collecting the per-standard tallies.
8. Aggregate across all students per (content_id, standard_code):
   - `standards_matrix.standards`: sorted union of all standards across all picked assessments.
   - `standards_matrix.cells[content_id][standard_code]`: `{percentage: <class-mean across students who attempted>, students_assessed: <count>}`. Cells absent from the inner map = standard not covered by that assessment.
   - "Class-mean" = mean of per-student percentages on that standard, weighted equally per student. Use `_coalesce` to skip students with no contribution.

**Response shape:**

```json
{
  "class_id": "uuid",
  "class_name": "string",
  "attempt_mode": "latest",
  "class_roster_size": 25,
  "assessments": [
    {
      "content_id": "uuid",
      "title": "Quiz 1",
      "max_points": 30,
      "n": 22,
      "submission_rate": 0.88,
      "mean": 78.4,
      "median": 80.0,
      "min": 30,
      "max": 100,
      "q1": 65,
      "q3": 90,
      "percentages": [88, 92, 70, ...]
    }
  ],
  "standards_matrix": {
    "standards": ["MA.6.AR.1.1", "MA.6.AR.1.2", "..."],
    "cells": {
      "<content_id>": {
        "<standard_code>": {"percentage": 75.5, "students_assessed": 22}
      }
    }
  }
}
```

**Quartile computation:** use `statistics.quantiles(percentages, n=4, method='inclusive')` — Python 3.8+. For `n < 2` (single data point) the quartile call raises `StatisticsError`; guard with an explicit `if n < 2:` and return `q1 = q3 = mean`. For `n == 0` (no submissions on this content) the assessment row should still appear in `assessments` with `n: 0, mean/median/q1/q3/min/max: 0` and an empty `percentages` array — frontend renders an empty box-plot slot for that assessment.

**Empty-state handling:**
- Class has no enrolled students → `class_roster_size = 0`, all `submission_rate = 0.0`. Endpoint still returns 200.
- All picked assessments have zero submissions → `assessments[i].n = 0` for all; `standards_matrix.standards = []`. 200.
- Picked assessments touch 0 standards (untagged content) → `standards_matrix.standards = []`. 200.

**Pagination:** mirror Phase 3a's pattern. `.range(start, start + page_size - 1)` until a partial page returns. `page_size = 1000`.

---

## Frontend

### New component: `frontend/src/tabs/AssessmentComparison.jsx` (~280 LOC)

**Props:** `{ classId }`

**State:**
- `availableAssessments`: list fetched on mount (from a small bootstrap fetch — see "Bootstrap fetch" below).
- `selectedContentIds`: array of UUIDs, max length 6.
- `attemptMode`: `'latest'` (default) | `'best'` | `'average'`.
- `data`: comparison response, or null.
- `loading`: boolean.
- `error`: string or null.
- `searchQuery`: string for filtering the chips.

**Bootstrap fetch:**
The picker needs the list of assessments published to the class. Reuse the existing `getClassGradebook(classId, 'latest')` endpoint (Phase 3a) and read its `assessments` array — that already returns the right shape (`content_id`, `title`, `publish_date`). Caching: this fetch happens on mount and on `classId` change. Filter results client-side via `searchQuery`.

**Behavior:**
- On mount and when `classId` changes: fetch the available assessment list. Reset `selectedContentIds` and `data`.
- When `selectedContentIds.length < 2`: do NOT call the comparison endpoint. Show "Pick at least 2 assessments to compare" placeholder.
- When `selectedContentIds.length >= 2 && <= 6`: call `api.getClassAssessmentComparison(classId, selectedContentIds, attemptMode)` and render the comparison output.
- When `attemptMode` changes (with valid selection): re-fetch.
- Loading and error patterns mirror `Gradebook.jsx`.

**Sections:**

1. **Header**: class name + selection counter ("3 of 6 assessments selected").
2. **Controls row**: attempt mode buttons (Latest / Best / Average) — same component pattern as Gradebook.
3. **Picker**:
   - Search field at top: `<input>` filters the chip list by title (case-insensitive substring).
   - Chip list below: each chip is a clickable button with the assessment title. Selected chips have a highlighted style (primary-accent border + background tint); unselected chips have the muted glass-card border.
   - Selection cap: when 6 chips are selected, unselected chips become `disabled` (or visually muted with a "max 6" tooltip).
   - Empty state: "No assessments published to this class yet."
4. **Placeholder** when `selectedContentIds.length < 2`: "Pick at least 2 assessments to compare."
5. **Stats summary cards** (one per selected assessment, in selection order):
   - Title, N (e.g., "22 of 25"), submission rate (88%), mean %, median %, max points.
   - 3-tier color band on the card based on mean (≥85 green / 70-84 yellow / <70 red).
   - "No submissions yet" empty-state card if `n: 0`.
6. **Box-plot row**: a single horizontal SVG (custom — recharts doesn't have a native box plot). One box per assessment, colored to match its summary card. Y axis: 0-100%. Reference lines at 70 and 85 (matching Progress Rank thresholds). X axis: assessment titles (truncated if long; full title on hover).
7. **Standards heatmap**:
   - Rows: standards (alphabetical, the union from `standards_matrix.standards`).
   - Columns: assessments (in selection order, abbreviated titles).
   - Cell: 3-tier color when covered (`mastery percentage` from `standards_matrix.cells[content_id][standard_code].percentage`), muted gray dash when not covered.
   - Click a covered cell → tooltip with `students_assessed: N` and the precise mastery %.
   - Empty state when `standards_matrix.standards` is empty: "No standards-tagged questions on these assessments."

### API client — `frontend/src/services/api.js`

Add next to `getClassGradebook` (Phase 3a):

```javascript
export async function getClassAssessmentComparison(classId, contentIds, attemptMode) {
  var mode = attemptMode || 'latest';
  var params = new URLSearchParams({
    content_ids: contentIds.join(','),
    attempt_mode: mode,
  });
  return fetchApi(
    '/api/teacher/class/' + encodeURIComponent(classId) +
    '/compare?' + params.toString()
  );
}
```

`contentIds.join(',')` produces the comma-separated string the backend parses. `URLSearchParams` URL-encodes the result.

### Wire-up — `AnalyticsTab.jsx`

- Import: add `import AssessmentComparison from "./AssessmentComparison";` next to the existing `Gradebook` import.
- Update the `classView` enum: `'progressRank' | 'gradebook' | 'compare'`.
- Add a third button to the sub-tab switcher (after the Gradebook button), styled identically.
- The conditional render becomes a 3-way:
  ```javascript
  {classView === 'progressRank' ? (
    <ProgressRankGrid classId={selectedClassForGrid} />
  ) : classView === 'gradebook' ? (
    <Gradebook classId={selectedClassForGrid} />
  ) : (
    <AssessmentComparison classId={selectedClassForGrid} />
  )}
  ```
- Class-selector `onChange` already resets `classView` to `'progressRank'` (Phase 3a pattern); no change needed.

---

## Error handling

| Failure mode | HTTP | Body shape | UX |
|---|---|---|---|
| Unauthenticated | 401 | Plain JSON via `require_teacher` | Login redirect |
| Class not owned | 403 | RFC 7807 via `error_response` | Sub-tab shows error |
| Missing `content_ids` query param | 400 | RFC 7807 via `error_response("content_ids is required", 400)` | Frontend never fetches without ≥2 selected, so this only fires on direct API access; sub-tab shows error |
| Fewer than 2 `content_ids` | 400 | RFC 7807 | Frontend gates the call; this is a defense-in-depth |
| More than 6 `content_ids` | 400 | RFC 7807 | Frontend caps client-side; defense-in-depth |
| `content_id` outside the class | 403 | RFC 7807 (`Not authorized`) | Sub-tab shows error |
| Empty class / zero submissions | 200 + zero-stat assessments | Standard JSON | Cards show "no submissions yet"; box plot shows empty slot; heatmap rows = 0 |
| Malformed `standards_mastery` for a submission | 200 + sanitize-in-place + WARNING log | Standard JSON | Affected submission's mastery contribution dropped silently; rest renders normally |
| Backend exception | 500 RFC 7807 via `@handle_route_errors` | RFC 7807 | Sub-tab shows generic error; teacher retries |

---

## Testing

### Backend — `tests/test_assessment_comparison.py` (~12 tests)

- `test_unauthenticated_returns_401`.
- `test_other_teacher_class_returns_403`.
- `test_missing_content_ids_returns_400`.
- `test_one_content_id_returns_400` — "pick at least 2".
- `test_seven_content_ids_returns_400` — "compare at most 6".
- `test_content_id_outside_class_returns_403` — defends against cross-class injection.
- `test_invalid_attempt_mode_falls_back_to_latest`.
- `test_happy_path_two_assessments_returns_full_response` — verify all top-level fields, assessments array shape, `submission_rate`, quartiles.
- `test_happy_path_six_assessments_returns_full_response` — verify max-allowed selection works.
- `test_attempt_mode_average_uses_mean_percentage` — multiple attempts per student × content; verify `percentages[i]` is the mean across attempts.
- `test_assessment_with_zero_submissions_returns_zero_stats` — picked assessment has no submissions; `n: 0, mean/median/q1/q3: 0, percentages: []`.
- `test_standards_matrix_union_and_cells_correct` — pick 2 assessments where one covers `[A, B]` and the other covers `[B, C]`; verify `standards: [A, B, C]` (sorted) and `cells` populated correctly with `students_assessed` counts.
- `test_malformed_standards_mastery_does_not_500` — one submission has list-shape mastery; endpoint returns 200 with the submission's distribution data still populated and that mastery contribution dropped.

### Frontend
Build verification only (matches Phase 2 / 2b / 3a pattern).

### Manual smoke test
1. Pick a class with 3+ assessments and submissions.
2. Switch to Compare sub-tab. Picker shows all assessments as chips.
3. Click 2 chips → comparison renders (cards + box plot + heatmap).
4. Click a 3rd chip → comparison re-fetches and re-renders.
5. Toggle attempt mode (Latest / Best / Average) — distributions update.
6. Try to pick a 7th chip — UI prevents (visually muted; no fetch).
7. Click an already-selected chip → deselect; comparison re-fetches.
8. Drop below 2 → comparison area clears; "pick 2+" message returns.
9. Search field filters chip list correctly.
10. Hover a heatmap cell → tooltip shows precise mastery % + students_assessed.
11. Switch sub-tab to Gradebook → AssessmentComparison unmounts; switch back → reset state (acceptable for MVP; saved-view persistence is Phase 3b.5).

---

## Out of scope (deferred)

- **Phase 3b.2** — Cross-class comparison (same assessment across class periods).
- **Phase 3b.3** — Per-question-type breakdown (MC vs FITB vs written), DOK distribution, time-on-task per assessment.
- **Phase 3b.4** — Statistical significance tests, paired-test indicators, trend lines.
- **Phase 3b.5** — Saved view preferences (server-persisted picker state per teacher).
- **Phase 3b.6** — Export comparison to PDF / CSV.
- **Phase 3b.7** — Drill-down from a heatmap cell into per-question detail (currently the cell tooltip is the deepest view).
- Real-time updates (sub-tab re-fetches on mount; no polling).

---

## Compliance

- **Data sources:** Reads only from `classes`, `class_students`, `students`, `published_content`, `student_submissions`. No SSO, no roster sync, no Clever / ClassLink / OneRoster contracts touched. The 199 SIS contract tests untouched.
- **PII:** Per-assessment aggregates do not include student names — only counts. The picker shows assessment titles only. No new PII surface.
- **Auth model:** Class ownership is checked before any data fetch. The cross-class injection guard ensures a teacher can't compare an assessment they don't own by passing its `content_id` in a class they DO own.

---

## Files touched

**Created:**
- `frontend/src/tabs/AssessmentComparison.jsx` — sub-tab component (~280 LOC).
- `tests/test_assessment_comparison.py` — 12 backend test cases.

**Modified:**
- `backend/routes/student_portal_routes.py` — add `get_class_assessment_comparison` route handler. No new helpers.
- `frontend/src/tabs/AnalyticsTab.jsx` — add `AssessmentComparison` import, third sub-tab button, 3-way conditional render. No state-shape change beyond the `classView` enum gaining `'compare'`.
- `frontend/src/services/api.js` — add `getClassAssessmentComparison` client.

**Not touched:**
- Existing helpers (`_select_submissions_by_mode`, `_aggregate_mastery_for_student`, `_sanitize_standards_mastery`, `_coalesce`, `_parse_ts`, `_build_*` from Phase 2b) — used as-is.
- Any SIS / SSO / roster file.
- `mypy.ini` / `.github/workflows/ci.yml` / `setup.cfg` / `requirements*.{in,txt}`.
- `backend/services/grading_service.py` — read-only research; no changes.
