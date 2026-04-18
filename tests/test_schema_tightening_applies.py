"""Phase 4.1 schema tightening — smoke test.

Spins up Postgres 15 via testcontainers, applies every Graider base schema
file plus the new schema-tightening migration, then asserts:

  1. Migration applies cleanly (no SQL errors)
  2. submissions.status is NOT NULL with CHECK matching Celery lifecycle states
  3. submissions rejects typo'd status values (INSERT with 'quened' fails)
  4. idx_student_submissions_status_started exists

Runtime: ~15 seconds (container startup dominates). Skipped if Docker or
testcontainers is unavailable. CI runs Docker; local dev without Docker
Desktop skips cleanly.

Why a separate file from tests/test_rls_migration_applies.py: that file
is RLS-focused (pg_policies assertions). Mixing schema-tightening
assertions there would dilute its purpose. Both tests share the same
SCHEMA_APPLY_ORDER pattern.
"""
from __future__ import annotations

import pathlib
import subprocess

import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# Same ordering as test_rls_migration_applies.py — portal schema first
# because supabase_schema.sql ALTERs student_submissions from that file.
SCHEMA_APPLY_ORDER = [
    "supabase_student_portal_schema.sql",
    "backend/database/supabase_schema.sql",
    "backend/database/supabase_teacher_schema.sql",
    "supabase_submission_confirmations.sql",
    "supabase_roster_rls.sql",
]

MIGRATION_FILE = "backend/database/migration_2026_04_17_phase4.1_schema_tightening.sql"

EXPECTED_SUBMISSIONS_STATUS_VALUES = {"queued", "grading_in_progress", "graded", "failed"}

AUTH_SCHEMA_STUB = """
CREATE SCHEMA IF NOT EXISTS auth;
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
LANGUAGE sql STABLE AS $$ SELECT NULL::uuid; $$;
CREATE OR REPLACE FUNCTION auth.jwt() RETURNS jsonb
LANGUAGE sql STABLE AS $$ SELECT '{}'::jsonb; $$;
CREATE OR REPLACE FUNCTION auth.role() RETURNS text
LANGUAGE sql STABLE AS $$ SELECT NULL::text; $$;
"""


def _docker_available() -> bool:
    try:
        subprocess.run(["docker", "ps"], capture_output=True, timeout=5, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


@pytest.fixture(scope="module")
def postgres_container():
    if not _docker_available():
        pytest.skip("Docker not available; smoke test requires testcontainers")
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers[postgres] not installed; run `pip install -r requirements-dev.txt`")
    try:
        import psycopg2
    except ImportError:
        pytest.skip("psycopg2 not installed; run `pip install -r requirements-dev.txt`")

    with PostgresContainer("postgres:15-alpine") as pg:
        conn_url = pg.get_connection_url().replace("postgresql+psycopg2", "postgresql")
        conn = psycopg2.connect(conn_url)
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute(AUTH_SCHEMA_STUB)
        for rel_path in SCHEMA_APPLY_ORDER:
            sql_content = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
            try:
                cur.execute(sql_content)
            except psycopg2.Error as e:
                pytest.fail(f"Base schema file {rel_path} failed to apply: {e}")

        yield cur


def test_migration_applies_without_errors(postgres_container):
    """The schema-tightening migration must apply cleanly on top of the base schema."""
    cur = postgres_container
    migration_sql = (REPO_ROOT / MIGRATION_FILE).read_text(encoding="utf-8")
    import psycopg2
    try:
        cur.execute(migration_sql)
    except psycopg2.Error as e:
        pytest.fail(f"Schema tightening migration failed: {e}")


def test_submissions_status_is_not_null(postgres_container):
    """After migration, submissions.status must be NOT NULL."""
    cur = postgres_container
    cur.execute(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'submissions' "
        "  AND column_name = 'status';"
    )
    row = cur.fetchone()
    assert row is not None, "submissions.status column not found"
    assert row[0] == "NO", f"Expected NOT NULL; got is_nullable={row[0]}"


def test_submissions_status_check_rejects_typo(postgres_container):
    """Inserting a typo'd status should fail after the migration."""
    cur = postgres_container
    import psycopg2

    # Minimal insert — submissions requires assessment_id + join_code + student_name + answers
    # Create a parent published_assessments row first (needed for FK).
    # Required NOT NULL columns: join_code, title, assessment.
    cur.execute(
        "INSERT INTO published_assessments (teacher_id, assessment, join_code, title) "
        "VALUES (%s, %s::jsonb, %s, %s) "
        "RETURNING id;",
        ("test-teacher", '{}', "TEST01", "Test Assessment"),
    )
    assessment_id = cur.fetchone()[0]

    # Valid status — should succeed
    cur.execute(
        "INSERT INTO submissions (assessment_id, join_code, student_name, answers, status) "
        "VALUES (%s, %s, %s, %s::jsonb, %s);",
        (assessment_id, "TEST01", "Test Student", '{}', "queued"),
    )

    # Typo'd status — should fail with check violation
    with pytest.raises(psycopg2.errors.CheckViolation):
        cur.execute(
            "INSERT INTO submissions (assessment_id, join_code, student_name, answers, status) "
            "VALUES (%s, %s, %s, %s::jsonb, %s);",
            (assessment_id, "TEST01", "Typo Student", '{}', "quened"),
        )


def test_submissions_status_accepts_all_celery_lifecycle_values(postgres_container):
    """Every Celery lifecycle state must be accepted by the CHECK."""
    cur = postgres_container
    # Re-use the test-teacher assessment from the previous test (module scope).
    cur.execute("SELECT id FROM published_assessments LIMIT 1;")
    row = cur.fetchone()
    assert row is not None, "published_assessments empty — prior test did not seed"
    assessment_id = row[0]

    for i, status in enumerate(sorted(EXPECTED_SUBMISSIONS_STATUS_VALUES)):
        cur.execute(
            "INSERT INTO submissions (assessment_id, join_code, student_name, answers, status) "
            "VALUES (%s, %s, %s, %s::jsonb, %s);",
            (assessment_id, f"LIFE{i:02d}", f"Lifecycle {status}", '{}', status),
        )


def test_student_submissions_reclaim_index_exists(postgres_container):
    """idx_student_submissions_status_started must exist on (status, grading_started_at)."""
    cur = postgres_container
    cur.execute(
        "SELECT indexdef FROM pg_indexes "
        "WHERE schemaname = 'public' "
        "  AND indexname = 'idx_student_submissions_status_started';"
    )
    row = cur.fetchone()
    assert row is not None, "idx_student_submissions_status_started index not found"
    indexdef = row[0]
    # Verify the index covers (status, grading_started_at)
    assert "status" in indexdef and "grading_started_at" in indexdef, (
        f"Index does not cover expected columns: {indexdef}"
    )


def test_rollback_reverts_changes(postgres_container):
    """Applying the paired rollback removes the CHECK + index + NOT NULL."""
    cur = postgres_container
    rollback_sql = (
        REPO_ROOT / "backend/database/rollback_2026_04_17_phase4.1_schema_tightening.sql"
    ).read_text(encoding="utf-8")
    import psycopg2
    try:
        cur.execute(rollback_sql)
    except psycopg2.Error as e:
        pytest.fail(f"Rollback failed to apply: {e}")

    # CHECK constraint should be gone
    cur.execute(
        "SELECT conname FROM pg_constraint "
        "WHERE conname = 'submissions_status_check';"
    )
    assert cur.fetchone() is None, "submissions_status_check constraint should be removed"

    # Column should be nullable again
    cur.execute(
        "SELECT is_nullable FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'submissions' "
        "  AND column_name = 'status';"
    )
    assert cur.fetchone()[0] == "YES", "submissions.status should be nullable after rollback"

    # Index should be gone
    cur.execute(
        "SELECT indexname FROM pg_indexes "
        "WHERE indexname = 'idx_student_submissions_status_started';"
    )
    assert cur.fetchone() is None, "Reclaim index should be dropped by rollback"
