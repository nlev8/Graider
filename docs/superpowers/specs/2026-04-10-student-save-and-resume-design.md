# Student Save-and-Resume — Design Spec

## Problem

Students taking class-based assessments/assignments lose all their answers if they close the tab or navigate away. Answers are stored only in React state (`StudentPortal.jsx` line 37). There's no draft mechanism in the backend, no auto-save, no resume. Students must complete the entire assessment in one sitting.

## Solution

Store in-progress answers as drafts in `student_submissions` with `status='draft'`. Auto-save every 15 seconds and on manual click. Resume automatically when the student re-opens the assessment. Timer runs server-side to prevent abuse. Add "Mark for Review" flags and teacher-side "End attempt" control inspired by Wayground.

## Data Model

### `student_submissions` table — new columns

| Column | Type | Purpose |
|--------|------|---------|
| `draft_answers` | JSONB | In-progress answers, saved periodically |
| `marked_for_review` | JSONB (array) | Question keys the student flagged for review |
| `time_started_at` | timestamptz | When the student first started the attempt, used for server-side timer |

### Status values

- `not_started` — no submission row yet
- `draft` — in-progress, auto-saving
- `submitted` — final, awaiting grading
- `graded` — scored
- `returned` — teacher sent back (existing)

## Backend Endpoints

### `POST /api/student/submission/<content_id>/draft`

Auto-save and manual-save hit the same endpoint. Student session auth required.

**Request body:**
```json
{
  "answers": { "q1": "...", "q2": "..." },
  "marked_for_review": ["q3", "q5"]
}
```

**Behavior:**
- If no `student_submissions` row exists: create one with `status='draft'`, `time_started_at=now()`, `draft_answers`, `marked_for_review`
- If a draft row exists: update `draft_answers`, `marked_for_review`, bump `updated_at`
- If row exists with `status='submitted'` or `'graded'`: return 409 "Already submitted"
- Return `{ "success": true, "time_started_at": ..., "remaining_seconds": ... }`

### `GET /api/student/submission/<content_id>/draft`

Fetch existing draft to resume.

**Returns:**
```json
{
  "answers": {...},
  "marked_for_review": [...],
  "time_started_at": "2026-04-10T...",
  "remaining_seconds": 1200,
  "time_limit_seconds": 1800
}
```

Or `{ "draft": null }` if no draft exists.

Server calculates `remaining_seconds = max(0, time_limit_seconds - (now - time_started_at))`. If `time_limit_seconds` is null (no time limit), `remaining_seconds` is null.

### `POST /api/student/submission/<content_id>/submit-draft`

Converts a draft to a final submission. Merges `draft_answers` into `answers`, sets `status='submitted'`, triggers grading (existing flow).

### `POST /api/teacher/end-attempt/<submission_id>`

Teacher-side force-end. Converts draft to final submission with whatever answers exist. Requires teacher ownership check.

## Frontend — Student (StudentPortal.jsx)

### On mount

If `contentId` is set (class-based assessment), fetch draft via `GET /api/student/submission/<content_id>/draft`. If draft exists:
- Populate `answers` state with `draft.answers`
- Populate `markedForReview` state with `draft.marked_for_review`
- Set `remainingSeconds` from server response
- Show banner: "Resumed from draft — {N} questions answered"

If no draft exists, record `time_started_at=now()` on first answer change (triggers draft creation via auto-save).

### Auto-save

`useEffect` that runs when `answers` or `markedForReview` changes. Debounced 15 seconds. Calls `POST /.../draft`. Silent on success (no toast). On failure, retries with exponential backoff. Maximum retry interval: 60 seconds.

### Manual save

"Save for later" button next to the Submit button. Calls the same endpoint, shows success toast "Draft saved — you can close the tab and come back later."

### Mark for Review

Each question has a small flag icon button next to it. Click toggles the question key in `markedForReview` state. Flagged questions show a subtle yellow border. Before submit, a review screen lists:
- Unanswered questions (red)
- Flagged questions (yellow)
- Completed questions (green)

Student can click each to jump back. "Submit anyway" button at the bottom.

### Timer

`remainingSeconds` counts down client-side. Server is source of truth — every auto-save response includes updated `remaining_seconds`, and client re-syncs. When hits 0, auto-submit draft.

## Frontend — Teacher (App.jsx, Assessment Results panel)

### "In Progress" section

In the assessment results panel (when viewing a specific assessment's results), add an "In Progress" section above the submitted list showing students with `status='draft'`.

**Per-student row:**
- Student name
- Progress: "12 of 20 questions answered"
- Time: "15 min elapsed"
- "End attempt" button → confirmation → calls `POST /api/teacher/end-attempt/<submission_id>`

### Ended attempts

When a teacher ends an attempt, it becomes a regular submitted row in the results with whatever answers existed. A subtle label indicates "Force-ended by teacher."

## Files

| File | Changes |
|------|---------|
| Supabase schema | Add `draft_answers`, `marked_for_review`, `time_started_at` columns to `student_submissions`; update status check constraint |
| `backend/routes/student_account_routes.py` | Add draft endpoints (save, get, submit-draft); update existing submission handlers to handle drafts |
| `backend/routes/student_portal_routes.py` | Add teacher end-attempt endpoint; include in-progress drafts in assessment results |
| `frontend/src/services/api.js` | Add `saveDraft`, `getDraft`, `submitDraft`, `endAttempt` helpers |
| `frontend/src/components/StudentPortal.jsx` | Fetch draft on mount, auto-save, manual save button, mark-for-review flags, review screen, timer |
| `frontend/src/App.jsx` | In-progress section in assessment results panel with "End attempt" button |

## Non-goals

- Drafts for join-code portal submissions (only class-based) — join codes are anonymous, no way to match drafts to students
- Offline support (localStorage backup) — auto-save requires network, but network is usually available during active use
- Real-time collaborative drafts — one student per attempt
- Drafts for resource content (flashcards, study guides) — only assessments/assignments
- Cross-device sync beyond what Supabase provides naturally (student logs in on another device, draft loads from their account)

## Security

- Draft save endpoint verifies student session token
- Teacher end-attempt verifies class ownership
- Drafts are not visible to other students or teachers outside the owning class
- Time limit enforced server-side — clients can't cheat by pausing the client clock
