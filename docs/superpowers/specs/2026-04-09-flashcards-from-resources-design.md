# Flashcards from Uploaded Resources — Design Spec

## Problem

The flashcard generator in Planner > Details > Tools only works when a lesson plan or assessment has been generated. Teachers who upload reference documents and want flashcards without generating a full lesson plan or assessment first see a disabled button or "Generate a lesson plan or assessment first" error.

## Solution

Add uploaded resource documents as a third content source for the flashcard generator. No backend changes needed — the existing `/api/generate-flashcards` endpoint accepts arbitrary text.

## Content Source Priority

1. **Lesson plan** — `lessonPlan.overview` + day topics (existing)
2. **Generated assessment** — section/question text (existing)
3. **Uploaded resources** — concatenated `uploadedDocs[].text` (new fallback)
4. **Error** — "Generate a lesson plan, assessment, or upload resources first."

All three sources are additive — if a teacher has a lesson plan AND uploaded docs, both contribute to the flashcard content.

## Changes

**File:** `frontend/src/App.jsx`

1. **Content building (line ~15219-15229):** After the existing `lessonPlan` and `generatedAssignment` blocks, add a fallback that appends `uploadedDocs` text content.

2. **Error message (line ~15231):** Update from "Generate a lesson plan or assessment first" to "Generate a lesson plan, assessment, or upload resources first."

3. **Button disabled condition (line ~15262):** Change from `!lessonPlan && !generatedAssignment` to `!lessonPlan && !generatedAssignment && uploadedDocs.length === 0`.

## Non-goals

- No backend changes
- No new API endpoints
- No changes to the flashcard rendering or export
- No changes to the study guide or slide deck generators (could be done separately later)
