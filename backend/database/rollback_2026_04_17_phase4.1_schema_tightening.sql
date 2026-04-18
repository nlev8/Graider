-- Phase 4.1 schema tightening — ROLLBACK (2026-04-17)
--
-- Reverts every change in migration_2026_04_17_phase4.1_schema_tightening.sql.
-- Idempotent. Safe to run against a DB where the migration was never applied.

-- =========================================================================
-- SECTION 1 — Revert submissions.status CHECK + NOT NULL
-- =========================================================================
ALTER TABLE submissions DROP CONSTRAINT IF EXISTS submissions_status_check;
ALTER TABLE submissions ALTER COLUMN status DROP NOT NULL;

-- =========================================================================
-- SECTION 2 — Drop student_submissions reclaim index
-- =========================================================================
DROP INDEX IF EXISTS idx_student_submissions_status_started;
