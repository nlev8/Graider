# Phase 3a — Ready for Execution

**Date:** 2026-04-14
**Status:** Spec + plan complete, Codex Gate 1 GREEN on rev 2, awaiting execution.

## What this is

Phase 3 of the codebase improvement roadmap splits the app.py monolith (3528 lines) into a `backend/grading/` package. Phase 3a covers app.py only; Phase 3b (planner_routes.py — 8104 lines) is deferred to a separate spec.

## Key artifacts

- **Branch:** `spec/phase3a-app-refactor`
- **Spec:** `docs/superpowers/specs/2026-04-14-phase3a-app-refactor-design.md`
- **Plan:** `docs/superpowers/plans/2026-04-14-phase3a-app-refactor.md`

## Design (rev 2)

- **Migration pattern:** `init_app(app)` initializer — NOT a full `create_app()` factory. Module-level `@app.route` decorators stay at module level. Full factory deferred to Phase 3b+ when route handlers migrate to blueprints.
- **Module split:** 3 files under `backend/grading/`:
  - `state.py` (~220 LOC) — state dict + locks + `load_saved_results`/`save_results`
  - `thread.py` (~70 LOC) — BYOK wrapper; imports pipeline
  - `pipeline.py` (~2000 LOC) — `_run_grading_thread_inner` business logic, byte-identical move
- **PR4 adds:** `backend/services/rubric_formatting.py` — extracted from nested `format_rubric_for_prompt`; fixes latent `portal_grading.py:380` ImportError.

## 4-PR sequence

1. **PR1:** `init_app(app)` initializer. Zero code extraction. New `tests/test_app_boot.py` with boot check + route-snapshot test pinning SIS-critical endpoint paths + HTTP methods.
2. **PR2:** Extract state + persistence to `grading/state.py`. Shim in app.py. New `tests/test_grading_shims.py`.
3. **PR3:** Extract thread wrapper (`grading/thread.py` ~70 LOC) + inner pipeline (`grading/pipeline.py` ~2000 LOC). Shim extended. Byte-identical move.
4. **PR4:** Extract rubric formatter to `backend/services/rubric_formatting.py`. Migrate consumers (portal_grading × 3, assistant_tools_student × 2, email_routes × 1). Remove shim. Delete transitional test.

## Review history

- **Brainstorming** → identified scope decomposition, migration strategy, granularity.
- **Codex Gate 1 (rev 1)** → GREEN but flagged 3 gotchas (persistence with state, shim surface, format_rubric nested).
- **Gemini review (rev 1 spec)** → pushed back on 4 points: create_app risky → init_app; route-count weak → route-snapshot; format_rubric should move now → PR4 extract; thread.py semantic conflict → split to pipeline.py.
- **Codex tie-break** → accepted 3, tightened 1 (route snapshot must include HTTP methods).
- **Rev 2 committed.** Codex final Gate 1: **GREEN** on all 4 critical checks (init_app ordering, AST scan completeness, rubric closure verification, PR sequence integrity).

## Hard constraints for execution

- SIS compliance 180/180 green every PR (tests/test_sso_contracts.py + Clever/ClassLink/OneRoster suites)
- Coverage floor 32 (CI enforces; current 33.33%)
- Function bodies byte-identical across extraction PRs
- Zero Clever/ClassLink/OneRoster/roster_sync/oneroster_gradebook file modifications
- Every PR must boot (`python -c "from backend.app import app; print(len(app.url_map._rules))"` returns ≥ 250)

## Known gotchas (documented in spec)

- **Gotcha #1:** `load_saved_results`/`save_results` MUST move with state (circular import risk if `state.py` imports them from `backend.app`).
- **Gotcha #2:** Shim surface — `app.py` must keep re-exporting `_get_state`, `_get_lock`, `reset_state`, `_grading_states`, `save_results`, `load_saved_results`, `run_grading_thread`, `_run_grading_thread_inner` for backwards-compat through PR2 and PR3. Consumers at portal_grading.py:255,380,563 + assistant_tools_student.py:515,680 + email_routes.py:1102 + app.py:2055 register_routes injection + SIGTERM handler.
- **Gotcha #3:** `format_rubric_for_prompt` is nested inside `_run_grading_thread_inner` at line 587. No closure dependencies (Codex verified by reading backend/app.py:587-625). Moves with pipeline in PR3, extracted to own module in PR4.
- **Pre-existing latent bug:** `portal_grading.py:380` `from backend.app import format_rubric_for_prompt` has always ImportError'd when exercised (function was never module-importable). PR4 fixes by importing from the new `backend.services.rubric_formatting` module.

## Next session pickup

When resuming:
1. Check out `spec/phase3a-app-refactor` OR verify artifacts merged to main
2. Read plan + spec
3. Invoke `superpowers:subagent-driven-development`
4. Dispatch PR1 implementation subagent (init_app refactor is the simplest starting point, no code extraction)
5. Follow 4-gate Codex workflow per user's hard rule: "MUST be Codex confirmed, ALWAYS"

## Related memory

- `project_phase2_complete.md` — prior milestone (coverage floor 32, NotebookLM removed)
- `project_codebase_improvement_roadmap.md` — full 5-phase plan
- `feedback_always_recommit_after_review.md` — recommit plan files after each review so reviewer sees fresh revision
- `feedback_always_branch_for_new_work.md` — never commit to main
