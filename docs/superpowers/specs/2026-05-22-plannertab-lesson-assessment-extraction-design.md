# PlannerTab lesson + assessment extraction (via `useQuestionEditing`) — Design

**Date:** 2026-05-22 · **Status:** Design approved, pending spec review · **Scope:** 3 PRs · Wave 3 slices 4–6.
**Lever:** Code-Quality concentrated complexity — `frontend/src/tabs/PlannerTab.jsx` (5,322 LOC after the calendar/tools/dashboard slices).

> **For agentic workers:** execute via the established cadence — per-PR exhaustive free-identifier audit (props + imports + parent-body `function`/`const`/`var` closures), then implementation (PR1 via TDD on the hook; PR2/PR3 via assembly+rewire scripts because the file is large and a subagent edit timed out on the calendar removal), then two-stage subagent review, Vite build + frontend test floor + Playwright E2E + normalized-JSX parity.

---

## 1. Goal

Decompose PlannerTab's two largest and last-remaining inline blocks — **lesson** (~2,192 LOC) and **assessment** (~1,624 LOC) — across 3 behavior-preserving PRs. Unlike calendar/tools/dashboard (cleanly isolated, pure JSX moves), these are **cross-coupled** through a shared question-editing cluster; PR1 resolves that coupling by decentralizing it into a hook, which de-risks the two component extractions and is itself the "genuine state decentralization" the 2026-05-22 post-Wave-3 re-score named.

## 2. Cross-coupling audit (against `PlannerTab.jsx` @ main `b9688db`)

- **Blocks:** lesson `{plannerMode === "lesson" && (` line 1251 → `)}` 3443 (inner 1252–3442); assessment `{plannerMode === "assessment" && (` line 3444 → `)}` 5068 (inner 3445–5067). After them: the already-extracted `<PlannerDashboard>`/`<PlannerCalendar>`/`<PlannerTools>` calls.
- **Shared question-editing STATE (PlannerTab-local, used by BOTH blocks):** `editMode` (615), `selectedQuestions` (616), `editingQuestion` (617), `regeneratingQuestions` (618). (`sectionsDropdownOpen` (619) is **assessment-only**.)
- **Shared question-editing HANDLERS (PlannerTab-body, used by BOTH):** `toggleQuestionSelect` (628), `selectAllQuestions` (637), `saveEditedQuestion` (647), `deleteSelectedQuestions` (664), `regenerateSelectedQuestions` (686), `regenerateOneQuestion` (756). They consume the `getActiveAssignment`/`setActiveAssignment` props (which read/write the truly-shared App state `lessonPlan`/`generatedAssignment`/`generatedAssessment` depending on mode) plus `api.regenerateQuestions`. They call **no other PlannerTab closures** (verified).
- **Other shared closure used by both:** `publishAssessmentHandler` (460).
- **Lesson-only closures:** `brainstormIdeasHandler`, `generateLessonPlan`, `handleDocUpload`, `handleMatchStandards`, `removeUploadedDoc`.
- **Assessment-only closures:** none.
- **`shareWithClass` and `renderTagRow` are NOT used by either block** (dashboard-only — already extracted). They are not part of these interfaces.
- **Shared props (both blocks):** `assignment`, `standards`, `selectedStandards`, `setSelectedStandards`, `uploadedDocs`. **Lesson-only props:** `config`, `lessonPlan`/`setLessonPlan`, `generatedAssignment`/`setGeneratedAssignment`, `unitConfig`/`setUnitConfig`, `contentOnly`/`setContentOnly`, `addToast`, `user`, `setPlannerMode`, `setAssignment`. **Assessment-only props:** `assessmentConfig`/`setAssessmentConfig`, `assessmentAnswers`/`setAssessmentAnswers`, `assessmentLoading`, `gradingAssessment`, `savingAssessment`, `saveAssessmentName`/`setSaveAssessmentName`, `selectedSources`/`setSelectedSources`, `generatedAssessment`/`setGeneratedAssessment`, `periods`, `savedAssignments`, `savedAssignmentData`, `savedLessons`.
  - Exact per-block interfaces are re-derived programmatically at each PR's implementation (line numbers shift after PR1); the lists above are the audited starting point.

## 3. Key behavior-preservation decision: single shared hook instance

The 4 QE state vars currently live in PlannerTab, which is **always-mounted** (`display:none` toggle); the lesson/assessment blocks are conditionally rendered inside it. So QE state (selections, edit-mode) **persists across mode switches today**. If each extracted component called its own `useQuestionEditing` instance, that state would reset whenever the user switches lesson↔assessment — a behavior change.

**Therefore: PlannerTab calls `useQuestionEditing` exactly once and passes the returned bundle down to both `PlannerLesson` and `PlannerAssessment` as props.** Single shared instance preserved (no reset-on-switch); logic decentralized into the hook; JSX decentralized into the components.

## 4. PR1 — `frontend/src/hooks/useQuestionEditing.js`

Decentralization only; no component extraction. Behavior-preserving.

### Hook
```js
import { useState } from "react";
import * as api from "../services/api";

export function useQuestionEditing({
  getActiveAssignment, setActiveAssignment,
  addToast, config, unitConfig, globalAINotes,
  lessonPlan, generatedAssignment, generatedAssessment,
}) {
  const [editMode, setEditMode] = useState(false);
  const [selectedQuestions, setSelectedQuestions] = useState(new Set());
  const [editingQuestion, setEditingQuestion] = useState(null); // "sIdx-qIdx" key
  const [regeneratingQuestions, setRegeneratingQuestions] = useState(new Set());

  // 6 handlers moved VERBATIM from PlannerTab (toggleQuestionSelect, selectAllQuestions,
  // saveEditedQuestion, deleteSelectedQuestions, regenerateSelectedQuestions, regenerateOneQuestion)

  return {
    editMode, setEditMode, selectedQuestions, setSelectedQuestions,
    editingQuestion, setEditingQuestion, regeneratingQuestions, setRegeneratingQuestions,
    toggleQuestionSelect, selectAllQuestions, saveEditedQuestion,
    deleteSelectedQuestions, regenerateSelectedQuestions, regenerateOneQuestion,
  };
}
```
- The 4 `useState` lines and the 6 handler bodies move **verbatim** (the only change: handler closures now close over the hook's params/state instead of PlannerTab's). Init values copied from the current decls (615–618).
- **PlannerTab change:** replace the 4 state decls (615–618) + 6 handler defs (628–807) with one call + destructure:
  ```js
  const {
    editMode, setEditMode, selectedQuestions, setSelectedQuestions,
    editingQuestion, setEditingQuestion, regeneratingQuestions, setRegeneratingQuestions,
    toggleQuestionSelect, selectAllQuestions, saveEditedQuestion,
    deleteSelectedQuestions, regenerateSelectedQuestions, regenerateOneQuestion,
  } = useQuestionEditing({ getActiveAssignment, setActiveAssignment, addToast, config, unitConfig, globalAINotes, lessonPlan, generatedAssignment, generatedAssessment });
  ```
  The lesson + assessment blocks are **untouched** (same bare identifiers, now sourced from the hook). `sectionsDropdownOpen` and `publishAssessmentHandler` stay in PlannerTab (not part of this hook).
- **Test:** `frontend/src/hooks/__tests__/useQuestionEditing.test.js` (or alongside existing test convention) — unit tests via `@testing-library/react`'s `renderHook`: `toggleQuestionSelect` toggles a key; `selectAllQuestions` selects across sections of a stub active assignment; `saveEditedQuestion` calls `setActiveAssignment` with the edit applied; `regenerateOneQuestion`/`regenerateSelectedQuestions` call `api.regenerateQuestions` (mocked) and write back via `setActiveAssignment`. This is the new independently-testable surface.
- **PlannerTab LOC:** ≈ −180.

## 5. PR2 — `frontend/src/components/PlannerLesson.jsx`

- Verbatim move of the lesson inner JSX (1251–3443 region, re-audited post-PR1).
- **Lesson-only handlers move INTO the component** (`brainstormIdeasHandler`, `generateLessonPlan`, `handleDocUpload`, `handleMatchStandards`, `removeUploadedDoc`) — they are lesson-only, so this genuinely decentralizes them (their own prop deps re-audited and forwarded).
- Receives as props: the lesson-only state props + the shared props + the **QE bundle** (the 14 hook returns) + `getActiveAssignment`/`setActiveAssignment` + `publishAssessmentHandler` (the shared non-QE handler, if the lesson block uses it — re-audit).
- Exhaustive free-identifier audit (props + imports + parent-body closures) derives the exact interface; prop set derived programmatically so signature == call site.

## 6. PR3 — `frontend/src/components/PlannerAssessment.jsx`

- Verbatim move of the assessment inner JSX (3444–5068 region, re-audited).
- `sectionsDropdownOpen` (assessment-only) becomes **local state** in the component.
- Receives: assessment-only props + shared props + the QE bundle + `getActiveAssignment`/`setActiveAssignment` + `publishAssessmentHandler`.
- Same programmatic-interface discipline.

## 7. Behavior preservation (all PRs)

- PR1: verbatim state + handler move into the hook; single instance in PlannerTab; blocks unchanged. No behavior change (the hook returns the same names; closures capture the same values via params).
- PR2/PR3: verbatim JSX moves under the existing `{plannerMode === "lesson"/"assessment" && (<Component … />)}` gates (mount/unmount unchanged). QE bundle forwarded from PlannerTab's single hook instance → selections persist across mode switches exactly as today.
- Truly-shared App state (`lessonPlan`/`generatedAssignment`/`generatedAssessment`) stays in App; PlannerTab forwards it. No `App.jsx` change.

## 8. Testing & proof (per PR)

- PR1: `useQuestionEditing` unit tests (renderHook) + full suite stays green + Vite build. No JSX parity needed (no JSX moved); the lesson/assessment blocks are byte-identical (only state/handler source changed).
- PR2/PR3: new `PlannerLesson.test.jsx` / `PlannerAssessment.test.jsx` (smoke + a focused handler/QE-wiring test) + **normalized-JSX parity** (the definitive verbatim check) + **free-variable scan** of the new component (zero undefined identifiers — the runtime-completeness guard that caught `shareWithClass`/`renderTagRow`) + signature==call-site check + full suite + Playwright E2E.
- Two-stage subagent review (spec-compliance then code-quality) per PR.

## 9. Out of scope

- No logic/UX/endpoint changes; no `App.jsx` change.
- No merging lesson + assessment into one component (defeats de-concentration).
- The Code-Quality dimension will not reach 8 on PlannerTab alone (per the re-score) — SettingsTab.jsx (6,534) + App.jsx (7,144) remain; those are separate future levers, not in scope here.

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| QE state resets on mode-switch (behavior change) | Single hook instance in PlannerTab, bundle forwarded to both (§3). |
| A handler captures a PlannerTab value not passed as a hook input | Audited: the 6 handlers' deps are exactly the 9 inputs + `api`; no other closures. Re-verify in PR1. |
| Missed prop/closure when extracting the components (runtime error) | Per-PR exhaustive free-identifier scan (props/imports/parent-body closures) + programmatic prop derivation + free-var scan of the new component + two-stage review. |
| Large mechanical edit times out a subagent | Controller-run assertion-guarded assembly/anchor scripts (the proven calendar/tools/dashboard method); subagents do review only. |
| Not a verbatim JSX move | Whitespace-normalized parity diff per component PR. |

## 11. Expected numbers

- PR1: PlannerTab ≈ −180 LOC (state + handlers → hook). New `useQuestionEditing.js` ≈ ~200 LOC.
- PR2: PlannerTab − ~2,000 LOC. New `PlannerLesson.jsx` ≈ ~2,100 LOC.
- PR3: PlannerTab − ~1,500 LOC. New `PlannerAssessment.jsx` ≈ ~1,600 LOC.
- End state: PlannerTab ≈ ~1,600–1,800 LOC (an orchestrator that owns shared App-state forwarding + the trailing modals + the mode-nav + the hook call) — below the <3k target all three re-score models named. Cumulative Wave 3: 7,405 → ~1,700 (−77%).

## 12. References

- Prior Wave 3 slices: calendar (#456), tools (#458), dashboard (#459); closeouts #457/#460; post-Wave-3 re-score #461 (Code Quality held 7, recommended continue lesson/assessment then SettingsTab).
- Canonical scorecard: `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`.
- Prior phase plan: `docs/superpowers/plans/2026-05-04-planner-tab-extraction.md` (flagged question-editing as cross-cutting over lessonPlan/generatedAssignment/generatedAssessment).
