# Multi-Pass Grading: Full App Integration Plan

## Status: ✅ IMPLEMENTED

All fixes below have been applied to `assignment_grader.py`.

---

## Problem (Original)

The multi-pass `grade_per_question()` was receiving truncated context — `custom_ai_instructions[:500]` and `accommodation_context[:300]` — which stripped critical grading information like period differentiation, rubric overrides, expected answers, and accommodation details.

---

## Key Insight: `app.py` Already Builds Full Context

**`backend/app.py` (lines 975-1119)** builds `file_ai_notes` by concatenating ALL context into a single string before calling the grading engine:

| # | Context | How It Gets Into `custom_ai_instructions` |
|---|---------|------------------------------------------|
| 1 | **Global AI instructions** | `global_ai_notes` from Settings |
| 2 | **Assignment gradingNotes** | From Builder config (expected answers, vocab definitions) |
| 3 | **Rubric type overrides** | FITB / essay / cornell-notes / custom rubric instructions |
| 4 | **Accommodation context** (IEP/504) | `build_accommodation_prompt(student_id)` appended |
| 5 | **Student history** (prior grades, streaks) | `build_history_context(student_id)` appended |
| 6 | **Period differentiation** | Class period + rubric weight adjustments (advanced: +15% critical thinking; support: +20% effort) |
| 7 | **GradingNotes expected answers** | Inside gradingNotes block |

This concatenated string arrives as `custom_ai_instructions` in the grading functions. **No additional context building is needed in `assignment_grader.py`.**

---

## The Fix: Pass `custom_ai_instructions` Untruncated

Instead of the originally proposed `_build_grading_context()` dict, the simpler approach is:

1. Pass the **full untruncated** `custom_ai_instructions` string as `teacher_instructions` to every sub-call
2. Let `grade_per_question()` and `generate_feedback()` embed it directly in their prompts
3. Only build things NOT in `custom_ai_instructions` separately (ELL language, expected answer parsing, section metadata)

---

## Context Flow (Implemented)

| # | Context | Multi-Pass Status | How |
|---|---------|-------------------|-----|
| 1 | **Rubric** (default or custom) | ✅ | In `custom_ai_instructions` via rubric type overrides |
| 2 | **Section rubric** (per-marker points & types) | ✅ | `_distribute_points()` returns section metadata per response |
| 3 | **Global AI instructions** | ✅ | In `custom_ai_instructions` — UNTRUNCATED |
| 4 | **Grading style** (lenient/strict/standard) | ✅ | Separate `grading_style` param → score anchors in prompt |
| 5 | **Accommodation context** (IEP/504) | ✅ | In `custom_ai_instructions` — UNTRUNCATED |
| 6 | **Student history** (prior grades, streaks) | ✅ | In `custom_ai_instructions` — UNTRUNCATED |
| 7 | **Writing style baseline** (AI detection) | ✅ | Handled post-grading in `grade_multipass()`, same as single-pass |
| 8 | **Assignment template** (original questions) | ✅ | Passed to `extract_student_responses()` for extraction |
| 9 | **Grade level + age range** | ✅ | Separate `grade_level` param in prompt |
| 10 | **Subject** | ✅ | Separate `subject` param in prompt |
| 11 | **Response type instructions** (FITB/vocab/written) | ✅ | `response_type` + `section_type` → type-specific prompt block |
| 12 | **Completeness caps** (skipped sections penalty) | ✅ | Aggregator applies caps based on `blank_count` + `grading_style` |
| 13 | **Period differentiation** | ✅ | In `custom_ai_instructions` — UNTRUNCATED |
| 14 | **ELL language** | ✅ | Loaded separately in `grade_multipass()` → passed to `generate_feedback()` for bilingual translation |
| 15 | **GradingNotes** (expected answers) | ✅ | `_parse_expected_answers()` extracts from `custom_ai_instructions`, matched to per-question calls |

---

## Implemented Function Signatures

### `grade_per_question()`
```python
def grade_per_question(question: str, student_answer: str, expected_answer: str,
                       points: int, grade_level: str, subject: str,
                       teacher_instructions: str, grading_style: str,
                       ai_model: str = 'gpt-4o',
                       response_type: str = 'marker_response',
                       section_name: str = '', section_type: str = 'written') -> dict:
```
- `teacher_instructions` = full untruncated `custom_ai_instructions` from `app.py`
- `response_type` drives section-specific grading instructions (vocab_term, numbered_question, fitb_full, fill_in_blank, summary, written)
- `section_name` and `section_type` from `_distribute_points()` metadata
- Uses OpenAI Structured Output → `PerQuestionResponse` Pydantic model
- `temperature=0, seed=42` for reproducibility

### `generate_feedback()`
```python
def generate_feedback(question_results: list, total_score: int, total_possible: int,
                      letter_grade: str, grade_level: str, subject: str,
                      teacher_instructions: str = '', ell_language: str = None,
                      ai_model: str = 'gpt-4o-mini') -> dict:
```
- `teacher_instructions` = full untruncated `custom_ai_instructions` (includes student history, accommodations, teacher priorities)
- `ell_language` loaded separately for bilingual translation post-step
- Uses OpenAI Structured Output → `FeedbackResponse` Pydantic model
- `temperature=0.4` for creative but consistent feedback

### `_distribute_points()`
```python
def _distribute_points(responses: list, marker_config: list, total_points: int) -> list:
```
- Returns `[{'points': int, 'section_name': str, 'section_type': str}, ...]`
- Matches each extracted response to its marker_config entry by name

### `_parse_expected_answers()`
```python
def _parse_expected_answers(custom_instructions: str) -> dict:
```
- Parses "Q1: answer" patterns and "VOCABULARY EXPECTED DEFINITIONS" blocks from gradingNotes
- Returns dict mapping question index (int) or term text (str) to expected answer

### `grade_multipass()` orchestrator
```python
def grade_multipass(student_name, assignment_data, custom_ai_instructions='',
                    grade_level='6', subject='Social Studies', ai_model='gpt-4o-mini',
                    student_id=None, assignment_template=None, rubric_prompt=None,
                    custom_markers=None, exclude_markers=None, marker_config=None,
                    effort_points=15, extraction_mode='structured', grading_style='standard'):
```
- Passes `custom_ai_instructions` **untruncated** as `teacher_instructions` to all sub-calls
- Does NOT call `build_accommodation_prompt()` or `build_history_context()` (already in `custom_ai_instructions`)
- Only builds separately: ELL language (for translation), expected answers (for per-question matching), section metadata (for type-specific grading)

---

## Marker Flow (Implemented)

```
Teacher configures in Builder:
  customMarkers: ["VOCABULARY", "QUESTIONS", "SUMMARY"]
  excludeMarkers: ["Name", "Date", "Period"]
  marker_config: [
    {"start": "VOCABULARY", "points": 30, "type": "fill-in-blank"},
    {"start": "QUESTIONS", "points": 40, "type": "written"},
    {"start": "SUMMARY", "points": 20, "type": "written"}
  ]
  gradingNotes: "EXPECTED ANSWERS:\n- Q1: Lewis and Clark...\nVOCABULARY:\n- Nationalism: strong loyalty..."

  ↓

app.py builds file_ai_notes (lines 975-1119):
  → global_ai_notes + gradingNotes + rubric overrides + accommodation + history + period differentiation
  → This becomes custom_ai_instructions

  ↓

extract_student_responses(content, customMarkers, excludeMarkers, assignment_template)
  → Finds VOCABULARY, QUESTIONS, SUMMARY sections
  → Parses vocab terms, numbered questions, written responses
  → Returns: [{question: "Nationalism", answer: "love for country", type: "vocab_term"}, ...]
  → Also returns: blank_questions, missing_sections

  ↓

_distribute_points(responses, marker_config, total_content_points)
  → Matches each response to its marker section
  → Returns: [{points: 30, section_name: "VOCABULARY", section_type: "fill-in-blank"}, ...]

_parse_expected_answers(custom_ai_instructions)
  → Extracts Q1/Q2 patterns and VOCABULARY EXPECTED DEFINITIONS from gradingNotes
  → Returns: {0: "Lewis and Clark...", "Nationalism": "strong loyalty..."}

  ↓

grade_per_question(question="Nationalism", answer="love for country",
                   expected="strong loyalty to one's nation",
                   points=30,
                   grade_level="6", subject="Social Studies",
                   teacher_instructions=custom_ai_instructions,  # FULL — untruncated
                   grading_style="standard",
                   response_type="vocab_term",
                   section_name="VOCABULARY",
                   section_type="fill-in-blank")
  → AI gets: section type instructions, expected answer, teacher's full grading context
    (rubric, differentiation, accommodations, history), score anchors, grading style

  ↓

Scores aggregated → Effort points calculated → Completeness caps applied
  → generate_feedback(question_results, score, possible, letter_grade,
                       grade_level, subject,
                       teacher_instructions=custom_ai_instructions,
                       ell_language=ell_language)
  → Feedback AI gets: full teacher context, student history, per-question results
  → ELL translation appended if applicable

  ↓

Detection merged by grade_with_parallel_detection() (unchanged)
  → Writing profile updated → Result returned
```

---

## What Does NOT Change

- `extract_student_responses()` — extraction logic unchanged
- `detect_ai_plagiarism()` — detection logic unchanged, runs in parallel via `grade_with_parallel_detection()`
- `grade_with_parallel_detection()` — wiring + detection merge unchanged
- `grade_assignment()` — single-pass remains as fallback for Claude/Gemini models
- Score caps, feedback replacement, blank detection — all unchanged
- AI detection auto-cap + approval flow — all unchanged
- Frontend — no changes needed, result format is identical

---

## Why NOT `_build_grading_context()`

The original plan proposed a `_build_grading_context()` function that would rebuild accommodation, history, rubric, etc. inside `assignment_grader.py`. This was **redundant** because:

1. `app.py` already builds this exact context at lines 975-1119
2. It arrives as the `custom_ai_instructions` parameter — already a complete string
3. Rebuilding it would duplicate logic and risk divergence between single-pass and multi-pass
4. The simpler approach: just pass the string through **untruncated**

The only things built separately in `assignment_grader.py` are:
- **Expected answers** — parsed from gradingNotes for per-question matching
- **Section metadata** — from marker_config for type-specific grading instructions
- **ELL language** — loaded from `~/.graider_data/ell_students.json` for translation post-step
