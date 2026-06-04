# Code Quality 6→7 — God-Function Split Campaign

**Goal:** Drive the Code Quality rubric dimension from **6 → 7** by getting every backend source
function below **300 LOC** (the level-7 anchor: *"No file >3,000 LOC; no function >300 LOC; a
Flask-free service layer exists"*), behavior-preservingly.

> **Status: IN PROGRESS — 9/18 done.** Waves 1–2 + the easy half of Wave 3 complete. **9 backend
> functions >300 LOC remain** (the harder half: route control-flow handlers + the grading giants).
> Code Quality stays **6** until ALL are <300 (and a frontend-JS function scan is run).

---

## ⚠️ Correction to the 2026-06-04 App.jsx closeout (#665)

The #665 closeout (in `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`)
claimed *"grade_assignment (407) and grade_multipass (363) are the only two functions >300 LOC
blocking the point."* **That was wrong.** A mechanical `ast` scan (the rubric's own "scan
def-to-def spans" verify step) found **18 backend functions >300 LOC**. Splitting the two grading
functions (#666, #667) was necessary but nowhere near sufficient. This doc is the corrected,
complete path. Honest current state: **Code Quality 6**, overall ~7.35.

---

## The proven per-function protocol (risk-tiered)

Each function is one PR. Validate the split plan against the **live** file first (recon line ranges
drift). Then:

1. **Anchor-based byte-verbatim extraction script** (never hand-edit large moves). Prove the move:
   - 4-space body block → **byte-identical** (md5 of moved block == md5 from `git show main:`).
   - 8-space block (inside try/if/loop) → **uniform de-indent-by-4**, proven *reversible*
     (re-indent by 4 reproduces the original exactly).
2. **AST free-variable check** on each helper: every loaded name must be a param, a module global,
   a builtin, an inline import, an except-binding, or a nested def. Zero unresolved.
3. **The function's net green** (golden/characterization), then **full suite** (`pytest -q
   --ignore=tests/load`, ~4 min, expect 5751 passed), then **ruff**.
4. **Tier gates:**
   - **Class A** (behavior-preserving, strong net): byte-proof + net + full suite → **merge on green CI**.
   - **Class B** (critical path / auth / no strong net): **+ 4-agent adversarial workflow + Codex
     independent review**, manual merge.
   - **Netless giants** (`grade_single_file`, `_run_grading_thread_inner`): **write a golden net
     FIRST** (own PR) + Codex co-planning, then split.

### Gotchas already hit (do not repeat)
- **Decorator rebinding** (#670): inserting a module-level helper *between* a route's decorator
  stack (`@route`/`@require_teacher`/`@handle_route_errors`) and its `def` rebinds the decorators
  onto the helper → 500s. **Insert before the first decorator.** Caught by the net.
- **`continue` → `return`** (#669): a `continue` targeting the *outer* loop, when its branch moves
  into a helper, must become `return` (return-from-helper ≡ continue-in-caller, *iff* nothing
  follows the chain in the loop body). A `continue` for an *inner* loop stays.
- **`elif`→`if`**: when a moved block starts mid-`if/elif` chain, the first `elif` becomes `if`.
- **`response_text`-style shared exception state**: a block whose vars are read by a later `except`
  cannot be naively extracted (left grade_assignment's dispatch inline in #667 for this reason).
- **>300 helper**: if extracting one block yields a helper that is itself >300 (e.g.
  `_create_visual_for_question`'s 520-line dispatch), split the chain into 2 halves with a
  sequential dispatch in the parent (`fig = part1(...); if fig is None: fig = part2(...)`).

---

## Progress

### Shipped (this campaign + prerequisites)
| PR | Function | LOC before→after | Class |
|--|--|--|--|
| #666 | `grade_multipass` (Pass-2 split) | 361 → 275 | B |
| #667 | `grade_assignment` (prep + json-recovery) | 405 → 284 | B |
| #668 | `_check_question_quality` | 301 → 262 | A |
| #669 | `create_document_docx` | 343 → 83 | A |
| #670 | `get_class_remediation_effectiveness` | 312 → 268 | A |
| #671 | `_create_visual_for_question` | 584 → 65 | A |
| #673 | `generate_assessment_content` | 440 → 263 | A |
| #674 | `generate_lesson_plan_content` | 451 → 239 | A |
| #675 | `generate_assignment_from_lesson_content` | 441 → 258 | A |
| #676 | `_export_assignment_docx_graider` | 315 → 271 | A |
| #677 | `_build_system_prompt` | 341 → 184 | A |

### Remaining 9 (the harder half)
- **Route control-flow handlers** (early returns / branching — extract response/compute blocks, mind the decorator-insertion gotcha): `classlink_callback` (318 🔐 auth), `post_remediate` (471), `export_generated_assignment` (439), `generate` (373), `assistant_chat` (472).
- **Grading giants — write a golden net FIRST, then Codex co-planning** (no deterministic net today): `grade_portal_submission_sync` (452 🔴), `extract_student_responses` (866, shared mutable state across marker loops), `grade_single_file` (626, nested closure in `_run_grading_thread_inner`), `_run_grading_thread_inner` (1492, ThreadPoolExecutor orchestrator).

> The route handlers are doable with the established protocol; the 4 grading giants are the part
> that genuinely needs fresh context + new nets. Pattern note for routes: helpers MUST be inserted
> ABOVE the decorator stack (`@route`/`@require_teacher`/`@handle_route_errors`/`@limiter.limit`).

### Remaining 14 (sequenced)

**Wave 2 — Class B, strong net** (Codex dual review):
| LOC | Function | File | Helpers | Notes |
|--|--|--|--|--|
| 866 | `extract_student_responses` | services/response_extraction.py | 3+ | 18 golden char tests. Dominated by a 640-line `if custom_markers:` block → split the marker-position builder (~903-1067) + per-marker extraction loop (~1121-1447, itself ~327 LOC → sub-split). Shared mutable state (marker_positions, extracted, blank_questions) — careful. |
| 318 | `classlink_callback` 🔐 | routes/classlink_routes.py | 4 | auth; 10+ SSO/security tests. Watch OIDC require-list rules (workflow.md #10). |
| 440 | `generate_assessment_content` | services/planner_generation.py | 8 | char test |
| 451 | `generate_lesson_plan_content` | services/planner_generation.py | 9 | contract tests |
| 471 | `post_remediate` | routes/student_portal_routes.py | 7 | 9 validation tests; route (decorator-insertion gotcha applies) |

**Wave 3 — Class B, partial net** (add a characterization test first, then split + Codex):
`_export_assignment_docx_graider` (315), `grade_portal_submission_sync` (452 🔴 grading),
`generate_assignment_from_lesson_content` (441), `export_generated_assignment` (439),
`assistant_chat` (472).

**Wave 4 — Class B, netless giants** (write golden net FIRST + Codex co-planning):
`generate` (373), `_build_system_prompt` (341), `grade_single_file` (626 🔴 nested closure inside
`_run_grading_thread_inner`, ThreadPoolExecutor entanglement), `_run_grading_thread_inner` (1492 🔴
the monster — partial safety-rail net only).

> `grade_single_file` + `_run_grading_thread_inner` are intertwined (the former is a nested closure
> in the latter with 10+ closure captures + a stateful executor loop). They need dedicated planning
> + new golden nets and should be done LAST, together.

### Final step
After all 14: run a **frontend JS/JSX function-LOC scan** (the rubric covers FE+BE). Only when ALL
source functions are <300 does Code Quality flip 6→7 (overall ~7.35 → ~7.45). Update the #665
closeout + the rubric-anchor doc (`2026-06-02-hardening-rubric-anchors.md`, fix the prose that named
only 2 functions).

---

## How to resume (handoff)
- Recon plans (per-function split sketches, coverage, hazards) are in the workflow result captured
  at recon time; line ranges **must be re-validated** against the live file (they drift each merge).
- Re-scan remaining functions any time:
  ```
  python - <<'PY'
  import ast, os
  for dp,_,fs in os.walk("backend"):
      if any(x in dp for x in ("venv",".git","/tests",".gitnexus")): continue
      for fn in fs:
          if fn.endswith(".py"):
              try: t=ast.parse(open(os.path.join(dp,fn)).read())
              except Exception: continue
              for n in ast.walk(t):
                  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and (n.end_lineno-n.lineno+1)>300:
                      print(n.end_lineno-n.lineno+1, n.name, os.path.join(dp,fn))
  PY
  ```
- Branch naming: `refactor/cq7-NN-<short-name>`. Reindex GitNexus once per wave, not per PR.
