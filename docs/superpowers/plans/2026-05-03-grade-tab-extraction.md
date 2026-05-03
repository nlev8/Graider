# Grade Tab Extraction Plan

> **For agentic workers:** Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to execute this plan task-by-task.

**Goal:** Move the 1,617 LOC inline Grade-tab JSX out of `frontend/src/App.jsx` into `frontend/src/tabs/GradeTab.jsx`, **and** move the 14 Grade-specific state pairs out of `App()` so state ownership decentralizes — not just JSX layout.

**Why:** Codex's 2026-05-03 re-score (8.4/10 average) flagged the single biggest remaining gap as: *"App.jsx is still 15,906 LOC. State/orchestration complexity stayed centralized even after today's 16 component extractions — extracting modals didn't move state ownership, only JSX."* This plan addresses it head-on.

**Architecture:** Hybrid presentational-then-stateful migration. PR 1 ships a presentational Grade tab (state stays in App, large prop surface). PR 2-4 progressively move state into the new component. Final state: `App()` no longer declares any Grade-specific `useState`; it just renders `<GradeTab sharedProps={...} />` for the routing case.

**Tech Stack:** React 18 + Vite + Vitest. Same pattern as today's modal extractions (#161-167) but at tab-level granularity.

---

## State taxonomy

### Grade-specific (move to GradeTab)

These 14 state pairs are referenced ONLY inside the Grade tab block (`activeTab === "grade"`). Confirmed via grep across `frontend/src/`.

| State | Decl line in App.jsx | Notes |
|---|---|---|
| `selectedFiles` / `setSelectedFiles` | 829 | File list for batch grading |
| `selectedPeriod` / `setSelectedPeriod` | 831 | Period filter dropdown |
| `gradeFilterStudent` / `setGradeFilterStudent` | 835 | Individual-student filter |
| `gradeFilterAssignment` / `setGradeFilterAssignment` | 836 | Assignment filter |
| `individualUpload` / `setIndividualUpload` | 839 | Single-file grade workflow state |
| `skipVerified` / `setSkipVerified` | 921 | Regrade-all toggle |
| `excludeGradedStudents` / `setExcludeGradedStudents` | 922 | Skip-already-graded toggle |
| `excludeApprovedStudents` / `setExcludeApprovedStudents` | 923 | Skip-already-approved toggle |
| `showActivityLog` / `setShowActivityLog` | 924 | Activity log expander |
| `savedAssignmentData` / `setSavedAssignmentData` | 1024 | Cached assignment-config map |
| `gradingModesExpanded` / `setGradingModesExpanded` | 1027 | Modes panel expand/collapse |
| `gradeAssignment` / `setGradeAssignment` | 1032 | Currently-loaded assignment config |
| `gradeImportedDoc` / `setGradeImportedDoc` | 1039 | Imported source doc for current assignment |
| (TBD: confirm during PR 2 — `logRef`) | — | The forwardRef from `ActivityLog`. Stays where the consumer is. |

### App-wide (stay in App)

| State | Why it stays |
|---|---|
| `status` / `setStatus` | Used by Results tab + Analytics tab |
| `config` | Used by every tab (theme, AI model, etc.) |
| `assignments` | Used by Builder + Planner tabs |
| `periods`, `periodStudents`, `sortedPeriods` | Used by Settings tab too |
| `theme` | App-shell |
| `addToast` | App-shell |
| `loadAssignment`, `loadPeriodStudents`, `saveAssignmentConfig` | Shared handlers — keep in App |

These are passed as **read-only props** plus a small set of action callbacks — same pattern as today's presentational modals.

---

## File Structure

- `frontend/src/tabs/GradeTab.jsx` — new file. Receives App-wide reads as props, owns its own Grade-specific state by end of PR 4.
- `frontend/src/App.jsx` — loses ~1,620 LOC of inline JSX + 14 state declarations + 14 setters. Drops to ~14,200 LOC.
- `frontend/src/__tests__/GradeTab.test.jsx` — new component test file (added in PR 1).

---

## Tasks

### Task 1: Presentational extraction (PR 1)

**Files:**
- Create: `frontend/src/tabs/GradeTab.jsx`
- Modify: `frontend/src/App.jsx:7293-8910` (replace inline JSX with `<GradeTab ... />`)

- [ ] **Step 1: Write a failing smoke test**

```jsx
// frontend/src/__tests__/GradeTab.test.jsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import GradeTab from '../tabs/GradeTab';

describe('GradeTab smoke', () => {
  it('renders without crashing with minimal props', () => {
    render(
      <GradeTab
        status={{ results: [], log: [], is_running: false }}
        config={{ ai_model: 'gpt-4o', cost_limit_per_session: 0 }}
        selectedFiles={[]}
        setSelectedFiles={() => {}}
        // ... fill in all 30+ props with stubs
      />
    );
    // First render shouldn't throw — no specific text assertion needed.
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- GradeTab`
Expected: FAIL with "Cannot find module '../tabs/GradeTab'"

- [ ] **Step 3: Create `frontend/src/tabs/GradeTab.jsx` with the lifted JSX**

Copy lines 7294-8910 from `App.jsx` (inside the `activeTab === "grade" && (` wrapper). Wrap in:
```jsx
import React from 'react';
import Icon from '../components/Icon';
import ActivityLog from '../components/ActivityLog';
// ... whatever else the JSX imports

export default function GradeTab(props) {
  // Destructure ALL closures the JSX captures. Use the survey from the
  // plan as a starting point. Build will fail fast with "X is not
  // defined" until every one is in props.
  const {
    status, config, ... ,
    selectedFiles, setSelectedFiles, ... ,
    loadAssignment, loadPeriodStudents, saveAssignmentConfig,
    addToast, theme,
  } = props;

  return (
    <div data-tutorial="grade-card" className="fade-in">
      {/* paste JSX here */}
    </div>
  );
}
```

- [ ] **Step 4: Replace inline JSX in App.jsx**

```jsx
{activeTab === "grade" && (
  <GradeTab
    status={status} setStatus={setStatus}
    config={config}
    // ... pass all 30+ props
  />
)}
```

Add import: `import GradeTab from './tabs/GradeTab';`

- [ ] **Step 5: Iteratively fix `X is not defined` errors**

Run `npm run build`. For each undefined identifier, add it to the destructure + the call site. Do NOT guess — let the build tell you what's missing.

- [ ] **Step 6: Run smoke test to verify it passes**

Run: `cd frontend && npm test -- GradeTab`
Expected: PASS.

- [ ] **Step 7: Run full suite**

Run: `cd frontend && npm test && npm run build`
Expected: 151+/151+ tests pass, build clean.

- [ ] **Step 8: Codex parity review**

Dispatch Codex on the PR. The instruction: "Verify the extracted GradeTab.jsx renders identically to the inline JSX it replaced in App.jsx (lines 7293-8910 pre-PR). The extraction is presentational only — no state ownership moves in this PR."

- [ ] **Step 9: Commit**

```
refactor: extract Grade tab JSX into tabs/GradeTab.jsx (presentational)

PR 1 of 4 in the Grade tab extraction sprint per
docs/superpowers/plans/2026-05-03-grade-tab-extraction.md.

App.jsx -1,617 LOC of inline JSX. State stays in App.jsx for now;
follow-up PRs (2-4) move state ownership.
```

### Task 2: Move toggle/filter state into GradeTab (PR 2)

Move state pairs that are pure UI toggles with no cross-tab side effect:
- `gradingModesExpanded`
- `showActivityLog`
- `skipVerified`, `excludeGradedStudents`, `excludeApprovedStudents` (the three regrade toggles)

**Step pattern (per state pair):**
1. Add `useState(...)` declaration to GradeTab with same default as App.jsx had.
2. Remove the corresponding declaration from App.jsx.
3. Remove the prop from the call site.
4. Remove the prop from the destructure.
5. Verify build + tests + smoke that the UI still works.

These five state pairs are isolated — no other tab reads them. Safe.

### Task 3: Move file/period selection state (PR 3)

- `selectedFiles`
- `selectedPeriod`
- `gradeFilterStudent`
- `gradeFilterAssignment`

These need a small handler shim because grading actually USES these values. The grading thread orchestration in App.jsx reads `selectedFiles` to know what to grade. Lift `selectedFiles` to a callback the parent reads via `onChange`, OR keep `selectedFiles` in App and only move the filters to GradeTab.

**Decision needed at PR 3 time:** which approach. Default to "filters move, selectedFiles stays" since selectedFiles is grading-orchestration state.

### Task 4: Move assignment-loaded state (PR 4)

- `gradeAssignment` / `setGradeAssignment`
- `gradeImportedDoc` / `setGradeImportedDoc`
- `individualUpload` / `setIndividualUpload`
- `savedAssignmentData` / `setSavedAssignmentData`

Same pattern as PR 2/3. By end of PR 4, App.jsx has zero Grade-specific `useState` declarations.

---

## Verification per PR

- `npm test` — all tests pass (currently 150; after PR 1 should be 151+ from new GradeTab.test.jsx)
- `npm run build` — clean
- 8 CI gates green
- Codex parity review (per-PR pattern from today's modals — `--config 'model_reasoning_effort="medium"'` causes hangs, omit it; see `feedback_codex_cli_hangs_for_repo_surveys.md`)
- Manual smoke: load `/`, switch to Grade tab, click around (file select, filter, toggle expand)

## Risks

| Risk | Mitigation |
|---|---|
| 30+ prop surface in PR 1 is unwieldy | That's the whole point — exposes the coupling. PR 2-4 reduce it. |
| State that I think is Grade-specific is actually used elsewhere | Build will fail with `X is not defined` in the OTHER tab. The plan is wrong; update it and re-run. |
| Refs (e.g. `logRef` from ActivityLog) need special handling | Use `forwardRef` if needed; precedent in `frontend/src/components/ActivityLog.jsx`. |
| Tests for the extracted component need extensive prop stubbing | Worth writing a single `makeProps()` helper in the test file to keep the boilerplate one place. |

## Numbers (expected)

- After PR 1: App.jsx -1,617 LOC. New GradeTab.jsx +1,650 LOC (with prop boilerplate). State unchanged.
- After PR 4: App.jsx -14 useState declarations (~14 more LOC). State decentralized. Codex re-score should move Architecture from 8.4 → ~8.7 and Code Quality from 8.7 → ~9.0.
