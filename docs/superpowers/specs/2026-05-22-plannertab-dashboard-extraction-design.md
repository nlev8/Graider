# PlannerTab Dashboard Extraction — Design

**Date:** 2026-05-22 · **Status:** Design · **Scope:** one PR · Wave 3 slice 3.
**Lever:** Code-Quality — `frontend/src/tabs/PlannerTab.jsx` (5,853 LOC after the tools slice).

## 1. Goal

Extract the "Student Portal Dashboard" block (`plannerMode === "dashboard"`) out of `frontend/src/tabs/PlannerTab.jsx` into `frontend/src/components/PlannerDashboard.jsx`, behavior-preserving, **zero logic change**.

## 2. Nature of this slice (honest)

Unlike calendar/tools (which owned real local state), the dashboard block is **already fully prop-driven**: its data and handlers live in `App.jsx` and pass through PlannerTab. So this is a **purely presentational extraction with a large prop surface (~36 props)** — the win is ~550 LOC out of PlannerTab and an isolated dashboard render, **not** state/logic decentralization (there is none left to do here). The large prop count is an accepted pattern in this codebase (see the 2026-05-04 plan's PR-1 prop surface rationale).

## 3. Verified facts (audited 2026-05-22 @ main `a360f46`)

- **Block:** `{/* Student Portal Dashboard */}` (5067) → `{plannerMode === "dashboard" && (` (5068) → inner `<div className="fade-in">` (5069) … `</div>` (5638) → `)}` (5639). Next sibling `{/* Calendar Mode */}` (5641).
- **Own state:** none, except `attemptDrawerStudent` (decl ~123) + `setAttemptDrawerStudent`, which are **shared** with the globally-rendered trailing `<AttemptDrawer>` (used at ~5666). They stay in PlannerTab and are **forwarded** as props (moving them would break the trailing modal).
- **Parent-body functions referenced:** none (all handlers are props from App — verified with the free-variable scan that caught `shareWithClass` in the tools slice).
- **Prop surface (~36, derived programmatically, all read/called, none written-as-local):** data — `allTeacherTags`, `assignment`, `contentSubmissionsGroups`, `inProgressDrafts`, `loadingPublished`, `loadingResults`, `loadingSavedAssessments`, `loadingSharedResources`, `publishedAssessments`, `savedAssessments`, `selectedAssessmentResults`, `selectedTagFilter`, `sharedResources`, `teacherClasses`, `plannerMode`; handlers — `addToast`, `deletePublishedAssessment`, `deleteSavedAssessment`, `fetchAssessmentResults`, `fetchPublishedAssessments`, `fetchSavedAssessments`, `fetchSharedResources`, `fetchTeacherClasses`, `fetchTeacherTags`, `handleDeleteAllSharedResources`, `handleDeleteSharedResource`, `itemMatchesTagFilter`, `loadSavedAssessment`, `toggleAssessmentStatus`; setters (forwarded) — `setInProgressDrafts`, `setPublishedAssessments`, `setSelectedAssessmentResults`, `setSelectedTagFilter`, `setSharedResources`; shared state — `attemptDrawerStudent`, `setAttemptDrawerStudent`.
  - **The exact set is derived programmatically at implementation** (intersection of the destructure identifiers with the block's referenced identifiers + the shared `attemptDrawerStudent`), so the component signature and the call site cannot drift. Components used in the block: re-audit at implementation (likely `Icon` + possibly tag/resource sub-pieces already extracted) and import the live ones.

## 4. Architecture — single presentational component

`frontend/src/components/PlannerDashboard.jsx`: receives the ~36 props, renders the verbatim JSX. No internal state, no effects.

## 5. Behavior preservation

Pure verbatim move. PlannerTab keeps the `{plannerMode === "dashboard" && (<PlannerDashboard … />)}` gate. `attemptDrawerStudent` stays in PlannerTab (shared with the trailing AttemptDrawer); the dashboard sets it via the forwarded `setAttemptDrawerStudent`. Proven by whitespace-normalized JSX parity.

## 6. PlannerTab.jsx changes

- Replace the dashboard block (5067-5639) with the `<PlannerDashboard … />` call (all ~36 props forwarded).
- Add `import PlannerDashboard from "../components/PlannerDashboard";`.
- Keep all forwarded props + `attemptDrawerStudent` state in PlannerTab (still used by the trailing AttemptDrawer). Remove any import that becomes dead (re-audit).
- No `App.jsx` change. Expected: 5,853 → ~5,290 LOC.

## 7. Testing & proof

- New `frontend/src/__tests__/PlannerDashboard.test.jsx`: smoke render with the ~36 props stubbed (a `makeProps` factory; arrays default `[]`, functions `vi.fn()`), + 1 focused test (e.g. a delete/fetch button click invokes the forwarded handler).
- **Runtime-completeness guard:** because a missed handler prop is a runtime error (not a build error), a free-variable scan of `PlannerDashboard.jsx` must report **zero** undefined identifiers (every referenced non-local identifier is in the prop list or an import). This is a required check, plus the two-stage review.
- Normalized-JSX parity (definitive). Vite build clean + full suite + Playwright E2E.

## 8. Out of scope

No state decentralization (none to do), no logic/UX changes, no other mode blocks, no `App.jsx` change.

## 9. Risks

| Risk | Mitigation |
|---|---|
| Missed handler prop → runtime error | Programmatic prop derivation (signature + call from one source) + a zero-free-variable scan of the new component + two-stage review. |
| `attemptDrawerStudent` wrongly moved → breaks trailing AttemptDrawer | Audited as shared; forward it (don't move). |
| Large 36-prop interface smell | Accepted pattern for this prop-driven block; documented here. |
| Not a verbatim move | Whitespace-normalized parity diff. |

## 10. Numbers

- PlannerTab.jsx: 5,853 → ~5,290 LOC (~560 out). New PlannerDashboard.jsx ~600 LOC. Cumulative Wave 3: 7,405 → ~5,290 (−29%).

## 11. References

- Calendar + tools slices: PRs #456, #458; specs alongside this. Scorecard: `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`.
