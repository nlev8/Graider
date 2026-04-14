# Phase 3a — backend/app.py refactor design (DRAFT for Gemini review)

> **Status:** DRAFT — brainstorming in progress. Codex has reviewed the grading-module granularity call and flagged gotchas (sections below). Gemini review requested before finalizing.

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
**(c) then (b): Factory-first, then incremental grading extraction with shims.**

Sequence of PRs:
- **PR1 (factory):** Introduce `create_app()` in app.py. Move Flask instantiation + middleware + error handlers into the factory. No code is EXTRACTED to other files — this PR only rearranges app.py internally to expose `create_app()`. Smoke test: `from backend.app import create_app; app = create_app(); app.url_map` enumerates the same routes.
- **PR2 (state):** Create `backend/grading/__init__.py` and `backend/grading/state.py`. Move `_grading_states`, `_grading_locks`, `_create_default_state`, `_get_state`, `_get_lock`, `_update_state`, `reset_state`, plus `load_saved_results` and `save_results` (they belong with state — see Gotcha #1). Add re-export shims in app.py: `from backend.grading.state import *`. All existing `from backend.app import _get_state` imports keep working.
- **PR3 (thread + pipeline):** Create `backend/grading/thread.py`. Move `run_grading_thread` + `_run_grading_thread_inner` (WITH the inlined pipeline). Add re-export shim in app.py. SIGTERM handler in app.py updated to import `_grading_states` from `backend.grading.state`.
- **PR4 (cleanup):** Migrate consumers (portal_grading, assistant_tools_student, email_routes, register_routes caller) to import directly from `backend.grading.*` instead of `backend.app`. Remove shims.

**Why this sequence:** Each PR is independently mergeable, reviewable in isolation, and has a narrow blast radius. Safety net = Phase 1/2 SIS contracts + coverage floor at every step.

### Decision 3 — Grading module granularity
**(b) Two files: `grading/state.py` + `grading/thread.py`.**

- `grading/state.py` (~220 LOC once persistence helpers move): state dict, locks, all state mutation helpers, `load_saved_results`, `save_results`.
- `grading/thread.py` (~2100 LOC): `run_grading_thread` wrapper + `_run_grading_thread_inner` with pipeline inlined.

**Why not (a) three files?** Splitting the 2000-line pipeline adds a wrapper→pipeline seam without reducing the real risk, which is the large behaviorally-untested inner function. Defer until we can do the split with tests.

**Why not (c) single file?** `state.py` has a clean interface (get/update/reset/persist) worth its own module. Keeping it separate makes future tests easier to write against.

**Codex confirmed (b).**

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
`portal_grading.py:563` imports `format_rubric_for_prompt` from `backend.app`. This function is NOT state or thread — it's a rubric formatter. It should stay in app.py OR move to a new location (e.g., `backend/services/rubric_formatting.py`) but NOT into `grading/`.

**Decision:** Leave `format_rubric_for_prompt` in app.py for Phase 3a. Moving it is a separate concern.

---

## Safety net for Phase 3a

Beyond standard workflow (branch + CI + Codex gates):

1. **Boot check after each PR:** `python -c "from backend.app import app; print(len(app.url_map._rules))"`. Record the baseline pre-PR; must match post-PR.
2. **Route-count diff check** committed as a one-liner test:
   ```python
   # tests/test_app_boot.py
   def test_app_boots_and_registers_expected_routes():
       from backend.app import app
       # Record baseline: N routes (updated whenever routes added/removed deliberately)
       assert len(app.url_map._rules) >= 250  # Pin the floor
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

## PR sequence summary

| PR | What | Net LOC delta in app.py | Risk |
|---|---|---|---|
| PR1 (factory) | Introduce `create_app()`; no code movement | 0 (internal reorder only) | Low — startup ordering |
| PR2 (state) | Move state + persistence helpers to `grading/state.py`; shim in app.py | −220 | Low — shim keeps consumers working |
| PR3 (thread) | Move thread + pipeline to `grading/thread.py`; shim in app.py | −2100 | Medium — biggest moving piece, but no code changes |
| PR4 (cleanup) | Migrate consumers; remove shims | 0 in app.py (shims gone) | Low — drop-in path rewrites |

**Final app.py size estimate:** ~1400 lines (Flask init, middleware, error handlers, audit helpers, `format_rubric_for_prompt`, calibration helper, route handlers that haven't yet moved to blueprints).

---

## Open questions for Gemini

1. Does the (c)→(b) migration strategy have any risk I'm missing? Should PR1 (factory) be even more minimal, or does it need to do more than `create_app()`?
2. Is the shim approach (`from backend.grading.state import *` re-exported from app.py) the canonical Flask pattern, or is there a cleaner way (e.g., `backend.grading` as the top-level reexport and have app.py disappear entirely as a re-export layer)?
3. Gotcha #3 — should `format_rubric_for_prompt` stay in app.py or move to `backend/services/rubric_formatting.py` NOW (as part of PR4 cleanup) or defer?
4. The safety net proposal (boot check + route-count test + SIS smoke + shim guard test) — is anything critical missing?
5. Does the 4-PR sequence feel right, or should PR3 (thread) be split further (e.g., into PR3a: move the outer wrapper; PR3b: move the pipeline)?
6. Any architectural concerns with keeping the 2000-line pipeline as a single function inside `grading/thread.py`? Alternative: move it to `grading/pipeline.py` as just a file move (no internal split), or is that premature?

---

## Not in this spec

- Phase 3b: `planner_routes.py` decomposition (separate spec, separate brainstorming cycle)
- Internal split of the 2000-line pipeline (requires unit tests first)
- Route handler migration out of app.py into blueprints (separate concern; handlers currently in app.py are mostly legacy and can stay for now)
- `format_rubric_for_prompt` relocation (deferred)
