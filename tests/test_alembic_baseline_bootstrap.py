"""0001 real baseline — `alembic upgrade head` from a TRULY EMPTY database
bootstraps the full live schema (no SQL files pre-applied, no stamp), and
0002 applies on top of it.

This is the Data Integrity level-8 proof ("full live schema expressed in
migrations; up tested in CI"): before PR7 the baseline was a no-op
pass-stamp and an empty-DB upgrade failed in 0002 (ALTER TABLE on a
table that no migration had created).

Docker-gated via testcontainers like
tests/test_submission_dedup_migration_applies.py — skips cleanly without
Docker. For machines without Docker, set GRAIDER_BASELINE_TEST_PG_URL to
a superuser/owner URL of a scratch Postgres 15+ cluster; the fixture
creates (and drops) a throwaway database there instead.
"""
from __future__ import annotations

import contextlib
import os
import pathlib
import subprocess
import uuid

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# Every app-owned public table the baseline must create from empty
# (live introspection 2026-06-11; excludes alembic_version).
EXPECTED_TABLES = {
    "audit_log",
    "behavior_events",
    "behavior_sessions",
    "class_students",
    "classes",
    "drafts",
    "published_assessments",
    "published_content",
    "student_history",
    "student_sessions",
    "student_submissions",
    "students",
    "submission_confirmations",
    "submissions",
    "teacher_data",
}


def _docker_available() -> bool:
    try:
        subprocess.run(["docker", "ps"], capture_output=True, timeout=5, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _upgrade_head(url: str) -> None:
    env = {**os.environ, "ALEMBIC_DATABASE_URL": url}
    r = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True,
    )
    assert r.returncode == 0, (
        f"alembic upgrade head from EMPTY database failed:\n{r.stderr}"
    )


@pytest.fixture(scope="module")
def empty_migrated_db():
    """Yield a cursor on a database migrated from EMPTY via alembic only."""
    external = os.getenv("GRAIDER_BASELINE_TEST_PG_URL")
    if external:
        yield from _migrate_on_external_cluster(external)
        return

    if not _docker_available():
        pytest.skip("Docker not available; set GRAIDER_BASELINE_TEST_PG_URL "
                    "to run against a local scratch cluster")
    try:
        from testcontainers.postgres import PostgresContainer
        import psycopg2
    except ImportError:
        pytest.skip("testcontainers[postgres]/psycopg2 not installed")

    with PostgresContainer("postgres:15-alpine") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2", "postgresql")
        _upgrade_head(url)
        conn = psycopg2.connect(url)
        conn.autocommit = True
        yield conn.cursor()
        conn.close()


def _migrate_on_external_cluster(admin_url: str):
    """Create a throwaway DB on an external cluster, migrate, drop it."""
    psycopg2 = pytest.importorskip("psycopg2")
    dbname = f"baseline_bootstrap_{uuid.uuid4().hex[:12]}"
    admin = psycopg2.connect(admin_url)
    admin.autocommit = True
    admin_cur = admin.cursor()
    admin_cur.execute(f'CREATE DATABASE "{dbname}"')
    base, _, _ = admin_url.rpartition("/")
    url = f"{base}/{dbname}"
    try:
        _upgrade_head(url)
        conn = psycopg2.connect(url)
        conn.autocommit = True
        yield conn.cursor()
        conn.close()
    finally:
        with contextlib.suppress(Exception):  # noqa: BLE001 — teardown best-effort drop
            admin_cur.execute(f'DROP DATABASE "{dbname}" WITH (FORCE)')
        admin.close()


def test_baseline_creates_all_live_tables_from_empty(empty_migrated_db):
    cur = empty_migrated_db
    cur.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
    )
    present = {row[0] for row in cur.fetchall()}
    missing = EXPECTED_TABLES - present
    assert not missing, f"Baseline did not create: {sorted(missing)}"


def test_upgrade_reaches_head_revision(empty_migrated_db):
    cur = empty_migrated_db
    cur.execute("SELECT version_num FROM alembic_version")
    assert cur.fetchone()[0] == "0002_subm_dedup"


def test_0002_applied_on_top_of_real_baseline(empty_migrated_db):
    """From empty, 0001 creates submissions/student_submissions and 0002
    must then add dedup_key + the partial unique indexes."""
    cur = empty_migrated_db
    cur.execute(
        "SELECT table_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND column_name = 'dedup_key'"
    )
    assert {r[0] for r in cur.fetchall()} == {"submissions", "student_submissions"}
    cur.execute(
        "SELECT indexname FROM pg_indexes WHERE indexname IN "
        "('uq_submissions_dedup_key', 'uq_student_submissions_dedup_key')"
    )
    assert len(cur.fetchall()) == 2


@pytest.mark.parametrize("table,constraint", [
    ("submissions", "submissions_status_check"),
    ("submissions", "unique_submission_per_student"),
    ("student_submissions", "student_submissions_status_check"),
    ("classes", "classes_teacher_clever_section_unique"),
    ("behavior_events", "behavior_events_session_id_teacher_id_fkey"),
    ("submission_confirmations", "submission_confirmations_submission_id_fkey"),
])
def test_live_constraints_expressed(empty_migrated_db, table, constraint):
    cur = empty_migrated_db
    cur.execute(
        "SELECT 1 FROM pg_constraint WHERE conname = %s "
        "AND conrelid = ('public.' || %s)::regclass",
        (constraint, table),
    )
    assert cur.fetchone() is not None, f"{table}.{constraint} missing"


@pytest.mark.parametrize("index", [
    "idx_submissions_unique_student",       # partial UNIQUE, dedup semantics
    "idx_student_submissions_unique",       # partial UNIQUE, attempt_number=1
    "idx_teacher_data_key_prefix",          # text_pattern_ops
    "idx_events_teacher_session_time",
])
def test_live_indexes_expressed(empty_migrated_db, index):
    cur = empty_migrated_db
    cur.execute("SELECT 1 FROM pg_indexes WHERE indexname = %s", (index,))
    assert cur.fetchone() is not None, f"index {index} missing"


def test_rls_enabled_but_policies_skipped_on_bare_postgres(empty_migrated_db):
    """RLS ENABLE is unconditional; policies are guarded on auth.uid()
    existing, so a bare Postgres (no Supabase auth stub) gets RLS with no
    policies rather than a failed upgrade."""
    cur = empty_migrated_db
    cur.execute(
        "SELECT count(*) FROM pg_tables WHERE schemaname = 'public' "
        "AND rowsecurity AND tablename = ANY(%s)",
        (sorted(EXPECTED_TABLES),),
    )
    assert cur.fetchone()[0] == len(EXPECTED_TABLES)
    cur.execute("SELECT count(*) FROM pg_policies WHERE schemaname = 'public'")
    assert cur.fetchone()[0] == 0


def test_join_code_trigger_live_behavior(empty_migrated_db):
    """classes_auto_join_code fills a blank join_code on INSERT (live
    trigger + function expressed by the baseline)."""
    cur = empty_migrated_db
    cur.execute(
        "INSERT INTO classes (teacher_id, name, join_code) "
        "VALUES (gen_random_uuid(), 'Baseline Smoke', '') RETURNING join_code"
    )
    code = cur.fetchone()[0]
    assert code and len(code) == 6
