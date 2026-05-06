# Settings Tab Extraction — Spec

> **Status:** DRAFT — pending Codex high-effort review round 1.
> **Goal author:** Claude Opus 4.7 (1M context).
> **Date:** 2026-05-06.
> **Prior precedent:** `docs/superpowers/plans/2026-05-04-planner-tab-extraction.md` (18 PRs, ~5x Grade tab scale).

---

## TL;DR

`frontend/src/tabs/SettingsTab.jsx` is **6,534 LOC** with **~115 props** flowing in from `App.jsx`. This is the largest remaining state-concentration site after the Planner-tab extraction sprint completed (#157-207). It's the Codex-flagged "single biggest remaining gap to next +0.5" from the 2026-05-05 re-score (8.6/10).

This spec proposes extracting the file's seven internal sub-tabs into independent components AND moving their state ownership into the new components — the "true domain boundaries" Codex specifically called for, NOT another round of "relocation of large blocks."

Estimated: **~10-12 PRs over 2-3 weeks**. First PR is a presentational `BillingSection` proof-of-concept (~245 LOC, smallest sub-tab) to validate the pattern before scaling up.

---

## 1. Why

The 2026-05-05 Codex re-score (`project_codex_rescore_2026-05-05.md`) said:

> **Single biggest gap:** Remaining monolith concentration — PlannerTab.jsx (7,405 LOC), SettingsTab.jsx (6,531), backend/routes/planner_routes.py (6,050).
> **Next track:** true boundary split with state/API ownership pushed into smaller domain modules, **NOT more relocation of large blocks.** App.jsx reductions vs PlannerTab.jsx growth show the limit of "extract big blocks into one file" as a strategy.

In other words: the Planner-tab extraction reduced App.jsx LOC but did NOT reduce the prop count or the state-concentration problem (the 124-prop `<PlannerTab>` is the symptom). For SettingsTab, we need to do better — extract sub-tabs **with** their owned state.

Plus: SettingsTab is a SIS-touching surface (the `classroom` sub-tab at lines 1700-4001 is the Clever/OneRoster/ClassLink/LTI/roster/accommodations panel). Per `feedback_codex_always_high_effort.md` and the SIS-sprint lessons learned, every state move in this surface needs a Codex high-effort gate review.

## 2. Current State Landscape

### LOC + props
- `frontend/src/tabs/SettingsTab.jsx`: 6,534 LOC, ~115 props.
- Props are passed through `<SettingsTab .../>` invocation in `App.jsx`.
- All state for SettingsTab currently lives in `App.jsx` and is lifted as props.

### Internal sub-tab boundaries (verified by `settingsTab === '...'` grep)

| Sub-tab | Lines | LOC | Notes |
|---------|-------|-----|-------|
| `general` | 295-666 | ~370 | App-wide config, period management, basics |
| `grading` | 667-918 | ~250 | Grading style, defaults, calibration |
| `ai` | 919-1699 | ~780 | AI provider keys, model selection, global AI notes |
| `classroom` | 1700-4001 | **~2,300** | Clever/OneRoster/ClassLink/LTI/roster/accommodations (SIS surface) |
| `privacy` | 4002-5032 | ~1,030 | FERPA settings, data deletion, audit log access, district admin |
| `billing` | 5033-5276 | ~245 | Stripe subscription, usage stats |
| `resources` | 5277-end | ~1,250 | Saved resources (assets), generation history |

Plus ~290 LOC of boilerplate: imports, function signature, prop list, top-level API hookups.

### Cross-tab state dependency map

States that SettingsTab consumes but are also used by other tabs (these MUST stay in App.jsx and be lifted):
- `config` (app-wide)
- `rubric` (Settings + Grade)
- `globalAINotes` (Settings + Grade + Builder)
- `apiKeys` / `showApiKeys` / `savingApiKeys` (Settings + Builder for usage)
- `costSummary` (Settings + global cost-tracker UI)
- `subscription` (Settings + global gating)
- `periods` (Settings + Planner uses)
- (Estimate: ~30 truly-shared states.)

States that are SettingsTab-only (these are candidates to move with their sub-tab):
- All `cleverSyncResult`, `cleverSelectedSections`, `cleverSelected*` (classroom sub-tab)
- All `oneRosterConfig`, `oneRosterSyncResult` (classroom sub-tab)
- All `classlinkConfig`, `classlinkSession` (classroom sub-tab)
- All `ltiConfig`, `ltiContexts` (classroom sub-tab)
- `expandedPeriod`, `expandedStudents`, `loadingExpandedStudents`, `newPeriodName`, `uploadingPeriod`, `newStudent`, `addingStudent`, `editingStudentId`, `editStudentData` (classroom sub-tab — period/roster admin)
- `adminStatus`, `adminClaimCode` (privacy sub-tab — district admin)
- (Estimate: ~85 SettingsTab-only states; needs hard verification per `feedback_phantom_id_after_state_move.md`.)

## 3. Architecture decision: Path A vs Path B

### Path A — Sub-tab extraction (Planner-style, "relocation of large blocks")

Extract each of the 7 sub-tabs as a separate React component. State stays in App.jsx, lifted as props to each sub-tab component. SettingsTab.jsx becomes a thin shell that routes to the active sub-tab.

**Outcome:** SettingsTab.jsx shrinks to ~500 LOC. 7 new files at 250-2,300 LOC each. App.jsx prop count to SettingsTab DROPS (~115 → ~30) only because the props are now flowing to the sub-tab components instead. **The total prop-passing burden is unchanged**; it's just spread across more component boundaries.

**Effort:** ~7 PRs. Mechanical. Low per-PR risk.

### Path B — State-owning extraction (Codex-recommended, "true domain boundaries")

Extract each sub-tab as a component that owns its own state. Use domain hooks (`useGeneralSettings`, `useClassroomRoster`, `useBillingState`, etc.) to encapsulate state + API calls + side effects per domain. App.jsx loses ownership of all SettingsTab-only states.

**Outcome:** SettingsTab.jsx shrinks to ~500 LOC. 7 new sub-tab files at 250-2,300 LOC each AS WELL AS 7-10 new domain hook files. App.jsx prop count to SettingsTab drops to ~30 (truly-shared only). Total App.jsx state declarations drop by ~85 (the SettingsTab-only states move out).

**Effort:** ~10-12 PRs. Per PR: extract sub-tab JSX (Path A) + extract its state into a hook + update consumers in same PR. Higher per-PR Codex-review surface (state moves trigger phantom-id risk per `feedback_phantom_id_after_state_move.md`).

### Recommendation: Path B

The whole point of Codex's "next track" feedback was that Path A doesn't move the needle on state concentration. Path A is purely cosmetic; Path B addresses the actual architectural debt.

The risk premium of Path B (state moves) is real but the project has a working playbook for it: aggressive Codex high-effort gate review on every state-move PR (which Round-1 of the SIS sprint and the Planner phantom-id memory both confirmed catches real bugs).

## 4. Extraction order

Smallest first to validate the pattern, then bigger:

| PR | Sub-tab | LOC | Domain hooks introduced | Notes |
|----|---------|-----|------------------------|-------|
| 1 | `billing` | ~245 | `useBillingState` (subscription + cost summary) | Smallest, fewest dependencies. PoC. |
| 2 | `grading` | ~250 | (none — uses shared `rubric`/`config`) | Clean second; no SettingsTab-only state. |
| 3 | `general` | ~370 | `usePeriodManagement` (period CRUD shared with Planner; partial extraction only) | Carefully scope — `periods` is shared. |
| 4 | `ai` | ~780 | `useApiKeysState` (apiKeys + showApiKeys + savingApiKeys) | API keys are also used outside Settings; partial scope. |
| 5 | `resources` | ~1,250 | `useResourcesState` (saved resources list, filters) | Self-contained domain. |
| 6 | `privacy` | ~1,030 | `useDistrictAdminState` (admin status, invite codes), `useDataDeletionState` | District admin is its own module. |
| 7-10 | `classroom` | ~2,300 (split into 4 PRs) | `useCleverIntegration`, `useOneRosterIntegration`, `useClassLinkIntegration`, `useLTIIntegration` | SIS surface. Each integration its own PR. **CODEX HIGH-EFFORT GATE MANDATORY per SIS-CONTRACT class.** |
| 11 | Final cleanup | — | — | Delete unused props, verify SettingsTab.jsx final size + App.jsx final state count, write changelog. |

Per-PR scope ceiling: **<400 LOC delta** in SettingsTab + extracted file combined (excluding new test code). Per `feedback_phantom_id_after_state_move.md`, smaller is safer for state moves.

## 5. State taxonomy (rough first cut — to be hardened by Codex review round 1)

### Truly shared (STAY in App.jsx, lift as props)
Estimated ~30 pairs. Examples:
- `config` / `setConfig`
- `rubric` / `setRubric`
- `globalAINotes` / `setGlobalAINotes`
- `apiKeys` / `setApiKeys` / `showApiKeys` / `setShowApiKeys` / `savingApiKeys` / `setSavingApiKeys`
- `costSummary` / `setCostSummary`
- `subscription` / `setSubscription` / `subscriptionLoading` / `setSubscriptionLoading`
- `periods` / `setPeriods` (also Planner)
- `rosters` / `setRosters` (also Grade)
- (Codex round 1 will need to grep all consumers to harden this list — the Planner sprint over-classified 12 as "shared" that turned out to be Planner-only helpers living outside the JSX block; same risk applies here.)

### SettingsTab-only (MOVE to extracted sub-tabs with their domain hooks)
Estimated ~85 pairs. Examples (by sub-tab):
- **billing:** `subscription`, `subscriptionLoading` (also app-wide gates → review for shared status)
- **classroom:** `cleverSyncResult`, `cleverSelectedSections`, all OneRoster, ClassLink, LTI states
- **classroom (period mgmt):** `expandedPeriod`, `expandedStudents`, `loadingExpandedStudents`, `newPeriodName`, etc.
- **privacy (district admin):** `adminStatus`, `adminClaimCode`, etc.

The Planner-extraction memory (`feedback_phantom_id_after_state_move.md`) flagged 4/13 PRs that had phantom-id bugs after state moves. Apply the same diligence: grep ALL setter call sites + globally-rendered modals + App-level helpers passed as props before each PR.

## 6. Codex review schedule

Per `feedback_codex_always_high_effort.md`, all reviews high-effort.

| Stage | Review | Required |
|-------|--------|----------|
| This spec | Round 1 review (high-effort) | YES — before any code |
| Each PR | Per-commit gate review (high-effort) | YES |
| PR 1 (billing PoC) | Pattern-validation review | YES — extra scrutiny |
| PRs 7-10 (classroom SIS) | SIS-CONTRACT class gate review | YES — strictest tier |
| Sprint end | Whole-repo verification audit | YES — same pattern as SIS post-sprint audit |

## 7. Risk inventory

1. **Phantom-id bugs after state moves** — primary risk class. Codex caught 4/13 in Planner sprint. Apply: per-PR semantic verification, grep ALL setters + modals + helpers.
2. **Cross-cutting state misclassification** — over-classifying "shared" or "SettingsTab-only" produces broken extractions. Codex round 1 will reclassify; expect ~10-15% reclassification per Planner-sprint precedent.
3. **SIS regression in classroom sub-tab** — classroom (PRs 7-10) touches Clever/OneRoster/ClassLink/LTI flows. Any regression there is a compliance issue. Required: SIS-CONTRACT class review, full SIS test suite green per PR.
4. **Build-time JSX errors during extraction** — `<SubTab .../>` invocation must match prop signature. Risk: typo in prop name = silent undefined. Mitigation: TypeScript-style runtime PropTypes check or use Vitest snapshot in CI.
5. **Performance regression** — domain hooks may re-render more frequently than App-level state if not memoized. Mitigation: profile each PR with React DevTools Profiler; require explicit `useMemo`/`useCallback` for non-trivial computations.
6. **Test coverage drift** — extracted components need their own tests; deleted code coverage shouldn't be lost. Mitigation: per-PR test plan must include a `pytest tests/test_settings_routes_coverage.py` run.

## 8. Success metrics

By end of sprint:
- `frontend/src/tabs/SettingsTab.jsx`: < 600 LOC (was 6,534)
- App.jsx prop count to SettingsTab: < 30 (was ~115)
- App.jsx total `useState` declarations: ↓ ~85 (the SettingsTab-only states moved out)
- New domain hook files: 7-10
- New sub-tab component files: 7
- All sub-tab components individually < 1,500 LOC
- Codex high-effort gate review APPROVE on every PR
- Whole-repo Codex audit: no new findings vs. pre-sprint baseline
- Healthz: no degradation across the sprint
- Test count: net ↑ (extracted components have new tests; old SettingsTab tests preserved)

## 9. Out of scope

- Backend `planner_routes.py` (6,050 LOC) refactor — separate sprint candidate B.
- Visual redesign of the Settings UI — refactor only, no UX changes.
- New SIS integrations or compliance items — sprint #208-214 already closed audit findings.
- Migrating to TypeScript — separate strategic decision.
- Adopting Zustand/Redux/etc. — keep current state-management primitives (useState + lift to App.jsx for shared, custom hooks for owned state).

## 10. Open questions for Codex review

1. Is Path B truly the right call vs. Path A given the state-move risk premium? Or should we do a Path-A first pass for safety and a Path-B cleanup pass later?
2. Does the proposed extraction order (smallest first) give us enough early signal, or should we tackle a medium-complexity sub-tab earlier (e.g., `general` at PR 2 instead of `grading`)?
3. Are domain hooks the right abstraction, or should we instead use Context API for cross-component state within a sub-tab (e.g., `<ClassroomProvider>` wrapping the classroom sub-tab)?
4. What's the right per-PR LOC ceiling? 400 feels right based on Planner-sprint precedent, but classroom sub-tab is so big (~2,300 LOC across 4 PRs) that the per-PR delta will average ~575 LOC just for the JSX move.
5. Should test coverage for the extracted components be required upfront (TDD) or can it follow per the project's incremental testing approach?

---

## Appendix A — Per-PR PR template

```
PR Title: refactor(settings): extract <sub-tab> sub-tab + <hook-name> domain hook

Body:

## What
- Move SettingsTab.jsx lines L-M (sub-tab `<sub-tab>`) into frontend/src/tabs/SettingsTab/<SubTabName>.jsx
- Extract state ownership for <list states> into frontend/src/hooks/<hook-name>.js
- Update App.jsx to remove now-orphaned state declarations

## Why
- Per docs/superpowers/specs/2026-05-06-settings-tab-extraction.md PR <N>

## Validation
- [ ] No new App.jsx prop is passed to <SubTabName>
- [ ] All <list states> setter call sites updated to use new hook
- [ ] grep verification: no surviving `setX(...)` reference in App.jsx for any moved state
- [ ] Per-component snapshot test added/updated
- [ ] Codex high-effort gate review APPROVE
```

## Appendix B — Codex review prompt template (for each PR)

```
SETTINGS-TAB-EXTRACTION class high-effort gate review of PR #<N> (commit <SHA>).

Context:
- Spec: docs/superpowers/specs/2026-05-06-settings-tab-extraction.md
- Prior PRs in sprint: <list>

What this PR does:
- <description>

Review goals:
1. Did the PR move ALL setter call sites for the listed states? (grep verify)
2. Are there phantom-id bugs from globally-rendered modals or App-level helpers? (Planner-sprint pattern)
3. Did the PR introduce any prop name typos that React would silently undefined?
4. Did the PR break SIS surface tests (if classroom-related)?
5. Is the per-component test coverage adequate?

Output: severity-classified findings + VERDICT.
```
