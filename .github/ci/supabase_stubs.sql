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
