# app.py Route God-Module Extraction: Design

**Date:** 2026-05-19
**Status:** Design approved (user approved 2026-05-19). Next: writing-plans.
**Context:** Tier 2 (Code Quality / Architecture decomposition) of the dimension roadmap, Slice 3. The 2026-05-18 3-model reconciled re-score held Architecture at 7 (2-1 split resolved down) specifically because `backend/app.py` is still a 1,935-LOC god-module with roughly 16 extractable API route functions plus the dual publish path. This slice targets that exact holdout. Slices 1 and 2 (planner_routes and assignment_grader extraction) are the proven precedent.

## 1. Goal

Move the three cohesive API route clusters out of `backend/app.py` (1,935 LOC) into three responsibility-named Flask Blueprints under `backend/routes/`, with zero behavior change, behind an exhaustive route-level characterization net. This shrinks `app.py` to the app-factory plus middleware plus SPA/static shell (about 650 LOC) and removes the concrete Architecture-7 objection.

## 2. Problem

`backend/app.py` has 28 `@app.route` decorators in 1,935 lines. Roughly 16 of them are domain API routes that have nothing to do with the app factory: grading-results CRUD, FERPA data operations, and student-history/roster reads. The remaining routes are the SPA/static shell (`/`, `/join*`, `/student*`, `/district*`, `/<path:path>`, `/healthz`, `/api/user-manual`) plus the factory itself (`set_security_headers`, `handle_404`/`handle_500`, `_handle_sigterm`, `init_app`, the `Flask(static_folder=...)` setup), which legitimately belong with the app shell. The codebase already has a clean per-domain blueprint convention (`backend/routes/*_routes.py`, wired through `from backend.routes import register_routes` at `app.py:433`), so the misplaced 16 routes are an unfinished decomposition, not a missing pattern. The grading-state coupling that historically blocked this was already removed: state lives in `backend/grading/state.py` and `backend/grading/thread.py`; the candidate routes import it, they do not close over `app.py` locals.

A pre-extraction scan of the candidate range found exactly one import-cycle risk: `get_audit_logs` (`app.py:254`), whose sole production caller is the FERPA `/api/ferpa/audit-log` route. It is FERPA-cohesive and has no app-local-state coupling. `AUDIT_LOG_FILE` is duplicated as a module-level constant in four files, but a canonical lower module already exists (`backend/utils/audit.py`, which also owns the `audit_log()` writer).

## 3. The coupling-reduction rule (adapted from Slices 1 and 2, section 3)

A route is "extracted" only if its blueprint module imports cleanly with **no import cycle back into `backend.app`**. Concretely:

- The new blueprint imports shared state exactly as `app.py` did (`from backend.grading.state import _get_state, _get_lock, reset_state, _grading_states, _states_meta_lock`; `from backend.grading.thread import run_grading_thread`; `student_history` and other shared helpers from their existing modules).
- A cluster-internal helper (defined inside the moved range and called only by the moved routes) co-moves with its cluster.
- The one identified cycle risk, `get_audit_logs`, co-moves into `ferpa_routes.py` (its only production caller is the FERPA audit-log route; it is FERPA-cohesive) and references `AUDIT_LOG_FILE` from the canonical `backend/utils/audit.py`, not the `app.py:243` duplicate. The now-unused `app.py:243` `AUDIT_LOG_FILE` constant is removed as a dead-constant cleanup. The broader four-way `AUDIT_LOG_FILE` duplication (`accommodations.py`, `utils/audit.py`, `routes/assistant_routes.py`, `app.py`) is recorded out-of-scope; it is a separate DRY concern, not this slice.
- If PR-time re-derivation finds a route that closes over a staying `app.py` local, that route stays in `app.py` and is recorded with the reason (the Slice 1 and 2 escape hatch). The scan found none beyond the resolved `get_audit_logs`.
- Moves are verbatim. `@app.route('/path', methods=[...])` becomes `@bp.route('/path', methods=[...])` with the path string and methods byte-identical; **no `url_prefix`**; every stacked decorator (`@require_teacher`, `@handle_route_errors`, rate-limit, and any others) preserved exactly and in original order; function bodies byte-identical.
- Zero behavior change. The nine existing route and integration suites stay green unchanged. The exhaustive route-level net is the evidence the move was wiring-safe.

## 4. Target blueprints (exact route lists)

Three new files under the existing `backend/routes/*_routes.py` convention, each a `Blueprint` registered via the existing `register_routes` aggregator (one line added per PR, no other wiring, no `url_prefix`):

### 4.1 `backend/routes/grading_results_routes.py` (PR 1; the literal Architecture-7 holdout; name avoids the existing `grading_routes.py`)
`/api/grade-individual`, `/api/delete-result`, `/api/update-approval`, `/api/update-approvals-bulk`. Plus the cluster-internal CSV-sync helpers `_remove_from_master_csv` and `_sync_approval_to_master_csv` (called only by these routes), which co-move.

### 4.2 `backend/routes/ferpa_routes.py` (PR 2; biggest LOC and the destructive/PII routes)
`/api/ferpa/delete-all-data`, `/api/ferpa/audit-log`, `/api/ferpa/data-summary`, `/api/ferpa/export-data`, `/api/ferpa/export-student`, `/api/ferpa/import-student`. Plus `get_audit_logs` co-moved (per section 3), referencing `backend/utils/audit.AUDIT_LOG_FILE`; the dead `app.py:243` constant removed.

### 4.3 `backend/routes/roster_routes.py` (PR 3; plus slice closeout)
`/api/student-history/<student_id>`, `/api/student-baseline/<student_id>`, `/api/retranslate-feedback`, `/api/extract-student-from-image`, `/api/add-student-to-roster`, `/api/list-periods`.

Line numbers are re-derived at implementation time before editing (they shift as earlier PRs land); a URL-map equality test plus the per-cluster grep are the authoritative completeness checks.

## 5. Sequencing and PR structure

Three sequenced PRs, in order 1 then 2 then 3, mirroring Slice 1's standards then export then prompts shape (smallest and lowest-risk first to prove the route-to-blueprint harness and the authed-test-client exhaustive-net pattern before the larger FERPA move). Each PR: build and pin the exhaustive net for that cluster against the current `@app.route` wiring, move the cluster verbatim, register the blueprint via `register_routes`, delete the cluster plus its now-unused imports from `app.py`, keep the net byte-identical and all existing suites green, full regression plus the 9 required CI checks, subagent-driven two-stage review (spec-compliance then code-quality). PR 3 also closes the slice (assessment-doc dated note, plan STATUS CLOSED, final `app.py` LOC, recorded out-of-scope items).

## 6. Exhaustive route-level characterization net (user choice B)

Before each cluster's move, drive every route in it through the existing authed test-client fixture (`tests/conftest_routes.py` `client`, which sets `g.user_id`). Pin status code plus the exact response JSON across the cross-product: each route times {happy path, auth-missing (401/403), invalid or empty input}; and for the destructive or PII routes (`ferpa/delete-all-data`, `ferpa/export-student`, `ferpa/export-data`, `delete-result`, `update-approvals-bulk`) additionally the not-found, empty-state, and partial-match branches plus the exact serialized body. The net is written against the current `@app.route` wiring, pinned green, committed, then after the move only the import path and blueprint change and every assertion must still pass byte-identical. That equivalence is the zero-behavior-change proof. The nine existing route and integration suites are the outer guard and must stay green unchanged.

## 7. Approaches considered

- **Three responsibility-named blueprints, sequenced small to big (chosen).** Genuine per-domain decomposition matching the codebase's existing `*_routes.py` convention, reviewable PRs, risk front-loaded out, exact mirror of the proven Slice 1 and 2 shape.
- **One `app_api_routes.py` catch-all blueprint, one PR.** Rejected: a roughly 1,200-LOC catch-all just relocates the monolith, the exact anti-pattern Slices 1 and 2 designs rejected.
- **Split by HTTP or technical shape (queries vs mutations, GET vs POST).** Rejected: splits by mechanism, not responsibility, producing low-cohesion modules and ignoring the established per-domain convention.

## 8. Scope

**In:** the three blueprint modules; the 16 listed routes moved verbatim; the cluster-internal helper co-moves; the `get_audit_logs` co-move plus canonical `AUDIT_LOG_FILE` import plus the dead `app.py:243` constant removal; the one-line-per-PR `register_routes` wiring; the exhaustive route-level net; removal of `app.py` imports left unused after each cluster leaves.

**Out (explicitly):** the SPA/static shell and factory routes (`/`, `/join*`, `/student*`, `/district*`, `/<path:path>`, `/healthz`, `/api/user-manual`, `set_security_headers`, `handle_404`/`handle_500`, `_handle_sigterm`, `init_app`, the `Flask(static_folder=...)` setup) all stay; the broader four-way `AUDIT_LOG_FILE` duplication; the dual publish-path consolidation (a separate, higher-blast-radius lever needing its own brainstorm); `PlannerTab.jsx` (the sequenced subsequent frontend lever); any behavior change; any route signature, URL, or decorator change.

## 9. Risks and handling

- **A lost or re-ordered decorator (auth bypass, error-handler drop).** The exhaustive net pins the auth-missing branch per route; a verbatim diff check confirms the decorator stack is byte-identical; the existing suites are the outer guard.
- **Import cycle back into `backend.app`.** The section 3 rule; the single identified risk (`get_audit_logs`) is resolved via the canonical `backend/utils/audit` import; the new blueprints import only stdlib, `backend.grading.*`, `backend.utils.*`, or siblings, never `backend.app`; verified per PR.
- **URL drift.** No `url_prefix`; literal paths preserved; a test asserts the URL map for the moved routes is unchanged before and after.
- **Hidden app-local closure.** The scan found none beyond `get_audit_logs`; if PR-time re-derivation finds one, that route stays and is recorded.

## 10. Success criteria

Three single-responsibility route blueprints exist, registered via `register_routes`. `backend/app.py` is reduced to the factory plus middleware plus SPA/static shell (about 650 LOC) with the 16 routes and their now-unused imports gone. URLs are byte-identical (a URL-map test proves it). The exhaustive net is green both before and after each move. Full local regression and all 9 required CI checks are green on every PR. The nine existing route and integration suites are unchanged-green. After PR 3, a 3-model reconciled re-score is run, since whether Architecture moves 7 to 8 is a judgment call (unlike the mechanically test-guarded extraction itself, which is proven by the verbatim net); the reconciled effect is recorded in the assessment doc.
