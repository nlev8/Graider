# Standards–Requirements Mismatch Warning

## Context

Teachers enter "Additional Requirements" (e.g., "focus on consequences of the Mexican American War") alongside selected standards. If the requirements reference content from a *different* standard than the ones selected, the AI still generates — but the output won't match intent. We need a client-side pre-flight check that warns (non-blocking) when the requirements text doesn't align with the selected standards' content.

## Approach

**Pure keyword-matching utility** — no AI call, no backend change. Runs synchronously before each generation API call. Extracts a keyword pool from the selected standards' `topics`, `vocabulary`, and `benchmark` fields, then checks overlap with the requirements text. If zero relevant overlap is found, shows a warning toast. The teacher can still proceed.

## Plan

### 1. New utility — `frontend/src/utils/standardsMismatch.js` (~120 lines)

**Exported function:**
```js
checkRequirementsMismatch(requirementsText, selectedStandardCodes, allStandards)
→ { mismatch: boolean, message: string }
```

**Algorithm:**
1. If `requirementsText` is blank → `{ mismatch: false }`
2. Build keyword pool from all selected standards:
   - **Multi-word phrases** (kept intact): all `topics[]` + `vocabulary[]` entries
   - **Single words** (tokenized, stopwords removed): from `benchmark` + `learning_targets[]`
3. Tokenize requirements text → remove stopwords → remove generic instructional words → remaining = `contentWords`
4. If `contentWords` is empty (requirements are purely instructional like "include visuals") → `{ mismatch: false }`
5. Check multi-word phrase matches: for each phrase from standards, check if lowercased requirements text contains it
6. Check single-word matches: for each content word, check if it exists in the single-word pool
7. Decision:
   - Any multi-word phrase match → no warning (strong alignment signal)
   - ≥15% single-word overlap → no warning
   - Otherwise → `{ mismatch: true, message: "..." }`
8. **Bonus — inverse code check**: scan requirements for standard code patterns (regex). If a code is found that isn't in `selectedStandards`, mention it in the warning.

**Constants included in file:**
- `STOPWORDS` — ~80 common English stopwords
- `GENERIC_INSTRUCTIONAL_WORDS` — ~100 pedagogy terms ("visuals", "group work", "scaffolded", "hands-on", etc.) that should never trigger a mismatch
- `STANDARD_CODE_PATTERN` — regex matching codes like `SS.7.C.1.1`, `MA.6.NSO.1.1`

### 2. Frontend — Insert checks in 4 handlers (`frontend/src/App.jsx`)

Add import at top:
```js
import { checkRequirementsMismatch } from "./utils/standardsMismatch";
```

Insert non-blocking check in each handler, **after** existing validation guards, **before** the loading state setter / API call:

| Handler | Location | Notes |
|---|---|---|
| `brainstormIdeasHandler` | After standards check, before `setBrainstormLoading(true)` | Always runs |
| `generateLessonPlan` | After standards check, before `setPlannerLoading(true)` | Always runs |
| `generateAssessmentHandler` | After standards check, before `setAssessmentLoading(true)` | Always runs |
| `generateAssignmentFromLessonHandler` | After `!lessonPlan` check, before `setAssignmentLoading(true)` | Only if `selectedStandards.length > 0` |

Each insertion is 3 lines:
```js
const mismatchResult = checkRequirementsMismatch(unitConfig.requirements, selectedStandards, standards);
if (mismatchResult.mismatch) addToast(mismatchResult.message, "warning");
```

### Edge cases handled

| Scenario | Result |
|---|---|
| Empty/blank requirements | No check, no warning |
| Generic-only requirements ("include visuals and group work") | Content words empty after filtering, no warning |
| "focus on Civil War" with Enlightenment standards selected | "Civil War" not in topics/vocab, low word overlap → warning |
| "focus on Enlightenment thinkers" with SS.7.C.1.1 | "Enlightenment" matches topic + vocab → no warning |
| Requirements mention code "SS.7.C.1.5" but only SS.7.C.1.1 selected | Inverse check catches it, adds to warning message |
| Multi-standard selection | Keyword pool is union across all selected → broader match |
| Works across all subjects | Keyword pool comes from whatever standards are selected |

### Key files
- `frontend/src/utils/standardsMismatch.js` — **NEW**, utility function
- `frontend/src/App.jsx` — 1 import + 4 check insertions (~13 new lines)

### Verification
1. `npm run build` passes
2. Select SS.8.4.1 (Mexican American War), type "focus on causes of the Civil War" → amber warning toast appears
3. Same standard, type "focus on consequences of the Mexican American War" → no warning
4. Type "include visuals and group work" with any standard → no warning
5. Type requirements referencing a standard code not selected → warning mentions the code
6. Empty requirements field → no warning, generation proceeds normally
7. Warning is non-blocking — generation always proceeds regardless
