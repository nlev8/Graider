# PlannerTab Calendar Cluster Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the calendar cluster (~730 LOC) out of `frontend/src/tabs/PlannerTab.jsx` into a single new `frontend/src/components/PlannerCalendar.jsx`, behavior-preserving, zero logic change.

**Architecture:** Approach A (single component), matching the Wave 2 cadence. The new component owns all 15 calendar state vars, the fetch effect, and all 11 calendar helpers internally; it imports `Icon`/`HolidayModal`/`ImportEventsModal`/`api` directly. Interface is five props: `{ active, addToast, savedLessons, supportDocs, setSupportDocs }` (`supportDocs`/`setSupportDocs` are App-level shared state forwarded through — see the spec §3 correction; the initial audit missed them). The only non-verbatim change is the fetch effect, re-expressed from a `[activeTab, plannerMode]` guard to `useEffect(() => { if (active) loadCalendar(); }, [active])`, with PlannerTab passing `active={activeTab === "planner"}` and its existing conditional render handling the `plannerMode === "calendar"` half.

**Tech Stack:** React 18 + Vite + Vitest + React Testing Library. Frontend slice — no backend characterization net. Proof = Vite build + frontend test count floor + Playwright `health-check.spec.js` E2E smoke + new `PlannerCalendar.test.jsx` + normalized-JSX parity review.

**Spec:** `docs/superpowers/specs/2026-05-22-plannertab-calendar-extraction-design.md`

---

## File Structure

- **Create** `frontend/src/components/PlannerCalendar.jsx` (~700 LOC) — owns the calendar cluster end to end. Single responsibility: render and manage the planner Calendar mode.
- **Create** `frontend/src/__tests__/PlannerCalendar.test.jsx` — pins the `active`-prop fetch contract in isolation.
- **Modify** `frontend/src/tabs/PlannerTab.jsx` — remove the moved code (15 state vars, fetch effect, 11 helpers, slice comment, ~600-line JSX block); add the import and the `<PlannerCalendar … />` call. Drops 7,405 → ~6,675 LOC.
- **Untouched:** `frontend/src/App.jsx` — already passes `activeTab`, `addToast`, `savedLessons` to PlannerTab.

### Exact source regions to move (current line numbers @ branch base; **re-verify in Task 1 — they drift**)

| Region | Lines | Anchor markers |
|---|---|---|
| State vars (15) | 1142–1156 | `const [calendarData, setCalendarData] = useState(` … `const [quickAddForm, setQuickAddForm] = useState(` |
| Calendar fetch effect | 1159–1163 | comment `// Calendar fetch effect — moved from App.jsx PR 3.` |
| Calendar helpers (11) | 1173–1273 | `function loadCalendar() {` … end of `function isSchoolDay(dow) { … }` |
| Calendar JSX block | 5808–6406 | `{/* Calendar Mode */}` → `{plannerMode === "calendar" && (` → inner `<div className="fade-in">` (5810) … `</div>` (6405) → `)}` (6406); next sibling is `{/* Tools Mode */}` |
| Slice comment | 102–107 | `/* * Calendar slice — owned locally by PlannerTab (PR 3 …` |

**Stays in PlannerTab (do NOT move):** the dashboard `fetchTeacherClasses` effect at 1166–1170 (`if (plannerMode === "dashboard")`), and the mode-nav buttons (≈1293–1404) including the "Calendar" button that calls `setPlannerMode('calendar')`.

### Exact import list for the new component (verified — nothing else)

```jsx
import React, { useState, useEffect } from "react";
import Icon from "./Icon";
import HolidayModal from "./HolidayModal";
import ImportEventsModal from "./ImportEventsModal";
import * as api from "../services/api";
```

The calendar block uses only `Icon` (13×), `HolidayModal` (1×), `ImportEventsModal` (1×), and `api.{listSupportDocuments,parseDocumentForCalendar,importCalendarEvents}`. The 11 helpers use raw `fetch` (5×), not `api`. `getAuthHeaders`, `checkRequirementsMismatch`, `StandardCard`, and the other PlannerTab imports are NOT used by this cluster — do not import them.

---

## Tasks

### Task 1: Pre-flight audit (verify line refs + isolation against current HEAD)

No code change. Confirms the spec's audited facts still hold against the exact working-tree file before any move (line numbers shift if anything landed since the spec was written).

**Files:**
- Read-only: `frontend/src/tabs/PlannerTab.jsx`

- [ ] **Step 1: Confirm branch**

Run: `git branch --show-current`
Expected: `docs/plannertab-calendar-extraction`

- [ ] **Step 2: Re-confirm all 15 calendar state vars are calendar-block-only**

Run:
```bash
cd frontend/src/tabs
for v in calendarData calendarMonth calendarView selectedCalendarDate showHolidayModal holidayForm calendarDragId showImportModal importParsing importEvents importChecked importSelectedDoc importImporting editingEvent quickAddForm; do
  echo "== $v =="; grep -nE "\b${v}\b" PlannerTab.jsx
done
```
Expected: every reference to each var falls inside the calendar state block, the fetch effect, the 11 helpers, or the calendar JSX block. The only out-of-range hit is `calendarData` in the slice comment (~line 104). **If any var is referenced inside the lesson/assessment/dashboard/tools blocks, STOP — it is not calendar-only and the spec's isolation claim is broken; re-scope before proceeding.**

- [ ] **Step 3: Re-confirm all 11 helpers are calendar-cluster-only**

Run:
```bash
cd frontend/src/tabs
for fn in loadCalendar scheduleLesson unscheduleLesson addHoliday removeHoliday getCalendarDays getWeekDays getStartOfWeek isHoliday getLessonsForDate isSchoolDay; do
  echo "== $fn =="; grep -nE "\b${fn}\b" PlannerTab.jsx | grep -vE "function ${fn}"
done
```
Expected: every call site is inside the calendar JSX block (≈5808–6406) or an internal helper-to-helper call (e.g. `loadCalendar()` inside `scheduleLesson`/`unscheduleLesson`/`addHoliday`/`removeHoliday`). No call sites in other mode blocks.

- [ ] **Step 4: Capture the current exact line numbers for the move**

Run:
```bash
cd frontend/src/tabs
grep -nE "const \[calendarData, setCalendarData\] = useState|const \[quickAddForm, setQuickAddForm\] = useState|// Calendar fetch effect|function loadCalendar\(\)|function isSchoolDay\(dow\)|\{/\* Calendar Mode \*/\}|\{plannerMode === \"calendar\"|\{/\* Tools Mode \*/\}" PlannerTab.jsx
```
Record the actual line numbers for: state-block start/end, fetch-effect, helper-region start/end, and the `{/* Calendar Mode */}` → `{/* Tools Mode */}` JSX boundaries. Use these (not the spec's pre-audit numbers) for the moves in Tasks 2–3.

- [ ] **Step 5: No commit** (audit only).

---

### Task 2: Create and test `PlannerCalendar.jsx` (component exists + tested; PlannerTab still uses its inline block — temporary duplication, app still works)

**Files:**
- Create: `frontend/src/components/PlannerCalendar.jsx`
- Test: `frontend/src/__tests__/PlannerCalendar.test.jsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/__tests__/PlannerCalendar.test.jsx`:

```jsx
import React from 'react';
import { render } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PlannerCalendar from '../components/PlannerCalendar';

// PlannerCalendar calls api.* for the import flow and raw fetch for calendar
// load/CRUD. Mock both so the component renders and the fetch contract is
// observable in isolation.
vi.mock('../services/api', () => ({
  listSupportDocuments: vi.fn().mockResolvedValue({ documents: [] }),
  parseDocumentForCalendar: vi.fn().mockResolvedValue({ events: [] }),
  importCalendarEvents: vi.fn().mockResolvedValue({ status: 'imported' }),
}));

const makeProps = (overrides = {}) => ({
  active: false,
  addToast: vi.fn(),
  savedLessons: [],
  ...overrides,
});

describe('PlannerCalendar', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      json: async () => ({ scheduled_lessons: [], holidays: [], school_days: {} }),
    });
  });

  it('smoke: renders without crashing when inactive', () => {
    render(<PlannerCalendar {...makeProps({ active: false })} />);
  });

  it('active=true → fetches /api/calendar on mount', async () => {
    render(<PlannerCalendar {...makeProps({ active: true })} />);
    await Promise.resolve();
    expect(global.fetch).toHaveBeenCalledWith('/api/calendar');
  });

  it('active=false → does not fetch /api/calendar on mount', async () => {
    render(<PlannerCalendar {...makeProps({ active: false })} />);
    await Promise.resolve();
    expect(global.fetch).not.toHaveBeenCalledWith('/api/calendar');
  });
});
```

- [ ] **Step 2: Run the test → verify it FAILS**

Run: `cd frontend && npx vitest run src/__tests__/PlannerCalendar.test.jsx`
Expected: FAIL — cannot resolve `../components/PlannerCalendar` (module does not exist yet).

- [ ] **Step 3: Create `frontend/src/components/PlannerCalendar.jsx` (verbatim move + enumerated transforms)**

Create the file with this exact scaffold, then fill the three marked regions by **copying verbatim** from `PlannerTab.jsx` (use the line numbers captured in Task 1 Step 4):

```jsx
import React, { useState, useEffect } from "react";
import Icon from "./Icon";
import HolidayModal from "./HolidayModal";
import ImportEventsModal from "./ImportEventsModal";
import * as api from "../services/api";

export default function PlannerCalendar({ active, addToast, savedLessons, supportDocs, setSupportDocs }) {
  // === REGION 1: 15 calendar state vars ===
  // Copy verbatim from PlannerTab.jsx state block (spec lines 1142–1156):
  //   const [calendarData, setCalendarData] = useState({ scheduled_lessons: [], holidays: [], school_days: {} });
  //   ... through ...
  //   const [quickAddForm, setQuickAddForm] = useState({ title: "", unit: "", color: "#6366f1" });

  // === REGION 2: fetch effect (RE-EXPRESSED — the one non-verbatim change) ===
  useEffect(() => {
    if (active) loadCalendar();
  }, [active]);

  // === REGION 3: 11 calendar helpers ===
  // Copy verbatim from PlannerTab.jsx helper region (spec lines 1173–1273):
  //   function loadCalendar() { ... }
  //   async function scheduleLesson(entry) { ... }
  //   async function unscheduleLesson(entryId) { ... }
  //   async function addHoliday(holiday) { ... }
  //   async function removeHoliday(date) { ... }
  //   function getCalendarDays(month) { ... }
  //   function getWeekDays(startOfWeek) { ... }
  //   function getStartOfWeek(date) { ... }
  //   function isHoliday(dateStr) { ... }
  //   function getLessonsForDate(dateStr) { ... }
  //   function isSchoolDay(dow) { ... }

  return (
    // === REGION 4: calendar JSX ===
    // Copy verbatim the INNER block from PlannerTab.jsx — the
    // `<div className="fade-in">` ... `</div>` (spec lines 5810–6405).
    // Do NOT copy the `{plannerMode === "calendar" && (` wrapper or its `)}`.
  );
}
```

Transformation rules (the ONLY changes from verbatim):
1. The fetch effect is replaced by the `useEffect(() => { if (active) loadCalendar(); }, [active])` shown above (do **not** copy the original `if (activeTab === "planner" && plannerMode === "calendar")` effect).
2. `addToast` and `savedLessons` come from the destructured props (already in the signature) — no other change to their usage.
3. Component import paths are siblings: `Icon`/`HolidayModal`/`ImportEventsModal` from `./` (not `../components/`); `api` from `../services/api` (unchanged).
4. Everything else (all 15 states, all 11 helpers, the entire JSX inner block) is copied **byte-for-byte**.

- [ ] **Step 4: Run the new test → verify it PASSES, and build is clean**

Run: `cd frontend && npx vitest run src/__tests__/PlannerCalendar.test.jsx`
Expected: 3 passed.

Run: `cd frontend && npm run build`
Expected: build succeeds. If it fails with `X is not defined`, the JSX references an identifier not in `{ active, addToast, savedLessons, supportDocs, setSupportDocs }` or the imports. (Implementation-time audit found the original 3-prop surface missed `supportDocs`/`setSupportDocs` — App-level shared state that must be forwarded as props, not made local; see spec §3 correction.) Do not invent props; trace any further identifier back to the source, and if it is shared App state, forward it as a prop rather than localizing it.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/PlannerCalendar.jsx frontend/src/__tests__/PlannerCalendar.test.jsx
git commit -m "$(cat <<'EOF'
feat(planner): add PlannerCalendar component (calendar cluster, additive)

Verbatim move of the calendar cluster (15 state vars + fetch effect + 11
helpers + ~600-line JSX) into components/PlannerCalendar.jsx. Fetch effect
re-expressed as active-prop guard. PlannerTab still renders its inline block
(rewired in the next commit); this commit is additive so the app stays green.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Rewire PlannerTab to use PlannerCalendar; remove the inline calendar code

**Files:**
- Modify: `frontend/src/tabs/PlannerTab.jsx`

- [ ] **Step 1: Add the import**

Add to the import block at the top of `PlannerTab.jsx` (alongside the other `../components/` imports, e.g. after the `ImportEventsModal` import):

```jsx
import PlannerCalendar from "../components/PlannerCalendar";
```

- [ ] **Step 2: Replace the inline calendar JSX block with the component call**

Replace the entire calendar JSX block — from `{/* Calendar Mode */}` through its closing `)}` (spec lines 5808–6406) — with:

```jsx
                  {/* Calendar Mode */}
                  {plannerMode === "calendar" && (
                    <PlannerCalendar
                      active={activeTab === "planner"}
                      addToast={addToast}
                      savedLessons={savedLessons}
                      supportDocs={supportDocs}
                      setSupportDocs={setSupportDocs}
                    />
                  )}
```

- [ ] **Step 3: Remove the moved state, effect, helpers, and slice comment**

Delete from `PlannerTab.jsx`:
- the 15 calendar state declarations (spec 1142–1156),
- the calendar fetch effect (spec 1159–1163) — **but keep** the dashboard `fetchTeacherClasses` effect immediately below it (1166–1170),
- the 11 calendar helpers (spec 1173–1273),
- the calendar slice comment (spec 102–107).

**Do NOT remove** `supportDocs`/`setSupportDocs` from PlannerTab's prop destructuring (≈ line 53) — they are App-level shared state forwarded to `<PlannerCalendar>` above, and removing them would break the shared-doc-list contract with the Settings/Tools tab. No `App.jsx` change.

- [ ] **Step 4: Build and verify no dangling references**

Run: `cd frontend && npm run build`
Expected: build succeeds. A failure here means a moved identifier is still referenced in PlannerTab — that would contradict the Task-1 isolation audit; investigate the specific identifier rather than re-adding state.

- [ ] **Step 5: Run the existing PlannerTab tests → verify they STAY green (behavior net)**

Run: `cd frontend && npx vitest run src/__tests__/PlannerTab.test.jsx`
Expected: all pass — in particular `calendar-mode effect fires fetch /api/calendar when plannerMode=calendar` (now satisfied via PlannerTab → PlannerCalendar) and `Calendar mode button click invokes setPlannerMode("calendar")` (the button stays in PlannerTab's nav bar).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/tabs/PlannerTab.jsx
git commit -m "$(cat <<'EOF'
refactor(planner): render PlannerCalendar; remove inline calendar cluster

PlannerTab now renders <PlannerCalendar active={activeTab === "planner"} ...>
and the inline calendar state/effect/helpers/JSX are removed. ~730 LOC out of
PlannerTab.jsx (7,405 → ~6,675). Behavior-preserving; existing PlannerTab
calendar tests stay green.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Full verification + normalized-JSX parity review

**Files:**
- Read-only verification.

- [ ] **Step 1: Full frontend test suite + build**

Run: `cd frontend && npx vitest run && npm run build`
Expected: all tests pass (count = previous floor + 3 from `PlannerCalendar.test.jsx`); build clean. Confirm the count did not drop below the Frontend Build CI floor.

- [ ] **Step 2: Normalized-JSX parity review**

Confirm the moved JSX matches the pre-PR PlannerTab calendar block byte-for-byte except the enumerated transforms (effect re-expression, import paths, prop destructure). Extract the inner JSX from *both* sides and diff whitespace-normalized:
```bash
# BEFORE: the pre-rewire PlannerTab inner calendar JSX. At this point HEAD is the
# Task 3 rewire commit, so HEAD~1 is the last commit that still has the inline
# block. Use the JSX inner-block line numbers captured in Task 1 (the
# `<div className="fade-in">` ... `</div>` between `{plannerMode === "calendar" && (`
# and its closing `)}` — spec lines 5810–6405 before any drift).
git show HEAD~1:frontend/src/tabs/PlannerTab.jsx | sed -n '<JSX_START>,<JSX_END>p' > /tmp/cal_before.jsx
# AFTER: PlannerCalendar's JSX, stripped of the `return (` first line and the `);`
# last line so only the inner `<div className="fade-in">` ... `</div>` remains.
sed -n '/^  return (/,/^  );/p' frontend/src/components/PlannerCalendar.jsx | sed '1d;$d' > /tmp/cal_after.jsx
diff <(tr -d '[:space:]' < /tmp/cal_before.jsx) <(tr -d '[:space:]' < /tmp/cal_after.jsx) && echo "JSX PARITY OK (whitespace-normalized)"
```
Expected: empty diff → confirms a verbatim JSX move. (Substitute `<JSX_START>`/`<JSX_END>` with the Task-1 line numbers; if Task 4 does not run immediately after Task 3's commit, adjust the `HEAD~1` ref to the pre-rewire commit.)

- [ ] **Step 3: Manual smoke (optional but recommended)**

Start the backend per `CLAUDE.md` (venv at `/Users/alexc/Downloads/Graider/venv/`), load `/`, switch to the Planner tab → Calendar mode, confirm the month grid renders, schedule/unschedule a lesson, add/remove a holiday, and open the import modal. Behavior identical to pre-PR. **Never contact `:3000`** (legacy app).

- [ ] **Step 4: No commit** (verification only).

---

### Task 5: Land the spec + plan + implementation as one PR

**Files:**
- Already committed: spec, plan, component, test, PlannerTab edit.

- [ ] **Step 1: Confirm spec + plan are already committed**

The spec and plan were committed during the brainstorming/writing-plans phase (commits `docs(spec): …` and `docs(spec+plan): …` on this branch). Verify with `git log --oneline -5`; no new docs commit is needed here. The implementation commits from Tasks 2–3 join them on the same branch.

- [ ] **Step 2: Push and open the PR**

```bash
git push -u origin docs/plannertab-calendar-extraction
gh pr create --title "refactor(planner): extract calendar cluster into PlannerCalendar (Wave 3 slice 1)" --body "$(cat <<'EOF'
Extracts the calendar cluster (~730 LOC: 15 state vars + fetch effect + 11
helpers + ~600-line JSX) out of PlannerTab.jsx into a single new
components/PlannerCalendar.jsx. Behavior-preserving; the only non-verbatim
change is the fetch effect, re-expressed as an `active`-prop guard.

PlannerTab.jsx: 7,405 → ~6,675 LOC. Resumes the PlannerTab decomposition
cadence on the cleanest isolated cluster.

Spec: docs/superpowers/specs/2026-05-22-plannertab-calendar-extraction-design.md
Plan: docs/superpowers/plans/2026-05-22-plannertab-calendar-extraction.md

Proof: Vite build + frontend test count floor (+3 from PlannerCalendar.test.jsx)
+ Playwright health-check E2E smoke + existing PlannerTab calendar tests stay
green + normalized-JSX parity review.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Confirm the 9 CI checks pass; merge when green**

Run: `gh pr checks --watch`
Expected: all 9 required checks green (Backend Tests, Frontend Build, Frontend E2E Smoke, Migrations Smoke, Lockfile Drift, Ruff, Bandit, Secret Scan, Mypy Strict). Merge when green → Railway auto-deploys.

---

## Verification per PR

- `cd frontend && npx vitest run` — all tests pass (floor + 3).
- `cd frontend && npm run build` — clean.
- 9 CI gates green.
- Normalized-JSX parity confirmed (Task 4 Step 2).
- Manual smoke of the Planner → Calendar mode (Task 4 Step 3).

## Risks

| Risk | Mitigation |
|---|---|
| Line numbers drifted since the spec | Task 1 re-captures exact line numbers from the working tree before any move. |
| A calendar identifier is referenced outside the cluster (missed leak) | Task 1 Steps 2–3 re-run the isolation greps; build fails in Task 3 Step 4 would also surface it. |
| Fetch-effect timing diverges | The `active` prop + conditional render replicate the original `[activeTab, plannerMode]` guard (spec §6); the existing PlannerTab calendar test (Task 3 Step 5) nets it. |
| Import paths wrong (`../components/` vs `./`) | Exact import list given above; build-verified in Task 2 Step 4. |
| JSX not a true verbatim move | Whitespace-normalized parity diff in Task 4 Step 2. |

## Expected numbers

- `PlannerTab.jsx`: 7,405 → ~6,675 LOC (~730 removed).
- New `PlannerCalendar.jsx`: ~700 LOC.
- Frontend test count: +3.
- No `App.jsx` change; no backend change.
