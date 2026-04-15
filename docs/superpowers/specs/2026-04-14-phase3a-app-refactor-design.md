# Phase 3a — backend/app.py refactor design (DRAFT for Gemini review)

> **Status:** FINAL (rev 2, 2026-04-14). Codex + Gemini reviewed. Revisions in rev 2: init_app(app) replaces create_app() factory; 3-file grading split (state + thread + pipeline); format_rubric_for_prompt moves to services/rubric_formatting.py in PR4; route snapshot test includes HTTP methods.

**Date:** 2026-04-14
**Scope parent:** Phase 3 of `project_codebase_improvement_roadmap.md` (split monoliths).
**Scope of THIS spec:** Phase 3a only — extract grading code from `backend/app.py` (3528 lines). A separate Phase 3b will handle `planner_routes.py` (8104 lines) and is deliberately out of scope here.

---

## Goal

Reduce `backend/app.py` from **3528 → ~1400 lines** by extracting grading state + thread code into a new `backend/grading/` package, while establishing the Flask app-factory pattern. Zero behavior change. Zero SIS compliance regression (Clever/ClassLink/OneRoster flows stay green, 180/180 contract tests pass throughout).

## Non-goals

- **No pipeline decomposition.** The ~2000-line inner grading pipeline inside `_run_grading_thread_inner` stays as a single function for now — splitting it without unit tests that pin its behavior is too risky. Deferred.
- **No planner_routes.py refactor.** That's Phase 3b.
- **No route reshuffling.** Blueprint registration ordering stays identical; the app factory just moves the instantiation, not the wiring order.
- **No new features, no bug fixes piggybacked.** Pure restructure.

## Hard constraints

- Clever / ClassLink / OneRoster / roster_sync / oneroster_gradebook code unchanged. Same file paths, same function signatures.
- SIS contract suite 180/180 green throughout all transitional PRs.
- CI coverage floor 32 holds.
- Each PR must boot (`python -c "from backend.app import app; print(app.url_map)"`) and register the same route count as before.

---

## Architectural decisions

### Decision 1 — Scope decomposition
Two separate plans: **Phase 3a (app.py) first → Phase 3b (planner_routes.py) after 3a lands.**

**Why:** The app-factory pattern and shim conventions established in 3a become prerequisites for 3b. Shipping 3a first shrinks 3b's design space. Each sub-plan gets its own Codex Gate 1.

### Decision 2 — Migration strategy
**(c) then (b): `init_app(app)` initializer pattern first, then incremental grading extraction with shims.**

**Revised from rev 1:** We use `init_app(app)` (initializer that takes an existing `app` object) rather than `create_app()` (factory that returns a new `app`). Reason per Codex/Gemini tie-break: `backend/app.py` still has module-level `@app.route` decorators (e.g., `delete_single_result` at line 2359, `import_individual_student_data` at line 2898, plus handlers at lines 2365, 2416, 2451, 2486, 2564, 2608, 2642, 2906). A `create_app()` factory would require MOVING those decorators INSIDE the factory scope — either risky (manual relocation of every handler) or large scope creep (convert all to blueprints). `init_app(app)` keeps `app = Flask(__name__)` at module level so the existing decorators continue to attach correctly; only initialization wiring (middleware, error handlers, blueprint registration, SIGTERM setup) moves into the initializer.

Full blueprint migration and the final `create_app()` factory are Phase 3b+ concerns.

Sequence of PRs:
- **PR1 (init_app):** Introduce `init_app(app)` in app.py. Module-level `app = Flask(__name__)` stays; module-level `@app.route` decorators stay. Extract ONLY: `@app.after_request` / `@app.errorhandler` registrations, `register_routes(...)` call, and SIGTERM setup into `init_app(app)`. Call `init_app(app)` at module level once all decorators have attached. Smoke test: importing `backend.app` produces an app with the same URL rules (incl. methods) as before.
- **PR2 (state):** Create `backend/grading/__init__.py` and `backend/grading/state.py`. Move `_grading_states`, `_grading_locks`, `_create_default_state`, `_get_state`, `_get_lock`, `_update_state`, `reset_state`, plus `load_saved_results` and `save_results` (they belong with state — see Gotcha #1). Add re-export shims in app.py. All existing `from backend.app import _get_state` imports keep working.
- **PR3 (thread + pipeline split):** Create `backend/grading/pipeline.py` and `backend/grading/thread.py`. `pipeline.py` holds `_run_grading_thread_inner` (the ~2000-line business-logic pipeline, with its nested `format_rubric_for_prompt` still intact — moved out in PR4). `thread.py` holds `run_grading_thread` (the ~70-line BYOK wrapper) and imports `_run_grading_thread_inner` from `pipeline`. This 3-file split (not 2) was the rev-2 change: putting 2000 lines of business logic in a file named `thread.py` conflated concerns; semantic separation now, not "later."
- **PR4 (cleanup):** (a) Extract `format_rubric_for_prompt` from the nested scope inside `pipeline.py._run_grading_thread_inner` into a new `backend/services/rubric_formatting.py`. Update the call site inside `pipeline.py` and fix `portal_grading.py:380` to import from the new location (rather than delete the block as "dead" — the new location makes the import actually work). (b) Migrate remaining consumers (`portal_grading.py`:255/563, `assistant_tools_student.py`:515/680, `email_routes.py`:1102) to import from `backend.grading.*`. (c) Remove all shims from app.py.

**Why this sequence:** Each PR is independently mergeable, reviewable in isolation, and has a narrow blast radius. Safety net = Phase 1/2 SIS contracts + coverage floor + new route-snapshot test at every step.

### Decision 3 — Grading module granularity
**Three files: `grading/state.py` + `grading/thread.py` + `grading/pipeline.py`** (rev 2 change).

- `grading/state.py` (~220 LOC): state dict, locks, all state mutation helpers, `load_saved_results`, `save_results`.
- `grading/thread.py` (~70 LOC): `run_grading_thread` BYOK wrapper. Imports `_run_grading_thread_inner` from `pipeline`. Lifecycle/concurrency concerns only.
- `grading/pipeline.py` (~2000 LOC): `_run_grading_thread_inner` business-logic pipeline. Pure move in PR3 (no internal decomposition). In PR4, the nested `format_rubric_for_prompt` moves out to `backend/services/rubric_formatting.py`.

**Why the rev 2 revision (was 2 files, now 3):** Gemini flagged that putting a 2000-line business-logic pipeline in a file named `thread.py` conflates concerns — `thread.py` implies lifecycle/concurrency. Codex agreed on review: since PR3 is a pure byte-identical move regardless of target filename, splitting into `thread.py` + `pipeline.py` adds semantic clarity at zero additional risk and paves the way for unit-testing the pipeline in Phase 3b. The earlier Codex "2 files" vote was about not decomposing the pipeline INTERNALLY (chopping into helpers); the separate-file move preserves that constraint.

**Why not a single file?** `state.py` has a clean interface (get/update/reset/persist) worth its own module. The wrapper→pipeline seam is semantic (lifecycle vs business logic) not speculative.

---

## Gotchas flagged by Codex

### Gotcha #1 — Persistence helpers must move WITH state
`_create_default_state()` calls `load_saved_results()`. If `state.py` imports `load_saved_results` from `backend.app`, we create a circular import (`app.py` will also re-export `_get_state` from `state.py`).

**Fix:** Move `load_saved_results`, `save_results` into `grading/state.py`. They conceptually ARE state persistence. `app.py` keeps a shim `from backend.grading.state import load_saved_results, save_results` for backwards compatibility of existing consumers.

### Gotcha #2 — Shim surface area
These files currently import state/thread helpers from `backend.app`:
- `backend/services/portal_grading.py:255,380,563` — `save_results`, `load_saved_results`, `_get_lock`, `format_rubric_for_prompt`
- `backend/services/assistant_tools_student.py:515,680` — `_get_state`, `save_results`
- `backend/routes/email_routes.py:1102` — `_get_state`
- `backend/app.py:2055` (calls `register_routes(..., _get_state, run_grading_thread, reset_state, _get_lock)` — the routes module receives these as injected args)
- `backend/app.py:2064-2069` — SIGTERM handler walks `_grading_states` directly
- Various route handlers in app.py (lines 2365, 2416, 2451, 2486, 2564, 2608, 2642, 2906) call `_get_state()` directly

**Implication:** `app.py` must keep re-exporting `_get_state`, `save_results`, `load_saved_results`, `_get_lock`, `reset_state`, `run_grading_thread` via shim (`from backend.grading.state import *` and `from backend.grading.thread import *`) throughout PR2 and PR3. PR4 removes shims only after all consumers are migrated.

### Gotcha #3 — `format_rubric_for_prompt`
`portal_grading.py:380` currently does `from backend.app import format_rubric_for_prompt`. The function is NESTED inside `_run_grading_thread_inner` at app.py:587 — it has never been module-level importable, so that import is a pre-existing latent bug (ImportError would fire if the code path ever executed). The function is a pure rubric-string formatter; it takes `rubric_data` as an explicit parameter and does not close over any enclosing state (Codex verified).

**Decision (rev 2 change):** PR4 extracts `format_rubric_for_prompt` OUT of the nested scope inside `pipeline.py._run_grading_thread_inner` into `backend/services/rubric_formatting.py`. The call site inside `_run_grading_thread_inner` becomes `from backend.services.rubric_formatting import format_rubric_for_prompt`. `portal_grading.py:380` is updated to import from the new location — FIXING the latent bug, not deleting the import as "dead code."

This is a scope bump relative to rev 1 (~15 LOC new file + 2 call-site updates) but it's pure formatting logic with narrow blast radius. Codex + Gemini both endorsed the move.

---

## Safety net for Phase 3a

Beyond standard workflow (branch + CI + Codex gates):

1. **Boot check after each PR:** `python -c "from backend.app import app; print(len(app.url_map._rules))"`. Record the baseline pre-PR; must match post-PR.
2. **Route snapshot with methods** (rev 2 upgrade — Gemini flagged, Codex tightened): pin `{endpoint: (rule, sorted(methods))}` against a baseline, not just count. Catches silent path OR method drift:
   ```python
   # tests/test_app_boot.py
   def test_app_routes_unchanged():
       """Snapshot exact endpoint → (rule, methods) mapping. Delta = behavior change."""
       from backend.app import app
       current = {
           rule.endpoint: (rule.rule, sorted(rule.methods - {"HEAD", "OPTIONS"}))
           for rule in app.url_map.iter_rules()
       }
       assert len(current) >= 250  # Floor check
       # Optional: compare against a committed JSON snapshot for exact-match
       # — deferred to a future PR if flake emerges from dynamic routes.
   ```
3. **SIS callback smoke:** Local dev-server hit on `/api/clever/login-url`, `/api/classlink/login-url`, `/api/oneroster/config` before PR; compare response shape.
4. **Import shim guard test:**
   ```python
   # tests/test_grading_shims.py
   def test_backend_app_reexports_grading_state_during_transition():
       from backend.app import _get_state, save_results, load_saved_results, _get_lock, reset_state, run_grading_thread
       assert callable(_get_state)
       # ... etc. Remove this test in PR4 when shims are removed.
   ```

---

## PR sequence summary (rev 2)

| PR | What | Net LOC delta in app.py | Risk |
|---|---|---|---|
| PR1 (init_app) | Introduce `init_app(app)`; module-level `app = Flask(...)` stays; `@app.route` decorators stay; only middleware/error-handlers/blueprint-registration/SIGTERM wrapping changes | ~0 (internal reorder only) | Low — initializer pattern preserves existing decorator scope |
| PR2 (state) | Move state + persistence helpers to `grading/state.py`; shim in app.py | −220 | Low — shim keeps consumers working |
| PR3 (thread + pipeline, 3-file split) | Move `run_grading_thread` wrapper to `grading/thread.py` (~70 LOC) and `_run_grading_thread_inner` to `grading/pipeline.py` (~2000 LOC); shim in app.py re-exports both | −2100 | Medium — biggest moving piece, but byte-identical copy + tests |
| PR4 (cleanup + rubric extract) | Extract nested `format_rubric_for_prompt` to `services/rubric_formatting.py`; fix portal_grading.py:380 import; migrate remaining consumers; remove shims | 0 in app.py (shims gone) | Low — drop-in path rewrites + small new service file |

**Final app.py size estimate:** ~1400 lines (Flask init, middleware, error handlers, audit helpers, calibration helper, legacy module-level `@app.route` handlers not yet in blueprints — moved to Phase 3b+).

---

## Review outcomes (Gemini + Codex tie-break)

Rev 1 had 6 open questions. Gemini reviewed and pushed back on 3 decisions + flagged one safety-net upgrade. Codex tie-broke: accepted all 4 changes, tightened the route-snapshot proposal to include HTTP methods. Final rev 2 decisions:

1. **PR1 mechanic:** Use `init_app(app)` initializer instead of `create_app()` factory. Module-level `app` and `@app.route` decorators stay put.
2. **Shim pattern:** Keep the `from backend.grading.state import *` re-export facade in app.py. Standard Pythonic migration pattern.
3. **format_rubric_for_prompt:** Extract to `backend/services/rubric_formatting.py` in PR4 (scope bump vs rev 1). Fixes the latent portal_grading.py:380 import bug as a side effect.
4. **Safety net upgrade:** Route-snapshot test pins `{endpoint: (rule, sorted(methods))}`, not just count. Catches path OR method drift.
5. **4-PR sequence:** Correct as-is. Don't split PR3 further; a byte-identical move reviews better as one PR.
6. **PR3 target files:** 3-file split (state + thread + pipeline), NOT 2. Semantic clarity at zero additional risk since it's still a pure move.

---

## Not in this spec

- Phase 3b: `planner_routes.py` decomposition (separate spec, separate brainstorming cycle)
- Internal split of the 2000-line pipeline (requires unit tests first)
- Route handler migration out of app.py into blueprints (separate concern; handlers currently in app.py are mostly legacy and can stay for now)
- `format_rubric_for_prompt` relocation (deferred)
