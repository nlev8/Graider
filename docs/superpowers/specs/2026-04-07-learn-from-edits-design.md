# Learn from Edits — Design Spec

## Problem

When a teacher corrects an AI-assigned grade, the original score is overwritten and the correction is lost. The AI makes the same mistakes on the next assignment. Teachers shouldn't have to correct the same grading patterns repeatedly.

## Solution

Capture the delta between AI scores and teacher corrections. Store correction patterns per-teacher and globally. Inject those patterns into the grading prompt so the AI calibrates to each teacher's expectations and improves across all teachers for systematic accuracy issues.

## Scope

- Score corrections only for the learning loop (feedback deltas captured but not acted on yet)
- Prompt injection only — no post-processing score adjustments
- Per-teacher patterns (style/preference) + global patterns (systematic AI errors)
- Global threshold: 3+ teachers must independently show the same correction pattern before it surfaces

## Layer 1: Capture the Delta

When a teacher edits a grade via `POST /api/update-result`, preserve the original AI values before overwriting.

Add fields to the result object:
- `ai_score` (int) — original AI-assigned score, copied from `score` on first edit
- `ai_feedback` (str) — original AI feedback, copied from `feedback` on first edit
- `teacher_edited` (bool) — true if teacher modified score or feedback
- `edit_timestamp` (str) — ISO timestamp of the edit

On first edit of a result:
1. If `ai_score` is not already set, copy `score` → `ai_score`
2. If `ai_feedback` is not already set, copy `feedback` → `ai_feedback`
3. Set `teacher_edited = true`
4. Set `edit_timestamp` to now
5. Then apply the teacher's new values to `score` and `feedback` (existing behavior)

Subsequent edits update `score`/`feedback` and `edit_timestamp` but do not overwrite `ai_score`/`ai_feedback` (those are always the original AI values).

No UI changes — the edit flow stays the same.

## Layer 2: Store Correction Patterns (Per-Teacher)

New storage key per teacher: `grading_corrections` in `teacher_data`.

```json
{
  "corrections": [
    {
      "assignment": "Unit 3 Assessment",
      "question_type": "short_answer",
      "subject": "US History",
      "grade_level": "8",
      "ai_score": 2,
      "teacher_score": 4,
      "max_points": 5,
      "delta": 2,
      "student_answer_snippet": "Student explained the cause but used incomplete sentences",
      "timestamp": "2026-04-07T10:30:00Z"
    }
  ],
  "patterns": {
    "short_answer": { "avg_delta": 1.8, "count": 12, "direction": "up" },
    "multiple_choice": { "avg_delta": 0.0, "count": 0, "direction": "none" },
    "extended_writing": { "avg_delta": -0.5, "count": 3, "direction": "down" }
  },
  "updated_at": "2026-04-07T10:30:00Z"
}
```

`corrections` — raw log of the last 100 score edits. Each entry records the question type, subject, AI score, teacher score, and a snippet of the student's answer for context.

`patterns` — computed summary updated on each edit. Average score delta per question type, direction (teacher grades higher or lower than AI), and count. Only question types with 3+ corrections generate a pattern.

When a teacher edits a score:
1. Determine the question type from the result's breakdown or section data
2. Append to `corrections` (trim to last 100)
3. Recompute `patterns` for the affected question type
4. Save via `storage.save('grading_corrections', data, teacher_id)`

## Layer 3: Global Patterns

Same structure stored at system level: `storage.save('grading_corrections:global', data, 'system')`.

When a per-teacher correction is saved, also append an anonymized entry to the global log:
- No student name, no teacher ID
- Only: question_type, subject, grade_level, ai_score, teacher_score, delta, timestamp

Global patterns recompute the same way as per-teacher but with an additional constraint: a global pattern only surfaces when 3+ different teachers have independently corrected in the same direction for the same question type.

To track teacher diversity, the global log includes a hashed teacher identifier (not the actual ID) so we can count unique teachers without identifying them.

## Layer 4: Inject into Grading Prompt

In `backend/app.py` where `file_ai_notes` is built (inline in the grading thread), after student history context and before rubric, add a correction context block.

New function: `build_correction_context(teacher_id, subject, question_types)` in a new file `backend/services/correction_patterns.py`.

This function:
1. Loads per-teacher patterns from `storage.load('grading_corrections', teacher_id)`
2. Loads global patterns from `storage.load('grading_corrections:global', 'system')`
3. For each question type in the current assignment, checks if a pattern exists
4. Builds a prompt string with specific examples

**Per-teacher injection (always included if 3+ corrections exist for a question type):**

```
GRADING CALIBRATION (based on this teacher's previous corrections):
- Short Answer: This teacher has adjusted scores upward by ~1.8 points on average across 12 corrections. When students demonstrate understanding but use incomplete sentences or informal language, this teacher expects higher scores. Adjust your grading accordingly.
```

**Global injection (only if 3+ teachers agree):**

```
ACCURACY NOTE: Multiple teachers have independently found that short answer questions in US History are underscored by ~1.2 points on average. Consider this systematic tendency when grading.
```

The injection includes up to 3 concrete examples from the corrections log (most recent, most representative) so the AI has specific cases to reference, not just abstract statistics.

## Where It Connects

The correction context string is appended to `file_ai_notes` in `app.py` (file-based grading) and passed as part of `teacher_instructions` in `portal_grading.py` (portal grading). Both paths feed into `grade_per_question()` which already receives `custom_ai_instructions`.

No changes to `assignment_grader.py` — the correction context rides the existing `teacher_instructions` parameter.

## Files Changed

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/routes/grading_routes.py` | **Modify** | Capture AI score/feedback delta on edit |
| `backend/services/correction_patterns.py` | **Create** | Store corrections, compute patterns, build prompt context |
| `backend/app.py` | **Modify** | Inject correction context into `file_ai_notes` |
| `backend/services/portal_grading.py` | **Modify** | Inject correction context into portal grading instructions |
| `tests/test_correction_patterns.py` | **Create** | Tests for pattern computation and prompt building |

## What This Does NOT Include

- No UI for viewing correction patterns (future dashboard)
- No feedback learning loop (data captured but not acted on)
- No model fine-tuning — prompt injection only
- No student-facing changes
- No changes to the Results tab edit UI
