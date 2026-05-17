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
        import psycopg2  # noqa: F401
    except ImportError:
        pytest.skip("testcontainers[postgres]/psycopg2 not installed")

    import psycopg2
    with PostgresContainer("postgres:15-alpine") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2", "postgresql")
        conn = psycopg2.connect(url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(AUTH_SCHEMA_STUB)
        for rel in SCHEMA_APPLY_ORDER:
            cur.execute((REPO_ROOT / rel).read_text(encoding="utf-8"))
        env = {**os.environ, "ALEMBIC_DATABASE_URL": url}
        subprocess.run(["alembic", "stamp", "0001_baseline"], cwd=REPO_ROOT,
                        env=env, check=True, capture_output=True)
        r = subprocess.run(["alembic", "upgrade", "head"], cwd=REPO_ROOT,
                            env=env, capture_output=True, text=True)
        assert r.returncode == 0, f"alembic upgrade head failed: {r.stderr}"
        yield cur


@pytest.mark.parametrize("idx", [
    "uq_submissions_dedup_key",
    "uq_student_submissions_dedup_key",
])
def test_partial_unique_index_exists(migrated_db, idx):
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
