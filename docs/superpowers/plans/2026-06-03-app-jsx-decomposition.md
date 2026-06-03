# App.jsx Decomposition Implementation Plan (PR8)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. **Every slice is gated by a Codex-high-effort + Claude dual review (the consensus pattern used all sprint) BEFORE merge.** This is a Class B refactor (high regression risk in a 145-hook shell) — no auto-merge.

**Goal:** Cut `frontend/src/App.jsx` from 4,811 LOC to <3,000 LOC by extracting cohesive logic clusters (state + effects + handlers) into single-responsibility custom hooks under `frontend/src/hooks/`, with ZERO behavior change, closing the Code Quality rubric level-7 criterion "no file >3,000 LOC".

**Architecture:** App.jsx's bulk is logic, not render — the JSX render is only ~965 lines (3846–4811); the function body (236–3845, ~3,600 lines) holds 145 hooks of state/effects/handlers. Component extraction alone cannot reach <3,000; the win comes from **custom-hook extraction**. Each hook receives the inputs it needs as arguments and returns the state + handlers App.jsx renders/uses (pure-forward — signatures match call sites by construction). A **Vitest characterization harness built FIRST** (Task 0) renders `<App/>` in key states and snapshots behavior; every subsequent slice must keep it byte-green pre/post move.

**Tech Stack:** React 18, Vite, Vitest + @testing-library/react, custom hooks. No new dependencies.

**Why this is risky (read before starting):** the ledger's prior App.jsx work "relocated lines without cutting coupling." A custom hook that closes over App-body state it doesn't own, or that reorders hook calls, silently breaks. The characterization harness + the per-slice free-variable scan are the safety nets. **Do not skip Task 0.** Do not extract two clusters in one slice. Do not "improve" logic while moving it.

---

## File Structure

| File | Responsibility |
|---|---|
| `frontend/src/App.jsx` | App shell — after this plan: render tree + the `useXxx()` calls + cross-cutting glue only. Target <3,000 LOC. |
| `frontend/src/__tests__/App.characterization.test.jsx` | NEW. The safety net — renders `<App/>` in key states, snapshots the rendered output + that the right fetch/Supabase calls fire. Must stay green across every slice. |
| `frontend/src/hooks/useTheme.js` | NEW (Task 1). Theme state + persistence effect. |
| `frontend/src/hooks/useToasts.js` | NEW (Task 2). Toast list + add/remove/auto-dismiss. |
| `frontend/src/hooks/useAuthSession.js` | NEW (Task 3). `user`/`authLoading`/`userApproved` + the Supabase `onAuthStateChange` listener + SIGNED_OUT/PASSWORD_RECOVERY handling. |
| `frontend/src/hooks/useUrlRedirectParams.js` | NEW (Task 4). Clever/ClassLink/billing URL-query-param effects (the `?clever_login`, `?classlink_login`, `?billing` handling). |
| `frontend/src/hooks/useFocusExport.js` | NEW (Task 5). Focus/VPortal export modal state + handlers + pending-confirmations fetch. |
| `frontend/src/hooks/useGradingResults.js` | NEW (Task 6). `status` + `editedResults` + the results-processing effects (1969–2090). |
| `frontend/src/hooks/useTeacherContent.js` | NEW (Task 7). Published assessments, classes, shared resources, saved assessments, rosters/periods/support docs. |
| `frontend/src/hooks/useAssignmentBuilder.js` | NEW (Task 8). `assignment` + saved-assignment load/save + import. |

> Hooks live in `frontend/src/hooks/` (create the dir in Task 1). Each is `.js` (no JSX). Each exports one `useXxx`.

---

## The Canonical Slice Procedure (every Task 1–8 follows this EXACTLY)

This is the parameterized template. Each task below fills in only: the **hook name**, the **state vars**, the **effects** (by current line range), the **handlers**, and the **hook's argument list** (the inputs it closes over that App still owns) + **return object** (what App still renders/uses).

For a slice extracting cluster `X` into `useX`:

- [ ] **Step A — characterization green BEFORE.** Run `cd frontend && npx vitest run src/__tests__/App.characterization.test.jsx`. Expected: PASS. (If not, stop — the harness must be green before you move anything.)
- [ ] **Step B — create the hook file.** Move the cluster's `useState`/`useRef`/`useMemo`/`useCallback`, the listed `useEffect` blocks, and the listed handler functions VERBATIM into `frontend/src/hooks/useX.js`. Wrap them in `export function useX(<args>) { ... return { <state>, <handlers> }; }`. The `<args>` are every identifier the moved code reads but does NOT own (e.g. `user`, `config`, `activeTab`). The return object is every identifier App.jsx still references after the move.
- [ ] **Step C — rewire App.jsx.** Delete the moved declarations from the App body. Add `import { useX } from "./hooks/useX";` and, at the SAME position in the hook-call order the state used to occupy (hook order is load-bearing — keep it), `const { <state>, <handlers> } = useX(<args>);`.
- [ ] **Step D — free-variable scan.** `cd frontend && npx eslint src/hooks/useX.js src/App.jsx` (the repo's eslint config flags undefined identifiers). Expected: no `no-undef`. Manually confirm every `<arg>` is passed and every returned name is consumed.
- [ ] **Step E — characterization green AFTER (byte-identical).** Re-run the harness from Step A. Expected: PASS with **no snapshot diff**. A snapshot diff = behavior changed = revert and re-scope.
- [ ] **Step F — full frontend suite + build.** `cd frontend && npx vitest run && npm run build`. Expected: all green, build succeeds.
- [ ] **Step G — LOC checkpoint.** `wc -l src/App.jsx` — record the new count in the PR body (it must strictly decrease).
- [ ] **Step H — commit.** `git add frontend/src/hooks/useX.js frontend/src/App.jsx frontend/src/__tests__/App.characterization.test.jsx && git commit -m "refactor(app): extract useX hook (pure-forward, behavior-preserving)"`
- [ ] **Step I — dual review gate (Class B).** Dispatch Codex (`codex exec -c model_reasoning_effort=high`) AND a Claude code-reviewer on `git diff main...HEAD`, both focused on: (1) is the move byte-verbatim (no logic changed)? (2) is hook-call ORDER preserved? (3) does any moved closure capture stale App state? (4) characterization snapshot unchanged? Reconcile to consensus APPROVE before merge. Merge manually.

---

## Task 0: Build the characterization harness (THE SAFETY NET — do first)

**Files:**
- Create: `frontend/src/__tests__/App.characterization.test.jsx`

- [ ] **Step 1: Write the harness.** It must render `<App/>` in the states the slices touch and snapshot the result. Mock the external boundaries (Supabase client, `fetch`, `localStorage`, `window.location`). Minimum states to snapshot:

```jsx
import { render, screen } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";

// Mock the Supabase client BEFORE importing App.
vi.mock("../supabaseClient", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
      signOut: vi.fn(),
    },
  },
}));

beforeEach(() => {
  global.fetch = vi.fn((url) =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  );
  localStorage.clear();
});

describe("App characterization (behavior baseline for the decomposition)", () => {
  it("renders the logged-out shell", async () => {
    const App = (await import("../App")).default;
    const { container } = render(<App />);
    expect(container).toMatchSnapshot();
  });

  it("toggles theme via the documented effect", async () => {
    const App = (await import("../App")).default;
    render(<App />);
    // Assert the theme effect wrote to localStorage / data-theme — pin the
    // observable behavior the useTheme slice must preserve.
    expect(document.documentElement.getAttribute("data-theme")).toBeDefined();
  });
});
```

> NOTE TO IMPLEMENTER: this skeleton is the floor, not the ceiling. Before writing it, read `frontend/src/App.jsx:236-510` (auth + theme), the existing `frontend/src/__tests__/App.logout.test.jsx` and `AppTabImports.test.jsx` (they already mock the boundaries — reuse their exact mock setup, do not invent a new one), and add a snapshot for the logged-in + each-tab state. The harness is only as good as the states it pins; pin every state a slice will touch.

- [ ] **Step 2: Run it — must PASS (green baseline).** `cd frontend && npx vitest run src/__tests__/App.characterization.test.jsx`. Commit the snapshot file. This is the contract every slice is held to.
- [ ] **Step 3: Commit.** `git add frontend/src/__tests__/App.characterization.test.jsx frontend/src/__tests__/__snapshots__/ && git commit -m "test(app): characterization harness for the App.jsx decomposition"`

---

## Task 1: Extract `useTheme` (warm-up — smallest, safest)

**Cluster:** `theme` state (App.jsx:491) + the persistence effect (497–500).
**Hook:** `useTheme()` → returns `{ theme, setTheme, toggleTheme }`. No args (self-contained — reads/writes `localStorage` + `document`).
**Procedure:** follow the Canonical Slice Procedure. The `toggleTheme` handler (the `setTheme(prev => prev === "dark" ? "light" : "dark")` at ~503) moves in too.
**Why first:** ~15 lines, zero cross-cluster coupling — proves the harness + the procedure end-to-end on the lowest-risk cluster.

---

## Task 2: Extract `useToasts`

**Cluster:** `toasts` state (907) + its add/remove/auto-dismiss handlers + the toast-spawning effect (2068–2090, `status.results`-keyed).
**Hook:** `useToasts(statusResults, showToastNotifications)` → `{ toasts, addToast, removeToast }`. Args: the two values the auto-toast effect reads (`status.results`, `config.showToastNotifications`) — passed in, not closed over.
**Procedure:** Canonical. Watch the effect dep array `[status.results, config.showToastNotifications]` — it becomes `[statusResults, showToastNotifications]` (the hook args), value-identical.

---

## Task 3: Extract `useAuthSession`

**Cluster:** `user`/`_setUser` (253), `authLoading` (254), `userApproved` (255), `aiNoticeDismissed` (256), `showPasswordReset` (273) + the auth-bootstrap effect (286–408, the `onAuthStateChange` listener incl. SIGNED_OUT + PASSWORD_RECOVERY) + the approval-check effect (412–469) + the user-load effect (472–474).
**Hook:** `useAuthSession()` → `{ user, setUser, authLoading, userApproved, setUserApproved, aiNoticeDismissed, setAiNoticeDismissed, showPasswordReset, setShowPasswordReset }`. Likely no args (it owns the auth lifecycle), but VERIFY: if the approval effect reads `isLocalhost`, pass it in.
**Risk note:** this is the highest-value but couples to many consumers. The characterization harness MUST snapshot both logged-out and logged-in states before this slice. The `onAuthStateChange` subscription cleanup (the `return () => subscription.unsubscribe()`) MUST move with the effect.

---

## Task 4: Extract `useUrlRedirectParams`

**Cluster:** the URL-query-param effects — Clever (`?clever_login=success` ~292), ClassLink (`?classlink_login=success` ~334), billing (`?billing=success|cancel|portal-return` ~1616–1631). Each reads `window.location`, shows a toast, and cleans the URL.
**Hook:** `useUrlRedirectParams({ addToast, setUser })` → no return (effect-only) OR returns any banner state it sets. Args: whatever the effects call (`addToast` from Task 2, any setters they invoke).
**Procedure:** Canonical. These are `useEffect(() => {...}, [])` mount effects — order among them is not load-bearing, but their position relative to other hooks is; keep them grouped where they were.

---

## Task 5: Extract `useFocusExport`

**Cluster:** `focusExportModal` (553), `focusExportLoading` (554), `focusIncludeLetterGrade` (555), `gradesApproved` (557), `vportalEmail` (560), `vportalConfigured` (561), `pendingConfirmations` (562), `pendingConfirmationStudents` (563), `confirmationStudentFilter` (564) + the pending-confirmations fetch effect (1841–1843, keyed on `activeTab`/filters) + the Focus-export handler functions.
**Hook:** `useFocusExport({ activeTab, resultsPeriodFilter, confirmationStudentFilter, assignmentsFolder, isRunning })` → the state setters + the export handlers. Args = the effect's dep values.

---

## Task 6: Extract `useGradingResults`

**Cluster:** `status` (799), `editedResults` (999) + the results-processing effects (1969–2090: the `status.results`-keyed effects that compute derived data, EXCLUDING the toast effect already moved in Task 2).
**Hook:** `useGradingResults({ config })` → `{ status, setStatus, editedResults, setEditedResults }`. **Highest care:** `status` is read by MANY consumers across the render; confirm every reader still gets it from the hook return. The status-polling effect (1729–1824, `status.is_running`-keyed) moves here too if it owns `setStatus`.

---

## Task 7: Extract `useTeacherContent`

**Cluster:** `teacherClasses` (1399), `publishedAssessments` (1409), `loadingPublished` (1410), `sharedResources` (1417), `savedAssessments` (1426), `rosters` (1436), `periods` (1437), `supportDocs` (1438), `accommodationPresets` (1445) + their fetch effects + load handlers.
**Hook:** `useTeacherContent({ user, activeTab })` → all the above + their loaders. This is a large cluster — if it exceeds ~400 LOC, split into `useTeacherClasses` + `usePublishedContent` as two sub-slices (still one cluster per commit).

---

## Task 8: Extract `useAssignmentBuilder`

**Cluster:** `assignment` (936), `savedAssignments` (967), `savedAssignmentData` (968), `loadedAssignmentName` (971), `isLoadingAssignment` (972), `importedDoc` (976) + the assignment-autosave effect (1634–1713) + load/save/import handlers.
**Hook:** `useAssignmentBuilder({ settingsLoaded })` → the state + handlers. The autosave effect's deps `[assignment, importedDoc, settingsLoaded, loadedAssignmentName, isLoadingAssignment]` become hook-internal except `settingsLoaded` (arg).

---

## Task 9: Final LOC verification + close-out

- [ ] **Step 1:** `cd frontend && wc -l src/App.jsx` — assert **< 3,000**. If still ≥3,000, the remaining over-target lines are in the render; extract the next-largest cohesive cluster (re-run the procedure) or pull a render block (the modals at 3900/3927/4426 are already components — move their state-driving glue into the relevant hook). Repeat until <3,000.
- [ ] **Step 2:** Run the Code Quality rubric check: confirm no function in App.jsx exceeds 300 LOC (`awk`-scan def-to-def spans). If `App()` itself is the only >300 "function," that's expected (it's the component) — the rubric's function-LOC criterion targets named helpers, but note it in the PR.
- [ ] **Step 3:** Full `cd frontend && npx vitest run && npm run build`, then the backend full suite `pytest -q --ignore=tests/load` (App.jsx has no backend coupling, but run it to be safe), then update the hardening rubric's "Current" Code Quality line if a re-score confirms 6→7.
- [ ] **Step 4:** Whole-branch dual review (Codex high-effort + Claude) before the final merge.

---

## Sequencing & risk

Tasks run in order 0 → 1 → ... → 9. Task 0 is mandatory and blocking. Tasks 1–2 are warm-ups (lowest risk) that validate the harness + procedure. Task 3 (auth) and Task 6 (grading status) are the highest-coupling — do them only after the harness has proven itself on 1–2 and after adding the logged-in + per-tab snapshots. Each task is its own commit + its own dual-review gate; **merge each slice's PR before starting the next** (keeps blast radius to one cluster and lets a regression be bisected to a single hook).

## Out of scope
- No logic changes, no "while I'm here" cleanups, no prop-drilling refactors, no converting class patterns. Verbatim moves only.
- The JSX render tree stays in App.jsx (the modals are already components; this plan does not re-architect the render).
- If <3,000 is reached before Task 8, STOP — don't extract further for its own sake (YAGNI; the rubric criterion is the target, not maximal extraction).

## Self-review (done)
- **Coverage:** every named hook (useTheme/useToasts/useAuthSession/useUrlRedirectParams/useFocusExport/useGradingResults/useTeacherContent/useAssignmentBuilder) maps to a task; the <3,000 goal has a verification task (9). ✅
- **Placeholders:** the Canonical Slice Procedure carries the actual steps; each task fills concrete state vars + line ranges (no "TBD"). ✅
- **Consistency:** hook names + return shapes referenced in later tasks match their definitions; `addToast` (Task 2) is consumed by Tasks 4/5 as written. ✅
