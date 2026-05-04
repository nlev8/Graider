# Planner Tab Extraction Plan

> **For agentic workers:** Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to execute this plan task-by-task.

**Goal:** Move the ~5,943 LOC inline Planner-tab JSX (App.jsx lines 7574-13515) out of `frontend/src/App.jsx` into `frontend/src/tabs/PlannerTab.jsx`, then progressively move ~91 Planner-only state pairs (and their handlers/effects/inline async sites) into the new component so state ownership decentralizes — not just JSX layout. The taxonomy is indicative, not exhaustive: per-PR semantic verification + PR 1's `X is not defined` build-driven discovery will catch any state the upfront audit missed.

**Why:** Codex's 2026-05-03 re-score (8.5/10 average) called the biggest remaining structural gap *"App-shell orchestration debt: Planner is rendered inline in App.jsx."* PR #184 (2026-05-03) deleted the **dead** PlannerTab.jsx file (7,569 LOC, never imported); the live inline block is what actually renders. This sprint extracts that inline block into a properly-wired tab component using the playbook validated by the Grade-tab sprint (PRs #180-183).

**Architecture:** Hybrid presentational-then-stateful migration, scaled up for the ~5x larger state surface. PR 1 ships a presentational PlannerTab (state stays in App, very large prop surface). PRs 2-7 progressively move state into the new component in coherent vertical slices. Final state: `App()` no longer declares any Planner-specific `useState`; it just renders `<PlannerTab .../>` at always-mounted display:none (Assistant + Grade tab precedent).

**Tech Stack:** React 18 + Vite + Vitest. Same pattern as Grade tab sprint (plan #179, PRs #180-183) but at ~5x scale.

---

## Codex Review Status

This plan goes through high-effort Codex review rounds before implementation begins, mirroring the Grade-tab sprint (which had 7 rounds, 21 findings).

- [x] Round 2 (2026-05-04, high-effort): **REVISE_THEN_PROCEED** — 1 CRITICAL + 1 MAJOR. Folded in below:
  - **CRITICAL #1 (Round 2):** Audit incomplete — missed state driven by globally-rendered Planner modals (lines >13800 in App.jsx, after the Planner JSX block ends). Re-audit added 11 confirmed missed Planner-only states: `savedUnits` (1226), `showSaveLesson` (1228), `saveLessonUnit` (1229), `newUnitName` (1230), `attemptDrawerStudent` (1585), `newUnitModal` (1589), `publishedAssessmentModal` (1569), `loadingPublishStudents` (1617), `showShareModal` (1571), `shareModalSharing` (1574), `showPublishModal` (1599). Per Codex Round 3 MAJOR #1, 4 more reclassify back to Planner-only after I incorrectly grouped them as Settings-shared: `shareModalContent` (1572 — used by share modal at 1155 + 14049, no SettingsTab usage), `shareModalSelected` (1573 — same), `assessmentGradingResults` (1538 — no SettingsTab usage), `tagDropdownOpenFor` (1592 — used at 4179 inside Planner-owned dashboard helper). New total: ~91 Planner-only. Only `assessmentTemplates` (1575) and `uploadingTemplate` (1576) genuinely stay shared (passed to SettingsTab at App.jsx:7448).
  - **MAJOR #2 (Round 2):** Wrong line refs corrected:
    - Calendar fetch effect: App.jsx:2113 (was incorrectly 2207, which is `isHoliday` helper).
    - Standards-load effect: App.jsx:2078 (was conflated with calendar fetch).
    - `getActiveAssignment` / `setActiveAssignment`: App.jsx:4490 + 4498 (was 4510).
    - Lesson/assignment exports at App.jsx:8685 + 8801 are `api.exportGeneratedAssignment` (was incorrectly described as `exportLessonPlan`/`exportAssignment`).
    - 2090 is the standards-load catch path, not a matching effect.

- [x] Round 1 (2026-05-04, high-effort): **REVISE_THEN_PROCEED** — 2 CRITICAL + 3 MAJOR + 3 MINOR. Folded in below:
  - **CRITICAL #1:** 12 states marked "shared" were over-classified — their "elsewhere" hits are Planner-owned helpers that happen to live outside the JSX block. Reclassified Planner-only: `selectedAssessmentResults`, `selectedQuestions`, `assessmentAnswers`, `selectedSources`, `publishingAssessment`, `plannerMode`, `selectedIdea`, `assignmentQuestionCounts`, `calendarData`, `allTeacherTags`, `selectedTagFilter`, `saveAssessmentName`. Updated taxonomy.
  - **CRITICAL #2:** Task 5 missed the entire publish-modal flow. Added concrete state list (`showPublishModal`, `publishSettings`, `publishClassId`, `publishModalStudents`, `loadingPublishStudents`, `publishedAssessmentModal`) and handlers (`publishAssessmentHandler` at App.jsx:3806, `loadPublishModalStudents`, `confirmPublishAssessment`) plus the globally-rendered modals at App.jsx:13996. The publish flow gets its own dedicated PR.
  - **MAJOR #3:** Slice independence claims wrong. Restructured: question editing is cross-cutting over lessonPlan/generatedAssignment/generatedAssessment via `getActiveAssignment` (App.jsx:4490) and `setActiveAssignment` (App.jsx:4498); RL is a separate isolated workflow; `selectedSources` belongs with assessment generation; `plannerMode`/`calendarData` belong with the Planner shell.
  - **MAJOR #4:** Inline API risk underspecified. Added concrete handler inventory per task with line refs (export buttons, calendar import, RL extraction, study guide export, flashcard export, slide export, etc.).
  - **MAJOR #5:** Resequenced — start with narrower slices (Planner shell → calendar → RL → question editing → lesson-plan core → assessment → publish), not broadest.
  - **MINOR #6:** "Semantic shared-state verification complete" is now a hard precondition before any PR after PR 1.
  - **MINOR #7:** PR 1 prop estimate rationale clarified — intentionally large closure-prop extraction, not a byproduct of shared-state count.
  - **MINOR #8:** Per-slice tables now separate "feature-area states discovered" from "states actually moved in this PR".
- [ ] Round 2+: TBD until ACCEPT consensus

---

## State Taxonomy

### Planner-only — ~91 pairs (move to PlannerTab over PRs 2-7)

Initial audit on 2026-05-04 classified 67 pairs as Planner-only by raw occurrence counting. Codex Round 1 CRITICAL #1 reclassified 12 from "shared" → "Planner-only" after semantic verification (their non-Planner uses are Planner-owned helpers living outside the JSX block). Codex Round 2 CRITICAL #1 surfaced 11 missed by the audit because they're driven by globally-rendered Planner modals (lines >13800 in App.jsx, after the Planner JSX block ends): `savedUnits`, `showSaveLesson`, `saveLessonUnit`, `newUnitName`, `attemptDrawerStudent`, `newUnitModal`, `publishedAssessmentModal`, `loadingPublishStudents`, `showShareModal`, `shareModalSharing`, `showPublishModal`. Codex Round 3 MAJOR #1 reclassified 4 more from shared → Planner-only (`shareModalContent`, `shareModalSelected`, `assessmentGradingResults`, `tagDropdownOpenFor` — only `assessmentTemplates` and `uploadingTemplate` remain truly Settings-shared). Running total: 67 + 12 + 11 + ~1 (assessmentTemplates/uploadingTemplate were never counted as Planner-only) = ~91 Planner-only. **The taxonomy remains indicative, not exhaustive — PR 1's build-fail-driven discovery + per-PR semantic verification will catch any remaining missed state.**

| Reclassified state | Pre-Codex tag | Codex evidence (App.jsx) | Post-Codex |
|---|---|---|---|
| `selectedAssessmentResults` | shared (1 elsewhere) | `deletePublishedAssessment` (4417) is Planner-owned | Planner-only |
| `selectedQuestions` | shared (6 elsewhere) | reset effects at 1217; edit handlers at 4515 — all Planner | Planner-only |
| `assessmentAnswers` | shared (2 elsewhere) | assessment load (4037) + grading (4064) helpers — Planner | Planner-only |
| `selectedSources` | shared (1 elsewhere) | assessment generation at 3687 — Planner | Planner-only |
| `publishingAssessment` | shared (1 elsewhere) | publish-modal wiring at 13996 — Planner | Planner-only |
| `plannerMode` | shared (4 elsewhere) | Planner-only effects at 2100 — Planner | Planner-only |
| `selectedIdea` | shared (4 elsewhere) | lesson generation at 3540 — Planner | Planner-only |
| `assignmentQuestionCounts` | shared (4 elsewhere) | lesson generation at 3540 — Planner | Planner-only |
| `calendarData` | shared (4 elsewhere) | Planner-only calendar fetch effect at 2113 — Planner | Planner-only |
| `allTeacherTags` | shared (3 elsewhere) | dashboard filtering at 4168 — Planner | Planner-only |
| `selectedTagFilter` | shared (3 elsewhere) | dashboard filtering at 4168 — Planner | Planner-only |
| `saveAssessmentName` | shared (2 elsewhere) | save flow at 3971 — Planner | Planner-only |

**Slices below are now grouped by feature for sequencing — each task moves only the subset listed in its "states actually moved" table.**

### Truly shared — 21 pairs (STAY in App, pass as props)

These are confirmed used both inside the Planner block and by other tabs (Builder, Grade, Settings, Results, Admin). They CANNOT move into PlannerTab without breaking the other tabs.

| State | Decl | Notes |
|---|---|---|
| `lessonPlan` | 1069 | Used by Builder + Settings |
| `generatedAssignment` | 1075 | Builder uses |
| `assessmentConfig` | 1244 | Builder + assessment-publish flows |
| `config` | 507 | App-wide |
| `selectedStandards` | 1065 | Builder uses |
| `unitConfig` | 1232 | Builder uses |
| `standards` | 1064 | Builder uses |
| `assignment` | 979 | App-wide (Builder, Grade, Results) |
| `uploadedDocs` | 1088 | Builder uses |
| `generatedAssessment` | 1535 | Heavy Builder use |
| `rubric` | 1680 | App-wide (Settings + Grade) |
| `globalAINotes` | 912 | App-wide (Settings) |
| `supportDocs` | 1624 | Builder uses |
| `savedAssignments` | 1010 | App-wide |
| `teacherClasses` | 1567 | Admin tab uses |
| `periods` | 1623 | App-wide |
| `user`, `status`, `activeTab`, `savedAssignmentData`, `contentOnly` | various | App-wide infrastructure |

**Verify pattern (Grade-tab Round 1+ from PR #180):** Each "shared" classification needs semantic verification. Some "elsewhere" hits could be unrelated lexical shadows (e.g. a function-local `selectedQuestions` that happens to have the same name). Per Codex Round 1 MINOR #6: **complete semantic verification is now a hard precondition before any PR after PR 1.**

### App-shell handlers (stay in App, pass as props)

Same pattern as Grade tab. `addToast`, `setStatus`, `setConfig`, `loadAssignment`, etc. stay in App and are passed to PlannerTab.

---

## File Structure

- `frontend/src/tabs/PlannerTab.jsx` — new file (note: a stale dead file at the same path was deleted in PR #184; this is the live re-creation). Receives App-wide reads as props, owns its own Planner-specific state by end of the sprint.
- `frontend/src/App.jsx` — loses ~5,943 LOC of inline JSX (PR 1) + ~91 state declarations + setters + handlers + dead branches over PRs 2-7. Drops from 14,081 → ~6,800 LOC by sprint end.
- `frontend/src/__tests__/PlannerTab.test.jsx` — new component test file (added in PR 1, expanded each subsequent PR per Grade-tab pattern).

---

## Tasks

### Task 1: Presentational extraction (PR 1)

**Files:**
- Create: `frontend/src/tabs/PlannerTab.jsx`
- Modify: `frontend/src/App.jsx:7574-13515` (replace inline JSX with `<PlannerTab .../>`)

Same pattern as Grade-tab PR #180 (plan #179):

- [ ] **Step 1: Write failing tests (smoke + focused behavior tests)**

Per Grade-tab Codex review precedent: single smoke insufficient on a 5,943-LOC extraction. Initial focused tests:

```jsx
// frontend/src/__tests__/PlannerTab.test.jsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PlannerTab from '../tabs/PlannerTab';

vi.mock('../services/api', () => ({
  loadAssignment: vi.fn().mockResolvedValue({ assignment: {} }),
  generateLessonPlan: vi.fn().mockResolvedValue({ lessonPlan: 'Test' }),
  // expand as the test set grows
}));

const makeProps = (overrides = {}) => ({
  status: { results: [], log: [], is_running: false, error: null },
  config: { ai_model: 'gpt-4o', subject: 'Math', grade_level: '8' },
  addToast: vi.fn(),
  setStatus: vi.fn(),
  // 80+ shared state props
  ...overrides,
});

describe('PlannerTab', () => {
  it('smoke: renders without crashing with minimal props', () => {
    render(<PlannerTab {...makeProps()} />);
  });

  // Focused tests TBD per Codex Round 1+ review feedback. Likely candidates:
  // - plannerMode toggle (lesson/assessment/dashboard/calendar)
  // - lesson generation button → api.generateLessonPlan called
  // - one example of each tab's primary action
});
```

- [ ] **Step 2: Run test → FAIL (no PlannerTab module)**
- [ ] **Step 3: Create `frontend/src/tabs/PlannerTab.jsx` with the lifted JSX**

Copy lines 7574-13515 from `App.jsx` (inside the `activeTab === "planner" && (` wrapper). Wrap in:
```jsx
import React from 'react';
import Icon from '../components/Icon';
// ... whatever else the JSX imports inline

export default function PlannerTab(props) {
  // Destructure all closures the JSX captures. Build will fail fast with
  // "X is not defined" until every one is in props.
  //
  // Per Codex Round 1 MINOR #7: the prop count is large by design — this
  // is an intentionally wide closure-prop extraction. Expect ~80-100 props
  // (~91 Planner-only states + setters that haven't yet moved + ~30 App
  // handlers + constants + refs). PRs 2-7 reduce this surface.
  const {
    status, config, addToast, setStatus, ...
    // 80+ destructure entries
  } = props;

  return (
    <div data-tutorial="planner-card" className="fade-in">
      {/* paste lifted JSX here */}
    </div>
  );
}
```

- [ ] **Step 4: Replace inline JSX in App.jsx**

```jsx
{activeTab === "planner" && (
  <PlannerTab
    status={status} setStatus={setStatus}
    config={config}
    // 80+ props pass-through
  />
)}
```

Add import: `import PlannerTab from './tabs/PlannerTab';`

- [ ] **Step 5: Iteratively fix `X is not defined` errors**

Run `npm run build`. For each undefined identifier, add it to the destructure + the call site. Do NOT guess — let the build tell you what's missing.

- [ ] **Step 6: Run smoke test → PASS, full suite → PASS**
- [ ] **Step 7: Codex parity review (high-effort)**

Per Grade-tab convention. Verify normalized JSX byte-for-byte match against pre-PR App.jsx Planner block.

- [ ] **Step 8: Commit + PR + merge**

### Task 2: Always-mounted conversion + Planner shell (PR 2)

Per Codex Round 1 MAJOR #5 + Round 2 CRITICAL of Grade-tab plan: **Step 0 must convert PlannerTab to always-mounted display:none BEFORE any state moves.**

**Step 0 — Always-mounted conversion:**
```jsx
// Before (PR 1):
{activeTab === "planner" && (
  <PlannerTab ... />
)}

// After (PR 2 Step 0):
<div style={{ display: activeTab === "planner" ? "block" : "none" }}>
  <PlannerTab ... />
</div>
```

**States actually moved in this PR (3 — narrowest possible first stateful slice):**
- `plannerMode` (decl 1540) — main tab navigation between lesson/assessment/dashboard/calendar
- `calendarData` (decl 1551) — drives calendar view (Planner-only calendar fetch effect at App.jsx:2113)
- Any small Planner-only constants or top-level refs that don't belong to a deeper slice.

**Handlers / effects to move with this slice:**
- The Planner-only calendar fetch useEffect at App.jsx:2113 that reads `plannerMode` and writes `calendarData`. (Per Codex Round 2 MAJOR #2: 2207 is the `isHoliday` helper, not a useEffect; the previous draft was wrong.)

**Why this slice first:** Validates the always-mounted pattern + the smallest possible state subset. If anything goes wrong, blast radius is contained to the Planner shell.

### Task 3: Calendar + holiday + import (PR 3)

Per Codex Round 1 MAJOR #5: this is the next-narrowest slice and isolated from cross-cutting workflows.

**Feature-area states discovered:** `calendarView`, `calendarMonth`, `selectedCalendarDate`, `calendarDragId`, `showHolidayModal`, `holidayForm`, `showImportModal`, `importParsing`, `importEvents`, `importChecked`, `importSelectedDoc`, `importImporting`, `editingEvent`, `quickAddForm`.

**States actually moved in this PR (14):** all of the above. None are shared.

**Handlers / effects / inline-async sites to move with this slice (per Codex Round 1 MAJOR #4):**
- Calendar import parse/import callbacks at App.jsx:12651 (the `<ImportEventsModal>` onParse/onImport prop arrows)
- Calendar drag-drop event handlers (live inside the JSX, move with the lift)
- Holiday modal save/delete handlers (in `<HolidayModal>` props)
- The calendar fetch useEffect at App.jsx:2113 (moved with `calendarData` in PR 2; this PR follows it). **Note: the standards-load effect at App.jsx:2078 is unrelated — that stays put.**

### Task 4: Reading-level (RL) tools (PR 4)

Per Codex Round 1 MAJOR #3: RL is an isolated tools-mode workflow, separable from question-editing.

**Feature-area states discovered:** `rlInput`, `rlTargetLevel`, `rlPreserveTerms`, `rlTermInput`, `rlLoading`, `rlResult`, `rlExtracting`, `rlFiles`.

**States actually moved in this PR (8):** all of the above. None are shared.

**Handlers / effects / inline-async sites:**
- RL drag-drop file extraction handler at App.jsx:12722 (inline `extractTextFromFile` + `setRlFiles` + `setRlInput` chain)
- RL submit / target-level / preserve-terms handlers (inside the JSX — moves with the lift)

### Task 5: Question editing (PR 5)

Per Codex Round 1 MAJOR #3: question editing is cross-cutting over `lessonPlan`/`generatedAssignment`/`generatedAssessment` via `getActiveAssignment` (App.jsx:4490) and `setActiveAssignment` (App.jsx:4498). The active-assignment helpers must move with this slice.

**Feature-area states discovered:** `editingQuestion`, `selectedQuestions`, `regeneratingQuestions`, `editMode`, `sectionsDropdownOpen`.

**States actually moved in this PR (5):** all of the above. The "shared" classification of `selectedQuestions` was overridden by Codex Round 1 CRITICAL #1 — its "elsewhere" hits are Planner-owned helpers (App.jsx:1217 reset effects, App.jsx:4515 edit handlers).

**Handlers / effects / inline-async sites:**
- `getActiveAssignment` (App.jsx:4490) and `setActiveAssignment` (App.jsx:4498) — these read/write the truly-shared `lessonPlan`/`generatedAssignment`/`generatedAssessment`, so the helpers move into PlannerTab as a wrapper around props that read those App-shell states. (Per Codex Round 2 MAJOR #2: 4510 was the wrong line.)
- Question reset effects at App.jsx:1217 (move with `selectedQuestions`)
- Edit handlers at App.jsx:4515 (move with `editingQuestion`/`editMode`)

### Task 6: Lesson-plan core + flashcards/slides/study guide + saved-lessons (PR 6)

**States added by Codex Round 2/3 reclassification:** `savedUnits` (1226), `showSaveLesson` (1228), `saveLessonUnit` (1229), `newUnitName` (1230) — all drive the "save lesson to unit" workflow surfaced in the Round 2 audit. Folded into this PR's moved-state list.

Per Codex Round 1 MAJOR #5: heaviest cross-coupled workflow. Run last among slices.

**Feature-area states discovered:** lesson generation (`plannerLoading`, `lessonVariations`, `brainstormIdeas`, `selectedIdea`, `brainstormLoading`, `expandedStandards`, `assignmentSectionsOpen`, `assignmentQuestionCounts`, `previewShowAnswers`, `previewResults`, `docUploading`, `matchingInProgress`, `matchResults`); study guide (`studyGuide`, `studyGuideGenerating`, `studyGuideInstructions`); flashcards (`flashcards`, `flashcardsGenerating`, `flashcardInstructions`, `flashcardCount`); slides (`slideDeck`, `slideDeckGenerating`, `slideDeckInstructions`, `slideResources`, `slideResourceList`, `slideResourcesLoading`, `slideCount`, `slideImages`, `slideFormat`).

**States actually moved in this PR:** all of the above (~33). `selectedIdea` and `assignmentQuestionCounts` were reclassified Planner-only by Codex Round 1 CRITICAL #1; `savedUnits`/`showSaveLesson`/`saveLessonUnit`/`newUnitName` added by Round 2 audit.

**Handlers / effects / inline-async sites (per Codex Round 1 MAJOR #4):**
- Lesson/assignment export buttons at App.jsx:8685 + 8801 — both are inline `api.exportGeneratedAssignment` calls (per Codex Round 2 MAJOR #2: previous draft incorrectly named these `exportLessonPlan`/`exportAssignment`).
- Standards matching effects: TBD per per-PR investigation. (Per Codex Round 2 MAJOR #2: 2090 is the standards-load catch path, not a matching effect — previous reference was wrong.)
- Study guide export at App.jsx:13044 — raw `fetch(...)` to the export endpoint (per Codex Round 3 MAJOR #2: previous draft incorrectly named `api.exportStudyGuide` / `api.saveResource`; the live code uses raw fetch).
- Flashcard export at App.jsx:13228 — raw `fetch(...)`.
- Slide deck export at App.jsx:13476 — raw `fetch(...)` (creates blob URL inline; revokes inline — no state-level blob risk).

### Task 7: Assessment + saved/published + publish modals (PR 7)

Per Codex Round 1 CRITICAL #2: **the publish flow MUST be in scope.** The previous draft missed `showPublishModal`, `publishSettings`, `publishClassId`, `publishModalStudents`, `loadingPublishStudents`, `publishedAssessmentModal`, plus their handlers and the globally-rendered modals at App.jsx:13996.

**Feature-area states discovered (assessment subset):** `assessmentLoading`, `gradingAssessment`, `savingAssessment`, `saveAssessmentName`, `assessmentAnswers`, `selectedSources`, `selectedAssessmentResults`, `publishingAssessment`, `publishedAssessments`, `loadingPublished`, `inProgressDrafts`, `loadingResults`, `sharedResources`, `loadingSharedResources`, `contentSubmissionsGroups`, `savedAssessments`, `loadingSavedAssessments`, `savedLessons`, `showPlatformExport`, `allTeacherTags`, `selectedTagFilter`.

**Feature-area states discovered (publish-modal subset, added by Codex Round 1 CRITICAL #2):** `showPublishModal`, `publishSettings`, `publishClassId`, `publishModalStudents`, `loadingPublishStudents`, `publishedAssessmentModal`.

**Feature-area states discovered (share-modal subset + globally-rendered modals, added by Codex Round 2/3):** `assessmentGradingResults` (1538), `showShareModal` (1571), `shareModalContent` (1572), `shareModalSelected` (1573), `shareModalSharing` (1574), `attemptDrawerStudent` (1585), `newUnitModal` (1589), `tagDropdownOpenFor` (1592). All drive globally-rendered Planner modals (App.jsx:13891+, 14013-14074). The plan must move these along with the assessment+publish slice or the goal of "App.jsx has zero Planner-specific useState" is not met.

**States actually moved in this PR (~35):** all of the above. Several were reclassified Planner-only by Codex Round 1 CRITICAL #1: `selectedAssessmentResults`, `assessmentAnswers`, `selectedSources`, `publishingAssessment`, `allTeacherTags`, `selectedTagFilter`, `saveAssessmentName`. Several added by Round 2/3: `assessmentGradingResults`, `showShareModal`, `shareModalContent`, `shareModalSelected`, `shareModalSharing`, `attemptDrawerStudent`, `newUnitModal`, `tagDropdownOpenFor`, `loadingPublishStudents`, `publishedAssessmentModal`, `showPublishModal`.

**Handlers / effects / inline-async sites (per Codex Round 1 MAJOR #4 + CRITICAL #2):**
- Assessment generation at App.jsx:3687 (reads `selectedSources` — Planner-only)
- Assessment load / grading helpers at App.jsx:4037 + 4064 (read/write `assessmentAnswers`)
- Save flow at App.jsx:3971 (reads/writes `saveAssessmentName`)
- Delete published at App.jsx:4417 (reads `selectedAssessmentResults`)
- Publish modal scope:
  - `publishAssessmentHandler` at App.jsx:3806
  - `loadPublishModalStudents`
  - `confirmPublishAssessment`
  - The globally-rendered `<PublishContentModal>` and `<PublishedAssessmentModal>` at App.jsx:13996 — these need to move INTO PlannerTab as part of this slice (they're rendered globally so the planner JSX can trigger them, but their state ownership belongs to the planner workflow).
- Dashboard filtering at App.jsx:4168 (reads `allTeacherTags` + `selectedTagFilter`)
- Lesson-generation cross-references at App.jsx:3540 (reads `selectedIdea` + `assignmentQuestionCounts` — but those moved to PlannerTab in PR 6, so this PR may need to coordinate via re-exposing them via a callback the App helper invokes — TBD per Codex Round 2+ feedback).

### Task 8: Shared-state mutation audit + dead-code cleanup (final PR)

Per Codex Round 1 MINOR #6: **complete semantic verification of the 21 truly-shared states is a hard precondition before any PR 2-7 work.** This task tracks any further reclassifications discovered during PR 2-7 implementation, plus dead-code purge per Grade-tab PR 4 pattern.

Each "shared" state's "elsewhere" hits get the same semantic check applied to the 12 Codex Round 1 reclassifications. Some may turn out to be Planner-only and move into PlannerTab. The remaining truly-shared ones stay in App.

Also: dead-code purge per Grade-tab PR 4 pattern. Audit which of the moved-state's handlers, useEffects, or helpers have stale references; delete them.

---

## Verification per PR

- `npm test` — all tests pass (currently 160; after PR 1 should be 165+ from new PlannerTab.test.jsx)
- `npm run build` — clean
- 8 CI gates green
- Codex parity / contract review (high-effort per the always-high session policy)
- Manual smoke: load `/`, switch to Planner tab, exercise the slice's UI surface

## Risks

| Risk | Mitigation |
|---|---|
| 80-100 prop surface in PR 1 is enormous | Same as Grade-tab — that's the point; PRs 2-7 reduce it. Per Codex Round 1 MINOR #7: this is an intentionally wide closure-prop extraction, not a byproduct of taxonomy. |
| State classified as "shared" by raw count is actually Planner-only | Codex Round 1 CRITICAL #1 reclassified 12 such states. Pre-PR-2 audit must apply the same semantic check to the remaining 21 "shared" states (Codex Round 1 MINOR #6 — hard precondition). |
| **Tab-switch state reset (Grade-tab Round 2 CRITICAL)** | PR 2 Step 0 converts PlannerTab to always-mounted display:none, mirroring Assistant + Grade tab. State persistence preserved before any state moves. |
| **5x larger state surface than Grade tab — sprint needs 7 PRs** | Plan accommodates this by splitting tasks into coherent slices (Planner shell / calendar / RL / question editing / lesson-plan core / assessment+publish / cleanup). Codex Round 1 MAJOR #5 sequence: narrow → broad. |
| Inline `api.*` calls inside the JSX (Grade-tab Round 2 #4) | Concrete inventory in Task 6 (8685, 8801 inline `api.exportGeneratedAssignment`; raw `fetch(...)` at 13044, 13228, 13476 for study guide / flashcard / slide export) and Task 7 (3687, 3806, 3971, 4037, 4064, 4168, 4417). Each slice's async handlers move with state. Codex Round 1 MAJOR #4 — inventory at plan time, not PR time. |
| Globally-rendered modals (`<PublishContentModal>`, `<PublishedAssessmentModal>`) | PR 7 moves them into PlannerTab. Codex Round 1 CRITICAL #2 — these were missing from the prior draft and are explicitly in scope now. |
| Refs (e.g. dropzone, file input refs) | Use `forwardRef`; Grade-tab precedent. |
| Tests need extensive prop stubbing | `makeProps()` helper plus `vi.mock('../services/api')` for inline api calls. |
| Cross-cutting `getActiveAssignment`/`setActiveAssignment` helpers | PR 5 (question editing) moves these as wrappers around the truly-shared `lessonPlan`/`generatedAssignment`/`generatedAssessment` (which stay in App, passed as props). |

## Numbers (expected)

- After PR 1: App.jsx -5,943 LOC of inline JSX. New PlannerTab.jsx +6,100 LOC (with prop boilerplate). State unchanged.
- After PR 7: App.jsx -~91 useState declarations + ~30+ associated handlers/effects ≈ -1,800+ LOC. State decentralized for the entire Planner workflow.
- App.jsx 14,081 → ~6,800 LOC by sprint end (-52%). Combined with the prior Grade-tab sprint, App.jsx will have lost ~62% from its 17,674 starting point this session week.
- Codex re-score expected: Architecture 8.6 → ~9.0+, Code Quality 9.0 → ~9.2.
