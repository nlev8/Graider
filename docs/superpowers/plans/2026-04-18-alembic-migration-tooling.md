# Alembic Migration Tooling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce Alembic as the single forward path for Graider schema changes, applied automatically as a Railway pre-deploy step with CI-enforced expand-contract discipline and a named no-op baseline anchoring the existing live schema.

**Architecture:** Alembic scaffolding (`alembic.ini`, `backend/migrations/env.py`, template, `0001_baseline_existing_live_schema.py` no-op) plus three CI guardrails (migrations-smoke job against ephemeral Postgres with Supabase auth stubs; destructive-op scanner that requires `# destructive:` acknowledgment comments; cutoff-policy test that freezes `backend/database/` from further edits). No SQLAlchemy models, no ORM. Migrations are raw `op.execute(...)` SQL.

**Tech Stack:** Alembic 1.13+, psycopg 3 (sync), Postgres 15, GitHub Actions, pytest, Railway preDeployCommand.

**Spec:** `docs/superpowers/specs/2026-04-18-alembic-migration-tooling-design.md`

**Branch:** start fresh off `origin/main`: `feat/alembic-migration-tooling`

---

## File inventory

| File | Change | Responsibility |
|---|---|---|
| `requirements.txt` | modify | add `alembic` + `psycopg[binary]` |
| `alembic.ini` | create | top-level Alembic config — points at `backend/migrations`, reads `ALEMBIC_DATABASE_URL` |
| `backend/migrations/env.py` | create | online-mode migration driver; sets `transaction_per_migration=True` |
| `backend/migrations/script.py.mako` | create | revision template with forward-only downgrade default |
| `backend/migrations/versions/0001_baseline_existing_live_schema.py` | create | no-op baseline anchor |
| `.github/ci/supabase_stubs.sql` | create | auth schema stubs so vanilla Postgres can apply RLS migrations in CI |
| `.github/workflows/ci.yml` | modify | add `Migrations Smoke` job |
| `railway.json` | modify | add `preDeployCommand: "alembic upgrade head"` + `healthcheckPath: "/healthz"` |
| `.env.example` | modify | add `ALEMBIC_DATABASE_URL` placeholder |
| `tests/test_alembic_destructive_ops.py` | create | destructive-op regex scan with `# destructive:` ack requirement |
| `tests/test_cutoff_policy.py` | create | fails on new/modified files under `backend/database/` |
| `backend/database/CUTOFF.md` | create | human-readable freeze notice |
| `pyproject.toml` | modify | add `[tool.alembic-destructive-ops] allowlist = []` (empty; hook for emergency exemption) |

---

## Task 1: Set up branch and install dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Create branch off latest main**

```bash
git fetch origin main
git checkout -b feat/alembic-migration-tooling origin/main
```

- [ ] **Step 2: Append alembic + psycopg to requirements.txt**

Open `requirements.txt`. It currently ends with `celery==5.4.0`. Append:

```
alembic>=1.13,<2
psycopg[binary]>=3.2,<4
```

- [ ] **Step 3: Install and verify**

Run:
```bash
source venv/bin/activate
pip install -r requirements.txt
alembic --version
```

Expected: `alembic 1.13.x` or higher (no errors).

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "deps: add alembic and psycopg for migration tooling (Phase 4 follow-on)"
```

---

## Task 2: Create alembic.ini at repo root

**Files:**
- Create: `alembic.ini`

- [ ] **Step 1: Write the config file**

Create `alembic.ini` with this exact content:

```ini
# Graider Alembic configuration.
#
# This file is read by the `alembic` CLI from the repository root.
# Its main job is to point at backend/migrations/ and to tell Alembic
# how to get the database URL.
#
# The URL itself is NOT stored here. It is read from the
# ALEMBIC_DATABASE_URL environment variable by backend/migrations/env.py.
# This keeps secrets out of the repo and lets operator/CI provide the
# right URL for their environment.

[alembic]
script_location = backend/migrations
prepend_sys_path = .
timezone = UTC

# Deliberately unset. env.py reads ALEMBIC_DATABASE_URL from the env.
sqlalchemy.url =

# Revision filename format: zero-padded numeric prefix + slug.
# Matches the 0001_<slug>.py pattern used for the baseline.
file_template = %%(rev)s_%%(slug)s
truncate_slug_length = 40

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: Verify it's syntactically valid to Alembic**

Run:
```bash
alembic --config alembic.ini check
```

Expected: command should print an error about missing `script_location` contents (because `backend/migrations/` doesn't exist yet), NOT a parse error on the ini file. If you see `configparser.Error`, re-check the file.

---

## Task 3: Create backend/migrations/env.py

**Files:**
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/__init__.py` (empty; not strictly required by Alembic but keeps Python tooling happy)

- [ ] **Step 1: Create the migrations directory structure**

```bash
mkdir -p backend/migrations/versions
touch backend/migrations/__init__.py
touch backend/migrations/versions/__init__.py
```

- [ ] **Step 2: Write env.py**

Create `backend/migrations/env.py` with this exact content:

```python
"""Alembic online-mode environment.

Reads ALEMBIC_DATABASE_URL from the environment and connects via
psycopg 3 (sync). Configures transaction_per_migration=True so that
each revision runs in its own transaction — this is required by the
autocommit-only DDL policy in
docs/superpowers/specs/2026-04-18-alembic-migration-tooling-design.md.

We do NOT import from sqlalchemy.orm or any Graider application
modules here. This file must work against a completely empty Python
environment that has only alembic + psycopg installed, because the
Railway pre-deploy command runs it before the Flask app starts.
"""
from __future__ import annotations

import os
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool


_config = context.config


def _database_url() -> str:
    url = os.getenv("ALEMBIC_DATABASE_URL")
    if not url:
        print(
            "ERROR: ALEMBIC_DATABASE_URL environment variable is not set. "
            "Set it to a Postgres connection string (session pooler or "
            "direct — NOT transaction pooler). Example:\n"
            "  export ALEMBIC_DATABASE_URL='postgresql+psycopg://user:pw@host:port/db'",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return url


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a live database connection."""
    configuration = _config.get_section(_config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            # transaction_per_migration=True so each revision runs in its
            # own transaction. This is required by the spec's
            # autocommit-only DDL policy — without it, a failed autocommit
            # revision could strand work from earlier revisions in the
            # same `alembic upgrade` run.
            transaction_per_migration=True,
            # target_metadata stays None — we do not use autogenerate.
            # All migrations are raw op.execute() SQL.
            target_metadata=None,
            # Compare server default and type info is pointless without
            # metadata; explicitly off.
            compare_server_default=False,
            compare_type=False,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    # Offline mode is not supported in Graider's workflow. All migrations
    # run online against Railway's Postgres via the preDeployCommand.
    # Fail loudly rather than silently emitting SQL to stdout.
    print(
        "ERROR: Alembic offline mode is not supported. "
        "Run without --sql; migrations must execute online against the "
        "target database.",
        file=sys.stderr,
    )
    raise SystemExit(2)

run_migrations_online()
```

- [ ] **Step 3: Verify alembic can load env.py**

```bash
export ALEMBIC_DATABASE_URL=postgresql+psycopg://fake:fake@localhost:9999/fake
alembic heads
unset ALEMBIC_DATABASE_URL
```

Expected: command completes, prints nothing (no revisions exist yet). If you see an ImportError or parse error, check env.py.

- [ ] **Step 4: Commit**

```bash
git add alembic.ini backend/migrations/__init__.py backend/migrations/env.py backend/migrations/versions/__init__.py
git commit -m "feat: add Alembic scaffolding (alembic.ini + env.py with transaction_per_migration)"
```

---

## Task 4: Create revision template (script.py.mako)

**Files:**
- Create: `backend/migrations/script.py.mako`

- [ ] **Step 1: Write the template**

Create `backend/migrations/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

Classification: <additive | destructive>  (set before merge)
${"# destructive: <one-line justification>" if False else ""}
${"# autocommit: <op name>" if False else ""}
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}


# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    # Default: forward-only per
    # docs/superpowers/specs/2026-04-18-alembic-migration-tooling-design.md.
    # Replace only if you need local-dev reversibility; production must
    # NEVER run `alembic downgrade`.
    raise NotImplementedError("forward-only")
```

- [ ] **Step 2: Smoke-test by generating a throwaway revision**

```bash
export ALEMBIC_DATABASE_URL=postgresql+psycopg://fake:fake@localhost:9999/fake
alembic revision -m "throwaway smoke test"
```

Expected: a new file appears in `backend/migrations/versions/<hash>_throwaway_smoke_test.py` containing the template. Open it and verify:
- `down_revision: Union[str, None] = None` (first revision)
- `def downgrade(): raise NotImplementedError("forward-only")`
- Classification line present in docstring

- [ ] **Step 3: Remove the throwaway revision**

```bash
rm backend/migrations/versions/*throwaway*.py
unset ALEMBIC_DATABASE_URL
```

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/script.py.mako
git commit -m "feat: Alembic revision template with forward-only downgrade default"
```

---

## Task 5: Create the 0001 baseline revision

**Files:**
- Create: `backend/migrations/versions/0001_baseline_existing_live_schema.py`

- [ ] **Step 1: Write the baseline revision**

Create `backend/migrations/versions/0001_baseline_existing_live_schema.py`:

```python
"""Baseline — existing live schema at Alembic introduction.

Revision ID: 0001_baseline_existing_live_schema
Revises:
Create Date: 2026-04-18

Classification: additive (no-op — documents the anchor only)

This revision does NOT replay the pre-cutoff raw SQL migrations under
backend/database/. It exists only to provide a named anchor for the
Alembic revision graph.

Tradeoff accepted: Alembic becomes authoritative for forward schema
changes only, not for historical reconstruction. If a fresh-environment
bootstrap requirement arises later, we rebaseline then (see the spec
at docs/superpowers/specs/2026-04-18-alembic-migration-tooling-design.md).

Operator step (run once against live before the PR that introduces
Alembic is merged; also safe to run again because `alembic stamp` is
idempotent):

    export ALEMBIC_DATABASE_URL='<session-pooler-url>'
    alembic stamp 0001_baseline_existing_live_schema
"""
from __future__ import annotations

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "0001_baseline_existing_live_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Intentionally empty. Live schema at the cutoff date is represented
    # by the raw SQL artifacts under backend/database/ — see CUTOFF.md.
    pass


def downgrade() -> None:
    raise NotImplementedError("forward-only")
```

- [ ] **Step 2: Verify `alembic heads` shows the baseline**

```bash
export ALEMBIC_DATABASE_URL=postgresql+psycopg://fake:fake@localhost:9999/fake
alembic heads
```

Expected output: `0001_baseline_existing_live_schema (head)`.

- [ ] **Step 3: Verify `alembic history` shows one entry**

```bash
alembic history --verbose
```

Expected output includes `Rev: 0001_baseline_existing_live_schema` with empty Path and `down_revision = None`.

- [ ] **Step 4: Unset the fake URL**

```bash
unset ALEMBIC_DATABASE_URL
```

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/versions/0001_baseline_existing_live_schema.py
git commit -m "feat: add 0001 no-op baseline revision — anchors Alembic revision graph"
```

---

## Task 6: Add CI Supabase stubs

**Files:**
- Create: `.github/ci/supabase_stubs.sql`

- [ ] **Step 1: Create the stubs file**

```bash
mkdir -p .github/ci
```

Create `.github/ci/supabase_stubs.sql`:

```sql
-- CI-only Supabase auth-schema stubs.
--
-- Purpose: let vanilla Postgres apply migrations that reference
-- auth.uid() / auth.jwt() / auth.role() / auth.email() without
-- erroring on missing schema. The functions return NULL so any RLS
-- policy that compares them to a column simply evaluates FALSE —
-- which is what we want for a schema-validity smoke test.
--
-- Matches the pattern already used in
--   tests/test_rls_migration_applies.py
--   tests/test_schema_tightening_applies.py
-- plus auth.email() for the drift-reconciled Phase 4.2 policies.
--
-- DO NOT run this against production or staging. These stubs
-- intentionally return NULL and would silently disable every
-- RLS policy.

CREATE SCHEMA IF NOT EXISTS auth;

CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
    LANGUAGE sql STABLE AS $$ SELECT NULL::uuid; $$;

CREATE OR REPLACE FUNCTION auth.jwt() RETURNS jsonb
    LANGUAGE sql STABLE AS $$ SELECT '{}'::jsonb; $$;

CREATE OR REPLACE FUNCTION auth.role() RETURNS text
    LANGUAGE sql STABLE AS $$ SELECT NULL::text; $$;

CREATE OR REPLACE FUNCTION auth.email() RETURNS text
    LANGUAGE sql STABLE AS $$ SELECT NULL::text; $$;
```

- [ ] **Step 2: Commit**

```bash
git add .github/ci/supabase_stubs.sql
git commit -m "ci: Supabase auth-schema stubs for migrations-smoke job"
```

---

## Task 7: Add Migrations Smoke CI job

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Append the new job to ci.yml**

After the `frontend-build` job block (which ends at line 69 of the current file), append:

```yaml

  migrations-smoke:
    name: Migrations Smoke
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_PASSWORD: smoke
          POSTGRES_DB: smoke
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10

    env:
      ALEMBIC_DATABASE_URL: postgresql+psycopg://postgres:smoke@localhost:5432/smoke

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Install psql client
        run: sudo apt-get update && sudo apt-get install -y postgresql-client

      - name: Seed Supabase auth stubs
        run: psql "$ALEMBIC_DATABASE_URL" -v ON_ERROR_STOP=1 -f .github/ci/supabase_stubs.sql

      - name: Apply migrations
        run: alembic upgrade head

      - name: Show current revision
        run: alembic current --verbose
```

- [ ] **Step 2: Push a test commit and verify CI runs**

At this stage the job will run but the only migration is the no-op baseline, so it completes in ~40s. Don't push yet if you're still building — will push at the end in Task 13.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add Migrations Smoke job against ephemeral Postgres"
```

---

## Task 8: Write destructive-op CI scanner — failing tests first (TDD)

**Files:**
- Create: `tests/test_alembic_destructive_ops.py`
- Modify: `pyproject.toml` (or create if it doesn't exist)

- [ ] **Step 1: Check if pyproject.toml exists, create minimal if not**

```bash
ls pyproject.toml 2>/dev/null || cat > pyproject.toml <<'EOF'
[tool.alembic-destructive-ops]
allowlist = []
EOF
```

If `pyproject.toml` already exists, open it and append (if not already present):

```toml
[tool.alembic-destructive-ops]
allowlist = []
```

- [ ] **Step 2: Write the test with fixtures covering every destructive pattern**

Create `tests/test_alembic_destructive_ops.py`:

```python
"""CI guardrail: destructive Alembic ops require `# destructive:` acknowledgment.

Policy lives in docs/superpowers/specs/2026-04-18-alembic-migration-tooling-design.md
§ "Mechanical enforcement — destructive-op CI scan".

This test scans every Python file under backend/migrations/versions/ for
regex patterns that indicate destructive (or data-mutating) SQL and
fails unless the file contains an acknowledgment comment starting with
``# destructive:``.

False positives are expected and acceptable — the ack comment is cheap.
Every missed true positive is a production schema surprise, so we
prefer the pattern list to be broad.

The baseline revision (0001_baseline_existing_live_schema.py) and any
file listed in pyproject.toml's [tool.alembic-destructive-ops] allowlist
are skipped.
"""
from __future__ import annotations

import pathlib
import re
import textwrap

import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
VERSIONS_DIR = REPO_ROOT / "backend" / "migrations" / "versions"
BASELINE_STEM = "0001_baseline_existing_live_schema"
ACK_MARKER_RE = re.compile(r"^\s*#\s*destructive\s*:", re.MULTILINE)

DESTRUCTIVE_PATTERNS: list[str] = [
    # Alembic op helpers — schema destruction
    r"op\.drop_column\b",
    r"op\.drop_table\b",
    r"op\.rename_table\b",
    r"op\.drop_constraint\b",
    r"op\.drop_index\b",
    # alter_column tightening: type change or nullable=False
    r"op\.alter_column\([^)]*\btype_=",
    r"op\.alter_column\([^)]*\bnullable=False\b",
    # op.execute("...") escape hatches — raw SQL destruction
    r"\bDROP\s+(TABLE|COLUMN|CONSTRAINT|INDEX|POLICY|SCHEMA)\b",
    r"\bALTER\s+TABLE\s+\S+\s+DROP\b",
    r"\bALTER\s+TABLE\s+\S+\s+SET\s+NOT\s+NULL\b",
    r"\bALTER\s+TABLE\s+\S+\s+DROP\s+DEFAULT\b",
    r"\bTRUNCATE\b",
    # Data migrations — UPDATE/DELETE mutate existing rows and are
    # always destructive even if the net effect is desired.
    r"op\.execute\([^)]*\bUPDATE\s+\w+\s+SET\b",
    r"op\.execute\([^)]*\bDELETE\s+FROM\b",
    r"\bUPDATE\s+\w+\s+SET\b",
    r"\bDELETE\s+FROM\b",
]
_DESTRUCTIVE_RE = re.compile("|".join(DESTRUCTIVE_PATTERNS), re.IGNORECASE)


def _allowlist() -> set[str]:
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        import tomli as tomllib  # pragma: no cover

    pyproject = REPO_ROOT / "pyproject.toml"
    if not pyproject.exists():
        return set()
    data = tomllib.loads(pyproject.read_text())
    configured = (
        data.get("tool", {})
        .get("alembic-destructive-ops", {})
        .get("allowlist", [])
    )
    return {str(name) for name in configured}


def _iter_revision_files() -> list[pathlib.Path]:
    if not VERSIONS_DIR.exists():
        return []
    allowlist = _allowlist()
    files = []
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        if path.stem == BASELINE_STEM:
            continue
        if path.name in allowlist:
            continue
        files.append(path)
    return files


def test_every_destructive_revision_has_ack_comment():
    """For every non-baseline revision under backend/migrations/versions/,
    if it contains any DESTRUCTIVE_PATTERNS match, it must also contain
    a line starting with `# destructive:`.
    """
    offenders: list[str] = []
    for path in _iter_revision_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        hits = _DESTRUCTIVE_RE.findall(text)
        if not hits:
            continue
        if ACK_MARKER_RE.search(text) is None:
            offenders.append(
                f"{path.relative_to(REPO_ROOT)} contains destructive op(s) "
                f"but no `# destructive:` acknowledgment. First match: "
                f"{hits[0]!r}"
            )

    assert not offenders, (
        "Destructive Alembic ops must be acknowledged with a `# destructive:"
        " <justification>` comment. See "
        "docs/superpowers/specs/2026-04-18-alembic-migration-tooling-design.md"
        " § Mechanical enforcement.\n"
        + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# Self-tests — verify the regex list actually catches each pattern.
# These run against in-memory strings, not against files on disk, so they
# never touch the real revisions directory.
# ---------------------------------------------------------------------------

_DESTRUCTIVE_FIXTURES: list[tuple[str, str]] = [
    ("drop_column helper", "op.drop_column('t', 'c')"),
    ("drop_table helper", "op.drop_table('t')"),
    ("rename_table helper", "op.rename_table('a', 'b')"),
    ("drop_constraint helper", "op.drop_constraint('fk_x', 't')"),
    ("drop_index helper", "op.drop_index('ix_x')"),
    ("alter_column type tightening", "op.alter_column('t', 'c', type_=sa.String(10))"),
    ("alter_column nullable tightening", "op.alter_column('t', 'c', nullable=False)"),
    ("raw DROP TABLE", 'op.execute("DROP TABLE foo")'),
    ("raw DROP COLUMN", 'op.execute("ALTER TABLE foo DROP COLUMN bar")'),
    ("raw DROP POLICY", 'op.execute("DROP POLICY foo ON bar")'),
    ("raw DROP SCHEMA", 'op.execute("DROP SCHEMA old CASCADE")'),
    ("raw SET NOT NULL", 'op.execute("ALTER TABLE foo ALTER COLUMN bar SET NOT NULL")'),
    ("raw DROP DEFAULT", 'op.execute("ALTER TABLE foo ALTER COLUMN bar DROP DEFAULT")'),
    ("raw TRUNCATE", 'op.execute("TRUNCATE foo")'),
    ("UPDATE SET in op.execute", 'op.execute("UPDATE foo SET bar = 1")'),
    ("DELETE FROM in op.execute", 'op.execute("DELETE FROM foo WHERE id = 1")'),
    ("bare UPDATE SET", "UPDATE foo SET bar = 1"),
    ("bare DELETE FROM", "DELETE FROM foo WHERE id = 1"),
]


@pytest.mark.parametrize("label,snippet", _DESTRUCTIVE_FIXTURES,
                         ids=[name for name, _ in _DESTRUCTIVE_FIXTURES])
def test_destructive_regex_catches_pattern(label, snippet):
    """Every entry in DESTRUCTIVE_FIXTURES must match at least one pattern."""
    assert _DESTRUCTIVE_RE.search(snippet), (
        f"Regex did not match: {label!r} -> {snippet!r}. "
        "If this pattern is not destructive, remove it. If it is, add "
        "a regex for it to DESTRUCTIVE_PATTERNS."
    )


_BENIGN_FIXTURES: list[tuple[str, str]] = [
    ("create_table", "op.create_table('t')"),
    ("add_column", "op.add_column('t', sa.Column('c', sa.String))"),
    ("create_index", "op.create_index('ix_x', 't', ['c'])"),
    ("create_unique_constraint", "op.create_unique_constraint('uq_x', 't', ['c'])"),
    (
        "CREATE POLICY only",
        'op.execute("CREATE POLICY foo ON bar FOR SELECT USING (true)")',
    ),
]


@pytest.mark.parametrize("label,snippet", _BENIGN_FIXTURES,
                         ids=[name for name, _ in _BENIGN_FIXTURES])
def test_destructive_regex_does_not_match_benign(label, snippet):
    """Sanity: benign operations should not match DESTRUCTIVE_PATTERNS."""
    assert not _DESTRUCTIVE_RE.search(snippet), (
        f"Regex falsely matched benign op: {label!r} -> {snippet!r}"
    )


def test_ack_marker_regex_accepts_expected_forms():
    """The `# destructive:` ack comment must match common formattings."""
    valid = [
        "# destructive: dropping obsolete column",
        "   # destructive: idempotent policy swap",
        "#destructive: no space is also fine",
        "# Destructive: case-insensitive",
    ]
    for line in valid:
        assert ACK_MARKER_RE.search(line), f"Expected match: {line!r}"

    invalid = [
        "# note: this is destructive",  # not leading
        "op.execute('destructive stuff')",  # no comment prefix
    ]
    for line in invalid:
        assert not ACK_MARKER_RE.search(line), f"Expected no match: {line!r}"


def test_baseline_is_excluded_from_scan():
    """The 0001 baseline revision is empty by design and exempt."""
    paths = [p.name for p in _iter_revision_files()]
    assert not any(p.startswith("0001_baseline") for p in paths), (
        f"Baseline should not be in scanned file list: {paths}"
    )


def test_fixture_ack_flow_integration(tmp_path, monkeypatch):
    """End-to-end: a synthetic revision file with a destructive op but no
    ack triggers an offender report; adding the ack suppresses it."""
    fake_versions = tmp_path / "versions"
    fake_versions.mkdir()
    bad = fake_versions / "0002_drops_a_column.py"
    bad.write_text(textwrap.dedent('''
        """fake revision"""
        def upgrade():
            op.drop_column("t", "c")
    '''))

    monkeypatch.setattr(
        "tests.test_alembic_destructive_ops.VERSIONS_DIR",
        fake_versions,
    )
    # With no ack, _iter_revision_files returns the fake file,
    # and the destructive regex matches. Simulate the core assertion.
    text = bad.read_text()
    assert _DESTRUCTIVE_RE.search(text)
    assert ACK_MARKER_RE.search(text) is None

    # Adding the ack comment should suppress.
    bad.write_text(bad.read_text() + "\n# destructive: testing\n")
    text = bad.read_text()
    assert _DESTRUCTIVE_RE.search(text)
    assert ACK_MARKER_RE.search(text) is not None
```

- [ ] **Step 3: Run the test and verify ALL pass**

```bash
source venv/bin/activate
python -m pytest tests/test_alembic_destructive_ops.py -v
```

Expected output: all parametrised tests pass, plus the 4 standalone tests. If any `test_destructive_regex_catches_pattern` case FAILS, add the missing pattern to `DESTRUCTIVE_PATTERNS` and retry.

- [ ] **Step 4: Commit**

```bash
git add tests/test_alembic_destructive_ops.py pyproject.toml
git commit -m "feat: CI scanner — destructive Alembic ops require ack comment"
```

---

## Task 9: Write cutoff-policy test (freezes backend/database/)

**Files:**
- Create: `tests/test_cutoff_policy.py`
- Create: `backend/database/CUTOFF.md`

- [ ] **Step 1: Write the CUTOFF.md notice**

Create `backend/database/CUTOFF.md`:

```markdown
# backend/database/ is frozen

This directory holds Graider's pre-Alembic schema artifacts:

- `supabase_schema.sql`, `supabase_teacher_schema.sql`, etc. — base schema
- `migration_YYYY_MM_DD_*.sql` — hand-authored forward migrations
- `rollback_YYYY_MM_DD_*.sql` — corrective forward scripts (misleading name; see the spec)
- `verify_YYYY_MM_DD_*.sql` — post-apply health checks

**As of the commit that introduced `backend/migrations/` to `main`, this
directory is frozen.** No new files, no edits to existing files. All
forward schema changes are Alembic revisions under
`backend/migrations/versions/`.

**Why frozen and not deleted:** these files are the historical record of
live's current schema shape. Deleting them would make drift
investigations (like the 2026-04-18 Phase 4.2 audit) impossible.

**Enforcement:** `tests/test_cutoff_policy.py` fails CI if any file in
this directory is added, modified, or deleted on a branch.

**Design spec:**
`docs/superpowers/specs/2026-04-18-alembic-migration-tooling-design.md`
```

- [ ] **Step 2: Write the cutoff-policy test**

Create `tests/test_cutoff_policy.py`:

```python
"""CI guardrail: freeze backend/database/ against new or modified files.

Once this test lands on main, backend/database/ becomes a historical
archive. All forward schema work is an Alembic revision under
backend/migrations/versions/.

The test compares the HEAD tree to origin/main. It checks only files
under backend/database/ (any extension). A failure indicates that either:
  - a new file was added (policy violation — use Alembic instead), or
  - an existing file was modified (policy violation — historical
    artifacts are frozen), or
  - an existing file was deleted (policy violation — historical
    artifacts are not removable).

Rationale lives in:
  backend/database/CUTOFF.md
  docs/superpowers/specs/2026-04-18-alembic-migration-tooling-design.md

Local runs (with no origin/main to diff against) skip gracefully so
developers who check out a branch without a remote can still run pytest.
"""
from __future__ import annotations

import pathlib
import subprocess

import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
FROZEN_DIR = "backend/database"


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def _origin_main_available() -> bool:
    out = _git("rev-parse", "--verify", "--quiet", "origin/main")
    return bool(out.strip())


@pytest.fixture(scope="module")
def changed_paths() -> list[str]:
    if not _origin_main_available():
        pytest.skip(
            "origin/main not available — cutoff policy only enforced in "
            "CI and when the branch tracks a remote main."
        )
    # A..B: changes on B since it diverged from A.
    diff = _git("diff", "--name-status", "origin/main...HEAD")
    rows = [line.split("\t") for line in diff.splitlines() if line.strip()]
    return [
        f"{status}\t{path}"
        for status, *rest in rows
        for path in rest
    ]


def test_no_new_files_under_backend_database(changed_paths):
    offenders = [
        row
        for row in changed_paths
        if row.startswith("A\t") and row.split("\t")[1].startswith(f"{FROZEN_DIR}/")
    ]
    assert not offenders, (
        f"New files added under {FROZEN_DIR}/ — this directory is frozen. "
        "All forward schema changes must be Alembic revisions under "
        "backend/migrations/versions/. See backend/database/CUTOFF.md.\n"
        + "\n".join(offenders)
    )


def test_no_modified_files_under_backend_database(changed_paths):
    offenders = [
        row
        for row in changed_paths
        if row.startswith("M\t") and row.split("\t")[1].startswith(f"{FROZEN_DIR}/")
    ]
    assert not offenders, (
        f"Files under {FROZEN_DIR}/ were modified — historical artifacts "
        "are frozen. Forward-fix via an Alembic revision instead.\n"
        + "\n".join(offenders)
    )


def test_no_deleted_files_under_backend_database(changed_paths):
    offenders = [
        row
        for row in changed_paths
        if row.startswith("D\t") and row.split("\t")[1].startswith(f"{FROZEN_DIR}/")
    ]
    assert not offenders, (
        f"Files under {FROZEN_DIR}/ were deleted — historical artifacts "
        "are permanent.\n"
        + "\n".join(offenders)
    )


def test_cutoff_marker_exists():
    """The CUTOFF.md readme is the human entry point — must stay present."""
    path = REPO_ROOT / FROZEN_DIR / "CUTOFF.md"
    assert path.exists(), (
        f"{path} must exist to document the directory freeze. If you "
        "genuinely need to relocate the freeze marker, update "
        "tests/test_cutoff_policy.py at the same time."
    )
```

- [ ] **Step 3: Run the test**

```bash
source venv/bin/activate
python -m pytest tests/test_cutoff_policy.py -v
```

Expected behavior:
- `test_cutoff_marker_exists` passes.
- The three diff-based tests either pass (if origin/main is fetched and the branch's only `backend/database/` change is adding `CUTOFF.md` — which the test will flag as `A`) or **fail**, because adding `CUTOFF.md` IS an `A\tbackend/database/CUTOFF.md` row.

That means **the first run will fail on its own CUTOFF.md addition** — correctly. The test is self-consistent: CUTOFF.md is itself a new file under backend/database/.

**Resolution:** add `CUTOFF.md` to the explicit allowlist in the test. Update `test_no_new_files_under_backend_database`:

Edit this block:
```python
    offenders = [
        row
        for row in changed_paths
        if row.startswith("A\t") and row.split("\t")[1].startswith(f"{FROZEN_DIR}/")
    ]
```

Replace with:
```python
    ALLOWED_NEW = {f"{FROZEN_DIR}/CUTOFF.md"}
    offenders = [
        row
        for row in changed_paths
        if row.startswith("A\t")
        and row.split("\t")[1].startswith(f"{FROZEN_DIR}/")
        and row.split("\t")[1] not in ALLOWED_NEW
    ]
```

- [ ] **Step 4: Re-run and verify**

```bash
python -m pytest tests/test_cutoff_policy.py -v
```

Expected: all tests pass (the diff tests skip if origin/main is not fetched locally; that's fine — CI will have it).

- [ ] **Step 5: Commit**

```bash
git add tests/test_cutoff_policy.py backend/database/CUTOFF.md
git commit -m "feat: CI guardrail — freeze backend/database/ after Alembic cutoff"
```

---

## Task 10: Update railway.json with preDeployCommand and healthcheck

**Files:**
- Modify: `railway.json`

- [ ] **Step 1: Read current railway.json**

Current content (verified in Task 0):

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "cd backend && gunicorn app:app --bind 0.0.0.0:$PORT",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

- [ ] **Step 2: Replace with updated version**

Replace the entire `railway.json` contents with:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "preDeployCommand": "alembic upgrade head",
    "startCommand": "cd backend && gunicorn app:app --bind 0.0.0.0:$PORT",
    "healthcheckPath": "/healthz",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

- [ ] **Step 3: Validate the JSON is parseable**

```bash
python -c "import json; json.load(open('railway.json'))"
```

Expected: no output (i.e., no parse error).

- [ ] **Step 4: Commit**

```bash
git add railway.json
git commit -m "config: Railway preDeployCommand runs alembic upgrade head + healthcheck"
```

---

## Task 11: Update .env.example

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Append the new env var**

Open `.env.example` and append at the bottom:

```
# ---------------------------------------------------------------------
# Alembic migration tooling (Phase 4 follow-on, 2026-04-18)
# ---------------------------------------------------------------------
# Postgres connection string used ONLY by the `alembic` CLI and by the
# Railway preDeployCommand. Do NOT point this at the transaction
# pooler — Alembic requires session-level connection semantics. Use
# direct connection if Railway can reach Supabase via IPv4/IPv6 cleanly,
# otherwise use Supabase's session pooler. See:
#   docs/superpowers/specs/2026-04-18-alembic-migration-tooling-design.md
ALEMBIC_DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/graider
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: .env.example — document ALEMBIC_DATABASE_URL"
```

---

## Task 12: Local end-to-end smoke test

**Files:**
- None (verification-only task)

- [ ] **Step 1: Start a local Postgres via Docker**

```bash
docker run -d --name graider-alembic-smoke \
  -e POSTGRES_PASSWORD=smoke \
  -e POSTGRES_DB=smoke \
  -p 5432:5432 \
  postgres:15-alpine

# Wait for readiness
until docker exec graider-alembic-smoke pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done
```

- [ ] **Step 2: Seed the auth stubs**

```bash
docker exec -i graider-alembic-smoke psql -U postgres -d smoke -v ON_ERROR_STOP=1 < .github/ci/supabase_stubs.sql
```

Expected: `CREATE SCHEMA` + 4x `CREATE FUNCTION` — no errors.

- [ ] **Step 3: Run alembic upgrade head**

```bash
export ALEMBIC_DATABASE_URL=postgresql+psycopg://postgres:smoke@localhost:5432/smoke
source venv/bin/activate
alembic upgrade head
```

Expected output: `Running upgrade  -> 0001_baseline_existing_live_schema, Baseline — existing live schema at Alembic introduction.`

- [ ] **Step 4: Verify current revision**

```bash
alembic current --verbose
```

Expected: prints `0001_baseline_existing_live_schema` with `(head)` notation.

- [ ] **Step 5: Verify alembic_version table exists in Postgres**

```bash
docker exec graider-alembic-smoke psql -U postgres -d smoke -c "SELECT version_num FROM alembic_version;"
```

Expected: returns `0001_baseline_existing_live_schema`.

- [ ] **Step 6: Clean up**

```bash
unset ALEMBIC_DATABASE_URL
docker stop graider-alembic-smoke
docker rm graider-alembic-smoke
```

- [ ] **Step 7: No commit for this task — verification only**

If any step above fails, fix the root cause in the relevant task before continuing.

---

## Task 13: Run the full test suite

**Files:**
- None (verification-only)

- [ ] **Step 1: Run the full suite**

```bash
source venv/bin/activate
FLASK_ENV=testing python -m pytest -q --no-header
```

Expected: `N passed, K skipped` with **zero failures**. The new tests
(`test_alembic_destructive_ops.py`, `test_cutoff_policy.py`) must pass.
The existing 1550+ tests must still pass.

- [ ] **Step 2: Run just the new tests with -v for explicit confirmation**

```bash
python -m pytest tests/test_alembic_destructive_ops.py tests/test_cutoff_policy.py -v --no-header
```

Expected: every case passes (or the cutoff tests skip if origin/main isn't fetched — that's fine locally).

---

## Task 14: Push branch and open PR

**Files:**
- None (git operations)

- [ ] **Step 1: Push the branch**

```bash
git push -u origin feat/alembic-migration-tooling
```

- [ ] **Step 2: Open a PR**

```bash
gh pr create --title "feat: Alembic migration tooling (Phase 4 follow-on)" --body "$(cat <<'EOF'
## Summary

Introduces Alembic as the sole forward path for Graider schema changes, applied automatically as a Railway `preDeployCommand`. Closes the drift-prevention gap that surfaced in PR #101 (Phase 4.2 RLS reconciliation).

## What's in this PR

- `alembic.ini` + `backend/migrations/` scaffolding
- `0001_baseline_existing_live_schema.py` — no-op anchor
- `backend/database/CUTOFF.md` — freeze notice
- `.github/ci/supabase_stubs.sql` — auth schema stubs for CI
- `.github/workflows/ci.yml` — `Migrations Smoke` job
- `railway.json` — `preDeployCommand: "alembic upgrade head"` + `healthcheckPath: "/healthz"`
- `tests/test_alembic_destructive_ops.py` — destructive-op ack requirement
- `tests/test_cutoff_policy.py` — freeze enforcement on `backend/database/`
- `requirements.txt` — `alembic>=1.13,<2` + `psycopg[binary]>=3.2,<4`
- `.env.example` — `ALEMBIC_DATABASE_URL` placeholder

## Design decisions

See `docs/superpowers/specs/2026-04-18-alembic-migration-tooling-design.md` for the full brainstorm + Codex-reconciled spec. Highlights:

- Forward-only in production (`downgrade()` raises by default; recovery = code revert + corrective forward migration)
- Expand-contract discipline for destructive changes (separate PR + separate deploy)
- Session pooler, not transaction pooler
- `transaction_per_migration=True` in `env.py`
- Strict one-autocommit-op-per-revision rule for `CREATE INDEX CONCURRENTLY` / `ALTER TYPE ADD VALUE`

## Operator steps (before merge)

1. Set `ALEMBIC_DATABASE_URL` on the Railway web service — Supabase session pooler URL.
2. Set the same env var on your workstation, one-off:
   ```bash
   ALEMBIC_DATABASE_URL='<session-pooler-url>' alembic stamp 0001_baseline_existing_live_schema
   ```
3. Verify:
   ```bash
   ALEMBIC_DATABASE_URL='<session-pooler-url>' alembic current
   # → 0001_baseline_existing_live_schema (head)
   ```
4. Merge this PR. Railway deploys. `alembic upgrade head` runs as `preDeployCommand` and no-ops (already at head).

## Test plan

- [x] Local Docker Postgres smoke: `alembic upgrade head` → `0001_...`, `alembic current` confirms
- [x] `tests/test_alembic_destructive_ops.py` — all destructive patterns + self-tests pass
- [x] `tests/test_cutoff_policy.py` — CUTOFF.md present, freeze enforced against origin/main diff
- [x] Full test suite green
- [ ] CI migrations-smoke job succeeds against GitHub Actions Postgres service
- [ ] After merge: operator verifies `alembic current` in prod shows the baseline
- [ ] Post-deploy: next schema change lands as `0002_<slug>.py`

## Out of scope (deferred)

- Staging environment
- SQLAlchemy models / autogenerate
- Rebaseline from live (would enable fresh-DB bootstrap)
- Phase 4.2 PR2 (behavior/LTI/OneRoster RLS)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Watch CI and confirm green**

```bash
gh pr checks --watch
```

Expected: `Backend Tests`, `Frontend Build`, `Migrations Smoke` all pass.

- [ ] **Step 4: Do NOT merge yet**

Merging is the operator's responsibility after completing the stamp step. Return control to the user with the PR URL.

---

## Self-review checklist

**1. Spec coverage.** Every spec section has a task:

- § Architecture file inventory → Task 1 (requirements) + Task 2 (alembic.ini) + Task 3 (env.py) + Task 4 (script.py.mako) + Task 5 (0001) + Task 6 (stubs) + Task 7 (CI job) + Task 9 (CUTOFF.md) + Task 10 (railway.json) + Task 11 (.env.example)
- § Baseline → Task 5
- § Deployment flow (Railway) → Task 10
- § Connection string (session pooler, ALEMBIC_DATABASE_URL) → Task 3 (env.py reads it) + Task 11 (.env.example documents it) + PR body (operator sets on Railway)
- § CI smoke test (postgres service, supabase_stubs.sql, apply + current) → Task 6 + Task 7
- § Forward migration policy (forward-only downgrade default) → Task 4 (template) + Task 5 (baseline)
- § Mechanical enforcement — destructive-op CI scan → Task 8
- § Autocommit-only DDL policy → Task 3 (env.py sets `transaction_per_migration=True`) + Task 4 (template carries the policy comment placeholder)
- § Cutoff rule + CUTOFF.md + cutoff-policy test → Task 9
- § Rollout sequence → PR body instructs operator on steps 2–5; this plan produces the PR for step 1

**2. Placeholder scan.** No TBD/TODO/placeholder strings. Every code block has complete content.

**3. Type consistency.** Every file path matches across tasks (`backend/migrations/`, `tests/test_alembic_destructive_ops.py`, etc.). The `DESTRUCTIVE_PATTERNS` list in Task 8 matches the spec regex list exactly. `ACK_MARKER` = `# destructive:` consistently. `ALEMBIC_DATABASE_URL` used consistently across `env.py`, `.env.example`, CI workflow, and PR body.

**4. Bootstrap ordering.** Task 3 creates `__init__.py` + `env.py` before Task 4 creates the Mako template (Alembic needs `env.py` present to run `alembic revision`). Task 5 creates the baseline after Task 4 — because Task 5's verification uses `alembic heads` which reads script_location. Task 8 tests the regex against in-memory fixtures, so it doesn't depend on real revisions existing. Task 9 tests operate against git, so `CUTOFF.md` must be staged and committed BEFORE running the test — which Step 5 does.

**5. No premature abstraction.** The pyproject.toml allowlist is added empty-list only (so the test doesn't hard-code to "no allowlist exists"). Not used today; hook for emergency exemption.

Plan is consistent; no gaps detected.
