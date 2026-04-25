# Phase 2b — Student Report Card Design

**Status:** Approved 2026-04-25.

**Goal:** Add a per-student drill-down view, opened from the Progress Rank grid (Phase 2). Teachers click a student's row in the grid → a side drawer slides in showing that student's mastery trajectory and per-standard breakdown for the class.

**Plan:** Plan B (Progress Tracking Roadmap), Phase 2b. Builds on Phase 1's `student_submissions.results.standards_mastery` rollup and Phase 2's `_select_submissions_by_mode` / `_aggregate_mastery_for_student` helpers — both already on `main`.

---

## Architecture

A class-scoped per-student view. Reuses the same `standards_mastery` foundation Phase 1 shipped; no new data model, no new tables, no migration. The view is opened from the existing `ProgressRankGrid.jsx` component (Phase 2) — the only behavior change there is making the student-name cell clickable.

The card is **class-scoped**: it shows mastery within ONE class context, not the student's full cross-class history. Cross-class is a future phase.

---

## Backend

### New endpoint

```
GET /api/teacher/class/<class_id>/student/<student_id>/report-card
    ?attempt_mode=latest|best|average
```

**Auth & authorization:**
- `@require_teacher` (existing decorator)
- `@handle_route_errors` for RFC 7807 envelope (Phase 5d PR 1)
- Class-ownership check (mirror of `student_portal_routes.py:1221-1223`): the class's `teacher_id` must equal `g.teacher_id` or return 403.
- Student-in-class check: the student must be enrolled in the class via `class_students`. If not, return 404.

**Query parameter:**
- `attempt_mode`: one of `latest` (default), `best`, `average`. Invalid values silently fall back to `latest`, matching the grid endpoint's behavior at `student_portal_routes.py:1216-1218`.

**Implementation:**
- Add the route handler to `backend/routes/student_portal_routes.py` (next to `get_class_progress_rank`).
- Reuse `_select_submissions_by_mode` (line 111) and `_aggregate_mastery_for_student` (line 145) — both helpers already exist and are exactly what we need.
- Fetch path:
  1. Verify class ownership.
  2. Verify student is in class via `class_students` lookup.
  3. Fetch student name from `students` (id, first_name, last_name).
  4. Fetch all `published_content` for this class with `content_type IN ('assessment', 'assignment')`.
  5. Fetch all non-draft `student_submissions` for this student where `content_id` is in the class content set.
  6. Build the trajectory by listing every submission chronologically.
  7. Build the per-standard breakdown using the existing helpers, then sort worst-first by percentage.

**Response shape:**

```json
{
  "student_id": "uuid",
  "student_name": "Lastname, Firstname",
  "class_id": "uuid",
  "class_name": "string",
  "attempt_mode": "latest",
  "trajectory": [
    {
      "submission_id": "uuid",
      "content_id": "uuid",
      "title": "Quiz 3 — Equations",
      "submitted_at": "2026-04-12T15:30:00Z",
      "percentage": 87,
      "attempt_number": 1,
      "points_earned": 26,
      "points_possible": 30
    }
  ],
  "standards_breakdown": [
    {
      "code": "MA.6.AR.1.1",
      "percentage": 65,
      "points_earned": 13,
      "points_possible": 20,
      "question_count": 4,
      "contributing_submissions": [
        {
          "submission_id": "uuid",
          "title": "Quiz 3 — Equations",
          "submitted_at": "2026-04-12T15:30:00Z",
          "attempt_number": 1,
          "points_earned": 7,
          "points_possible": 10,
          "percentage": 70
        }
      ]
    }
  ]
}
```

**Field semantics:**

| Field | Notes |
|---|---|
| `trajectory` | All non-draft submissions for this student in this class, ordered ASC by `submitted_at` (oldest first). **Mode-agnostic** — every attempt is shown so the teacher sees the trend. |
| `standards_breakdown` | **Only attempted standards**, sorted **ASC by percentage** (worst-first). Aggregates respect `attempt_mode`. Uses the same per-standard rollup the grid uses. |
| `contributing_submissions` | Per-standard sublist showing which submissions contributed to that standard's mastery. Mirrors the cell-popover data on the grid. |

**Empty-state handling:** if the student has zero non-draft submissions in this class, return 200 with `trajectory: []` and `standards_breakdown: []`. The frontend renders an empty-state message; the request itself is not an error.

---

## Frontend

### New component

**File:** `frontend/src/tabs/StudentReportCard.jsx` (target ~200 LOC, mirroring `ProgressRankGrid.jsx`).

**Props:**
```
{ classId: string, studentId: string, attemptMode: string, onClose: () => void }
```

**Behavior:**
- On mount and when `studentId`/`attemptMode` changes, fetch via `api.getStudentReportCard(classId, studentId, attemptMode)`.
- Loading and error states match `ProgressRankGrid.jsx` patterns (spinner; red text on error).
- Renders as a fixed side drawer:
  - Position: `right: 0`, full height, `width: 600px` (clamps to viewport on narrow screens).
  - Background: `var(--card-bg)` with left border + shadow.
  - Click outside drawer → close. Click inside → `e.stopPropagation()`.
  - `×` button in the header.

**Sections inside the drawer:**

1. **Header** — student name, class name, attempt mode label.
2. **Trajectory chart** — recharts `<LineChart>` with:
   - X-axis: `submitted_at` formatted MM/DD.
   - Y-axis: percentage 0-100.
   - Two horizontal reference lines: 70 (yellow) and 85 (green) — matching the grid's mastery thresholds.
   - Tooltip on hover shows submission title + percentage + attempt number + date.
3. **Standards breakdown** — list of rows, one per attempted standard, sorted worst-first:
   - Standard code (monospace).
   - Color chip with percentage (3-tier coloring: green ≥85, yellow 70-84, red <70).
   - "Earned X / Y points across N questions".
   - Click row to expand → shows `contributing_submissions` inline.
4. **Empty state** — when both arrays empty: friendly message ("This student hasn't submitted anything in this class yet.").

### Wire-up

**Modify:** `frontend/src/tabs/ProgressRankGrid.jsx`

The student-name `<td>` at line 146-148 currently has no `onClick`. Add it:

```javascript
<td
  onClick={function() { setSelectedStudent(student); }}
  style={{ ..., cursor: 'pointer' }}
  ...
>
  {student.student_name}
</td>
```

Add component-level state `var [selectedStudent, setSelectedStudent] = useState(null);` and render the drawer at the bottom:

```javascript
{selectedStudent && (
  <StudentReportCard
    classId={classId}
    studentId={selectedStudent.student_id}
    attemptMode={attemptMode}
    onClose={function() { setSelectedStudent(null); }}
  />
)}
```

The grid's existing `attemptMode` state propagates to the card (Q5: inherit from grid).

### API client

**Modify:** `frontend/src/services/api.js`

Add next to `getClassProgressRank` (line 1648):

```javascript
export async function getStudentReportCard(classId, studentId, attemptMode) {
  const mode = attemptMode || 'latest';
  return fetchApi('/api/teacher/class/' + classId + '/student/' + studentId + '/report-card?attempt_mode=' + mode);
}
```

---

## Error handling

| Failure mode | HTTP | UX |
|---|---|---|
| Unauthenticated request | 401 | Frontend redirects to login (existing fetchApi behavior) |
| Class not owned by teacher | 403 | Drawer shows error message, doesn't render trajectory |
| Student not in class | 404 | Same as 403 — error message |
| No submissions yet | 200 + empty arrays | Drawer renders empty-state message |
| Backend exception | 500 with RFC 7807 envelope | Drawer shows generic error message; teacher can retry by reopening |

The endpoint uses the same `@handle_route_errors` decorator as the rest of Phase 5d's surface, so all errors come back as RFC 7807 problem+json with the legacy `error` field preserved.

---

## Testing

### Backend

**New file:** `tests/test_student_report_card.py`

Required cases:
- `test_unauthenticated_returns_401` — no teacher session.
- `test_other_teacher_class_returns_403` — class belongs to a different teacher.
- `test_student_not_in_class_returns_404` — valid class, but student not enrolled.
- `test_happy_path_returns_trajectory_and_breakdown` — student with multiple submissions across multiple assessments; verify trajectory chronological order, breakdown sorted worst-first, contributing_submissions populated.
- `test_no_submissions_returns_empty_arrays_with_200` — student in class but never submitted.
- `test_attempt_mode_latest_picks_most_recent_per_content` — submit 3 attempts at one assessment; verify the breakdown reflects only the latest.
- `test_attempt_mode_best_picks_highest_per_content` — same setup; verify best is used.
- `test_attempt_mode_average_aggregates_attempts` — same setup; verify average is used.
- `test_invalid_attempt_mode_falls_back_to_latest` — pass `attempt_mode=garbage`; verify it doesn't 400.

Test fixtures should follow the patterns in `tests/test_class_routes.py` and `tests/test_student_portal_routes.py`. Use the existing supabase mock fixture.

### Frontend

No new frontend unit tests in the MVP (consistent with how Phase 2 shipped — the grid has no dedicated tests either; Vite build and the existing E2E suite cover regression risk). If a Playwright test is wanted later, add it to `tests/e2e/`.

### Manual smoke test

After local backend + frontend changes, verify:
1. Open a class with at least one assessment and one submission.
2. Click a student's name in the grid → drawer slides in.
3. Trajectory chart renders with reference lines at 70/85.
4. Per-standard breakdown is sorted worst-first.
5. Click a standard row → contributing submissions expand inline.
6. Switch grid `attempt_mode` and re-open the drawer → drawer reflects the new mode.
7. Click outside / `×` → drawer closes.

---

## Out of scope (deferred)

- **Click-to-navigate from trajectory point** to a submission detail page. Phase 2c candidate.
- **Cross-class history** — this card is class-scoped only. A multi-class "Student Profile" view is a future phase.
- **Subject / grade-level filters** within the card.
- **Export to PDF / share link.**
- **Real-time updates** — the drawer fetches once on open; no polling or socket subscription.
- **Click standard header in grid** — different feature; remains deferred from Phase 2.
- **Per-question detail view** — the trajectory shows per-submission, not per-question. Question-level deep-dive belongs in a separate per-submission view that doesn't yet exist.

---

## Compliance

- **Data sources:** Reads only from `classes`, `class_students`, `students`, `published_content`, `student_submissions`. No SSO, no roster sync, no Clever/ClassLink/OneRoster contracts touched. The 199 SIS contract tests remain untouched.
- **PII:** Student names are already exposed in the existing grid endpoint; no new PII surface. Standards codes are public curriculum identifiers (not student-specific).
- **Auth model:** Same authentication path as `get_class_progress_rank` (the Phase 2 endpoint). Class ownership is checked via `classes.teacher_id == g.teacher_id`.

---

## Files touched

**Created:**
- `backend/routes/student_portal_routes.py` — new route handler `get_student_report_card` added in-place
- `frontend/src/tabs/StudentReportCard.jsx` — new component (~200 LOC)
- `tests/test_student_report_card.py` — new test file

**Modified:**
- `backend/routes/student_portal_routes.py` — add the new route handler
- `frontend/src/tabs/ProgressRankGrid.jsx` — add click handler on student-name cell + render the drawer
- `frontend/src/services/api.js` — add `getStudentReportCard` client function

**Not touched:**
- `backend/services/grading_service.py` (`_build_standards_mastery` already does what we need from Phase 1)
- Any SIS / SSO / roster file
- `mypy.ini` / `.github/workflows/ci.yml` / `setup.cfg` / `requirements*.{in,txt}`
