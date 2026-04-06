# Question Mix UI — Design Spec

## Problem

Teachers can't control the exact number of each question type when generating assignments or assessments. The current Sections UI is a set of on/off toggles — teachers enable "Multiple Choice" and "Short Answer" but can't say "I want 4 MC and 2 short answer." The AI distributes questions however it wants, and the only post-generation option is editing individual questions (can't swap types).

## Solution

Replace the Sections toggles with per-type number inputs. Each question type gets a count field (0 = skip). A counter shows assigned vs total so teachers know how many are left to distribute.

## Where it applies

Both:
1. **Lesson Planner → Assignment mode** — the Sections dropdown in the Details sidebar
2. **Assessment Generator** — the section categories config

## UI Design

```
Total Questions: [10]

Question Mix (8/10 assigned)
┌──────────────────────────────────┐
│ Multiple Choice         [4]     │
│ Short Answer            [2]     │
│ Math Computation        [0]     │
│ Geometry & Measurement  [0]     │
│ Graphing                [0]     │
│ Data Analysis           [0]     │
│ Extended Writing        [1]     │
│ Vocabulary              [0]     │
│ True / False            [1]     │
│ FL FAST Items           [0]     │
└──────────────────────────────────┘
⚠️ 2 questions unassigned — AI will distribute
```

## Rules

1. **Count > 0 = enabled.** No separate toggle. Setting a count to 0 hides that section from generation.
2. **Assigned < total:** Show info message: "N questions unassigned — AI will distribute among enabled types." This is not an error — it's the existing behavior (AI decides).
3. **Assigned = total:** Show green checkmark. Teacher has full control.
4. **Assigned > total:** Show red warning: "Exceeds total by N." Block generation until fixed.
5. **Counts are integers, min 0, max = total.** Number input with stepper arrows.
6. **Remove "Per Section (0 = auto)" field** — replaced by per-type counts.

## Data Flow

### Frontend → Backend

Currently the frontend sends:
```json
{
  "sectionCategories": {"multiple_choice": true, "short_answer": true, ...},
  "totalQuestions": 10,
  "questionsPerSection": 0
}
```

New format:
```json
{
  "sectionCategories": {"multiple_choice": true, "short_answer": true, ...},
  "questionTypeCounts": {"multiple_choice": 4, "short_answer": 2, "true_false": 1, "extended_writing": 1},
  "totalQuestions": 10
}
```

`sectionCategories` is derived from `questionTypeCounts` (any count > 0 = true). Keeps backward compatibility — old code that reads `sectionCategories` still works.

### Backend Prompt

The `_build_section_categories_prompt()` function in `planner_routes.py` already builds per-section instructions. Add the count to each instruction:

Current: "Generate standard multiple choice questions with 4 options."
New: "Generate exactly 4 multiple choice questions with 4 options."

If no count specified for a type, fall back to current behavior (AI decides).

## State Changes

### Assignment mode (lesson planner)

Replace `assignmentSectionCategories` (boolean map) with `assignmentQuestionCounts` (number map):

```javascript
const [assignmentQuestionCounts, setAssignmentQuestionCounts] = useState({
  multiple_choice: 4,
  short_answer: 2,
  extended_writing: 1,
  // all others default to 0
});
```

Derive `sectionCategories` at send time: `Object.fromEntries(Object.entries(counts).map(([k,v]) => [k, v > 0]))`

### Assessment Generator

Same change to `assessmentConfig.sectionCategories` — replace booleans with counts.

## What This Does NOT Include

- No drag-and-drop reordering of question types
- No per-question editing of type after generation (existing Edit Questions handles this)
- No DOK level distribution per type (future enhancement)
- No point allocation per type (points are set per-question in Edit Questions)
