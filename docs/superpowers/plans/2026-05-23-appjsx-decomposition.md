# App.jsx Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** De-concentrate `frontend/src/App.jsx` (7,144 LOC app shell; 153 useState / 39 useEffect / 256 handlers) by pushing single-tab state *down into its owning tab* (elimination) and lifting genuinely shared state into App-called domain hooks (relocation), behavior-preserving, in small gated PRs.

**Architecture:** Two move types, chosen per cluster by consumer count: **push-down** (single-consumer → into its tab/component) and **lift-to-hook** (2+-consumer → App-called hook). The gate is **characterization** (identical state/handler contract + exact effect timing/deps), not byte-for-byte JSX parity (which only supports pure-render slices). Each slice runs a **boundary inventory first** (consumer + free-variable + effect/ref) because render-consumer count overstates clean push-downs — effect entanglement is the gating constraint.

**Tech Stack:** React 18, Vite, Vitest + React Testing Library (`render`, `renderHook`), the repo's existing smoke/tab test suite, Playwright E2E (`health-check.spec.js`).

Spec: `docs/superpowers/specs/2026-05-23-appjsx-decomposition-design.md`.

---

## File structure

- **Create** `frontend/src/components/HelpTab.jsx` — the Help tab (own state + load effect + render), pushed down from App's inline help block. (Slice 1)
- **Create** `frontend/src/__tests__/HelpTab.test.jsx` — characterization test (once-ever fetch, render gating, search/expand). (Slice 1)
- **Modify** `frontend/src/App.jsx` — remove the help state/effect/render; render `<HelpTab .../>` unconditionally. (Slice 1) Remove the 2 clean BuilderTab state decls + their prop-pass. (Slice 2)
- **Modify** `frontend/src/tabs/BuilderTab.jsx` — declare the 2 pushed-down state vars internally; drop them from props. (Slice 2)
- **Modify** `frontend/src/__tests__/BuilderTab*.test.jsx` (or add one) — assert the 2 vars now self-managed. (Slice 2)

---

## The Gate (every slice must pass)

1. **Boundary inventory FIRST** (read-only, before any move): for each target var `v`, confirm it is referenced only by the destination unit's render AND not read/written by any App effect/handler that *stays*. Commands:
   - `grep -nE "\b(set)?v\b" frontend/src/App.jsx` — every reference.
   - Split pre-render (`awk 'NR<RETURN_LINE'`) vs render (`awk 'NR>=RETURN_LINE'`); any pre-render non-declaration ref means an effect/handler touches `v` → it is **entangled, defer it** (do not push down until its effect is untangled in a dedicated slice).
2. **Contract characterization:** the destination unit exposes identical state keys, initial values, setter/handler behavior, derived values, and observable fetch/update behavior under mocked APIs.
3. **Exact effect preservation:** effect bodies, **dependency arrays, and declaration order preserved verbatim**. Latent quirks (e.g. a dep array omitting a value it reads) are **preserved, not "fixed"** — file quirks as separate follow-ups. Place the moved hook-call / mounted component so effect execution order vs staying effects is unchanged.
4. **`renderHook` / component test** for the new unit (state transitions + effect-triggered fetches, mocked APIs / fake timers).
5. **Free-variable scan to zero** on the new/changed unit (every identifier resolves to prop/arg/import/local/builtin).
6. **Integration net:** full Vitest suite green, `npm run build` green, all 9 CI checks, Playwright E2E.
7. **JSX parity (supporting only):** for moved render blocks, a whitespace-normalized byte-for-byte diff of the moved JSX vs the original.
8. **Two-stage subagent review** per PR (spec-compliance then code-quality). Branch off freshly-merged main; re-audit boundaries (line numbers drift).

## Recipe A — push-down to a NEW component (inline render in App)

Used when the tab's render is inline in App (Help). (1) Create `components/<Tab>.jsx` importing what the block uses; (2) move the cluster's `useState` + its effect(s) + the render block in verbatim; (3) forward App-level identifiers the block references (setters/handlers it doesn't own) as props; (4) `if (activeTab !== "<id>") return null;` and render the component **unconditionally** from App (always mounted → state persists → load behavior preserved); (5) run The Gate.

## Recipe B — push-down INTO an existing tab component

Used when the tab already exists and receives the vars as props (Builder/Results/Planner/Settings). (1) Boundary-inventory each var; push only the clean ones, defer entangled ones; (2) move the `useState` declaration(s) + any exclusively-owned handlers/effects from App into the tab; (3) delete the var + setter from App's `<Tab .../>` prop-pass AND from the tab's props destructure; (4) run The Gate (free-var scan on both files; the existing tab tests as the net).

---

### Task 1 (Slice 1 / PR1): `HelpTab` push-down — Recipe A

**Files:**
- Create: `frontend/src/components/HelpTab.jsx`
- Create: `frontend/src/__tests__/HelpTab.test.jsx`
- Modify: `frontend/src/App.jsx` (remove help state lines 845–847, effect 2071–2078, render block 6210–6388; add import + `<HelpTab/>` call)

**Boundary (verified during planning):** `helpManual`/`helpSearch`/`helpExpanded` are referenced only inside the help render block + the load effect — no other App effect/handler touches them; the block also references `activeTab` (router state, stays in App → prop), `setShowTutorial`, `setTutorialStep` (tutorial state, stays in App → props), and imports `Icon`, `DOMPurify`.

- [ ] **Step 1: Write the failing characterization test.** `frontend/src/__tests__/HelpTab.test.jsx`:

```jsx
import React from 'react';
import { render, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import HelpTab from '../components/HelpTab';

beforeEach(() => {
  global.fetch = vi.fn(() => Promise.resolve({ json: () => Promise.resolve({ content: '## Manual\nhello' }) }));
});

const props = (over = {}) => ({ activeTab: 'help', setShowTutorial: vi.fn(), setTutorialStep: vi.fn(), ...over });

describe('HelpTab', () => {
  it('renders nothing when not the active tab', () => {
    const { container } = render(<HelpTab {...props({ activeTab: 'grade' })} />);
    expect(container.firstChild).toBeNull();
  });

  it('fetches the manual once ever, even across tab switches', async () => {
    const { rerender, findByText } = render(<HelpTab {...props({ activeTab: 'grade' })} />);
    expect(global.fetch).not.toHaveBeenCalled();           // inactive: no fetch
    rerender(<HelpTab {...props({ activeTab: 'help' })} />); // activate
    await findByText(/Interactive Tutorial/);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    rerender(<HelpTab {...props({ activeTab: 'grade' })} />); // switch away (stays mounted)
    rerender(<HelpTab {...props({ activeTab: 'help' })} />); // switch back
    expect(global.fetch).toHaveBeenCalledTimes(1);          // ONCE EVER — no refetch
  });
});
```

- [ ] **Step 2: Run it to verify it fails.** `cd frontend && npx vitest run src/__tests__/HelpTab.test.jsx` → FAIL (`Cannot find module '../components/HelpTab'`).

- [ ] **Step 3: Create `HelpTab.jsx` (scaffold + verbatim render move).**

```jsx
import React, { useState, useEffect } from "react";
import Icon from "./Icon";
import DOMPurify from "dompurify";

export default function HelpTab({ activeTab, setShowTutorial, setTutorialStep }) {
  const [helpManual, setHelpManual] = useState("");
  const [helpSearch, setHelpSearch] = useState("");
  const [helpExpanded, setHelpExpanded] = useState({});

  // Verbatim from App.jsx:2071-2078 — dep array [activeTab] preserved exactly (do NOT add helpManual)
  useEffect(() => {
    if (activeTab === "help" && !helpManual) {
      fetch("/api/user-manual")
        .then(r => r.json())
        .then(data => { if (data.content) setHelpManual(data.content); })
        .catch(() => {});
    }
  }, [activeTab]);

  if (activeTab !== "help") return null;

  return (
    /* PASTE the INNER JSX of App.jsx:6210-6388 verbatim:
       the `<div className="fade-in" ...> ... </div>` that was the body of
       `{activeTab === "help" && ( ... )}`. Byte-for-byte; the JSX-parity gate verifies it. */
  );
}
```

  Move the render by copying the inner `<div className="fade-in">…</div>` (App.jsx lines 6211–6387, i.e. the block body inside the `&& (` … `)}`) verbatim into the `return (…)`. It already references only: `Icon`, `DOMPurify`, the three local state vars + setters, `activeTab`, `setShowTutorial`, `setTutorialStep`.

- [ ] **Step 4: Run the test to verify it passes.** `cd frontend && npx vitest run src/__tests__/HelpTab.test.jsx` → PASS (3 tests).

- [ ] **Step 5: Free-variable scan on HelpTab.** Confirm every identifier in `HelpTab.jsx` resolves to a prop (`activeTab`/`setShowTutorial`/`setTutorialStep`), a local (`helpManual`/`helpSearch`/`helpExpanded` + setters), an import (`React`/`Icon`/`DOMPurify`), or a builtin (`fetch`). Run the repo's free-var scanner pattern over the file; expect zero unknowns.

- [ ] **Step 6: JSX parity (supporting).** Diff the moved render against the original:
  `diff <(sed -n '6211,6387p' /tmp/App.before.jsx | tr -d '[:space:]') <(awk '/return \(/{f=1;next} /^  \);/{f=0} f' frontend/src/components/HelpTab.jsx | tr -d '[:space:]')` → empty (capture `/tmp/App.before.jsx` = `git show HEAD:frontend/src/App.jsx` before editing App).

- [ ] **Step 7: Rewire App.jsx.** Delete the three `useState` (845–847), the load effect (2071–2078), and the help render block (6210–6388). Add `import HelpTab from "./components/HelpTab";`. In place of the deleted block, render unconditionally:

```jsx
<HelpTab activeTab={activeTab} setShowTutorial={setShowTutorial} setTutorialStep={setTutorialStep} />
```

  (Unconditional render — NOT `{activeTab === "help" && <HelpTab/>}` — so HelpTab stays mounted and `helpManual` persists, preserving the once-ever fetch.)

- [ ] **Step 8: Verify App still has no dangling refs.** `grep -nE "\bhelp(Manual|Search|Expanded)\b" frontend/src/App.jsx` → only none (all gone). Confirm `setShowTutorial`/`setTutorialStep`/`activeTab` still declared in App.

- [ ] **Step 9: Build + full suite + discard build artifacts.** `cd frontend && npm run build` (green); `npx vitest run` (full suite green, +3 HelpTab tests); `git checkout -- ../backend/static/ && git clean -fdq ../backend/static/`.

- [ ] **Step 10: Commit.**

```bash
git add frontend/src/components/HelpTab.jsx frontend/src/__tests__/HelpTab.test.jsx frontend/src/App.jsx
git commit -m "refactor(app): push Help tab down into HelpTab component (App.jsx decomp slice 1)"
```

- [ ] **Step 11: Two-stage review + PR + auto-merge** (spec-compliance, then code-quality). Open PR, enable `--squash --auto`.

---

### Task 2 (Slice 2 / PR2): `BuilderTab` clean-subset push-down — Recipe B

**Files:**
- Modify: `frontend/src/App.jsx` (remove decls at 1009 & 1012; remove prop-pass at 6541/6542/6551 + the `setModelAnswersLoading` pass adjacent to 6551)
- Modify: `frontend/src/tabs/BuilderTab.jsx` (declare the 2 vars internally; drop from props destructure)
- Modify/Create: `frontend/src/__tests__/BuilderTab*.test.jsx`

**Boundary (verified during planning):** Only `modelAnswersLoading` (App.jsx:1012) and `savedAssignmentsExpanded` (App.jsx:1009) are clean (render-only, no pre-render refs). The other 4 BuilderTab render-vars (`importedDoc`, `isLoadingAssignment`, `loadedAssignmentName`, `docEditorModal`) are entangled with the auto-save effect (dep array App.jsx:1828) and the doc-editor handler (App.jsx:2512–2531) — **deferred** to a later slice that untangles that effect first. Do NOT push them in this slice.

- [ ] **Step 1: Re-verify the boundary off merged main** (lines drift). For each of `modelAnswersLoading`, `savedAssignmentsExpanded`:
  `grep -nE "\b(set)?<var>\b" frontend/src/App.jsx` and confirm refs are only (a) the `const [..] = useState(..)` declaration and (b) the `<var>={<var>}` / `set<var>={set<var>}` pass to `<BuilderTab>`. Any other ref → STOP, it became entangled, re-scope.

- [ ] **Step 2: Write/extend the failing BuilderTab test.** Assert BuilderTab manages these internally (renders without the props, and the toggles work). Mock `services/api` per the existing tab-test pattern. Run → FAIL (props still required / not self-managed).

- [ ] **Step 3: Move the state into BuilderTab.** In `frontend/src/tabs/BuilderTab.jsx`, remove `savedAssignmentsExpanded`, `setSavedAssignmentsExpanded`, `modelAnswersLoading`, `setModelAnswersLoading` from the props destructure; add at the top of the component body:

```jsx
const [savedAssignmentsExpanded, setSavedAssignmentsExpanded] = useState(false);
const [modelAnswersLoading, setModelAnswersLoading] = useState(false);
```

  (Both initial values verified from App.jsx:1009–1012 — each is `useState(false)`.) **Precedent:** this exact "push state into the tab" move was already done in this codebase — see the App.jsx:1011 comment, *"gradingModesExpanded moved into tabs/GradeTab.jsx in PR 2 of the Grade tab extraction sprint."* Recipe B is the established pattern here, not a novel one.

- [ ] **Step 4: Remove from App.jsx.** Delete the two `useState` (App.jsx:1009, 1012) and the three/four prop-pass lines (`savedAssignmentsExpanded=`, `setSavedAssignmentsExpanded=`, `modelAnswersLoading=`, `setModelAnswersLoading=`) at the `<BuilderTab>` call site.

- [ ] **Step 5: Run BuilderTab test → PASS. Free-var scan** both files (App no longer references these; BuilderTab now declares them). `grep -nE "\b(set)?(modelAnswersLoading|savedAssignmentsExpanded)\b" frontend/src/App.jsx` → none.

- [ ] **Step 6: Build + full suite + discard artifacts** (as Task 1 Step 9).

- [ ] **Step 7: Commit.**

```bash
git add frontend/src/App.jsx frontend/src/tabs/BuilderTab.jsx frontend/src/__tests__/BuilderTab*.test.jsx
git commit -m "refactor(app): push 2 clean Builder state vars into BuilderTab (App.jsx decomp slice 2; 4 auto-save-entangled vars deferred)"
```

- [ ] **Step 8: Two-stage review + PR + auto-merge.**

---

## Slice 3+ (scope sketch — each gets its own plan, re-audited off merged main)

These are sketched, not detailed, because each must re-run the boundary inventory against then-current main and (for entangled clusters) carry its own untangling sub-design. They follow the Recipes + The Gate above.

- **Large push-downs (Recipe B), gated by per-var boundary inventory + effect-untangling where needed:**
  - `ResultsTab` (~23 render-sole-consumed vars), `PlannerTab` (~30), `SettingsTab` (~46). Each slice pushes only the **clean subset** first; effect-entangled vars (the dominant constraint, as Builder showed) are deferred to a sub-slice that first untangles the coupling. The largest (SettingsTab 46) will sub-slice by sub-cluster. **Expected effect-untangling targets** surfaced so far: the **auto-save effect** (App.jsx:~1752–1828, couples `assignment`/`importedDoc`/`isLoadingAssignment`/`loadedAssignmentName`) and the single **giant initial-load effect** (batch-fetches rosters/periods/support-docs/accommodations/lessons/assignments) — each domain's load must be carved out preserving which fetches fire on initial load.
- **Roster/shared lift-to-hook (Recipe: extract to `frontend/src/hooks/useRosterManagement.js`):** the ~28-var roster/SIS cluster shared across Grade/Planner/Settings/Analytics. App calls `const roster = useRosterManagement({ user, addToast, ... })` and spreads `roster.*` to consumers. Boundary fixed first by a consumer + free-var + effect inventory (it's read in the settings-load, analytics-gate, and sorted-periods effects — highest "false domain boundary" risk). Gate: `renderHook` characterization (identical returned bundle + exact effect timing/deps) + free-var + the existing tab tests. Other shared clusters (grading/results, calendar) follow the same recipe.
- **Auth-gate screen extraction (Recipe C — pure render, JSX-parity gated):** the early-return screens (`!user` login, `userApproved===null` loading, `userApproved===false` not-approved, App.jsx:~4020–4116) → an `AuthGate`/`AppRouter` component. Low-risk, any time; reuses the byte-for-byte JSX-parity gate directly.
- **Context:** considered only after the above; not committed.

---

## Self-review notes (carried from planning)

- **Render-consumer count overstates clean push-downs.** The consumer audit found ~105 single-tab render-vars (Settings 46 / Planner 30 / Results 23 / Builder 6), but the BuilderTab boundary check showed only 2/6 are clean — the rest are effect-entangled. Every push-down slice therefore runs the boundary inventory first and defers entangled vars. This is the single most important discipline in this plan.
- **The once-ever-fetch behavior** (HelpTab) is the canonical example of why push-downs render the component *unconditionally* (mounted) rather than conditionally — the characterization test asserts it explicitly.
- **Latent quirks preserved, not fixed** (HelpTab's `[activeTab]`-only dep array) — behavior-preservation first; quirks filed separately.
