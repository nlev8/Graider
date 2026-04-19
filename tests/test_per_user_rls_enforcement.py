"""Integration test — prove Phase 4.5 actually isolates teacher data via RLS.

Spins up Postgres via testcontainers, creates the auth schema stub (so
auth.uid() references parse), applies the Graider schema files that define
behavior_sessions + its RLS policy, seeds two teachers with rows, and
asserts each teacher sees only their own row when queried under the
`authenticated` role with auth.uid() rewired to impersonate them.

This mirrors what the real per-user Supabase client does at the HTTP
layer: PostgREST reads the JWT, sets role=authenticated, and policies
evaluate auth.uid() against teacher_id.

Second test round-trips a minted HS256 JWT through
backend/auth.py:validate_token() to confirm the JWT shape we use here
is the same shape Graider accepts in production.

Skipped if docker is unavailable (local dev without Docker Desktop).
"""
from __future__ import annotations

import os
import pathlib
import subprocess
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# Order matters: behavior_sessions FKs classes + students from supabase_schema.sql,
# and supabase_schema.sql has an ALTER on student_submissions (defined in
# supabase_student_portal_schema.sql). Mirrors tests/test_rls_migration_applies.py.
SCHEMA_APPLY_ORDER = [
    "supabase_student_portal_schema.sql",
    "backend/database/supabase_schema.sql",
    "supabase_behavior_schema.sql",
]

# Minimal auth schema stub so CREATE POLICY references to auth.uid() parse.
# auth.uid() returns UUID (matches Supabase's real signature). Graider's
# behavior policy is `auth.uid() = teacher_id` with teacher_id UUID.
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

DO $$ BEGIN
  CREATE ROLE authenticated NOLOGIN;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Supabase's realtime publication exists in prod; plain Postgres doesn't
-- have it. supabase_behavior_schema.sql does ALTER PUBLICATION on this
-- name at the end. Create an empty placeholder so the ALTER succeeds.
DO $$ BEGIN
  CREATE PUBLICATION supabase_realtime;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
"""


def _docker_available() -> bool:
    try:
        subprocess.run(["docker", "ps"], capture_output=True, timeout=5, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


_DOCKER_SKIP = pytest.mark.skipif(
    not _docker_available(),
    reason="docker unavailable; RLS integration test requires Postgres container",
)


@pytest.fixture(scope="module")
def prepared_db():
    """Spin up Postgres 15, apply auth stub + schema files, yield a libpq URL."""
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers[postgres] not installed")
    try:
        import psycopg2
    except ImportError:
        pytest.skip("psycopg2 not installed; run `pip install -r requirements-dev.txt`")

    with PostgresContainer("postgres:15-alpine") as pg:
        libpq_url = pg.get_connection_url().replace("postgresql+psycopg2", "postgresql")
        conn = psycopg2.connect(libpq_url)
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute(AUTH_SCHEMA_STUB)

        for rel_path in SCHEMA_APPLY_ORDER:
            sql_path = REPO_ROOT / rel_path
            if not sql_path.exists():
                pytest.fail(f"Schema file not found: {rel_path}")
            sql_content = sql_path.read_text(encoding="utf-8")
            try:
                cur.execute(sql_content)
            except psycopg2.Error as e:
                pytest.fail(
                    f"Schema file {rel_path} failed to apply to fresh Postgres: {e}"
                )

        # Grant the authenticated role access so RLS is the only gatekeeper.
        cur.execute("GRANT USAGE ON SCHEMA public TO authenticated;")
        cur.execute("GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;")
        cur.execute("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated;")

        conn.close()
        yield libpq_url


def _mint_jwt(user_id: str, secret: str) -> str:
    """Return an HS256 JWT matching backend/auth.py:validate_token() (aud='authenticated')."""
    now = datetime.now(tz=timezone.utc)
    return pyjwt.encode(
        {
            "sub": user_id,
            "aud": "authenticated",
            "role": "authenticated",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        secret,
        algorithm="HS256",
    )


@_DOCKER_SKIP
def test_rls_isolates_teachers_via_per_user_role(prepared_db):
    """Under SET ROLE authenticated with auth.uid() impersonating teacher X,
    the query returns only rows where teacher_id = X, proving RLS is enforced.
    """
    import psycopg2

    teacher_a = "11111111-1111-1111-1111-111111111111"
    teacher_b = "22222222-2222-2222-2222-222222222222"

    # Seed: each teacher owns one behavior_sessions row. Seeding happens as
    # the owner role (postgres/superuser), which bypasses RLS.
    conn = psycopg2.connect(prepared_db)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO behavior_sessions (teacher_id, date, period, started_at) "
        "VALUES (%s, CURRENT_DATE, '1', NOW()), (%s, CURRENT_DATE, '1', NOW());",
        (teacher_a, teacher_b),
    )

    # Superuser (no role switch) sees both rows — RLS doesn't apply to owner.
    cur.execute("SELECT count(*) FROM behavior_sessions;")
    assert cur.fetchone()[0] == 2, "superuser baseline should see both rows"

    def _query_as_teacher(teacher_uuid: str) -> int:
        # Rewire auth.uid() to return this teacher, then switch to
        # the authenticated role (which is what PostgREST uses for
        # JWT-bearing requests). Policies evaluate auth.uid() = teacher_id.
        cur.execute(
            f"CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid "
            f"LANGUAGE sql STABLE AS $$ SELECT '{teacher_uuid}'::uuid; $$;"
        )
        cur.execute("SET LOCAL ROLE authenticated;")
        cur.execute("SELECT count(*) FROM behavior_sessions;")
        count = cur.fetchone()[0]
        cur.execute("RESET ROLE;")
        return count

    a_count = _query_as_teacher(teacher_a)
    b_count = _query_as_teacher(teacher_b)

    # Reset the stub so the module fixture isn't left mutated.
    cur.execute(
        "CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid "
        "LANGUAGE sql STABLE AS $$ SELECT NULL::uuid; $$;"
    )

    conn.close()

    assert a_count == 1, f"teacher A should see exactly their own row; got {a_count}"
    assert b_count == 1, f"teacher B should see exactly their own row; got {b_count}"


def test_validate_token_accepts_minted_jwt(monkeypatch):
    """Sanity: our minted JWT shape round-trips through validate_token()
    with the same secret. Proves the JWT we'd send is one the server accepts.

    Forces the HS256 path by clearing SUPABASE_URL (disables the JWKS client
    that would otherwise try to validate against the real Supabase ES256 keys).
    """
    secret = "test-jwt-secret-at-least-32-chars-yes-ok"
    token = _mint_jwt("user-xyz", secret)

    monkeypatch.setenv("SUPABASE_JWT_SECRET", secret)
    monkeypatch.delenv("SUPABASE_URL", raising=False)

    import backend.auth as auth_module
    monkeypatch.setattr(auth_module, "_jwks_client", None)

    payload = auth_module.validate_token(token)
    assert payload is not None, "validate_token returned None on valid token"
    assert payload.get("sub") == "user-xyz"
    assert payload.get("aud") == "authenticated"
