# Grade Tab Extraction Plan

> **For agentic workers:** Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to execute this plan task-by-task.

**Goal:** Move the ~1,621 LOC inline Grade-tab JSX (App.jsx lines 7293-8913) out of `frontend/src/App.jsx` into `frontend/src/tabs/GradeTab.jsx`, then progressively move 11 Grade-specific state pairs (plus delete 1 dead state pair and 1 dead portal-era branch) so state ownership decentralizes — not just JSX layout.

**Why:** Codex's 2026-05-03 re-score (8.4/10 average) flagged the single biggest remaining gap as: *"App.jsx is still 15,906 LOC. State/orchestration complexity stayed centralized even after today's 16 component extractions — extracting modals didn't move state ownership, only JSX."* This plan addresses it head-on.

**Architecture:** Hybrid presentational-then-stateful migration. PR 1 ships a presentational Grade tab (state stays in App, large prop surface). PR 2-4 progressively move state into the new component. Final state: `App()` no longer declares any Grade-specific `useState`; it just renders `<GradeTab sharedProps={...} />` for the routing case.

**Tech Stack:** React 18 + Vite + Vitest. Same pattern as today's modal extractions (#161-167) but at tab-level granularity.

---

## Codex Round 1 Review (2026-05-03) — REVISIONS

Codex round 1 (default effort) returned `REVISE_THEN_PROCEED` with 1 CRITICAL + 5 MAJOR. Folded in:

- **CRITICAL** — `savedAssignmentData` is shared across BuilderTab, ResultsTab, AnalyticsTab, and PlannerTab. Removed from Grade-specific list; stays in App.
- **MAJOR** — `gradeImportedDoc` is set but never read. Marked DELETE-DON'T-MOVE in PR 4.
- **MAJOR** — State must move as **vertical slices** with their effects/refs/handlers. Tables below tag each state.
- **MAJOR** — `selectedFiles` is part of a dead portal-era branch (see Round 2 #5 below).
- **MAJOR** — Tasks 2-4 re-sequenced.
- **MAJOR** — PR 1 test strategy expanded.

## Codex Round 6 Review (2026-05-03, high-effort) — RATIONALE ACCURACY

Round 6 caught one description-accuracy issue (no scope change):

- **MINOR** — Plan said `selectedFiles` was "only used by the estimate banner." Verified: actually used at three sites in the dead branch (checkbox state at 8163-8176, conditional subpanel rendering at 8212, estimate banner at 8899). All three are dead and get deleted; deletion scope is unchanged but rationale is now accurate.

## Codex Round 5 Review (2026-05-03, high-effort) — DOCUMENTATION CONSISTENCY

Round 5 caught two doc-consistency issues:

- **MAJOR** — State taxonomy row for `gradeFilterStudent` was not updated when Task 4 was. Row reintroduced the contradiction by stating the effect "must move with state in PR 4" while Task 4 says delete the effect. Folded in.
- **MINOR** — PR 4 verification grep omitted `stripNamePunctuation` even though Task 4 lists it for deletion. Added to the grep.

## Codex Round 4 Review (2026-05-03, high-effort) — FINAL CLEANUP

Round 4 caught two more:

- **MAJOR** — Task 4 internal contradiction: the plan said "move `gradeFilterStudent` with its App-level effect at 2089-2098" while the same effect is in the dead-branch deletion list. Verified in code (App.jsx:2089-2098): the effect only calls `loadAvailableFiles()` (the no-op). Effect is dead. Fix folded in: `gradeFilterStudent` moves as pure local state; the effect is deleted, not moved.
- **MINOR** — Task 3 needed an explicit implementation step for blob-URL cleanup on `individualUpload.preview` (not just verification text). Fix folded in: Task 3 step 4 now includes a complete `useEffect` cleanup snippet.

Round 4 also confirmed: PR sequencing remains coherent (PR 2 persistence + toggle/log → PR 3 individual-upload + period + assignment → PR 4 student-filter + dead-branch + SettingsTab). The "App.jsx has zero Grade-owned state" claim is true in the narrow `useState` sense; Grade-only handlers like `handleStartGrading` may remain in App without contradiction.

## Codex Round 3 Review (2026-05-03, high-effort) — DEAD PASS-THROUGH

Codex round 3 confirmed all prior fixes are properly applied AND found one remaining issue:

- **MAJOR** — PR 4's dead-branch deletion missed dead prop plumbing for `loadAvailableFiles` and `filesLoading`. App.jsx:9289 passes both into `<SettingsTab>`, and SettingsTab.jsx:119-120 destructures them. Without removing the pass-through, the verification grep would fail and deleting App's symbols would break the build. Folded into Task 4.

Codex Round 3 also affirmed: no other Grade-specific state missed in App.jsx:824-1050; no additional inline api.loadAssignment / api.saveAssignmentConfig calls in Grade JSX beyond 7474, 7476, 7518, 7520, 7913; always-mounted display:none has no z-index/focus/ARIA blocker (optional `hidden` + `aria-hidden` for semantic clarity); PR 1 prop surface size is acceptable for a deliberately presentational extraction.

## Codex Round 2 Review (2026-05-03, high-effort) — ADDITIONAL REVISIONS

Codex round 2 at `model_reasoning_effort="high"` returned `REVISE_THEN_PROCEED` with 1 NEW CRITICAL + 4 NEW MAJOR + 1 MINOR. Verified against the live code:

- **CRITICAL** — Tab-switch persistence breaks. Grade tab is conditionally mounted (`{activeTab === "grade" && ...}`), so any state moved into GradeTab resets every tab switch. Today the state lives in App and survives. **Fix:** Before any state moves (PR 2), convert GradeTab to always-mounted with `display:none`-style hiding — same pattern as Assistant tab at App.jsx:9306-9317. PR 1 keeps the existing conditional mount (no state moves yet, so no regression).
- **MAJOR** — `periodStudents` (App.jsx:832) is misclassified as App-wide. Verified: zero references outside `frontend/src/App.jsx`. Reclassified as Grade-specific; moves with PR 3 vertical slice.
- **MAJOR** — PR 3 vertical slice was incomplete. The `individualUpload` state is mutated by `handleIndividualFileSelect` (App.jsx:2612), reset by `clearIndividualUpload` (App.jsx:2700), and feeds `getStudentSuggestions` (App.jsx:2716). PR 3 must move all three handlers + `loadPeriodStudents` (App.jsx:2515) too, plus the inline `api.loadAssignment` async loader at App.jsx:7913.
- **MAJOR** — `savedAssignmentData` is *shared mutable state* from Grade, not read-only. Grade calls `setSavedAssignmentData` directly at App.jsx:7468 and 7516 (completion-only toggle, due-date editor) plus inline `api.loadAssignment` at 7474, 7518. **Fix:** pass `setSavedAssignmentData` as a prop to GradeTab in PR 1. Narrow callbacks (`toggleCompletionOnly`, `setAssignmentDueDate`) are a future refactor, not required for extraction.
- **MAJOR** — PR 4 cleanup is bigger than just `selectedFiles` + `gradeImportedDoc`. Verified: `setAvailableFiles` and `setFilesLoading` are never called; `loadAvailableFiles` at App.jsx:2510 is a no-op with an explicit "files come from portal submissions" comment. Also dead: the preload effect at App.jsx:2090, matching-files UI at App.jsx:8055, helper `fileMatchesPeriodStudent` at App.jsx:2534, and the `selectedFiles` estimate banner at App.jsx:8899. PR 4 deletes the entire dead portal-era file-selection branch.
- **MINOR** — PR 1 test list updated. Replaced the "assignment-filter invokes prop `loadAssignment`" test with one that mocks `../services/api` (matches actual code seam), and added a test for the completion-only toggle hitting `savedAssignmentData` + `api.loadAssignment` + `api.saveAssignmentConfig`. Deferred auto-expand/auto-scroll tests to PR 2 and individual-grade path tests to PR 3.

PR 1 (presentational extraction) is still unchanged in *scope* but its tests now match the real code seams.

---

## State taxonomy

### Grade-specific (move to GradeTab)

These state pairs are referenced ONLY inside the Grade tab. Verified by grep + semantic check (string-grep alone is insufficient — same name can recur as unrelated lexical local elsewhere; e.g. `selectedPeriod` exists in PlannerTab.jsx as a different variable, but is not the same state).

| State | Decl line in App.jsx | Tied to (must move together) |
|---|---|---|
| `selectedFiles` / `setSelectedFiles` | 829 | Part of dead portal-era file-selection branch (Round 2 #5). **PR 4 deletes the whole branch.** |
| `selectedPeriod` / `setSelectedPeriod` | 831 | Loads roster via `loadPeriodStudents` (2515); captured by `handleIndividualGrade` (2612-2717) — **PR 3 vertical slice** |
| `periodStudents` / `setPeriodStudents` | 832 | Loaded by `loadPeriodStudents`; consumed by selected-period UI (7713) and `getStudentSuggestions` (2716). Reclassified Grade-only in Round 2. — **PR 3 vertical slice** |
| `gradeFilterStudent` / `setGradeFilterStudent` | 835 | Pure UI filter. The App-level effect at 2089-2098 only calls the no-op `loadAvailableFiles()` and is part of the dead branch — **PR 4 moves the state as pure local UI; deletes the effect** (Round 4+5). |
| `gradeFilterAssignment` / `setGradeFilterAssignment` | 836 | Inline async loader uses `api.loadAssignment` at App.jsx:7913 (Round 2 #4) — that loader is part of the `gradeAssignment` slice — **PR 3** |
| `individualUpload` / `setIndividualUpload` | 839 | Mutated by `handleIndividualFileSelect` (2612), reset by `clearIndividualUpload` (2700), feeds `getStudentSuggestions` (2716), captured by `handleIndividualGrade` (2612-2717) — **PR 3 vertical slice (all 4 handlers move together)** |
| `skipVerified` / `setSkipVerified` | 921 | Pure toggle — **PR 2** |
| `excludeGradedStudents` / `setExcludeGradedStudents` | 922 | Pure toggle — **PR 2** |
| `excludeApprovedStudents` / `setExcludeApprovedStudents` | 923 | Pure toggle — **PR 2** |
| `showActivityLog` / `setShowActivityLog` | 924 | `logRef` (1729) + auto-scroll effect (2368-2371) + auto-expand-on-error effect (2373-2378) + ActivityLog ref wiring (7644-7646) — **PR 2 vertical slice, all parts move together** |
| `gradingModesExpanded` / `setGradingModesExpanded` | 1027 | Pure toggle — **PR 2** |
| `gradeAssignment` / `setGradeAssignment` | 1032 | Captured by `handleIndividualGrade` (2612-2717); inline `api.loadAssignment` at 7913 — **PR 3 vertical slice** |
| `gradeImportedDoc` / `setGradeImportedDoc` | 1039 | **DEAD** (Round 1 #2). Set at 7927-7930 but no reads anywhere. **DELETE in PR 4, do not move.** |

### App-wide (stay in App)

| State | Why it stays |
|---|---|
| `status` / `setStatus` | Used by Results tab + Analytics tab |
| `config` | Used by every tab (theme, AI model, etc.) |
| `assignments` | Used by Builder + Planner tabs |
| `periods`, `sortedPeriods` | Used by PlannerTab + AnalyticsTab. (`periodStudents` reclassified Grade-only in Round 2; AnalyticsTab uses a different variable `periodStudentMap`.) |
| `theme` | App-shell |
| `addToast` | App-shell |
| `loadAssignment`, `saveAssignmentConfig` | Shared handlers — keep in App. (`loadPeriodStudents` reclassified Grade-only in Round 2 — moves with PR 3 slice.) |
| `savedAssignmentData` / `setSavedAssignmentData` | **(Reclassified per Codex Round 1 CRITICAL.)** Shared with BuilderTab (52-57, 169, 352-357), ResultsTab (323-324, 983-985), AnalyticsTab (648, 1191-1195, 1263-1268), PlannerTab (30-35, 4687). Refreshed by App after builder saves at App.jsx:3437-3439. **Per Round 2 #4: this is shared MUTABLE state from Grade — Grade calls `setSavedAssignmentData` directly at 7468 (completion-only toggle) and 7516 (due-date editor). Pass `setSavedAssignmentData` as a prop to GradeTab.** Narrow callbacks (`toggleCompletionOnly`, `setAssignmentDueDate`) are a future cleanup. |

State props are read-only EXCEPT `setSavedAssignmentData` which Grade legitimately mutates — same pattern as today's presentational modals plus the savedAssignmentData write seam.

---

## File Structure

- `frontend/src/tabs/GradeTab.jsx` — new file. Receives App-wide reads as props, owns its own Grade-specific state by end of PR 4.
- `frontend/src/App.jsx` — loses ~1,621 LOC of inline JSX (PR 1) + 11 state declarations + 11 setters + handlers + dead-branch (PR 2-4). Drops from 15,906 → ~14,000 LOC by end of PR 4.
- `frontend/src/__tests__/GradeTab.test.jsx` — new component test file (added in PR 1, expanded in PR 2 + PR 3).

---

## Tasks

### Task 1: Presentational extraction (PR 1)

**Files:**
- Create: `frontend/src/tabs/GradeTab.jsx`
- Modify: `frontend/src/App.jsx:7293-8910` (replace inline JSX with `<GradeTab ... />`)

- [ ] **Step 1: Write failing tests (smoke + focused behavior tests)**

Per Codex Round 1 MAJOR + Round 2 MINOR: focused behavior tests on the seams most likely to silently break, matched to the actual code seams (not the seams the original plan assumed).

```jsx
// frontend/src/__tests__/GradeTab.test.jsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import GradeTab from '../tabs/GradeTab';

// Mock the api module — Grade tab calls api.loadAssignment / api.saveAssignmentConfig inline.
vi.mock('../services/api', () => ({
  loadAssignment: vi.fn().mockResolvedValue({ assignment: { title: 'Lab 1', importedDoc: null } }),
  saveAssignmentConfig: vi.fn().mockResolvedValue({}),
  // ... other api fns called from Grade as no-op mocks
}));

// Single makeProps() helper to keep boilerplate in one place — Codex risk register.
const makeProps = (overrides = {}) => ({
  status: { results: [], log: [], is_running: false, complete: false },
  config: { ai_model: 'gpt-4o', cost_limit_per_session: 0 },
  selectedFiles: [],
  setSelectedFiles: vi.fn(),
  savedAssignments: [],
  savedAssignmentData: {},
  setSavedAssignmentData: vi.fn(),
  addToast: vi.fn(),
  // ... fill in remaining props with stubs (vi.fn() for callbacks)
  ...overrides,
});

describe('GradeTab', () => {
  it('smoke: renders without crashing with minimal props', () => {
    render(<GradeTab {...makeProps()} />);
  });

  it('error-banner dismiss invokes setStatus to clear status.error', () => {
    const setStatus = vi.fn();
    render(<GradeTab {...makeProps({ status: { ...makeProps().status, error: 'boom' }, setStatus })} />);
    // Find the dismiss button on the error banner and click.
    // Verify setStatus called with an updater that clears error.
  });

  it('activity-log expander toggles showActivityLog via setShowActivityLog', () => {
    const setShowActivityLog = vi.fn();
    render(<GradeTab {...makeProps({ showActivityLog: false, setShowActivityLog })} />);
    // Click the activity-log toggle, assert setShowActivityLog called.
  });

  it('assignment-filter selection invokes api.loadAssignment and updates state', async () => {
    const api = await import('../services/api');
    const setGradeAssignment = vi.fn();
    const addToast = vi.fn();
    render(<GradeTab {...makeProps({
      savedAssignments: ['Lab 1', 'Lab 2'],
      setGradeAssignment,
      addToast,
    })} />);
    // Select 'Lab 1' in the assignment-filter dropdown; await microtasks.
    // Assert api.loadAssignment was called with 'Lab 1'.
    // Assert setGradeAssignment was called with the loaded data.
  });

  it('completion-only toggle on a saved assignment row mutates savedAssignmentData and persists via api', async () => {
    const api = await import('../services/api');
    const setSavedAssignmentData = vi.fn();
    render(<GradeTab {...makeProps({
      savedAssignments: ['Lab 1'],
      savedAssignmentData: { 'Lab 1': { completionOnly: false } },
      setSavedAssignmentData,
    })} />);
    // Click the "AI Grading" / "Completion Only" toggle on the Lab 1 row.
    // Assert setSavedAssignmentData called with an updater.
    // Await microtasks; assert api.loadAssignment + api.saveAssignmentConfig were invoked.
  });
});
```

Test seams deferred to later PRs (per Codex Round 2 MINOR):
- **PR 2:** auto-expand-on-error and auto-scroll behavior tests (ref + effects move there)
- **PR 3:** individual-grade happy/error path, file preview cleanup on clear/unmount, selected-period roster loading + suggestions
- **PR 4:** no new behavior tests if the dead file-selection branch is fully deleted

Keep assertions resilient to JSX details — use role/label queries where possible. If an assertion is brittle, downgrade to "the callback was invoked."

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

### Task 2: Always-mounted conversion + move toggle/log behavior (PR 2) — REVISED PER CODEX ROUND 2

**Step 0 (NEW — Codex Round 2 CRITICAL fix): Convert GradeTab to always-mounted before any state moves.**

The Grade tab is currently conditionally mounted at `App.jsx:7293` (`{activeTab === "grade" && <GradeTab ... />}`). Once Grade-specific state lives inside GradeTab, conditional mounting will reset that state on every tab switch. Today, the state survives tab switches because it lives in App. To preserve this behavior, switch GradeTab to display:none-style hiding — same precedent as the Assistant tab at App.jsx:9306-9317.

```jsx
// Before (PR 1):
{activeTab === "grade" && (
  <GradeTab ... />
)}

// After (PR 2 Step 0):
<div style={{ display: activeTab === "grade" ? "block" : "none" }}>
  <GradeTab ... />
</div>
```

Verify after Step 0: tab-switch state survives because GradeTab never unmounts; performance is acceptable because Grade is the most-used tab and renders are cheap when display is none (children are visible in the DOM but hidden via CSS).

**Pure toggles** (move state only; no associated effects/refs):
- `gradingModesExpanded`
- `skipVerified`
- `excludeGradedStudents`
- `excludeApprovedStudents`

**Vertical slice — `showActivityLog` + `logRef` + 2 effects + ref wiring** (Round 1 MAJOR #3): all parts move together.
- `showActivityLog` / `setShowActivityLog` (App.jsx:924)
- `logRef` (App.jsx:1729) — `forwardRef` is the right tool (Codex Round 2 confirms); the auto-scroll effect only needs the DOM node ActivityLog already forwards.
- Auto-scroll effect (App.jsx:2368-2371)
- Auto-expand-on-error effect (App.jsx:2373-2378)
- ActivityLog ref wiring (App.jsx:7644-7646)

**Step pattern (per pure-toggle pair):**
1. Add `useState(...)` declaration to GradeTab with the same default as App.jsx had.
2. Remove the declaration from App.jsx.
3. Remove the prop from the call site.
4. Remove the prop from the destructure.
5. Verify build + tests + smoke.

**Step pattern (`showActivityLog` slice):**
1. Move the `useState` + the two `useEffect` blocks + the `useRef` for `logRef` into GradeTab.
2. Update the ActivityLog ref wiring inline.
3. Remove the App-level effect/ref/state.
4. Add behavior tests for auto-expand-on-error and auto-scroll (deferred from PR 1 per Codex Round 2 MINOR).
5. Verify the activity log auto-scroll AND auto-expand-on-error still work in the running app (manual smoke required — these are timer-driven effects).

### Task 3: Move individual-upload + period + assignment-config slice (PR 3) — REVISED PER CODEX ROUND 2

Per Codex Round 2 MAJOR #3, the slice is bigger than just three state pairs and one handler. Everything that closes over `individualUpload`, `selectedPeriod`, `periodStudents`, or `gradeAssignment` must move with them.

**State pairs to move into GradeTab:**
- `selectedPeriod` / `setSelectedPeriod` (App.jsx:831)
- `periodStudents` / `setPeriodStudents` (App.jsx:832) — Round 2 reclassified Grade-only
- `individualUpload` / `setIndividualUpload` (App.jsx:839)
- `gradeFilterAssignment` / `setGradeFilterAssignment` (App.jsx:836) — coupled to assignment-filter loader
- `gradeAssignment` / `setGradeAssignment` (App.jsx:1032)

**Handlers/helpers to move into GradeTab:**
- `loadPeriodStudents` (App.jsx:2515) — populates `periodStudents` from the chosen `selectedPeriod`
- `handleIndividualFileSelect` (App.jsx:2612) — mutates `individualUpload`
- `clearIndividualUpload` (App.jsx:2700) — resets `individualUpload`
- `getStudentSuggestions` (App.jsx:2716) — reads `individualUpload` + `periodStudents`
- `handleIndividualGrade` (App.jsx:2612-2717) — captures `selectedPeriod`, `individualUpload`, `gradeAssignment`
- The assignment-filter inline async loader at App.jsx:7913 (calls `api.loadAssignment` directly, not via prop)

**App-owned dependencies (stay as props):**
- `setStatus`, `addToast`, `config` — still owned by App; passed in
- `savedAssignments`, `savedAssignmentData`, `setSavedAssignmentData` — shared mutable state from App

**Step pattern:**
1. Move the five `useState`s into GradeTab with the same defaults.
2. Move all six handlers/helpers into GradeTab; convert any captures of App-only values to prop reads.
3. Update inline `api.loadAssignment` / `api.saveAssignmentConfig` calls — they continue to use the imported `api` module (no prop needed).
4. **(NEW — Codex Round 4 MINOR)** Add an explicit `useEffect` in GradeTab to revoke the blob URL on unmount/replacement of `individualUpload.preview`:

   ```jsx
   useEffect(() => {
     // Capture the current preview URL on render. The cleanup runs on unmount
     // OR before the next effect (i.e. when individualUpload.preview changes).
     const url = individualUpload.preview;
     return () => {
       if (url && typeof url === 'string' && url.startsWith('blob:')) {
         URL.revokeObjectURL(url);
       }
     };
   }, [individualUpload.preview]);
   ```

   This is a regression risk introduced by moving `individualUpload` local — App's parent-scope state never unmounts, so blob URLs survive without explicit cleanup today. Once it's GradeTab-local AND PR 2 has converted GradeTab to always-mounted, the `useEffect` cleanup runs on every preview replacement, which is correct.

5. Remove the five `useState`s, six handlers, and any associated effects from App.jsx; remove props from the GradeTab call site and destructure.
6. Add behavior tests for: individual-grade happy-path, individual-grade error-path, file preview cleanup on `clearIndividualUpload` AND on preview replacement (the new `useEffect`), and selected-period roster loading + suggestions.
7. Verify build + tests; manual smoke an individual grading run end-to-end. Verify `URL.revokeObjectURL` cleanup happens on `individualUpload.preview` when the upload clears or replaces (Round 2 CRITICAL note + Round 4 MINOR step).

### Task 4: Delete dead portal-era branch + filter cleanup (PR 4) — REVISED PER CODEX ROUND 2

Per Codex Round 2 MAJOR #5, the cleanup is much bigger than just `selectedFiles` and `gradeImportedDoc`. The whole portal-era file-selection branch is dead code.

**Delete entirely (verified dead in Round 2):**
- `availableFiles` / `setAvailableFiles` (App.jsx:828) — `setAvailableFiles` is never called.
- `filesLoading` / `setFilesLoading` (App.jsx:830) — `setFilesLoading` is never called.
- `loadAvailableFiles` (App.jsx:2510) — explicitly a no-op with comment "files come from portal submissions".
- The preload effect at App.jsx:2090 — drives the dead branch.
- The matching-files UI at App.jsx:8055 — only renders for the dead branch.
- Helper `fileMatchesPeriodStudent` at App.jsx:2534 — only used by the dead branch.
- Helper `stripNamePunctuation` at App.jsx:2533 — only used by `fileMatchesPeriodStudent` (App.jsx-local; AnalyticsTab has its own copy).
- `selectedFiles` / `setSelectedFiles` (App.jsx:829) — used throughout the dead matching-files branch: checkbox state at App.jsx:8163-8176, conditional subpanel rendering at App.jsx:8212, and estimate banner at App.jsx:8899. All three sites are part of the dead branch and get deleted with it. (If any non-dead use survives the deletion, move that piece as local Grade UI state — but per Round 6 verification, all uses are inside the dead branch.)
- `selectedFiles` estimate banner at App.jsx:8899 — dead with the branch (one of three dead use sites).
- `gradeImportedDoc` / `setGradeImportedDoc` (App.jsx:1039) — Round 1 #2 confirmed dead. Set at 7927 but never read.

**Move into GradeTab as local UI state:**
- `gradeFilterStudent` / `setGradeFilterStudent` (App.jsx:835) — pure UI filter; **move as pure local state**. The App-level effect at 2089-2098 is part of the dead branch (it only calls the no-op `loadAvailableFiles()`) — DELETE that effect, do not move it. (Round 4 MAJOR: prior plan version contradicted itself by both moving and deleting the effect.)

**Stays in App (do not touch):**
- `savedAssignmentData` / `setSavedAssignmentData` — Round 1 CRITICAL #1: shared with 4 other tabs. Continues to be passed to GradeTab as a prop (mutable — Round 2 #4).

**Dead pass-through cleanup (Codex Round 3 MAJOR):**

`loadAvailableFiles` and `filesLoading` are also passed from App into SettingsTab:
- `App.jsx:9289` — `loadAvailableFiles={loadAvailableFiles}`, `filesLoading={filesLoading}` props on `<SettingsTab ... />`
- `tabs/SettingsTab.jsx:119-120` — destructured but unused (the no-op chain).

Both consumers are dead. PR 4 must:
1. Remove the `loadAvailableFiles` and `filesLoading` props from the `<SettingsTab>` call site at App.jsx:9289-9290.
2. Remove `loadAvailableFiles` and `filesLoading` from the destructure in `tabs/SettingsTab.jsx:119-120`.
3. Verify SettingsTab uses neither (likely zero references in the body — confirm by `grep -n 'loadAvailableFiles\|filesLoading' frontend/src/tabs/SettingsTab.jsx`).

**Verification before/after deleting each item:**

```bash
# Confirm zero remaining consumers in frontend/src/ AFTER the SettingsTab cleanup:
grep -rn 'availableFiles\|setAvailableFiles\|filesLoading\|setFilesLoading\|loadAvailableFiles\|fileMatchesPeriodStudent\|stripNamePunctuation\|gradeImportedDoc\|setGradeImportedDoc' frontend/src/
# Expected: ZERO matches in App.jsx and SettingsTab.jsx. (Before the SettingsTab cleanup you'll see hits at App.jsx:9289-9290 and SettingsTab.jsx:119-120 — those are the EXPECTED dead pass-through to remove.)
# Note: AnalyticsTab.jsx has its OWN local copy of `stripNamePunctuation` (used independently, not imported); leave that alone — only delete App.jsx's copy at App.jsx:2533.

# Confirm selectedFiles is only used in the dead branch:
grep -rn 'selectedFiles\b' frontend/src/
```

If a grep surfaces *unexpected* consumers (anything beyond the App.jsx → SettingsTab pass-through above), narrow the deletion to the verified-dead pieces only. By end of PR 4, the only Grade-specific state remaining in App.jsx is `gradeFilterStudent` (which moves) — i.e. App.jsx has zero Grade-owned state.

---

## Verification per PR

- `npm test` — all tests pass (currently 150; after PR 1 should be 155+ from new GradeTab.test.jsx with focused tests)
- `npm run build` — clean
- 8 CI gates green
- Codex parity review (per-PR pattern from today's modals — both `medium` and `high` `model_reasoning_effort` overrides cause 0-byte hangs on long prompts; omit the override entirely. See `feedback_codex_cli_hangs_for_repo_surveys.md`)
- Manual smoke: load `/`, switch to Grade tab, click around (file select, filter, toggle expand)

## Risks

| Risk | Mitigation |
|---|---|
| 30+ prop surface in PR 1 is unwieldy | That's the whole point — exposes the coupling. PR 2-4 reduce it. |
| State that I think is Grade-specific is actually used elsewhere | Build will fail with `X is not defined` in the OTHER tab. The plan is wrong; update it and re-run. Codex round 1+2 already audited; semantic-grep verified. |
| **Tab-switch state reset (Codex Round 2 CRITICAL)** | PR 2 Step 0 converts GradeTab to always-mounted display:none, mirroring Assistant tab. State persistence preserved before any state moves. |
| Refs (e.g. `logRef` from ActivityLog) need special handling | Use `forwardRef`; precedent in `frontend/src/components/ActivityLog.jsx`. Codex Round 2 confirms this is correct for PR 2. |
| `URL.revokeObjectURL` for `individualUpload.preview` blob URL | PR 3 must add explicit cleanup on `clearIndividualUpload` and on unmount. App's current parent-scope state never unmounts, so this is a regression risk introduced when individualUpload becomes local. |
| `savedAssignmentData` mutated from Grade and 4 other tabs simultaneously | PR 1 passes `setSavedAssignmentData` directly. Future cleanup: replace with narrow callbacks (`toggleCompletionOnly`, `setAssignmentDueDate`) for clearer mutation contract. |
| Tests for the extracted component need extensive prop stubbing | Single `makeProps()` helper plus `vi.mock('../services/api')` for the inline api calls. |

## Numbers (expected)

- After PR 1: App.jsx -1,621 LOC of inline JSX (lines 7293-8913). New GradeTab.jsx +1,650 LOC (with prop boilerplate). State unchanged.
- After PR 2: App.jsx -4 toggle useStates -1 vertical slice (state + ref + 2 effects + ref wiring) ≈ -10 LOC + cleaner shape. Mount strategy is now always-mounted (Step 0).
- After PR 3: App.jsx -5 useStates -6 handlers + roster-loading subsystem ≈ -200+ LOC. State for individual-grade lives entirely in GradeTab.
- After PR 4: App.jsx -dead-branch ≈ -100+ LOC (file-selection state, `loadAvailableFiles`, preload effect, matching-files UI, `fileMatchesPeriodStudent`, banner). After this PR, App.jsx has zero Grade-owned state.
- Codex re-score expected: Architecture 8.4 → ~8.7, Code Quality 8.7 → ~9.0.
