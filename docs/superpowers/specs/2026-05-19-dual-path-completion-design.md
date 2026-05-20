# Dual Publish-Path Consolidation: Completion (Routes, Reads, Dedup, #431) — Design

**Date:** 2026-05-19
**Status:** Design approved (user approved 2026-05-19). Next: writing-plans.
**Context:** Tier 2 Slice 5 of the dimension roadmap, the natural sequenced continuation of Slice 4. Slice 4 (PR1 #430 + PR2 #432) closed the dual-path string-dispatch boundary at the write and grading layer; the post-dual-path 3-model reconciled re-score (PR #433, HEAD `6767d3e`) held Architecture at 7 because the consolidation was deliberately write-layer-only — the two HTTP entry routes, the `published_assessments`/`published_content` read split, and the divergent route-layer dedup pre-check were all still separate, and three transitional residuals (tracked in #431) remained from PR2's char-net contract. This slice closes the second half of Architecture ground 1 by completing the consolidation at those layers, and retires #431. The no-DI Architecture ground 3 remains a separate future lever. Implementation is gated on Railway recovery from the 2026-05-19 outage (production was unreachable when this design was approved); brainstorm and plan can land now since they are documentation.

## 1. Goal

Eliminate the remaining path-specific code in the two HTTP entry routes and the `published_*` read split by introducing a parallel `PublishedContentRepository` abstraction and extending `SubmissionRepository` with a route-layer dedup pre-check method; retire the three #431 transitional residuals. Behavior-preserving: no schema change, no data migration, no HTTP endpoint consolidation, characterization net byte-identical pre and post.

**STATUS: CLOSED 2026-05-20** — shipped via PR1 (#443: PublishedContentRepository module + ABC extension + char-net extension + test migration) and PR2 (route rewire + #431 fold-in). Second half of Architecture ground 1 closed. Zero schema change, zero behavior change.

## 2. Problem

Three connected residuals after Slice 4:

- **The two HTTP entry routes still carry path-specific code.** `student_portal_routes.py` `/api/student/submit/<code>` (join-code, anonymous) and `student_account_routes.py` `/api/student/class-submit/<content_id>` (class-based, token-authenticated) each open-code their published-content lookup, their dedup pre-check, and their submission upsert and grading dispatch. The submission write and grading dispatch went through `SubmissionRepository` in Slice 4; the lookup and dedup did not.
- **The `published_*` read split is unconsolidated.** Join-code reads `published_assessments` by `join_code`; class-based reads `published_content` by `content_id`. Both queries happen inline in their respective routes. No abstraction parallel to `SubmissionRepository` exists for this table family.
- **Dedup pre-check is semantically divergent.** Join-code uses `db.table('submissions').select('id, results').eq('join_code', code).ilike('student_name', name)` to fuzzy-match anonymous student names. Class-based uses an exact-match query on `student_submissions` keyed by authenticated `student_id` (Phase 4.1's `dedup_key` composite). The mechanisms are genuinely different because the auth models are different; the join-code path is fuzzy because anonymous students may type names slightly differently across attempts, and the class-based path is exact because the student is authenticated and has a stable UUID.
- **#431 transitional residue persists.** PR2's byte-identical-char-net contract forbade mutating pinned assertions, leaving three items: (a) `grading_tasks.py` `on_failure` still calls `_safe_update_submission` rather than `repo.mark_failed` because the char net patches that module symbol; (b) `_fetch_submission_row` and `_claim_submission_for_grading` are dead in production but retained because the PR1 char net references them; (c) `grade_portal_submission_sync` and `run_portal_grading_thread` kept the param name `supabase_table` (default now the enum value string) to avoid churning signature-pin tests.

## 3. Two parallel repository abstractions

Mirroring the PR1/PR2 shape that worked for the write/grading layer.

**New `backend/services/published_content_repository.py`.** A new abstraction sibling to `SubmissionRepository`:

- `PublishedContentRepository` ABC. Single method `fetch_by_lookup_key(key) -> dict | None`.
- `JoinCodePublishedRepository` (table `published_assessments`, lookup column `join_code`).
- `ClassPublishedRepository` (table `published_content`, lookup column `id`).
- Reuses the existing `SubmissionPathType` enum from `submission_repository`.
- Parallel factory: `published_content_repository_for(path_type, sb) -> PublishedContentRepository`.

Each adapter encapsulates its table name and the per-path lookup column behind a uniform interface; the route caller does not need to know which table is queried or by which column.

**Extension to `SubmissionRepository`.** Add a route-layer dedup pre-check method that semantically reads the submissions tables (so it fits `SubmissionRepository`'s existing scope of "submission-row I/O" rather than expanding `PublishedContentRepository`):

- New method `find_existing_submission(lookup_key, student_info) -> Optional[ExistingSubmission]`.
- `JoinCodeSubmissionRepository`'s implementation does `self._sb.table('submissions').select('id, results').eq('join_code', lookup_key).ilike('student_name', student_info['name']).execute()` and returns an `ExistingSubmission(id=..., results=..., student_name=...)` or None. Preserves the fuzzy anonymous-student dedup exactly (the `ilike` matcher is the byte-faithful contract).
- `ClassSubmissionRepository`'s implementation does the exact-match query on `student_submissions` keyed by `student_id` (preserving the Phase 4.1 authenticated dedup), returns `ExistingSubmission(id=..., results=None, student_name=None)` since the class path's existing dedup query selects only id today, or `results=...` if extending the select to include results is behavior-preserving (verify against current route code).

Return shape unification via a small dataclass:

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class ExistingSubmission:
    id: str
    results: Optional[dict] = None
    student_name: Optional[str] = None
```

Each adapter populates the fields its current query selects; the route caller handles None vs hit and uses whatever fields are available. This solves the return-shape divergence (join-code returns inline results so the "you've already submitted, here are your results" path works; class-based today returns only id) without forcing either path to change what it selects.

## 4. Route-layer rewire

The two HTTP entry routes stay separate. They have different auth contracts (anonymous-via-code vs token-authenticated), different URL shapes, and different post-submit response shapes. Collapsing them into one endpoint with a mode parameter would expand blast radius into the frontend (`api.js`, `StudentPortal.jsx`) and the auth path, which is out of scope and explicitly deferred (spec section 8). What changes is the body of each route:

```python
# Same shape in both routes, with path-specific lookup_key + student_info plumbing.
content_repo = published_content_repository_for(path_type, db)
submission_repo = repository_for(path_type, db)

published = content_repo.fetch_by_lookup_key(lookup_key)
if not published:
    return jsonify({"error": "Content not found"}), 404

existing = submission_repo.find_existing_submission(lookup_key, student_info)
if existing:
    return jsonify(existing_to_response(existing))

# Upsert + spawn grading via submission_repo: existing PR2 path, unchanged.
# Each route keeps its current upsert/spawn block; only the lookup + dedup
# pre-check above changes.
```

`existing_to_response` is a small per-route helper that formats the response in the shape that route already returns today (the join-code route returns `{"existing": True, "results": ...}` etc.; the class-based route returns its own shape). The dataclass is the data transport; the per-route helper is the presentation layer. This keeps the routes' HTTP contracts byte-identical without forcing a shared response shape.

## 5. #431 fold-in (all three items, bundled in this slice)

The char-net contract that forbade these in PR2 no longer binds because this slice migrates the relevant tests as part of the work, then deletes the helpers / unifies the write / renames the params:

1. **Unify the terminal-failure write.** Migrate `TestFailureSeam` (in `tests/test_dual_path_consolidation_char.py`) and `tests/test_grading_tasks.py` from patching `backend.services.portal_grading._safe_update_submission` to patching `backend.services.submission_repository.SubmissionRepository.update` (or `.mark_failed`, whichever asserts cleanest). Then switch `grading_tasks.py` `on_failure` from `_safe_update_submission(sb, submission_id, {...}, table_name=supabase_table)` to `repository_for(supabase_table, sb).mark_failed(submission_id, exc)`. Database effect is provably identical (same table via the enum value, same `{'status':'failed','error_message':str(exc)[:500]}` fields). Closes #431 item 1.
2. **Retire the orphaned helpers.** Migrate `TestClaimSeam` and `tests/test_grade_portal_submission_sync.py` from referencing `_fetch_submission_row` / `_claim_submission_for_grading` directly to referencing `SubmissionRepository.fetch` / `.claim_for_grading`. Once tests no longer pin the helpers, delete `_fetch_submission_row` and `_claim_submission_for_grading` from `portal_grading.py` (both have zero production callers post-PR2; verify with grep before deleting). Closes #431 item 2.
3. **Rename `supabase_table` to `path_type`.** On `grade_portal_submission_sync` and `run_portal_grading_thread`. Update the signature-pin tests (`sig.parameters['supabase_table'].default == 'student_submissions'` style assertions) to the new name. Default value remains `SubmissionPathType.CLASS` (the enum, not the string). `repository_for` already coerces both forms so internal callers passing strings continue to work. Closes #431 item 3.

## 6. Characterization-net-first methodology

PR2's discipline applied at the route layer. Extend `tests/test_dual_path_consolidation_char.py` (or add a new sibling file scoped to route-layer if the existing file gets too large) to pin both routes' full request-to-response observable contract before any rewire:

- Happy path: submit a new assessment, get the expected response (and observe the grading thread or Celery enqueue happen).
- Dedup hit: submit again with the same name + code (join-code) or same student + content (class-based), get the existing-results response (join-code) or the exact dedup contract (class-based).
- Missing content: submit to a nonexistent join_code / content_id, get the expected 404.
- Invalid input: missing required field, get the expected 400.

Pin against the current code, commit; then introduce the abstractions (PR1) and rewire the routes (PR2); the extended net stays byte-identical post-rewire. That equivalence is the zero-behavior-change proof for the route layer, exactly as the write-layer char net proved Slice 4's PR2.

Per-adapter unit tests for `PublishedContentRepository` and for `SubmissionRepository.find_existing_submission` use the same `FakeSupabase` test client that the existing `tests/test_submission_repository.py` already provides.

## 7. Approaches considered

- **Parallel `PublishedContentRepository`, route layer stays two endpoints (chosen).** Sibling abstraction mirroring SubmissionRepository's narrow-single-responsibility pattern. Lowest blast radius that closes the named ground. Routes' HTTP contracts unchanged. The proven Slice 4 shape.
- **Extend `SubmissionRepository` to absorb published-content reads.** Rejected: broadens the repo's responsibility beyond submission-row I/O. Risk of god-object as more table families fold in (the spec for the original consolidation explicitly noted this risk).
- **Rename `SubmissionRepository` to `DualPathRepository` and absorb everything.** Rejected: forces a multi-file rename of the now-load-bearing PR2 abstraction with high churn, and the god-object risk applies the same way.
- **Collapse the two HTTP routes into one endpoint with a mode parameter.** Rejected: explicit out-of-scope. Different auth contracts (anonymous-via-code vs token-authenticated), different URL shapes, would propagate into frontend `api.js` and `StudentPortal.jsx` and the auth path. The architectural boundary defect this slice addresses is the per-path code inside the routes, not the routes' existence as separate endpoints.

## 8. Scope

**In:**

- `backend/services/published_content_repository.py` (new): the ABC, two adapters, the parallel factory.
- `backend/services/submission_repository.py` (extend): `find_existing_submission` method on the ABC plus per-adapter implementations; the `ExistingSubmission` dataclass.
- `backend/routes/student_portal_routes.py` (rewire): the `/api/student/submit/<code>` body uses the two repos via the shape in section 4.
- `backend/routes/student_account_routes.py` (rewire): the `/api/student/class-submit/<content_id>` body uses the two repos via the same shape.
- `tests/test_dual_path_consolidation_char.py` (extend): route-layer char-net cases pinning both routes' full request-to-response observable contract for happy / dedup-hit / 404 / 400 branches.
- `tests/test_submission_repository.py` (extend): per-adapter unit tests for `find_existing_submission`.
- `tests/test_published_content_repository.py` (new): per-adapter unit tests.
- `backend/services/portal_grading.py` (cleanup): delete `_fetch_submission_row` and `_claim_submission_for_grading` once the char-net assertions migrate to the repo methods. Rename `supabase_table` param to `path_type` on `grade_portal_submission_sync` and `run_portal_grading_thread`.
- `backend/tasks/grading_tasks.py` (cleanup): switch `on_failure` to `repository_for(supabase_table, sb).mark_failed(submission_id, exc)` once `TestFailureSeam` migrates to repo-method patching.
- `tests/test_dual_path_consolidation_char.py` and `tests/test_grading_tasks.py` (test migration): assert against `SubmissionRepository.update` / `.mark_failed` instead of `_safe_update_submission`.
- `tests/test_grade_portal_submission_sync.py` (test migration): assert against `SubmissionRepository.fetch` / `.claim_for_grading` instead of the orphan helpers; remove `_is_stale_claim`-touching tests' helper references but keep `_is_stale_claim` itself unchanged.

**Out (explicit):**

- No schema change, no data migration, no physical table consolidation (still the future end-state lever; the spec for Slice 4 deferred it).
- No HTTP endpoint consolidation (the two routes stay two routes with their current paths, methods, and auth contracts).
- No frontend change (`api.js`, `StudentPortal.jsx`, and the auth flows are untouched).
- No dependency-injection introduction (Architecture ground 3 is a separate lever).
- No change to `_is_stale_claim` (still pipeline-scoped, still in `portal_grading.py`, still has its own char-net test).
- No change to the grading pipeline body beyond what the #431 cleanup mandates.

## 9. Sequencing: two PRs

Mirrors the PR1/PR2 split that worked for the write/grading slice. Each PR is reviewable on its own, and the additive PR1 is behavior-change-impossible by construction.

- **PR1 (additive):** `published_content_repository.py` module + 2 adapters + factory + per-adapter unit tests. Extension of `SubmissionRepository` with `find_existing_submission` + per-adapter unit tests. Extension of the char net to pin route-layer behavior pre-rewire. Migration of `TestFailureSeam`, `TestClaimSeam`, `tests/test_grading_tasks.py`, and `tests/test_grade_portal_submission_sync.py` from patching the module-level helpers to patching the repo methods (all tests still pass; nothing in production wired yet). Behavior change impossible by construction because no production code imports the new module yet and no route is rewired.
- **PR2 (the rewire):** Route bodies in `student_portal_routes.py` and `student_account_routes.py` use the new repos via the shape in section 4. Orphaned `_fetch_submission_row` and `_claim_submission_for_grading` deleted from `portal_grading.py`. `on_failure` in `grading_tasks.py` switched to `repo.mark_failed`. `supabase_table` param renamed to `path_type`. Extended char net stays byte-identical post-rewire (zero-behavior-change proof). Grep gate: zero direct `db.table('published_assessments')` or `db.table('published_content')` calls remain in `student_portal_routes.py` / `student_account_routes.py` outside the dedup-helper path; zero raw `db.table('submissions').select('id, results').eq('join_code', ...).ilike(...)` dedup queries remain in the routes (now go through `submission_repo.find_existing_submission`).

## 10. Risks and handling

- **Dedup return-shape divergence** (join-code's `select('id, results')` vs class-based's `select('id')`): solved by the `ExistingSubmission` dataclass with `results` as an optional field. Each adapter populates what its current query selects. Caller handles None vs hit and uses whatever fields are available. Both routes' HTTP responses stay byte-identical because the per-route `existing_to_response` helper formats from the dataclass into each route's existing response shape.
- **Fuzzy `ilike` join-code dedup semantic must be byte-preserved.** A typo'd name retry should not dedup; the existing route depends on this for the anonymous-student dedup contract. The `JoinCodeSubmissionRepository.find_existing_submission` implementation does the exact `ilike` query the route does today, with no normalization or trimming added. Char net pins a typo'd-name-no-dedup case explicitly.
- **#431 char-net migration ordering matters.** Tests must migrate to repo-method patching BEFORE the helpers are deleted, or assertions break. PR1 (additive) handles this safely: tests migrate in PR1 with the helpers still in place; helpers are deleted in PR2 once the tests no longer pin them.
- **Both execution contexts must stay green.** The always-on Celery join-code path and the thread-backed class-based path are different runtimes. The route-layer char net exercises both; full regression plus the 9 CI checks gate every PR.
- **Implementation gated on Railway recovery.** As of the 2026-05-19 production incident (recorded separately in PR #434's OpSafety roadmap), Railway non-enterprise builds were throttled. Spec and plan land now (docs only). Code PRs land when Railway is back.

## 11. Success criteria

`backend/services/published_content_repository.py` exists with the ABC, two adapters, factory, and per-adapter unit tests. `SubmissionRepository.find_existing_submission` exists with per-adapter implementations and unit tests; the `ExistingSubmission` dataclass is the return type. The two HTTP routes' bodies in `student_portal_routes.py` and `student_account_routes.py` use the parallel repos via the shape in section 4 with zero direct `db.table('published_*')` queries and zero raw dedup queries remaining in those routes. The grep gate proves it. The char net is extended to pin both routes' full request-to-response contract pre-rewire and stays byte-identical post-rewire. `_fetch_submission_row` and `_claim_submission_for_grading` are deleted from `portal_grading.py`. `on_failure` in `grading_tasks.py` calls `repo.mark_failed`. `supabase_table` is renamed to `path_type` on the two pipeline functions. Issue #431 is closed by reference in the slice closeout. Full local regression and all 9 required CI checks green on every PR; the existing portal, student-account, grading, Clever, and char-net suites stay green. After PR2, a 3-model reconciled re-score is run against the post-Slice-4 baseline; the open question is whether closing the second half of Architecture ground 1 and retiring #431 moves Architecture 7 to 8, with ground 3 (no DI) still open. The reconciled effect is recorded in the assessment doc as its own dated section.
