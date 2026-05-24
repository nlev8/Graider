# Backend Route De-concentration — Wave 5 (Code Quality 8 → 9)

**Status:** Design approved (standing sprint authorization). Brainstormed via `superpowers:brainstorming` with 3-model consultation (Claude controller first-hand + Codex + Gemini, unanimous, conservative-floor). Next: `superpowers:writing-plans`.

**Goal:** Move the **Code Quality** assessment dimension from 8 → 9 by de-concentrating the largest remaining *backend* god-files, behavior-preservingly, into the repo's established `backend/services/` pattern. This spec covers **Wave 5 Slice set A: `backend/routes/student_portal_routes.py`** (3,686 LOC). Later files (`planner_routes.py`) get their own spec once this gate is proven.

**Architecture:** Move cohesive logic out of the route module into Flask-free service modules under `backend/services/`, then **re-import the moved names back into the route module** ("re-export shim"). Every existing call site and test continues importing from `student_portal_routes` unchanged, so the existing pytest suite *is* the byte-identical characterization net; new direct unit tests pin each service.

**Tech Stack:** Python / Flask, pytest. No new dependencies.

---

## 1. Why this file, why now

The frontend god-files are done behavior-preservingly (App.jsx 7,144→4,810; PlannerTab 7,405→1,453; SettingsTab 6,534→1,576). The standing assessment (`docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`) states Code Quality 9 "needs **broad de-concentration** across the remaining backend god-files, not any single file." The concentrated backend mass is:

- `assignment_grader.py` — 5,344 LOC — **OFF-LIMITS** (grading engine; requires explicit separate user steer; not touched in this wave).
- `backend/routes/planner_routes.py` — 4,611 LOC — later wave.
- `backend/routes/student_portal_routes.py` — 3,686 LOC — **this wave**.

`student_portal_routes.py` is the correct first lever (3-model unanimous):

1. **Lowest extraction risk.** A contiguous block of Flask-free pure helpers spans lines 92–897 — no `request` / `g` / `session` / `jsonify` access (verified: the only matches in that range are prose inside docstrings). Relocation needs no change to decorators, request parsing, auth, or client-visible signatures.
2. **Strongest existing test net.** The exact helpers already have direct unit tests: `tests/test_aggregation_helpers.py`, `tests/test_mastery_shape.py`, `tests/test_sanitize_mastery_shape.py`, `tests/test_student_report_card.py`, `tests/test_gradebook.py`, `tests/test_remediation.py`, `tests/test_remediation_cap.py`, `tests/test_remediation_perstudent.py`. These import the helpers *from the route module*, so the re-export shim keeps them green with zero edits — they become the characterization gate for free.
3. **Highest signal per moved line.** `planner_routes.py`'s remaining bulk is AI-call / prompt-assembly / file-export route-body orchestration (`generate_lesson_plan`, `generate_assessment`, `export_generated_assignment`), which costs more to characterize. Pure helpers move cleanly first.

**What "8 → 9" actually requires (not busywork):** routes reduced to auth/request/response adapters, with business complexity encapsulated in stable, named, Flask-free, independently-tested domain services. LOC deletion is a side effect, not the goal. The signal is the *boundary*, not the byte count.

## 2. The extraction pattern (the gate)

Each slice is a **pure relocation**:

1. Create `backend/services/<module>.py`. Move the target functions **verbatim** (byte-identical bodies — never "improve", "clean up", or "fix" during a move; latent quirks are preserved exactly).
2. In `student_portal_routes.py`, replace the moved definitions with a re-import: `from backend.services.<module> import (name1, name2, ...)`. This **re-exports** the names from the route module, so:
   - existing route-body call sites resolve unchanged;
   - existing tests that `from backend.routes.student_portal_routes import <name>` resolve unchanged;
   - existing tests that `patch('backend.routes.student_portal_routes.<name>')` still patch the route-module binding (see Landmine R1).
3. Add a new direct unit-test file `tests/test_<module>.py` importing from `backend.services.<module>` and pinning the moved behavior (re-use/duplicate the existing fixtures).
4. Run the full suite + the 9 CI checks. Green = behavior-preserved.

**Gate per slice (all must pass):**
- Free-variable scan on each moved function = zero unresolved names in the new module (every referenced name is a param, a local, a module import, or a stdlib/global).
- `git diff` of each moved function body = byte-identical (a normalization-tolerant comparison; no logic change).
- Existing pytest suite green (the characterization net).
- New service unit tests green.
- `Ruff Lint`, `Bandit SAST`, `Mypy Strict (Critical Modules)`, `Backend Tests --cov-fail-under=60`, and the rest of the 9 branch-protection checks green.
- Two-stage subagent review (spec-compliance, then code-quality) per PR.

## 3. Service module boundaries

### `backend/services/student_mastery.py` (Slice 1)
Pure mastery/trajectory computation. Functions (move verbatim, re-export from route module):
- `_parse_ts` (timestamp parse helper)
- `_coalesce` (first-non-None helper)
- `_select_submissions_by_mode` (attempt-mode selection)
- `_aggregate_mastery_for_student`
- `_build_standards_breakdown_for_student`
- `_build_trajectory_for_student`
- `_normalize_mastery_shape`
- `_flatten_mastery_for_response`
- `_sanitize_standards_mastery`

All are Flask-free. Some take `db` as an explicit argument — that stays a parameter (never acquire the client inside the service; see Landmine R2).

### `backend/services/student_remediation.py` (Slice 2)
Remediation domain. Functions:
- remediation constants (the module-level config near line 641)
- `_validate_and_clean_lesson`
- `_check_remediation_cap` (takes `db`)
- `_difficulty_directive`
- `_build_remediation_prompt`
- `_gen_variant_for_student` (the per-student worker; runs under ThreadPoolExecutor — see Landmine R3)

If `student_remediation` needs any mastery helper (e.g. `_sanitize_standards_mastery`), it imports it from `student_mastery` (Slice 1 lands first; no cycle because both are leaf services).

### `backend/services/student_progress_reports.py` (Slice 3)
Assembly logic for `get_class_progress_rank` and `get_student_report_card`. The **service** takes `db`, `teacher_id`, `class_id`, `student_id`, `attempt_mode` and returns the response payload dict; the **route** keeps auth, request parsing, the `_progress_rank_cache` lookup/set (Landmine R4), and `jsonify`.

### Slice 4 — gradebook / detail / comparison assembly
Extract the assembly bodies of `get_class_gradebook`, `get_student_submission_detail`, `get_class_assessment_comparison` into a service (`backend/services/student_gradebook.py`), same route-keeps-IO shape as Slice 3.

### Slice 5 — `post_remediate` split (highest risk, last)
`post_remediate` (~523 LOC) is the largest single body. Extract resolver/generator helpers behind the *identical* route contract only after Slices 1–4 are stable. Preserve the LLM post-processing order exactly (Landmine R5) and the `_get_openai_context` import shape (Landmine R6).

## 4. Risks / Landmines (verified first-hand; carry into every slice)

- **R1 — Re-export shim is mandatory.** Many tests both *import* and `patch(...)` route-module names (`_get_teacher_supabase`, `get_supabase`, and the helpers themselves). After moving a function, the route module must still expose the name via re-import, or those patches silently target the wrong binding. Verify with a grep for `patch('backend.routes.student_portal_routes.<name>')` before each move.
- **R2 — Mixed-auth Supabase.** Anonymous join-code routes use `get_supabase()` (service-role); teacher routes use `_get_teacher_supabase()` (user-scoped, RLS). Services **must receive the `db` handle as a parameter** and never call `get_request_supabase`/`get_supabase` themselves — otherwise RLS scoping silently changes.
- **R3 — ThreadPoolExecutor context.** `_gen_variant_for_student` runs inside a thread pool and cannot reach Flask globals. It must receive a fully-hydrated context (api_key, ids, segment, students_by_id) as arguments — preserve its current keyword-only signature exactly.
- **R4 — Route-level cache.** `_progress_rank_cache = TTLCache(ttl_seconds=30)` (line 38) is process-local route state. Keep the cache lookup/set in the route handler; the extracted service computes, the route caches.
- **R5 — Remediation post-processing order.** In `post_remediate`, `raw_lesson` is captured *before* `_post_process_assignment` and validated *after* (around lines 3239 / 3269). Do not reorder or "clean up" this sequence.
- **R6 — No service→route imports (cycle).** `post_remediate` imports `backend.routes.planner_routes._get_openai_context` (lines 3079, 3202). Services must not import route modules. If Slice 5 moves generation logic, pass the OpenAI context in from the route, or extract a neutral context helper into a service — never `import backend.routes.*` from a service.
- **R7 — In-place mutation.** `_sanitize_standards_mastery(sub)` mutates `sub['results']` in place and returns `None`. Preserve mutation semantics and the `None` return exactly; callers rely on the side effect.
- **R8 — Submit seam off-limits.** `submit_assessment` (line ~1413) routes through `published_content_repository_for` / `repository_for` (the recently-consolidated `submission_repository` abstraction, lines ~1423–1461). Do not touch it in this wave.

## 5. Scope / non-goals

- **In scope:** Slices 1–5 above on `student_portal_routes.py`. Each is a separate PR, branched off fresh `main`, merged before the next (line numbers shift between slices → re-audit boundaries each time).
- **Out of scope (separate specs):** `planner_routes.py` de-concentration; `assignment_grader.py` (off-limits); any schema/behavior change; any dependency-injection work (that's an Architecture-tier lever, tracked separately); the submit seam.

## 6. Success criteria

- `student_portal_routes.py` materially smaller (target: route bodies become thin adapters; the ~800 LOC pure-helper block + the report/gradebook/remediation assembly relocated to named services).
- Every existing test green throughout (byte-identical behavior), plus new per-service unit tests.
- All 9 CI checks green on every PR.
- A post-wave 3-model reconciled re-score judges whether Code Quality moves 8 → 9 (honest expectation: a single file may not clinch 9 — the assessment says it needs *broad* de-concentration — but it is the necessary first file and a real boundary improvement).

---

*Execution: subagent-driven with two-stage review per PR; controller-run assertion-guarded edits where the moved block is large. Slice 1 (the mastery cluster) is fully detailed in the implementation plan; Slice 2 detailed; Slices 3–5 scope-sketched and planned in full when their turn comes (each re-audits boundaries off freshly-merged main). Spec + plan go up as one docs PR, then impl PRs follow.*
