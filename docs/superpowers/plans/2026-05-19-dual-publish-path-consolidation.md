# Dual Publish-Path Consolidation (Repository Layer) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `supabase_table` string dispatch in the submission-write/grading pipeline with a `SubmissionRepository` abstraction (ABC + two adapters + a serializable `SubmissionPathType` enum + a `repository_for` factory), so the pipeline has one code path, with zero schema change and zero behavior change.

**Architecture:** A new pure module `backend/services/submission_repository.py` owns the abstraction (additive, nothing imports it yet in PR1). PR2 rewires `portal_grading.py`, `grading_tasks.py`, and the four spawn/enqueue call sites to pass the enum and route every submission-row read/claim/update/fail through the repository; the two inline per-table branches relocate verbatim into the adapters. A characterization net pinning BOTH paths (Celery join-code and thread class-based) is committed green before any rewiring and must stay byte-identical after.

**Tech Stack:** Python 3.14, Supabase client, Celery + threading, pytest with `unittest.mock`. venv `/Users/alexc/Downloads/Graider/venv/` (`source venv/bin/activate`). Two sequenced PRs plus a post-slice 3-model re-score.

**Spec:** `docs/superpowers/specs/2026-05-19-dual-publish-path-consolidation-design.md`. Scope is the write/grading dispatch ONLY: the two HTTP routes, the `published_*` read split, and the route-layer dedup pre-check stay as-is (spec section 8).

**Refactor-plan note:** the two per-table behaviors that move into adapters are RELOCATED existing code, not rewritten. Steps identify them by exact location and instruct a byte-identical move (the proven Slice 1-3 discipline); their bodies are not re-pasted here because re-pasting unchanged logic is error-prone. All genuinely NEW code (enum, ABC, factory, adapter scaffolding, the fake-supabase test client, every test) is given in full. Line numbers are current-state (HEAD `6c40246`) and shift as edits land; each task re-derives them by content and the grep gate plus the characterization net are the authoritative checks.

**Environment note:** do NOT run `tests/load`; always `--ignore=tests/load`; do not contact :3000. `source venv/bin/activate` for every Python command.

---

## File Structure

- **Create:** `backend/services/submission_repository.py`, `SubmissionPathType` enum, `SubmissionRepository` ABC, `JoinCodeSubmissionRepository`, `ClassSubmissionRepository`, `repository_for` factory. One responsibility: encapsulate per-table submission-row I/O behind a typed interface. Imports only stdlib + `sentry_sdk` + `hashlib` + `logging` (whatever the relocated branches use); never imports `backend.app` or the route modules.
- **Modify:** `backend/services/portal_grading.py`, `_safe_update_submission` (310), `_fetch_submission_row` (335), `_claim_submission_for_grading` (361), `fetch_submission_full_context` (418), `grade_portal_submission_sync` (547), `run_portal_grading_thread` (988) route submission-row I/O through a `SubmissionRepository`; the `if supabase_table == 'submissions':` branch (526) and the accommodations-source selection inside `fetch_submission_full_context` relocate into the adapters.
- **Modify:** `backend/tasks/grading_tasks.py`, `grade_portal_submission` task (101, `supabase_table: str` param at 105) and `PortalGradingTask.on_failure` (40, the `args[2]`/kwarg extraction at 42, the `_safe_update_submission` call at 57) use `SubmissionPathType`.
- **Modify:** `backend/routes/student_portal_routes.py`, `_spawn_thread_grading` (52-73) and the Celery enqueue (`grade_portal_submission.delay(...)` at 1554-1557, the `_spawn_thread_grading(...)` fallback at 1568-1570) pass `SubmissionPathType.JOIN_CODE`.
- **Modify:** `backend/routes/student_account_routes.py`, the two `run_portal_grading_thread` thread spawns (target at 822 with `"student_submissions"` at 830; target at 1234 with `"student_submissions"` at 1246) pass `SubmissionPathType.CLASS`.
- **Create:** `tests/test_submission_repository.py`, per-adapter unit tests + enum + factory, using an injected fake supabase client.
- **Create:** `tests/test_dual_path_consolidation_char.py`, the characterization net pinning both paths' observable contract pre-change.
- **Modify (PR2 closeout):** `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`, this plan.

---

## Shared context for both PRs

**The seam signatures (current, HEAD `6c40246`).**

```
backend/services/portal_grading.py
  310 def _safe_update_submission(sb, submission_id, update_fields, table_name="student_submissions")
  335 def _fetch_submission_row(sb, supabase_table, submission_id)
  361 def _claim_submission_for_grading(sb, supabase_table, submission_id, task_id)
  418 def fetch_submission_full_context(supabase_table, submission_id, teacher_id)
  526   if supabase_table == 'submissions':            # per-table student_id normalization branch
  547 def grade_portal_submission_sync(submission_id, assessment, answers, student_info,
        teacher_config, teacher_id, supabase_table="student_submissions",
        student_accommodations=None, *, task_id=None, district_id=None, user_id=None, raise_transient=False)
  988 def run_portal_grading_thread(submission_id, assessment, answers, student_info,
        teacher_config, teacher_id, supabase_table="student_submissions", student_accommodations=None)
backend/tasks/grading_tasks.py
   40 def on_failure(self, exc, task_id, args, kwargs, einfo)
   42   supabase_table = args[2] if len(args) > 2 else kwargs.get('supabase_table', 'submissions')
   57   ... _safe_update_submission(..., table_name=supabase_table, ...)
  101 def grade_portal_submission(self, submission_id, teacher_id, supabase_table: str, ...)
  146   ctx = fetch_submission_full_context(supabase_table, submission_id, teacher_id)
  201   ... grade_portal_submission_sync(..., supabase_table=supabase_table, ...)
backend/routes/student_portal_routes.py
   52 def _spawn_thread_grading(submission_id, assessment, answers, student_info,
        teacher_config, teacher_id, supabase_table, student_accommodations)   # target=run_portal_grading_thread
 1554 grade_portal_submission.delay(... , 'submissions', ...)                  # enqueue, table str at 1557
 1568 _spawn_thread_grading(... , 'submissions', student_accommodations)       # enqueue-failure fallback at 1570
backend/routes/student_account_routes.py
  821 threading.Thread(target=run_portal_grading_thread, args=(... "student_submissions" at 830 ...))
 1234 threading.Thread(target=run_portal_grading_thread, args=(... "student_submissions" at 1246 ...))
```

**The two per-table behaviors that relocate into adapters (identify, move verbatim, do not rewrite):**
1. `portal_grading.py:526` `if supabase_table == 'submissions': ... else: ...`, the join-code vs class-based student-id normalization inside `fetch_submission_full_context`. Read the full `if/else` block (from 526 to where it rejoins common code) before moving.
2. The accommodations-source difference inside `fetch_submission_full_context` (the join-code path resolves accommodations from the published assessment settings; the class-based path falls back to the row's `accommodations`). Read `fetch_submission_full_context` (418-546) in full to locate both spots; both are the per-table parts that move into the adapter's context build, leaving the shared work in `fetch_submission_full_context`.

**The enum-across-Celery rule (load-bearing).** A repository object is NOT serializable across the Celery boundary. The ONLY thing that crosses any thread/Celery boundary is the enum `SubmissionPathType` (its members carry the existing string values so the wire format and the `on_failure` `args[2]` slot are unchanged). The pipeline reconstructs the adapter worker-side via `repository_for(path_type, sb)`. Never pass a repository instance into `.delay(...)`, `threading.Thread(args=...)`, or the task signature.

**Behavior-preservation discipline.** This is a behavior-preserving refactor, not a verbatim move (parameter types change, branches relocate). Therefore: the characterization net (Task 1.1) is pinned green against the CURRENT `supabase_table` wiring and committed FIRST; after the rewiring it must pass byte-identical (same statuses, same serialized rows). That equivalence is the zero-behavior-change proof. Per-adapter unit tests (Task 1.2) cover the new isolated units. The grep gate (Task 2.5) proves the string dispatch is gone.

**Fake supabase client for unit tests** (used verbatim in `tests/test_submission_repository.py`; mirrors the chained `sb.table(...).select(...).eq(...).single().execute()` / `.update(...).eq(...).execute()` shape the code uses):

```python
class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, table):
        self._t = table
        self._filters = {}

    def select(self, *_a, **_k):
        return self

    def update(self, fields):
        self._t.updates.append(dict(fields))
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def single(self):
        return self

    def execute(self):
        if self._t.raise_on_execute:
            raise self._t.raise_on_execute
        return _Resp(self._t.row)


class FakeTable:
    def __init__(self):
        self.row = None
        self.updates = []
        self.raise_on_execute = None


class FakeSupabase:
    """Records per-table state. Inject into an adapter to test it in isolation."""
    def __init__(self):
        self.tables = {}

    def table(self, name):
        t = self.tables.setdefault(name, FakeTable())
        self._last = name
        return _Query(t)
```

---

## PR 1: additive, characterization net + the repository module (zero behavior change, nothing wired yet)

### Task 1.1: Branch + characterization net pinned against current wiring

**Files:** Create `tests/test_dual_path_consolidation_char.py`

- [ ] **Step 1: Branch.**
```bash
git checkout main && git pull origin main && git checkout -b feature/dual-path-pr1-repository
```
- [ ] **Step 2: Survey the real observable contract.** Read `tests/test_grade_portal_submission_sync.py`, `tests/test_portal_grading.py`, `tests/test_grading_tasks.py` to see how the pipeline is driven in tests (they use `unittest.mock.patch`/`MagicMock` and signature introspection). Identify the existing helper most tests use to fake the pipeline's grading call so the net can assert status transitions and the final row without doing real AI grading.
- [ ] **Step 3: Write the net** pinning BOTH paths' observable contract against the CURRENT `supabase_table` wiring. Probe real behavior first (run a one-off `python -c`/`pytest -q`) and pin EXACTLY what is observed; do not assume. The net must cover, for the join-code path (`supabase_table='submissions'`, the Celery-backed path) and the class-based path (`supabase_table='student_submissions'`, the thread-backed path), independently:
  - the claim path: `_claim_submission_for_grading(sb, <table>, sid, task_id)` returns the same boolean and writes the same `grading_task_id`/`grading_started_at` for a fresh row, an already-claimed row, and a TTL-stale row;
  - the fetch path: `fetch_submission_full_context(<table>, sid, teacher_id)` returns the same normalized context shape for a representative join-code row and a representative class-based row (this is where the `:526` branch and the accommodations-source difference live, pin the exact returned dict for each);
  - the update path: `_safe_update_submission(sb, sid, {...}, table_name=<table>)` issues the update against the correct table and is a silent skip when `submission_id` is falsy and a Sentry capture when `sb` is None (pin all three);
  - the failure path: `PortalGradingTask.on_failure` extracts the table from `args[2]` and marks the row failed on the correct table.

```python
# tests/test_dual_path_consolidation_char.py
"""Characterization net for the dual publish-path consolidation.

Pins the EXACT observable contract of both submission paths (join-code
'submissions' and class-based 'student_submissions') against the current
supabase_table string-dispatch wiring. Committed green PRE-refactor; after
the SubmissionRepository rewiring every assertion here must still pass
byte-identical. That equivalence is the zero-behavior-change proof.
"""
from unittest.mock import MagicMock, patch
import backend.services.portal_grading as pg


def _sb_with_row(row):
    sb = MagicMock()
    q = sb.table.return_value.select.return_value.eq.return_value
    q.single.return_value.execute.return_value.data = row
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [row]
    return sb

# Fill the rest from the Step-3 probe. One test function per (path, branch)
# in the list above; assert exact return values / recorded table names /
# update payloads. Example skeleton (pin real values from the probe):

def test_safe_update_skips_when_no_submission_id():
    pg._safe_update_submission(MagicMock(), None, {"x": 1}, table_name="submissions")
    # pin: no exception, no table call (probe the real behavior and assert it)

def test_fetch_context_joincode_shape():
    # build a representative join-code submissions row; call
    # pg.fetch_submission_full_context('submissions', sid, tid) with the
    # supabase client patched; assert the EXACT normalized dict.
    ...

def test_fetch_context_classbased_shape():
    # same for 'student_submissions'; assert the EXACT normalized dict
    # (this pins the :526 branch + accommodations-source difference).
    ...
# ... claim fresh/already/stale x2 paths; on_failure table extraction.
```

- [ ] **Step 4: Pin green.** `source venv/bin/activate && python -m pytest tests/test_dual_path_consolidation_char.py -q --ignore=tests/load` -> ALL PASS. Report the case count and exactly which (path, branch) pairs are covered.
- [ ] **Step 5: Commit the net only.**
```bash
git add tests/test_dual_path_consolidation_char.py
git commit -m "test(portal): pin dual-path observable contract pre-consolidation (PR1)"
```

### Task 1.2: The `submission_repository.py` module (additive, TDD per unit)

**Files:** Create `backend/services/submission_repository.py`; Create `tests/test_submission_repository.py`

- [ ] **Step 1: RED, enum + factory existence/identity.** Create `tests/test_submission_repository.py` starting with the `FakeSupabase` client from Shared context, then:
```python
from backend.services.submission_repository import (
    SubmissionPathType, SubmissionRepository,
    JoinCodeSubmissionRepository, ClassSubmissionRepository, repository_for,
)


def test_enum_values_match_legacy_table_strings():
    # Wire compatibility: the enum's serialized values are the exact
    # legacy table-name strings, so the Celery args[2] slot is unchanged.
    assert SubmissionPathType.JOIN_CODE.value == "submissions"
    assert SubmissionPathType.CLASS.value == "student_submissions"


def test_factory_returns_correct_adapter_type():
    sb = FakeSupabase()
    assert isinstance(repository_for(SubmissionPathType.JOIN_CODE, sb),
                      JoinCodeSubmissionRepository)
    assert isinstance(repository_for(SubmissionPathType.CLASS, sb),
                      ClassSubmissionRepository)


def test_factory_accepts_legacy_string_for_migration_safety():
    sb = FakeSupabase()
    assert isinstance(repository_for("submissions", sb),
                      JoinCodeSubmissionRepository)
    assert isinstance(repository_for("student_submissions", sb),
                      ClassSubmissionRepository)
```
Run: `python -m pytest tests/test_submission_repository.py -q --ignore=tests/load` -> FAIL (ModuleNotFoundError).

- [ ] **Step 2: GREEN, enum, ABC, adapter scaffolding, factory.** Create `backend/services/submission_repository.py`:
```python
"""Submission-row repository abstraction for the dual publish path.

Replaces the `supabase_table` string dispatch in the grading pipeline.
Two adapters wrap the two existing tables (no schema change): the
anonymous join-code path (`submissions`) and the authenticated
class-based path (`student_submissions`). Only the enum crosses thread
and Celery boundaries (it is serializable; the enum values are the exact
legacy table-name strings, so the wire format is unchanged); the worker
reconstructs the adapter via `repository_for`. This module imports no
Flask, no route module, and never `backend.app`.
"""
import enum
import hashlib
import logging

import sentry_sdk

logger = logging.getLogger(__name__)


class SubmissionPathType(enum.Enum):
    JOIN_CODE = "submissions"
    CLASS = "student_submissions"


class SubmissionRepository:
    """Submission-row I/O for one publish path. Construct with an
    injected supabase client; the table name is fixed per subclass."""

    table_name: str = ""

    def __init__(self, sb):
        self._sb = sb

    def fetch(self, submission_id):
        """Return the raw submission row dict, or None."""
        raise NotImplementedError

    def claim_for_grading(self, submission_id, task_id):
        """Row-level dedup claim. Return True iff this caller won the claim."""
        raise NotImplementedError

    def update(self, submission_id, fields):
        """Update the submission row; silent skip on falsy id; Sentry on
        missing client or write failure (preserves _safe_update_submission)."""
        raise NotImplementedError

    def mark_failed(self, submission_id, error):
        """Mark the row grading_failed with the error message."""
        raise NotImplementedError


class JoinCodeSubmissionRepository(SubmissionRepository):
    table_name = SubmissionPathType.JOIN_CODE.value


class ClassSubmissionRepository(SubmissionRepository):
    table_name = SubmissionPathType.CLASS.value


def repository_for(path_type, sb):
    """Reconstruct the adapter from the serializable discriminator.
    Accepts the SubmissionPathType enum or the legacy table-name string
    (string acceptance is transitional safety for the Celery args slot)."""
    if isinstance(path_type, str):
        path_type = SubmissionPathType(path_type)
    if path_type is SubmissionPathType.JOIN_CODE:
        return JoinCodeSubmissionRepository(sb)
    if path_type is SubmissionPathType.CLASS:
        return ClassSubmissionRepository(sb)
    raise ValueError(f"unknown submission path type: {path_type!r}")
```
Run the Step-1 tests -> PASS.

- [ ] **Step 3: RED, `update` behavior (port `_safe_update_submission` semantics into the base).** Add to the test file:
```python
def test_update_silent_skip_on_falsy_id():
    sb = FakeSupabase()
    JoinCodeSubmissionRepository(sb).update(None, {"status": "graded"})
    assert sb.tables == {}  # no table touched, no exception


def test_update_sentry_on_missing_client(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "backend.services.submission_repository.sentry_sdk.capture_message",
        lambda *a, **k: calls.append((a, k)))
    JoinCodeSubmissionRepository(None).update("sid-1", {"status": "graded"})
    assert calls, "missing-client update must Sentry-capture (FERPA: id hashed)"


def test_update_writes_to_correct_table():
    sb = FakeSupabase()
    ClassSubmissionRepository(sb).update("sid-9", {"status": "graded"})
    assert sb.tables["student_submissions"].updates == [{"status": "graded"}]
    assert "submissions" not in sb.tables or sb.tables.get("submissions").updates == []
```
Run -> FAIL (NotImplementedError).

- [ ] **Step 4: GREEN, implement `update` on the base** (single implementation; the table name is the per-subclass `table_name`). Port the EXACT `_safe_update_submission` semantics (read `backend/services/portal_grading.py:310-333`): falsy-id silent return; missing-client -> hash the id with `hashlib.sha256(...).hexdigest()[:8]`, `logger.error`, `sentry_sdk.capture_message(..., level="error")`, return; else `self._sb.table(self.table_name).update(fields).eq("id", submission_id).execute()` wrapped in try/except that does `logger.error` + `sentry_sdk.capture_exception(e)`. Implement once on `SubmissionRepository`:
```python
    def update(self, submission_id, fields):
        if not submission_id:
            return
        if not self._sb:
            sub_hash = hashlib.sha256(str(submission_id).encode()).hexdigest()[:8]
            msg = ("Cannot update submission %s: Supabase client unavailable"
                   % sub_hash)
            logger.error(msg)
            sentry_sdk.capture_message(msg, level="error")
            return
        try:
            self._sb.table(self.table_name).update(fields).eq(
                "id", submission_id).execute()
        except Exception as e:  # noqa: BLE001 - parity with _safe_update_submission
            logger.error("Failed to update Supabase submission: %s", e)
            sentry_sdk.capture_exception(e)
```
Run Step-3 tests -> PASS.

- [ ] **Step 5: RED, `fetch` per adapter.** Add tests asserting `fetch(sid)` returns the row dict from the adapter's own table and `None` when absent, for both adapters (use `FakeSupabase`; set `sb.tables["submissions"].row = {...}` / `sb.tables["student_submissions"].row = {...}`). Pin the same access shape `_fetch_submission_row` uses (`backend/services/portal_grading.py:335-358`: `.select('*').eq('id', sid).single().execute()` then `.data`). Run -> FAIL.

- [ ] **Step 6: GREEN, implement `fetch`** on the base using `self.table_name`, mirroring `_fetch_submission_row` exactly (same select/eq/single/execute, same None-on-missing, same exception handling, read 335-358 and port verbatim into the method body). Run -> PASS.

- [ ] **Step 7: RED, `claim_for_grading` per path.** Add tests for: fresh row claim returns True and records `grading_task_id`+`grading_started_at`; already-claimed (non-stale) returns False; TTL-stale claim returns True. Drive both adapters. Pin the EXACT semantics of `_claim_submission_for_grading` + `_is_stale_claim` (`portal_grading.py:361-417`, read it). Run -> FAIL.

- [ ] **Step 8: GREEN, implement `claim_for_grading`** on the base, porting `_claim_submission_for_grading` verbatim (it currently calls `_safe_update_submission(..., table_name=supabase_table)`; in the method that becomes `self.update(...)`). Keep `_is_stale_claim` where it is in `portal_grading.py` and import it, OR move it into this module if it has no other caller (verify with `grep -rn _is_stale_claim backend/ --include=*.py`); if it has other callers, import it (no cycle: `submission_repository` may import a leaf helper from `portal_grading` only if `portal_grading` does not import `submission_repository` yet, in PR1 it does not, but to avoid a future cycle, MOVE `_is_stale_claim` into `submission_repository.py` if its only callers are claim-related, else duplicate the tiny pure predicate with a comment). Run -> PASS.

- [ ] **Step 9: RED, `mark_failed` per path.** Test that `mark_failed(sid, "boom")` updates the correct table with the failed status + error message shape used by `on_failure` today (read `grading_tasks.py:40-60` for the exact fields written). Run -> FAIL.

- [ ] **Step 10: GREEN, implement `mark_failed`** on the base as `self.update(submission_id, {<exact fields on_failure writes>})`. Run -> PASS.

- [ ] **Step 11: RED, relocate the per-table context normalization into the adapters.** Add a `normalize_context(self, row, *, base_context)` abstract method to `SubmissionRepository` and per-adapter tests pinning the EXACT normalized dict the char net (Task 1.1) recorded for a representative join-code row and class-based row. Run -> FAIL.

- [ ] **Step 12: GREEN, implement `normalize_context` on each adapter by MOVING the existing branch verbatim.** Read `backend/services/portal_grading.py:418-546`. The `if supabase_table == 'submissions':` block at 526 and the accommodations-source selection are the per-table parts. Move the `'submissions'` branch body verbatim into `JoinCodeSubmissionRepository.normalize_context` and the `else` branch verbatim into `ClassSubmissionRepository.normalize_context` (do not rewrite the logic; relocate it; adjust only variable wiring so the method takes `row` + `base_context` and returns the normalized context). Run the Step-11 tests -> PASS, asserting byte-identical to the char-net-pinned dicts.

- [ ] **Step 13: Full module test pass + no-cycle gate.**
  - `python -m pytest tests/test_submission_repository.py -q --ignore=tests/load` -> ALL PASS.
  - `grep -nE "^(from|import) backend\.(app|routes)" backend/services/submission_repository.py` -> EMPTY (no cycle, no route import).
  - `python -c "import backend.services.submission_repository"` (under venv) -> ok.
  - `ruff check backend/services/submission_repository.py tests/test_submission_repository.py` -> clean.
- [ ] **Step 14: Commit.**
```bash
git add backend/services/submission_repository.py tests/test_submission_repository.py
git commit -m "feat(portal): add SubmissionRepository abstraction (additive, unwired) (PR1)"
```

### Task 1.3: Open PR 1

- [ ] PR 1 is purely additive (the char net pins current behavior; the module is imported by nothing yet, so behavior change is impossible by construction). Controller opens/merges after two-stage review; the existing portal/grading/clever suites + the 9 CI checks must be green. Net + module + unit tests only.

---

## PR 2: rewire the pipeline + task + 4 call sites onto the repository

### Task 2.1: Branch + RED on the wiring contract

**Files:** Modify `tests/test_dual_path_consolidation_char.py`

- [ ] **Step 1: Branch off the merged PR1.**
```bash
git checkout main && git pull origin main && git checkout -b feature/dual-path-pr2-rewire
```
- [ ] **Step 2: RED, add the grep-gate assertion as an executable test.** Append to the char net:
```python
import pathlib


def test_no_supabase_table_string_dispatch_remains():
    """After PR2 the pipeline carries no supabase_table string dispatch:
    the enum + repository replace it."""
    pg = pathlib.Path("backend/services/portal_grading.py").read_text()
    gt = pathlib.Path("backend/tasks/grading_tasks.py").read_text()
    assert "supabase_table ==" not in pg
    assert "table_name=supabase_table" not in pg
    assert "supabase_table" not in gt or "SubmissionPathType" in gt
    # Tightened: zero `supabase_table` parameter dispatch in the pipeline.
    assert 'supabase_table="submissions"' not in pg
    assert 'supabase_table="student_submissions"' not in pg
```
Run: `python -m pytest tests/test_dual_path_consolidation_char.py::test_no_supabase_table_string_dispatch_remains -q --ignore=tests/load` -> FAIL (string dispatch still present).

### Task 2.2: Rewire `portal_grading.py` onto the repository

**Files:** Modify `backend/services/portal_grading.py`

- [ ] **Step 1: Re-derive lines** for the six seam functions + the 526 branch by content (`grep -nE "def (grade_portal_submission_sync|fetch_submission_full_context|run_portal_grading_thread|_fetch_submission_row|_claim_submission_for_grading|_safe_update_submission)\b|supabase_table ==" backend/services/portal_grading.py`).
- [ ] **Step 2: Replace the param type and route I/O through the repo.** In `fetch_submission_full_context`, `grade_portal_submission_sync`, and `run_portal_grading_thread`: change the `supabase_table` parameter to `path_type` typed `SubmissionPathType` (accept the legacy string too for one release: `repository_for` already coerces a str, so internal call sites that still pass a string keep working, this de-risks ordering). Near the top of each, build `repo = repository_for(path_type, sb)` once (the `sb` is already obtained in these functions; reuse it). Replace `_fetch_submission_row(sb, supabase_table, sid)` with `repo.fetch(sid)`, `_claim_submission_for_grading(sb, supabase_table, sid, task_id)` with `repo.claim_for_grading(sid, task_id)`, every `_safe_update_submission(sb, sid, fields, table_name=supabase_table)` and the raw `sb.table(supabase_table).update(...)` sites (967, 1017) with `repo.update(sid, fields)`. Replace the `if supabase_table == 'submissions':` block (526) with `ctx = repo.normalize_context(row, base_context=ctx)`. Keep `_safe_update_submission`/`_fetch_submission_row`/`_claim_submission_for_grading` as thin shims that delegate to a repo (or delete them if they have no remaining callers, verify each with `grep -rn`).
- [ ] **Step 3: Net stays byte-identical.** `python -m pytest tests/test_dual_path_consolidation_char.py tests/test_grade_portal_submission_sync.py tests/test_portal_grading.py tests/test_portal_grading_coverage.py tests/test_portal_grading_gaps.py -q --ignore=tests/load` -> ALL PASS, every pre-pinned assertion unchanged. If any pinned value changes, STOP and report (a real behavior change was introduced).
- [ ] **Step 4: Commit.**
```bash
git add backend/services/portal_grading.py tests/test_dual_path_consolidation_char.py
git commit -m "refactor(portal): route grading pipeline through SubmissionRepository (PR2)"
```

### Task 2.3: Rewire `grading_tasks.py`

**Files:** Modify `backend/tasks/grading_tasks.py`

- [ ] **Step 1:** Change `grade_portal_submission`'s `supabase_table: str` param (105) to accept the enum value; it already forwards to `fetch_submission_full_context` (146) and `grade_portal_submission_sync` (201) which now accept it (string-coercion-safe). In `on_failure` (40), the `args[2]`/kwarg extraction (42) stays (the enum's `.value` IS the legacy string, so `args[2]` is unchanged on the wire); reconstruct `repo = repository_for(supabase_table, sb)` and replace the `_safe_update_submission(..., table_name=supabase_table)` (57) with `repo.update(...)` (or `repo.mark_failed(...)` if the fields match `mark_failed`). Read 40-60 first; preserve the exact failed-row fields.
- [ ] **Step 2:** `python -m pytest tests/test_grading_tasks.py tests/test_dual_path_consolidation_char.py -q --ignore=tests/load` -> ALL PASS (the `on_failure` table-extraction char test must still pass byte-identical).
- [ ] **Step 3: Commit.**
```bash
git add backend/tasks/grading_tasks.py
git commit -m "refactor(tasks): grading Celery task uses SubmissionPathType + repository (PR2)"
```

### Task 2.4: Swap the 4 spawn/enqueue call sites to the enum

**Files:** Modify `backend/routes/student_portal_routes.py`, `backend/routes/student_account_routes.py`

- [ ] **Step 1:** `student_portal_routes.py`: import `SubmissionPathType`; the Celery enqueue `grade_portal_submission.delay(..., 'submissions', ...)` (re-derive; ~1557) -> pass `SubmissionPathType.JOIN_CODE.value` (keep `.value` so the Celery wire arg is the identical string and `on_failure`'s `args[2]` is unchanged); `_spawn_thread_grading(..., 'submissions', ...)` (~1570) and the `_spawn_thread_grading` def's `supabase_table` param (52-73, forwarded to `run_portal_grading_thread`) -> pass/forward `SubmissionPathType.JOIN_CODE`.
- [ ] **Step 2:** `student_account_routes.py`: import `SubmissionPathType`; the two `threading.Thread(target=run_portal_grading_thread, args=(... "student_submissions" ...))` (re-derive; ~830 and ~1246) -> `SubmissionPathType.CLASS`.
- [ ] **Step 3:** `python -m pytest tests/test_student_portal_routes.py tests/test_student_portal_routes_coverage.py tests/test_student_portal_routes_celery_flag.py tests/test_student_account_coverage.py tests/test_dual_path_consolidation_char.py -q --ignore=tests/load` -> ALL PASS.
- [ ] **Step 4: Commit.**
```bash
git add backend/routes/student_portal_routes.py backend/routes/student_account_routes.py
git commit -m "refactor(routes): submission spawn/enqueue sites pass SubmissionPathType (PR2)"
```

### Task 2.5: Grep gate + full regression + Sentry-floor check

- [ ] **Step 1: Grep gate.** `python -m pytest tests/test_dual_path_consolidation_char.py::test_no_supabase_table_string_dispatch_remains -q --ignore=tests/load` -> PASS (now green; was RED in Task 2.1). Also manual confirm: `grep -nE "supabase_table ==|table_name=supabase_table|supabase_table=\"(submissions|student_submissions)\"" backend/services/portal_grading.py` -> EMPTY.
- [ ] **Step 2: Char net byte-identical + no cycle.** `grep -nE "^(from|import) backend\.(app|routes)" backend/services/submission_repository.py` -> EMPTY. `python -m pytest tests/test_dual_path_consolidation_char.py tests/test_submission_repository.py -q --ignore=tests/load` -> ALL PASS unchanged.
- [ ] **Step 3: Sentry-floor move-accounting.** `grep -c sentry_sdk.capture_exception backend/services/portal_grading.py` and `... backend/services/submission_repository.py`. If any capture relocated into the repository module, update `tests/test_sis_alerting.py` `PR_B_EXPECTED_CAPTURES` the move-and-account way prior slices did (lower the `portal_grading.py` floor by the moved count, add a `backend/services/submission_repository.py: <n>` entry, dated no-em-dash comment) and run `python -m pytest tests/test_sis_alerting.py -q --ignore=tests/load` -> PASS. If zero moved, confirm `test_sis_alerting.py` is untouched and still green.
- [ ] **Step 4: Full regression.** `python -m pytest tests/ -q --ignore=tests/load 2>&1 | tail -8` -> 0 failed (a lone pre-existing `tests/test_llm_adapter_gemini.py::test_gemini_chat_uses_breaker` network flake that passes in isolation is the only tolerated exception; anything else, resolve or report). `ruff check backend/ -q` -> no new findings.
- [ ] **Step 5: Commit any move-accounting.**
```bash
git add -A
git commit -m "test(sentry): account for any capture relocation into submission_repository (PR2)" --allow-empty
```

### Task 2.6: Slice closeout + open PR 2

**Files:** Modify `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`, this plan

- [ ] **Step 1: STATUS-stamp this plan** with a line immediately after `**Goal:**`: `**STATUS: CLOSED 2026-05-19** -> shipped via PR1 (repository module + char net) and PR2 (rewire); zero schema change, zero behavior change; supabase_table string dispatch eliminated from the grading pipeline.` (use `->`, no em-dash).
- [ ] **Step 2: Append a dated section** to the assessment doc matching its existing dated-section house style (compare the Slice 1/2/3 sections; NO em-dash U+2014; no AI-tells): the dual-path code boundary is closed at the write/grading layer (the `supabase_table` string dispatch is gone, replaced by `SubmissionRepository` + `SubmissionPathType`), zero schema change / zero data migration / zero behavior change proven by the pre-pinned characterization net staying byte-identical plus per-adapter unit tests; what stays out of scope (the `published_*` read split + route-layer dedup pre-check + the two HTTP routes + the physical table consolidation, each a separable follow-up); state that a 3-model reconciled re-score follows as its own dated section (the Architecture 7->8 judgment, weighing that the no-dependency-injection ground remains).
- [ ] **Step 3: Commit docs + open PR 2.**
```bash
git add docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md docs/superpowers/plans/2026-05-19-dual-publish-path-consolidation.md
git commit -m "docs: close dual publish-path consolidation (PR1+PR2); 3-model re-score to follow"
```
Controller opens/merges PR 2 after two-stage review; 9 CI checks green; the portal/student-account/grading/Clever suites unchanged-green.

### Task 3: Post-slice 3-model reconciled re-score (controller judgment, separate from the PRs)

- [ ] After PR2 merges: Codex + Gemini + Claude independently re-score against the post-Slice-3 2026-05-19 baseline (does closing the dual-path code boundary move Architecture 7->8, weighing that the no-DI ground remains?), conservative-floor reconcile, append the dated section. Established post-slice judgment step, not part of the mechanical refactor.

---

## Self-Review

- **Spec coverage:** spec section 1 goal -> Goal + Task 1.2/2.2. Section 2 problem (11 sites, already-param-threaded seams) -> File Structure + Shared context seam table. Section 3 abstraction (the 4 ops + 2 adapters, narrow interface) -> Task 1.2 Steps 2/4/6/8/10 (fetch/claim/update/mark_failed) + Step 12 (the relocated per-table normalization inside the adapters, keeping the interface narrow). Section 4 Celery-boundary (enum crosses, factory reconstructs, task signature/`on_failure` preserved) -> the enum-across-Celery rule + Task 2.3 Step 1 + Task 2.4 (`.value` keeps the wire arg identical). Section 5 bounded call sites -> Task 2.4 with re-derived lines. Section 6 net-first + per-adapter units + grep gate -> Task 1.1 (pinned + committed first) + Task 1.2 unit tests + Task 2.1/2.5 grep gate. Section 7 approaches -> spec only. Section 8 scope (routes/reads/dedup/migration/frontend OUT) -> File Structure scope note + Task 2 touches only pipeline/task/4-sites; closeout records the out-of-scope follow-ups. Section 9 risks -> Celery (enum rule), hidden asymmetry (char net pins both paths pre-change), both runtimes (net covers Celery + thread; full regression), scope creep (grep gate scoped to the pipeline). Section 10 success -> Task 2.5 (grep gate, net byte-identical, regression, no cycle) + Task 3 (re-score).
- **Placeholder scan:** the char-net `...`/skeleton in Task 1.1 Step 3 is explicit characterization method ("probe real, pin exactly"), the established discipline, not an unfilled blank; the relocated per-table branch bodies are intentionally not re-pasted per the Refactor-plan note (identified by exact location, moved verbatim), same as the Slice 1-3 plans; all genuinely new code (enum, ABC, all four method bodies, factory, fake-sb client, every test) is given in full. No TBD, no "add error handling", no vague steps.
- **Type/name consistency:** `SubmissionPathType` (members `JOIN_CODE="submissions"`, `CLASS="student_submissions"`), `SubmissionRepository` + `JoinCodeSubmissionRepository`/`ClassSubmissionRepository`, methods `fetch`/`claim_for_grading`/`update`/`mark_failed`/`normalize_context`, `repository_for(path_type, sb)`, module `backend/services/submission_repository.py`, the seam line numbers, and the 4 call sites are identical across the spec, every task, and this self-review. The enum `.value` equals the legacy table string everywhere it crosses a boundary (stated in Shared context, Task 2.3, Task 2.4) so the Celery `on_failure` `args[2]` slot is provably unchanged.
