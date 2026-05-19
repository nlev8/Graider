# Dual Publish-Path Consolidation (Repository Layer): Design

**Date:** 2026-05-19
**Status:** Design approved (user approved 2026-05-19). Next: writing-plans.
**Context:** The next lever after Tier 2 Slice 3. The post-Slice-3 3-model reconciled re-score (HEAD `d54ee8e`, dated section in `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`) held Architecture at 7 (2-1 split resolved down). Slice 3 cleanly removed one of the three concrete Architecture-7 grounds (the `app.py` route god-module). Two remain: no dependency injection, and the unconsolidated dual publish path dispatched by a `supabase_table` string parameter. All three models independently named the dual publish path as the single biggest remaining architectural boundary. This design targets exactly that ground, at the lowest risk that closes it.

## 1. Goal

Eliminate the `supabase_table` string dispatch in the submission-write and grading pipeline by introducing a `SubmissionRepository` abstraction with two adapters, so the grading pipeline has one code path instead of branching on a table-name string. Zero schema change, zero data migration, zero behavior change, fully reversible (code only). This closes the dual publish-path Architecture-7 ground without betting live FERPA student-submission data on a migration.

## 2. Problem

Graider has two parallel publishing systems that converge on one grading pipeline. The join-code path (anonymous, 6-char code) uses `published_assessments` and `submissions`; the class-based path (authenticated via Clever SSO or email plus code, enrollment required) uses `published_content` and `student_submissions`. Both funnel into `grade_portal_submission_sync()`, which is parameterized by a `supabase_table` string that selects `submissions` versus `student_submissions`. The pre-extraction map found this string threaded through eleven sites across five files, with the discriminating logic appearing as inline `if supabase_table == 'submissions':` branches inside the pipeline body (notably the student-id normalization and the accommodations-source difference).

This is not a missing pattern so much as an unfinished abstraction. The grading pipeline is already roughly eighty percent abstracted: `grade_portal_submission_sync()`, `fetch_submission_full_context()`, and `_safe_update_submission()` already accept the table as a parameter, and the shared graders (`grade_instant_only()`, `grade_student_submission()`) are already path-agnostic. What is missing is a typed boundary: the table-name string is passed positionally through threads and the Celery task, and the per-table behavior is open-coded as conditionals rather than encapsulated. The result is the boundary defect the re-score names: a string-keyed dispatch instead of a unified abstraction.

The physical two-table schema is deliberately not the target here. Consolidating `submissions` and `student_submissions` into one table is a separate, higher-risk lever (a backfill migration on live student-submission data) explicitly deferred to its own future brainstorm. This design closes the code boundary that the score is gated on, and is the prerequisite that makes any later physical consolidation safe to reason about.

## 3. The repository abstraction

A new module `backend/services/submission_repository.py` defines a narrow `SubmissionRepository` abstract base class with exactly the operations the grading pipeline performs today, each of which is currently `supabase_table`-parameterized:

- `fetch(submission_id) -> dict | None`: read the submission row.
- `claim_for_grading(submission_id, task_id) -> bool`: the row-level dedup claim (the existing `_claim_submission_for_grading` semantics: claim only if not already claimed, TTL-reclaim respected).
- `update(submission_id, fields: dict) -> None`: the existing `_safe_update_submission` write.
- `mark_failed(submission_id, error: str) -> None`: the failure-marking path used by the Celery `on_failure` hook.

The interface is intentionally minimal. Reads of `published_assessments`/`published_content`, the divergent dedup pre-check at the route layer, and the two HTTP entry routes are out of scope (section 8); the repository owns only the submission-row operations the pipeline body performs.

Two concrete adapters implement it:

- `JoinCodeSubmissionRepository`: operates on `submissions`.
- `ClassSubmissionRepository`: operates on `student_submissions`.

Each adapter encapsulates the per-table specifics that today live in `if supabase_table == ...` branches inside the pipeline, specifically the student-id normalization (currently `portal_grading.py` around lines 526-529) and the accommodations-source difference (the join-code path reads `published_assessments.settings`; the class-based path falls back to the row's `accommodations`). After this change those conditionals live inside the adapters, not in the pipeline body. Each adapter takes its supabase client by injection, so it is unit-testable with a fake client and no Flask context or network.

## 4. The Celery-boundary constraint and its resolution

`grade_portal_submission_sync()` is invoked from two execution contexts: a Celery task (the always-on join-code path, Phase 4.1 PR3) and a background thread (the class-based path, and the join-code enqueue-failure fallback). A repository object is not serializable across the Celery boundary, so the repository instance cannot be the thing passed to the task.

Resolution: a small serializable enum `SubmissionPathType` with members `JOIN_CODE` and `CLASS` is the discriminator that crosses every boundary. It replaces the `'submissions'`/`'student_submissions'` string literals at the spawn and enqueue sites. A single module-level factory `repository_for(path_type: SubmissionPathType, sb_client) -> SubmissionRepository` reconstructs the correct adapter worker-side. The grading pipeline calls `repository_for(...)` exactly once near entry and then uses only the `SubmissionRepository` interface; there is no table-name branching anywhere in the pipeline body after this change.

The Celery task signature shape is preserved: the enum's serialized value occupies the positional slot the `supabase_table` string occupies today, so the `on_failure` hook (which today extracts `args[2]` or the `supabase_table` kwarg) and the retry/dedup semantics are structurally unchanged. The enum is the only new value crossing the wire; nothing else about task scheduling, retry, or failure handling changes.

## 5. Bounded call-site changes

The change is mechanical and bounded to the write/grading dispatch layer:

- The four spawn/enqueue sites pass `SubmissionPathType.X` instead of the table string: the join-code Celery enqueue (`student_portal_routes.py` around line 1557), the two class-based thread spawns (`student_account_routes.py` around lines 830 and 1246), and the shared `_spawn_thread_grading` helper (`student_portal_routes.py` around lines 52-73).
- `grade_portal_submission_sync()`, `fetch_submission_full_context()`, `run_portal_grading_thread()`, and `backend/tasks/grading_tasks.py` replace the `supabase_table` parameter with the `SubmissionPathType` enum, construct the repository once via the factory, and route every submission-row read/claim/update/fail through the `SubmissionRepository` interface. The inline `if supabase_table == ...` branches in the pipeline body move into the adapters.
- The shared graders `grade_instant_only()` and `grade_student_submission()` are already path-agnostic and are not touched.

Line numbers are re-derived at implementation time before editing; the authoritative completeness check is a grep gate proving zero remaining `supabase_table` string dispatch in the pipeline path (section 6).

## 6. Behavior-preservation guarantee and verification net

This is a behavior-preserving refactor, not a verbatim move: call sites change (the parameter type changes, branches relocate). The discipline is therefore characterization-net-first, the same rigor used across Slices 1 through 3 but applied to a refactor rather than a pure relocation:

- **Characterization net pinned pre-change.** Before introducing the abstraction, an exhaustive net pins the exact observable contract of BOTH paths against the current `supabase_table` wiring: for the join-code path and the class-based path independently, the submit-to-graded lifecycle (status transitions: queued/partial to grading_in_progress to graded, the exact final results-row shape), plus the claim/dedup branch, the grading-failed branch, and the deferred branch. Both the Celery-backed join-code path and the thread-backed class-based path are exercised. The net is pinned green against the pre-change code and committed first.
- **Net stays byte-identical post-change.** After the abstraction is introduced, every pinned status and serialized body must still pass byte-identical. That equivalence is the zero-behavior-change proof.
- **Per-adapter unit tests.** Each adapter is tested in isolation with a fake supabase client (the new independently-testable units): fetch, claim (including the already-claimed and TTL-reclaim cases), update, mark_failed, plus the per-adapter student-id normalization and accommodations-source behavior that moved out of the pipeline body.
- **Grep gate.** Zero remaining `supabase_table` string-parameter dispatch in `backend/services/portal_grading.py`, `backend/tasks/grading_tasks.py`, and the spawn sites after the change (the enum and the repository replace it). Any residual string dispatch in the pipeline path fails review.
- **Full regression plus the 9 required CI checks** green on every PR; the existing portal, student-account, grading, and Clever suites stay green unchanged.

## 7. Approaches considered

- **Repository layer over the existing two tables, no schema change (chosen).** A `SubmissionRepository` ABC plus two adapters and a serializable-enum factory. Eliminates the string dispatch and gives the pipeline one code path. Zero data migration, fully reversible, builds on the already-parameterized seams, smallest blast radius that fully closes the scored ground. Standard pattern, scales cleanly if a third path ever appears.
- **Union table (one table with the union of both schemas plus many nullable per-path columns) plus data migration.** Rejected for this lever: an awkward nullable-heavy schema and a production data migration on live FERPA submission data, for no additional closure of the code boundary beyond what the repository achieves.
- **Unified table with a `path_type` discriminator plus computed `dedup_key`, backfill-migrating live data.** The cleanest physical end state and best future scalability, but the highest-risk, effectively irreversible option (a backfill migration on live student-submission data, careful indexing, a rollback plan). Explicitly deferred to its own future brainstorm; the repository layer is the prerequisite that makes it safe to reason about later.

## 8. Scope

**In:** the `backend/services/submission_repository.py` module (the `SubmissionRepository` ABC, the `JoinCodeSubmissionRepository` and `ClassSubmissionRepository` adapters, the `SubmissionPathType` enum, the `repository_for` factory); the refactor of `grade_portal_submission_sync()`, `fetch_submission_full_context()`, `run_portal_grading_thread()`, and `backend/tasks/grading_tasks.py` to use the enum and the repository; the four spawn/enqueue call-site enum swaps; the relocation of the per-table conditionals from the pipeline body into the adapters; the pre-change characterization net covering both paths; the per-adapter unit tests.

**Out (explicitly):** any schema change or data migration; the two HTTP entry routes (`/api/student/submit/<code>` and `/api/student/class-submit/<content_id>`) stay separate, each constructing its path's adapter and handing the enum in; the `published_assessments`/`published_content` read split and the divergent route-layer dedup pre-check (ilike-name-match versus `dedup_key`) stay where they are (a separable follow-up, recorded); the physical table consolidation (the union and discriminator options of section 7) deferred to its own future brainstorm; the frontend (`StudentPortal.jsx`, `api.js`) untouched; the dependency-injection Architecture-7 ground (a separate concern, not addressed here).

## 9. Risks and handling

- **Celery serialization.** A repository object cannot cross the Celery boundary. Resolved structurally in section 4: only the serializable `SubmissionPathType` enum crosses; the factory reconstructs the adapter worker-side; the task signature shape and `on_failure`/retry semantics are preserved.
- **Hidden per-table behavioral asymmetry beyond the known branches.** The student-id normalization and accommodations-source differences are the known divergences; there may be others. Mitigated by the characterization net pinning both paths' real observable contracts before any code moves, so any unmodeled asymmetry surfaces as a net failure rather than a silent production change.
- **The two execution contexts must both stay green.** The always-on Celery join-code path and the thread-backed class-based path are different runtimes. The net exercises both; full regression plus the 9 CI checks gate every PR.
- **Scope creep into the read/route/dedup split.** Explicitly fenced in section 8 and enforced by the grep gate scoping to the write/grading pipeline only; the routes keep their own published-content lookup and dedup pre-check unchanged.

## 10. Success criteria

One `backend/services/submission_repository.py` with a narrow `SubmissionRepository` ABC, two adapters, the `SubmissionPathType` enum, and the `repository_for` factory. The grading pipeline has a single code path with zero `supabase_table` string dispatch (grep gate proves it). The pre-change characterization net covering both the Celery join-code path and the thread class-based path is green before the refactor and byte-identical green after; per-adapter unit tests cover each adapter in isolation. Full local regression and all 9 required CI checks green on every PR; the existing portal, student-account, grading, and Clever suites unchanged-green. No schema change, no data migration, no frontend change. After the slice, a 3-model reconciled re-score is run, since whether closing the dual-path code boundary moves Architecture 7 to 8 is the judgment question this program tracks (the other remaining ground, no dependency injection, is untouched and will be weighed in that reconciliation); the reconciled effect is recorded in the assessment doc as its own dated section.
