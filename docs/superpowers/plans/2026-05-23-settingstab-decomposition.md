# SettingsTab Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. **5 impl PRs**, each a per-section pure-forward extraction applied via the **Per-Section Recipe** below (controller-run assertion-guarded assembly+rewire scripts — subagent edits timed out on comparable PlannerTab blocks — then two-stage subagent review). **Each PR re-audits its own section boundaries; line numbers shift after every prior PR.** Steps use checkbox (`- [ ]`) syntax.

**Goal:** Decompose `frontend/src/tabs/SettingsTab.jsx` (6,534 LOC) into 7 focused `Settings*.jsx` section components, behavior-preserving; SettingsTab becomes a ~300-LOC orchestrator.

**Architecture:** Per-section **pure-forward** (the shipped PlannerLesson/PlannerDashboard/PlannerAssessment pattern). Each `{settingsTab === "X" && (...)}` block's JSX moves verbatim into `Settings<X>.jsx`; ALL state + the single mount effect + section modals stay in SettingsTab; each component receives the props it references (forwarded). No shared hook, no state move-in (0 parent-body closures, 1 global effect, no trailing modals — validated 3-model).

**Tech Stack:** React 18 + Vite + Vitest. Frontend slice — proof = Vite build + frontend test floor + Playwright E2E + per-component smoke test + free-variable scan + normalized-JSX parity.

**Spec:** `docs/superpowers/specs/2026-05-23-settingstab-decomposition-design.md`

---

## File Structure

- **Create** (7 components): `frontend/src/components/Settings{General,Grading,Billing,AI,Privacy,Resources,Classroom}.jsx` + a `frontend/src/__tests__/Settings<X>.test.jsx` per component.
- **Modify** `frontend/src/tabs/SettingsTab.jsx` across all 5 PRs (replace each section block with a `<Settings<X> .../>` call; keep all state/effect/modals). 6,534 → ~300 LOC.
- **Untouched:** `frontend/src/App.jsx`.

### Sections (current line numbers @ `5f8197d`; **re-verify in each PR — they drift**)

| Section | `settingsTab ===` | Lines | ~LOC | PR |
|---|---|---|---|---|
| general | `"general"` | 295–666 | 372 | PR1 |
| grading | `"grading"` | 667–918 | 252 | PR1 |
| billing | `"billing"` | 5033–5276 | 244 | PR1 |
| ai | `"ai"` | 919–1699 | 781 | PR2 |
| privacy | `"privacy"` | 4002–5032 | 1,031 | PR3 |
| resources | `"resources"` | 5277–6534 | 1,258 | PR4 |
| classroom | `"classroom"` | 1700–4001 | 2,302 | PR5 |

---

## Per-Section Recipe (apply for every Settings<X>)

This is the concrete, repeatable procedure each PR's task follows. `<X>` = the section name (e.g. `AI`), `<x>` = the `settingsTab` value (e.g. `"ai"`).

**R1 — Locate (controller, read-only).** Find the block: `grep -n '{settingsTab === "<x>" && (' frontend/src/tabs/SettingsTab.jsx`. The block runs from that conditional line to its matching `)}`; the inner JSX is from the line after `&& (` to the line before `)}`. Capture the exact inner-JSX line range.

**R2 — Write the failing smoke test** `frontend/src/__tests__/Settings<X>.test.jsx`:
```jsx
import React from 'react';
import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Settings<X> from '../components/Settings<X>';

vi.mock('../services/api', () => new Proxy({}, { get: () => vi.fn().mockResolvedValue({}) }));

// Explicit shapes for props the section JSX dereferences (config.*, arrays it .maps,
// objects it indexes); everything else (handlers/setters) auto-stubs via the Proxy.
const base = () => ({
  config: { subject: 'Math', grade_level: '8', state: 'FL', extraction_mode: 'structured' },
  apiKeys: {},
  // add any other dereferenced value-props discovered when the smoke test first runs
});
const makeProps = (over = {}) => new Proxy({ ...base(), ...over }, {
  get(t, p) { if (p in t) return t[p]; if (typeof p === 'symbol') return undefined; return vi.fn(); },
  has() { return true; },
});

describe('Settings<X>', () => {
  it('smoke: renders without crashing', () => {
    const { container } = render(<Settings<X> {...makeProps()} />);
    expect(container.firstChild).toBeTruthy();
  });
});
```
Run `cd frontend && npx vitest run src/__tests__/Settings<X>.test.jsx` → FAIL (no module). If, after the component exists (R4), the smoke test throws `Cannot read properties of undefined`, add the offending value-prop's safe shape to `base()` and re-run (iterate).

**R3 — Assemble the component (controller assembly script).** Programmatically build `frontend/src/components/Settings<X>.jsx`:
- Read SettingsTab; extract the inner section JSX (the R1 range).
- Derive the prop set = the candidate identifiers (destructured props ∪ all `useState` value+setter names ∪ imported component/util names) **intersected with** the identifiers actually referenced in the section JSX (`(?<![\w.])NAME(?![\w])`).
- Derive imports = SettingsTab imports whose symbol appears in the JSX, with `../components/` rewritten to sibling `./`.
- Emit: `import React from "react";` + used imports + `export default function Settings<X>({ ...sorted props... }) {` + `  return (` + verbatim JSX + `\n  );\n}`. Write the prop list to a temp file for R5.
- **No state, no handlers, no effects in the component.**

**R4 — Verify the component.** `cd frontend && npm run build` (clean) and the **free-variable scan**: every identifier the component references must be a prop, an import, a JS/React builtin, or a local declared inside the JSX (map/arrow params). Script:
```bash
cd frontend/src && python3 - <<'PY'
import re
comp=open("components/Settings<X>.jsx",encoding="utf-8").read()
props=set(open("/tmp/settings_<x>_props.txt").read().split("\n"))
known=set(props)|{"React","props"}
for m in re.finditer(r'import\s+(?:\* as )?(\w+)|import\s+\{([^}]+)\}',comp):
    if m.group(1): known.add(m.group(1))
    if m.group(2): known|={x.strip() for x in m.group(2).split(",")}
for m in re.finditer(r'\b(?:const|let|var)\s+([A-Za-z_]\w*)',comp): known.add(m.group(1))
for m in re.finditer(r'\[([A-Za-z_]\w*),\s*(set[A-Za-z_]\w*)\]',comp): known|={m.group(1),m.group(2)}
for m in re.finditer(r'\(([^)]*)\)\s*=>',comp):
    for p in m.group(1).split(","):
        p=p.strip().lstrip("{").rstrip("}").split("=")[0].split(":")[0].strip()
        if re.fullmatch(r'[A-Za-z_]\w*',p): known.add(p)
known|=set("Object Array String Number Boolean Math JSON Date Map Set Promise parseInt parseFloat isNaN console window document fetch setTimeout encodeURIComponent decodeURIComponent confirm alert FileReader FormData Blob URL navigator true false null undefined async await new typeof return if else for while of in this map filter forEach reduce includes split join slice".split())
called=set(re.findall(r'(?<![\w.])([a-z][A-Za-z0-9_]*)\s*\(',comp))
free=sorted(c for c in called if c not in known and c not in {"minmax","repeat","rgba","calc","url","catch","function","if","for","while","switch","return","await","typeof","gradient","state","var"})
print("free CALLED:", free if free else "(NONE - clean)")
PY
```
Any non-false-positive free identifier = a missed prop: add it to the component signature + the prop file, re-run until "(NONE - clean)". Run the smoke test → PASS. Commit (component + test). Discard build artifacts: `git restore backend/static && git clean -fd backend/static`.

**R5 — Rewire SettingsTab (controller anchor script).** Add `import Settings<X> from "../components/Settings<X>";`. Replace the section block (`{settingsTab === "<x>" && (` … its `)}`) with:
```jsx
            {settingsTab === "<x>" && (
              <Settings<X>
                {/* one  name={name}  line per prop, generated from the SAME temp file as the signature */}
              />
            )}
```
Remove **nothing else** (all state/effect/modals stay). Then `npm run build` (clean) + full suite green + remove any now-dead import from SettingsTab.

**R6 — Parity + review.** Normalized-JSX parity: the removed section JSX (from the pre-rewire commit) vs the component's `return (...)` body, whitespace-normalized → zero diff:
```bash
git show <pre-rewire-sha>:frontend/src/tabs/SettingsTab.jsx | sed -n '<innerStart>,<innerEnd>p' > /tmp/b.jsx
sed -n '/^  return (/,/^  );/p' frontend/src/components/Settings<X>.jsx | sed '1d;$d' > /tmp/a.jsx
diff <(tr -d '[:space:]' < /tmp/b.jsx) <(tr -d '[:space:]' < /tmp/a.jsx) && echo "PARITY OK"
```
Confirm signature props == call-site props (sorted, equal). Commit (SettingsTab only). Two-stage subagent review (spec-compliance then code-quality); fix findings.

---

## Tasks

### Task 1 — PR1: SettingsGeneral + SettingsGrading + SettingsBilling (3 small sections)

**Files:** Create `frontend/src/components/Settings{General,Grading,Billing}.jsx` + their tests; Modify `frontend/src/tabs/SettingsTab.jsx`.

- [ ] **Step 1:** Branch off `main`: `feature/settingstab-small-sections`.
- [ ] **Step 2:** For `general` (`<x>="general"`, ~295–666), `grading` (`"grading"`, ~667–918), and `billing` (`"billing"`, ~5033–5276): run the **Per-Section Recipe R1–R4** for each, producing `SettingsGeneral.jsx`, `SettingsGrading.jsx`, `SettingsBilling.jsx` + tests. Commit the three components + tests together.
- [ ] **Step 3:** Run **R5** for all three (add 3 imports; replace the 3 section blocks with `<SettingsGeneral/>` / `<SettingsGrading/>` / `<SettingsBilling/>` calls). Build clean + full suite green.
- [ ] **Step 4:** Run **R6** parity for all three (zero diff each) + remove any dead imports. Commit the SettingsTab rewire.
- [ ] **Step 5:** Two-stage review; fix findings; push; open PR1; watch the 9 CI checks; merge when green.

### Task 2 — PR2: SettingsAI

**Files:** Create `frontend/src/components/SettingsAI.jsx` + test; Modify `frontend/src/tabs/SettingsTab.jsx`.

- [ ] **Step 1:** Re-sync `main` (PR1 merged); branch `feature/settingstab-ai`.
- [ ] **Step 2:** Run the **Per-Section Recipe R1–R6** for `ai` (`<x>="ai"`; re-locate boundaries — they shifted after PR1). Note: the `ai` section uses `apiKeys.*` and the `showApiKeys`/`showManualSetup` modal states + `config.extraction_mode`/`config.ensemble*` — all forwarded; its modals render within the section.
- [ ] **Step 3:** Two-stage review; fix; push; open PR2; merge when green.

### Task 3 — PR3: SettingsPrivacy

**Files:** Create `frontend/src/components/SettingsPrivacy.jsx` + test; Modify `frontend/src/tabs/SettingsTab.jsx`.

- [ ] **Step 1:** Re-sync `main` (PR2 merged); branch `feature/settingstab-privacy`.
- [ ] **Step 2:** Run the **Per-Section Recipe R1–R6** for `privacy` (`<x>="privacy"`; re-locate boundaries).
- [ ] **Step 3:** Two-stage review; fix; push; open PR3; merge when green.

### Task 4 — PR4: SettingsResources

**Files:** Create `frontend/src/components/SettingsResources.jsx` + test; Modify `frontend/src/tabs/SettingsTab.jsx`.

- [ ] **Step 1:** Re-sync `main` (PR3 merged); branch `feature/settingstab-resources`.
- [ ] **Step 2:** Run the **Per-Section Recipe R1–R6** for `resources` (`<x>="resources"`; re-locate boundaries). Resources renders some modals (~original L5844) — they are within the section block and move with it; confirm via the free-var scan + parity.
- [ ] **Step 3:** Two-stage review; fix; push; open PR4; merge when green.

### Task 5 — PR5: SettingsClassroom (the 2,302-line giant, solo)

**Files:** Create `frontend/src/components/SettingsClassroom.jsx` + test; Modify `frontend/src/tabs/SettingsTab.jsx`.

- [ ] **Step 1:** Re-sync `main` (PR4 merged); branch `feature/settingstab-classroom`.
- [ ] **Step 2:** Run the **Per-Section Recipe R1–R6** for `classroom` (`<x>="classroom"`; re-locate boundaries). Largest prop surface (Clever/OneRoster/Vportal/OnboardingWizard modal states + their handlers, all forwarded). Expect the most iterations of the free-var scan; the OnboardingWizard/OneRoster/Vportal modals render within the classroom block and move with it.
- [ ] **Step 3:** Two-stage review; fix; push; open PR5; merge when green.
- [ ] **Step 4:** Confirm end state: `wc -l frontend/src/tabs/SettingsTab.jsx` ≈ ~300; no inline `settingsTab === "X"` JSX blocks remain (only the 7 `<Settings*/>` conditional renders).

---

## Verification per PR

- `cd frontend && npx vitest run` — pass (floor + new smoke tests).
- `cd frontend && npm run build` — clean.
- 9 CI gates green; two-stage review passed.
- Per component: free-variable scan zero + normalized-JSX parity zero diff + signature == call-site.

## Risks

| Risk | Mitigation |
|---|---|
| Missed prop (runtime error, not build error) | Programmatic prop derivation + free-var scan to zero + signature==call-site + two-stage review. |
| Section line numbers drift after each PR | Each task re-locates its block via `grep '{settingsTab === "<x>"'` (Recipe R1). |
| Large `classroom` edit times out a subagent | Controller-run assertion-guarded scripts; subagents review only. |
| Non-verbatim JSX | Whitespace-normalized parity diff per component. |
| Dead imports orphaned in SettingsTab as sections leave | R5 removes now-dead imports each PR (PlannerTab precedent). |

## Expected numbers

- SettingsTab.jsx: 6,534 → ~300 LOC (−95%).
- 7 new `Settings*.jsx` components (~6,200 LOC relocated into focused tested units) + 7 smoke tests.
- No `App.jsx` / backend change.
