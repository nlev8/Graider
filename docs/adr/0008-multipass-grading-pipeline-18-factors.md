# ADR 0008 — Multipass grading pipeline with all grading factors accumulated into prompt context

- **Status:** Accepted (retrospective record)
- **Date recorded:** 2026-06-10 (decision predates this record)

## Context

A single LLM call grading a whole multi-section assignment produced
unreliable scores: long prompts diluted per-question instructions, and a
teacher's context (rubric, accommodations, expected answers, grading style)
was inconsistently applied across questions. At the same time, grading
correctness depends on a large set of teacher- and student-specific inputs;
omitting *any one* of them produces wrong scores or generic feedback that
teachers immediately notice.

## Decision

1. **Multipass over single-pass for OpenAI grading:** the pipeline is
   `grade_multipass` → `grade_per_question` (one focused call per question)
   → `generate_feedback` (one synthesis call), implemented in
   `backend/services/grading_pipeline.py` (orchestration + single-pass
   `grade_assignment` for Claude/Gemini) and
   `backend/services/grading_leaves.py` (`grade_per_question`).
   `assignment_grader.py` survives as a thin re-export shim so legacy
   `from assignment_grader import ...` callers keep resolving.
2. **All grading factors flow through one accumulated context.** The
   canonical list — 18 factors: global AI instructions, assignment grading
   notes, custom rubric, rubric-type override, grading style, IEP/504
   accommodations, student history, class-period differentiation, expected
   answers, grade level & subject, section type, section name & points,
   student actual answers, ELL language, effort points & completeness caps,
   assignment template, FITB exemption, writing-style profile — is
   maintained in `CLAUDE.md` § "AI Grading Factors" and is contractual:
   **never drop a factor**. Mechanically, `file_ai_notes` (built in the
   grading thread, `backend/grading/pipeline.py`) accumulates the
   teacher/student/assignment factors into one string passed as
   `custom_ai_instructions` → `teacher_instructions`; the rubric prompt is
   appended to `effective_instructions` in `grade_multipass()` so
   per-question graders see it; `grading_style` both shapes the
   per-question prompt and applies deterministic score caps.
3. **Deterministic post-processing over prompt tweaking** for correctness
   guarantees (score caps, completeness caps, FITB exemption from
   AI/plagiarism detection) — prompts are layer 1; code is the safety net.

## Consequences

- Per-question calls cost more tokens than one big call; accepted for
  accuracy and for per-question feedback specificity. Token spend is
  tracked (`TokenTracker`, `backend/services/grading_models.py`).
- The factor list is a cross-cutting invariant: any new grading entry point
  (portal grading, Celery task, regrade) must thread the same factors, and
  refactors of the pipeline are reviewed against the list.
- Single-pass `grade_assignment` remains for non-OpenAI providers, so both
  paths must be updated when a factor is added.

## Evidence

- `CLAUDE.md` § "AI Grading Factors (CRITICAL — Never Drop Any Factor)"
  (full 18-factor list + flow description)
- `backend/services/grading_pipeline.py` (`grade_multipass`,
  `grade_assignment`), `backend/services/grading_leaves.py`
  (`grade_per_question`)
- `backend/grading/pipeline.py` (`file_ai_notes` accumulation in the
  grading thread), `backend/services/rubric_formatting.py`
  (`format_rubric_for_prompt`)
- `assignment_grader.py` (re-export shim header comments)
