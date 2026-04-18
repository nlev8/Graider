"""Phase 4.2 PR1 — smoke test that the RLS migration applies cleanly.

Spins up a Postgres 15 container via testcontainers, creates a minimal
`auth` schema stub (so policies referencing auth.uid() parse), applies
every Graider schema file in dependency order, then applies the PR1
migration. Asserts:

  1. Migration runs without SQL errors
  2. pg_tables.rowsecurity = true for every PR1 table
  3. pg_policies contains the expected policy names per table

Runtime: ~10-15 seconds (container startup dominates). Skipped if Docker
is unavailable (e.g., local dev without Docker Desktop) or if psycopg2
is not installed.
"""
from __future__ import annotations

import pathlib
import subprocess

import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# Order matters: parent tables must exist before tables or ALTERs that
# reference them. Key cross-file dependency:
#   backend/database/supabase_schema.sql ends with an ALTER TABLE
#   student_submissions ADD COLUMN ... block (Phase 4.1 PR0 migration).
#   student_submissions is defined in supabase_student_portal_schema.sql,
#   so portal_schema must apply BEFORE supabase_schema. Safe because
#   portal_schema has zero dependencies on supabase_schema's tables.
SCHEMA_APPLY_ORDER = [
    "supabase_student_portal_schema.sql",
    "backend/database/supabase_schema.sql",
    "backend/database/supabase_teacher_schema.sql",
    "supabase_submission_confirmations.sql",
    "supabase_roster_rls.sql",
]

MIGRATION_FILE = "backend/database/migration_2026_04_17_phase4.2_rls.sql"

# Expected policy names per PR1 table (matches migration output).
EXPECTED_POLICIES: dict[str, set[str]] = {
    "teacher_data": {"teacher_data_own"},
    "student_history": {"student_history_own"},
    "classes": {"classes_own"},
    "students": {"students_own"},
    "class_students": {"class_students_own"},
    "submissions": {
        "submissions_select_teacher",
        "submissions_update_teacher",
        "submissions_delete_teacher",
    },
    "published_assessments": {
        "published_assessments_select_teacher",
        "published_assessments_insert_teacher",
        "published_assessments_update_teacher",
        "published_assessments_delete_teacher",
    },
    "published_content": {"published_content_own"},
    "student_submissions": {"student_submissions_own"},
    "student_sessions": {"student_sessions_select_teacher"},
    "submission_confirmations": {"submission_confirmations_own"},
}

# Minimal auth schema stub so CREATE POLICY references to auth.uid() parse.
# In real Supabase this schema is provisioned automatically — auth.uid()
# returns UUID (NOT text) because it's backed by auth.users.id which is UUID.
# Graider's existing policies in supabase_roster_rls.sql rely on the UUID
# return type (`auth.uid() = teacher_id` with UUID teacher_id, no ::text cast).
# PR1's migration casts explicitly (`auth.uid()::text = teacher_id`) which
# works with either return type, but the stub must match Supabase's real
# signature so the existing policies also apply cleanly in the test container.
AUTH_SCHEMA_STUB = """
CREATE SCHEMA IF NOT EXISTS auth;

CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
LANGUAGE sql STABLE
AS $$ SELECT NULL::uuid; $$;

CREATE OR REPLACE FUNCTION auth.jwt() RETURNS jsonb
LANGUAGE sql STABLE
AS $$ SELECT '{}'::jsonb; $$;

CREATE OR REPLACE FUNCTION auth.role() RETURNS text
LANGUAGE sql STABLE
AS $$ SELECT NULL::text; $$;
"""


def _docker_available() -> bool:
    try:
        subprocess.run(["docker", "ps"], capture_output=True, timeout=5, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


@pytest.fixture(scope="module")
def postgres_container():
    """Spin up Postgres 15 and apply the auth stub + all schema files."""
    if not _docker_available():
        pytest.skip("Docker not available; smoke test requires testcontainers")

    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers[postgres] not installed")

    try:
        import psycopg2
    except ImportError:
        pytest.skip("psycopg2 not installed; run `pip install -r requirements-dev.txt`")

    with PostgresContainer("postgres:15-alpine") as pg:
        conn_url = pg.get_connection_url().replace("postgresql+psycopg2", "postgresql")
        conn = psycopg2.connect(conn_url)
        conn.autocommit = True
        cur = conn.cursor()

        # 1. Create auth schema stub (so auth.uid() references parse)
        cur.execute(AUTH_SCHEMA_STUB)

        # 2. Apply every base schema file in order
        for rel_path in SCHEMA_APPLY_ORDER:
            sql_path = REPO_ROOT / rel_path
            if not sql_path.exists():
                pytest.fail(f"Schema file not found: {rel_path}")
            sql_content = sql_path.read_text(encoding="utf-8")
            # Skip any ALTER TABLE ... ENABLE ROW LEVEL SECURITY and
            # existing CREATE POLICY blocks from base schema files — they
            # will be handled by the PR1 migration. This is done by running
            # the whole file; pre-existing policies that conflict with
            # PR1's DROP IF EXISTS are handled.
            try:
                cur.execute(sql_content)
            except psycopg2.Error as e:
                pytest.fail(
                    f"Base schema file {rel_path} failed to apply to fresh Postgres:\n"
                    f"  Error: {e}\n"
                    f"  (this indicates a pre-existing issue with the schema files, "
                    f"not necessarily a Phase 4.2 problem)"
                )

        yield cur


def test_migration_applies_without_errors(postgres_container):
    """The PR1 migration must apply to a freshly-seeded Postgres 15 instance."""
    cur = postgres_container
    migration_sql = (REPO_ROOT / MIGRATION_FILE).read_text(encoding="utf-8")
    import psycopg2
    try:
        cur.execute(migration_sql)
    except psycopg2.Error as e:
        pytest.fail(f"PR1 migration failed to apply: {e}\n\nFirst 500 chars of migration:\n{migration_sql[:500]}")


def test_every_pr1_table_has_rls_enabled_in_live_db(postgres_container):
    """After migration, pg_tables.rowsecurity = true for every PR1 table."""
    cur = postgres_container
    tables = sorted(EXPECTED_POLICIES.keys())
    cur.execute(
        "SELECT tablename, rowsecurity FROM pg_tables "
        "WHERE schemaname = 'public' AND tablename = ANY(%s);",
        (tables,),
    )
    rows = {row[0]: row[1] for row in cur.fetchall()}
    missing = [t for t in tables if t not in rows]
    assert not missing, f"Tables not found in pg_tables after migration: {missing}"
    disabled = [t for t, enabled in rows.items() if not enabled]
    assert not disabled, f"Tables with RLS disabled after migration: {disabled}"


def test_expected_policies_exist_in_live_db(postgres_container):
    """Every expected policy must be in pg_policies."""
    cur = postgres_container
    all_expected_tables = sorted(EXPECTED_POLICIES.keys())
    cur.execute(
        "SELECT tablename, policyname FROM pg_policies "
        "WHERE schemaname = 'public' AND tablename = ANY(%s);",
        (all_expected_tables,),
    )
    actual: dict[str, set[str]] = {}
    for tablename, policyname in cur.fetchall():
        actual.setdefault(tablename, set()).add(policyname)

    missing_by_table: dict[str, set[str]] = {}
    for table, expected_names in EXPECTED_POLICIES.items():
        present = actual.get(table, set())
        missing = expected_names - present
        if missing:
            missing_by_table[table] = missing

    assert not missing_by_table, (
        "Missing policies after migration:\n"
        + "\n".join(f"  {table}: {sorted(names)}" for table, names in missing_by_table.items())
    )


def test_broad_policies_dropped_in_live_db(postgres_container):
    """The tightened migration dropped these old broad policies.

    After applying the migration, pg_policies should NOT contain any
    'Anyone can ...' style policies on submissions or published_assessments.
    """
    cur = postgres_container
    cur.execute(
        "SELECT tablename, policyname FROM pg_policies "
        "WHERE schemaname = 'public' "
        "  AND tablename IN ('submissions', 'published_assessments') "
        "  AND policyname LIKE 'Anyone%%';"
    )
    offenders = cur.fetchall()
    assert not offenders, (
        f"Broad 'Anyone can ...' policies still present after PR1 migration: {offenders}. "
        f"These were supposed to be dropped by the migration."
    )
