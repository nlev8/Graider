# Dual Publish-Path Consolidation Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the second half of Architecture ground 1 by abstracting the published-content reads + route-layer dedup behind a parallel `PublishedContentRepository` and a `SubmissionRepository.find_existing_submission` extension, rewiring both HTTP entry routes onto them, and retiring the three #431 transitional residuals from Slice 4.

**Architecture:** Mirror the proven PR1/PR2 split that worked for Slice 4. PR1 is purely additive (new module, ABC extension, route-layer char-net extension, char-net assertion migration with helpers still in place) so behavior change is impossible by construction. PR2 rewires the two route bodies onto the new repos and folds in #431 (delete dead helpers, switch on_failure to repo.mark_failed, rename `supabase_table` to `path_type`). A pre-pinned characterization net stays byte-identical across the rewire.

**Tech Stack:** Python 3.14, Flask, Supabase client, Celery + threading, pytest with `unittest.mock`. venv `/Users/alexc/Downloads/Graider/venv/` (`source venv/bin/activate`). Two sequenced PRs plus a post-slice 3-model reconciled re-score.

**Spec:** `docs/superpowers/specs/2026-05-19-dual-path-completion-design.md`. The 2-PR split and the byte-identical-net contract are mandatory.

**Refactor-plan note:** for relocated existing code (test fixtures migrating from module-symbol patching to repo-method patching; route-body lines moving onto repo calls) the plan identifies the code by exact file:line and instructs an in-place rewire rather than re-pasting. All genuinely new code (the `PublishedContentRepository` module, the `ExistingSubmission` dataclass, the `find_existing_submission` method bodies, the route-layer char-net cases) is given in full. Line numbers are current as of main HEAD `d07293b` and shift as edits land; each task re-derives them by content. The grep gate plus the char-net byte-equivalence are the authoritative checks.

**Environment note:** do NOT run `tests/load`; always `--ignore=tests/load`; do not contact `:3000`. `source venv/bin/activate` for every Python command.

**Railway-recovery gate:** as of plan-writing, production is in a Railway/GCP outage. Code PRs (both PR1 and PR2 below) land only after Railway recovers and the queue is no longer throttled. Local development and the spec/plan itself are unaffected.

---

## File Structure

- **Create:** `backend/services/published_content_repository.py`. The `PublishedContentRepository` ABC, two adapters (`JoinCodePublishedRepository`, `ClassPublishedRepository`), and the parallel `published_content_repository_for(path_type, sb)` factory. Single responsibility: published-content row I/O for the two-table read split. Reuses the existing `SubmissionPathType` enum from `submission_repository`. Never imports `backend.app`, never imports route modules.
- **Modify:** `backend/services/submission_repository.py`. Add the `ExistingSubmission` dataclass and the `find_existing_submission(lookup_key, student_info)` method on the ABC, with per-adapter implementations on `JoinCodeSubmissionRepository` (fuzzy `ilike` on `submissions`) and `ClassSubmissionRepository` (exact match on `student_submissions`).
- **Modify (PR2):** `backend/routes/student_portal_routes.py`. The `submit_assessment` body (def 1413, deco 1409) at lines around 1454 (the existing dedup query) and at the published-content fetch site rewires to use the parallel repos via the shape in spec section 4.
- **Modify (PR2):** `backend/routes/student_account_routes.py`. The `submit_student_work` body (def 1107, deco 1104) at lines around 1137 (the existing dedup query) and at the published-content fetch site rewires the same way.
- **Modify (PR2):** `backend/services/portal_grading.py`. Delete the orphaned `_fetch_submission_row` (def 339) and `_claim_submission_for_grading` (def 374). Rename `supabase_table` -> `path_type` on `grade_portal_submission_sync` (def 546) and `run_portal_grading_thread` (def 1002).
- **Modify (PR2):** `backend/tasks/grading_tasks.py`. The `on_failure` body (lines 40-70) switches from `_safe_update_submission(sb, ...)` to `repository_for(supabase_table, sb).mark_failed(submission_id, exc)`.
- **Create:** `tests/test_published_content_repository.py`. Per-adapter unit tests using the same `FakeSupabase` pattern already in `tests/test_submission_repository.py`.
- **Modify:** `tests/test_submission_repository.py`. Per-adapter unit tests for `find_existing_submission` and the `ExistingSubmission` dataclass.
- **Modify:** `tests/test_dual_path_consolidation_char.py`. Add a new test class `TestRouteContractSeam` pinning both routes' full request-to-response observable contract pre-rewire; the existing `TestClaimSeam` (line 43), `TestUpdateSeam` (line 234), and `TestFailureSeam` (line 302) migrate from patching `_safe_update_submission`/`_fetch_submission_row`/`_claim_submission_for_grading` to patching the `SubmissionRepository` methods.
- **Modify:** `tests/test_grading_tasks.py`. The three `patch('backend.services.portal_grading._safe_update_submission')` sites (lines 82, 105, 312) migrate to `patch('backend.services.submission_repository.SubmissionRepository.update')` (or `.mark_failed`).
- **Modify:** `tests/test_grade_portal_submission_sync.py`. Tests that reference `_fetch_submission_row` and `_claim_submission_for_grading` directly migrate to reference the repo methods.
- **Modify (PR2 closeout):** `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`, this plan.

---

## Shared context for both PRs

**The current seam signatures (main HEAD `d07293b`).** Re-derive line numbers before editing.

```
backend/services/portal_grading.py
  314 def _safe_update_submission(sb, submission_id, update_fields, table_name="student_submissions")
  339 def _fetch_submission_row(sb, supabase_table, submission_id)
  374 def _claim_submission_for_grading(sb, table_name, submission_id, task_id)
  546 def grade_portal_submission_sync(... supabase_table=SubmissionPathType.CLASS.value ...)
 1002 def run_portal_grading_thread(... supabase_table=SubmissionPathType.CLASS.value ...)

backend/routes/student_portal_routes.py
 1409 @student_portal_bp.route('/api/student/submit/<code>', methods=['POST'])
 1413 def submit_assessment(code):
 1454   existing = db.table('submissions').select('id, results').eq('join_code', code).ilike('student_name', student_name).execute()
 1555   grade_portal_submission.delay(...)
 1572   _spawn_thread_grading(...)

backend/routes/student_account_routes.py
 1104 @student_account_bp.route('/api/student/class-submit/<content_id>', methods=['POST'])
 1107 def submit_student_work(content_id):
 1137   existing = db.table('student_submissions').select('id').eq(...)

backend/services/submission_repository.py
  (PR1/PR2 of Slice 4) SubmissionPathType enum + SubmissionRepository ABC + JoinCode/Class adapters + repository_for factory + fetch / claim_for_grading / update / mark_failed / normalize_context

backend/tasks/grading_tasks.py
   40 def on_failure(self, exc, task_id, args, kwargs, einfo)
   42   supabase_table = args[2] if len(args) > 2 else kwargs.get('supabase_table', 'submissions')
   ~63 _safe_update_submission(sb, submission_id, {'status':'failed','error_message':str(exc)[:500]}, table_name=supabase_table)
```

**The fake supabase client** is already in `tests/test_submission_repository.py` (lines 1-50: `_Resp`, `_Query`, `FakeTable`, `FakeSupabase`). Reuse it in `tests/test_published_content_repository.py` by importing from the test module, or copy-paste the four small classes (they are unchanged from PR1 of Slice 4).

**The `ExistingSubmission` dataclass** (NEW, used as the return type of `find_existing_submission`):

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class ExistingSubmission:
    """Return type of SubmissionRepository.find_existing_submission.

    Each adapter populates the fields its query selects. Caller handles
    None (no existing submission) vs hit, and uses whatever fields are
    available. JoinCode populates id + results + student_name (the
    'submissions' table's id, results, student_name columns). Class
    populates id + student_name (the 'student_submissions' table's id,
    student_name columns; results is fetched separately by callers that
    need it because the class-based path's existing dedup pre-check does
    not select results).
    """
    id: str
    results: Optional[dict] = None
    student_name: Optional[str] = None
```

**No-cycle gate.** `backend/services/published_content_repository.py` must NOT import `backend.app` or any route module. It may import from `backend.services.submission_repository` (for the `SubmissionPathType` enum) and stdlib. Verified post-edit with `grep -nE "^(from|import) backend\.(app|routes)" backend/services/published_content_repository.py` -> EMPTY.

**Methodology.** Same discipline as Slice 4: characterization-net-first. PR1 extends `tests/test_dual_path_consolidation_char.py` with the route-layer cases (`TestRouteContractSeam`) committed green against the current code. PR2 rewires the routes and the net stays byte-identical (every pinned status + JSON unchanged). Per-adapter unit tests cover the new isolated units.

---

## PR 1: additive (new module + ABC extension + char-net extension + test migration)

### Task 1.1: Branch + route-layer char-net extension pinned pre-rewire

**Files:** Modify `tests/test_dual_path_consolidation_char.py`

- [ ] **Step 1: Branch.**
```bash
git checkout main && git pull origin main && git checkout -b feature/dual-path-completion-pr1
```
- [ ] **Step 2: Survey the route bodies.** Read `backend/routes/student_portal_routes.py:1409-1605` (the full `submit_assessment` body including its published-content lookup, dedup, upsert, and spawn paths). Read `backend/routes/student_account_routes.py:1104-1300` (the full `submit_student_work` body). Identify the exact lines where (a) the published-content row is fetched, (b) the dedup query runs, (c) the existing-results response is built (join-code path only), (d) the new-submission upsert happens, (e) the grading is dispatched (Celery `.delay` or thread). These are the points the PR2 rewire will touch.
- [ ] **Step 3: Add `TestRouteContractSeam` class** to `tests/test_dual_path_consolidation_char.py` (after `TestFailureSeam` ends, before `test_no_supabase_table_string_dispatch_remains`):

```python
class TestRouteContractSeam:
    """Pins both HTTP entry routes' full request-to-response observable contract.

    PRE-rewire commit: assertions pin the EXACT status code + JSON body
    each route returns today for happy path / dedup hit / 404 / 400. PR2
    must keep these assertions byte-identical post-rewire. That equivalence
    is the zero-behavior-change proof for the route layer.

    Both paths exercised independently via the existing client/flask_app
    fixtures in tests/conftest_routes.py (join-code: anonymous client;
    class-based: authed client with X-Student-Token).
    """

    # Probe-then-pin discipline: write one test per branch, probe the
    # real route's response first (run the test against current code, see
    # what it returns), pin EXACTLY what is observed. Do not invent values.

    def test_joincode_happy_path_creates_submission(self, client):
        # POST /api/student/submit/<code> with valid join_code + answers
        # for a brand-new (name, code) pair. Pin the exact status + JSON.
        ...

    def test_joincode_dedup_returns_existing_results(self, client):
        # POST same (code, student_name) twice in a row. Second call hits
        # the ilike-name-match branch (line 1454 today). Pin the exact
        # existing-results JSON shape.
        ...

    def test_joincode_missing_content_404(self, client):
        # POST to a nonexistent join_code. Pin the exact 404 + JSON.
        ...

    def test_joincode_invalid_input_400(self, client):
        # POST with missing required field. Pin the exact 400 + JSON.
        ...

    def test_class_happy_path_creates_submission(self, authed_client):
        # POST /api/student/class-submit/<content_id> with valid token +
        # answers for a brand-new (student, content) pair. Pin status + JSON.
        ...

    def test_class_dedup_returns_existing_id(self, authed_client):
        # POST same (student, content) twice. Second call hits the
        # exact-match dedup branch (line 1137 today). Pin status + JSON.
        ...

    def test_class_missing_content_404(self, authed_client):
        # POST to a nonexistent content_id. Pin status + JSON.
        ...

    def test_class_invalid_input_400(self, authed_client):
        # POST with missing required field. Pin status + JSON.
        ...
```

For each `...` body: write the test, run it against the current code, observe the exact return, pin it. The `student_info` shape for the join-code path is `{'name': ..., 'email': ...}`; for the class path it derives from the X-Student-Token. The `client` and `authed_client` fixtures already exist in `tests/conftest_routes.py` and `tests/conftest.py`.

- [ ] **Step 4: Pin green.** `source venv/bin/activate && python -m pytest tests/test_dual_path_consolidation_char.py::TestRouteContractSeam -q --ignore=tests/load` -> ALL PASS. Report the case count.
- [ ] **Step 5: Commit the route-layer net only.**
```bash
git add tests/test_dual_path_consolidation_char.py
git commit -m "test(routes): pin both submit routes' observable contract pre-rewire (Slice 5 PR1)"
```

### Task 1.2: `ExistingSubmission` dataclass + `find_existing_submission` extension

**Files:** Modify `backend/services/submission_repository.py`; Modify `tests/test_submission_repository.py`

- [ ] **Step 1: RED — dataclass + ABC method existence test.** Append to `tests/test_submission_repository.py`:

```python
def test_existing_submission_dataclass_shape():
    from backend.services.submission_repository import ExistingSubmission
    es = ExistingSubmission(id="abc", results={"score": 90}, student_name="Pat")
    assert es.id == "abc"
    assert es.results == {"score": 90}
    assert es.student_name == "Pat"
    # Optional fields default to None
    es2 = ExistingSubmission(id="def")
    assert es2.results is None
    assert es2.student_name is None


def test_find_existing_submission_method_exists():
    from backend.services.submission_repository import SubmissionRepository
    assert hasattr(SubmissionRepository, "find_existing_submission")
```
Run -> FAIL.

- [ ] **Step 2: GREEN — add the dataclass.** Add to the top of `backend/services/submission_repository.py` (after the existing imports, before `class SubmissionPathType`):

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExistingSubmission:
    """Return type of SubmissionRepository.find_existing_submission.

    Each adapter populates the fields its query selects. Caller handles
    None vs hit and uses whatever fields are available. JoinCode populates
    id + results + student_name (the 'submissions' table's id, results,
    student_name columns). Class populates id + student_name (the
    'student_submissions' table's id, student_name columns; results is
    not selected by the class-based dedup pre-check today).
    """
    id: str
    results: Optional[dict] = None
    student_name: Optional[str] = None
```

Add the abstract method declaration on `SubmissionRepository`:

```python
    def find_existing_submission(self, lookup_key, student_info):
        """Route-layer dedup pre-check. Returns ExistingSubmission or None.

        Per-adapter implementation preserves each path's exact query mechanism
        (fuzzy ilike for join-code, exact match for class-based).
        """
        raise NotImplementedError("find_existing_submission is path-specific")
```

Run Step-1 tests -> PASS.

- [ ] **Step 3: RED — JoinCode `find_existing_submission` behavior.** Append:

```python
def test_joincode_find_existing_submission_hit():
    sb = FakeSupabase()
    sb.tables["submissions"].row = {
        "id": "sub-1", "student_name": "Pat", "results": {"score": 90}
    }
    repo = JoinCodeSubmissionRepository(sb)
    es = repo.find_existing_submission(lookup_key="ABCD12", student_info={"name": "Pat"})
    assert es is not None
    assert es.id == "sub-1"
    assert es.results == {"score": 90}
    assert es.student_name == "Pat"


def test_joincode_find_existing_submission_miss():
    sb = FakeSupabase()
    sb.tables["submissions"].row = None  # no row matches
    repo = JoinCodeSubmissionRepository(sb)
    es = repo.find_existing_submission(lookup_key="ABCD12", student_info={"name": "Pat"})
    assert es is None
```
Run -> FAIL.

- [ ] **Step 4: GREEN — implement on `JoinCodeSubmissionRepository`** (port the exact ilike query semantic from `student_portal_routes.py:1454`):

```python
    def find_existing_submission(self, lookup_key, student_info):
        if not self._sb or not lookup_key:
            return None
        try:
            result = self._sb.table(self.table_name).select(
                "id, results, student_name"
            ).eq("join_code", lookup_key).ilike(
                "student_name", student_info.get("name", "")
            ).execute()
        except Exception:
            return None
        rows = result.data if result else None
        if not rows:
            return None
        # If multiple matches, take the first (the existing route does
        # the same: it reads the first row of the result).
        row = rows[0] if isinstance(rows, list) else rows
        return ExistingSubmission(
            id=row.get("id"),
            results=row.get("results"),
            student_name=row.get("student_name"),
        )
```

Note: the FakeSupabase `_Query` class needs an `ilike(col, val)` method (currently has only `eq`). Add it inline by extending the fake in test setup, or extend the canonical fake. Cleanest: add a one-line `ilike` to the fake in `tests/test_submission_repository.py`:

```python
    def ilike(self, col, val):
        self._filters[("ilike", col)] = val
        return self
```

Run Step-3 tests -> PASS.

- [ ] **Step 5: RED — Class `find_existing_submission` behavior.** Append:

```python
def test_class_find_existing_submission_hit():
    sb = FakeSupabase()
    sb.tables["student_submissions"].row = {"id": "sub-7", "student_name": "Chris"}
    repo = ClassSubmissionRepository(sb)
    es = repo.find_existing_submission(
        lookup_key="content-uuid-1",
        student_info={"student_id": "stu-42"},
    )
    assert es is not None
    assert es.id == "sub-7"
    assert es.results is None  # class path's pre-check does not select results
    assert es.student_name == "Chris"


def test_class_find_existing_submission_miss():
    sb = FakeSupabase()
    sb.tables["student_submissions"].row = None
    repo = ClassSubmissionRepository(sb)
    es = repo.find_existing_submission(
        lookup_key="content-uuid-1",
        student_info={"student_id": "stu-42"},
    )
    assert es is None
```
Run -> FAIL.

- [ ] **Step 6: GREEN — implement on `ClassSubmissionRepository`.** Port the exact query from `student_account_routes.py:1137` (read 1137-1145 in full to get the eq() chain; the class-based dedup keys on `student_id` + `content_id` per the Phase 4.1 dedup_key composite). Place the body on the class:

```python
    def find_existing_submission(self, lookup_key, student_info):
        if not self._sb or not lookup_key or not student_info.get("student_id"):
            return None
        try:
            # Mirror student_account_routes.py:1137 exactly. The dedup
            # query selects only id today (class path does not return
            # existing results inline); preserve that.
            result = self._sb.table(self.table_name).select(
                "id, student_name"
            ).eq(
                "content_id", lookup_key
            ).eq(
                "student_id", student_info["student_id"]
            ).execute()
        except Exception:
            return None
        rows = result.data if result else None
        if not rows:
            return None
        row = rows[0] if isinstance(rows, list) else rows
        return ExistingSubmission(
            id=row.get("id"),
            results=None,
            student_name=row.get("student_name"),
        )
```

Run Step-5 tests -> PASS.

- [ ] **Step 7: Full module test pass.** `python -m pytest tests/test_submission_repository.py -q --ignore=tests/load` -> ALL PASS. Report count.
- [ ] **Step 8: Commit.**
```bash
git add backend/services/submission_repository.py tests/test_submission_repository.py
git commit -m "feat(portal): add ExistingSubmission + SubmissionRepository.find_existing_submission (Slice 5 PR1)"
```

### Task 1.3: `PublishedContentRepository` module (additive, parallel to `SubmissionRepository`)

**Files:** Create `backend/services/published_content_repository.py`; Create `tests/test_published_content_repository.py`

- [ ] **Step 1: RED — module + factory existence.** Create `tests/test_published_content_repository.py`:

```python
"""Unit tests for backend.services.published_content_repository (PR1, additive).

Parallel to backend.services.submission_repository. Reuses SubmissionPathType
as the path discriminator. Nothing in production imports this module in PR1.
"""
from tests.test_submission_repository import FakeSupabase


def test_module_imports():
    from backend.services.published_content_repository import (
        PublishedContentRepository,
        JoinCodePublishedRepository,
        ClassPublishedRepository,
        published_content_repository_for,
    )
    assert PublishedContentRepository.__name__ == "PublishedContentRepository"


def test_factory_returns_correct_adapter():
    from backend.services.submission_repository import SubmissionPathType
    from backend.services.published_content_repository import (
        JoinCodePublishedRepository,
        ClassPublishedRepository,
        published_content_repository_for,
    )
    sb = FakeSupabase()
    assert isinstance(
        published_content_repository_for(SubmissionPathType.JOIN_CODE, sb),
        JoinCodePublishedRepository,
    )
    assert isinstance(
        published_content_repository_for(SubmissionPathType.CLASS, sb),
        ClassPublishedRepository,
    )


def test_factory_accepts_legacy_string():
    from backend.services.published_content_repository import (
        JoinCodePublishedRepository,
        ClassPublishedRepository,
        published_content_repository_for,
    )
    sb = FakeSupabase()
    assert isinstance(
        published_content_repository_for("submissions", sb),
        JoinCodePublishedRepository,
    )
    assert isinstance(
        published_content_repository_for("student_submissions", sb),
        ClassPublishedRepository,
    )
```
Run -> FAIL (ModuleNotFoundError).

- [ ] **Step 2: GREEN — module scaffolding.** Create `backend/services/published_content_repository.py`:

```python
"""Published-content repository abstraction for the dual publish path.

Parallel to backend.services.submission_repository. The published-content
tables (published_assessments for the join-code path, published_content for
the class-based path) are read by the route entry points. This module
abstracts that read behind a uniform interface so the routes do not need
to know which table is queried or by which column.

Reuses the SubmissionPathType enum and the path-discriminator semantics from
submission_repository (the enum value equals the legacy submissions table
string so the Celery boundary stays unchanged). This module never imports
backend.app and never imports a route module.
"""
import logging
from typing import Optional

from backend.services.submission_repository import SubmissionPathType

logger = logging.getLogger(__name__)


class PublishedContentRepository:
    """Published-content row I/O for one publish path."""

    table_name: str = ""
    lookup_column: str = ""

    def __init__(self, sb):
        self._sb = sb

    def fetch_by_lookup_key(self, key) -> Optional[dict]:
        """Return the published-content row dict, or None if absent."""
        if not self._sb or not key:
            return None
        try:
            result = self._sb.table(self.table_name).select("*").eq(
                self.lookup_column, key
            ).execute()
        except Exception as e:
            logger.error("Failed to fetch published content: %s", e)
            return None
        rows = result.data if result else None
        if not rows:
            return None
        return rows[0] if isinstance(rows, list) else rows


class JoinCodePublishedRepository(PublishedContentRepository):
    table_name = "published_assessments"
    lookup_column = "join_code"


class ClassPublishedRepository(PublishedContentRepository):
    table_name = "published_content"
    lookup_column = "id"


def published_content_repository_for(path_type, sb) -> PublishedContentRepository:
    """Reconstruct the adapter from the path discriminator. Accepts the
    SubmissionPathType enum or the legacy table-name string (transitional)."""
    if isinstance(path_type, str):
        path_type = SubmissionPathType(path_type)
    if path_type is SubmissionPathType.JOIN_CODE:
        return JoinCodePublishedRepository(sb)
    if path_type is SubmissionPathType.CLASS:
        return ClassPublishedRepository(sb)
    raise ValueError(f"unknown submission path type: {path_type!r}")
```

Run Step-1 tests -> PASS.

- [ ] **Step 3: RED — `fetch_by_lookup_key` behavior per adapter.** Append:

```python
def test_joincode_fetch_by_lookup_key_hit():
    sb = FakeSupabase()
    sb.tables["published_assessments"].row = {
        "id": "pa-1", "join_code": "ABCD12", "assessment": {"title": "T"}
    }
    from backend.services.published_content_repository import JoinCodePublishedRepository
    repo = JoinCodePublishedRepository(sb)
    row = repo.fetch_by_lookup_key("ABCD12")
    assert row is not None
    assert row["id"] == "pa-1"


def test_joincode_fetch_by_lookup_key_miss():
    sb = FakeSupabase()
    sb.tables["published_assessments"].row = None
    from backend.services.published_content_repository import JoinCodePublishedRepository
    repo = JoinCodePublishedRepository(sb)
    assert repo.fetch_by_lookup_key("ABCD12") is None


def test_class_fetch_by_lookup_key_hit():
    sb = FakeSupabase()
    sb.tables["published_content"].row = {
        "id": "content-1", "content": {}, "due_date": "2026-06-01"
    }
    from backend.services.published_content_repository import ClassPublishedRepository
    repo = ClassPublishedRepository(sb)
    row = repo.fetch_by_lookup_key("content-1")
    assert row is not None
    assert row["id"] == "content-1"


def test_class_fetch_by_lookup_key_miss():
    sb = FakeSupabase()
    sb.tables["published_content"].row = None
    from backend.services.published_content_repository import ClassPublishedRepository
    repo = ClassPublishedRepository(sb)
    assert repo.fetch_by_lookup_key("content-1") is None


def test_falsy_inputs_return_none():
    from backend.services.published_content_repository import JoinCodePublishedRepository
    repo = JoinCodePublishedRepository(FakeSupabase())
    assert repo.fetch_by_lookup_key(None) is None
    assert repo.fetch_by_lookup_key("") is None
    repo2 = JoinCodePublishedRepository(None)
    assert repo2.fetch_by_lookup_key("ABCD12") is None
```
Run -> all PASS already (the GREEN implementation in Step 2 covered these). If any FAIL, fix the base `fetch_by_lookup_key` body.

- [ ] **Step 4: Full module test pass + no-cycle gate.**
  - `python -m pytest tests/test_published_content_repository.py -q --ignore=tests/load` -> ALL PASS.
  - `grep -nE "^(from|import) backend\.(app|routes)" backend/services/published_content_repository.py` -> EMPTY.
  - `python -c "import backend.services.published_content_repository"` (under venv) -> ok.
  - `ruff check backend/services/published_content_repository.py tests/test_published_content_repository.py` -> clean.
- [ ] **Step 5: Commit.**
```bash
git add backend/services/published_content_repository.py tests/test_published_content_repository.py
git commit -m "feat(portal): add PublishedContentRepository abstraction (additive, unwired) (Slice 5 PR1)"
```

### Task 1.4: Migrate test patch targets from module symbols to repo methods

**Files:** Modify `tests/test_dual_path_consolidation_char.py`, `tests/test_grading_tasks.py`, `tests/test_grade_portal_submission_sync.py`

The PR2 rewire will (a) delete `_fetch_submission_row` and `_claim_submission_for_grading` from `portal_grading.py`, and (b) switch `on_failure` from `_safe_update_submission` to `repo.mark_failed`. Tests that patch those module symbols must migrate to patching the repository methods FIRST (with the helpers still in place and still being called by the tests' subjects) so PR2 can do its deletions without breaking tests.

- [ ] **Step 1: Migrate `TestFailureSeam`** in `tests/test_dual_path_consolidation_char.py:302`. Read the class body first. Each test in the class patches `backend.services.portal_grading._safe_update_submission` and asserts call args. Rewrite the patches to target `backend.services.submission_repository.SubmissionRepository.update` (or `.mark_failed`, whichever the test asserts) AND adjust the call-arg assertions to match the repo method's signature (no `sb` parameter; no `table_name` kwarg; the table is implicit in `self.table_name`; the fields dict is positional or keyword as the repo method takes). For each test, run it after the change to confirm it still passes with the helpers still in place (Slice 4's `on_failure` calls `_safe_update_submission` which then calls `repo.update` internally? No: `_safe_update_submission` does NOT call `repo.update`; it writes directly to `sb.table(table_name).update(...)`. So patching `SubmissionRepository.update` would NOT be intercepted by current code.).
- [ ] **Step 2 (revised approach for TestFailureSeam):** because Slice 4's current `on_failure` calls `_safe_update_submission` directly (bypassing the repo), migrating the patch target now would make the test pass for the wrong reason (the patched repo method is never called). Two options:
  - **(a) Keep `TestFailureSeam` patching `_safe_update_submission` for PR1, then update both the patch target AND the production code in PR2 in lockstep.** This is the cleaner sequencing: PR1 leaves `TestFailureSeam` alone; PR2 changes both `grading_tasks.py:on_failure` (to call `repo.mark_failed`) and the test (to patch `SubmissionRepository.update`/`.mark_failed`) in the same commit. The byte-identical-char-net invariant is satisfied because the OBSERVABLE row write is the same.
  - **(b) Add an indirection in `_safe_update_submission` so it delegates to `repo.update` internally.** Wider blast radius; rejected.
- [ ] **Step 3: Apply option (a).** Do NOT modify `TestFailureSeam` in PR1. Leave it as-is until PR2's Task 2.4 (which migrates the test + the production code in lockstep). Document this choice in the commit message of the next step.
- [ ] **Step 4: Migrate `TestClaimSeam`** in `tests/test_dual_path_consolidation_char.py:43`. Tests in this class patch `backend.services.portal_grading._claim_submission_for_grading` or `_fetch_submission_row`. Slice 4's `grade_portal_submission_sync` calls `repo.fetch()` and `repo.claim_for_grading()` directly (not the helpers), so patching the repo methods IS effective for these tests. Re-target each `patch(...)` from the helper module symbol to the corresponding repo method (`SubmissionRepository.fetch`, `SubmissionRepository.claim_for_grading`). Adjust call-arg assertions to drop the `sb` / `table_name` positional args. Run -> PASS.
- [ ] **Step 5: Migrate `test_grading_tasks.py`** sites at lines 82, 105, 312. The `on_failure` test sites — same problem as `TestFailureSeam`. Leave as-is for PR1; migrate in PR2's lockstep change. Other sites that patch `_fetch_submission_row` or `_claim_submission_for_grading` -> retarget to repo methods (same as Step 4).
- [ ] **Step 6: Migrate `tests/test_grade_portal_submission_sync.py`** sites that reference `_fetch_submission_row` or `_claim_submission_for_grading` directly -> retarget to repo methods. Tests that reference `_is_stale_claim` stay untouched (the predicate stays in portal_grading.py).
- [ ] **Step 7: Run the migrated suites.** `python -m pytest tests/test_dual_path_consolidation_char.py tests/test_grading_tasks.py tests/test_grade_portal_submission_sync.py -q --ignore=tests/load` -> ALL PASS. Char net byte-identical to pre-migration values (status codes + JSON payloads unchanged; only patch targets changed).
- [ ] **Step 8: Commit.**
```bash
git add tests/test_dual_path_consolidation_char.py tests/test_grading_tasks.py tests/test_grade_portal_submission_sync.py
git commit -m "test: migrate _fetch/_claim patch targets to SubmissionRepository methods (Slice 5 PR1)

TestFailureSeam and on_failure-related sites in test_grading_tasks stay on
_safe_update_submission patches; PR2 will migrate them in lockstep with
the production-code switch from _safe_update_submission to repo.mark_failed."
```

### Task 1.5: Open PR 1

- [ ] Controller opens PR1 after two-stage subagent review (spec-compliance then code-quality). 9 CI checks green; suite stays 5115 passed / 0 failed (or +1/+N from the new tests added in this PR). Branch is purely additive: no production code calls the new module yet, no orphan helper is deleted yet, `on_failure` still calls `_safe_update_submission`. Behavior change is impossible by construction.

---

## PR 2: the rewire (routes onto repos + #431 fold-in + char net stays byte-identical)

### Task 2.1: Branch + RED grep gate

**Files:** Modify `tests/test_dual_path_consolidation_char.py`

- [ ] **Step 1: Branch off the merged PR1.**
```bash
git checkout main && git pull origin main && git checkout -b feature/dual-path-completion-pr2
```
- [ ] **Step 2: RED — add a route-layer grep-gate test.** Append to `tests/test_dual_path_consolidation_char.py`:

```python
def test_no_inline_published_or_dedup_queries_in_submit_routes():
    """After PR2 the two submit routes do not contain raw inline queries
    against published_assessments / published_content / the dedup pre-check
    pattern. Those reads go through the repos."""
    import pathlib
    sp = pathlib.Path("backend/routes/student_portal_routes.py").read_text()
    sa = pathlib.Path("backend/routes/student_account_routes.py").read_text()
    # Submit-by-code body (def submit_assessment) must not call db.table('published_assessments')
    # nor do the inline ilike-name dedup. Other functions in the same file
    # that legitimately query published_assessments are unaffected.
    # Heuristic: the specific dedup pattern is gone repo-wide.
    assert ".ilike('student_name'" not in sp, "join-code inline ilike dedup remains"
    # Class-submit body (def submit_student_work) must not contain inline
    # student_submissions dedup pre-check.
    # The exact dedup at line 1137 today is: db.table('student_submissions').select('id').eq(...)
    # post-PR2 it is repo.find_existing_submission(...) inside submit_student_work.
    # Other functions can still query student_submissions; the gate is scoped to the route bodies.
    # We grep for the specific pattern only inside submit_student_work's body lines (re-derive at edit time).
    # For a coarse gate: assert no .select('id').eq('content_id' AND ).eq('student_id' chained in the file's submit body.
    # Refined gate is part of the implementation (the body itself is the source of truth).
```

(Refined gate body: read the function range for `submit_student_work` and substring-check; the loose gate above is acceptable for PR-level enforcement plus the char-net byte-identity is the real proof.)

Run -> FAIL (the `ilike` pattern is still in `student_portal_routes.py:1454`).

- [ ] **Step 3: Commit the RED gate.**
```bash
git add tests/test_dual_path_consolidation_char.py
git commit -m "test(routes): RED grep gate for inline dedup removal (Slice 5 PR2)"
```

### Task 2.2: Rewire `student_portal_routes.py` `submit_assessment`

**Files:** Modify `backend/routes/student_portal_routes.py`

- [ ] **Step 1: Re-derive lines** (`grep -nE "^def submit_assessment|db\.table\('published_assessments'\)|db\.table\('submissions'\).*join_code|ilike\('student_name'" backend/routes/student_portal_routes.py`). Read the full body (def 1413 today, runs roughly through 1605).
- [ ] **Step 2: Identify the published-content fetch site** (inside `submit_assessment`'s body, the line where the route reads `db.table('published_assessments').select(...).eq('join_code', code)` to get the assessment row). Capture its exact local variable assignment (e.g. `assessment = ...['assessment']` or whatever the route does).
- [ ] **Step 3: Rewire.** At the top of `submit_assessment` (right after the route's input validation + `db = get_supabase()` setup), add:

```python
from backend.services.published_content_repository import published_content_repository_for
from backend.services.submission_repository import (
    SubmissionPathType, repository_for,
)
content_repo = published_content_repository_for(SubmissionPathType.JOIN_CODE, db)
submission_repo = repository_for(SubmissionPathType.JOIN_CODE, db)
```

Replace the inline published-content fetch with `published_row = content_repo.fetch_by_lookup_key(code)`. Replace the inline dedup query at line 1454 with `existing = submission_repo.find_existing_submission(code, {"name": student_name})`. The post-dedup branch (returning the existing results to the client) consumes `existing.id`, `existing.results`, `existing.student_name` directly from the dataclass (no shape change to the route's response JSON because the per-route response builder formats the dataclass back into the route's existing shape — see spec section 4).

Keep all subsequent code (upsert, Celery `.delay`, thread fallback `_spawn_thread_grading`) UNCHANGED. The Slice 4 abstraction handles the write/grading path; this PR only changes the read/dedup pre-check.

- [ ] **Step 4: Run the route's tests + the route-layer char net.**
```bash
source venv/bin/activate
python -m pytest tests/test_student_portal_routes.py tests/test_dual_path_consolidation_char.py::TestRouteContractSeam -q --ignore=tests/load
```
ALL PASS, with `TestRouteContractSeam` assertions byte-identical to PR1's pinned values. If any pinned status code or JSON body changes, STOP and report (a real behavior change leaked).
- [ ] **Step 5: Commit.**
```bash
git add backend/routes/student_portal_routes.py
git commit -m "refactor(routes): student_portal_routes.submit_assessment uses parallel repos (Slice 5 PR2)"
```

### Task 2.3: Rewire `student_account_routes.py` `submit_student_work`

**Files:** Modify `backend/routes/student_account_routes.py`

- [ ] **Step 1: Re-derive lines** (`grep -nE "^def submit_student_work|db\.table\('published_content'\)|db\.table\('student_submissions'\).*content_id" backend/routes/student_account_routes.py`). Read the full body (def 1107 today, runs roughly through 1300).
- [ ] **Step 2:** At the top of `submit_student_work` (after auth/token resolution + `db = get_supabase()` setup), add:

```python
from backend.services.published_content_repository import published_content_repository_for
from backend.services.submission_repository import (
    SubmissionPathType, repository_for,
)
content_repo = published_content_repository_for(SubmissionPathType.CLASS, db)
submission_repo = repository_for(SubmissionPathType.CLASS, db)
```

Replace the inline `db.table('published_content').select(...).eq('id', content_id)` fetch with `published_row = content_repo.fetch_by_lookup_key(content_id)`. Replace the inline dedup query at line 1137 with `existing = submission_repo.find_existing_submission(content_id, {"student_id": student_id})`. The post-dedup branch consumes `existing.id` and `existing.student_name` from the dataclass (results is None on this path because the class-based dedup pre-check does not select results today; the route's response builder uses what it has, unchanged).

All subsequent code (upsert, thread spawn `threading.Thread(target=run_portal_grading_thread, ...)`) UNCHANGED.

- [ ] **Step 3: Run the route's tests + char net.**
```bash
python -m pytest tests/test_student_account_coverage.py tests/test_dual_path_consolidation_char.py::TestRouteContractSeam -q --ignore=tests/load
```
ALL PASS, byte-identical to PR1's pin.
- [ ] **Step 4: Commit.**
```bash
git add backend/routes/student_account_routes.py
git commit -m "refactor(routes): student_account_routes.submit_student_work uses parallel repos (Slice 5 PR2)"
```

### Task 2.4: #431 fold-in (3 items, in this order)

**Files:** Modify `backend/tasks/grading_tasks.py`, `backend/services/portal_grading.py`, `tests/test_dual_path_consolidation_char.py`, `tests/test_grading_tasks.py`, `tests/test_grade_portal_submission_sync.py`

Lockstep migration: change BOTH the production code AND the patching tests in the same commit so the char net stays byte-identical.

- [ ] **Step 1: Migrate `on_failure` (#431 item 1).** In `backend/tasks/grading_tasks.py:40-70`:
  - Replace the `from backend.services.portal_grading import _safe_update_submission` import inside `on_failure` with `from backend.services.submission_repository import repository_for`.
  - Replace the `_safe_update_submission(sb, submission_id, {'status':'failed','error_message':str(exc)[:500]}, table_name=supabase_table)` call with `repository_for(supabase_table, sb).mark_failed(submission_id, exc)`.
  - Update the PR2 NOTE comment block above the call to reflect the new state.
  In `tests/test_dual_path_consolidation_char.py` `TestFailureSeam` (line 302) and `tests/test_grading_tasks.py` lines 82, 105, 312: replace `patch('backend.services.portal_grading._safe_update_submission')` with `patch('backend.services.submission_repository.SubmissionRepository.update')` (or `.mark_failed`, depending on what the test asserts). Adjust call-arg assertions to match the new method's signature (drop `sb` positional arg, drop `table_name` kwarg, expect `submission_id` + `fields` or `submission_id` + `error`).
  Run `python -m pytest tests/test_grading_tasks.py tests/test_dual_path_consolidation_char.py::TestFailureSeam -q --ignore=tests/load` -> ALL PASS, every pinned status + DB-effect assertion unchanged.
- [ ] **Step 2: Delete orphaned helpers (#431 item 2).** Confirm zero production callers: `grep -rnE "(_fetch_submission_row|_claim_submission_for_grading)\(" backend/ --include="*.py" | grep -vE "def (_fetch_submission_row|_claim_submission_for_grading)"`. Expected: only test-file references (Task 1.4 migrated those to repo methods already). Delete `_fetch_submission_row` (def `portal_grading.py:339`) and `_claim_submission_for_grading` (def `portal_grading.py:374`) and their bodies. Leave `_safe_update_submission` (def 314) untouched (the repo `update` method ports its semantics but the helper itself may still have non-test callers; check first — `grep -rn "_safe_update_submission(" backend/ --include="*.py" | grep -v "def _safe_update_submission"` — if zero non-test callers, delete it too; otherwise leave it as a small back-compat shim).
  Run `python -m pytest tests/test_grade_portal_submission_sync.py tests/test_dual_path_consolidation_char.py -q --ignore=tests/load` -> ALL PASS.
- [ ] **Step 3: Rename `supabase_table` -> `path_type` (#431 item 3).** In `backend/services/portal_grading.py`:
  - `grade_portal_submission_sync` (def 546): rename `supabase_table` -> `path_type`; default stays `SubmissionPathType.CLASS` (the enum, not `.CLASS.value`; the function body's `repository_for(path_type, sb)` call coerces). Update the docstring.
  - `run_portal_grading_thread` (def 1002): same rename.
  In tests that pin the signature (`sig.parameters['supabase_table'].default == ...`): rename the kwarg and update the expected default to `SubmissionPathType.CLASS`. Re-derive the test locations with `grep -rn "sig.parameters\['supabase_table'\]" tests/`.
  In `backend/tasks/grading_tasks.py` `grade_portal_submission` task (def 101) and the `on_failure` extraction (line 42): the param to the Celery task stays `supabase_table` in name because the `on_failure args[2]` slot is tied to that positional, and the enum's `.value` (the legacy string) is what crosses the wire. The internal forwarding to `grade_portal_submission_sync` becomes `path_type=supabase_table` (the coercion handles it).
  Run `python -m pytest tests/test_dual_path_consolidation_char.py tests/test_grade_portal_submission_sync.py tests/test_grading_tasks.py -q --ignore=tests/load` -> ALL PASS.
- [ ] **Step 4: Commit (single commit folds all 3 items).**
```bash
git add backend/tasks/grading_tasks.py backend/services/portal_grading.py tests/test_dual_path_consolidation_char.py tests/test_grading_tasks.py tests/test_grade_portal_submission_sync.py
git commit -m "refactor(portal): close #431 transitional residuals (unify on_failure + retire dead helpers + rename param) (Slice 5 PR2)

- on_failure now calls repo.mark_failed; TestFailureSeam patches the repo method
- _fetch_submission_row and _claim_submission_for_grading deleted (zero callers post-PR2)
- supabase_table renamed to path_type on grade_portal_submission_sync + run_portal_grading_thread
- char net byte-identical post-change"
```

### Task 2.5: Grep gate green + char-net byte-identical + full regression

- [ ] **Step 1:** `python -m pytest tests/test_dual_path_consolidation_char.py::test_no_inline_published_or_dedup_queries_in_submit_routes -q --ignore=tests/load` -> PASS (was RED in Task 2.1).
- [ ] **Step 2:** `python -m pytest tests/test_dual_path_consolidation_char.py -q --ignore=tests/load` -> ALL PASS. `TestRouteContractSeam` assertions byte-identical to PR1's pin. `TestClaimSeam`, `TestUpdateSeam`, `TestFailureSeam` pass with the migrated patches.
- [ ] **Step 3:** No-cycle gate: `grep -nE "^(from|import) backend\.(app|routes)" backend/services/published_content_repository.py backend/services/submission_repository.py` -> EMPTY. `python -c "import backend.services.published_content_repository; import backend.services.submission_repository"` -> ok.
- [ ] **Step 4:** Full regression: `python -m pytest tests/ -q --ignore=tests/load 2>&1 | tail -8` -> 0 failed (tolerated exception: a lone `tests/test_llm_adapter_gemini.py::test_gemini_chat_uses_breaker` network flake that passes in isolation). `ruff check backend/ -q` -> no new findings.
- [ ] **Step 5:** Sentry conservation: `grep -c sentry_sdk.capture_exception backend/services/portal_grading.py backend/services/published_content_repository.py backend/services/submission_repository.py backend/routes/student_portal_routes.py backend/routes/student_account_routes.py` vs origin/main. If any moved between files, update `tests/test_sis_alerting.py` `PR_B_EXPECTED_CAPTURES` the move-and-account way prior slices did (dated, no em-dash required per project house style), and re-run `python -m pytest tests/test_sis_alerting.py -q --ignore=tests/load`.
- [ ] **Step 6: Commit (any move-accounting only; otherwise skip).**
```bash
git add -A
git commit -m "test(sentry): account for any capture relocation (Slice 5 PR2)" --allow-empty
```

### Task 2.6: Slice closeout + open PR 2

**Files:** Modify `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`, this plan, the spec doc

- [ ] **Step 1: STATUS-stamp** the plan with a line right after `**Goal:**`: `**STATUS: CLOSED 2026-05-19** -> shipped via PR1 (PublishedContentRepository module + ABC extension + char-net extension + test migration) and PR2 (route rewire + #431 fold-in). Second half of Architecture ground 1 closed. Zero schema change, zero behavior change.` Same STATUS line on the spec doc.
- [ ] **Step 2: Append a dated section** to `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` matching the existing dated-section house style. Cover: route + read + dedup boundary closed (the inline queries are gone, the abstractions are load-bearing in both routes); #431 fold-in shipped (on_failure unified, 2 dead helpers retired, supabase_table renamed); zero schema change / zero data migration / zero behavior change proven by the byte-identical char net plus per-adapter unit tests; out-of-scope unchanged (no DI introduction, no HTTP endpoint consolidation, no frontend change, no physical table consolidation); state that a 3-model reconciled re-score follows as its own dated section, weighing whether closing ground 1 fully (with ground 3 still open) moves Architecture 7 to 8.
- [ ] **Step 3: Close #431.** Add a comment to issue #431 referencing the PR2 merge sha. The implementer does NOT close the issue directly; the controller does after merge.
- [ ] **Step 4: Commit docs.**
```bash
git add docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md docs/superpowers/plans/2026-05-19-dual-path-completion.md docs/superpowers/specs/2026-05-19-dual-path-completion-design.md
git commit -m "docs: close dual-path consolidation completion (PR1 + PR2); #431 retired; 3-model re-score to follow"
```
- [ ] **Step 5: Controller opens PR2** after two-stage subagent review. 9 CI checks green. Suite stays green. Controller merges; on merge, controller closes #431.

### Task 3: Post-slice 3-model reconciled re-score (controller judgment, separate from the PRs)

- [ ] After PR2 merges: Codex + Gemini + Claude independently re-score against the 2026-05-19 Post-Dual-Path baseline (the one in the assessment doc at HEAD `6767d3e`). The decisive judgment: with Architecture ground 1 now fully closed (both write/grading layer from Slice 4 and route/read/dedup layer from Slice 5), and #431 retired, but ground 3 (no DI) still open and physical table consolidation still deferred, does Architecture move 7 to 8? Conservative-floor reconcile (splits resolve down; failed-to-run not failed-low per the 2026-05-09 Clever precedent). Append the dated section. Established post-slice judgment step, not part of the mechanical extraction.

---

## Self-Review

- **Spec coverage:** spec §1 Goal -> Goal + all tasks. §2 Problem (the three residuals: routes, read split, dedup, #431) -> Task 2.2/2.3 (routes); Task 1.3 (read split); Task 1.2 (dedup); Task 2.4 (#431). §3 Two parallel repository abstractions -> Task 1.2 + Task 1.3. §4 Route-layer rewire -> Task 2.2 + Task 2.3. §5 #431 fold-in (3 items) -> Task 2.4 (3 steps, in order). §6 Char-net-first methodology -> Task 1.1 (pre-pin) + Tasks 2.2/2.3/2.4 (byte-identical post). §7 Approaches considered -> spec only. §8 Scope -> File Structure stays / scope notes per task. §9 Sequencing 2 PRs -> PR1 + PR2 task structure. §10 Risks -> per-task verification gates. §11 Success criteria -> Task 2.5 (grep gate, byte-identical, regression, no cycle) + Task 3 (re-score).
- **Placeholder scan:** the `...` in the `TestRouteContractSeam` test bodies is the explicit probe-then-pin discipline (every prior slice's char net used the same pattern); the implementer probes the real route and pins exact values, not an unfilled blank. The migrated-helper bodies (`TestClaimSeam` patches retargeting) are identified-and-relocated existing code per the Refactor-plan note. All genuinely new code (`ExistingSubmission` dataclass, the four repo method bodies, the `PublishedContentRepository` module, the factory) is given in full. No TBD, no vague steps.
- **Type consistency:** `PublishedContentRepository` ABC, `JoinCodePublishedRepository` (table_name `'published_assessments'`, lookup_column `'join_code'`), `ClassPublishedRepository` (table_name `'published_content'`, lookup_column `'id'`), `published_content_repository_for(path_type, sb)` factory, `fetch_by_lookup_key(key) -> Optional[dict]` method. `ExistingSubmission` dataclass (`id: str`, `results: Optional[dict] = None`, `student_name: Optional[str] = None`). `SubmissionRepository.find_existing_submission(lookup_key, student_info) -> Optional[ExistingSubmission]`. Names and types are consistent across the spec, the file-structure section, each task, and this self-review. The reused `SubmissionPathType` enum from Slice 4 is reused exactly (values `'submissions'` and `'student_submissions'`); the new factory accepts the enum or the legacy string for transitional safety.
- **Sequencing rationale:** PR1 is additive-only (no production code calls the new module, no helper is deleted, `on_failure` still calls `_safe_update_submission`); behavior change is impossible by construction. PR2 does the rewire + #431 fold-in in lockstep, with the byte-identical char net as the zero-behavior-change proof. Task 1.4 honestly notes that `TestFailureSeam` and `on_failure`-related test sites cannot be migrated in PR1 (because Slice 4's `on_failure` still calls `_safe_update_submission` directly, so patching the repo method would not intercept the call); those migrate in PR2's Task 2.4 in lockstep with the production-code switch. The byte-identical-net invariant is preserved either way because the observable DB row write is the same.
