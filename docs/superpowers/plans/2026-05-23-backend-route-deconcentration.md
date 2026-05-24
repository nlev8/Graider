# Backend Route De-concentration Implementation Plan (Wave 5)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** De-concentrate `backend/routes/student_portal_routes.py` (3,686 LOC) into Flask-free `backend/services/` modules, behavior-preservingly, to move Code Quality 8 → 9.

**Architecture:** Each slice moves a cohesive function cluster *verbatim* into a new `backend/services/` module, then **re-imports the moved names back into the route module** ("re-export shim"). Existing call sites and the existing pytest suite (which import the helpers from the route module) stay green unchanged — they are the byte-identical characterization net. New per-service unit tests pin the moved behavior directly against the service module.

**Tech Stack:** Python / Flask, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-23-backend-route-deconcentration-design.md` (read its §4 Landmines before every slice).

---

## File Structure

| File | Slice | Responsibility |
|------|-------|----------------|
| `backend/services/student_mastery.py` | 1 (this PR, full detail) | Pure mastery/trajectory computation: `_parse_ts`, `_coalesce`, `_select_submissions_by_mode`, `_aggregate_mastery_for_student`, `_build_standards_breakdown_for_student`, `_build_trajectory_for_student`, `_normalize_mastery_shape`, `_flatten_mastery_for_response`, `_sanitize_standards_mastery` |
| `tests/test_student_mastery_service.py` | 1 | New direct-import unit tests against the service module |
| `backend/routes/student_portal_routes.py` | 1 | Loses the 9 moved defs; gains a re-import line that re-exports them |
| `backend/services/student_remediation.py` | 2 (full detail) | Remediation domain: constants + `_validate_and_clean_lesson`, `_check_remediation_cap`, `_difficulty_directive`, `_build_remediation_prompt`, `_gen_variant_for_student` |
| `backend/services/student_progress_reports.py` | 3 (scope-sketch) | `get_class_progress_rank` + `get_student_report_card` assembly |
| `backend/services/student_gradebook.py` | 4 (scope-sketch) | gradebook / submission-detail / comparison assembly |
| (in-place) `post_remediate` resolver/generator helpers | 5 (scope-sketch) | extract behind identical route contract |

**Convention for every slice:** branch off freshly-merged `main` (`git checkout -b refactor/student-portal-slice-N origin/main`), because each merge shifts line numbers — re-audit boundaries with a fresh grep before moving.

---

## Task 1 (Slice 1): Extract the mastery cluster into `backend/services/student_mastery.py`

**Files:**
- Create: `backend/services/student_mastery.py`
- Create: `tests/test_student_mastery_service.py`
- Modify: `backend/routes/student_portal_routes.py` (remove 9 defs at lines 92–115, 145–353, 356–555, 558–597; add one re-import line where they were)

**The 9 functions to move** (verbatim — byte-identical bodies, no edits):
`_parse_ts` (92–101), `_coalesce` (104–115), `_select_submissions_by_mode` (145–176), `_aggregate_mastery_for_student` (179–353), `_build_standards_breakdown_for_student` (356–431), `_build_trajectory_for_student` (434–472), `_normalize_mastery_shape` (475–504), `_flatten_mastery_for_response` (507–555), `_sanitize_standards_mastery` (558–597).

> **Do NOT move** `_spawn_thread_grading` (53–74), `generate_join_code` (77–89), or `_find_content_row` (118–142) — they are not mastery helpers (`generate_join_code` and `_find_content_row` do DB I/O and belong to later slices/route).

**External dependencies the new module needs** (derived from the bodies):
- `from datetime import datetime` (used by `_parse_ts`, `_build_trajectory_for_student`)
- `from backend.services.dok import _validate_dok` (used by `_normalize_mastery_shape`)
- `import logging` + `_logger = logging.getLogger(__name__)` (used by `_sanitize_standards_mastery`)
- `from collections import defaultdict` is imported *inside* `_aggregate_mastery_for_student` — keep that in-function import verbatim (do not hoist it; byte-identical rule).

> **Landmine R7 (verified):** `_sanitize_standards_mastery` mutates `sub['results']` in place and returns `None`. `_flatten_mastery_for_response` returns a NEW dict (does not mutate). Preserve both exactly.
> **Logger note (verified):** `tests/test_sanitize_mastery_shape.py` does not use `caplog` or assert the logger name, so the new module owning its own `_logger` is safe.

- [ ] **Step 1: Re-audit boundaries on fresh main**

```bash
git checkout -b refactor/student-portal-mastery origin/main
grep -nE "^def (_parse_ts|_coalesce|_select_submissions_by_mode|_aggregate_mastery_for_student|_build_standards_breakdown_for_student|_build_trajectory_for_student|_normalize_mastery_shape|_flatten_mastery_for_response|_sanitize_standards_mastery)\b" backend/routes/student_portal_routes.py
```
Expected: 9 lines printed. Note the current line numbers (they may have shifted from this plan's numbers).

- [ ] **Step 2: Write the failing service unit test**

Create `tests/test_student_mastery_service.py`. The new tests import from the *service* module (the new home), proving the module exists and the functions work there:

```python
"""Direct-import characterization tests for backend/services/student_mastery.py
(Wave 5 Slice 1 — behavior-preserving extraction from student_portal_routes)."""
from datetime import datetime


def test_parse_ts_handles_z_suffix_and_garbage():
    from backend.services.student_mastery import _parse_ts
    assert _parse_ts("2026-01-02T03:04:05Z") == datetime.fromisoformat("2026-01-02T03:04:05+00:00")
    assert _parse_ts("") == datetime.min
    assert _parse_ts(None) == datetime.min
    assert _parse_ts("not-a-date") == datetime.min


def test_coalesce_keeps_falsy_but_not_none():
    from backend.services.student_mastery import _coalesce
    assert _coalesce(None, 0, 5) == 0          # 0 is a legitimate value, not skipped
    assert _coalesce(None, None, default="x") == "x"
    assert _coalesce(None, "", "y") == ""       # "" is legitimate


def test_normalize_mastery_shape_wraps_flat_and_passes_new():
    from backend.services.student_mastery import _normalize_mastery_shape
    flat = {"points_earned": 4, "points_possible": 5, "question_count": 2, "percentage": 80}
    out = _normalize_mastery_shape(flat)
    assert out == {"overall": flat, "by_dok": {}}
    assert _normalize_mastery_shape("garbage") is None


def test_sanitize_standards_mastery_mutates_in_place_returns_none():
    from backend.services.student_mastery import _sanitize_standards_mastery
    sub = {"id": "s1", "results": {"standards_mastery": "not-a-dict"}}
    ret = _sanitize_standards_mastery(sub)
    assert ret is None                                  # returns None
    assert sub["results"]["standards_mastery"] == {}    # mutated in place


def test_flatten_mastery_for_response_returns_new_dict():
    from backend.services.student_mastery import _flatten_mastery_for_response
    results = {"standards_mastery": {"A": {"overall": {"points_earned": 3, "points_possible": 6, "question_count": 1}}}}
    out = _flatten_mastery_for_response(results)
    assert out is not results                            # new dict, no mutation
    assert out["standards_mastery"]["A"]["percentage"] == 50.0


def test_aggregate_mastery_latest_sums_overall():
    from backend.services.student_mastery import _aggregate_mastery_for_student
    subs = {"c1": [{"id": "s1", "attempt_number": 1,
                    "results": {"standards_mastery": {"A": {"points_earned": 8, "points_possible": 10, "question_count": 2}}}}]}
    out = _aggregate_mastery_for_student(subs, {"c1": "Quiz"}, "latest")
    assert out["A"]["percentage"] == 80.0
    assert out["A"]["points_possible"] == 10
```

- [ ] **Step 3: Run the new test to verify it fails**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && pytest tests/test_student_mastery_service.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.services.student_mastery'`.

- [ ] **Step 4: Create the service module by moving the 9 functions verbatim**

Create `backend/services/student_mastery.py` with this header, then paste the 9 function bodies **exactly** as they appear in the route file (same comments, same in-function `from collections import defaultdict`):

```python
"""Pure mastery/trajectory computation for the student portal.

Wave 5 Slice 1 — extracted verbatim from backend/routes/student_portal_routes.py
(behavior-preserving). Flask-free: no request/g/session access; callers pass any
DB handle in explicitly. Re-exported from student_portal_routes.py so existing
imports and `patch('backend.routes.student_portal_routes.<name>')` keep working.
"""
import logging
from datetime import datetime

from backend.services.dok import _validate_dok

_logger = logging.getLogger(__name__)


# <paste _parse_ts, _coalesce, _select_submissions_by_mode,
#  _aggregate_mastery_for_student, _build_standards_breakdown_for_student,
#  _build_trajectory_for_student, _normalize_mastery_shape,
#  _flatten_mastery_for_response, _sanitize_standards_mastery — VERBATIM>
```

- [ ] **Step 5: Run the new service test to verify it passes**

Run: `pytest tests/test_student_mastery_service.py -q`
Expected: PASS (6 tests).

- [ ] **Step 6: Remove the 9 defs from the route module and add the re-export shim**

In `backend/routes/student_portal_routes.py`, delete the 9 function definitions (keep `_spawn_thread_grading`, `generate_join_code`, `_find_content_row`). Where the first moved def was (right after the `_get_teacher_supabase` import block, near line 50), add:

```python
# Wave 5 Slice 1: mastery/trajectory helpers extracted to
# backend/services/student_mastery.py. Re-imported here so existing route
# bodies, external callers, and tests that import or patch these names on
# this module keep working unchanged.
from backend.services.student_mastery import (  # noqa: F401  (re-export shim)
    _parse_ts,
    _coalesce,
    _select_submissions_by_mode,
    _aggregate_mastery_for_student,
    _build_standards_breakdown_for_student,
    _build_trajectory_for_student,
    _normalize_mastery_shape,
    _flatten_mastery_for_response,
    _sanitize_standards_mastery,
)
```

- [ ] **Step 7: Free-variable / leftover-reference scan**

```bash
# No orphaned defs left behind, no duplicate defs:
grep -nE "^def (_parse_ts|_coalesce|_select_submissions_by_mode|_aggregate_mastery_for_student|_build_standards_breakdown_for_student|_build_trajectory_for_student|_normalize_mastery_shape|_flatten_mastery_for_response|_sanitize_standards_mastery)\b" backend/routes/student_portal_routes.py
# The module still imports cleanly:
python -c "import backend.routes.student_portal_routes as m; [getattr(m, n) for n in ('_parse_ts','_coalesce','_select_submissions_by_mode','_aggregate_mastery_for_student','_build_standards_breakdown_for_student','_build_trajectory_for_student','_normalize_mastery_shape','_flatten_mastery_for_response','_sanitize_standards_mastery')]; print('all 9 re-exported OK')"
```
Expected: first grep prints nothing (defs gone from route module); python prints `all 9 re-exported OK`.

- [ ] **Step 8: Run the full existing characterization net (must stay green)**

Run: `pytest tests/test_aggregation_helpers.py tests/test_mastery_shape.py tests/test_sanitize_mastery_shape.py tests/test_student_report_card.py tests/test_gradebook.py tests/test_student_mastery_service.py -q`
Expected: PASS (all). These import the helpers from the route module (re-export shim) and from the new service module.

- [ ] **Step 9: Run the broader portal suite + lint/type gates**

Run:
```bash
pytest tests/ -q -k "portal or mastery or gradebook or report_card or remediation or aggregation"
ruff check backend/services/student_mastery.py backend/routes/student_portal_routes.py
mypy backend/services/student_mastery.py  # if it is in the mypy-strict critical set; otherwise skip
```
Expected: tests PASS; ruff clean.

- [ ] **Step 10: Commit**

```bash
git add backend/services/student_mastery.py tests/test_student_mastery_service.py backend/routes/student_portal_routes.py
git commit -m "refactor(portal): extract mastery cluster into student_mastery service (Wave 5 slice 1)

Behavior-preserving move of 9 pure mastery/trajectory helpers out of
student_portal_routes.py into backend/services/student_mastery.py, re-exported
from the route module so existing imports/patches stay green. New direct-import
unit tests pin the service. No behavior change.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

- [ ] **Step 11: Push, open PR, enable auto-merge**

```bash
git push -u origin refactor/student-portal-mastery
gh pr create --title "refactor(portal): extract mastery cluster → student_mastery service (Wave 5 slice 1)" --body "Behavior-preserving extraction; re-export shim keeps existing imports/patches green; new service unit tests added. Part of backend de-concentration (Code Quality 8→9). Spec: docs/superpowers/specs/2026-05-23-backend-route-deconcentration-design.md"
gh pr merge --squash --auto --delete-branch
```

---

## Task 2 (Slice 2): Extract the remediation cluster into `backend/services/student_remediation.py`

**Files:**
- Create: `backend/services/student_remediation.py`
- Create: `tests/test_student_remediation_service.py`
- Modify: `backend/routes/student_portal_routes.py` (remove the remediation defs + constants; add re-import shim)

**Functions + constants to move** (verbatim): the remediation constants block (`REMEDIATION_PER_STUDENT_WEEKLY_CAP`, `REMEDIATION_PERSONALIZED_MAX`, `REMEDIATION_COUNT_MIN/MAX/DEFAULT`, `DIFFICULTY_OPTIONS`, `REMEDIATION_DIFFICULTY_DEFAULT`), `_validate_and_clean_lesson`, `_check_remediation_cap`, `_difficulty_directive`, `_build_remediation_prompt`, `_gen_variant_for_student`.

**External dependencies (re-audit before moving — these are from the spec; confirm with grep):**
- `_logger` (module logger) — used by `_validate_and_clean_lesson`.
- DOK helpers from `backend.services.dok` (`DOK_OPTIONS`, `DOK_DESCRIPTIONS`, `REMEDIATION_DOK_DEFAULT`, `_validate_dok`, `_derive_uniform_dok`) — `_build_remediation_prompt` / `_gen_variant_for_student` likely use these; import them into the new module from `backend.services.dok` (NOT from the route module).
- `_check_remediation_cap(db, ...)` takes `db` as a parameter (Landmine R2 — keep it a param; never acquire a client inside the service).
- `_gen_variant_for_student` runs under `ThreadPoolExecutor` (Landmine R3) — preserve its keyword-only signature `(*, sid, segment, students_by_id, api_key, ...)` exactly; it must receive a fully-hydrated context.

> **Landmine R6 (cycle):** if any moved function references `_get_openai_context`, do NOT import `backend.routes.planner_routes` from the service. Pass the OpenAI context (uid, client) in as parameters from the route. Re-audit with: `grep -n "_get_openai_context" backend/routes/student_portal_routes.py` and confirm none of the *moved* functions call it (it's called inside `post_remediate`, which stays in the route until Slice 5).

- [ ] **Step 1: Re-audit boundaries on fresh main**

```bash
git checkout -b refactor/student-portal-remediation origin/main
grep -nE "^def (_validate_and_clean_lesson|_check_remediation_cap|_difficulty_directive|_build_remediation_prompt|_gen_variant_for_student)\b|^REMEDIATION_|^DIFFICULTY_OPTIONS" backend/routes/student_portal_routes.py
# Confirm none of these 5 functions reference _get_openai_context (cycle guard):
awk '/^def (_validate_and_clean_lesson|_check_remediation_cap|_difficulty_directive|_build_remediation_prompt|_gen_variant_for_student)\b/,/^def [a-zA-Z]/' backend/routes/student_portal_routes.py | grep -n "_get_openai_context" || echo "CLEAN: no cycle in moved fns"
```
Expected: the defs/constants print; the cycle check prints `CLEAN: no cycle in moved fns`.

- [ ] **Step 2: Write the failing service unit test**

Create `tests/test_student_remediation_service.py`:

```python
"""Direct-import tests for backend/services/student_remediation.py (Wave 5 Slice 2)."""


def test_validate_and_clean_lesson_keeps_only_three_fields():
    from backend.services.student_remediation import _validate_and_clean_lesson
    raw = {"intro": " hi ", "worked_example": "x", "key_takeaway": "y", "evil": "drop me"}
    out = _validate_and_clean_lesson(raw)
    assert out == {"intro": "hi", "worked_example": "x", "key_takeaway": "y"}


def test_validate_and_clean_lesson_rejects_nondict_and_missing():
    from backend.services.student_remediation import _validate_and_clean_lesson
    assert _validate_and_clean_lesson("nope") is None
    assert _validate_and_clean_lesson({"intro": "a", "worked_example": "b"}) is None  # missing key_takeaway


def test_difficulty_directive_returns_string_for_each_option():
    from backend.services.student_remediation import _difficulty_directive
    for opt in ("easier", "same", "harder"):
        assert isinstance(_difficulty_directive(opt, "7"), str)


def test_constants_are_re_exported_from_route_module():
    # Re-export shim keeps these reachable on the old module path.
    from backend.routes.student_portal_routes import REMEDIATION_PER_STUDENT_WEEKLY_CAP, REMEDIATION_COUNT_DEFAULT
    from backend.services.student_remediation import REMEDIATION_PER_STUDENT_WEEKLY_CAP as svc_cap
    assert REMEDIATION_PER_STUDENT_WEEKLY_CAP == svc_cap
```

- [ ] **Step 3: Run to verify failure**

Run: `pytest tests/test_student_remediation_service.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.services.student_remediation'`.

- [ ] **Step 4: Create the service module (move constants + 5 functions verbatim)**

Create `backend/services/student_remediation.py` with a docstring header mirroring `student_mastery.py`'s, the needed imports (`logging`, the `backend.services.dok` symbols actually used, and `from backend.services.student_mastery import _sanitize_standards_mastery` / `_aggregate_mastery_for_student` IF a moved function uses them — re-audit), `_logger = logging.getLogger(__name__)`, then the constants and the 5 functions **verbatim**.

- [ ] **Step 5: Run the new test to verify it passes**

Run: `pytest tests/test_student_remediation_service.py -q`
Expected: PASS.

- [ ] **Step 6: Remove from route module + add re-export shim**

Delete the moved constants and 5 defs from `student_portal_routes.py`. Add:

```python
# Wave 5 Slice 2: remediation helpers + constants extracted to
# backend/services/student_remediation.py. Re-imported for back-compat.
from backend.services.student_remediation import (  # noqa: F401  (re-export shim)
    REMEDIATION_PER_STUDENT_WEEKLY_CAP,
    REMEDIATION_PERSONALIZED_MAX,
    REMEDIATION_COUNT_MIN,
    REMEDIATION_COUNT_MAX,
    REMEDIATION_COUNT_DEFAULT,
    DIFFICULTY_OPTIONS,
    REMEDIATION_DIFFICULTY_DEFAULT,
    _validate_and_clean_lesson,
    _check_remediation_cap,
    _difficulty_directive,
    _build_remediation_prompt,
    _gen_variant_for_student,
)
```

- [ ] **Step 7: Leftover-reference + import scan**

```bash
grep -nE "^def (_validate_and_clean_lesson|_check_remediation_cap|_difficulty_directive|_build_remediation_prompt|_gen_variant_for_student)\b" backend/routes/student_portal_routes.py
python -c "import backend.routes.student_portal_routes as m; [getattr(m,n) for n in ('_validate_and_clean_lesson','_check_remediation_cap','_difficulty_directive','_build_remediation_prompt','_gen_variant_for_student','REMEDIATION_COUNT_DEFAULT')]; print('remediation re-exports OK')"
```
Expected: grep prints nothing; python prints `remediation re-exports OK`.

- [ ] **Step 8: Run remediation characterization net + lint**

Run:
```bash
pytest tests/test_remediation.py tests/test_remediation_cap.py tests/test_remediation_perstudent.py tests/test_student_remediation_service.py -q
ruff check backend/services/student_remediation.py backend/routes/student_portal_routes.py
```
Expected: PASS; ruff clean.

- [ ] **Step 9: Commit, push, PR, auto-merge**

```bash
git add backend/services/student_remediation.py tests/test_student_remediation_service.py backend/routes/student_portal_routes.py
git commit -m "refactor(portal): extract remediation cluster into student_remediation service (Wave 5 slice 2)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push -u origin refactor/student-portal-remediation
gh pr create --title "refactor(portal): extract remediation cluster → student_remediation service (Wave 5 slice 2)" --body "Behavior-preserving; re-export shim; new service unit tests. Spec: docs/superpowers/specs/2026-05-23-backend-route-deconcentration-design.md"
gh pr merge --squash --auto --delete-branch
```

---

## Task 3 (Slice 3, scope-sketch): `student_progress_reports.py`

**Detailed in full when its turn comes** (re-audit off freshly-merged main first). Sketch:
- Extract the assembly bodies of `get_class_progress_rank` and `get_student_report_card` into `backend/services/student_progress_reports.py`. The service takes `db, teacher_id, class_id, student_id, attempt_mode` and returns the response payload dict.
- The **route keeps**: `@require_teacher`, request parsing, the `_progress_rank_cache` lookup/set (Landmine R4 — cache stays in route), and `jsonify`.
- Gate: existing `tests/test_student_report_card.py` + a new `tests/test_student_progress_reports_service.py` + full suite + 9 CI checks.
- This is route-body extraction (not pure-helper), so add a route-contract characterization test (call the endpoint with a fixture `db`, assert response JSON identical pre/post) before moving.

## Task 4 (Slice 4, scope-sketch): `student_gradebook.py`

**Detailed in full when its turn comes.** Sketch:
- Extract assembly bodies of `get_class_gradebook`, `get_student_submission_detail`, `get_class_assessment_comparison` into `backend/services/student_gradebook.py` (they share attempt-selection + grade/progress presentation concepts).
- Same route-keeps-IO shape as Slice 3. Gate: `tests/test_gradebook.py` + new service tests + route-contract char tests.

## Task 5 (Slice 5, scope-sketch): split `post_remediate`

**Highest risk — detailed in full last, after Slices 1–4 are stable.** Sketch:
- `post_remediate` (~523 LOC) → extract resolver/generator helpers behind the *identical* route contract.
- Landmine R5: capture `raw_lesson` before `_post_process_assignment`, validate after — do not reorder.
- Landmine R6: pass the OpenAI context (from `_get_openai_context`) IN from the route; never import `backend.routes.planner_routes` from a service.
- Landmine R3: `_gen_variant_for_student` (already a service after Slice 2) is invoked here via ThreadPoolExecutor — keep the thread-pool orchestration in the route or a dedicated orchestrator that receives fully-hydrated context.
- Gate: a route-contract characterization test pinning `/api/teacher/class/<id>/remediate` request→response (with LLM + `_post_process_assignment` mocked) byte-identical pre/post, plus the existing remediation tests.

---

## Post-wave step: 3-model re-score

After Slices 1–5 land, run a 3-model reconciled re-score (Claude controller first-hand + Codex `codex exec` + Gemini `gemini -p`, conservative-floor) weighing whether Code Quality moves 8 → 9, appended as a dated section to `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`. Honest expectation: one file may hold at 8 (the assessment says 9 needs *broad* de-concentration across `planner_routes.py` too) — this is the necessary first file, and `planner_routes.py` gets its own spec next.
