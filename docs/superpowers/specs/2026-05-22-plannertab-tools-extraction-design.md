# PlannerTab Tools Tab Extraction — Design

**Date:** 2026-05-22
**Status:** Design (continues the approved Wave 3 cluster-extraction pattern)
**Scope:** One PR. Behavior-preserving structural extraction. Wave 3, slice 2.
**Lever:** Code-Quality concentrated complexity — `frontend/src/tabs/PlannerTab.jsx` (now 6,680 LOC after the calendar slice).

> **For agentic workers:** execute via the calendar-slice pattern (PR #456): mechanical edits applied by deterministic anchor/assembly scripts (the file is large; subagent edits timed out on the calendar removal), then two-stage subagent review (spec-compliance + code-quality), Vite build + frontend test floor + Playwright E2E + normalized-JSX parity.

---

## 1. Goal

Extract the **Tools tab** cluster out of `frontend/src/tabs/PlannerTab.jsx` into a new component `frontend/src/components/PlannerTools.jsx`, **zero behavior change, zero logic change** — a pure verbatim move. Continues the Wave 3 cadence after the calendar slice (PR #456).

## 2. Scope correction (recorded honestly)

The post-calendar handoff/recommendation labeled "tools" as "reading-level, ~806 LOC, 8 `rl*` state vars, high isolation." An implementation-time audit corrected this: the `plannerMode === "tools"` block is the **full Tools tab — four sub-tools**: reading-level adjuster, study-guide generator, flashcards generator, and slide-deck generator. It is still a clean single-component extraction (no write-coupling, no effects, no named helpers; it owns all its state and only *reads* shared content state), but it is larger and has a real prop interface, not a near-empty one.

## 3. Verified facts (audited 2026-05-22 against `PlannerTab.jsx` @ main `0bb8f06`)

- **Tools JSX block:** `{/* Tools Mode */}` (line 5683) → `{plannerMode === "tools" && (` (5684) → inner `<div className="fade-in">` (5685) … `</div>` (6487) → `)}` (6488). Next sibling is `{/* AttemptDrawer … */}` (6490). It is the last `plannerMode` block before the trailing globally-rendered modals.
- **24 tool-local state vars, all PlannerTab-local `useState`, all referenced ONLY within the tools block** (verified: no references elsewhere in PlannerTab; apparent `flashcards` hits at ~5320-5329 are `res.content_type === 'flashcards'` string literals in the dashboard block, not the state var):
  - study guide (597-600): `studyGuide`, `studyGuideGenerating`, `studyGuideInstructions` (+ `// Study guide` comment at 597)
  - flashcards (601-605): `flashcards`, `flashcardsGenerating`, `flashcardInstructions`, `flashcardCount` (+ `// Flashcards` comment)
  - slides (606-615): `slideDeck`, `slideDeckGenerating`, `slideDeckInstructions`, `slideResources`, `slideResourceList`, `slideResourcesLoading`, `slideCount`, `slideImages`, `slideFormat` (+ `// Slide deck` comment)
  - reading-level (835-847): a 5-line RL slice comment (835-839) + `rlInput`, `rlTargetLevel`, `rlPreserveTerms`, `rlTermInput`, `rlLoading`, `rlResult`, `rlExtracting`, `rlFiles` (840-847)
  - (line 596 `previewShowAnswers` sits directly above the study-guide block but is **lesson-preview** state — NOT a tool; it stays.)
- **No effect and no named helper functions** belong to the tools cluster — every handler is inline in the JSX. (Cleaner than calendar: there is no fetch effect to re-express, so this move has **zero** non-verbatim changes.)
- **External dependency surface (exhaustive scan):**
  - **6 shared props, all read-only in this block** (no setters of these are called in the block): `config` (e.g. `config.subject`, `config.grade`, `config.globalAINotes`), `lessonPlan`, `generatedAssignment`, `globalAINotes`, `uploadedDocs`, `addToast`.
  - `api.*` (5): `adjustReadingLevel`, `extractTextFromFile`, `listResources`, `loadResource`, `saveResource`.
  - 8 raw `fetch(...)` calls (verbatim): `/api/generate-study-guide`, `/api/export-study-guide` (×2), `/api/generate-flashcards`, `/api/export-flashcards` (×2), `/api/generate-slides`, `/api/export-slides`.
  - Components: only `<Icon>` (20×) and `<React.Fragment>`. No other extracted component, no `getAuthHeaders`, no other import.

## 4. Architecture — single component

New file: `frontend/src/components/PlannerTools.jsx`. Owns all 24 tool-local state vars internally; imports `Icon` + `api` directly; uses global `fetch` for the 8 raw calls (verbatim).

### Interface (7 forwarded props)

```jsx
<PlannerTools
  config={config}
  lessonPlan={lessonPlan}
  generatedAssignment={generatedAssignment}
  globalAINotes={globalAINotes}
  uploadedDocs={uploadedDocs}
  addToast={addToast}
  shareWithClass={shareWithClass}
/>
```

No `active` prop (no mount effect, unlike calendar). All 24 state vars and the tool-specific inline handlers are component-internal.

**Correction (code-quality review):** the initial audit listed 6 props but missed `shareWithClass` — a PlannerTab-body closure (the share-with-classes handler, coupled to PlannerTab's `teacherClasses` + share-modal state used by other blocks) called by the 3 "Share with Class" buttons in the study-guide/flashcards/slides sub-tools. It must be **forwarded as a prop** (it stays in PlannerTab; moving it would drag the whole share-modal infra). The audit's prop/import/state scan did not cover PlannerTab-body *functions*; a follow-up free-variable scan confirmed `shareWithClass` is the only such case. A regression test (generate study guide → click "Share with Class" → assert the prop fires) guards it.

### File-level shape

```jsx
import React, { useState } from "react";
import Icon from "./Icon";
import * as api from "../services/api";

export default function PlannerTools({ config, lessonPlan, generatedAssignment, globalAINotes, uploadedDocs, addToast, shareWithClass }) {
  // 24 tool-local state vars (verbatim from PlannerTab: study/flashcard/slide 597-615, rl 835-847)
  return (
    // the ~803-line tools JSX block, verbatim from PlannerTab inner 5685-6487
  );
}
```

## 5. Behavior preservation

**Pure verbatim move — zero logic changes.** Unlike the calendar slice, there is no effect to re-express. The 24 state vars move byte-for-byte; the 6 shared props are forwarded read-only (their usages inside the block are unchanged tokens); the JSX is copied byte-for-byte. The parent keeps the existing `{plannerMode === "tools" && (<PlannerTools … />)}` conditional render, so mount/unmount semantics are identical.

## 6. PlannerTab.jsx changes

- Remove the study/flashcard/slide state block (597-615, including the three `//` section comments) — **keep line 596 `previewShowAnswers`**.
- Remove the RL slice comment + rl state (835-847).
- Remove the tools JSX block (5683-6488) and replace with the `<PlannerTools … />` call.
- Add `import PlannerTools from "../components/PlannerTools";`.
- Remove any import that becomes dead (audit: the tools block uses only `Icon` (still used elsewhere) and `api` (still used) — so **no new dead imports expected**; re-verify at implementation).
- **Keep** all 6 shared props (`config`, `lessonPlan`, `generatedAssignment`, `globalAINotes`, `uploadedDocs`, `addToast`) in PlannerTab's prop destructure — they are forwarded and remain App-level state. No `App.jsx` change.
- Expected: PlannerTab.jsx **6,680 → ~5,850 LOC** (~830 removed: ~803 JSX + ~24 state + comments). New `PlannerTools.jsx` ≈ ~835 LOC.

## 7. Testing & proof

- **New `frontend/src/__tests__/PlannerTools.test.jsx`:** smoke (renders without crashing with the 6 props as minimal stubs) + 1-2 focused tests on a tool action that is cheap to trigger (e.g. the reading-level "Adjust" button calls `api.adjustReadingLevel`, mocked). Mock `../services/api` + `global.fetch` per the existing harness. Net frontend test count goes up (floor never drops).
- **Existing PlannerTab tests stay green** (the tools block has no dedicated existing test like calendar's fetch test; the smoke/mode tests still pass through PlannerTab).
- **Normalized-JSX parity:** the inner tools JSX removed from PlannerTab must be byte-for-byte identical (whitespace-normalized) to PlannerTools' JSX — the definitive verbatim check.
- **Slice proof gates:** Vite build clean + frontend test count ≥ floor + Playwright `health-check.spec.js` E2E (the 9 CI checks).

## 8. Out of scope (explicit)

- No splitting the four sub-tools into separate components (they're interleaved in one tab; extract the whole tab).
- No hook/util split; no logic, UX, endpoint, or styling changes.
- No touching the other `plannerMode` blocks (lesson, assessment, dashboard) or the trailing modals.
- No `App.jsx` change.

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| One of the 24 state vars is referenced outside the tools block (missed leak) | Audited 2026-05-22 — all 24 are tools-only (the `flashcards` string-literal hits in the dashboard are not the var). Implementation re-runs the isolation grep before moving. |
| A shared prop is also *written* in the block (would need setter forwarding) | Setter scan found only the 24 tool-local setters in the block; the 6 shared props are read-only. Re-verify at implementation. |
| Large mechanical edit times out a subagent (as the calendar removal did) | Apply the moves via deterministic assembly/anchor scripts (controller-run), with assertions; subagents do the two-stage review only. |
| JSX not a true verbatim move | Whitespace-normalized parity diff (the definitive check). |

## 10. Expected numbers

- `PlannerTab.jsx`: 6,680 → ~5,850 LOC (~830 removed). Cumulative across the Wave 3 calendar + tools slices: 7,405 → ~5,850 (−21%).
- New `PlannerTools.jsx`: ~835 LOC.
- Frontend test count: +2-3.

## 11. References

- Calendar slice (Wave 3 slice 1): `docs/superpowers/specs/2026-05-22-plannertab-calendar-extraction-design.md` + plan; PR #456; closeout in the assessment doc (PR #457).
- Canonical scorecard: `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`.
- Prior phase plan: `docs/superpowers/plans/2026-05-04-planner-tab-extraction.md`.
