# PlannerTab Calendar Cluster Extraction — Design

**Date:** 2026-05-22
**Status:** Design approved, pending spec review
**Scope:** One PR. Behavior-preserving structural extraction.
**Lever:** Code-Quality concentrated complexity — `frontend/src/tabs/PlannerTab.jsx` (7,405 LOC, the largest raw file).

> **For agentic workers:** After spec approval, use `superpowers:writing-plans` to produce the implementation plan, then `superpowers:subagent-driven-development` (or `executing-plans`) to execute it task-by-task.

---

## 1. Goal

Extract the self-contained **calendar cluster** out of `frontend/src/tabs/PlannerTab.jsx` into a single new component `frontend/src/components/PlannerCalendar.jsx`, with **zero behavior change and zero logic change** — a pure structural move. This resumes the PlannerTab decomposition cadence (Wave 3, slice 1) on the cleanest, most isolated remaining inline cluster.

## 2. Background & why this cluster

`PlannerTab.jsx` reached 7,405 LOC because the earlier extraction sprint (2026-05-04 plan, Waves 1–2) moved the inline Planner JSX *and* ~91 Planner-only state pairs out of `App.jsx` and **into** `PlannerTab.jsx`. The terminal goal of that plan ("App.jsx has zero Planner-specific useState") was met, which is precisely why `PlannerTab.jsx` itself is now the lever. The next phase decomposes `PlannerTab.jsx` by extracting cohesive clusters *out of it* into `frontend/src/components/`, continuing the Wave 2 cadence (AttemptDrawer, ShareWithClassesModal, HolidayModal, ImportEventsModal, etc. were each extracted this way).

The JSX return (line 1275 → 7404) splits into five `plannerMode` blocks plus trailing already-extracted modals:

| Cluster | JSX size | Dedicated state | Dedicated helpers | Isolation |
|---|---|---|---|---|
| lesson | ~2,193 | many | 5+ | Low — cross-couples shared `lessonPlan`/`generatedAssignment` + exports |
| assessment | ~1,625 | assessment*/publish*/share* | 3 | Low–Med — publish/share modals, shared `generatedAssessment` |
| tools (reading-level) | ~806 | 8 `rl*` | inline | High — isolated workflow |
| **calendar** | **~600** | **15** | **11 named** | **High — fully isolated, clean api interface** |
| dashboard | ~573 | tags/published/share | some shared | Med |

Calendar is chosen for v1: highest cohesion + isolation = lowest risk to re-warm the cadence, while still removing ~730 LOC in one clean slice. The two largest blocks (lesson, assessment) are deliberately deferred — they are the most cross-coupled and are better tackled after the cadence is re-warmed on an isolated cluster.

## 3. Verified facts (audited 2026-05-22 against `PlannerTab.jsx` @ main `164f96a`)

- **PlannerTab is always-mounted** — rendered at `App.jsx:6623` inside `<div style={{ display: activeTab === "planner" ? "block" : "none" }}>`. It never unmounts; only CSS `display` toggles. Children of a `display:none` subtree remain mounted in React.
- The calendar block is **conditionally rendered** inside PlannerTab via `{plannerMode === "calendar" && (…)}` (line 5809), so the calendar subtree itself mounts/unmounts on `plannerMode` change.
- **All 15 calendar state vars (1142–1156) are calendar-block-only** — no references anywhere else in `PlannerTab.jsx` (the one apparent hit at line 104 is a comment).
- **All 11 calendar helpers are calendar-cluster-only** — every call site is within the calendar block (5809–6408) or an internal helper-to-helper call (e.g. `loadCalendar` invoked by `scheduleLesson`/`addHoliday`/etc.).
- **Calendar JSX external dependency surface:** `addToast` (5 refs), `savedLessons` (3 refs — reads `savedLessons.units`), `supportDocs`/`setSupportDocs` (reads `supportDocs.length`, lazy-loads via `setSupportDocs`, passes `supportDocs` to `ImportEventsModal`), `api.*` (3 refs — `listSupportDocuments`, `parseDocumentForCalendar`, `importCalendarEvents`). The apparent `status` ref was a false positive (`data.status` from a response, not the app-shell `status` prop). **No `lessonPlan`/`generatedAssignment`/`generatedAssessment` leakage.**
  - **Correction (implementation-time audit, 2026-05-22):** the initial design audit omitted `supportDocs`/`setSupportDocs`. They are App-level **shared** state (`App.jsx:1481`, also passed to the Settings/Tools tab at `App.jsx:6479`); the calendar import flow reads the shared doc list and lazy-loads it. They must be **passed through as props** (not made component-local), or the shared-doc-list contract with the other tab breaks. **The component interface is five props, not three.**
- Components used in the calendar JSX: `Icon`, `HolidayModal`, `ImportEventsModal` — all already extracted and importable.
- **Existing behavior net:** `frontend/src/__tests__/PlannerTab.test.jsx:194–212` asserts the `/api/calendar` fetch fires when `plannerMode==='calendar'` and does **not** fire in lesson mode; lines 215–223 assert the Calendar mode button calls `setPlannerMode('calendar')`. These run *through* PlannerTab, so they validate the post-extraction wiring without modification.

## 4. The calendar fetch effect (current)

```jsx
// PlannerTab.jsx:1159–1163
useEffect(() => {
  if (activeTab === "planner" && plannerMode === "calendar") {
    fetch("/api/calendar").then(r => r.json()).then(setCalendarData).catch(() => {});
  }
}, [activeTab, plannerMode]);
```

The dashboard effect immediately below (`PlannerTab.jsx:1166–1170`, `fetchTeacherClasses` on `plannerMode==='dashboard'`) is **not** calendar and **stays** in PlannerTab.

## 5. Architecture — single component

New file: `frontend/src/components/PlannerCalendar.jsx` (Approach A, matching the Wave 2 single-component cadence). It owns all calendar state, the fetch effect, and all 11 helpers internally; it imports `Icon`, `HolidayModal`, `ImportEventsModal`, and `api` directly.

### Interface (props — the entire surface)

```jsx
<PlannerCalendar
  active={activeTab === "planner"}   // gates the fetch effect (see §6)
  addToast={addToast}                // CRUD error toasts (unchanged)
  savedLessons={savedLessons}        // read-only; powers the quick-add unit dropdown
  supportDocs={supportDocs}          // shared doc list (also used by Settings/Tools tab)
  setSupportDocs={setSupportDocs}    // shared setter; calendar import lazy-loads the list
/>
```

Five props total. All 15 state vars and 11 helpers are component-internal; `supportDocs`/`setSupportDocs` are forwarded shared state (see §3 correction).

### File-level shape

```jsx
import React, { useState, useEffect } from "react";
import Icon from "./Icon";
import HolidayModal from "./HolidayModal";
import ImportEventsModal from "./ImportEventsModal";
import * as api from "../services/api";

export default function PlannerCalendar({ active, addToast, savedLessons, supportDocs, setSupportDocs }) {
  // 15 calendar state vars (verbatim from PlannerTab 1142–1156)
  // fetch effect (re-expressed; see §6)
  // 11 helpers (verbatim from PlannerTab 1173–1273)
  return (
    // the ~600-line calendar JSX block, verbatim from PlannerTab 5809–6408
  );
}
```

## 6. Behavior preservation

The only non-verbatim change is the effect guard. Original guard: `activeTab === "planner" && plannerMode === "calendar"`.

After extraction:
- `plannerMode === "calendar"` → satisfied by PlannerTab's existing conditional render `{plannerMode === "calendar" && <PlannerCalendar … />}`, which mounts/unmounts the component exactly as the inline `{plannerMode === "calendar" && (…)}` block did.
- `activeTab === "planner"` → carried by the `active` prop. The effect becomes:

```jsx
useEffect(() => { if (active) loadCalendar(); }, [active]);
```

**Equivalence argument:** The original effect fetches whenever the `[activeTab, plannerMode]` pair transitions into the `planner + calendar` state, and never fetches otherwise. With the conditional-render gate handling `plannerMode` and `active = (activeTab === "planner")` handling the tab dimension, the child's `[active]` effect fires `loadCalendar()` exactly on `active → true` — i.e. whenever the component is mounted (plannerMode is calendar) *and* the planner tab is showing. This produces the same fetch timing for every transition: planner+calendar → fetch; tab leaves planner → no fetch; tab returns → fetch; plannerMode leaves calendar → unmount; returns → remount → fetch-if-active. No fetch occurs in any state where the original did not.

Everything else is a **verbatim move**: identical try/catch + `addToast(...)` error handling, identical `/api/calendar*` request shapes, identical date math, identical JSX.

## 7. Data flow (unchanged)

- Mount / `active → true`: `loadCalendar()` → `GET /api/calendar` → `setCalendarData`.
- Schedule lesson: `scheduleLesson(entry)` → `PUT /api/calendar/schedule` → on `scheduled`, `loadCalendar()`.
- Unschedule: `unscheduleLesson(id)` → `DELETE /api/calendar/schedule/:id` → `loadCalendar()`.
- Add holiday: `addHoliday(h)` → `POST /api/calendar/holiday` → on `added`, `loadCalendar()`.
- Remove holiday: `removeHoliday(date)` → `DELETE /api/calendar/holiday?date=…` → `loadCalendar()`.
- Import: `api.parseDocumentForCalendar(doc)` → user selects events → `api.importCalendarEvents(selected)` → on `imported`, reload.
- `savedLessons.units` (prop, read-only) populates the quick-add unit dropdown.

## 8. Error handling (unchanged)

Each mutation helper retains its existing `try/catch` with `if (addToast) addToast("Failed to …", "error")`. The fetch/load paths retain their `.catch(() => {})` swallow. No change.

## 9. PlannerTab.jsx changes

- Remove: 15 state declarations (1142–1156), the calendar fetch effect (1159–1163), the slice comment (102–107, which describes the now-departing calendar code), the 11 helpers (1173–1273), and the ~600-line JSX block (5809–6408).
- Keep: the dashboard `fetchTeacherClasses` effect (1166–1170).
- Add: `import PlannerCalendar from "../components/PlannerCalendar";`
- Replace the calendar block with:
  ```jsx
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
- **Keep** `supportDocs`/`setSupportDocs` in PlannerTab's prop destructuring — they are forwarded to PlannerCalendar (and remain App-level shared state). Do **not** remove them from PlannerTab or App.jsx.
- No `App.jsx` change required — PlannerTab already receives `activeTab`, `addToast`, `savedLessons`, `supportDocs`, and `setSupportDocs` as props.

## 10. Testing & proof

No backend characterization net (frontend slice). Proof is the Frontend Build + E2E CI gates plus targeted component tests.

- **Existing net stays green (unmodified):** `PlannerTab.test.jsx:194–212` + `:215–223`. These exercise the calendar fetch wiring and the mode button *through* PlannerTab, so a correct extraction keeps them passing.
- **New `frontend/src/__tests__/PlannerCalendar.test.jsx`** (matching the location of `HolidayModal.test.jsx` / `AttemptDrawer.test.jsx`). These directly pin the one behavioral reformulation — the `active`-prop fetch contract — in isolation:
  - smoke: renders without crashing with minimal props (`active=false`).
  - `active=true` → fetches `/api/calendar` on mount.
  - `active=false` → does not fetch.
  - (mock `../services/api` + `global.fetch` per the existing PlannerTab test harness.)
- The verbatim remainder (schedule/holiday/import mutations, date math, JSX) is covered by the existing PlannerTab calendar integration test + the normalized-JSX parity review + Vite build + Playwright E2E smoke — the established mechanism for verbatim moves in this repo. Schedule/holiday interaction tests are intentionally not added here: holiday-add routes through the already-tested `HolidayModal`, and scheduling requires drag/date-selection DOM that would make for fragile assertions with little marginal coverage over the parity review.
- **Frontend test count floor** must not drop (Frontend Build CI enforces a count ≥ floor); this slice only adds tests.
- **Slice proof gates:** Vite build clean + frontend test count ≥ floor + Playwright `health-check.spec.js` E2E smoke (the 9 CI checks).
- **Parity review:** normalized-JSX parity of the moved 600-line block against the pre-PR PlannerTab calendar block (the established Codex-style review step), to confirm byte-for-byte equivalence modulo the prop wiring.

## 11. Out of scope (explicit)

- No hook split (`useCalendar`) and no pure-util split (`calendarDates.js`) — single component only, per Approach A.
- No logic, UX, styling, or endpoint changes.
- No touching the other four `plannerMode` blocks (lesson, assessment, dashboard, tools).
- No `App.jsx` changes.
- No dead-code purge beyond removing the moved calendar code and its now-obsolete slice comment.

## 12. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Fetch-effect timing diverges after extraction | The `active` prop replicates the `activeTab` half of the guard; the conditional render replicates the `plannerMode` half. Equivalence argued in §6 and netted by the existing PlannerTab calendar tests. |
| A calendar helper or state var is referenced outside the calendar block (missed leak) | Audited 2026-05-22: all 15 state vars and all 11 helpers are calendar-cluster-only. The implementation's first step re-runs the grep to confirm against the exact pre-PR file before moving. |
| Inline `api.*` calls inside the JSX break when imports move | `api` is imported directly into the new component; the calendar block's only api calls are `listSupportDocuments`, `parseDocumentForCalendar`, `importCalendarEvents`. |
| `Icon`/`HolidayModal`/`ImportEventsModal` import paths change (was `../components/X`, now `./X`) | New component lives in `components/`, so imports become sibling `./` paths. Mechanical, build-verified. |
| Net behavior drift not caught by unit tests | Vite build + Playwright E2E smoke + normalized-JSX parity review. |

## 13. Expected numbers

- `PlannerTab.jsx`: **7,405 → ~6,675 LOC** (~730 removed).
- New `PlannerCalendar.jsx`: **~700 LOC**.
- Frontend test count: **+3** (new `PlannerCalendar.test.jsx`: smoke + `active=true` fetch + `active=false` no-fetch).
- No backend LOC change; no `App.jsx` change.

## 14. References

- Prior phase plan: `docs/superpowers/plans/2026-05-04-planner-tab-extraction.md` (App.jsx → PlannerTab.jsx, Waves 1–2, CLOSED).
- Canonical scorecard: `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`.
- Handoff naming this lever: `handoff.md` (2026-05-22) §6 "Recommended next lever".
- Wave 2 component precedent: `frontend/src/components/{AttemptDrawer,ShareWithClassesModal,HolidayModal,ImportEventsModal}.jsx` + their `frontend/src/__tests__/*.test.jsx`.
