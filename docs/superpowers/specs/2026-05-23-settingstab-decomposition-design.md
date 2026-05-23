# SettingsTab Decomposition — Design

**Date:** 2026-05-23 · **Status:** Design approved, pending spec review · **Scope:** 5 PRs.
**Lever:** Code-Quality concentrated complexity — `frontend/src/tabs/SettingsTab.jsx` (6,534 LOC), the largest tab-level frontend god-file after the PlannerTab decomposition (now the unanimous next lever per the 2026-05-23 post-Wave-3 re-score).

> **For agentic workers:** execute via the proven PlannerTab pattern — per-section controller-run assembly+rewire scripts (subagent edits timed out on comparable blocks), then two-stage subagent review. Per component: programmatic prop derivation (signature == call site), free-variable scan to zero, byte-for-byte normalized-JSX parity, a smoke test, Vite build + frontend test floor + Playwright E2E.

## 1. Goal

Decompose `SettingsTab.jsx` into 7 focused section components under `frontend/src/components/`, behavior-preserving (zero logic change). SettingsTab becomes a thin orchestrator (~300 LOC: header + sub-tab nav + the 36 state declarations + the single mount effect + 7 `<Settings*/>` calls). Mirrors the completed PlannerTab decomposition (7,405 → 1,453, −80%).

## 2. Approach: per-section pure-forward (Option A) — 3-model validated

Each `{settingsTab === "X" && (...)}` block's JSX moves **verbatim** into `Settings<X>.jsx`; **everything is forwarded as props** (SettingsTab keeps all state + the effect; each section receives the subset it references). No shared hook, no state move-in.

**Why pure-forward with no hook (validated by Claude + Gemini; Codex did not complete in time):**
- **0 parent-body closures** in SettingsTab (verified: no `const X = () =>` / `function X` at 2-space indent) → no shared handlers across sections, so no `useQuestionEditing`-style hook is needed (unlike PlannerTab's lesson/assessment).
- **1 `useEffect` (line 191)** — a top-of-body mount/init fetch for global state (states list, OneRoster, LTI, admin); it stays in SettingsTab, untouched. No section-specific or cross-section effect coupling.
- **No trailing globally-rendered modals** — SettingsTab closes immediately after the `resources` section; section modals (e.g. ApiKeys/ManualSetup in `ai`, OneRoster/Vportal/OnboardingWizard in `classroom`) are triggered **and** rendered within their own section block, so they move with it. The two traps that forced the lesson/assessment fork (staying effect mutating section state; modal triggered-here-rendered-elsewhere) do not exist here.

## 3. Sections (audited @ main `5f8197d`; re-verify per PR — line numbers drift)

| Section | `settingsTab ===` | Lines | ~LOC |
|---|---|---|---|
| general | `"general"` | 295–666 | 372 |
| grading | `"grading"` | 667–918 | 252 |
| ai | `"ai"` | 919–1699 | 781 |
| classroom | `"classroom"` | 1700–4001 | 2,302 |
| privacy | `"privacy"` | 4002–5032 | 1,031 |
| billing | `"billing"` | 5033–5276 | 244 |
| resources | `"resources"` | 5277–6534 | 1,258 |

## 4. Slicing — 5 PRs (smallest → biggest)

| PR | Component(s) | ~LOC out |
|---|---|---|
| **PR1** | `SettingsGeneral` + `SettingsGrading` + `SettingsBilling` (3 small sections, bundled) | ~870 |
| **PR2** | `SettingsAI` | ~781 |
| **PR3** | `SettingsPrivacy` | ~1,031 |
| **PR4** | `SettingsResources` | ~1,258 |
| **PR5** | `SettingsClassroom` (the 2,302-line giant, solo, last) | ~2,302 |

Smallest-first warms the cadence on low-risk sections; the largest/most-coupled (`classroom`, with the most forwarded props) lands last with full context.

## 5. Per-component recipe (each section)

1. **Audit** the section's inner JSX (between `{settingsTab === "X" && (` and its `)}`); derive the prop set **programmatically** = all identifiers it references that are destructured props / state / setters / imports (intersect with the section JSX). Confirm no parent-body closure is referenced (none exist).
2. **Assemble** `frontend/src/components/Settings<X>.jsx` = imports (sibling `./` paths for components, `../services/api` for api) + `export default function Settings<X>({ ...props }) { return ( <verbatim section JSX> ); }`. No state, no handlers, no effects.
3. **Free-variable scan** the new component → **zero** undefined identifiers (every referenced id is a prop, import, or local). Iterate until clean (this is the runtime-completeness guard — a missed prop is a runtime error, not a build error).
4. **Test** `frontend/src/__tests__/Settings<X>.test.jsx` — smoke render with a Proxy `makeProps` (explicit shapes for dereferenced value-props, `vi.fn()` fallback), failing-first then passing.
5. **Rewire** SettingsTab: add the import, replace the section block with `{settingsTab === "X" && (<Settings<X> ...forward exact prop set... />)}`. Remove **nothing else** (all state/effect/modals stay). Generate the call's props from the same source as the signature (signature == call site, verified equal).
6. **Verify**: Vite build clean; full frontend suite green; **normalized-JSX parity** (removed section JSX vs the component's JSX, whitespace-normalized → zero diff); remove any now-dead import from SettingsTab.
7. **Two-stage review** (spec-compliance then code-quality) per PR.

## 6. Behavior preservation

Pure verbatim JSX moves under the existing `{settingsTab === "X" && (...)}` gates (mount/unmount unchanged). All state, the mount effect, and section modals stay in SettingsTab → no reset, no broken effects/modals. No `App.jsx` change (SettingsTab already receives its props from App and forwards them onward).

## 7. Out of scope

- No logic/UX/endpoint changes; no shared hook (none needed); no state move-in.
- No prop-grouping/bundling into object props (Gemini's mitigation for the large prop surface) — it would rewrite the JSX and break verbatim parity. Deferred; flat props accepted (the documented PlannerTab trade-off). A follow-up could group later.
- No `App.jsx` change.

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Missed prop (runtime error, not build error) | Programmatic prop derivation + free-variable scan to zero per component + signature==call-site + two-stage review. |
| A section's state is actually used by another section / the mount effect (cross-coupling, like lesson/assessment) | Pure-forward sidesteps it entirely — all state stays in SettingsTab; nothing is moved. (And the audit found no parent-body closures + no trailing modals.) |
| Large mechanical edit times out a subagent | Controller-run assertion-guarded assembly/anchor scripts; subagents review only. |
| Non-verbatim JSX | Whitespace-normalized parity diff per component PR. |
| Large prop surface (classroom ~40+) | Accepted (documented PlannerTab trade-off); grouping deferred. |

## 9. Expected numbers

- SettingsTab.jsx: 6,534 → ~300 LOC (−95%). Seven new `Settings*.jsx` components (~6,200 LOC relocated into focused, tested units).
- Frontend test count: +~7 (one smoke test per component).
- No `App.jsx` or backend change.

## 10. References

- Completed PlannerTab decomposition (the proven pattern): PRs #456/#458/#459/#463/#465/#467; closeouts; the 2026-05-23 post-Wave-3 re-score (Code Quality 7 → 8) naming SettingsTab the next lever.
- Canonical scorecard: `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`.
- Pattern precedent (pure-forward): `docs/superpowers/specs/2026-05-22-plannertab-lesson-assessment-extraction-design.md` (§ "Design correction").
