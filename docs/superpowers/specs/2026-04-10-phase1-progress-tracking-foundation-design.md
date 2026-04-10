# Phase 1 — Progress Tracking Foundation Design Spec

## Problem

Graider's progress tracking is shallow compared to Progress Learning. Teachers can't see which standards a student has mastered, how long they spent per question, or compare attempts on the same assessment. To build richer reports in Phase 2/3 (Progress Rank grid, Student Report Card, Quick-Click Remediation), we need a data foundation that captures standard tagging on graded results, per-question time spent, and attempt history.

## Solution

Propagate question standards into graded results, capture per-question time tracking from the student portal, and expose attempt history in the teacher UI. All changes are additive — existing data, endpoints, and UIs keep working. No schema migration touches SSO, roster sync, or OneRoster grade posting.

## Scope

This is pure data plumbing plus two small teacher UI touches. No new reports, no new dashboards. Phase 2 builds the reports on top of this foundation.

## Data Model

### `student_submissions` — one new column

```sql
ALTER TABLE student_submissions
  ADD COLUMN IF NOT EXISTS question_times JSONB;
```

- `question_times` — nullable JSONB mapping question key → seconds spent. Example: `{ "0-0": 45, "0-1": 120, "1-0": 30 }`. Null for existing rows; populated on new submissions.

No other schema changes. Attempts already work via `attempt_number` + one row per attempt. No `is_canonical` column — the attempt history drawer shows all attempts but doesn't change which one is "official" (Phase 3 will redesign the gradebook).

### `results` JSONB — new fields

Each graded question gets a `standard` field copied from the source question:

```json
{
  "questions": [
    {
      "question": "...",
      "student_answer": "...",
      "correct_answer": "...",
      "is_correct": true,
      "points_earned": 1,
      "points_possible": 1,
      "standard": "SS.8.A.1.1"
    }
  ],
  "standards_mastery": {
    "SS.8.A.1.1": { "points_earned": 3, "points_possible": 4, "question_count": 2 },
    "SS.8.A.1.2": { "points_earned": 1, "points_possible": 2, "question_count": 1 }
  },
  "score": 15,
  "total_points": 20,
  "percentage": 75
}
```

`standards_mastery` is a per-standard rollup computed at grading time. Questions without a `standard` field are excluded from the rollup and still appear under `questions[]` with `standard: null`.

## Backend Changes

### Grading pipeline — 3 files

1. **`backend/services/grading_service.py`** — `grade_instant_only` and `grade_student_submission`
2. **`backend/services/portal_grading.py`** — `run_portal_grading_thread` (multipass grading)

In each grading path, after computing per-question scores, copy the `standard` field from the source question into the result dict, then build the `standards_mastery` rollup by iterating over graded questions and summing points per standard.

### Submission endpoint — accept question_times

**`backend/routes/student_account_routes.py`** — `submit_student_work` (around line 734-950)

- Accept `question_times` in the request body alongside `answers`
- Store in the `question_times` column on the new submission row
- No behavior change if client doesn't send it (backwards compatible)

**`backend/routes/student_account_routes.py`** — `save_submission_draft` (added in previous phase)

- Accept `question_times` in the draft save body
- Store in the existing draft row

### Teacher results endpoint — return attempts

**`backend/routes/student_portal_routes.py`** — `get_assessment_results` (or the equivalent class-based endpoint)

When a teacher views submissions for a class-based assessment, return ALL attempts (not just the latest), sorted by `attempt_number`. Frontend groups them by student.

If this endpoint doesn't already exist for class-based content (the current one uses `join_code`), add a new endpoint: `GET /api/teacher/content/<content_id>/submissions` that returns all submissions grouped by student.

## Frontend Changes

### Student — per-question time capture

**`frontend/src/components/StudentPortal.jsx`**

Add state: `var [questionTimes, setQuestionTimes] = useState({});` and `var [currentQuestionKey, setCurrentQuestionKey] = useState(null);` and `var [questionStartedAt, setQuestionStartedAt] = useState(null);`

When a student focuses/answers a new question:
- Calculate elapsed seconds for the previous question key (if any)
- Add to `questionTimes[prevKey] = (questionTimes[prevKey] || 0) + elapsed`
- Set `currentQuestionKey = newKey`, `questionStartedAt = Date.now()`

Send `questionTimes` with:
- The final submit POST (into `submit_student_work`)
- Each draft auto-save and manual save (into `save_submission_draft`)

### Teacher — standards badges + summary card

**`frontend/src/App.jsx`** — assessment results panel

**1. Per-question standard badge:** In the submission detail view (when a teacher clicks a student's row to see the graded output), each question row shows a small badge with the standard code next to the points display. Pulls from `results.questions[i].standard`.

**2. Standards summary card:** At the top of the assessment results panel, above the submissions list, add a card titled "Standards in this Assessment." It lists each standard from the assessment's questions with:
- Standard code
- Question count
- Class average (computed by summing `standards_mastery[code].points_earned` across all canonical submissions and dividing by total possible)

Only shown when the assessment has at least one question with a standard.

### Teacher — attempt history drawer

**`frontend/src/App.jsx`** — assessment results panel

Each student row in the submissions list shows an "Attempt X of Y" label when `attempt_number > 1` or more than one attempt exists for this student.

Click the label → opens a side drawer with:
- All attempts for this student on this assessment, sorted by attempt_number
- Each attempt shows: attempt number, submission date, score, percentage, time taken
- Click an attempt → opens the existing graded-view modal preloaded with that attempt's data
- No "set canonical" button — that's Phase 3

## Compliance (Clever / ClassLink / OneRoster)

**No changes to SSO, roster sync, or grade posting.**

Verified:
- `backend/routes/clever_routes.py` never reads `student_submissions.results` or `published_content.content` JSONB — only interacts with `classes`, `students`, `class_students` tables
- `backend/routes/classlink_routes.py` same — roster-only
- `backend/routes/oneroster_routes.py` and `backend/services/oneroster_gradebook.py` only post aggregate `score`/`max_score` to external systems, not per-question details
- `backend/roster_sync.py` is fully isolated from submission content

Standards codes (e.g., `SS.8.A.1.1`) are public state curriculum identifiers — not PII and not covered by FERPA. Storing them in `student_submissions.results` doesn't change the data's sensitivity classification.

Per-question time tracking captures elapsed seconds only, not timestamps or PII. No new data categories, no new disclosure, no new compliance considerations.

## Non-Goals

- Progress Rank grid view (cross-assessment mastery grid) → Phase 2
- Student Report Card with trajectory charts → Phase 2
- Quick-Click Remediation (AI-generated targeted practice) → Phase 4
- Canonical attempt selection / gradebook redesign → Phase 3
- Backfilling standards into historical submissions → not needed; new data accumulates going forward
- Time-per-question reports ("students spent avg 3 min on Q5") → Phase 2
- Per-standard class mastery across multiple assessments → Phase 2

## Migration Plan

1. Run `ALTER TABLE` migration manually in Supabase dashboard (user action)
2. Deploy backend changes — grading pipeline starts populating `standard` and `standards_mastery` on new submissions
3. Deploy frontend changes — students start sending `question_times`, teachers see new badges/summary/drawer
4. Existing submissions keep working with null `question_times` and no `standard` field in results — UI gracefully handles missing data
5. Teachers see the foundation features immediately (badges, summary, drawer) while Phase 2/3 build the bigger reports on top
