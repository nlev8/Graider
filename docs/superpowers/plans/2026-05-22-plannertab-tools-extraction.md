# PlannerTab Tools Tab Extraction Implementation Plan

> **For agentic workers:** Wave 3 slice 2. Large mechanical move — apply edits via deterministic scripts (subagent edits timed out on the calendar removal), then two-stage subagent review (spec-compliance + code-quality). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Extract the Tools tab (reading-level + study guide + flashcards + slides) out of `frontend/src/tabs/PlannerTab.jsx` into a new `frontend/src/components/PlannerTools.jsx`, behavior-preserving, **zero logic change** (no effect to re-express).

**Architecture:** Single component. Owns 24 tool-local state vars; 6 read-only shared props (`config`, `lessonPlan`, `generatedAssignment`, `globalAINotes`, `uploadedDocs`, `addToast`); imports `Icon` + `api`; 8 raw fetches verbatim.

**Tech Stack:** React 18 + Vite + Vitest. Frontend slice — proof = Vite build + frontend test floor + Playwright E2E + new `PlannerTools.test.jsx` + normalized-JSX parity.

**Spec:** `docs/superpowers/specs/2026-05-22-plannertab-tools-extraction-design.md`

---

## File Structure

- **Create** `frontend/src/components/PlannerTools.jsx` (~835 LOC).
- **Create** `frontend/src/__tests__/PlannerTools.test.jsx`.
- **Modify** `frontend/src/tabs/PlannerTab.jsx` — remove 24 state vars (597-615 + 835-847) + the tools JSX block (5683-6488); add import + `<PlannerTools …/>`. 6,680 → ~5,850 LOC.
- **Untouched:** `App.jsx` (already passes the 6 shared props).

### Exact source regions (current line numbers @ `0bb8f06`; **re-verify in Task 1 — they drift**)

| Region | Lines |
|---|---|
| study/flashcard/slide state (+ `//` section comments) | 597–615 (keep 596 `previewShowAnswers`) |
| RL slice comment + rl state | 835–847 |
| Tools JSX block | 5683 (`{/* Tools Mode */}`) → 6488 (`)}`); inner `<div className="fade-in">` 5685 → `</div>` 6487 |

### Exact import list for the new component

```jsx
import React, { useState } from "react";
import Icon from "./Icon";
import * as api from "../services/api";
```

Nothing else (8 raw fetches use global `fetch`; only `<Icon>`/`<React.Fragment>` components; no `getAuthHeaders`).

---

## Tasks

### Task 1: Pre-flight re-audit (controller, read-only)

- [ ] **Step 1:** Confirm branch `feature/plannertab-tools-extraction`.
- [ ] **Step 2:** Re-confirm all 24 tool-local state vars are referenced ONLY in the tools block (Python isolation scan from the spec §3; the `flashcards` string-literal hits in the dashboard are not the var). If any leaks, it must become a forwarded prop, not moved — STOP and re-scope.
- [ ] **Step 3:** Re-confirm the 6 shared props are read-only in the block (no `setConfig`/`setLessonPlan`/`setGeneratedAssignment`/`setGlobalAINotes`/`setUploadedDocs` calls inside 5685-6487).
- [ ] **Step 4:** Capture current exact line numbers for the three regions (anchors: `// Study guide`, `* Reading-level (RL) tools slice`, `{/* Tools Mode */}`, `{/* AttemptDrawer`).
- [ ] No commit.

### Task 2: Create `PlannerTools.jsx` + test (assembly script)

- [ ] **Step 1:** Write `frontend/src/__tests__/PlannerTools.test.jsx` (failing first):

```jsx
import React from 'react';
import { render } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PlannerTools from '../components/PlannerTools';

vi.mock('../services/api', () => ({
  adjustReadingLevel: vi.fn().mockResolvedValue({ adjusted_text: 'x', reading_level_estimate: '6' }),
  extractTextFromFile: vi.fn().mockResolvedValue({ text: '' }),
  listResources: vi.fn().mockResolvedValue({ resources: [] }),
  loadResource: vi.fn().mockResolvedValue({ resource: {} }),
  saveResource: vi.fn().mockResolvedValue({ status: 'saved' }),
}));

const makeProps = (overrides = {}) => ({
  config: { subject: 'Math', grade: '8', globalAINotes: '' },
  lessonPlan: null,
  generatedAssignment: null,
  globalAINotes: '',
  uploadedDocs: [],
  addToast: vi.fn(),
  ...overrides,
});

describe('PlannerTools', () => {
  beforeEach(() => { global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) }); });

  it('smoke: renders without crashing', () => {
    render(<PlannerTools {...makeProps()} />);
  });

  it('renders the reading-level input', () => {
    const { container } = render(<PlannerTools {...makeProps()} />);
    expect(container.querySelector('textarea, input')).toBeTruthy();
  });
});
```

- [ ] **Step 2:** Run `cd frontend && npx vitest run src/__tests__/PlannerTools.test.jsx` → FAIL (no module).
- [ ] **Step 3:** Create `frontend/src/components/PlannerTools.jsx` via a deterministic assembly script: header (the 3 imports + the `PlannerTools({ … 6 props })` signature), then the 24 state declarations copied verbatim from PlannerTab (597-600, 602-605, 607-615, 840-847 — the decl lines only, dropping the `//`/`/* */` comments), then `return (` + the inner tools JSX (5685-6487) copied verbatim + `);` + `}`. **No logic changes whatsoever.**
- [ ] **Step 4:** `cd frontend && npx vitest run src/__tests__/PlannerTools.test.jsx` → PASS; `npm run build` → clean. If `X is not defined`: the block references an identifier outside `{config, lessonPlan, generatedAssignment, globalAINotes, uploadedDocs, addToast}` + imports — trace it; if it's shared App state, forward it as a prop (do not localize).
- [ ] **Step 5:** Commit (component + test). Discard `backend/static` build artifacts after (`git restore backend/static && git clean -fd backend/static`).

### Task 3: Rewire PlannerTab (anchor script)

- [ ] **Step 1:** Add `import PlannerTools from "../components/PlannerTools";`.
- [ ] **Step 2:** Replace the tools JSX block (`{/* Tools Mode */}` → its `)}`) with:

```jsx
                  {/* Tools Mode */}
                  {plannerMode === "tools" && (
                    <PlannerTools
                      config={config}
                      lessonPlan={lessonPlan}
                      generatedAssignment={generatedAssignment}
                      globalAINotes={globalAINotes}
                      uploadedDocs={uploadedDocs}
                      addToast={addToast}
                    />
                  )}
```

- [ ] **Step 3:** Remove the study/flashcard/slide state block (597-615, incl. the 3 `//` comments; **keep 596**) and the RL comment + rl state (835-847).
- [ ] **Step 4:** `cd frontend && npm run build` → clean (a dangling reference means a moved identifier is still used in PlannerTab — investigate, do not re-add state). Confirm no newly-dead imports (`Icon`/`api` stay used elsewhere).
- [ ] **Step 5:** `cd frontend && npx vitest run` → full suite passes (count = prior floor + the new PlannerTools tests). Confirm removals: `grep -nE "const \[(studyGuide|flashcards|slideDeck|rlInput),|plannerMode === \"tools\"" frontend/src/tabs/PlannerTab.jsx` shows only the `<PlannerTools>` conditional render, no state decls.
- [ ] **Step 6:** Commit (PlannerTab only). Discard `backend/static`.

### Task 4: Verification + normalized-JSX parity (controller)

- [ ] **Step 1:** `cd frontend && npx vitest run && npm run build` → all green.
- [ ] **Step 2:** Parity diff — the inner tools JSX removed from PlannerTab (from the pre-rewire commit) vs PlannerTools' JSX, whitespace-normalized:

```bash
cd /Users/alexc/Downloads/Graider/frontend/src
git show <pre-rewire-sha>:tabs/PlannerTab.jsx | sed -n '5685,6487p' > /tmp/removed.jsx
sed -n '/^  return (/,/^  );/p' components/PlannerTools.jsx | sed '1d;$d' > /tmp/comp.jsx
diff <(tr -d '[:space:]' < /tmp/removed.jsx) <(tr -d '[:space:]' < /tmp/comp.jsx) && echo "JSX PARITY OK"
```

Expect empty diff. (Substitute the pre-rewire commit + Task-1 line numbers.)
- [ ] **Step 3:** No commit.

### Task 5: Two-stage review + PR + merge

- [ ] **Step 1:** Dispatch spec-compliance reviewer (verify interface, 24 state moved, 6 read-only props forwarded, verbatim move via parity, no App.jsx change, no behavior change). Fix any findings.
- [ ] **Step 2:** Dispatch code-quality reviewer (cleanliness, no orphaned imports/props, no stray whitespace). Fix any findings.
- [ ] **Step 3:** Push; open PR with spec+plan+impl; watch the 9 CI checks; merge when green (autonomous merge authorized).

---

## Verification per PR

- `cd frontend && npx vitest run` — pass (floor + new tests).
- `cd frontend && npm run build` — clean.
- 9 CI gates green.
- Normalized-JSX parity confirmed.

## Expected numbers

- `PlannerTab.jsx`: 6,680 → ~5,850 LOC (~830 removed).
- New `PlannerTools.jsx`: ~835 LOC.
- Frontend test count: +2-3.
- No `App.jsx` / backend change.
