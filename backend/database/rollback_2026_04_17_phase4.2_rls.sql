-- Phase 4.2 PR1 — ROLLBACK (2026-04-17, revised 2026-04-18)
--
-- Reverts every change in migration_2026_04_17_phase4.2_rls.sql.
-- Idempotent. Safe to run against a DB where the migration was never
-- applied (all DROP statements use IF EXISTS).
--
-- 2026-04-18 REVISION — DRIFT-AWARE ROLLBACK
-- The original rollback assumed the migration dropped "Anyone can read"
-- anonymous policies that were present in the source-of-truth schema.
-- A drift audit against live (2026-04-18) showed those anonymous
-- policies did NOT exist on live; instead live had "Teachers manage
-- own X" policies with email-based expressions (see migration header).
--
-- This rollback therefore does NOT try to restore any prior policy
-- set. It simply drops every policy the migration installed. After
-- rollback the 11 target tables will have RLS enabled (they already
-- did before PR1) but zero teacher-scoped policies. Service-role
-- access keeps working (bypasses RLS). Any JWT-based access would
-- see zero rows.
--
-- If rollback is run against a state where PR1's drops were applied,
-- the drifted policies will have been removed too and are NOT
-- resurrected here — it's safer to re-apply the migration than to
-- restore known-buggy email-based policies. If a true drift-preserving
-- rollback is needed, copy the CREATE POLICY statements from
-- docs/superpowers/specs/2026-04-17-phase4.2-database-rls-design.md
-- (Appendix: pre-migration drift inventory, captured 2026-04-18).
--
-- What this does:
--   1. Drops every PR1-added policy on all 11+ tables
--   2. Does NOT re-enable anonymous access on submissions/
--      published_assessments (those policies never existed on live)
--   3. Does NOT disable RLS — all 11 tables had RLS before PR1 and
--      keep it after rollback

-- =========================================================================
-- SECTION 1 — Drop PR1 policies on re-verify tables
-- =========================================================================
DROP POLICY IF EXISTS teacher_data_own ON teacher_data;
DROP POLICY IF EXISTS student_history_own ON student_history;
DROP POLICY IF EXISTS classes_own ON classes;
DROP POLICY IF EXISTS students_own ON students;
DROP POLICY IF EXISTS class_students_own ON class_students;

-- =========================================================================
-- SECTION 2 — Drop PR1 policies on published_assessments
-- =========================================================================
DROP POLICY IF EXISTS published_assessments_select_teacher ON published_assessments;
DROP POLICY IF EXISTS published_assessments_insert_teacher ON published_assessments;
DROP POLICY IF EXISTS published_assessments_update_teacher ON published_assessments;
DROP POLICY IF EXISTS published_assessments_delete_teacher ON published_assessments;

-- =========================================================================
-- SECTION 3 — Drop PR1 policies on submissions
-- =========================================================================
DROP POLICY IF EXISTS submissions_select_teacher ON submissions;
DROP POLICY IF EXISTS submissions_update_teacher ON submissions;
DROP POLICY IF EXISTS submissions_delete_teacher ON submissions;

-- =========================================================================
-- SECTION 4 — Drop PR1 policies on newly-policied tables
-- (RLS left enabled — those tables had RLS before PR1 too.)
-- =========================================================================
DROP POLICY IF EXISTS published_content_own ON published_content;
DROP POLICY IF EXISTS student_submissions_own ON student_submissions;
DROP POLICY IF EXISTS student_sessions_select_teacher ON student_sessions;

-- =========================================================================
-- SECTION 5 — submission_confirmations (conditional — table may not exist)
-- =========================================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname = 'submission_confirmations'
          AND c.relkind = 'r'
    ) THEN
        EXECUTE 'DROP POLICY IF EXISTS submission_confirmations_own ON submission_confirmations';
    END IF;
END $$;

-- =========================================================================
-- Rollback complete. All 11+ tables keep RLS enabled with no policies
-- (except the originals that were not touched by PR1: this matters only
-- if Phase 4.5 JWT access is live, in which case the right move is to
-- re-apply the migration, not extend this rollback).
-- =========================================================================
