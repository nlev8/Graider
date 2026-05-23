# App.jsx Decomposition — Design

**Date:** 2026-05-23
**Status:** Design (approved in brainstorm; pending spec review)
**Topic:** Decompose `frontend/src/App.jsx` (7,144 LOC), the next concentrated-complexity Code-Quality lever.

---

## Goal

De-concentrate `frontend/src/App.jsx` — a single `function App()` (line 227) that owns **153 `useState` + 39 `useEffect` + 20 `useRef` + ~256 inner handler declarations** and prop-drills them into ~25 already-extracted components — into focused, independently-testable units, **behavior-preserving**, sliced into small PRs each gated and reviewed, on the proven cadence (brainstorm → spec → writing-plans → subagent-driven development with two-stage review + auto-merge).

This is the unanimous next lever from the 2026-05-23 post-SettingsTab 3-model re-score (Code Quality held at 8; App.jsx named the single largest remaining source file).

## Why App.jsx is different from the tab god-files

PlannerTab (7,405 → 1,453) and SettingsTab (6,534 → 1,576) were decomposed via **per-section pure-forward JSX extraction**, gated on **byte-for-byte whitespace-normalized JSX parity** — because their bulk was inline JSX inside `=== "X"` section blocks.

App.jsx is the app **shell**. Its rendering is **already delegated** to imported components (5 tabs + lazy Analytics, plus LoginScreen/StudentApp/StudentPortal/PasswordResetScreen/DistrictSetup and many modals/panels). Its bulk is **owned state + effects + handlers**, not inline JSX. Therefore:

- **The JSX-parity gate only partly applies** (only to the residual render — auth-gate screens, tab-nav, a few inline tab bodies).
- The real lever is **state-owner decomposition**, which a JSX diff cannot verify. The primary confidence signal shifts to **characterization** (the extracted unit exposes an identical state/handler contract).

This design point is **3-model reconciled** (see Provenance).

## Decomposition shape (3-model reconciled: hooks-led hybrid)

All three models ranked the tools **(a) hooks > (b) render extraction > (c) context**, with **(d) hybrid/sequenced** as the real strategy. Two distinct moves, chosen per cluster by **consumer count**:

1. **Push-down (elimination).** State/effects/handlers/render used by **exactly one** tab move **down into that tab's component** and are deleted from App. This is *true elimination*, not relocation — it directly answers the prior re-scores' "LOC relocated, not eliminated" critique.
2. **Lift-to-hook (justified relocation).** State/effects/handlers shared by **2+** tabs move into an App-called domain hook (e.g. `useRosterManagement`); App calls the hook and spreads the returned bundle to consumers, becoming a thin distributor. The owner mass shrinks; the cross-cutting data stays correctly centralized.

**Render/screen extraction (b)** is secondary — applied to the residual render mass (auth-gate screens, tab-nav) where pure-forward JSX parity still works. **Context (c)** is deferred to last (or never): converting prop-drilling to context changes re-render semantics and is the least behavior-preserving option; it is only considered if drilling remains painful after the hook/push-down passes.

## Safety gate (characterization, not JSX parity)

Because the dominant move is a state/handler relocation, each slice is gated by:

1. **Contract characterization.** The extracted unit (hook or pushed-down component) exposes an **identical contract**: same state keys, same initial values, same setter/handler behavior, same derived values, and same externally observable fetch/update behavior under mocked APIs.
2. **Exact effect preservation.** Effect bodies, **dependency arrays, and declaration order are preserved verbatim.** Latent quirks (e.g. an effect whose dep array omits a value it reads) are **preserved, not "fixed"** during extraction — behavior-preservation first; quirks filed as separate follow-ups. The hook call is placed at a position that preserves effect execution order relative to effects that remain in App.
3. **`renderHook` / component tests** for the new unit covering its state transitions and effect-triggered fetches (with mocked APIs / fake timers).
4. **Free-variable scan to zero** — the proven gate: every identifier in the moved code resolves to a prop/arg, an import, a local, or a builtin (the same scanner family used for the SettingsTab slices, adapted for hook inputs).
5. **The existing tab/smoke test suite as the integration net** + Vite build + all 9 CI checks + Playwright E2E.
6. **Referential stability** where a moved handler is consumed by a memoized child: wrap in `useCallback` only if the original already had stable identity or the child's correctness depends on it — never introduce behavior change; default is to preserve the original (re)creation semantics.
7. **JSX parity (supporting)** for any pure-render screen/tab-nav extraction slice, exactly as in the tab decompositions.

Execution mirrors the tab cadence: controller-run assertion-guarded assembly/rewire where helpful, **two-stage subagent review per PR** (spec-compliance then code-quality), each PR branched off freshly-merged main and re-auditing boundaries.

## Slice sequence

Small slices, lowest-risk-first to prove each gate before the high-value/high-risk targets — the same discipline that started the SettingsTab decomposition with the small sections, not the 2,300-line classroom.

**Audit finding (consumer classification, run during planning).** A render-prop consumer audit shows the **dominant** lever is *push-down*, not the roster hook: ~105 App state vars are the **sole render-consumer of a single tab** — SettingsTab 46, PlannerTab 30, ResultsTab 23, BuilderTab 6. These are App owning state that belongs to one feature and is merely drilled through. Pushing each cluster **down into its owning tab** genuinely *eliminates* it from the shell (cohesion: state lives with the feature). The genuinely *shared* state (roster/SIS, ~28 vars consumed by 4–5 tabs) is a smaller, separate lift-to-hook lever, sequenced after the push-down pattern is proven. **Caveat carried into every slice:** the audit classifies *render* consumers only; a push-down candidate must also be verified free of reads/writes by any App effect that *stays* (or that effect moves with it) and free of shared `useRef` — the "false domain boundary via effects/refs" trap. The boundary is fixed per slice by a consumer + free-variable + effect/ref inventory before any code moves.

- **Slice 1 — `HelpTab` push-down (detailed first PR).** Smallest, fully self-contained, single-consumer cluster (3 state vars, 1 effect, 1 render block) — proves the characterization + push-down gate on the lowest-blast-radius seam. Detailed below.
- **Slice 2 — `BuilderTab` clean-subset push-down.** The per-slice boundary inventory (run during planning) found that of BuilderTab's 6 render-sole-consumed vars, only **2 are cleanly push-downable** (`modelAnswersLoading`, `savedAssignmentsExpanded` — render-only, no staying-effect reads); the other 4 (`importedDoc`, `isLoadingAssignment`, `loadedAssignmentName`, `docEditorModal`) are **entangled with App's auto-save effect** (dep array at App.jsx:1828) and a doc-editor handler, so they are **deferred** to a later slice that first untangles that effect. Slice 2 pushes only the 2 clean vars into the existing `BuilderTab.jsx` — the minimal proof of the "push state into an existing tab" recipe (Recipe B). This is deliberately small; its purpose is to prove the recipe safely, not to maximize LOC. **Key finding it records: render-consumer count *overstates* clean push-downs — effect entanglement is the gating constraint, which is why every push-down slice runs the boundary inventory first and defers effect-entangled vars to an untangling sub-design.**
- **Slice 3+ — the large push-downs:** `ResultsTab` (~23), `PlannerTab` (~30), `SettingsTab` (~46), each its own slice (the largest may sub-slice by sub-cluster), gated by the same recipe + boundary inventory. These are where App.jsx's LOC and state count fall the most.
- **Roster/shared-state lift-to-hook:** `useRosterManagement` (~28-var roster/SIS cluster shared across Grade/Planner/Settings/Analytics, read in the settings-load, analytics-gate, and sorted-periods effects). Done after push-downs prove the gate; its cross-cutting boundary is fixed by the consumer/free-var/effect inventory first ("false domain boundaries" risk is highest here). Other shared clusters (grading/results, calendar) follow the same lift-to-hook recipe.
- **Auth-gate screen extraction** (login/loading/not-approved → an `AuthGate`/`AppRouter`, pure-render, JSX-parity-gated) — a parallel low-risk track, any time.
- **Context:** considered only after the above; not committed to in this design.

This plan details Slices 1 and 2 fully and scope-sketches Slice 3+ and the roster hook; each later slice gets its own plan, re-auditing its boundary against freshly-merged main (line numbers and consumer sets drift as prior slices land).

## Slice 1 detail: `HelpTab` push-down

**Why first:** Help is the cleanest possible proof-of-pattern. Its state is consumed by *only* the Help tab (verified: the three help state vars are read only inside the help render block; none is passed as a prop to any other component), so it is a **push-down (elimination)**, not a hook.

**What moves out of App.jsx into a new `frontend/src/components/HelpTab.jsx`:**
- State: `helpManual` (line 845), `helpSearch` (846), `helpExpanded` (847) — three `useState`.
- Effect: the user-manual fetch, `if (activeTab === "help" && !helpManual) { fetch("/api/user-manual")... }` with dep array `[activeTab]` (lines 2071–2078). **The `[activeTab]` dep reads `helpManual` but does not list it — this latent quirk is preserved verbatim.**
- Render: the `{activeTab === "help" && ( ... )}` block (lines 6210–6388, ~179 lines) and any help-only inline handlers within it.

**Behavior-preservation subtlety (decisive for the form of the move).** In the original, `helpManual` lives in App and **persists across tab switches**, so the `activeTab`-gated fetch runs **once ever** (on first open `!helpManual` is true; on every later open it is false → no refetch). A naive `{activeTab === "help" && <HelpTab />}` push-down would **unmount `HelpTab` on every switch away**, resetting its state and **refetching on every open** — a behavior change. Therefore:

**The behavior-preserving form:** App renders `<HelpTab activeTab={activeTab} />` **unconditionally** (always mounted); `HelpTab` moves the `activeTab === "help"` visibility gate and the `[activeTab]`-dep fetch effect **inside, verbatim**. Because the component stays mounted, its `helpManual` persists across tab switches and the once-ever-on-first-open lazy fetch is preserved exactly. (This mirrors how the grade tab is already kept mounted via a `display` toggle at App.jsx:6113, rather than conditionally rendered.) `activeTab` (the tab-router state, shared by every tab) stays in App and is passed as a prop.

**What stays in App.jsx:** `activeTab`; App renders `<HelpTab activeTab={activeTab} />`. `HelpTab` owns its three state vars, its load effect (now firing the first time `activeTab` becomes `"help"`, gated by `!helpManual`), and its render (hidden when `activeTab !== "help"`).

**Net:** ~190 LOC eliminated from App.jsx (genuinely removed from the shell, not relocated to an App-hook). Modest LOC; the value is proving the gate. The characterization test must assert the **once-ever fetch** explicitly (mount inactive → activate → fetch fires once → switch away → switch back → no second fetch), since that is the exact behavior the form above protects.

**Gate for Slice 1:** a `HelpTab` component test (renders, search filters, section expand/collapse, manual fetched on first mount under mocked fetch) + free-variable scan to zero + the existing suite + build + E2E + two-stage review. JSX parity is checked on the moved render block as a supporting signal.

## Risks (3-model reconciled) and detection

1. **Effect ordering / timing drift.** Moving effects into a hook/component can change their execution order relative to effects left in App (React runs effects in declaration order). *Detection:* preserve hook-call/component-mount position; compare the extracted `useEffect` order before/after; test with mocked APIs and fake timers. For push-downs, the effect runs on the child's mount — verify the trigger timing is equivalent to the original `activeTab`-gated effect.
2. **Stale closures / accidental dependency edits.** Handlers currently close over App-local state directly; moving them risks a missed dependency or an opportunistic "cleanup" that changes behavior. *Detection:* `eslint-plugin-react-hooks` exhaustive-deps; `renderHook`/component tests that update state before invoking a handler; a hard rule of **no dependency-array edits during extraction**.
3. **False domain boundaries (esp. roster/SIS).** State that looks domain-clustered may be cross-read by multiple tabs and effects (roster/SIS is read in settings-load, the analytics-gate, sorted-periods, and 5 tab consumers). *Detection:* a free-variable / consumer inventory (`grep` every read of each state var across App and all consumers) **before** fixing any hook boundary; this is a prerequisite step inside Slice 3, not an afterthought.
4. **Shared refs across clusters.** Of the 20 `useRef`s, some may be shared across what look like separate domains. *Detection:* `grep` every `.current` use of each ref to map its footprint before assigning it to a hook.
5. **The single giant initial-load effect.** App has one effect that batch-fetches many domains (rosters, periods, support-docs, accommodations, lessons, assignments). When a domain hook is extracted, its slice of that mega-effect must be carved out while preserving load behavior. *Detection:* characterize the fetch set before/after; do not change which fetches fire on initial load.

## Out of scope / recorded follow-ups

- **The `[activeTab]` dependency quirk on the help effect** — preserved, not fixed, in Slice 1; filed as a separate follow-up if it is a genuine defect.
- **Context providers** — not committed to in this design; revisited only if prop-drilling remains painful after the hook/push-down passes.
- **App.jsx module-level constants** (`TABS`, `markerLibrary`, `ASSIGNMENT_TEMPLATES`, `MODEL_COST_PER_ASSIGNMENT`, lines 69–226) — could move to a `constants`/`data` module later; not part of the state-decomposition lever.

## Provenance (3-model reconciliation)

The decomposition shape, the characterization-over-parity gate, and the "Help-first, not roster-first" slice ordering are **3-model reconciled** (Claude controller first-hand + Codex via `codex exec` + Gemini via `gemini -p`), all three verifying live code:
- **Shape — unanimous:** hooks-led (a > b > c), hybrid/sequenced (d) as the real strategy.
- **Gate — unanimous:** characterization (renderHook + identical bundle + exact effect timing/deps + free-var scan), JSX parity demoted to a supporting signal for render-only slices.
- **First slice:** Codex argued (with file:line evidence) against starting at the high-value-but-cross-cutting roster cluster, for a small self-contained seam first; reconciled to **HelpTab**, unified with Gemini's push-down principle (single-consumer state → eliminate into its tab). The planning-phase consumer audit then showed the push-down principle is the *dominant* lever (~105 single-tab state vars), reclassifying it from a warm-up to the headline; the roster/SIS lift-to-hook is a smaller, later lever, sequenced after the gate is proven.
