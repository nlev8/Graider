# Portal Multipass Grading — Design Spec

## Problem

The portal auto-grader (`grade_student_submission` in `student_portal_routes.py`) uses basic scoring: instant MC/TF, simple OpenAI call for written answers. It does NOT use Graider's core 18-factor multipass grading pipeline (`grade_per_question` + `generate_feedback` in `assignment_grader.py`), which provides writing style fingerprinting, historical feedback, IEP/ELL accommodations, rubric-aware scoring, and category breakdowns.

## Solution

Connect portal submissions to the full multipass grading pipeline. Skip Pass 1 (extraction) since portal answers are already structured JSON. Feed directly into Pass 2 (`grade_per_question`) and Pass 3 (`generate_feedback`).

## Submission Flow

1. Student submits via portal
2. **MC/TF/matching** — graded instantly (deterministic), results shown to student immediately
3. **Auto-detect**: If assignment has NO written questions → done, full score shown, no teacher approval needed
4. **If written questions exist**:
   - Student sees: "5/7 multiple choice correct. 3 written responses pending teacher review." No percentage or letter grade.
   - Background thread spawns to run multipass grading
   - Background thread loads: teacher config (AI notes, rubric, grading style), student history, accommodations
   - Calls `grade_per_question()` for each written question with all 18 factors
   - Calls `generate_feedback()` for overall feedback with writing style analysis
   - Writes result to teacher's results storage (for Results tab + Analytics)
   - Updates Supabase `student_submissions` record with full grading data
   - Result appears in Results tab with `email_approval: "pending"`
5. Teacher reviews in Results tab, edits feedback if needed, approves
6. Student sees full scores + feedback after approval

## Result Record Format

The background grading writes a result in the exact format analytics expects:

```python
{
    "student_name": "Jane Doe",
    "student_id": "stu_uuid",
    "assignment": "Title of Published Content",
    "score": 85,
    "letter_grade": "B",
    "period": "Q3",
    "graded_at": "2026-03-20T...",
    "email_approval": "pending",
    "filename": "",
    "source": "portal",
    "breakdown": {
        "content_accuracy": 88,
        "completeness": 90,
        "writing_quality": 78,
        "effort_engagement": 85
    },
    "feedback": "...",
    "per_question_scores": [...],
}
```

## What This Enables

- Writing style fingerprint tracked over time per student
- Historical-aware feedback referencing past performance and trends
- IEP/ELL accommodations modify grading expectations
- Rubric category breakdowns (content, completeness, writing, effort)
- Grading style (lenient/standard/strict) applied
- Student history updated after each grading
- Full analytics integration (student progress, trends, category analysis)

## Auto-Detection Logic

- If ALL questions are MC/TF/matching → instant grading, full score shown, no approval needed
- If ANY question is short_answer/extended_response/essay → multipass pipeline + teacher approval

## Same Pipeline for Assessments and Assignments

Both use `sections` → `questions` structure. Grading behavior is determined by question type and teacher settings (grading style), not by the assessment/assignment label.

## District Report Export Fix

The `export_district_report` endpoint currently reads from `master_grades.csv` only. Update to read from results storage first (same as main analytics), fall back to CSV.

## Files to Modify

- `backend/routes/student_portal_routes.py` — Update submission handler to spawn background grading thread for written questions
- `backend/routes/student_account_routes.py` — Same update for class-based submissions
- `backend/app.py` or new `backend/services/portal_grading.py` — New `grade_portal_submission_full()` function that orchestrates Pass 2 + Pass 3
- `backend/routes/analytics_routes.py` — Update district report export to read from results storage
- `frontend/src/components/StudentPortal.jsx` — Update results display for partial scores
- `frontend/src/components/StudentDashboard.jsx` — Show "pending review" status for written questions

## What Does NOT Change

- `assignment_grader.py` — No changes to the grading engine itself
- `analytics_routes.py` main analytics — Reads from results storage, works automatically
- Results tab — Already handles `email_approval: "pending"`
- Teacher approval workflow — Already exists
