# Phase 3b1 — planner_routes.py post-processing helpers extraction design

> **Status:** FINAL rev 1. Codex + Claude brainstormed scope decomposition; Codex endorsed option (a) with 5-PR sequence and 5 risk callouts now incorporated.

**Date:** 2026-04-15
**Scope parent:** Phase 3 of `project_codebase_improvement_roadmap.md` (split monoliths).
**Scope of THIS spec:** Phase 3b1 — extract post-processing helpers from `backend/routes/planner_routes.py` (8104 LOC) into a new `backend/services/assignment_post_processing.py` module. Phase 3b2+ (route decomposition into feature blueprints) deferred to a separate spec.

---

## Goal

Reduce `backend/routes/planner_routes.py` from **8104 → ~5950 LOC** (−27%) by extracting the ~2150 LOC post-processing pipeline into a dedicated service module. Zero behavior change. SIS compliance (Clever/ClassLink/OneRoster) stays green throughout.

## Non-goals

- **No route splitting.** The 25 `@planner_bp.route` handlers stay in `planner_routes.py`. Phase 3b2+ concern.
- **No internal pipeline decomposition.** The 6-phase `_post_process_assignment` sequence + 12 hydrators move intact; splitting them is a later concern with real unit tests.
- **No behavior fixes.** Any latent bugs discovered during the move are documented, not fixed, unless they block the extraction.

## Hard constraints

- Clever/ClassLink/OneRoster/roster_sync/oneroster_gradebook files unchanged.
- SIS contract suite 180/180 green every PR.
- CI coverage floor 32 holds.
- Function bodies byte-identical for PRs 1, 2, 3, and 5. **PR4 is the sole approved exception** — `_auto_fix_flagged_questions` gets an explicit-context signature refactor (see Gotcha #1).
- Every PR must boot (`python -c "from backend.app import app; print(len(app.url_map._rules))"` returns ≥ 250).

---

## What moves

**Target file:** `backend/services/assignment_post_processing.py` (new, ~2150 LOC)

### Post-processing pipeline (the 6-phase sequence at `planner_routes.py:192-221`)
- `_post_process_assignment` (orchestrator)
- `_classify_question_type` (Phase 1)
- `_hydrate_question` (Phase 2 dispatcher) + 12 sub-hydrators + 1 inference helper:
  - `_hydrate_matching`, `_hydrate_geometry`, `_hydrate_data_table`, `_hydrate_box_plot`, `_hydrate_dot_plot`, `_hydrate_stem_and_leaf`, `_hydrate_transformations`, `_hydrate_fraction_model`, `_hydrate_unit_circle`, `_hydrate_protractor`, `_hydrate_grid_match`, `_hydrate_inline_dropdown`
  - `_infer_editable_columns` (called by `_hydrate_data_table`)
- `_validate_question` (Phase 3)
- `_is_project_question` (Phase 3b filter)
- `_validate_question_quality` + `_check_question_quality` (Phase 3c)
- `_auto_fix_flagged_questions` (Phase 3d — **needs context refactor, see Gotcha #1**)
- `_enforce_question_count` + `_count_questions` + `_build_question_count_instruction` (Phase 4)
- `_normalize_points` (Phase 5)
- `_merge_usage` (helper used across pipeline)

### Geometry + text utilities
- `_detect_primary_shape`, `_detect_mode`, `_is_identification_question`, `_infer_shape_answer`, `_looks_like_graphing_question`, `_extract_equations_from_text`, `_split_markdown_table`, `_extract_dimensions_from_text`, `_extract_pythagorean_sides`, `_compute_geometry_answer`

### Prompt builders
- `_build_subject_boundary_prompt`, `_build_section_categories_prompt`

### Cost tracking
- `_extract_usage`, `_record_planner_cost` — pure functions, no Flask `g` coupling (Codex verified lines 42-88). Safe to move without context refactor.

### NOT moved (stay in planner_routes.py)
- `load_standards`, `_get_standards_map`, `_load_standards_file`, `_grade_matches`, `_extract_grade_from_code` — standards loading is scope-ish but tied to route-specific config loading. Deferred to Phase 3b2.
- `load_support_documents_for_planning` — similar scope concern; stays.
- All `@planner_bp.route` handlers (25) and their helpers `_build_assignment_prompt`, `_save_grading_config_for_export`, `_question_to_visual_dict`, `_export_assignment_docx_graider`, `parse_template_structure`, `generate_qti_xml`.

---

## Migration strategy

**Incremental 5-PR sequence with import shims, following the Phase 3a playbook:**

### PR1 — Leaf helpers only (no cross-references to unmoved code)
Create `backend/services/assignment_post_processing.py`. Move ONLY helpers whose bodies do not reference any function staying in planner_routes.py:

- `_validate_question` (pure validator — uses `_REQUIRED_FIELDS` constant, moves together)
- `_enforce_question_count`, `_count_questions`, `_build_question_count_instruction` (Phase 4 trio — self-contained)
- `_normalize_points` (Phase 5 — pure math on points, uses `_DEFAULT_POINTS` constant, moves together)
- `_merge_usage` (pure dict merge)
- `_extract_usage`, `_record_planner_cost` (pure cost-tracking helpers per Codex — no Flask coupling; `PLANNER_COSTS_FILE` constant moves together)

**Constants moved with their sole consumers (3):** `PLANNER_COSTS_FILE`, `_REQUIRED_FIELDS`, `_DEFAULT_POINTS`.

**`_classify_question_type` deferred to PR2** — AST analysis (2026-04-15 pre-execution check, confirmed by Codex + Gemini) showed it calls 5 PR2 functions (`_is_identification_question`, `_detect_primary_shape`, `_detect_mode`, `_looks_like_graphing_question`, `_extract_equations_from_text`) and references `_ALL_GEOMETRY_TYPES` constant. Moving it alone creates NameError-at-call-time in the service module.

**Also deferred to later PRs to avoid service↔route import cycles:**
- `_post_process_assignment` — orchestrator calls `_hydrate_question` (moves PR2), `_validate_question_quality` (moves PR3), `_auto_fix_flagged_questions` (moves PR4). Stays in planner_routes.py until **PR5** when all callees have migrated.
- `_hydrate_question` — dispatcher calls 12 sub-hydrators (move PR2 together).

Add re-export shim in planner_routes.py so the moved functions remain callable at the old path for any tests that import directly from planner_routes.

**Safety rails added in PR1:**
- AST bound-name completeness test for service module (walks `LOAD_GLOBAL` bytecode, asserts all resolve — catches the NameError class automatically for all future PRs).
- Execution-based shim test (calls each moved function with minimal input, not just `callable()` assertion).

### PR2 — Classifier + hydrator dispatcher + all sub-hydrators + text/geometry utilities
Move `_classify_question_type` (deferred from PR1 — now co-located with its 5 callees) together with `_hydrate_question` dispatcher, all 12 sub-hydrators (`_hydrate_matching`, `_hydrate_geometry`, `_hydrate_data_table`, etc.), `_infer_editable_columns`, and the geometry/text utility suite (`_detect_*`, `_extract_*` except `_infer_editable_columns`, `_looks_like_*`, `_is_identification_question`, `_infer_shape_answer`, `_split_markdown_table`, `_compute_geometry_answer`). Dispatcher and its callees now co-located in the service. Shim continues re-exporting to planner_routes.

**Constants moved with their consumers (9):** `_TRUSTED_AI_TYPES`, `_ALL_GEOMETRY_TYPES`, `_SHAPE_KEYWORDS`, `_POLYGON_SIDES`, `_MODE_KEYWORDS`, `_ANALYSIS_PATTERN`, `_CALC_KEYWORDS`, `_FORMULA_RE`, `_GEOMETRY_DEFAULTS`.

### PR3 — Quality validation + project filter + golden tests
Move `_is_project_question`, `_validate_question_quality`, `_check_question_quality`. **ADD golden tests** that pin the 6-phase ordering end-to-end with known-input/known-output fixtures (Codex Gotcha #3). These tests lock the extraction contract before the riskiest PRs land.

**Constant moved with its consumer (1):** `_PROJECT_KEYWORDS`.

### PR4 — Auto-fix with explicit context
Move `_auto_fix_flagged_questions` behind a refactored signature that takes `user_id` and `client` as explicit parameters instead of pulling from Flask `g` and `backend.api_keys` (Codex Gotcha #1). Route call sites updated to pass the context. This is the ONLY non-byte-identical PR — the signature change is the risk surface; PR3's golden tests + handler smoke test guard the behavior.

### PR5 — Orchestrator + prompt builders + consumer migration + shim removal
Move the remaining pieces now that all their callees are already in the service module:
- `_post_process_assignment` (the 6-phase orchestrator — now safe to move because `_hydrate_question` is in PR2, `_validate_question_quality` in PR3, `_auto_fix_flagged_questions` in PR4; byte-identical body)
- `_build_subject_boundary_prompt`, `_build_section_categories_prompt` (pure prompt builders)

Migrate all route handler call sites in planner_routes.py to import directly from `backend.services.assignment_post_processing`. Remove the re-export shim.

**Why this sequence:** PR1 lands the seam and proves the import direction. PR2 moves the bulk mechanical code with zero semantic change. PR3 adds the behavioral safety net BEFORE the risky context-refactor in PR4. PR5 completes the migration with zero shim surface remaining.

---

## Gotchas flagged by Codex

### Gotcha #1 — `_auto_fix_flagged_questions` is not pure service code
Reaches into Flask `g.user_id` and `backend.api_keys`. Moving it as-is would couple `assignment_post_processing.py` to Flask globals — a regression relative to what a clean service boundary should be.

**Fix (PR4):** Refactor signature to take `user_id` and `client` (or a model-creation callable) as explicit parameters. Route call sites in `planner_routes.py` extract from `g` and pass explicitly. Service module has zero Flask dependency after extraction.

### Gotcha #2 — Hidden schema contracts in hydrators
Question dicts get mutated with aliases like `column_headers`→`headers`, `correct_answer`↔`answer`, `correctVertices` additions, placeholder expansion, editable-column inference (`_hydrate_matching`, `_hydrate_data_table`, `_hydrate_inline_dropdown`, etc., lines 1007-1418). Consumers downstream rely on these aliases.

**Fix (PR3):** Write golden tests with representative `q` dicts **before the risky PR4 context refactor lands**. Each test: run the pipeline, snapshot the output, pin the snapshot. PRs 1 and 2 are byte-identical moves so existing coverage protects them; the golden tests MUST exist before PR4 changes a function signature.

### Gotcha #3 — 6-phase ordering is behaviorally significant
`_post_process_assignment` runs in strict order (classify → hydrate → validate → project filter → quality validation → auto-fix → enforce count → normalize points). Earlier phases set fields later phases depend on.

**Fix:** Preserve ordering exactly. `_post_process_assignment` body stays byte-identical — only its *location* changes (moves to the service module in PR5 after all its callees have migrated). PR3's golden tests exercise the full chain, not individual phases, to catch any accidental reorder.

### Gotcha #4 — Tests may import planner_routes directly
Some existing tests may use `from backend.routes.planner_routes import _hydrate_question` or similar. Extraction breaks those imports unless the shim forwards them.

**Fix:** The re-export shim in planner_routes.py (PRs 1-4) keeps these tests green. PR5 migrates test imports to the canonical path before removing the shim. `grep -rn "from backend.routes.planner_routes import _" tests/` will enumerate the affected tests.

### Gotcha #5 — Route-side assumptions about post-pipeline state
`generate_assessment` specifically reads `warning` / `warning_severity` after `_post_process_assignment` (lines 6235-6250) and assumes specific numbering/points state after `_enforce_question_count` and `_normalize_points` have run. Other callers of the full pipeline (`generate_lesson_plan`, `generate_assignment_from_lesson`) are less exposed to these specific fields.

Note: `regenerate_questions` (lines 7257-7260) does NOT run the full pipeline — it calls classify/hydrate/validate only, so the warning-field invariants above do not apply there.

**Fix:** Add a handler-level smoke test in PR3 that calls `_post_process_assignment` via `generate_assessment`'s code path and asserts `warning` / `warning_severity` fields + total-points invariants. Plus a lightweight smoke for `regenerate_questions` to pin its three-phase-only usage.

---

## Safety net for Phase 3b1

Beyond standard workflow (branch + CI + Codex gates):

1. **Boot check after each PR:** `python -c "from backend.app import app; print(len(app.url_map._rules))"` must return ≥ 250.
2. **SIS contract suite**: 180/180 green every PR.
3. **Shim guard test** (transitional, created in PR1, deleted in PR5): pins that `_post_process_assignment`, `_hydrate_question`, etc. remain importable from `backend.routes.planner_routes` AND are callable from the canonical `backend.services.assignment_post_processing`.
4. **Golden tests** (permanent, created in PR3): representative `q` dicts in, expected `q` dicts out, covering:
   - Matching question with `column_headers` alias
   - Data table with `initial_data` inference
   - Geometry with dimension extraction + `correctVertices`
   - Fill-in-blank with placeholder expansion
   - Multi-question assignment exercising the full 6-phase chain (ordering regression guard)
5. **AST bound-name completeness test** (same pattern as Phase 3a `test_pipeline_global_refs_all_resolve`): walks `_post_process_assignment` bytecode, asserts every `LOAD_GLOBAL` resolves to the new module's namespace or a Python builtin.
6. **Handler-level smoke test** (Gotcha #5): added in PR3, asserts `generate_assessment` still returns `warning` / `warning_severity` fields + total-points invariants after the full pipeline runs; lightweight smoke for `regenerate_questions` asserts its three-phase subset works. Pins the route-side contract before PR4's context refactor could disrupt it.

---

## PR sequence summary

| PR | Moves | Net planner_routes.py delta | Risk |
|---|---|---|---|
| PR1 (leaf helpers) | 8 pure helpers (`_validate_question`, `_enforce_question_count`, `_count_questions`, `_build_question_count_instruction`, `_normalize_points`, `_merge_usage`, `_extract_usage`, `_record_planner_cost`) + 3 constants (`PLANNER_COSTS_FILE`, `_REQUIRED_FIELDS`, `_DEFAULT_POINTS`) ~220 LOC | −220 | Low — byte-identical move + shim + AST completeness test; no cross-refs to unmoved code |
| PR2 (classifier + hydrators) | `_classify_question_type` + `_hydrate_question` dispatcher + 12 sub-hydrators + `_infer_editable_columns` + ~10 text/geometry utils + 9 constants (`_TRUSTED_AI_TYPES`, `_ALL_GEOMETRY_TYPES`, `_SHAPE_KEYWORDS`, `_POLYGON_SIDES`, `_MODE_KEYWORDS`, `_ANALYSIS_PATTERN`, `_CALC_KEYWORDS`, `_FORMULA_RE`, `_GEOMETRY_DEFAULTS`) ~1430 LOC | −1430 | Medium — large move but pure functions; classifier co-located with its 5 callees |
| PR3 (quality + golden tests) | 3 quality functions (`_is_project_question`, `_validate_question_quality`, `_check_question_quality`) + 1 constant (`_PROJECT_KEYWORDS`) ~150 LOC + new golden test file + handler smoke | −150 | Medium — tests lock the contract before the risky PR4 |
| PR4 (auto-fix refactor) | `_auto_fix_flagged_questions` (~120 LOC) + signature refactor | −120 | HIGH — ONLY non-byte-identical PR (explicit context refactor). Route call sites must pass user_id/client explicitly. |
| PR5 (orchestrator + cleanup) | `_post_process_assignment` orchestrator (~30 LOC — safe to move now that all callees are in the service) + `_build_subject_boundary_prompt` + `_build_section_categories_prompt` (~95 LOC) + shim removal + consumer migration | −125 | Low — drop-in path rewrites, no new cycles |

**Final planner_routes.py size estimate:** ~5950 LOC (standards loading, support doc loading, all 25 route handlers, route-local helpers).

---

## Review outcomes (Codex scope consult)

Rev 1 chose option (a) over (b) routes-only and (c) both. Codex reasoning:
1. `_post_process_assignment` reused across 4 handlers — already a shared service, wrong file location
2. Route-first split would force new blueprints to import from a still-monolithic helper module — wrong dependency direction
3. The 12-hydrator pipeline is the highest-risk surface — isolating it first delivers the most architectural value per LOC
4. Helpers have shared mutation semantics that a service boundary would codify; routes are loosely coupled

Codex-endorsed 5-PR sequence + 5 risk callouts incorporated above.

---

## Not in this spec

- Phase 3b2+: Route decomposition into feature blueprints (`lesson_routes.py`, `assignment_gen_routes.py`, `assessment_routes.py`, `study_material_routes.py`). Separate spec, separate brainstorming cycle.
- Standards loading extraction (`load_standards`, `_get_standards_map`, etc.). Deferred to Phase 3b2 because it's tied to route-specific config loading.
- Internal split of the 6-phase pipeline (chopping hydrators into smaller units). Requires unit tests at hydrator level first — Phase 3b3+ or Phase 5 concern.
- Any fix of the `config`/`logger` latent bugs carried over from Phase 3a. Remain pre-existing and **explicitly allowlisted** in `PREEXISTING_LATENT` of `tests/test_pipeline_safety_rails.py::test_pipeline_global_refs_all_resolve` — same treatment as Phase 3a. If an analogous AST bound-name test is added for the new service module, use the same allowlist-with-comment pattern.
- Migrating `_post_process_assignment` call sites outside planner_routes.py (none known — Codex confirmed all 4 callers are internal to the file).
