# PlannerTab lesson + assessment extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax. **Three PRs** — PR1 (hook) via TDD; PR2/PR3 (components) via controller-run assertion-guarded assembly+rewire scripts (subagent edits timed out on the large calendar removal) + two-stage subagent review. **Line numbers shift after PR1 — each PR re-audits its own boundaries.**

**Goal:** Extract PlannerTab's cross-coupled lesson (~2,192 LOC) + assessment (~1,624 LOC) blocks into `PlannerLesson.jsx` + `PlannerAssessment.jsx`, after first decentralizing the shared question-editing cluster into a `useQuestionEditing` hook — behavior-preserving throughout.

**Architecture:** PR1 lifts the 4 shared QE state vars + 6 handlers into `hooks/useQuestionEditing.js`; PlannerTab calls it **once** (single instance preserves cross-mode persistence) and forwards the bundle to both components in PR2/PR3. Truly-shared App state (`lessonPlan`/`generatedAssignment`/`generatedAssessment`) stays in App.

**Tech Stack:** React 18 + Vite + Vitest + React Testing Library (`renderHook`). Frontend slice — proof = Vite build + frontend test floor + Playwright E2E + per-PR tests + normalized-JSX parity (PR2/PR3).

**Spec:** `docs/superpowers/specs/2026-05-22-plannertab-lesson-assessment-extraction-design.md`

---

## File Structure

- **Create** `frontend/src/hooks/useQuestionEditing.js` (~200 LOC) — 4 QE state vars + 6 handlers; one responsibility (question editing over the active assignment).
- **Create** `frontend/src/hooks/__tests__/useQuestionEditing.test.js` — hook unit tests.
- **Create** `frontend/src/components/PlannerLesson.jsx` (~2,100 LOC, PR2) + `frontend/src/__tests__/PlannerLesson.test.jsx`.
- **Create** `frontend/src/components/PlannerAssessment.jsx` (~1,600 LOC, PR3) + `frontend/src/__tests__/PlannerAssessment.test.jsx`.
- **Modify** `frontend/src/tabs/PlannerTab.jsx` across all 3 PRs (hook call; then two `<Planner… />` calls replacing the inline blocks).
- **Untouched:** `frontend/src/App.jsx`.

### Source regions (current line numbers @ `b9688db`; **re-verify in each PR's Task — they drift**)

| Region | Lines |
|---|---|
| QE state (editMode/selectedQuestions/editingQuestion/regeneratingQuestions) | 615–618 |
| `sectionsDropdownOpen` (assessment-only, stays until PR3) | 619 |
| 6 QE handlers | 628 (`toggleQuestionSelect`) … end of `regenerateOneQuestion` (def 756) |
| lesson block | 1251 (`{plannerMode === "lesson" && (`) → 3443 (`)}`) |
| assessment block | 3444 (`{plannerMode === "assessment" && (`) → 5068 (`)}`) |

Handler signatures (verified): `toggleQuestionSelect(qKey)`, `selectAllQuestions()`, `saveEditedQuestion(sIdx, qIdx, updatedQuestion)`, `deleteSelectedQuestions()`, `regenerateSelectedQuestions()` (async), `regenerateOneQuestion(sIdx, qIdx)` (async).

---

## PR1 — `useQuestionEditing` hook

### Task 1: Pre-flight audit (controller, read-only)

- [ ] **Step 1:** Confirm branch (impl PR1 branch off `main`).
- [ ] **Step 2:** Re-confirm the 6 handler bodies' external dependencies are exactly `{getActiveAssignment, setActiveAssignment, addToast, config, unitConfig}` + `api.regenerateQuestions` + the 4 own state setters, and that they call no other PlannerTab closures (they may call each other — fine, both in the hook):
```bash
cd /Users/alexc/Downloads/Graider/frontend/src/tabs
python3 - <<'PY'
import re
lines=open("PlannerTab.jsx",encoding="utf-8").read().split("\n")
# capture the handler region precisely: from the toggleQuestionSelect def to end of regenerateOneQuestion
start=[i for i,l in enumerate(lines,1) if re.search(r'const toggleQuestionSelect',l)][0]
# find the line of the next top-level const/function AFTER regenerateOneQuestion def
roq=[i for i,l in enumerate(lines,1) if re.search(r'const regenerateOneQuestion',l)][0]
nxt=[i for i,l in enumerate(lines,1) if i>roq and re.match(r'  (const|function|var|let) [A-Za-z]',l)][0]
body="\n".join(lines[start-1:nxt-1])
dz="\n".join(lines[30:94]); dz=re.sub(r'/\*.*?\*/','',dz,flags=re.DOTALL); dz=re.sub(r'//[^\n]*','',dz)
props={t.strip() for t in dz.replace("{","").replace("}","").split(",") if re.fullmatch(r'[A-Za-z_]\w*',t.strip())}
ids=set(re.findall(r'(?<![\w.])([A-Za-z_]\w*)(?![\w])',body))
print("props used:", sorted(p for p in props if p in ids))
print("api.*:", sorted(set(re.findall(r'\bapi\.(\w+)',body))))
PY
```
Expected: props used ⊆ the 5 inputs (plus possibly others — if any NEW prop appears, add it to the hook inputs); `api.*` = `['regenerateQuestions']`. No commit.

### Task 2: Write the failing hook test

**Files:** Create `frontend/src/hooks/__tests__/useQuestionEditing.test.js`

- [ ] **Step 1:** Write the test:
```js
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { useQuestionEditing } from '../useQuestionEditing';

vi.mock('../../services/api', () => ({
  regenerateQuestions: vi.fn().mockResolvedValue({ questions: [{ question: 'regenerated' }] }),
}));

const makeInputs = (over = {}) => ({
  getActiveAssignment: vi.fn(() => ({
    sections: [{ name: 'S1', questions: [{ question: 'q1' }, { question: 'q2' }] }],
  })),
  setActiveAssignment: vi.fn(),
  addToast: vi.fn(),
  config: { ai_model: 'gpt-4o', subject: 'Math', grade_level: '8' },
  unitConfig: {},
  globalAINotes: '',
  lessonPlan: null,
  generatedAssignment: null,
  generatedAssessment: null,
  ...over,
});

describe('useQuestionEditing', () => {
  it('initial state: editMode false, empty selection', () => {
    const { result } = renderHook(() => useQuestionEditing(makeInputs()));
    expect(result.current.editMode).toBe(false);
    expect(result.current.selectedQuestions.size).toBe(0);
  });

  it('toggleQuestionSelect toggles a key in selectedQuestions', () => {
    const { result } = renderHook(() => useQuestionEditing(makeInputs()));
    act(() => result.current.toggleQuestionSelect('0-0'));
    expect(result.current.selectedQuestions.has('0-0')).toBe(true);
    act(() => result.current.toggleQuestionSelect('0-0'));
    expect(result.current.selectedQuestions.has('0-0')).toBe(false);
  });

  it('saveEditedQuestion writes the active assignment back via setActiveAssignment', () => {
    const setActiveAssignment = vi.fn();
    const { result } = renderHook(() => useQuestionEditing(makeInputs({ setActiveAssignment })));
    act(() => result.current.saveEditedQuestion(0, 0, { question: 'edited' }));
    expect(setActiveAssignment).toHaveBeenCalled();
  });

  it('regenerateOneQuestion calls api.regenerateQuestions', async () => {
    const api = await import('../../services/api');
    const { result } = renderHook(() => useQuestionEditing(makeInputs()));
    await act(async () => { await result.current.regenerateOneQuestion(0, 0); });
    expect(api.regenerateQuestions).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2:** Run → FAIL (no module): `cd frontend && npx vitest run src/hooks/__tests__/useQuestionEditing.test.js` → cannot resolve `../useQuestionEditing`.

### Task 3: Create the hook + rewire PlannerTab

**Files:** Create `frontend/src/hooks/useQuestionEditing.js`; Modify `frontend/src/tabs/PlannerTab.jsx`

- [ ] **Step 1:** Create `frontend/src/hooks/useQuestionEditing.js`:
```js
import { useState } from "react";
import * as api from "../services/api";

export function useQuestionEditing({
  getActiveAssignment, setActiveAssignment,
  addToast, config, unitConfig,
}) {
  const [editMode, setEditMode] = useState(false);
  const [selectedQuestions, setSelectedQuestions] = useState(new Set());
  const [editingQuestion, setEditingQuestion] = useState(null); // "sIdx-qIdx" key
  const [regeneratingQuestions, setRegeneratingQuestions] = useState(new Set());

  // PASTE the 6 handler bodies VERBATIM from PlannerTab.jsx (toggleQuestionSelect,
  // selectAllQuestions, saveEditedQuestion, deleteSelectedQuestions,
  // regenerateSelectedQuestions, regenerateOneQuestion). They reference the params
  // and the 4 state vars/setters above by the same bare names — no edits to the bodies.

  return {
    editMode, setEditMode, selectedQuestions, setSelectedQuestions,
    editingQuestion, setEditingQuestion, regeneratingQuestions, setRegeneratingQuestions,
    toggleQuestionSelect, selectAllQuestions, saveEditedQuestion,
    deleteSelectedQuestions, regenerateSelectedQuestions, regenerateOneQuestion,
  };
}
```
Copy the 6 handler bodies verbatim from the current PlannerTab (the Task-1 region). Do not alter logic.

- [ ] **Step 2:** In `PlannerTab.jsx`: add `import { useQuestionEditing } from "../hooks/useQuestionEditing";`. Remove the 4 QE state decls (615–618) and the 6 handler defs (628…end of `regenerateOneQuestion`). **Keep** `sectionsDropdownOpen` (619) and `publishAssessmentHandler`. Insert the call where the state decls were:
```jsx
  const {
    editMode, setEditMode, selectedQuestions, setSelectedQuestions,
    editingQuestion, setEditingQuestion, regeneratingQuestions, setRegeneratingQuestions,
    toggleQuestionSelect, selectAllQuestions, saveEditedQuestion,
    deleteSelectedQuestions, regenerateSelectedQuestions, regenerateOneQuestion,
  } = useQuestionEditing({
    getActiveAssignment, setActiveAssignment, addToast, config, unitConfig,
    
  });
```
The lesson + assessment blocks are **untouched** (same bare names).

- [ ] **Step 3:** Run the hook test → PASS: `cd frontend && npx vitest run src/hooks/__tests__/useQuestionEditing.test.js` → 4 passed.
- [ ] **Step 4:** Build + full suite: `cd frontend && npm run build` (clean) + `npx vitest run` (all pass, count = floor + 4). If build/`X is not defined`: a handler referenced a value not in the 5 inputs — add it to the hook inputs + the call (do not guess; trace it).
- [ ] **Step 5:** Confirm removal: `grep -nE "const \[(editMode|selectedQuestions|editingQuestion|regeneratingQuestions)|const (toggleQuestionSelect|saveEditedQuestion|regenerateOneQuestion)" frontend/src/tabs/PlannerTab.jsx` → EMPTY. `grep -c "useQuestionEditing" frontend/src/tabs/PlannerTab.jsx` → 2 (import + call).
- [ ] **Step 6:** Commit (hook + test + PlannerTab); discard `backend/static` (`git restore backend/static && git clean -fd backend/static`).
- [ ] **Step 7:** Two-stage review (spec-compliance: verbatim handler move + single call + 5 inputs + blocks untouched; then code-quality). Fix findings.
- [ ] **Step 8:** Push, open PR1, watch the 9 CI checks, merge when green.

---

## PR2 — `PlannerLesson.jsx`

> Re-sync `main` (PR1 merged) and re-audit; PR1 shifted line numbers.

### Task 4: Pre-flight audit (controller)

- [ ] **Step 1:** Locate the current lesson block (`grep -n '{plannerMode === "lesson" && ('`); capture inner JSX bounds.
- [ ] **Step 2:** Exhaustive free-identifier scan of the lesson block (props + imports + parent-body `function`/`const`/`var` closures), per the dashboard-slice method. Classify each: lesson-only handler (→ move into the component), shared QE return (→ prop from the hook bundle), shared prop/handler (→ forward), import (→ import in the component). Confirm `shareWithClass`/`renderTagRow` are NOT referenced.
- [ ] **Step 3:** Confirm the lesson-only handlers (`brainstormIdeasHandler`, `generateLessonPlan`, `handleDocUpload`, `handleMatchStandards`, `removeUploadedDoc`) are referenced ONLY in the lesson block (so they can move in); capture each one's own external deps.

### Task 5: Create + test `PlannerLesson.jsx` (assembly script)

- [ ] **Step 1:** Write `frontend/src/__tests__/PlannerLesson.test.jsx` (failing) — smoke render with all props stubbed (a `makeProps` factory; the QE bundle stubbed: `toggleQuestionSelect: vi.fn()`, `selectedQuestions: new Set()`, etc.) + one focused test (e.g. a generation button click invokes the lesson-only handler / a forwarded handler). Run → FAIL.
- [ ] **Step 2:** Run a deterministic assembly script (controller): assemble `frontend/src/components/PlannerLesson.jsx` = imports (the used set, sibling `./` paths) + the moved lesson-only handlers (verbatim) + signature with the **programmatically derived** prop set + `return (` + the verbatim lesson inner JSX + `);`. Emit the prop set to a file for the rewire.
- [ ] **Step 3:** Run the new test → PASS; `npm run build` → clean.
- [ ] **Step 4:** **Free-variable scan** of `PlannerLesson.jsx`: every referenced identifier ∈ props ∪ imports ∪ locals ∪ builtins. Zero leftovers (the runtime-completeness guard). Fix by adding any missed prop.
- [ ] **Step 5:** Commit (component + test); discard `backend/static`.

### Task 6: Rewire PlannerTab (anchor script)

- [ ] **Step 1:** Add `import PlannerLesson from "../components/PlannerLesson";`.
- [ ] **Step 2:** Replace the lesson block (`{plannerMode === "lesson" && (` … `)}`) with `{plannerMode === "lesson" && (<PlannerLesson …forward the exact prop set… />)}` — props generated from the same file as the signature (signature == call site, verified equal).
- [ ] **Step 3:** Remove the moved lesson-only handler defs from PlannerTab (they live in the component now). Keep everything still used elsewhere. Remove any now-dead import.
- [ ] **Step 4:** `npm run build` clean; full suite green; **normalized-JSX parity** diff (removed lesson inner JSX vs PlannerLesson's JSX, whitespace-normalized) → zero diff. Commit; discard `backend/static`.
- [ ] **Step 5:** Two-stage review; fix findings; push; open PR2; merge when green.

---

## PR3 — `PlannerAssessment.jsx`

> Re-sync `main` (PR2 merged) and re-audit.

### Task 7: Pre-flight audit (controller)

- [ ] **Step 1:** Locate the current assessment block; capture inner JSX bounds.
- [ ] **Step 2:** Exhaustive free-identifier scan (props + imports + parent-body closures). `sectionsDropdownOpen` (+ setter) becomes **local state** in the component (not a prop). Confirm the QE bundle members used, the assessment-only props, and `publishAssessmentHandler`/`getActiveAssignment`/`setActiveAssignment` usage.

### Task 8: Create + test `PlannerAssessment.jsx` (assembly script)

- [ ] **Step 1:** Write `frontend/src/__tests__/PlannerAssessment.test.jsx` (failing) — smoke + one focused test. Run → FAIL.
- [ ] **Step 2:** Assembly script: `frontend/src/components/PlannerAssessment.jsx` = imports + `const [sectionsDropdownOpen, setSectionsDropdownOpen] = useState(false);` (moved local) + signature (programmatic prop set, minus sectionsDropdownOpen) + `return (` + verbatim assessment inner JSX + `);`. Emit prop set.
- [ ] **Step 3:** New test PASS; `npm run build` clean.
- [ ] **Step 4:** Free-variable scan → zero leftovers. Fix any miss.
- [ ] **Step 5:** Commit (component + test); discard `backend/static`.

### Task 9: Rewire PlannerTab (anchor script)

- [ ] **Step 1:** Add `import PlannerAssessment from "../components/PlannerAssessment";`.
- [ ] **Step 2:** Replace the assessment block with `{plannerMode === "assessment" && (<PlannerAssessment …exact prop set… />)}` (signature == call site).
- [ ] **Step 3:** Remove the now-moved `sectionsDropdownOpen` (619) state from PlannerTab + any now-dead import/handler.
- [ ] **Step 4:** `npm run build` clean; full suite green; normalized-JSX parity zero diff. Commit; discard `backend/static`.
- [ ] **Step 5:** Two-stage review; push; open PR3; merge when green.
- [ ] **Step 6:** Confirm end-state: `wc -l frontend/src/tabs/PlannerTab.jsx` ≈ ~1,700; PlannerTab no longer contains inline lesson/assessment JSX.

---

## Verification per PR

- `cd frontend && npx vitest run` — pass (floor + new tests).
- `cd frontend && npm run build` — clean.
- 9 CI gates green; two-stage review passed.
- PR2/PR3: normalized-JSX parity zero diff + free-variable scan zero leftovers + signature == call site.

## Risks

| Risk | Mitigation |
|---|---|
| A handler captures a value not in the 9 hook inputs | Task 1 scan; build/runtime trace in Task 3 Step 4. |
| QE state resets on mode switch | Single hook call in PlannerTab; bundle forwarded (not per-component instances). |
| Missed prop/closure in PR2/PR3 (runtime error) | Exhaustive free-id audit + free-variable scan of the new component + programmatic prop derivation (signature==call) + two-stage review. |
| Large edit times out a subagent | Controller-run assertion-guarded scripts; subagents review only. |
| Non-verbatim JSX | Whitespace-normalized parity diff per component PR. |

## Expected numbers

- PR1: PlannerTab ≈ −180; new `useQuestionEditing.js` ≈ ~200; +4 tests.
- PR2: PlannerTab ≈ −2,000; new `PlannerLesson.jsx` ≈ ~2,100.
- PR3: PlannerTab ≈ −1,500; new `PlannerAssessment.jsx` ≈ ~1,600.
- End: PlannerTab ≈ ~1,700 LOC. Cumulative Wave 3: 7,405 → ~1,700 (−77%). No `App.jsx`/backend change.
