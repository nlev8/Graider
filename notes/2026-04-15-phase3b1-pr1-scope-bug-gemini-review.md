# Phase 3b1 — PR1 Scope Bug & Proposed Correction (Gemini Review)

**Date:** 2026-04-15
**Status:** Finding confirmed by Codex. Proposed correction below. Seeking Gemini second opinion before amending spec/plan.

## TL;DR

The Phase 3b1 spec + plan claim PR1 moves 9 "leaf helpers with no cross-references to unmoved code." AST analysis disproves this for `_classify_question_type` (5 function cross-refs to PR2) and for 3 others with constant-only cross-refs. Codex also flagged additional constant cross-refs in PR2 and PR3 that the plan's scope tables never name. Proposed fix: **keep the 5-PR sequence but expand each PR's scope table to carry its required module-level constants/helpers together**.

## Background

Phase 3b1 extracts ~2150 LOC of post-processing helpers from `backend/routes/planner_routes.py` (8104 LOC) into a new `backend/services/assignment_post_processing.py` module. Artifacts:

- Spec: `docs/superpowers/specs/2026-04-15-phase3b1-planner-helpers-design.md`
- Plan: `docs/superpowers/plans/2026-04-15-phase3b1-planner-helpers.md`
- Review history: 8 Codex rounds all GREEN. Missed this class of bug.

The hard constraint every PR preserves: **function bodies byte-identical for PRs 1, 2, 3, 5**. PR4 is the sole signature-refactor exception (explicit-context refactor on `_auto_fix_flagged_questions`).

## The Bug

AST walk of `backend/routes/planner_routes.py` enumerating module-level references inside each PR1-scoped function:

| Helper | Cross-refs to unmoved code | Bomb class |
|---|---|---|
| `_extract_usage` (L42) | — | clean |
| `_record_planner_cost` (L59) | `PLANNER_COSTS_FILE` (L56) | constant |
| `_classify_question_type` (L744) | `_TRUSTED_AI_TYPES` (L735), `_ALL_GEOMETRY_TYPES` (L1488), `_is_identification_question`, `_detect_primary_shape`, `_detect_mode`, `_looks_like_graphing_question`, `_extract_equations_from_text` | **5 functions + 2 constants — RUNTIME NameError** |
| `_validate_question` (L879) | `_REQUIRED_FIELDS` (L850) | constant |
| `_build_question_count_instruction` (L1883) | — | clean |
| `_count_questions` (L1897) | — | clean |
| `_enforce_question_count` (L1905) | `_count_questions` | same-PR (OK) |
| `_merge_usage` (L1944) | — | clean |
| `_normalize_points` (L1977) | `_DEFAULT_POINTS` (L1962) | constant |

### Why it ships broken

If PR1 lands as the plan specifies, `backend/services/assignment_post_processing.py` will contain `_classify_question_type` calling `_is_identification_question` etc. Python resolves those names from the service module's globals at call time. They won't be there — they're in `backend/routes/planner_routes.py`. NameError on the first invocation via the service path.

Why CI misses it: the PR1 shim guard test asserts only `callable(fn)`. `callable()` returns True because the function object exists. It never executes the function. Test passes, module is broken.

This is the **same class** as the DOCUMENTS_DIR / `_check_batch_calibration` NameErrors that static Gate 3 missed in Phase 3a PR3, caught only by the exhaustive Codex pass with actual function calls.

## Codex Verdict (confirmed)

Codex rescue pass ran the AST check, re-read the spec + plan, and confirmed the finding. Codex also found additional cross-refs in PR2 and PR3 that the plan's scope tables never reference:

### PR2 missing-from-scope-table (7 constants)
- `_SHAPE_KEYWORDS` (L1431) — used by `_detect_primary_shape`
- `_POLYGON_SIDES` (L1464) — used by `_detect_primary_shape`
- `_MODE_KEYWORDS` (L1469) — used by `_detect_mode`
- `_ANALYSIS_PATTERN` (L1093) — used by `_hydrate_data_table`
- `_CALC_KEYWORDS` (L1098) — used by `_infer_editable_columns`
- `_FORMULA_RE` (L1102) — used by `_infer_editable_columns`
- `_GEOMETRY_DEFAULTS` (L1866) — used by `_hydrate_geometry`

### PR3 missing-from-scope-table (1 constant)
- `_PROJECT_KEYWORDS` (L240) — used by `_is_project_question`

### PR4/PR5
Codex found no additional scope-table bombs beyond intended prior-PR dependencies.

## Proposed Correction (Codex option C)

**Keep the sequential 5-PR plan. Expand each PR's scope table to carry its required constants/helpers together.** Every function still moves byte-identical; we're just making the scope table match the actual call graph.

### Revised PR1
- **Functions (8, down from 9):** `_extract_usage`, `_record_planner_cost`, `_validate_question`, `_build_question_count_instruction`, `_count_questions`, `_enforce_question_count`, `_merge_usage`, `_normalize_points`
- **Constants (new, 3):** `PLANNER_COSTS_FILE`, `_REQUIRED_FIELDS`, `_DEFAULT_POINTS`
- **Removed:** `_classify_question_type` (moves to PR2)

### Revised PR2
- **Functions (25, up from 24):** add `_classify_question_type` alongside existing dispatcher + 12 sub-hydrators + `_infer_editable_columns` + 10 geometry/text utils
- **Constants (new, 9):** `_TRUSTED_AI_TYPES`, `_ALL_GEOMETRY_TYPES`, `_SHAPE_KEYWORDS`, `_POLYGON_SIDES`, `_MODE_KEYWORDS`, `_ANALYSIS_PATTERN`, `_CALC_KEYWORDS`, `_FORMULA_RE`, `_GEOMETRY_DEFAULTS`

### Revised PR3
- **Functions (3, unchanged):** `_is_project_question`, `_validate_question_quality`, `_check_question_quality`
- **Constants (new, 1):** `_PROJECT_KEYWORDS`
- Golden tests + handler smoke unchanged

### PR4 + PR5
No scope changes needed.

## Secondary safety improvements

In addition to scope table correction, strengthen the test that catches this class of bug:

**Upgrade shim guard test** to also *invoke* each moved function with a minimal input. `callable(fn)` is insufficient — we need something that hits `LOAD_GLOBAL` instructions in the function body. Simplest: after PR1, add a `test_pr1_helpers_execute_without_nameerror` that calls each with representative inputs and asserts no NameError raised.

**Add AST bound-name completeness test for the service module in PR1** (same pattern as Phase 3a's `test_pipeline_global_refs_all_resolve`). Walks the module's bytecode, asserts every `LOAD_GLOBAL` resolves to the new module's namespace, a cross-module import, or a builtin. Codex Gotcha would have been caught at test-authoring time if this existed.

## Questions for Gemini

1. Is the proposed correction (option C) the right call, or would you restructure differently?
2. The revised PR2 scope grows from 24 to 25 functions + 9 new constants. Is that acceptable or should we split PR2 into PR2a (hydrators) and PR2b (classifier + geometry utils)?
3. Are the secondary safety improvements (execution-based shim test + AST bound-name completeness test) worth landing in PR1, or deferrable?
4. Any other concrete cross-ref bombs you spot in PR4 (`_auto_fix_flagged_questions` context refactor) or PR5 (`_post_process_assignment` orchestrator) that Codex missed?
5. Would you recommend holding the docs-only PR #70 until we amend the spec + plan, or merge as-is and fix the scope in PR1's branch?

## Files to review

- `docs/superpowers/specs/2026-04-15-phase3b1-planner-helpers-design.md`
- `docs/superpowers/plans/2026-04-15-phase3b1-planner-helpers.md`
- `backend/routes/planner_routes.py` (lines 42-90, 735-900, 1431-1500, 1866-1980)

Please return: verdict on each of the 5 questions above, plus any additional issues you spot. Target 300-500 words.
