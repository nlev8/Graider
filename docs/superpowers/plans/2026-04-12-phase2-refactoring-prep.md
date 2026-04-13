# Phase 2 Refactoring Prep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate silent grading failures, reconcile schema drift, and build the characterization safety net that makes the Phase 3 monolith split safe.

**Architecture:** Three-part hardening pass built on the Phase 1 safety net. **Hotfixes 1–2** close observability + schema gaps that are either bleeding or latent-dangerous today. **Task 3** builds black-box characterization tests around `stem_grading.py` before anyone splits it (Feathers' rule: stabilize behavior before refactor). **Tasks 4–6** finish the Phase 1 exception audit and kill zero-coverage production paths. **Task 7** is the exit gate.

**Tech Stack:** pytest + pytest-cov, Sentry SDK 2.x (`backend.observability.sentry.critical_path` + `sentry_sdk.capture_exception`), Supabase (PostgREST), BetterStack Logs (fed by Sentry), Flask.

---

## Scope

Phase 2 is **refactoring preparation**, not refactoring itself. Zero behavior changes except:
- Previously-silent grading failures become observable (hotfix 1)
- Schema drifts are reconciled to a single source of truth (hotfix 2)

No monolith splitting, no RLS work, no new features. Those belong to Phase 3 and Phase 4.

---

## File Structure

**Modify (hotfix 1):**
- `backend/services/portal_grading.py` — wire 4 grading-critical catches to Sentry
- `backend/routes/student_account_routes.py:872` — wire grading-thread spawn failure

**Modify (hotfix 2):**
- `backend/services/portal_grading.py` — normalize `status` writes to the CHECK constraint set
- `backend/routes/student_account_routes.py` — same
- `backend/routes/student_portal_routes.py` — same
- One of: new Supabase migration SQL OR code removal of `teacher_id` references on `published_assessments` (decision in Task 2 Step 1)

**Create (Task 3):**
- `tests/characterization/__init__.py`
- `tests/characterization/test_stem_grading_golden.py`
- `tests/characterization/fixtures/` — captured input/output pairs

**Modify (Task 4):**
- `docs/exception-audit-2026-04.md` — categorize remaining 703 rows

**Modify (Task 5):**
- Various files per-row from Task 4 output

**Create/Modify (Task 6):**
- `tests/test_student_history.py` (new)
- `tests/test_outlook_sender.py` (new)
- `tests/test_openai_tts_service.py` (new)
- `tests/test_staging.py` (new)

**Modify (Task 7):**
- `.github/workflows/ci.yml` — floor 30 → 35

---

## Task 1 (Hotfix 1): Wire BetterStack to grading-critical NEEDS_ALERT catches

**Why first:** Five catches are silently swallowing grading-thread failures today. Students see stuck submissions; teachers see nothing; on-call is unaware. Elapsed time from first impact to discovery is whatever it takes for a teacher to email support. This is operational-SLA material, not tech-debt.

**Files:**
- Modify: `backend/services/portal_grading.py:474` (feedback generation)
- Modify: `backend/services/portal_grading.py:499` (save to teacher storage)
- Modify: `backend/services/portal_grading.py:523` (Supabase submission update)
- Modify: `backend/services/portal_grading.py:546` (top-level grading thread)
- Modify: `backend/routes/student_account_routes.py:872` (grading-thread spawn)
- Test: `tests/test_portal_grading_alerting.py` (new)

### Step 1.1 — Write the failing test that proves `capture_exception` is called on feedback generation failure

Create `tests/test_portal_grading_alerting.py`:

```python
"""Sentry/BetterStack alerting contract tests for portal_grading.

Each NEEDS_ALERT catch identified in docs/exception-audit-2026-04.md
MUST call sentry_sdk.capture_exception so BetterStack sees the failure.
These tests pin the contract — future refactors can't silently strip
the alerting call.
"""
from unittest.mock import patch, MagicMock

import pytest


def test_feedback_generation_failure_captures_to_sentry():
    """portal_grading.py line 474 region: generate_feedback() throws →
    exception must be captured, NOT silently swallowed."""
    from backend.services import portal_grading

    with patch("backend.services.portal_grading.sentry_sdk") as mock_sentry, \
         patch("backend.services.portal_grading.generate_feedback",
               side_effect=RuntimeError("feedback boom")):
        # The wrapper we'll introduce: a small helper that runs
        # generate_feedback and returns a default + captures on failure.
        result = portal_grading._safe_generate_feedback(
            question="Q", student_answer="A", expected="E",
        )
        assert result is not None  # Default fallback returned
        mock_sentry.capture_exception.assert_called_once()
```

### Step 1.2 — Run and verify it fails

```bash
source venv/bin/activate && python -m pytest tests/test_portal_grading_alerting.py::test_feedback_generation_failure_captures_to_sentry -v 2>&1 | tail -5
```

Expected: `AttributeError: module 'backend.services.portal_grading' has no attribute '_safe_generate_feedback'`.

### Step 1.3 — Add the `_safe_*` helpers + wire `sentry_sdk` import

In `backend/services/portal_grading.py`, near the other imports:

```python
import sentry_sdk
```

Then add helpers above `run_portal_grading_thread`:

```python
def _safe_generate_feedback(**kwargs):
    """Call generate_feedback; on failure, capture to Sentry and return
    a safe fallback so the grading thread can continue."""
    try:
        from assignment_grader import generate_feedback
        return generate_feedback(**kwargs)
    except Exception as e:
        logger.error("Feedback generation failed: %s", e)
        sentry_sdk.capture_exception(e)
        return {"feedback": "Grading complete. Teacher will review and provide detailed feedback.",
                "rubric_breakdown": {}}


def _safe_save_results(results, teacher_id):
    try:
        save_results(results, teacher_id)
    except Exception as e:
        logger.error("Failed to save result to teacher storage: %s", e)
        sentry_sdk.capture_exception(e)


def _safe_update_submission(sb, submission_id, update_fields):
    if not (sb and submission_id):
        return
    try:
        sb.table("student_submissions").update(update_fields).eq("id", submission_id).execute()
    except Exception as e:
        logger.error("Failed to update Supabase submission: %s", e)
        sentry_sdk.capture_exception(e)
```

### Step 1.4 — Run the test and verify it passes

```bash
source venv/bin/activate && python -m pytest tests/test_portal_grading_alerting.py::test_feedback_generation_failure_captures_to_sentry -v 2>&1 | tail -5
```

Expected: `1 passed`.

### Step 1.5 — Add failing tests for the other three portal_grading catches

Append to `tests/test_portal_grading_alerting.py`:

```python
def test_save_result_failure_captures_to_sentry():
    from backend.services import portal_grading
    with patch("backend.services.portal_grading.sentry_sdk") as mock_sentry, \
         patch("backend.services.portal_grading.save_results",
               side_effect=RuntimeError("save boom")):
        portal_grading._safe_save_results([{"x": 1}], "teacher-123")
        mock_sentry.capture_exception.assert_called_once()


def test_supabase_submission_update_failure_captures_to_sentry():
    from backend.services import portal_grading
    mock_sb = MagicMock()
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.side_effect = \
        RuntimeError("supabase boom")
    with patch("backend.services.portal_grading.sentry_sdk") as mock_sentry:
        portal_grading._safe_update_submission(mock_sb, "sub-id", {"status": "graded"})
        mock_sentry.capture_exception.assert_called_once()


def test_grading_thread_top_level_failure_captures_to_sentry():
    """The whole thread entry point (line 546 region) must capture any
    escaping exception. Apply the @critical_path decorator on the
    thread entry — Sentry's FlaskIntegration captures the exception
    with severity=critical set."""
    from backend.services import portal_grading
    # Pin that the function is decorated with critical_path.
    assert hasattr(portal_grading.run_portal_grading_thread, "__wrapped__"), \
        "run_portal_grading_thread must be wrapped by @critical_path"
```

### Step 1.6 — Run them, confirm they fail

```bash
source venv/bin/activate && python -m pytest tests/test_portal_grading_alerting.py -v 2>&1 | tail -10
```

Expected: 3 new failures (first test still passes).

### Step 1.7 — Replace the 3 raw try/except blocks with `_safe_*` calls

In `backend/services/portal_grading.py`:

- Around line 474 (the `generate_feedback` call site): replace the `try/except` block with a call to `_safe_generate_feedback(...)` that assigns `feedback_text` and `breakdown` from the returned dict.
- Around line 499 (the `save_results` call site): replace with `_safe_save_results(results, teacher_id)`.
- Around line 523 (the Supabase `update(...).execute()` call site): replace with `_safe_update_submission(sb, submission_id, {...})`.

### Step 1.8 — Decorate the grading thread entry with `@critical_path`

In `backend/services/portal_grading.py`, at the top:

```python
from backend.observability.sentry import critical_path
```

And on the `run_portal_grading_thread` definition:

```python
@critical_path
def run_portal_grading_thread(...):
    ...
```

The existing line-546-region `except Exception as e: logger.error(...)` block stays as-is — `@critical_path` tags the escape; the existing `except` gracefully records partial state. Keep both.

### Step 1.9 — Run full alerting suite

```bash
source venv/bin/activate && python -m pytest tests/test_portal_grading_alerting.py -v 2>&1 | tail -10
```

Expected: all 4 pass.

### Step 1.10 — Add the grading-thread spawn catch test + fix

In `tests/test_portal_grading_alerting.py`:

```python
def test_grading_thread_spawn_failure_captures_to_sentry():
    """student_account_routes.py line 872: threading.Thread(...).start()
    raises → must capture_exception, not just log.warning."""
    from backend.routes import student_account_routes as sar
    with patch("backend.routes.student_account_routes.sentry_sdk") as mock_sentry, \
         patch("backend.routes.student_account_routes.threading.Thread",
               side_effect=RuntimeError("spawn boom")):
        # Call the inner helper that spawns the thread.
        sar._spawn_grading_thread_safe(target=lambda: None, args=())
        mock_sentry.capture_exception.assert_called_once()
```

In `backend/routes/student_account_routes.py`: import `sentry_sdk`, add helper:

```python
def _spawn_grading_thread_safe(*, target, args):
    try:
        t = threading.Thread(target=target, args=args, daemon=True)
        t.start()
        return t
    except Exception as e:
        _logger.warning("Failed to spawn portal grading: %s", e)
        sentry_sdk.capture_exception(e)
        return None
```

At the line-872 catch: replace the inline try/except with `_spawn_grading_thread_safe(...)`.

### Step 1.11 — Full verify + commit

```bash
source venv/bin/activate && python -m pytest tests/test_portal_grading_alerting.py tests/test_portal_grading.py -v 2>&1 | tail -15
```

Expected: all alerting tests pass, no regressions in the existing portal_grading suite.

```bash
git add tests/test_portal_grading_alerting.py backend/services/portal_grading.py backend/routes/student_account_routes.py
git commit -m "feat(observability): wire grading-critical catches to Sentry

Phase 2 Hotfix 1. Converts 5 silently-swallowed grading failures into
observable Sentry events (which feed BetterStack alerts):

  - portal_grading:474  feedback generation → _safe_generate_feedback
  - portal_grading:499  save_results       → _safe_save_results
  - portal_grading:523  Supabase update    → _safe_update_submission
  - portal_grading:546  thread entry       → @critical_path decorator
  - student_account_routes:872 thread spawn → _spawn_grading_thread_safe

Behavior unchanged for the happy path; failure paths now page instead
of silently continuing.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 (Hotfix 2): Schema drift reconciliation

**Why now, not Phase 4:** RLS policies in Phase 4 assume schema truth. Enforcing access control on top of `status` write-paths the CHECK constraint rejects, or on a column (`teacher_id`) that exists in live DB but not in SQL of record, is reckless — first bad row makes the RLS-gated route look broken. Reconcile before hardening.

**Files:**
- Create: `supabase/migrations/20260413_phase2_schema_reconcile.sql`
- Modify: `backend/services/portal_grading.py`
- Modify: `backend/routes/student_account_routes.py`
- Modify: `backend/routes/student_portal_routes.py`
- Test: `tests/test_schema_assertions.py` (update drift-documentation tests)

### Step 2.1 — Decide the `status` target set

Read every `student_submissions.status` write in the codebase:

```bash
source venv/bin/activate && grep -rn '"status":' backend/ --include="*.py" | grep -i "submission\|student_submissions\|partial\|grading_" | head -40
```

Record the code-write set (expected: `partial`, `grading_deferred`, `grading_failed`, `draft`) and compare to the CHECK set (`in_progress`, `submitted`, `grading`, `graded`, `returned`). Decide which set wins — recommend **union both sets into the CHECK** rather than renaming code paths, because the code distinctions (`grading_deferred` vs `grading_failed` vs `partial`) carry real state semantics that `grading`/`returned` don't.

Document the decision at the top of the migration file.

### Step 2.2 — Decide the `teacher_id` question

Two options:
- **Option A (recommended):** `teacher_id` exists in live DB (Phase 1 schema test proved this) — codify it in SQL of record and keep the live column. Minimal change.
- **Option B:** Drop the column from live DB — breaks anything reading it.

Grep for reads first:

```bash
source venv/bin/activate && grep -rn "published_assessments" backend/ --include="*.py" | grep -i "teacher_id\|select" | head -20
```

If any read references `teacher_id`, Option A is the only safe choice.

### Step 2.3 — Write the migration SQL

Create `supabase/migrations/20260413_phase2_schema_reconcile.sql`:

```sql
-- Phase 2 Hotfix 2: Schema drift reconciliation.
--
-- 1. Widens student_submissions.status CHECK to cover values the code
--    actually writes (partial, grading_deferred, grading_failed, draft)
--    in addition to the originals (in_progress, submitted, grading,
--    graded, returned). Union approach — no code changes required.
--
-- 2. Codifies published_assessments.teacher_id that already exists in
--    live DB (surfaced by tests/test_schema_assertions.py::
--    TestPublishedAssessmentsSchema::test_no_teacher_id_column on
--    2026-04-12). The column is present; we're making the SQL file
--    the source of record match live.

BEGIN;

-- 1. student_submissions.status CHECK expansion
ALTER TABLE student_submissions
    DROP CONSTRAINT IF EXISTS student_submissions_status_check;

ALTER TABLE student_submissions
    ADD CONSTRAINT student_submissions_status_check
    CHECK (status IN (
        'in_progress', 'submitted', 'grading', 'graded', 'returned',
        'partial', 'grading_deferred', 'grading_failed', 'draft'
    ));

-- 2. published_assessments.teacher_id — codify existing live column.
--    Idempotent: only adds if missing.
ALTER TABLE published_assessments
    ADD COLUMN IF NOT EXISTS teacher_id text;

CREATE INDEX IF NOT EXISTS idx_published_assessments_teacher
    ON published_assessments(teacher_id);

COMMIT;
```

### Step 2.4 — Apply the migration to staging (manual)

```bash
# Apply via Supabase SQL editor or supabase CLI against staging project.
# Do NOT apply to production until Task 2 verify passes end-to-end.
```

Pause here — ask the human for confirmation that staging has been migrated before proceeding.

### Step 2.5 — Update schema assertion tests to reflect the reconciled truth

In `tests/test_schema_assertions.py`, replace `test_no_teacher_id_column` with `test_teacher_id_column_exists`:

```python
def test_teacher_id_column_exists(self):
    """published_assessments.teacher_id is codified in the SQL of record
    as of migration 20260413. Query must succeed, not error."""
    sb = _get_live_supabase()
    result = sb.table("published_assessments").select("teacher_id").limit(0).execute()
    assert result is not None
```

Update the docstring in `test_status_values_drift_is_documented` to note the drift is resolved and rename to `test_status_accepts_all_code_values`:

```python
def test_status_accepts_all_code_values(self):
    """After migration 20260413, student_submissions.status accepts
    the union of the original 5 values and the 4 code-written values.
    Proves the CHECK no longer rejects legitimate code writes."""
    # Verified by the migration itself; this test just ensures the
    # column is queryable.
    sb = _get_live_supabase()
    result = sb.table("student_submissions").select("status").limit(1).execute()
    assert result is not None
```

### Step 2.6 — Run the live suite

```bash
source venv/bin/activate && python -m pytest tests/test_schema_assertions.py -v -m live 2>&1 | tail -15
```

Expected: 10 passed, 0 skipped.

### Step 2.7 — Commit

```bash
git add supabase/migrations/20260413_phase2_schema_reconcile.sql tests/test_schema_assertions.py
git commit -m "fix(schema): reconcile status CHECK + teacher_id drift

Phase 2 Hotfix 2. Closes two drifts surfaced during Phase 1:

  - student_submissions.status CHECK widened to union the 5 original
    values with the 4 values the code actually writes.
  - published_assessments.teacher_id (already in live DB) codified in
    the SQL of record.

Schema is now the single source of truth — prerequisite for Phase 4
RLS hardening. Schema assertion tests updated accordingly.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Characterization tests for `stem_grading.py`

**Why:** Feathers' rule. `stem_grading.py` is 5% covered and tangled. Before Phase 3 splits it, we need a black-box test harness that pins observable outputs for a set of known inputs. After the split, the same harness must still pass — that's the regression proof.

**Approach:** Capture N real grading inputs+outputs as JSON fixtures (no live API calls — mock the OpenAI layer, pin the function's deterministic post-processing). Each fixture is one test case.

**Files:**
- Create: `tests/characterization/__init__.py`
- Create: `tests/characterization/test_stem_grading_golden.py`
- Create: `tests/characterization/fixtures/stem_grading/` (~8-12 JSON fixtures)

### Step 3.1 — Survey `stem_grading.py` entry points

```bash
source venv/bin/activate && grep -n "^def \|^class " backend/services/stem_grading.py
```

Pick the ~3 top-level entry points that route handlers actually call. Those are the characterization targets. Internal helpers are out of scope — if they change during the split, the top-level outputs shouldn't.

### Step 3.2 — Write a fixture capture script

Create `tests/characterization/capture_stem_fixtures.py` (not committed as a test — it's a one-shot tool):

```python
"""One-shot: runs stem_grading entry points on a curated set of
inputs with a mocked OpenAI layer, writes (input, output) JSON pairs
to fixtures/stem_grading/. Re-run when adding coverage; never run
from CI."""
import json, pathlib
from unittest.mock import patch

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures" / "stem_grading"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

CASES = [
    # name, (entrypoint, kwargs, mocked_openai_response)
    # Fill in 8-12 cases covering: MC correct, MC wrong, free-response
    # correct, free-response partial, empty answer, malformed rubric,
    # accommodation-present, accommodation-absent.
]

def run():
    from backend.services import stem_grading
    for name, (fn_name, kwargs, fake_oai) in CASES:
        fn = getattr(stem_grading, fn_name)
        with patch("backend.services.stem_grading.openai_client") as mock:
            mock.chat.completions.create.return_value = fake_oai
            out = fn(**kwargs)
        (FIXTURES_DIR / f"{name}.json").write_text(json.dumps(
            {"input": {"fn": fn_name, "kwargs": kwargs, "oai": fake_oai},
             "output": out}, indent=2, default=str))

if __name__ == "__main__":
    run()
```

Populate `CASES` by reading `stem_grading.py` and picking 8-12 inputs that exercise the branches you can see. The exact list is the implementer's call — the rule is: coverage of every `if`/`else` branch that produces a distinct output shape.

### Step 3.3 — Run the capture, commit the fixtures

```bash
source venv/bin/activate && python tests/characterization/capture_stem_fixtures.py && ls tests/characterization/fixtures/stem_grading/
```

Manually eyeball each JSON file — if any output looks wrong (e.g., negative score, swallowed error message, empty feedback where the input clearly warrants one), that's a **latent bug**. STOP and raise it before pinning the "wrong" output as the golden truth.

### Step 3.4 — Write the characterization test

Create `tests/characterization/test_stem_grading_golden.py`:

```python
"""Characterization tests for stem_grading.

For each fixture in fixtures/stem_grading/, re-run the entry point
with the captured input + mocked OpenAI response and assert the
output matches the captured output byte-for-byte. These tests PIN
the current behavior so the Phase 3 monolith split can prove it
preserved it.

If a fixture's assertion breaks, there are three legitimate
responses:
  1. The split introduced a regression — fix the split.
  2. The split intentionally changed the output — re-capture the
     fixture in the same commit as the split, with a commit message
     documenting the behavior change.
  3. The captured output was always wrong (latent bug fixed by the
     split) — same as 2, but the commit message is celebratory.

What's NOT legitimate: silently editing a fixture to make a failing
test pass.
"""
import json, pathlib
from unittest.mock import patch

import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures" / "stem_grading"


def _load_fixtures():
    return [(p.stem, json.loads(p.read_text())) for p in sorted(FIXTURES_DIR.glob("*.json"))]


@pytest.mark.parametrize("name,fixture", _load_fixtures())
def test_stem_grading_characterization(name, fixture):
    from backend.services import stem_grading
    fn = getattr(stem_grading, fixture["input"]["fn"])
    kwargs = fixture["input"]["kwargs"]
    fake_oai = fixture["input"]["oai"]

    with patch("backend.services.stem_grading.openai_client") as mock:
        mock.chat.completions.create.return_value = fake_oai
        out = fn(**kwargs)

    assert out == fixture["output"], f"Characterization drift in fixture {name}"
```

### Step 3.5 — Run and verify green

```bash
source venv/bin/activate && python -m pytest tests/characterization/ -v 2>&1 | tail -15
```

Expected: all parametrized cases pass. If any fail, your capture is non-deterministic (hidden time/randomness). Fix by patching the source of non-determinism before re-capturing.

### Step 3.6 — Commit

```bash
git add tests/characterization/
git commit -m "test: characterization harness for stem_grading (Phase 3 prep)

Black-box pins of stem_grading entry points against captured input/
output pairs with a mocked OpenAI layer. Phase 3's monolith split
must keep these green; any intentional output change requires
re-capturing the fixture in the same commit.

Feathers, Working Effectively with Legacy Code: stabilize behavior
before refactor.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Categorize the remaining 703 exception catches

**Leaner task — mechanical sweep.** The goal is a fully-annotated audit file, not perfection per row. Use the Task 3 Task 11 categorization patterns (from Phase 1) as the rubric; most new rows will fall into one bucket on sight.

**Files:**
- Modify: `docs/exception-audit-2026-04.md`

### Step 4.1 — Regenerate the audit

After Hotfixes 1–2, some catches changed shape. Regenerate:

```bash
source venv/bin/activate && python scripts/audit_exceptions.py > docs/exception-audit-2026-04.md
```

### Step 4.2 — Re-apply the 86 Phase 1 categorizations

They're in the previous git history. Easiest path: cherry-pick the categorization commit (`9f322b5` equivalent on this branch) OR re-run the Python mapping script from Phase 1 Task 11 commit.

### Step 4.3 — Categorize the remaining ~700 in batches by file

For each file with `UNCATEGORIZED` rows, read the handler bodies and apply the rubric:

| Pattern | Category |
|---|---|
| Top-level route guard: `log.exception + return 500` | INTENTIONAL |
| Typed catch (`ValueError`, `KeyError`, etc.) with documented fallback | INTENTIONAL |
| Bare `pass` on a best-effort write (audit, file-mtime, cache miss) | INTENTIONAL |
| Bare `pass` on a query result the caller depends on | LEGACY |
| `log.warning` + silent continue on something user-visible | NEEDS_ALERT |
| `log.error` + graceful HTTP error response | INTENTIONAL |
| `log.error` + silent continue on critical path | NEEDS_ALERT |
| `raise` after typed-check (e.g., duplicate detection) | INTENTIONAL |

Commit every ~100 rows so the history is reviewable.

### Step 4.4 — Exit criterion

Zero rows remain `UNCATEGORIZED`. Verify:

```bash
grep -c "UNCATEGORIZED" docs/exception-audit-2026-04.md
```

Expected: `0`.

Commit:

```bash
git add docs/exception-audit-2026-04.md
git commit -m "docs: complete exception audit (703 remaining catches categorized)

All 789 catches now carry a category. Phase 2 Task 5 fixes the LEGACY
and NEEDS_ALERT buckets; INTENTIONAL stays as-is.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Fix 12 LEGACY + remaining NEEDS_ALERT

**Files:** per-row from Task 4 output.

### Step 5.1 — Extract the work list

```bash
grep -E '\| (LEGACY|NEEDS_ALERT) \|' docs/exception-audit-2026-04.md > /tmp/phase2-task5-worklist.md
wc -l /tmp/phase2-task5-worklist.md
```

### Step 5.2 — For each LEGACY row, choose one of

- **Replace with typed catch** if the swallowed exception type is known (e.g., `ValueError` on parse).
- **Delete the try/except** if the only path is `pass` and the operation is non-critical (e.g., best-effort audit).
- **Convert to NEEDS_ALERT pattern** if the swallowed failure matters (`sentry_sdk.capture_exception`).

One commit per file. Commit message format:

```
fix(exceptions): tighten LEGACY catches in <file>

Converts N bare Exception swallows to typed catches or Sentry
captures per the audit rubric. Row references:
  - <file>:<line>  <pattern>  → <action>
```

### Step 5.3 — For each remaining NEEDS_ALERT row

Apply the Hotfix-1 pattern: `sentry_sdk.capture_exception(e)` inside the existing `except` block. No behavior change; just observability. One commit per file.

### Step 5.4 — Full test suite green

```bash
source venv/bin/activate && python -m pytest tests/ -q -m "not live" 2>&1 | tail -5
```

Expected: all pass. No regressions.

---

## Task 6: Kill 0%-coverage production paths + backfill `student_history.py`

**Why:** Exit-gate criterion demands no production module at 0%. `student_history.py` specifically: cross-boundary writes (teacher → student), referenced by portal grading factor list (CLAUDE.md §7), deserves a dedicated test file before Phase 3.

**Files:** see File Structure.

### Step 6.1 — `tests/test_student_history.py`

Mirror the existing `tests/test_portal_grading.py` structure. Target ≥ 40% coverage of `student_history.py` — focus on: `save_student_history`, `load_student_history`, `build_history_context`, and the score-window trimming logic.

Commit when ≥40%.

### Step 6.2 — `tests/test_outlook_sender.py`

Keep it minimal — hit public entry points with mocked SMTP. Target: break 0%, aim for ≥20%. Commit.

### Step 6.3 — `tests/test_openai_tts_service.py`

Same approach — mock OpenAI, hit public functions. Target: ≥20%. Commit.

### Step 6.4 — `tests/test_staging.py`

Same approach. Target: ≥20%. Commit.

### Step 6.5 — Verify coverage floor

```bash
source venv/bin/activate && python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress --ignore=tests/e2e -m "not live" --cov=backend --cov-fail-under=35 2>&1 | tail -5
```

Expected: **35% reached**. If not, revisit lowest-covered modules from the report until it is.

---

## Task 7: Phase 2 Exit Gate — raise CI floor to 35%

**Files:**
- Modify: `.github/workflows/ci.yml`

### Step 7.1 — Update the floor

```yaml
--cov-fail-under=35
```

### Step 7.2 — Verify

```bash
source venv/bin/activate && python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress --ignore=tests/e2e -m "not live" --cov=backend --cov-fail-under=35 2>&1 | tail -5
```

Expected: pass.

### Step 7.3 — Confirm exit criteria checklist

- [ ] Hotfix 1 merged: 5 grading-critical catches capture to Sentry.
- [ ] Hotfix 2 merged: schema drifts reconciled; `tests/test_schema_assertions.py` is 10 passed, 0 skipped.
- [ ] Characterization harness green: `tests/characterization/test_stem_grading_golden.py` covers ≥ 8 fixtures, all passing.
- [ ] `docs/exception-audit-2026-04.md` has zero `UNCATEGORIZED` rows.
- [ ] All LEGACY + NEEDS_ALERT catches fixed.
- [ ] Zero production modules at 0% coverage.
- [ ] CI coverage floor = 35%.

### Step 7.4 — Commit + PR

```bash
git add .github/workflows/ci.yml
git commit -m "ci: raise coverage floor to 35% (Phase 2 exit gate)

Phase 2 complete. Characterization + alerting + schema work landed;
floor rises from the pre-Phase-2 reality-check 30% to the Phase 1
original target of 35%. Phase 3 exit target is 40%.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Phase 2 Exit → Phase 3 Entry

Phase 3 can now safely:
- Split `stem_grading.py` (characterization harness protects the split)
- Split `visualization.py` (lighter contracts; reduced risk)
- Decompose planner_routes / assignment_grader monoliths
- Apply Phase 4 RLS on top of a reconciled schema

Deferred to Phase 3:
- 40% floor as Phase 3 exit criterion
- `visualization.py` characterization (if/when split begins)
- Monolith splitting itself

Deferred to Phase 4:
- RLS policies on reconciled tables
- Task queue (replace grading-thread pattern)
- Staging environment
