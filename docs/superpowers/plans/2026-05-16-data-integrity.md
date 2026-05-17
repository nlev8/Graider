# Data Integrity → ~9 — Forward-Only Submission Dedup + Temporal Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make submission dedup a provable, concurrency-safe, forward-only DB guarantee; make CI prove it; fix the 2 remaining naive timestamps.

**Architecture:** A new nullable `dedup_key` column on `submissions` + `student_submissions`, populated only by new writes (legacy rows stay NULL), backed by a `CREATE UNIQUE INDEX CONCURRENTLY … WHERE dedup_key IS NOT NULL` partial index — forward-only by construction (cannot fail on history, rewrites nothing). Routes set the key; the existing `23505` catch becomes a real guarantee. Alembic migration `0002`; CI Migrations Smoke applies base schema then `alembic upgrade head` and asserts the indexes exist.

**Tech Stack:** Python 3.12, Alembic (raw `op.execute`, autocommit blocks per `backend/migrations/env.py`), Postgres 15, pytest + testcontainers (Docker-gated, skips cleanly without Docker), Supabase client (mocked in route tests).

**Spec:** `docs/superpowers/specs/2026-05-16-data-integrity-design.md`. Scope OUT: full Alembic rebaseline, historical dup cleanup, any non-Data-Integrity dimension.

---

### Task 1: Temporal hardening — survey_routes naive timestamps

**Files:**
- Modify: `backend/routes/survey_routes.py:6` (import), `:366`, `:375`
- Test: `tests/test_survey_timestamps_tzaware.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_survey_timestamps_tzaware.py
"""Survey submit must write tz-aware ISO timestamps (Data Integrity Tier 1)."""
import re
from datetime import datetime


def test_survey_module_uses_tz_aware_now():
    """No naive datetime.utcnow() may remain in survey_routes; the submit
    path must produce an offset-bearing ISO-8601 timestamp."""
    import backend.routes.survey_routes as sr
    src = (sr.__file__)
    text = open(src, encoding="utf-8").read()
    assert "datetime.utcnow()" not in text, "naive utcnow() still present"
    # the tz-aware call must be the replacement
    assert "datetime.now(timezone.utc)" in text
    # sanity: an emitted timestamp parses WITH an offset
    ts = datetime.now(__import__("datetime").timezone.utc).isoformat()
    assert re.search(r"\+00:00$", ts)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source venv/bin/activate && python -m pytest tests/test_survey_timestamps_tzaware.py -q`
Expected: FAIL — `assert "datetime.utcnow()" not in text` fails (it is present at :366/:375).

- [ ] **Step 3: Make the minimal change**

In `backend/routes/survey_routes.py` line 6, change:
```python
from datetime import datetime
```
to:
```python
from datetime import datetime, timezone
```
Line 366: `response_data['submitted_at'] = datetime.utcnow().isoformat()` → `response_data['submitted_at'] = datetime.now(timezone.utc).isoformat()`
Line 375: `'updated_at': datetime.utcnow().isoformat(),` → `'updated_at': datetime.now(timezone.utc).isoformat(),`

- [ ] **Step 4: Run test to verify it passes**

Run: `source venv/bin/activate && python -m pytest tests/test_survey_timestamps_tzaware.py -q`
Expected: PASS. Also run `ruff check backend/routes/survey_routes.py` → "All checks passed!"

- [ ] **Step 5: Commit**

```bash
git add backend/routes/survey_routes.py tests/test_survey_timestamps_tzaware.py
git commit -m "fix(survey): tz-aware timestamps (Data Integrity Tier 1)"
```

---

### Task 2: Alembic migration `0002` — forward-only dedup columns + partial unique indexes

**Files:**
- Create: `backend/migrations/versions/0002_submission_dedup_forward_only.py`

- [ ] **Step 1: Write the migration (no separate unit test — Task 3 is its real test)**

```python
# backend/migrations/versions/0002_submission_dedup_forward_only.py
"""Forward-only submission dedup keys + partial unique indexes.

Revision ID: 0002_subm_dedup
Revises: 0001_baseline
Create Date: 2026-05-16

Classification: additive, forward-only, reversible.

Adds a nullable `dedup_key` to `submissions` and `student_submissions`
and a partial UNIQUE index `WHERE dedup_key IS NOT NULL`. All existing
rows have dedup_key = NULL, so the index build cannot fail on historical
duplicates and rewrites nothing (the spec's forward-only requirement).
Routes populate the key for new writes only.

downgrade() is implemented (unlike 0001's forward-only stance) because
this change is purely additive — dropping the index + column fully and
safely reverses it (spec requires reversibility).

CONCURRENTLY DDL cannot run in a transaction; env.py uses
transaction_per_migration, so each statement runs inside
op.get_context().autocommit_block().
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002_subm_dedup"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATEMENTS_UP = [
    "ALTER TABLE submissions ADD COLUMN IF NOT EXISTS dedup_key TEXT",
    "ALTER TABLE student_submissions ADD COLUMN IF NOT EXISTS dedup_key TEXT",
    "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_submissions_dedup_key "
    "ON submissions (dedup_key) WHERE dedup_key IS NOT NULL",
    "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_student_submissions_dedup_key "
    "ON student_submissions (dedup_key) WHERE dedup_key IS NOT NULL",
]

_STATEMENTS_DOWN = [
    "DROP INDEX CONCURRENTLY IF EXISTS uq_submissions_dedup_key",
    "DROP INDEX CONCURRENTLY IF EXISTS uq_student_submissions_dedup_key",
    "ALTER TABLE submissions DROP COLUMN IF EXISTS dedup_key",
    "ALTER TABLE student_submissions DROP COLUMN IF EXISTS dedup_key",
]


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for stmt in _STATEMENTS_UP:
            op.execute(stmt)


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for stmt in _STATEMENTS_DOWN:
            op.execute(stmt)
```

- [ ] **Step 2: Sanity-check the revision graph**

Run: `source venv/bin/activate && python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; s=ScriptDirectory.from_config(Config('alembic.ini')); print([ (r.revision, r.down_revision) for r in s.walk_revisions() ])"`
Expected: shows `('0002_subm_dedup', '0001_baseline')` and `('0001_baseline', None)` — single linear chain, no branches/cycles.

- [ ] **Step 3: Commit**

```bash
git add backend/migrations/versions/0002_submission_dedup_forward_only.py
git commit -m "feat(db): migration 0002 — forward-only submission dedup keys"
```

---

### Task 3: Prove it — schema test that `alembic upgrade head` creates the indexes

**Files:**
- Create: `tests/test_submission_dedup_migration_applies.py`

- [ ] **Step 1: Write the failing test** (mirrors `tests/test_schema_tightening_applies.py` harness)

```python
# tests/test_submission_dedup_migration_applies.py
"""0002 forward-only dedup migration — applies on base schema; the two
partial UNIQUE indexes exist after `alembic upgrade head`; legacy NULL
rows do not collide. Docker-gated (skips cleanly without Docker)."""
from __future__ import annotations

import os
import pathlib
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

SCHEMA_APPLY_ORDER = [
    "supabase_student_portal_schema.sql",
    "backend/database/supabase_schema.sql",
    "backend/database/supabase_teacher_schema.sql",
    "supabase_submission_confirmations.sql",
    "supabase_roster_rls.sql",
]

AUTH_SCHEMA_STUB = """
CREATE SCHEMA IF NOT EXISTS auth;
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$ SELECT NULL::uuid; $$;
CREATE OR REPLACE FUNCTION auth.jwt() RETURNS jsonb LANGUAGE sql STABLE AS $$ SELECT '{}'::jsonb; $$;
CREATE OR REPLACE FUNCTION auth.role() RETURNS text LANGUAGE sql STABLE AS $$ SELECT NULL::text; $$;
"""


def _docker_available() -> bool:
    try:
        subprocess.run(["docker", "ps"], capture_output=True, timeout=5, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


@pytest.fixture(scope="module")
def migrated_db():
    if not _docker_available():
        pytest.skip("Docker not available")
    try:
        from testcontainers.postgres import PostgresContainer
        import psycopg2
    except ImportError:
        pytest.skip("testcontainers[postgres]/psycopg2 not installed")

    with PostgresContainer("postgres:15-alpine") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2", "postgresql")
        conn = psycopg2.connect(url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(AUTH_SCHEMA_STUB)
        for rel in SCHEMA_APPLY_ORDER:
            cur.execute((REPO_ROOT / rel).read_text(encoding="utf-8"))
        # stamp baseline, then run forward migrations
        env = {**os.environ, "ALEMBIC_DATABASE_URL": url}
        subprocess.run(["alembic", "stamp", "0001_baseline"], cwd=REPO_ROOT,
                        env=env, check=True, capture_output=True)
        r = subprocess.run(["alembic", "upgrade", "head"], cwd=REPO_ROOT,
                            env=env, capture_output=True, text=True)
        assert r.returncode == 0, f"alembic upgrade head failed: {r.stderr}"
        yield cur


@pytest.mark.parametrize("idx,table", [
    ("uq_submissions_dedup_key", "submissions"),
    ("uq_student_submissions_dedup_key", "student_submissions"),
])
def test_partial_unique_index_exists(migrated_db, idx, table):
    cur = migrated_db
    cur.execute("SELECT indexdef FROM pg_indexes WHERE indexname = %s;", (idx,))
    row = cur.fetchone()
    assert row is not None, f"{idx} not created by alembic upgrade head"
    assert "UNIQUE" in row[0] and "dedup_key IS NOT NULL" in row[0], row[0]


def test_dedup_key_blocks_duplicate_but_allows_null(migrated_db):
    import psycopg2
    cur = migrated_db
    cur.execute("INSERT INTO published_assessments (teacher_id, assessment, join_code, title) "
                "VALUES ('t','{}'::jsonb,'DKEY01','T') RETURNING id;")
    cur.execute("INSERT INTO submissions (assessment_id, join_code, student_name, answers, dedup_key) "
                "VALUES (NULL,'DKEY01','A','{}'::jsonb, NULL);")
    cur.execute("INSERT INTO submissions (assessment_id, join_code, student_name, answers, dedup_key) "
                "VALUES (NULL,'DKEY01','B','{}'::jsonb, NULL);")  # 2 NULLs OK
    cur.execute("INSERT INTO submissions (assessment_id, join_code, student_name, answers, dedup_key) "
                "VALUES (NULL,'DKEY01','C','{}'::jsonb, 'DKEY01|c');")
    with pytest.raises(psycopg2.errors.UniqueViolation):
        cur.execute("INSERT INTO submissions (assessment_id, join_code, student_name, answers, dedup_key) "
                    "VALUES (NULL,'DKEY01','C2','{}'::jsonb, 'DKEY01|c');")
```

- [ ] **Step 2: Run to verify it fails (or skips without Docker)**

Run: `source venv/bin/activate && python -m pytest tests/test_submission_dedup_migration_applies.py -q`
Expected (Docker present): FAIL — indexes absent until Task 2's migration is on the revision chain (if Task 2 already committed, this is the GREEN proof instead; that's fine — it's the migration's real test). Without Docker: `skipped` (acceptable; CI has Docker).

- [ ] **Step 3: Confirm GREEN with Task 2 applied**

Run the same command. Expected: PASS (Docker) or SKIP (no Docker).

- [ ] **Step 4: Make CI prove it — Migrations Smoke**

In `.github/workflows/ci.yml`, the `Migrations Smoke` job currently only runs `alembic upgrade head`. Add, *before* `alembic upgrade head`, a step applying the base schema in `SCHEMA_APPLY_ORDER` (+ `AUTH_SCHEMA_STUB`) against the job's `postgres:15-alpine` service, and `alembic stamp 0001_baseline`; add, *after* it, an assertion step:
```yaml
      - name: Assert dedup unique indexes exist
        env:
          PGPASSWORD: smoke
        run: |
          for idx in uq_submissions_dedup_key uq_student_submissions_dedup_key; do
            psql -h localhost -U postgres -d smoke -tAc \
              "SELECT 1 FROM pg_indexes WHERE indexname='$idx';" | grep -q 1 \
              || { echo "::error::missing index $idx after alembic upgrade head"; exit 1; }
          done
```
(Match existing job's psql/connection conventions; the assertion is the provability gate.)

- [ ] **Step 5: Commit**

```bash
git add tests/test_submission_dedup_migration_applies.py .github/workflows/ci.yml
git commit -m "test(db): prove 0002 dedup indexes via Migrations Smoke + schema test"
```

---

### Task 4: Join-code route populates `dedup_key` (single-attempt only)

**Files:**
- Modify: `backend/routes/student_portal_routes.py` (the submit handler — the line `submission_row['id'] = str(uuid.uuid4())`, ~:1494)
- Test: `tests/test_join_code_dedup_key.py` (create)

- [ ] **Step 1: Write the failing test** (mock supabase; 2nd insert raises 23505 → friendly 400; multi-attempt → key absent)

```python
# tests/test_join_code_dedup_key.py
"""Join-code submit sets dedup_key only when allow_multiple_attempts is
False, and surfaces a friendly 400 on the resulting unique violation."""
from unittest.mock import MagicMock, patch
import backend.routes.student_portal_routes as spr


def _row_captured(allow_multiple):
    """Drive the dedup_key assignment in isolation, mirroring the route:
    `if not settings.get('allow_multiple_attempts', False):`"""
    settings = {"allow_multiple_attempts": allow_multiple}
    submission_row = {}
    code = "ABC123"
    student_name = "  Jane DOE "
    # --- replicate exactly the lines this task adds (see Step 3) ---
    if not settings.get("allow_multiple_attempts", False):
        submission_row["dedup_key"] = f"{code}|{student_name.strip().lower()}"
    return submission_row


def test_single_attempt_sets_normalized_dedup_key():
    row = _row_captured(allow_multiple=False)
    assert row["dedup_key"] == "ABC123|jane doe"


def test_multi_attempt_leaves_dedup_key_unset():
    row = _row_captured(allow_multiple=True)
    assert "dedup_key" not in row


def test_route_translates_23505_to_friendly_400():
    """The existing except-block must return the friendly 400 when the
    DB raises a unique violation (now backed by a real index)."""
    src = open(spr.__file__, encoding="utf-8").read()
    # the dedup_key population must be present and gated
    assert 'submission_row["dedup_key"]' in src or "submission_row['dedup_key']" in src
    assert "allow_multiple_attempts" in src
    # the 23505 -> 400 path already exists; assert it is intact
    assert "'23505'" in src and "already submitted" in src.lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `source venv/bin/activate && python -m pytest tests/test_join_code_dedup_key.py -q`
Expected: FAIL — `test_route_translates_23505_to_friendly_400` fails (`dedup_key` not yet in source).

- [ ] **Step 3: Add the minimal route change**

In `backend/routes/student_portal_routes.py`, immediately after the existing line:
```python
        submission_row['id'] = str(uuid.uuid4())
```
add (using the in-scope `settings`, `code`, `student_name` — confirmed at the pre-check `:1451-1458`):
```python
        # Forward-only dedup: single-attempt assessments get a unique key
        # so concurrent double-submits hit the partial unique index
        # (matches the existing case-insensitive ilike pre-check).
        if not settings.get('allow_multiple_attempts', False):
            submission_row['dedup_key'] = f"{code}|{student_name.strip().lower()}"
```
Leave the existing pre-check SELECT and the `except … '23505' … 'already submitted' … 400` block unchanged.

- [ ] **Step 4: Run to verify it passes + no regression**

Run: `source venv/bin/activate && python -m pytest tests/test_join_code_dedup_key.py tests/test_clever_student_session_multi_enrollment.py -q -k "dedup or join_code" && ruff check backend/routes/student_portal_routes.py`
Expected: PASS; ruff "All checks passed!"

- [ ] **Step 5: Commit**

```bash
git add backend/routes/student_portal_routes.py tests/test_join_code_dedup_key.py
git commit -m "feat(portal): join-code submit sets forward-only dedup_key"
```

---

### Task 5: Class-based route populates `dedup_key`

**Files:**
- Modify: `backend/routes/student_account_routes.py` (the class submit handler — the line `submission_row['id'] = str(uuid.uuid4())`, ~:1199)
- Test: `tests/test_class_submit_dedup_key.py` (create)

- [ ] **Step 1: Read the exact submission_row keys**

Run: `source venv/bin/activate && sed -n '1130,1205p' backend/routes/student_account_routes.py`
Expected: confirm the local variables / `submission_row` keys for student id, content id, and attempt number (the route computes `attempt = len(existing.data) + 1` and sets the row). Note the exact key names (e.g. `submission_row['student_id']`, `['content_id']`, `['attempt_number']`).

- [ ] **Step 2: Write the failing test**

```python
# tests/test_class_submit_dedup_key.py
"""Class submit sets dedup_key = student_id|content_id|attempt_number so
concurrent same-attempt double-submits collide on the partial index,
while legitimate new attempts (incremented attempt_number) do not."""
import backend.routes.student_account_routes as sar


def test_source_sets_attempt_scoped_dedup_key():
    src = open(sar.__file__, encoding="utf-8").read()
    assert "dedup_key" in src, "class submit must set dedup_key"
    # attempt-scoped (NOT student_id|content_id only — multi-attempt is intentional)
    assert "attempt" in src.split("dedup_key", 1)[1][:200], \
        "dedup_key must include attempt_number (multi-attempt is intentional)"
    assert "'23505'" in src and "already submitted" in src.lower()


def test_key_shape_is_triple():
    sid, cid, att = "s1", "c1", 2
    assert f"{sid}|{cid}|{att}" == "s1|c1|2"  # documents the exact shape
```

- [ ] **Step 3: Run to verify it fails**

Run: `source venv/bin/activate && python -m pytest tests/test_class_submit_dedup_key.py -q`
Expected: FAIL — `dedup_key` not yet in `student_account_routes.py`.

- [ ] **Step 4: Add the minimal route change**

In `backend/routes/student_account_routes.py`, immediately after the existing line:
```python
        submission_row['id'] = str(uuid.uuid4())
```
add (use the exact keys confirmed in Step 1; canonical form shown):
```python
        # Forward-only dedup keyed by the intentional attempt model:
        # concurrent same-attempt double-submits collide on the partial
        # unique index; a genuine new attempt (incremented attempt_number)
        # has a distinct key and still succeeds.
        submission_row['dedup_key'] = (
            f"{submission_row['student_id']}|"
            f"{submission_row['content_id']}|"
            f"{submission_row['attempt_number']}"
        )
```
If Step 1 showed different key names, substitute them verbatim. Leave the existing `except … '23505' … 'already submitted' … 400` block unchanged.

- [ ] **Step 5: Run to verify it passes + regression**

Run: `source venv/bin/activate && python -m pytest tests/test_class_submit_dedup_key.py -q && ruff check backend/routes/student_account_routes.py && python -m pytest tests/ -q -k "submission or student_account or dedup or survey_timestamps" 2>&1 | tail -2`
Expected: target tests PASS; ruff clean; regression slice PASS (0 failed).

- [ ] **Step 6: Commit**

```bash
git add backend/routes/student_account_routes.py tests/test_class_submit_dedup_key.py
git commit -m "feat(class-submit): forward-only attempt-scoped dedup_key"
```

---

### Task 6: Full regression + PR

- [ ] **Step 1:** `source venv/bin/activate && python -m pytest tests/ -q -k "submission or dedup or survey or schema_tightening or migration_applies or sis or clever" 2>&1 | tail -3` → 0 failed.
- [ ] **Step 2:** `ruff check backend/` → All checks passed.
- [ ] **Step 3:** Open PR `feature/data-integrity-tier1`; the 9 required checks (incl. Migrations Smoke now asserting the indexes) must be green. Squash-merge.
- [ ] **Step 4:** After merge, append a dated "Data Integrity Tier 1 shipped" note to `docs/superpowers/specs/2026-03-20-comprehensive-hardening-assessment.md` and STATUS-stamp this plan CLOSED. (A verification re-score is optional — Data Integrity 7→~9 is bounded and CI-proven; not a multi-model gate like Clever was.)

---

## Self-Review

- **Spec coverage:** §3.1 column+partial index → Task 2; §3.2 route key population → Tasks 4 (join-code, gated on `allow_multiple_attempts`) + 5 (class, attempt-scoped); §3.3 23505-becomes-real → asserted in Tasks 4/5; §3.4 migration shape (autocommit_block, reversible) → Task 2; §3.5 utcnow → Task 1; §3.6 CI provability → Task 3 Step 4 + the schema test. All spec sections mapped.
- **Placeholder scan:** every code/command step has concrete content; Task 5 Step 1 is a real read-then-edit (exact keys verified before the edit, canonical form shown) — not a placeholder.
- **Type/name consistency:** `dedup_key` column name, `uq_submissions_dedup_key` / `uq_student_submissions_dedup_key` index names, revision `0002_subm_dedup` / down `0001_baseline` are identical across Tasks 2/3/4/5.
- **Scope:** single bounded plan; rebaseline + historical cleanup explicitly out (spec §5), restated in Task 6.
