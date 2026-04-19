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

-- ---------------------------------------------------------------------
-- CI-only stub tables for Phase 4.2 PR2 migration policies.
-- Real schema lives in live Supabase (pre-Alembic-cutoff raw SQL). For
-- CI purposes we only need tables that the RLS policies can attach to —
-- minimum columns: a PK `id` and the `teacher_id` the policy checks.
-- Keep these STUB-ONLY: do not add columns to match live unless a new
-- migration's policies require them. Loading this file against live
-- would be a no-op (CREATE TABLE IF NOT EXISTS) but strongly discouraged.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS behavior_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL
);
ALTER TABLE behavior_sessions ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS behavior_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL
);
ALTER TABLE behavior_events ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
