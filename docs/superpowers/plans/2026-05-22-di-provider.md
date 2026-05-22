# Dependency-Injection Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**STATUS: CLOSED 2026-05-22** — shipped via PR1 (#452: provider + factory `sb=_UNSET` evolution) and PR2 (#453: grading/task failure-seam migration + char-net call-count→falsifiable-observable-effect update + ergonomics-proof test). DI provider live at the repository/supabase seam; the `grading_tasks.py` failure seams + `portal_grading.py` deferred-update route through it; tests swap the DB via `override_supabase(fake)`. The 3rd Architecture-7 ground (no DI) is addressed at the seam; the broader conversion (dual-use sites, `submit_student_work` raise-vs-None semantics, the ~80 other `get_supabase()` sites, AI clients, config) is sequenced follow-up.

**Goal:** Introduce a lightweight hand-rolled dependency provider (`backend/providers.py`) at the repository/supabase seam so tests swap the database for a fake at a single `override_supabase(fake)` switch instead of monkeypatching `get_supabase()` per-module, and route the genuinely-clean grading/task failure seams through it in production.

**Architecture:** A new `backend/providers.py` wraps `supabase_client.get_supabase()` and the repo factories, with a `contextvars`-backed test-override hook. The two repo factories evolve to `sb=None` default-resolving from the provider (backward-compatible). PR1 is additive (provider + tests + factory evolution, behavior change impossible). PR2 migrates the refined set of repo-only seam call sites and updates ~3 char-net call-count assertions to observable-effect assertions.

**Tech Stack:** Python 3.14, Flask + Celery, Supabase client, pytest with `unittest.mock`. venv `/Users/alexc/Downloads/Graider/venv/` (`source venv/bin/activate`).

**Spec:** `docs/superpowers/specs/2026-05-22-di-provider-design.md` (including the section 6.3 planning-time refinement). The 2-PR split, the `contextvars` override, and the refined migration set are mandatory.

**Environment note:** do NOT run `tests/load`; always `--ignore=tests/load`; do not contact `:3000`. `source venv/bin/activate` for every Python command. All changes via PR with 9 CI checks green and commit trailer `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

---

## File Structure

**PR1 (additive):**
- **Create:** `backend/providers.py`. The provider module: `get_supabase_provider()`, `get_submission_repository(path_type)`, `get_published_content_repository(path_type)`, `override_supabase(fake)` contextmanager. Single responsibility: resolve the repository/supabase seam dependencies, with a test-override hook. Imports from `backend.supabase_client` and the two repo modules via in-function imports (no circular import, no `backend.app` import).
- **Create:** `tests/test_providers.py`. Unit tests for the provider.
- **Modify:** `backend/services/submission_repository.py`. `repository_for(path_type, sb=None)` — default-resolve `sb` from the provider when omitted.
- **Modify:** `backend/services/published_content_repository.py`. `published_content_repository_for(path_type, sb=None)` — same.

**PR2 (rewire):**
- **Modify:** `backend/tasks/grading_tasks.py`. `on_failure` (~line 57) + no-assessment failure branch (~line 183): route repo construction through `get_submission_repository(path_type)`.
- **Modify:** `backend/services/portal_grading.py`. `run_portal_grading_thread` inline update (~line 946): route through `get_submission_repository(path_type)`.
- **Modify:** `tests/test_dual_path_consolidation_char.py`. Update the ~3 `TestFailureSeam` call-count assertions to observable-effect assertions.
- **Modify:** one existing seam test (in `tests/test_grading_tasks.py` or `tests/test_dual_path_consolidation_char.py`) rewritten to use `override_supabase` — the ergonomics proof.

**Closeout:**
- **Modify:** `docs/superpowers/specs/2026-05-22-di-provider-design.md` (STATUS), `docs/superpowers/plans/2026-05-22-di-provider.md` (STATUS), `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` (dated section).

---

## Shared context

**`SubmissionPathType`** lives in `backend/services/submission_repository.py` (enum: `JOIN_CODE = "submissions"`, `CLASS = "student_submissions"`). The factories accept the enum OR the legacy string.

**Current factory signatures (verify before editing):**
```
backend/services/submission_repository.py:340      def repository_for(path_type, sb):
backend/services/published_content_repository.py:76 def published_content_repository_for(path_type, sb):
```

**The `FakeSupabase` test scaffolding** is in `tests/test_submission_repository.py` (classes `FakeSupabase`, `FakeTable`, `_Query`, `_Resp`). Reuse by importing: `from tests.test_submission_repository import FakeSupabase`.

**The repo adapters take `sb` in `__init__`** and guard `if not self._sb` internally — so a repo built with a `None` client no-ops its writes safely. This is why migrating an `if sb:`-guarded call site to `get_submission_repository(...)` (which always builds a repo) keeps the observable DB effect identical (no write when client is None) even though `repository_for` is now always called.

---

## PR 1: additive (provider + factory evolution)

### Task 1.1: Branch + provider module (TDD)

**Files:** Create `backend/providers.py`; Create `tests/test_providers.py`

- [ ] **Step 1: Branch.**

```bash
cd /Users/alexc/Downloads/Graider
git checkout main && git pull origin main && git checkout -b feature/di-provider-pr1
```

- [ ] **Step 2: RED — provider existence + default-path tests.**

Create `tests/test_providers.py`:

```python
"""Unit tests for backend.providers (the repository/supabase DI seam)."""
from unittest.mock import patch

from tests.test_submission_repository import FakeSupabase


def test_get_supabase_provider_returns_real_client_when_no_override():
    fake = FakeSupabase()
    with patch("backend.supabase_client.get_supabase", return_value=fake):
        from backend.providers import get_supabase_provider
        assert get_supabase_provider() is fake


def test_override_supabase_returns_fake_inside_block_real_after():
    real = FakeSupabase()
    fake = FakeSupabase()
    from backend.providers import get_supabase_provider, override_supabase
    with patch("backend.supabase_client.get_supabase", return_value=real):
        assert get_supabase_provider() is real
        with override_supabase(fake):
            assert get_supabase_provider() is fake
        assert get_supabase_provider() is real


def test_override_resets_even_on_exception():
    real = FakeSupabase()
    fake = FakeSupabase()
    from backend.providers import get_supabase_provider, override_supabase
    with patch("backend.supabase_client.get_supabase", return_value=real):
        try:
            with override_supabase(fake):
                assert get_supabase_provider() is fake
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert get_supabase_provider() is real
```

Run:
```bash
source venv/bin/activate
python -m pytest tests/test_providers.py -v --ignore=tests/load
```
Expected: FAIL (ModuleNotFoundError: backend.providers).

- [ ] **Step 3: GREEN — create the provider module.**

Create `backend/providers.py`:

```python
"""Dependency provider for the repository/supabase seam.

Single resolution point for the supabase client + repository adapters at
the seam abstracted in Tier 2 Slices 4-5. Lets tests swap the database
for a fake at one switch (override_supabase) instead of monkeypatching
get_supabase() per-module.

Wraps, does not replace: backend.supabase_client.get_supabase() stays the
real accessor; this module calls it. Context-independent (plain module
functions) so it works in both Flask-request and Celery-task contexts.
The override is contextvars-backed so it cannot leak across tests or
worker threads.

See docs/superpowers/specs/2026-05-22-di-provider-design.md.
"""
import contextlib
import contextvars
from typing import Any

_supabase_override: contextvars.ContextVar = contextvars.ContextVar(
    "supabase_override", default=None
)


def get_supabase_provider() -> Any:
    """Resolve the supabase client: the test override if one is set in the
    current context, else the real client from supabase_client."""
    override = _supabase_override.get()
    if override is not None:
        return override
    from backend.supabase_client import get_supabase
    return get_supabase()


def get_submission_repository(path_type):
    """Build the SubmissionRepository adapter for path_type using the
    provider-resolved supabase client."""
    from backend.services.submission_repository import repository_for
    return repository_for(path_type, get_supabase_provider())


def get_published_content_repository(path_type):
    """Build the PublishedContentRepository adapter for path_type using the
    provider-resolved supabase client."""
    from backend.services.published_content_repository import (
        published_content_repository_for,
    )
    return published_content_repository_for(path_type, get_supabase_provider())


@contextlib.contextmanager
def override_supabase(fake):
    """Test-only: route get_supabase_provider() to `fake` for the duration
    of the with-block. contextvars-scoped so it cannot leak across tests or
    worker threads; resets on exit (including on exception)."""
    token = _supabase_override.set(fake)
    try:
        yield
    finally:
        _supabase_override.reset(token)
```

Run Step-2 tests:
```bash
python -m pytest tests/test_providers.py -v --ignore=tests/load
```
Expected: 3 PASS.

- [ ] **Step 4: RED — repository-resolution tests.**

Append to `tests/test_providers.py`:

```python
def test_get_submission_repository_returns_joincode_adapter():
    from backend.services.submission_repository import (
        SubmissionPathType, JoinCodeSubmissionRepository,
    )
    from backend.providers import get_submission_repository, override_supabase
    fake = FakeSupabase()
    with override_supabase(fake):
        repo = get_submission_repository(SubmissionPathType.JOIN_CODE)
    assert isinstance(repo, JoinCodeSubmissionRepository)
    assert repo._sb is fake


def test_get_submission_repository_returns_class_adapter():
    from backend.services.submission_repository import (
        SubmissionPathType, ClassSubmissionRepository,
    )
    from backend.providers import get_submission_repository, override_supabase
    fake = FakeSupabase()
    with override_supabase(fake):
        repo = get_submission_repository(SubmissionPathType.CLASS)
    assert isinstance(repo, ClassSubmissionRepository)
    assert repo._sb is fake


def test_get_published_content_repository_returns_correct_adapters():
    from backend.services.submission_repository import SubmissionPathType
    from backend.services.published_content_repository import (
        JoinCodePublishedRepository, ClassPublishedRepository,
    )
    from backend.providers import get_published_content_repository, override_supabase
    fake = FakeSupabase()
    with override_supabase(fake):
        jc = get_published_content_repository(SubmissionPathType.JOIN_CODE)
        cl = get_published_content_repository(SubmissionPathType.CLASS)
    assert isinstance(jc, JoinCodePublishedRepository)
    assert isinstance(cl, ClassPublishedRepository)
```

Run:
```bash
python -m pytest tests/test_providers.py -v --ignore=tests/load
```
Expected: the 3 new tests PASS (the provider already builds repos via the factories, which accept an explicit `sb`). If they fail, fix `get_submission_repository`/`get_published_content_repository`.

- [ ] **Step 5: RED — contextvars isolation test.**

Append to `tests/test_providers.py`:

```python
def test_override_isolated_across_threads():
    """A fake set in one thread's context must not leak into another thread.
    contextvars default-isolates per-thread, so the child thread sees the
    real client, not the parent's override."""
    import threading
    from backend.providers import get_supabase_provider, override_supabase

    real = FakeSupabase()
    parent_fake = FakeSupabase()
    seen = {}

    def child():
        # New thread → fresh context → no override visible.
        seen["child"] = get_supabase_provider()

    with patch("backend.supabase_client.get_supabase", return_value=real):
        with override_supabase(parent_fake):
            assert get_supabase_provider() is parent_fake
            t = threading.Thread(target=child)
            t.start()
            t.join()

    assert seen["child"] is real  # child did NOT see parent's override
```

Run:
```bash
python -m pytest tests/test_providers.py::test_override_isolated_across_threads -v --ignore=tests/load
```
Expected: PASS (contextvars isolates per-thread by default — a new thread starts with the default `None` override).

NOTE: if this test is flaky or the threading semantics differ in the runner, the implementer must investigate the actual contextvars behavior rather than weaken the assertion. The isolation property is the whole safety argument for choosing contextvars over a module-global dict.

- [ ] **Step 6: Full provider-test pass + no-cycle gate.**

```bash
python -m pytest tests/test_providers.py -q --ignore=tests/load
grep -nE "^(from|import) backend\.app" backend/providers.py
ruff check backend/providers.py tests/test_providers.py
```
Expected: all provider tests PASS; the grep for `backend.app` is EMPTY; ruff clean.

- [ ] **Step 7: Commit.**

```bash
git add backend/providers.py tests/test_providers.py
git commit -m "feat(providers): DI provider for the repository/supabase seam + tests (DI PR1)

New backend/providers.py: get_supabase_provider() (contextvars override
or supabase_client.get_supabase()), get_submission_repository(path_type),
get_published_content_repository(path_type), and override_supabase(fake)
contextmanager (contextvars-backed, resets in finally including on
exception). Lets tests swap the database for a fake at one switch instead
of monkeypatching get_supabase() per-module.

Context-independent (plain module functions; works in Flask + Celery).
In-function imports avoid circular import + never import backend.app.

Tests cover: default path, override + reset (incl. on-exception reset),
both submission adapters, both published-content adapters, and
contextvars per-thread isolation (the safety property that justifies
contextvars over a module-global dict).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 1.2: Factory `sb=None` evolution (TDD)

**Files:** Modify `backend/services/submission_repository.py`; Modify `backend/services/published_content_repository.py`; Modify `tests/test_providers.py`

- [ ] **Step 1: RED — optional-arg resolution tests.**

Append to `tests/test_providers.py`:

```python
def test_repository_for_no_sb_resolves_via_provider():
    from backend.services.submission_repository import (
        SubmissionPathType, repository_for, JoinCodeSubmissionRepository,
    )
    from backend.providers import override_supabase
    fake = FakeSupabase()
    with override_supabase(fake):
        repo = repository_for(SubmissionPathType.JOIN_CODE)  # no sb arg
    assert isinstance(repo, JoinCodeSubmissionRepository)
    assert repo._sb is fake


def test_repository_for_explicit_sb_is_unchanged():
    from backend.services.submission_repository import (
        SubmissionPathType, repository_for, JoinCodeSubmissionRepository,
    )
    explicit = FakeSupabase()
    repo = repository_for(SubmissionPathType.JOIN_CODE, explicit)
    assert isinstance(repo, JoinCodeSubmissionRepository)
    assert repo._sb is explicit


def test_published_content_repository_for_no_sb_resolves_via_provider():
    from backend.services.submission_repository import SubmissionPathType
    from backend.services.published_content_repository import (
        published_content_repository_for, ClassPublishedRepository,
    )
    from backend.providers import override_supabase
    fake = FakeSupabase()
    with override_supabase(fake):
        repo = published_content_repository_for(SubmissionPathType.CLASS)
    assert isinstance(repo, ClassPublishedRepository)
    assert repo._sb is fake
```

Run:
```bash
python -m pytest tests/test_providers.py::test_repository_for_no_sb_resolves_via_provider tests/test_providers.py::test_published_content_repository_for_no_sb_resolves_via_provider -v --ignore=tests/load
```
Expected: FAIL (`repository_for() missing 1 required positional argument: 'sb'`).

- [ ] **Step 2: GREEN — evolve `repository_for`.**

In `backend/services/submission_repository.py`, change the `repository_for` signature + add the resolution branch:

```python
def repository_for(path_type, sb=None):
    """Return the adapter for a SubmissionPathType (or its legacy table-name
    string). When sb is None, resolve it from backend.providers (the DI
    seam). Raises ValueError for anything else."""
    if sb is None:
        from backend.providers import get_supabase_provider
        sb = get_supabase_provider()
    if isinstance(path_type, str):
        path_type = SubmissionPathType(path_type)
    if path_type is SubmissionPathType.JOIN_CODE:
        return JoinCodeSubmissionRepository(sb)
    if path_type is SubmissionPathType.CLASS:
        return ClassSubmissionRepository(sb)
    raise ValueError(f"unknown submission path type: {path_type!r}")
```

(Re-derive the exact existing body before editing — keep the `isinstance` coercion + dispatch + ValueError exactly as they are; only add the leading `sb is None` branch and the `=None` default.)

- [ ] **Step 3: GREEN — evolve `published_content_repository_for`.**

In `backend/services/published_content_repository.py`, same change:

```python
def published_content_repository_for(path_type, sb=None) -> PublishedContentRepository:
    """Reconstruct the adapter from the path discriminator. When sb is None,
    resolve it from backend.providers (the DI seam). Accepts the
    SubmissionPathType enum or the legacy table-name string (transitional)."""
    if sb is None:
        from backend.providers import get_supabase_provider
        sb = get_supabase_provider()
    if isinstance(path_type, str):
        path_type = SubmissionPathType(path_type)
    # ... rest unchanged (adapter dispatch + ValueError)
```

(Re-derive the exact existing body; only add the leading `sb is None` branch + `=None` default.)

- [ ] **Step 4: GREEN — run the optional-arg tests.**

```bash
python -m pytest tests/test_providers.py -q --ignore=tests/load
```
Expected: ALL provider tests PASS (including the 3 new optional-arg tests).

- [ ] **Step 5: Regression — the existing repo + char-net suites must stay green.**

```bash
python -m pytest tests/test_submission_repository.py tests/test_published_content_repository.py tests/test_dual_path_consolidation_char.py -q --ignore=tests/load
```
Expected: ALL PASS. The `sb=None` evolution is backward-compatible — every existing caller passes `sb` explicitly, so the new branch never fires for them.

- [ ] **Step 6: Ruff + commit.**

```bash
ruff check backend/services/submission_repository.py backend/services/published_content_repository.py tests/test_providers.py
git add backend/services/submission_repository.py backend/services/published_content_repository.py tests/test_providers.py
git commit -m "feat(repos): repository factories default-resolve sb from the provider (DI PR1)

repository_for(path_type, sb=None) and published_content_repository_for(
path_type, sb=None) now resolve sb from backend.providers.get_supabase_provider()
when omitted (in-function import avoids circular import). Backward-
compatible: every existing caller passes sb explicitly, so the new
sb-is-None branch never fires for them. The existing repo + char-net
suites stay green.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 1.3: Open PR1

- [ ] **Step 1: Push + open PR.**

```bash
git push -u origin feature/di-provider-pr1
gh pr create --base main --head feature/di-provider-pr1 \
  --title "feat(providers): DI provider for the repository/supabase seam (additive) (DI PR1)" \
  --body "$(cat <<'BODY'
## Summary

DI PR1 — purely additive. Creates the dependency provider and evolves the repo factories to default-resolve from it. No production call site changes; behavior change impossible by construction.

## Files
- \`backend/providers.py\` (new) — get_supabase_provider(), get_submission_repository(path_type), get_published_content_repository(path_type), override_supabase(fake) [contextvars-backed].
- \`tests/test_providers.py\` (new) — default path, override + reset (incl. on-exception), both adapters x2, optional-arg resolution, back-compat explicit-arg, contextvars per-thread isolation.
- \`backend/services/submission_repository.py\` — repository_for(path_type, sb=None).
- \`backend/services/published_content_repository.py\` — published_content_repository_for(path_type, sb=None).

## Why
Tests can now swap the database for a fake at one \`override_supabase(fake)\` switch instead of monkeypatching get_supabase() per-module. Closes the 3rd Architecture-7 ground (no DI) at the repository seam. Hand-rolled provider (3-model reconciled) — zero new dependencies, works in Flask + Celery.

## Verification
- \`node\`-free: \`python -m pytest tests/test_providers.py -q --ignore=tests/load\` all green.
- Backward-compat: existing repo + char-net suites green (every existing caller passes sb explicitly).
- No-cycle gate: providers.py never imports backend.app.

## Out of scope (PR2 + follow-up)
Production call-site migration (PR2). Dual-use sites + submit_student_work raise-vs-None semantics (follow-up). The ~80 other get_supabase() sites + AI clients + config (follow-up slices).

## Plan + spec
- Plan: \`docs/superpowers/plans/2026-05-22-di-provider.md\`
- Spec: \`docs/superpowers/specs/2026-05-22-di-provider-design.md\`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
BODY
)"
gh pr merge --squash --auto
```

- [ ] **Step 2: Watch merge; on merge, clean up local branch.**

Background-poll until merged, capture sha, then:
```bash
git checkout main && git pull origin main && git branch -D feature/di-provider-pr1
```

---

## PR 2: rewire (migrate clean seams + update call-count assertions + ergonomics proof)

### Task 2.1: Branch + migrate `grading_tasks.py` failure seams (lockstep with char-net update)

**Files:** Modify `backend/tasks/grading_tasks.py`; Modify `tests/test_dual_path_consolidation_char.py`

- [ ] **Step 1: Branch.**

```bash
git checkout main && git pull origin main && git checkout -b feature/di-provider-pr2
```

- [ ] **Step 2: Read the two failure seams + the char-net tests.**

```bash
sed -n '40,70p' backend/tasks/grading_tasks.py     # on_failure
sed -n '175,195p' backend/tasks/grading_tasks.py   # no-assessment failure branch
grep -nA 20 "def test_on_failure_skips_update_when_sb_none\|def test_on_failure_noop_without_submission_id" tests/test_dual_path_consolidation_char.py
```

Confirm `on_failure` currently does:
```python
sb = get_supabase()
if sb:
    repository_for(supabase_table, sb).mark_failed(submission_id, exc)
```
and the no-assessment branch does the analogous `sb = get_supabase(); if sb: repository_for(path_type, sb).mark_failed(submission_id, "Assessment content unavailable at grading time")`.

- [ ] **Step 3: Migrate `on_failure`.**

Replace the `sb = get_supabase(); if sb: repository_for(...)...` block with a provider call. The repo's internal `if not self._sb` guard preserves the no-write-when-None behavior:

```python
from backend.providers import get_submission_repository
get_submission_repository(supabase_table).mark_failed(submission_id, exc)
```

Remove the now-unneeded `from backend.supabase_client import get_supabase` + `sb = get_supabase()` + `if sb:` lines IN THIS BLOCK ONLY (leave the `from backend.services.submission_repository import repository_for` import removal too if it's now unused in that block — verify it's not used elsewhere in the function). Keep the outer `try/except Exception: pass` and the `if not submission_id: return` guard exactly as they are.

- [ ] **Step 4: Migrate the no-assessment failure branch (~line 183).**

Same transform:
```python
from backend.providers import get_submission_repository
get_submission_repository(path_type).mark_failed(
    submission_id, 'Assessment content unavailable at grading time'
)
```
Keep the outer `try/except Exception: pass` and the `if sb:`→(removed) reasoning: the repo's internal guard handles the None-client case.

- [ ] **Step 5: Update the char-net call-count assertions (lockstep).**

In `tests/test_dual_path_consolidation_char.py`, `TestFailureSeam`:

`test_on_failure_skips_update_when_sb_none` — currently patches `repository_for` and asserts `assert_not_called()` when `get_supabase` returns None. The observable contract is "no DB write when the client is None." Rewrite to assert the observable effect: patch `get_supabase` to return None (or a `FakeSupabase` whose `.table(...).update(...)` records calls), invoke `on_failure`, and assert NO update/write was issued. Concretely:

```python
def test_on_failure_no_write_when_sb_none(self):
    """When the resolved client is None, on_failure must not write. The
    repo's internal guard no-ops; observable contract = no DB write."""
    from backend.tasks.grading_tasks import PortalGradingTask
    from backend.providers import override_supabase
    task = PortalGradingTask()
    task.name = "grading.portal_submission"
    # No client available: provider resolves to None via the override hook.
    with override_supabase(None), patch(
        "backend.supabase_client.get_supabase", return_value=None
    ):
        task.on_failure(
            exc=RuntimeError("q"), task_id="t",
            args=["sub-9", "teacher-1", JOIN_CODE_TABLE], kwargs={}, einfo=None,
        )
    # No exception escaped, no write attempted (None client → repo no-ops).
```

NOTE: `override_supabase(None)` sets the contextvar to `None`, which the provider treats as "no override" (it then calls `get_supabase`, patched to None). To force a None client cleanly, rely on the `patch("backend.supabase_client.get_supabase", return_value=None)` alone (don't use `override_supabase(None)` since None means "no override"). Use a recording fake if you need to assert "update never called": set the override to a `FakeSupabase` and assert its `.table().update` was never invoked. Pick whichever cleanly proves no-write; the implementer decides at TDD time and documents the choice.

`test_on_failure_noop_without_submission_id` — this one asserts no work when `submission_id` is absent (args=[]). The `if not submission_id: return` guard is UNCHANGED by the migration (it runs before any repo call). This test can keep asserting the early return, but if it patches `repository_for` and asserts `assert_not_called()`, update it to assert the observable no-write the same way, OR confirm the early-return guard still makes `get_submission_repository` never reached (patch `backend.providers.get_submission_repository` and assert not called — the guard returns before it).

- [ ] **Step 6: Run the failure-seam tests + char net.**

```bash
source venv/bin/activate
python -m pytest tests/test_grading_tasks.py tests/test_dual_path_consolidation_char.py -v --ignore=tests/load 2>&1 | tail -30
```
Expected: ALL PASS. `TestRouteContractSeam` (9 tests) byte-identical green. The updated `TestFailureSeam` tests green with observable-effect assertions.

- [ ] **Step 7: Ruff + commit.**

```bash
ruff check backend/tasks/grading_tasks.py tests/test_dual_path_consolidation_char.py
git add backend/tasks/grading_tasks.py tests/test_dual_path_consolidation_char.py
git commit -m "refactor(tasks): grading_tasks failure seams use the DI provider (DI PR2)

on_failure and the no-assessment failure branch now call
get_submission_repository(path_type).mark_failed(...) instead of
sb = get_supabase(); if sb: repository_for(path_type, sb).mark_failed(...).
The repo's internal if-not-self._sb guard preserves the no-write-when-None
behavior (observable DB effect identical).

Lockstep char-net update: the ~2 TestFailureSeam tests that asserted
repository_for was NOT called when the client is None now assert the
observable contract (no DB write when client is None) instead of the
call-count. That assertion was pinning an implementation detail; the
observable behavior is unchanged. TestRouteContractSeam stays
byte-identical.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 2.2: Migrate `portal_grading.py` inline update + ergonomics-proof test

**Files:** Modify `backend/services/portal_grading.py`; Modify one existing seam test (`tests/test_grading_tasks.py` or `tests/test_dual_path_consolidation_char.py`)

- [ ] **Step 1: Read the inline-update site.**

```bash
sed -n '940,955p' backend/services/portal_grading.py
```
Confirm it's `sb = get_supabase(); if sb and submission_id: repository_for(path_type, sb).update(submission_id, {"status": "grading_deferred"})`.

- [ ] **Step 2: Migrate it.**

```python
if submission_id:
    from backend.providers import get_submission_repository
    get_submission_repository(path_type).update(
        submission_id, {"status": "grading_deferred"}
    )
```
The `if sb and submission_id:` becomes `if submission_id:` — the repo's internal guard handles the None client. Keep the surrounding `try/except` exactly.

- [ ] **Step 3: Check whether any test pins this branch's call-count.**

```bash
grep -rn "grading_deferred" tests/ --include="*.py"
```
If a test asserts `repository_for` call-count on the deferred-update branch when sb is None, update it to the observable-effect assertion (same pattern as Task 2.1 Step 5). If no test pins it, no test change needed.

- [ ] **Step 4: Ergonomics-proof — rewrite one existing seam test to use `override_supabase`.**

Pick an existing test that currently multi-patches `get_supabase` across modules for a grading-failure scenario (search `tests/test_grading_tasks.py` for a test that patches `backend.supabase_client.get_supabase` AND asserts a repo write). Rewrite it to use `override_supabase(fake)` once:

```python
def test_on_failure_writes_failed_via_override(self):
    """Ergonomics proof: a single override_supabase(fake) swaps the DB for
    the whole failure path — no per-module get_supabase patching."""
    from backend.tasks.grading_tasks import PortalGradingTask
    from backend.providers import override_supabase
    from tests.test_submission_repository import FakeSupabase
    fake = FakeSupabase()
    fake.table("submissions")  # materialize
    task = PortalGradingTask()
    task.name = "grading.portal_submission"
    with override_supabase(fake):
        task.on_failure(
            exc=RuntimeError("boom"), task_id="t",
            args=["sub-1", "teacher-1", "submissions"], kwargs={}, einfo=None,
        )
    # Assert the fake recorded a failed-status update on the submissions table.
    # (Use the FakeSupabase recording mechanism; verify the update payload
    #  has status=='failed' and error_message contains 'boom'.)
```

The implementer adapts the assertion to the actual `FakeSupabase` recording API (inspect `tests/test_submission_repository.py` for how writes are captured). The point: ONE `override_supabase(fake)` replaces what used to be 1-3 `patch(...get_supabase...)` calls. Document the before/after patch count in the commit message.

- [ ] **Step 5: Run + ruff.**

```bash
python -m pytest tests/test_grading_tasks.py tests/test_dual_path_consolidation_char.py tests/test_grade_portal_submission_sync.py -q --ignore=tests/load
ruff check backend/services/portal_grading.py
```
Expected: all green.

- [ ] **Step 6: Commit.**

```bash
git add backend/services/portal_grading.py tests/test_grading_tasks.py
git commit -m "refactor(portal): run_portal_grading_thread deferred-update uses the DI provider + ergonomics-proof test (DI PR2)

The inline grading_deferred update in run_portal_grading_thread now uses
get_submission_repository(path_type).update(...) (repo's internal guard
handles the None client). Plus the ergonomics proof: one on_failure test
rewritten from multi-module get_supabase patching to a single
override_supabase(fake) switch — demonstrating the testability win the
provider was built for.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 2.3: Full regression + open PR2

- [ ] **Step 1: Full regression.**

```bash
source venv/bin/activate
python -m pytest tests/ -q --ignore=tests/load 2>&1 | tail -8
```
Expected: 0 failed (tolerating the known `test_anthropic_chat_uses_breaker` / `test_gemini_chat_uses_breaker` network flakes that pass in isolation — if either fails, re-run it alone to confirm it's the flake: `python -m pytest tests/test_llm_adapter_anthropic.py::test_anthropic_chat_uses_breaker -v --ignore=tests/load`). Report the pass count.

- [ ] **Step 2: Push + open PR2.**

```bash
git push -u origin feature/di-provider-pr2
gh pr create --base main --head feature/di-provider-pr2 \
  --title "refactor: grading/task failure seams use the DI provider (DI PR2)" \
  --body "$(cat <<'BODY'
## Summary

DI PR2 — routes the genuinely-clean repo-only grading/task failure seams through the provider, updates the ~2-3 char-net call-count assertions to observable-effect assertions, and rewrites one seam test to use override_supabase as the ergonomics proof.

## Migrated (repo-only, get_supabase-based seams)
- \`grading_tasks.py\` on_failure + no-assessment failure branch → get_submission_repository(path_type).mark_failed(...)
- \`portal_grading.py\` run_portal_grading_thread deferred-update → get_submission_repository(path_type).update(...)

## Char-net update (behavior-preserving)
The ~2-3 TestFailureSeam tests that asserted repository_for was NOT called when the client is None now assert the observable contract (no DB write when client is None). The repo's internal if-not-self._sb guard makes the observable DB effect identical; only the call-count assertion (an implementation detail) changed. TestRouteContractSeam (the HTTP contract net) stays 100% byte-identical.

## Ergonomics proof
One on_failure test rewritten from multi-module get_supabase patching to a single override_supabase(fake) — the testability win the provider was built for.

## Deferred (follow-up, documented in spec section 6.3)
- Dual-use sites (sb used for both repo + direct db.table queries): fetch_submission_full_context, submit_assessment.
- submit_student_work (get_supabase_or_raise raise-vs-None semantics).
- The ~80 other get_supabase() sites, AI clients, config.

## Verification
Full regression 0 failed (modulo the known breaker network flakes that pass in isolation). Ruff clean.

## Plan + spec
- Plan: \`docs/superpowers/plans/2026-05-22-di-provider.md\`
- Spec: \`docs/superpowers/specs/2026-05-22-di-provider-design.md\`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
BODY
)"
gh pr merge --squash --auto
```

- [ ] **Step 3: Watch merge; clean up local branch.**

---

## Task 3: Slice closeout

**Files:** Modify `docs/superpowers/specs/2026-05-22-di-provider-design.md`, `docs/superpowers/plans/2026-05-22-di-provider.md`, `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`

- [ ] **Step 1: Branch.**

```bash
git checkout main && git pull origin main && git checkout -b docs/di-provider-closeout
```

- [ ] **Step 2: STATUS-stamp the spec.** In `docs/superpowers/specs/2026-05-22-di-provider-design.md`, change `**Status:** OPEN` to:
```
**Status:** CLOSED 2026-05-2X — shipped via PR1 (#XXX: provider + factory evolution) and PR2 (#YYY: grading/task failure-seam migration + char-net call-count→observable-effect update + ergonomics-proof test). Dual-use + raise-semantics sites deferred to follow-up.
```

- [ ] **Step 3: STATUS-stamp the plan.** Add after `**Goal:**`:
```
**STATUS: CLOSED 2026-05-2X** — shipped via PR1 (#XXX) and PR2 (#YYY). DI provider live at the repository/supabase seam; grading/task failure seams route through it; tests swap the DB via override_supabase(fake). 3rd Architecture-7 ground addressed at the seam (broader conversion is follow-up slices).
```

- [ ] **Step 4: Append dated section** to `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md`:

```markdown

---

# 2026-05-2X DI provider closeout (PR #XXX + PR #YYY)

The third Architecture-7 ground (no dependency injection) addressed at the repository/supabase seam. Brainstormed via superpowers:brainstorming with 3-model consultation on the mechanism (Claude + Codex reconciled on a hand-rolled provider; Gemini leaned toward a DI library but failed to engage the Flask+Celery dual-context constraint — weak signal). Executed subagent-driven with two-stage review.

## What shipped
- `backend/providers.py` (PR1 #XXX) — get_supabase_provider(), get_submission_repository(path_type), get_published_content_repository(path_type), override_supabase(fake) [contextvars-backed].
- `repository_for(path_type, sb=None)` + `published_content_repository_for(path_type, sb=None)` (PR1 #XXX) — default-resolve from the provider; backward-compatible.
- Grading/task failure seams (PR2 #YYY) — on_failure, the no-assessment branch, and run_portal_grading_thread's deferred-update route through get_submission_repository(path_type); the repo's internal None-client guard preserves the observable no-write-when-None behavior.
- Char-net update (PR2 #YYY) — the ~2-3 TestFailureSeam call-count assertions became observable-effect assertions (no DB write when client None); TestRouteContractSeam stayed byte-identical.
- Ergonomics proof (PR2 #YYY) — one seam test rewritten from multi-module get_supabase patching to a single override_supabase(fake).

## Planning-time scope refinement (recorded honestly)
A code audit during planning found the call-site migration is narrower than the spec first assumed: the char net pins call-count at the if-sb guards; submit_student_work uses get_supabase_or_raise (raise-vs-None vs the provider's get_supabase); several sites use sb for both repo construction and direct db.table queries. The clean repo-only get_supabase-based seams migrated; the dual-use and raise-semantics sites are deferred to follow-up rather than force-migrated.

## Out of scope (follow-up slices)
The ~80 other get_supabase() sites, the 6 duplicate _get_supabase() defs, AI/LLM clients, config loading, and the dual-use + raise-semantics seams above.

## Next step
Post-slice 3-model reconciled re-score weighing whether Architecture moves 8 → 9. Honest framing: this is lightweight provider-based DI live at one seam (the grading/task failure path), genuinely used in production, with the testability win demonstrated — but NOT a framework across the codebase, and the dual-use/raise-semantics seams + the ~80 other call sites still acquire deps directly. The re-score decides whether seam-level DI + the clean infrastructure clears the bar, or whether the broader conversion follow-up is needed first.
```

Replace `XX`/`XXX`/`YYY` with actual dates + PR numbers from main's history.

- [ ] **Step 5: Commit + push + open closeout PR + auto-merge.**

```bash
git add docs/superpowers/specs/2026-05-22-di-provider-design.md docs/superpowers/plans/2026-05-22-di-provider.md docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md
git commit -m "docs: close DI provider slice (PR1 + PR2); 3-model re-score follows

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push -u origin docs/di-provider-closeout
gh pr create --base main --head docs/di-provider-closeout --title "docs: close DI provider slice (STATUS + dated section)" --body "Slice closeout for the DI provider. STATUS-CLOSED stamps on spec + plan; dated section in the assessment doc recording what shipped, the planning-time scope refinement, what's deferred, and the re-score framing.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr merge --squash --auto
```

---

## Task 4: Post-slice 3-model reconciled re-score (optional, controller judgment)

Run by the controller after Task 3 merges, only if the controller judges the Architecture 8 → 9 question worth the model time. Honest framing required: provider-based DI is live at ONE seam (grading/task failure), genuinely used in production, testability win demonstrated — but it is not a framework across the codebase and most call sites still acquire deps directly. A conservative-floor reconcile will likely weigh whether seam-level DI clears the bar or whether the broader conversion is a prerequisite.

- [ ] Dispatch Claude (Agent general-purpose opus) + Codex (Agent codex:codex-rescue) + Gemini (gemini CLI) with the same re-score prompt against the post-DI-slice state vs the 2026-05-21 Post-Slice-5 baseline. Reconcile conservative-floor (failed-to-run ≠ failed-low). Append a dated section.

---

## Self-Review

**1. Spec coverage:**

| Spec section | Plan task |
|---|---|
| §1 Goal / §2 Motivation | Plan goal + Task 1.1 (provider) + Task 2.x (production use) |
| §3 Mechanism (hand-rolled provider) | Task 1.1 |
| §4 Scope (repo/supabase seam, one slice) | PR1 + PR2 structure |
| §5 Architecture (providers.py shape) | Task 1.1 Step 3 |
| §6.1 providers.py | Task 1.1 |
| §6.2 factory evolution | Task 1.2 |
| §6.3 refined call-site migration | Task 2.1 (grading_tasks) + Task 2.2 (portal_grading); deferrals documented |
| §7 sequencing 2 PRs | PR1 (1.1-1.3), PR2 (2.1-2.3) |
| §8 testing | Task 1.1 (provider tests), Task 2.1 (char-net update), Task 2.2 (ergonomics proof), Task 2.3 (full regression) |
| §9 error handling | provider's override-reset-in-finally (Task 1.1), repo internal None-guard (Task 2.x), circular-import avoidance (Task 1.1/1.2 in-function imports) |
| §10 success criteria | Task 2.3 + Task 3 closeout + Task 4 re-score |
| §11 risks | contextvars isolation test (Task 1.1 Step 5), in-function imports, char-net-first, scope-creep guard via the deferral list |

**2. Placeholder scan:** The closeout (Task 3) uses `XX`/`XXX`/`YYY` for not-yet-known dates and PR numbers — these are explicitly "fill from main's history at closeout time," the standard closeout pattern, not unfilled implementation placeholders. Task 2.1 Step 5 leaves the implementer a documented choice between two valid no-write-assertion mechanisms (None client vs recording fake) — this is a genuine TDD-time decision, with both options spelled out, not a vague "handle it." All code steps have complete code blocks.

**3. Type consistency:** `get_supabase_provider()`, `get_submission_repository(path_type)`, `get_published_content_repository(path_type)`, `override_supabase(fake)` used consistently across Task 1.1 (definition), Task 1.2 (factory resolution), Task 2.x (production calls + tests). `repository_for(path_type, sb=None)` / `published_content_repository_for(path_type, sb=None)` signatures consistent. `_supabase_override` contextvar + `_sb` repo attribute consistent. `SubmissionPathType.JOIN_CODE`/`.CLASS` used consistently.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-22-di-provider.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Controller dispatches a fresh subagent per task, two-stage review (spec-compliance then code-quality), continuous. Matches every Slice 4/5/6 task.

**2. Inline Execution** — Execute in this session using `superpowers:executing-plans`, batched with checkpoints.

Which approach?
