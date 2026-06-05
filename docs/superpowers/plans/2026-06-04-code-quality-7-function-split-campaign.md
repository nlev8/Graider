# Code Quality 6→7 — God-Function Split Campaign

**Goal:** Drive the Code Quality rubric dimension from **6 → 7** by getting every backend source
function below **300 LOC** (the level-7 anchor: *"No file >3,000 LOC; no function >300 LOC; a
Flask-free service layer exists"*), behavior-preservingly.

> **Status: IN PROGRESS — 16/18 done.** Waves 1–2 + Wave 3 + the assistant route pair complete.
> **2 backend functions >300 LOC remain** — the entangled grading monster:
> `_run_grading_thread_inner` (1492) + `grade_single_file` (626, a nested closure inside it). These are a
> PAIR that must be split together; needs a fresh-context dedicated session + new golden net (ThreadPoolExecutor
> entanglement, 10+ closure captures). Code Quality stays **6** until BOTH are <300 (and a frontend-JS
> function scan is run).
>
> The `assistant_chat`/`generate` pair was split on branch `refactor/cq7-assistant-chat-split`: `generate()`
> lifted to module-level `_run_assistant_stream` (273) + per-round tool loop extracted to `_execute_tool_round`
> (130); `assistant_chat` 472→105. Golden net `tests/test_assistant_chat_golden.py` (5 SSE scenarios), byte-identity
> vs main proven, 4-lens adversarial review all PRESERVED (zero critical/important).

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
| #681 | `export_generated_assignment` (PDF section loop → `_render_assignment_pdf_sections`) | 439 → 168 | A |
| #682 | `post_remediate` (personalized + shared paths → 2 helpers) | 471 → 236 | B |
| #683 | `classlink_callback` 🔐 (student + teacher login tails → 2 helpers) | 318 → 234 | B |
| #686 | `grade_portal_submission_sync` 🔴 (score+feedback+persist → `_finalize_portal_grading`) | 452 → 251 | B |
| #687 | `extract_student_responses` (4 helpers: marker-builder / content-end / per-marker-loop / fallback) | 866 → 255 | B |
| _pending_ | `assistant_chat`/`generate` (lift `generate`→`_run_assistant_stream` + tool loop→`_execute_tool_round`; golden SSE net + 4-lens adversarial review) | 472/373 → 105/273/130 | B |

### Remaining 2 (the harder half)
- ~~**Intertwined assistant route**~~ ✅ DONE (`refactor/cq7-assistant-chat-split`): `generate` (373) lifted to `_run_assistant_stream` (273) + tool loop → `_execute_tool_round` (130); `assistant_chat` 472→105. Golden net + byte-identity + 4-lens adversarial review (all PRESERVED).
- **Grading giants — write a golden net FIRST, then Codex co-planning** (no deterministic net today): ~~`grade_portal_submission_sync` (452 🔴)~~ ✅ #686, ~~`extract_student_responses` (866)~~ ✅ #687 (4-helper split incl. a nested content-end helper; the 36-test full-output characterization suite was the golden net), `grade_single_file` (626, nested closure in `_run_grading_thread_inner`), `_run_grading_thread_inner` (1492, ThreadPoolExecutor orchestrator). The last two are intertwined — split together.

> The route handlers are doable with the established protocol; the 4 grading giants are the part
> that genuinely needs fresh context + new nets. Pattern note for routes: helpers MUST be inserted
> ABOVE the decorator stack (`@route`/`@require_teacher`/`@handle_route_errors`/`@limiter.limit`).

### Remaining 14 (sequenced)

**Wave 2 — Class B, strong net** (Codex dual review):
| LOC | Function | File | Helpers | Notes |
|--|--|--|--|--|
| 866 | ~~`extract_student_responses`~~ ✅ #687 | services/response_extraction.py | 4 | DONE. 36-test full-output char net was the golden. Split into marker-builder + content-end (nested) + per-marker-loop + fallback; shared lists passed by ref (.append only; .remove stayed in parent). |
| 318 | ~~`classlink_callback`~~ ✅ #683 🔐 | routes/classlink_routes.py | 2 | auth; ~141 SSO/security tests. Extracted the 2 post-auth login tails (student/teacher); OIDC validation + require-list left byte-identical inline (Rule #10). |
| 440 | `generate_assessment_content` | services/planner_generation.py | 8 | char test |
| 451 | `generate_lesson_plan_content` | services/planner_generation.py | 9 | contract tests |
| 471 | ~~`post_remediate`~~ ✅ #682 | routes/student_portal_routes.py | 2 | Strong net (111 remediation tests, not 9). Split the 2 tail blocks (personalized + shared paths) that already ended in `return`. |

**Wave 3 — Class B, partial net** (add a characterization test first, then split + Codex):
~~`_export_assignment_docx_graider` (315)~~ ✅ #676, `grade_portal_submission_sync` (452 🔴 grading),
~~`generate_assignment_from_lesson_content` (441)~~ ✅ #675,
~~`export_generated_assignment` (439)~~ ✅ #681 (golden flowable-signature net, Class A),
~~`assistant_chat` (472)~~ ✅ `refactor/cq7-assistant-chat-split`.

**Wave 4 — Class B, netless giants** (write golden net FIRST + Codex co-planning):
~~`generate` (373)~~ ✅ (lifted to `_run_assistant_stream`, same branch as `assistant_chat`),
~~`_build_system_prompt` (341)~~ ✅ #677, `grade_single_file` (626 🔴 nested closure inside
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
