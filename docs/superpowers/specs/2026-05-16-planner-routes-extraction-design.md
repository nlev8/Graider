# planner_routes.py Service Extraction — Design

**Date:** 2026-05-16
**Status:** Design approved (user deferred to recommendation 2026-05-16). Next: writing-plans.
**Context:** Tier 2 (Code Quality / Architecture decomposition) of the dimension roadmap, first slice. User selected `planner_routes.py service extraction` from the Tier 2 decomposition as the lowest-risk, precedent-backed starting slice.

## 1. Goal

Move pure business logic out of `backend/routes/planner_routes.py` (6,050 LOC at `b0ebd54`) into focused `backend/services/planner_*.py` modules so each unit has one responsibility and is unit-testable without a Flask context. This raises Code Quality, Architecture, and Test Coverage at once, with zero behavior change.

## 2. Problem

`planner_routes.py` is the largest backend route file: 27 route endpoints plus 47 module-level functions in one file. Much of it is pure logic (standards loading, document export rendering, prompt building) that does not belong in a Flask route module and cannot be unit-tested without spinning the app. The grading post-processing pipeline was already extracted to `backend/services/assignment_post_processing.py` (planner_routes imports `_classify_question_type`, `_hydrate_question`, `_post_process_assignment`, `_validate_question`, etc. from it). That prior extraction is the proven precedent and must NOT be redone. The remaining misplaced logic falls into three clusters.

## 3. The coupling-reduction rule (anti-relocation guard)

This is the defining constraint, written because the prior `App.jsx` extraction relocated LOC instead of reducing coupling.

- A function is "extracted" only if it becomes callable and unit-testable **without a Flask request or app context**. The new test for it must import the service module and call the function directly, no test client.
- If a function cannot be called without app/request state, that is hidden coupling to fix by passing the dependency in as an explicit argument, not a reason to move it blindly. If a clean signature is genuinely infeasible for a specific function, it stays in `planner_routes.py` and is recorded as out-of-scope with the reason. Do not force a bad extraction.
- Route handlers shrink to: validate input, call the service function(s), `jsonify` the result. No business logic, no inline LLM adapter calls, no inline document generation inside handlers.
- Zero behavior change. Existing route and integration tests stay green unchanged. Each extracted module gets new unit tests that exercise it directly. Those unit tests are the evidence the coupling was actually severed; LOC reduction in `planner_routes.py` is a side effect, not the objective.

## 4. Target modules (exact functions, by current line)

Pattern mirrors existing siblings: `assignment_post_processing.py`, `worksheet_generator.py`, `assistant_tools_*`.

### 4.1 `backend/services/planner_standards.py` (PR 1 — first, smallest, purest)
Standards loading and matching, plus the support-doc/context helpers it co-locates with:
`_get_openai_context` (:81), `load_support_documents_for_planning` (:104), `_extract_grade_from_code` (:175), `_grade_matches` (:212), `_get_standards_map` (:236), `_load_standards_file` (:249), `load_standards` (:263). Roughly 260 LOC of mostly pure parsing/matching. First because it is the lowest-risk cluster and proves the methodology plus the service-unit-test harness.

Note: `_get_openai_context` likely assembles an LLM client/config. If it reads app config or env, the extraction passes that in explicitly (or the function returns a plain config object the caller wires). If that proves infeasible without dragging app state, it stays and is flagged per the rule in §3.

### 4.2 `backend/services/planner_export.py` (PR 2 — biggest LOC and Code-Quality win)
Document, visual, and platform-export rendering:
`_save_grading_config_for_export` (:2150), `_question_to_visual_dict` (:2282), `_export_assignment_docx_graider` (:2346), `_create_visual_for_question` (:3103), `parse_template_structure` (:4482), `generate_qti_xml` (:4814), `_get_export_dir` (:5528). Roughly 1.5k to 2k LOC. `_create_visual_for_question` is the most entangled (used by multiple export routes); before moving it, add characterization tests that pin its current output for a representative set of question types, then move it under that net.

### 4.3 `backend/services/planner_prompts.py` (PR 3 — small, pure)
Prompt construction: `_build_assignment_prompt` (:1298), `_build_period_differentiation_block` (:3692). Pure string building, trivially testable.

## 5. Sequencing and PR structure

Three sequenced PRs, one module each, in order 1 → 2 → 3. Each PR: move the cluster, replace in-route usage with imports of the new module (thin shim), add direct unit tests for the moved functions, keep all existing tests green, full regression plus the 9 required CI checks. Standards first deliberately: it is the smallest and purest, so it validates the extraction pattern and the unit-test harness before the larger, more entangled export move.

## 6. Approaches considered

- **Responsibility-split into three focused modules, sequenced small to big (chosen).** Genuine coupling reduction, reviewable PRs, risk front-loaded out.
- **One big-bang `planner_service.py` with all helpers.** Rejected: a 2k-LOC catch-all module just relocates the monolith, which is the exact anti-pattern this spike exists to prevent.
- **Extract only the export blob first.** Rejected: `_create_visual_for_question` is the most entangled function; making it the first move maximizes regression risk before the pattern is proven.

## 7. Scope

**In:** the three service modules; thin-shim route handlers for the moved logic; direct unit tests per module; characterization tests for `_create_visual_for_question` before its move.

**Out (explicitly):** redoing the already-extracted post-processing pipeline; refactoring route request-flow beyond the thin shim; dual publish-path consolidation or any other Tier 2 slice; any behavior change; touching `assignment_post_processing.py`.

## 8. Risks and handling

- **Hidden app/request coupling in a helper.** Handled by the §3 rule: pass dependencies explicitly, or leave the function and record why. The unit test (must run with no Flask client) is the objective check.
- **`_create_visual_for_question` entanglement.** Characterization tests pin current output before the move; existing export route tests stay as the behavior guard.
- **Import cycles** (`planner_routes` ↔ new service ↔ `assignment_post_processing`). The new modules must not import from `planner_routes`. If a shared helper is needed by both, it goes in the lowest service module, not back in routes.
- **Net behavior drift.** Each PR runs full regression; the 9 CI checks (including the route/integration suites) gate every PR.

## 9. Success criteria

`planner_routes.py` route handlers are thin (validate, call service, jsonify) for the moved areas. Three single-responsibility `planner_*.py` modules exist, each with unit tests that run without a Flask context. Full local regression and all 9 required CI checks green on every PR. No behavior change observable in the existing route/integration tests. Reconciled effect recorded in the assessment doc after the third PR (Code Quality / Architecture nudge; no multi-model re-score required since the change is mechanically test-guarded, like Data Integrity Tier 1).
