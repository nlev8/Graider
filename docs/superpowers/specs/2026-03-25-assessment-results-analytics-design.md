# Assessment Results & Analytics Integration — Design Spec

## Goal

Add formative/summative assessment labeling, a dedicated Assessment Results section in the Results tab, and assessment data integration into Analytics with per-question item analysis.

## Scope

**In scope:**
- Formative/summative label at publish time (assessment_category field)
- New collapsible "Assessment Results" section in Results tab
- Assessment detail view with student scores and per-question breakdown
- Formative/summative filter tabs
- Merge assessment scores into existing Analytics charts
- New Item Analysis panel in Analytics (per-question % correct + answer distribution)
- Formative vs summative comparison summary
- Both publish paths (join-code and class-based)
- FERPA compliance: strict teacher scoping, audit logging

**Out of scope:**
- Co-teacher data sharing (strict teacher-only access)
- Formative trend tracking over time (future enhancement)
- Modifying existing Assignment Results section
- Student-facing analytics

## Publish Flow Changes

### Assessment Category Label

When `content_type === "assessment"`, the publish modal adds a toggle:
- **Formative** (default) — quizzes, checks for understanding, exit tickets
- **Summative** — unit tests, midterms, finals

Not shown when `content_type === "assignment"`.

### Storage

Stored as `assessment_category: "formative" | "summative"` inside the existing `settings` JSONB column in both `published_assessments` and `published_content` tables. No schema migration needed.

Default: `"formative"` if not set (backward compatible with existing assessments).

## Results Tab Changes

### Layout

Two collapsible sections, both expanded by default:

1. **Assessment Results** (new, top) — purple accent header with chevron toggle
2. **Assignment Results** (existing, bottom) — unchanged content, collapsible header added

Each header shows a count badge (e.g., "3 assessments", "12 graded").

### Assessment Results Section

**Header bar:**
- Collapsible chevron + "Assessment Results" title + count badge
- Filter tabs: All / Formative / Summative

**Table columns:**
- Assessment title + publish date + period/join code
- Type badge: green "Formative" or red "Summative"
- Submission count (completed / total expected)
- Average score (percentage)
- Status: "Complete" (green) or "N pending" (amber)
- "View Details" link

**Data sources:**
- `published_assessments` table (join-code path) — filtered by `teacher_id`
- `published_content` table (class-based path) — filtered by `teacher_id`, `content_type = 'assessment'`
- Submissions from `submissions` and `student_submissions` tables respectively

### Assessment Detail View

Expands inline when teacher clicks "View Details":

**Summary bar:**
- Total submissions, average score, highest score, lowest score, average time taken

**Student scores table:**
- Columns: student name, score, percentage, letter grade, time taken, submitted at, status
- Sortable by any column
- Status: "Graded" (green), "Pending" (amber for AI-graded written responses), "Submitted" (gray)

**Per-question breakdown (collapsible):**
- Each question: number, question text, type, correct answer, % students correct
- For MC: answer distribution — how many students picked each option (count + percentage)
- For TF: True vs False distribution
- For short answer/extended response: "X graded, Y pending" count
- Questions where <50% correct highlighted with a warning indicator

## Analytics Tab Changes

### Filter Extension

New filter toggle at the top of Analytics: "All / Assignments / Assessments"
- Controls which data feeds all existing charts (grade distribution, student averages, trends)
- Default: "All" — combined view

### Existing Charts — Enhanced

When "All" or "Assessments" filter active:
- **Grade Distribution pie chart** — includes assessment scores
- **Assignment Averages bar chart** — renamed to "Performance by Activity", shows both assignments and assessments
- **Student Proficiency vs Growth scatter** — includes assessment data points in average/trend calculations
- **Needs Attention / Top Performers** — assessment scores factor into student averages and trends

### Item Analysis Panel (New)

Only visible when "Assessments" or "All" filter active and at least one assessment has results.

**Controls:**
- Dropdown to select a specific assessment (lists all published assessments with results)

**Per-question bar chart:**
- Horizontal bars showing % correct per question
- Color coded: green (>80%), amber (50-80%), red (<50%)
- Click a bar to expand answer distribution:
  - MC: "A: 10% (3 students), B: 85% (24 students) [correct], C: 3% (1), D: 2% (1)"
  - TF: "True: 72% (20), False: 28% (8) [correct: False]"
  - Short answer: "Graded: 25, Pending: 3, Avg score: 7.2/10"

### Formative vs Summative Summary Card

Small card in the Analytics overview:
- Formative average: X%
- Summative average: Y%
- Helps teachers see if students perform differently on low-stakes vs high-stakes

## Backend Changes

### New Endpoint: `GET /api/assessment-results`

Returns all assessments published by the current teacher with aggregated data.

**Auth:** `@require_teacher`
**Audit:** Logged via `audit_log("VIEW_ASSESSMENT_RESULTS", ...)`

**Response:**
```json
{
  "assessments": [
    {
      "id": "uuid",
      "title": "US History - Ch 5 Quiz",
      "assessment_category": "formative",
      "content_type": "assessment",
      "source": "join_code" | "class_based",
      "join_code": "ABC123",
      "period": "Period 3",
      "published_at": "2026-03-24T...",
      "settings": { ... },
      "stats": {
        "total_submissions": 24,
        "expected_submissions": 28,  // null for join-code assessments (no roster)
        "average_score": 78,
        "highest_score": 100,
        "lowest_score": 45,
        "average_time_seconds": 420,
        "pending_count": 4,
        "graded_count": 20
      },
      "submissions": [
        {
          "student_name": "Jane Doe",
          "score": 85,
          "percentage": 85,
          "letter_grade": "B",
          "time_taken_seconds": 380,
          "submitted_at": "2026-03-24T...",
          "status": "graded",
          "answers": null,  // omitted in list view — fetched on "View Details" expansion
          "results": null   // omitted in list view — fetched on "View Details" expansion
        }
      ],
      "question_analysis": [
        {
          "number": 1,
          "question": "What document declared independence?",
          "type": "multiple_choice",
          "correct_answer": "B",
          "percent_correct": 85,
          "response_distribution": {
            "A": { "count": 3, "percent": 10 },
            "B": { "count": 24, "percent": 85, "is_correct": true },
            "C": { "count": 1, "percent": 3 },
            "D": { "count": 0, "percent": 0 }
          }
        },
        {
          "number": 2,
          "type": "true_false",
          "correct_answer": "True",
          "percent_correct": 72,
          "response_distribution": {
            "True": { "count": 20, "percent": 72, "is_correct": true },
            "False": { "count": 8, "percent": 28 }
          }
        },
        {
          "number": 3,
          "type": "short_answer",
          "percent_correct": null,
          "graded_count": 25,
          "pending_count": 3,
          "average_score": 7.2,
          "max_points": 10
        }
      ]
    }
  ]
}
```

**Query logic:**
1. Fetch `published_assessments` where `teacher_id` = current teacher
2. Fetch `published_content` where `teacher_id` = current teacher AND `content_type = 'assessment'`
3. For each: fetch submissions from respective tables
4. Compute aggregates (average, distribution, per-question analysis)
5. Return merged list sorted by `published_at` DESC

### Modified Endpoint: `GET /api/analytics`

**New query parameter:** `source=all|assignments|assessments`

**New response fields:**
```json
{
  "assessment_stats": [
    {
      "name": "US History - Ch 5 Quiz",
      "category": "formative",
      "average": 78,
      "count": 24,
      "highest": 100,
      "lowest": 45
    }
  ],
  "assessment_category_summary": {
    "formative_average": 82,
    "formative_count": 3,
    "summative_average": 72,
    "summative_count": 1
  }
}
```

When `source=all` or `source=assessments`:
- Assessment scores included in `class_stats` (class average, grade distribution)
- Assessment scores included in `student_progress` (individual averages, trends)
- Assessment entries included in `all_grades` array

### No Database Schema Changes

- `assessment_category` stored in existing `settings` JSONB column
- No new tables
- No column additions
- Unique constraint on `submissions(join_code, student_name)` already added

## FERPA Compliance

| Requirement | Implementation |
|---|---|
| Teacher-scoped data access | All queries filter by `teacher_id` from session |
| No cross-teacher visibility | Strict — only publishing teacher sees results |
| Auth on all endpoints | `@require_teacher` decorator on `/api/assessment-results` |
| Audit logging | `audit_log("VIEW_ASSESSMENT_RESULTS")` on data access |
| Student PII protection | Names visible only to publishing teacher, not in any public/shared context |
| No external AI calls | Assessment results are aggregation only — no student data sent to AI |
| Clever compliance | Teacher-scoped storage patterns match existing `require_teacher_id()` guards |
| Data minimization | Response includes only what the teacher needs — no internal IDs, no cross-references |

## Frontend Files

| File | Change |
|---|---|
| `frontend/src/tabs/ResultsTab.jsx` | Add Assessment Results section with collapsible headers |
| `frontend/src/tabs/AnalyticsTab.jsx` | Add source filter, item analysis panel, category summary card |
| `frontend/src/App.jsx` | Add `assessmentResults` state, fetch endpoint, pass to ResultsTab/AnalyticsTab. Add `assessmentCategory` to publish settings. |
| `frontend/src/services/api.js` | Add `getAssessmentResults()` API call |

## Backend Files

| File | Change |
|---|---|
| `backend/routes/student_portal_routes.py` | Store `assessment_category` in publish settings |
| `backend/routes/assessment_results_routes.py` | NEW file — `/api/assessment-results` endpoint |
| `backend/routes/analytics_routes.py` | Add `source` filter, include assessment data in analytics response |

## Test Impact

**New tests needed:**
- `/api/assessment-results` endpoint: auth, teacher scoping, formative/summative filtering, aggregation correctness
- Analytics with `source` filter: verify assessment data merges correctly
- Publish flow: verify `assessment_category` persisted and returned

**Existing tests unaffected:**
- All student portal tests (QuestionPlayer, submission flow)
- All assignment grading tests
- Current analytics tests (assignment-only path unchanged)
