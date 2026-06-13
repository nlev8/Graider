# Code Quality 7 → 8 — Function/File Split Campaign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flip the hardening rubric's Code Quality dimension 7 → 8 — **no file >2,500 LOC, no
function >200 LOC** across `backend/` + `frontend/src/` (strict, no exceptions) —
behavior-preservingly, taking overall 7.85 → ~7.95.

**Architecture:** Split 1 oversized file + 127 oversized functions (47 backend, 80 frontend) into
focused units. Each split is one PR. Bulk (~112 fns + the file) is **Class A** behavior-preserving
extraction proven by byte-identity + existing nets → auto-merge on green. A ~15-function
**grading-critical** subset is **Class B** → golden-grading regression + opus + Codex gate, manual
merge. Nine domain-clustered waves, run sequentially.

**Tech Stack:** Python 3 (`ast` for the BE scan + free-var checks), `@babel/parser` (FE scan),
pytest + existing golden/prompt-snapshot nets, vitest + Vite build, `codex exec` for the adversarial
pass, GitNexus for reindex.

**Spec:** `docs/superpowers/specs/2026-06-13-cq-7-to-8-design.md` (approved 2026-06-13).
**Reuses the proven protocol from:** `docs/superpowers/plans/2026-06-04-code-quality-7-function-split-campaign.md`.

---

## Why per-function code is NOT pre-written in this plan

The 6→7 campaign plan states it directly: *"recon line ranges drift; re-validate against the live
file (they drift each merge)."* Pre-writing extraction diffs for 127 functions would be stale after
the first merge in any wave. Instead this plan pins **the procedure** (exact scripts, exact
commands, exact gates) and **the per-target recon** (file, function, LOC-over, known hazards). The
executing subagent generates the actual move against the live file using the byte-verbatim
extraction script in §Protocol-BE / §Protocol-FE. This matches repo precedent and is the only
correct approach given line-drift.

---

## Definition of Done (campaign)

- [ ] `python scripts/cq_scan_backend.py` → **0** functions >200 LOC.
- [ ] `node scripts/cq_scan_frontend.mjs` → **0** functions >200 LOC.
- [ ] `find backend frontend/src \( -name '*.py' -o -name '*.jsx' -o -name '*.js' \) | xargs wc -l | awk '$1>2500'` → **empty**.
- [ ] Full `pytest -q --ignore=tests/load` green on `main`; `cd frontend && npx vitest run` green; `npm run build` green.
- [ ] GitNexus reindexed (`npx gitnexus analyze --embeddings --skip-agents-md`).
- [ ] Re-score commit: anchors doc CQ row 7→8 + overall 7.85→~7.95, opus + Codex gated.

---

## Task 0 — Wave 0: commit the reproducible scan scripts

**Files:**
- Create: `scripts/cq_scan_backend.py`
- Create: `scripts/cq_scan_frontend.mjs`
- Create: `tests/test_cq_scan.py`

- [ ] **Step 1: Write the failing test for the backend scan**

`tests/test_cq_scan.py`:
```python
import subprocess, sys, textwrap, pathlib

def test_backend_scan_flags_over_200(tmp_path):
    f = tmp_path / "big.py"
    body = "\n".join(f"    x{i} = {i}" for i in range(210))
    f.write_text(f"def huge():\n{body}\n")
    out = subprocess.run(
        [sys.executable, str(pathlib.Path("scripts/cq_scan_backend.py")), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert "huge" in out.stdout
    assert out.returncode == 1  # nonzero when offenders exist

def test_backend_scan_clean_is_zero_exit(tmp_path):
    (tmp_path / "ok.py").write_text("def small():\n    return 1\n")
    out = subprocess.run(
        [sys.executable, str(pathlib.Path("scripts/cq_scan_backend.py")), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert out.returncode == 0
    assert out.stdout.strip() == "" or "0 functions" in out.stdout
```

- [ ] **Step 2: Run it, verify it fails** (`pytest tests/test_cq_scan.py -q` → FAIL, script missing).

- [ ] **Step 3: Write `scripts/cq_scan_backend.py`**

```python
#!/usr/bin/env python3
"""CQ level-8 backend scan: flag any function whose physical span >200 LOC.
Usage: cq_scan_backend.py [root1 root2 ...]  (default: backend)
Exit 1 if any offender, 0 if clean. Definition: end_lineno - lineno + 1 (decorators excluded,
matching Python's FunctionDef.lineno)."""
import ast, os, sys

LIMIT = 200

def scan(roots):
    rows = []
    for root in roots:
        for dp, _, files in os.walk(root):
            if "__pycache__" in dp:
                continue
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                p = os.path.join(dp, fn)
                try:
                    tree = ast.parse(open(p, encoding="utf-8").read())
                except Exception:
                    continue
                for n in ast.walk(tree):
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        loc = (n.end_lineno or n.lineno) - n.lineno + 1
                        if loc > LIMIT:
                            rows.append((loc, p, n.name))
    return sorted(rows, reverse=True)

if __name__ == "__main__":
    roots = sys.argv[1:] or ["backend"]
    rows = scan(roots)
    for loc, p, name in rows:
        print(f"{loc:5d}  {p}::{name}")
    print(f"\n{len(rows)} functions >{LIMIT} LOC", file=sys.stderr)
    sys.exit(1 if rows else 0)
```

- [ ] **Step 4: Write `scripts/cq_scan_frontend.mjs`**

```javascript
#!/usr/bin/env node
// CQ level-8 frontend scan: flag any function whose line span >200 LOC under frontend/src.
// Exit 1 if any offender, 0 if clean. Run from frontend/ (needs @babel/parser).
import fs from "node:fs";
import path from "node:path";
import { parse } from "@babel/parser";

const LIMIT = 200;
const root = process.argv[2] || "src";
const rows = [];

function len(node) {
  return node.loc ? node.loc.end.line - node.loc.start.line + 1 : 0;
}
function visit(node, hint) {
  if (!node || typeof node !== "object") return;
  if (Array.isArray(node)) return node.forEach((n) => visit(n, hint));
  if (node.type) {
    const isFn =
      node.type === "FunctionDeclaration" ||
      node.type === "FunctionExpression" ||
      node.type === "ArrowFunctionExpression";
    if (isFn) {
      const nm =
        node.type === "FunctionDeclaration" && node.id ? node.id.name : hint || "(anon)";
      const L = len(node);
      if (L > LIMIT) rows.push([L, node.__file, nm]);
    }
  }
  for (const k in node) {
    if (["loc", "start", "end", "leadingComments", "trailingComments"].includes(k)) continue;
    let h = hint;
    if (node.type === "VariableDeclarator" && node.id && node.id.name) h = node.id.name;
    visit(node[k], h);
  }
}
function walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (e.name === "node_modules") continue;
      walk(p);
    } else if (/\.(jsx?|tsx?)$/.test(e.name)) {
      let ast;
      try {
        ast = parse(fs.readFileSync(p, "utf8"), { sourceType: "module", plugins: ["jsx"] });
      } catch {
        continue;
      }
      const tag = (n) => {
        if (n && typeof n === "object") {
          if (n.type) n.__file = p;
          for (const k in n) if (k !== "__file") tag(n[k]);
        }
      };
      tag(ast);
      visit(ast, null);
    }
  }
}
walk(root);
const seen = new Set();
const uniq = rows.filter((r) => {
  const k = r.join("::");
  return seen.has(k) ? false : (seen.add(k), true);
});
uniq.sort((a, b) => b[0] - a[0]);
for (const [L, f, n] of uniq) console.log(`${String(L).padStart(5)}  ${f}::${n}`);
console.error(`\n${uniq.length} functions >${LIMIT} LOC`);
process.exit(uniq.length ? 1 : 0);
```

- [ ] **Step 5: Run both for real, confirm they reproduce tonight's numbers**

Run: `python scripts/cq_scan_backend.py` → expect `47 functions >200 LOC`.
Run: `cd frontend && node ../scripts/cq_scan_frontend.mjs` → expect `80 functions >200 LOC`.
Run: `pytest tests/test_cq_scan.py -q` → PASS.

- [ ] **Step 6: Commit** (Class A)

```bash
git checkout -b refactor/cq8-00-scan-scripts
git add scripts/cq_scan_backend.py scripts/cq_scan_frontend.mjs tests/test_cq_scan.py
git commit -m "tooling(cq): committed level-8 LOC scan scripts (BE ast + FE babel)"
```
Push, PR, auto-merge on green.

---

## Protocol-BE — backend function split (reused from the 6→7 campaign, threshold now 200)

Apply to every backend Tier A function. **Re-validate line ranges against the live file first.**

1. **Recon:** read the function. Find a natural seam — a self-contained block (a loop body, a
   branch, a build-phase) of ~50–120 LOC whose extraction drops the parent ≤200. Targets are only
   3–94 LOC over the line, so **usually ONE extraction suffices** (unlike the 6→7 giants).
2. **AST free-variable check** on the proposed helper: every loaded name must resolve to a param,
   module global, builtin, inline import, except-binding, or nested def. Zero unresolved. Script:
   ```python
   import ast
   src = open("<file>").read(); tree = ast.parse(src)
   # locate the helper node, collect ast.Name loads vs the function's args/assigned names
   ```
3. **Byte-verbatim extraction** (never hand-edit large moves):
   - 4-space body block → moved block **byte-identical** (`md5` of moved lines == `md5` from
     `git show main:<file>` slice).
   - 8-space block (inside try/if/loop) → **uniform de-indent-by-4**, proven *reversible*
     (re-indent reproduces original exactly).
4. **Gotchas (already hit in 6→7 — do NOT repeat):**
   - **Route helpers insert ABOVE the decorator stack** (`@route`/`@require_teacher`/
     `@handle_route_errors`/`@limiter.limit`) — inserting between decorator and `def` rebinds them → 500s.
   - **`continue`→`return`** when an outer-loop `continue` moves into a helper (iff nothing follows
     the chain in the loop body). Inner-loop `continue` stays.
   - **`elif`→`if`** when a moved block starts mid-`if/elif` chain.
   - **Shared-exception state:** a block whose vars are read by a later `except` can't be naively
     extracted — leave it inline, find another seam.
   - **Helper still >200:** split the chain into two with sequential dispatch in the parent.
5. **Nets:** the function's net (golden/characterization/unit) green → full
   `pytest -q --ignore=tests/load` (~5966 passed, 16 skipped baseline) → `ruff check` → `bandit -q -r <file>`.
6. **Pin scan:** `grep -rn "<file>" tests/test_sis_alerting.py` — if pinned, update `(file,line)`
   tuples with documenting comments and prove the pin test passes.
7. **Re-scan:** `python scripts/cq_scan_backend.py` shows the function gone from the list.
8. **Tier gate:** Class A → byte-proof + nets + full suite → merge on green CI. (Branch:
   `refactor/cq8-NN-<short-name>`.)

---

## Protocol-FE — frontend function/component split

Apply to every frontend Tier A function. JSX has no byte-identity proof (you extract a JSX subtree
into a child component + pass props), so the proof is **render-equivalence + green tests**.

1. **Recon:** classify the offender:
   - **Component (>200 LOC render fn):** extract a cohesive JSX subtree into a child component in a
     sibling file (follow the established `components/<name>/*` or `tabs/<area>/*` split pattern the
     campaign already uses). The child receives exactly the props it reads — no behavior change.
   - **Hook (`useX` >200 LOC):** extract a cohesive group of related state+effects into a sub-hook
     (`useXType.js`) that the parent hook composes. Same return shape.
   - **Handler factory / `(anon)` default export:** extract helper functions or sub-sections.
2. **Pure-prop discipline:** the extracted child/hook reads only what's passed in; no new fetches,
   no reordered effects, no changed memo deps. The "moving, not adding" tell must answer *moving*.
3. **Nets:**
   - The component's existing `frontend/src/__tests__/<Name>.mount.test.jsx` (or `.test.jsx`) stays
     green. **If none exists, add a mount test in the same PR** that renders the component with
     representative props and asserts key text/roles present (this becomes the render-equivalence net).
   - `cd frontend && npx vitest run` green; `npm run build` green.
4. **Re-scan:** `cd frontend && node ../scripts/cq_scan_frontend.mjs` shows the function gone.
5. **Tier gate:** Class A → green nets + build + opus + Codex pure-move check → merge on green.

**Worked FE example (representative — `Sidebar.jsx::Sidebar`, 245 LOC):**

- [ ] Step A — read `frontend/src/components/Sidebar.jsx`; identify the largest cohesive JSX block
  (e.g. the nav-section list rendering, or a settings/footer subtree) ~60+ LOC.
- [ ] Step B — if `frontend/src/__tests__/Sidebar.mount.test.jsx` is absent, write it:
  ```jsx
  import { render, screen } from "@testing-library/react";
  import Sidebar from "../components/Sidebar.jsx";
  test("Sidebar renders nav sections", () => {
    render(<Sidebar /* representative props */ />);
    expect(screen.getByRole("navigation")).toBeInTheDocument();
  });
  ```
  Run `npx vitest run src/__tests__/Sidebar.mount.test.jsx` → PASS (pins current render).
- [ ] Step C — extract the block to `frontend/src/components/sidebar/SidebarNavSection.jsx`,
  passing exactly the props/handlers it reads; replace the inline block with `<SidebarNavSection ... />`.
- [ ] Step D — `npx vitest run` green; `npm run build` green; `node ../scripts/cq_scan_frontend.mjs`
  no longer lists `Sidebar`.
- [ ] Step E — commit `refactor/cq8-NN-sidebar`, push, auto-merge on green.

---

## Waves 1–7 — Tier A (Class A, auto-merge on green)

Each row is one PR via Protocol-BE or Protocol-FE. Branch `refactor/cq8-NN-<short>`. Reindex
GitNexus once per wave (not per PR). Re-validate LOC/line ranges against the live file before each
split. Dispatch ~6–8 PRs per wave as parallel worktree subagents (template at the end).

### Wave 1 — assistant_tools_reports file split + reports functions (BE)
- [ ] **File split:** `backend/services/assistant_tools_reports.py` (2,723 LOC) → split into a
  package `backend/services/assistant_tools_reports/` (e.g. `__init__.py` re-exporting public
  symbols, plus topical modules by report type) so the largest module is <2,500 (ideally <2,000).
  Pure-move of whole functions; all imports preserved via `__init__` re-export. Net: every test that
  `grep -rln "assistant_tools_reports" tests/` surfaces stays green.
- [ ] `assistant_tools_reports.py::_parse_curriculum_map_for_dates` (235) — Protocol-BE.
- [ ] `routes/assistant_routes.py::_run_assistant_stream` (273) — Protocol-BE.
- [ ] `services/assistant_tools_student.py::_execute_student_removal` (204) — Protocol-BE.

### Wave 2 — interactive math components (FE)
- [ ] `components/InteractiveCoordinatePlane.jsx::InteractiveCoordinatePlane` (277)
- [ ] `components/InteractiveBoxPlot.jsx::InteractiveBoxPlot` (245)
- [ ] `components/InteractiveFunctionGraph.jsx::InteractiveFunctionGraph` (237)
- [ ] `components/InteractiveTransformations.jsx::InteractiveTransformations` (232)
- [ ] `components/InteractiveProbabilityTree.jsx::InteractiveProbabilityTree` (214)
- [ ] `components/InteractiveNumberLine.jsx::InteractiveNumberLine` (213)
- [ ] `components/InteractiveProtractor.jsx::InteractiveProtractor` (211)
- [ ] `components/CoordinateInput.jsx::CoordinateInput` (233)

(Each via Protocol-FE — extract the SVG/render subtree or controls panel into a child; add a mount
test if absent. These are the "awkward" splits flagged in the spec; the seam is usually
controls-panel vs. canvas-render.)

### Wave 3 — analytics + results (FE)
- [ ] `tabs/analytics/AssignmentTracker.jsx::AssignmentTrackerCard` (291)
- [ ] `tabs/analytics/AssignmentTracker.jsx::PeriodMissingReport` (289) *(same file → one PR, two extractions)*
- [ ] `tabs/ResultsTab.jsx::(anon default export)` (288)
- [ ] `tabs/results/ResultsExportControls.jsx::ResultsExportControls` (279)
- [ ] `tabs/results/ResultsFilterControls.jsx::ResultsFilterControls` (261)
- [ ] `tabs/results/ResultsTableRow.jsx::ResultsTableRow` (245)
- [ ] `tabs/analytics/ScatterSection.jsx::ScatterSection` (242)
- [ ] `tabs/analytics/GradeChartsSection.jsx::GradeChartsSection` (232)
- [ ] `tabs/analytics/StaticSections.jsx::StaticSections` (228)
- [ ] `tabs/results/AssessmentResultsSection.jsx::AssessmentRow` (218)
- [ ] `tabs/results/ResultsTable.jsx::ResultsTable` (207)

### Wave 4 — settings + settings-classroom (FE)
- [ ] `tabs/SettingsTab.jsx::(anon default export)` (288)
- [ ] `tabs/settings/AccommodationModal.jsx::AccommodationModal` (259)
- [ ] `components/SettingsGrading.jsx::SettingsGrading` (252)
- [ ] `components/SettingsBilling.jsx::SettingsBilling` (244)
- [ ] `components/settings-classroom/OneRosterSection.jsx::OneRosterFullForm` (242)
- [ ] `components/settings-classroom/PeriodsSection.jsx::PeriodsSection` (235) + `::PeriodStudentList` (207) *(one PR)*
- [ ] `components/settings-classroom/AccommodationsSection.jsx::AccommodationsSection` (228) + `::AccommodationStudentList` (219) *(one PR)*
- [ ] `components/settings-classroom/CleverSyncSection.jsx::CleverSyncSection` (218)
- [ ] `components/settings-privacy/WritingProfilesSection.jsx::WritingProfilesSection` (216)
- [ ] `tabs/settings/ParentContactMappingModal.jsx::ParentContactMappingModal` (229)

### Wave 5 — planner (FE + BE non-grading)
FE:
- [ ] `components/planner-tools/SlideDeckGenerator.jsx::SlideDeckGenerator` (243)
- [ ] `components/planner-lesson/LessonPlanActions.jsx::LessonPlanActions` (241)
- [ ] `tabs/PlannerTab.jsx::PlannerTab` (237)
- [ ] `components/planner-tools/ReadingLevelAdjuster.jsx::ReadingLevelAdjuster` (230)
- [ ] `components/planner-lesson/StandardsSelectorPanel.jsx::StandardsSelectorPanel` (224)
- [ ] `components/PlannerCalendar.jsx::PlannerCalendar` (222)
- [ ] `components/planner-lesson/GeneratedAssignmentPanel.jsx::GeneratedAssignmentPanel` (222)
- [ ] `components/planner-lesson/BrainstormIdeasPanel.jsx::BrainstormIdeasPanel` (215)
- [ ] `components/planner-assessment/AssessmentPreviewHeader.jsx::AssessmentPreviewHeader` (211)
- [ ] `components/planner-lesson/VariationCard.jsx::VariationCard` (201)
BE (Protocol-BE; `planner_generation` generators are NOT grading — they build content, not scores):
- [ ] `routes/planner_routes.py::_render_assignment_pdf_sections` (289)
- [ ] `services/planner_export.py::_export_assignment_docx_graider` (271)
- [ ] `services/planner_export.py::_build_question_figure_part2` (269) + `::_build_question_figure_part1` (261) *(one PR)*
- [ ] `services/planner_export.py::build_platform_export` (210)
- [ ] `routes/planner_routes.py::export_lesson_plan` (206)
- [ ] `services/planner_generation.py::generate_assessment_content` (263)
- [ ] `services/planner_generation.py::generate_assignment_from_lesson_content` (258)
- [ ] `services/planner_generation.py::generate_lesson_plan_content` (239)
- [ ] `services/planner_generation.py::_build_lesson_content_prompt` (218)

### Wave 6 — app/ hooks, tab panels, remaining FE
- [ ] `hooks/useVoice.js::useVoice` (288)
- [ ] `app/useAppPlannerResultsHandlers.js::useAppPlannerResultsHandlers` (274)
- [ ] `app/FocusExportModal.jsx::FocusExportModal` (266)
- [ ] `app/useAppContentState.js::useAppContentState` (265)
- [ ] `components/OnboardingWizard.jsx::OnboardingWizard` (265)
- [ ] `hooks/useAuthSession.js::useAuthSession` (258)
- [ ] `tabs/remediation-drawer/useRemediationDrawer.js::useRemediationDrawer` (258)
- [ ] `components/AutomationBuilder.jsx::AutomationBuilder` (253)
- [ ] `app/useAppLifecycleEffects.js::useAppLifecycleEffects` (251)
- [ ] `app/useAppBuilderHandlers.js::useAppBuilderHandlers` (250)
- [ ] `components/QuestionPlayer.jsx::QuestionPlayer` (250)
- [ ] `components/assistant-chat/useAssistantChat.js::useAssistantChat` (247)
- [ ] `hooks/useResultsCurveAndEmail.js::useResultsCurveAndEmail` (246)
- [ ] `components/Sidebar.jsx::Sidebar` (245) *(worked example above)*
- [ ] `tabs/AdminTab.jsx::(anon)` (244)
- [ ] `components/assignment-player/MathVisualInput.jsx::MathVisualInput` (241)
- [ ] `components/MatchingCards.jsx::MatchingCards` (239)
- [ ] `components/review-modal/GradeFeedbackTab.jsx::GradeFeedbackTab` (236)
- [ ] `hooks/useAssignmentBuilderActions.js::useAssignmentBuilderActions` (235)
- [ ] `components/QuestionEditOverlay.jsx::InlineEditForm` (233)
- [ ] `components/AssignmentPlayer.jsx::AssignmentPlayer` (232)
- [ ] `components/DistrictSetup.jsx::ConfigForm` (258)
- [ ] `components/automation-builder/AutomationEditView.jsx::AutomationEditView` (226)
- [ ] `app/AppTabPanels.jsx::PrimaryTabPanels` (226) + `::StudioTabPanels` (210) *(one PR)*
- [ ] `tabs/grade/IndividualUploadPanel.jsx::IndividualUploadPanel` (226)
- [ ] `components/student-portal/createPortalHandlers.js::createPortalHandlers` (224)
- [ ] `tabs/StudentReportCard.jsx::StudentReportCard` (230)
- [ ] `components/review-modal/EmailPreviewTab.jsx::EmailPreviewTab` (217)
- [ ] `hooks/useBehaviorListener.js::useBehaviorListener` (217)
- [ ] `tabs/grade/RegradeToggles.jsx::RegradeToggles` (210)
- [ ] `components/assignment-player/ChoiceTextInput.jsx::ChoiceTextInput` (208)
- [ ] `tabs/builder/QuestionsSection.jsx::QuestionsSection` (206)
- [ ] `hooks/useQuestionEditing.js::useQuestionEditing` (205)
- [ ] `tabs/BuilderTab.jsx::(anon default export)` (205)
- [ ] `tabs/builder/ImportDocumentSection.jsx::ImportDocumentSection` (205)
- [ ] `app/useAppCoreState.js::useAppCoreState` (201)
- [ ] `components/login-screen/SignInView.jsx::SignInView` (201)
- [ ] `__tests__/GradeTab.test.jsx::(anon)` (254) — split the `describe` block into focused
  `describe`s across two files (`GradeTab.upload.test.jsx` / `GradeTab.grading.test.jsx`); the
  "function" is the outer test closure. Strict standard keeps test files in scope.

> Wave 6 is the largest (~40 PRs); split it into 6a/6b/6c sub-batches of ~8 PRs each when dispatching.

### Wave 7 — remaining BE non-grading
- [ ] `routes/analytics_routes.py::get_analytics` (289) — Protocol-BE
- [ ] `services/grader_roster.py::load_roster` (276) — Protocol-BE
- [ ] `services/document_generator.py::_process_visual_block` (271) — Protocol-BE
- [ ] `services/llm_adapter/anthropic_adapter.py::stream_chat` (269) — Protocol-BE
- [ ] `services/llm_adapter/gemini_adapter.py::stream_chat` (236) — Protocol-BE
- [ ] `services/llm_adapter/openai_adapter.py::stream_chat` (227) — Protocol-BE
- [ ] `routes/ferpa_routes.py::export_individual_student_data` (264) 🔐 — Protocol-BE (FERPA path: opus review even though Class A)
- [ ] `routes/ferpa_routes.py::import_individual_student_data` (211) 🔐 — Protocol-BE
- [ ] `routes/student_portal_routes.py::get_class_remediation_effectiveness` (260) — Protocol-BE
- [ ] `routes/student_portal_routes.py::post_remediate` (236) — Protocol-BE (already split once at #682, 471→236; has crept back over 200 — find a second seam)
- [ ] `routes/student_portal_routes.py::submit_assessment` (218) — Protocol-BE
- [ ] `routes/student_account_routes.py::submit_student_work` (216) — Protocol-BE
- [ ] `routes/grading_routes.py::export_focus_csv` (253) — Protocol-BE (CSV export, not scoring)
- [ ] `routes/email_routes.py::send_confirmation_emails` (251) — Protocol-BE
- [ ] `routes/classlink_routes.py::classlink_callback` (234) 🔐 — Protocol-BE. **OIDC require-list stays byte-identical inline (Hard Rule #10).**
- [ ] `routes/clever_routes.py::clever_callback` (219) 🔐 — Protocol-BE. **MANDATORY SIS pin scan** (`tests/test_sis_alerting.py` pins lines in this file: 332/389/883/925) — update pins with documenting comments.
- [ ] `routes/settings_routes.py::save_parent_contact_mapping` (208) — Protocol-BE
- [ ] `services/worksheet_generator.py::_embed_visual` (206) — Protocol-BE
- [ ] `services/grader_cli.py::run_grading` (206) — Protocol-BE (CLI wrapper, not the grading core)

> 🔐 = auth/identity/FERPA. Per workflow.md these earn opus review even under Class A; if the split
> touches auth/redaction *logic* (not just moves it), reclassify that single PR to Class B.

---

## Wave 8 — Tier B: grading-critical (~15 functions), Class B

**Class B discipline (every PR in this wave):** byte-proof + free-var check (Protocol-BE) **PLUS**
golden-grading regression + prompt-snapshot byte-identity + factor-coverage checklist in the PR
body + opus adversarial review + Codex pass → **manual controller merge, NEVER `--auto`.**

### Task 8.1 — coverage audit FIRST (gate for the whole wave)

- [ ] For each of the 15 Tier B functions, confirm a golden/snapshot test pins it. Map:
  - `_run_grading_thread_inner`, `grade_single_file`, `_build_file_ai_notes`, `_grade_all_files`
    → `tests/test_grading_thread_golden.py` (drives the real thread).
  - `grade_assignment`, `grade_multipass`, `grade_per_question`, `generate_feedback`
    → `tests/test_grader_golden.py` + `tests/test_grader_prompt_snapshots.py` +
    `tests/test_grading_prompt_snapshot.py` + `tests/test_grading_pipeline_helpers.py`.
  - `grade_portal_submission_sync`, `_finalize_portal_grading` → `tests/test_portal_grading_golden.py`.
  - `extract_student_responses`, `_extract_responses_per_marker` → the 36-test characterization
    suite from #687 (confirm it still exists; `grep -rln "extract_student_responses" tests/`).
  - `_check_question_quality` → `tests/test_assignment_post_processing.py`.
  - `grade_assessment_answers_logic` → `grep -rln "grade_assessment_answers_logic" tests/`.
  - `grade_geometry` → `grep -rln "grade_geometry" tests/`.
- [ ] **If any function lacks a pinning golden test, write one FIRST in its own additive PR**
  (drive the real function, mock only the LLM via `tests/grading_fakes.py` and IO; pin the full
  output dict — scores, breakdown, feedback, per-question). Do NOT split a grading function nothing pins.

### Task 8.2–8.N — one PR per Tier B function (or per file-family)

For each, in order of risk (smallest blast radius first):

- [ ] `assignment_player_routes.py::grade_geometry` (213) — Protocol-BE + golden geometry-grading net.
- [ ] `planner_assessments.py::grade_assessment_answers_logic` (203) — Protocol-BE + answer-logic net.
- [ ] `assignment_post_processing.py::_check_question_quality` (257) — Protocol-BE + post-processing net (note: this file was already split once at #668; re-validate seam).
- [ ] `services/response_extraction.py::extract_student_responses` (255) + `::_extract_responses_per_marker` (260) — one PR; the #687 char-suite is the net; **marker/list aliasing hazard** (shared lists passed by ref — `.append` only, `.remove` stays in parent).
- [ ] `services/portal_grading.py::grade_portal_submission_sync` (251) + `::_finalize_portal_grading` (218) — one PR; `test_portal_grading_golden.py` is the net.
- [ ] `services/grading_leaves.py::grade_per_question` (240) + `::generate_feedback` (290) — one PR; prompt-snapshot nets assert the per-question + feedback prompts are byte-identical (**the factor-coverage gate**).
- [ ] `services/grading_pipeline.py::grade_multipass` (277) + `::grade_assignment` (285) — one PR (or two); golden + prompt-snapshot nets. **`grade_assignment`'s dispatch has shared-exception state (#667) — leave dispatch inline, find another seam.**
- [ ] `backend/grading/pipeline.py::_build_file_ai_notes` (264) — Protocol-BE; `_build_file_ai_notes` accumulates the 18 factors → factor-coverage checklist is mandatory; `test_grading_thread_golden.py` net.
- [ ] `backend/grading/pipeline.py::_grade_all_files` (233), `grade_single_file` (280),
  `_run_grading_thread_inner` (294) — these three are intertwined (ThreadPoolExecutor + closure
  captures, per the 6→7 grading-giants recon). **Re-read `2026-06-05-grading-giants-split-plan.md`**
  — the executor-submit wiring at the capture boundary is the load-bearing hazard. Likely 2–3 PRs;
  `test_grading_thread_golden.py` with PARALLEL_WORKERS=3 is the net.

**Factor-coverage checklist (paste into each Wave-8 PR body), per CLAUDE.md's 18 factors:**
```
For this split, the prompt/scoring inputs that still flow unchanged (✓ each):
[ ] global AI instructions  [ ] assignment grading notes  [ ] custom rubric
[ ] rubric type override     [ ] grading style (+score caps) [ ] IEP/504 accommodations
[ ] student history          [ ] class period differentiation [ ] expected answers
[ ] grade level & subject    [ ] section type               [ ] section name & points
[ ] student actual answers   [ ] ELL language               [ ] effort/completeness caps
[ ] assignment template      [ ] FITB exemption             [ ] writing style profile
Prompt-snapshot net byte-identical: [ ]   Golden scores identical: [ ]
```

---

## Wave 9 — re-scan + re-score (Class A, docs-only)

- [ ] **Step 1:** run all three DoD scans → confirm 0/0/empty. Capture raw output.

```bash
python scripts/cq_scan_backend.py; echo "exit=$?"
cd frontend && node ../scripts/cq_scan_frontend.mjs; echo "exit=$?"; cd ..
find backend frontend/src \( -name '*.py' -o -name '*.jsx' -o -name '*.js' \) | xargs wc -l | awk '$1>2500 && $2!="total"'
```
Expected: both scans exit 0; the `find` prints nothing.

- [ ] **Step 2:** full suite green — `pytest -q --ignore=tests/load`; `cd frontend && npx vitest run && npm run build`.
- [ ] **Step 3:** GitNexus reindex — `npx gitnexus analyze --embeddings --skip-agents-md`.
- [ ] **Step 4:** edit `docs/superpowers/specs/2026-06-02-hardening-rubric-anchors.md` — change the
  CQ "Current: 7" prose to 8 with the re-scan evidence inline; add a dated re-score row; update the
  overall mean 7.85 → ~7.95 with the per-dimension spot-check noting only CQ moved.
- [ ] **Step 5:** commit (Class A, docs-only) on `docs/cq8-rescore`; PR body carries the evidence
  ledger (before: 1 file + 127 fns → after: 0/0; test counts; wave/PR index). **Gate: opus
  adversarial re-score + Codex pass** (the #778 maintenance procedure) before merge.

---

## Subagent dispatch template (per Tier A PR; subagent-driven-development)

```
You are splitting ONE oversized function to flip Code Quality 7→8. Isolated git worktree —
branch refactor/cq8-NN-<short>, commit, push, PR (base main) from here. Venv:
source /Users/alexc/Downloads/Graider/venv/bin/activate.

FIRST read .claude/rules/workflow.md AND
docs/superpowers/plans/2026-06-13-cq-7-to-8-campaign.md (Protocol-BE or Protocol-FE).

TARGET: <file>::<function> (<LOC> LOC → must end ≤200, behavior-preserving).

Do: re-validate live line ranges → apply the protocol (byte-verbatim for BE / pure-prop for FE) →
free-var check (BE) → the function's net green → full pytest -q --ignore=tests/load (BE) or
npx vitest run + npm run build (FE) → ruff+bandit (BE) → pin scan if file in tests/test_sis_alerting.py
→ re-run the scan script to confirm the function is gone. Commit scope clean (no flask_session/,
no .claude noise).

Report: Status DONE|DONE_WITH_CONCERNS|BLOCKED; branch+PR#; before/after LOC; net output tail with
counts; scan-script confirmation line; self-review (pure-move? hazards hit?); concerns. Raw data only.
```

For Tier B PRs, append: *"CLASS B — golden-grading regression + prompt-snapshot byte-identity +
the factor-coverage checklist must all be in the PR body. DO NOT enable auto-merge."*

---

## Self-review (against the spec)

- **Spec §1 strict standard** → DoD scans + Wave 6 keeps `GradeTab.test.jsx`; Wave 2 keeps the SVG
  math components. ✓
- **Spec §4 two tiers (15 Class B)** → Wave 8 lists exactly the 15; Waves 1–7 are Class A. ✓
- **Spec §5 nine waves** → Tasks 0 + Waves 1–9. ✓
- **Spec §6 nets** → Protocol-BE byte-identity + Protocol-FE mount tests + Wave 8 golden/snapshot
  gates + 8.1 coverage audit. ✓
- **Spec §6 SIS pin** → called out in Protocol-BE step 6 and Wave 7 `clever_callback`. ✓
- **Spec §9 DoD** → the DoD block + Wave 9. ✓
- **Count check (verified function-by-function against the scan):**
  BE = W1(3) + W5-BE(10) + W7(19) + W8(15) = **47** ✓;
  FE = W2(8) + W3(11) + W4(12) + W5-FE(10) + W6(39) = **80** ✓; total **127** + the 1 file split.
  `post_remediate` (236, student_portal_routes) was caught missing on first pass and added to W7.
  (Re-run scans at Wave 9; the scan is the true gate, not this count.)
- **Placeholder scan:** scripts are complete; per-function code intentionally generated at execution
  against the live file (line-drift rationale documented up top — matches repo precedent). ✓
```
