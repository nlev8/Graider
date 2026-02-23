# Programmatic FITB Scorer

## Goal
Score fill-in-the-blank answers deterministically using fuzzy string matching instead of sending short factual answers to the AI. Only send written sections (Questions, Summary, Reflection) to the AI. Falls back to current AI-only path if no answer key is found.

## File Changes

**Only file modified:** `/Users/alexc/Downloads/Graider/assignment_grader.py`

No changes to `backend/app.py`, frontend, or assignment configs.

---

## New Functions (4 total, ~200 lines)

All placed around line 400 (after `extract_fitb_by_template_comparison`, before `extract_student_responses`).

### 1. `parse_answer_key_from_notes(grading_notes: str) -> list | None`
- Searches for lines matching `Check:`, `Answers:`, `Expected:`, or `Answer Key:` (case-insensitive)
- Splits by comma to get individual answer entries
- Splits each entry by `/` for alternates: `"doubled/size"` → `["doubled", "size"]`
- Returns `None` if no answer key line found (triggers fallback to AI)

### 2. `normalize_for_comparison(text: str) -> str`
- Lowercase, strip punctuation, collapse whitespace
- Remove `$`, commas in numbers (`"15,000,000"` → `"15000000"`)
- Strip filler articles for short text

### 3. `score_fitb_programmatic(extracted_responses: list, grading_notes: str) -> dict`
- Calls `parse_answer_key_from_notes` — returns early with `has_answer_key: False` if no key
- Separates responses into `fitb_items` (type contains `"fill_in_blank"`) and `written_items` (everything else)
- Order-based matching: answer_key[0] ↔ fitb_items[0], etc.
- For each pair, uses `difflib.SequenceMatcher` for fuzzy matching + containment check for sentence-type blanks
- Thresholds: `≥0.85` = correct, `≥0.60` = partial (half credit), else wrong
- Returns `{"score": 0-100, "correct": int, "partial": int, "total": int, "details": [...], "written_sections": [...], "has_answer_key": bool}`

### 4. `build_fitb_feedback(details, score, total, correct) -> str`
- Generates 2-3 sentence feedback from scoring details
- Mentions correct count, lists wrong/partial answers with expected values
- Tone matches existing Graider feedback style (encouraging, specific)

---

## Integration Point

**Location:** `grade_assignment()` at line ~3109 where `is_fitb` is checked.

**New flow (inserted before existing FITB code block):**

```
if is_fitb and content:
    1. Run extraction: extract_student_responses(content, markers, excludes, template)
    2. Call score_fitb_programmatic(extracted_responses, custom_ai_instructions)
    3. If has_answer_key and total > 0:
       a. If written_sections exist (hybrid assignment):
          - Score FITB blanks programmatically
          - Send ONLY written_sections to AI for grading
          - Blend: final = fitb_score * (blanks / total_items) + ai_score * (written / total_items)
       b. If NO written_sections (pure FITB):
          - Return programmatic result directly — NO API call
          - Build feedback with build_fitb_feedback()
          - Set ai_detection/plagiarism_detection to "none"
    4. Else (no answer key): fall through to existing AI-only FITB path (unchanged)
```

**The existing code at lines 3123-3146 becomes the `else` fallback — zero changes to it.**

---

## Matching Strategy

| Student writes | Expected | Strategy | Result |
|---|---|---|---|
| `"1803"` | `"1803"` | Exact after normalize | correct |
| `"Thomas Jeferson"` | `"Thomas Jefferson"` | SequenceMatcher 0.93 | correct |
| `"15million"` | `"15 million"` | Normalize removes spaces in numbers | correct |
| `"Louisiana"` | `"France"` | SequenceMatcher 0.25 | wrong |
| `"doubled the size"` | `"doubled/size"` | Check each alternate, containment match | correct |
| `"trade ways"` | `"territories/land"` | SequenceMatcher <0.6 for both | wrong |

For `fill_in_blank_sentence` type (answer is full sentence like "The year was _1803___"):
- Extract just the filled-in portion using underscore boundaries
- Also check if expected answer appears as substring within the full answer

---

## Safety / No-Break Guarantees

1. **Non-FITB assignments**: `is_fitb` is False → new code never reached
2. **FITB without grading notes**: `parse_answer_key_from_notes` returns `None` → falls to existing AI path
3. **FITB with grading notes but no "Check:" line**: Same as #2
4. **Existing AI-only FITB code**: Moved into `else` branch, completely unchanged
5. **No new dependencies**: Uses `difflib.SequenceMatcher` from Python stdlib

---

## Verification

1. Test `parse_answer_key_from_notes` with Louisiana Purchase grading notes → should return `[["1803"], ["France"], ["doubled", "size"], ["15 million"], ["territories", "land"]]`
2. Test `score_fitb_programmatic` with Eddilys Leonardo's extracted responses → should score each blank
3. Regrade Eddilys via API → should get programmatic FITB score + AI score for written sections, no plagiarism flag
4. Regrade a non-FITB assignment (e.g., Cornell Notes Increasing Regional Tensions) → should work exactly as before
5. Check an assignment without grading notes → falls back to AI-only, no errors
