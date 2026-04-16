# Phase 3b1 — COMPLETE

**Date:** 2026-04-15
**Status:** All 5 PRs merged. Phase 3b2+ (route decomposition) deferred to separate spec.

## Outcome

`backend/routes/planner_routes.py`: **8104 → ~5100 LOC (−37%)**
`backend/services/assignment_post_processing.py`: new module, **~2135 LOC, fully pure (zero Flask coupling)**

## 5-PR sequence (all squash-merged to main)

| PR | Title | Delta |
|---|---|---|
| #71 | PR1 — 8 leaf helpers + 3 constants | planner_routes 8104→7884, +backend/services/assignment_post_processing.py (248 LOC) |
| #72 | PR2 — 25 functions + 9 constants (classifier + hydrators + utils) | planner_routes 7884→6702, service module 248→1473 LOC |
| #73 | PR3 — 3 quality functions + 1 constant + 9 golden tests + handler smoke | planner_routes 6702→5319, service module 1473→1851 LOC |
| #74 | PR4 — `_auto_fix_flagged_questions` explicit-context signature refactor | sole non-byte-identical PR; service module gains `with_retry` import + refactored auto-fix |
| #75 | PR5 — orchestrator + prompt builders + shim removal + Alternative B | planner_routes ~5300→~5100 LOC; 49-name shim gone; Flask extraction via `_get_openai_context()` |

## Key architectural outcomes

- **Service module purity verified by AST test** — `dis`-level check that no `g`/`flask` LOAD_GLOBAL in `_auto_fix_flagged_questions` body
- **Explicit-context pattern** — `_post_process_assignment(..., *, user_id=None, client=None)`. Route handlers call `_get_openai_context()` helper and splat kwargs
- **Pipeline contract pinned** by 9 golden tests + 3 permanent contract tests (AST completeness, PR1 execution, auto-fix contract)
- **Sequential merge required** — each PR's minimal imports referenced prior PRs' moved names. PRs merged in order: #71 → #72 → #73 → #74 → #75

## Pre-execution scope correction (LESSON LEARNED)

Before writing any code, AST analysis caught that `_classify_question_type` was scoped to PR1 but calls 5 PR2 functions — would have been a runtime NameError bomb (same class as Phase 3a PR3's DOCUMENTS_DIR bug). Codex + Gemini review converged on the fix. This saved 1-2 days of debugging.

**Process change adopted:** AST bound-name completeness + execution-based tests ship in PR1, not PR3. Catches NameError class before it hits later PRs.

## Alternative B (spec reviewer-driven correction)

PR5 initially shipped with a Flask fallback inside the service's `_auto_fix_flagged_questions` — this preserved byte-identical orchestrator but weakened PR4's "zero Flask coupling" goal.

Spec reviewer recommended Alternative B: make `_post_process_assignment` accept `*, user_id=None, client=None` (1-line body deviation from byte-identical) and pass through to auto-fix. Deleted the dead adapter. 5 test patches migrated.

**Trade-off:** lost strict byte-identity on orchestrator (1-line kwargs addition); gained full service purity.

## Permanent safety rails (ship forward to Phase 3b2+)

1. `tests/test_planner_routes_shim.py` — 3 contract tests:
   - `test_pr1_helpers_execute_without_nameerror` (runtime execution smoke)
   - `test_service_module_global_refs_all_resolve` (AST LOAD_GLOBAL completeness)
   - `test_auto_fix_and_orchestrator_explicit_context_contract` (signature + purity via `dis`)

2. `tests/test_assignment_post_processing.py` — 9 golden tests pinning:
   - Hydration aliases (column_headers → headers, correct_answer ↔ answer)
   - Rectangle geometry defaults + answer computation
   - Validator downgrade behavior
   - Project filter regex branches
   - Quality validator MC mismatch + dedup
   - Quality checker answer-key gating
   - `_post_process_assignment` AST completeness
   - `_normalize_points` preservation of warning fields (Gotcha #5)

## Next phase

**Phase 3b2+** — split `planner_routes.py` routes into feature blueprints. Separate spec + brainstorming cycle required. Suggested decomposition:
- `lesson_routes.py` — lesson plan generation + export
- `assignment_gen_routes.py` — assignment generation flow
- `assessment_routes.py` — assessment generation + publishing
- `study_material_routes.py` — study guides, flashcards, slide decks

Should target another ~2000 LOC reduction of planner_routes.py if executed with the same discipline.

## Related docs + memory

- `docs/superpowers/specs/2026-04-15-phase3b1-planner-helpers-design.md` — spec (rev 3 final)
- `docs/superpowers/plans/2026-04-15-phase3b1-planner-helpers.md` — 5-task plan
- `project_phase3a_complete.md` (memory) — prior milestone
- `project_phase3b1_complete.md` (memory) — this milestone's record
- `project_codebase_improvement_roadmap.md` (memory) — full 5-phase plan

## Final verification metrics

- SIS compliance: 180/180 across all 5 PRs
- Coverage: 33.68% → 34.25% (floor 32 held throughout)
- Full test suite: 1433 → 1441 tests
- Zero Clever/ClassLink/OneRoster file modifications
- 2 Codex exhaustive Gate 3 runs (PR2, PR3) + direct runtime verification (PR4)
- Code quality + spec compliance review on every PR
