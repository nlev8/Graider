-- Phase 4.1 schema tightening (2026-04-17)
--
-- Follow-up to Phase 4.1 PR0 (merged as PR #78) that added the columns:
--   submissions.status TEXT DEFAULT 'queued'
--   submissions.grading_task_id, .grading_started_at, .error_message
--   student_submissions.grading_task_id, .grading_started_at, .error_message
--
-- Codex cross-check on Phase 4.1 PR1 flagged two residual gaps:
--   1. submissions.status is nullable with no CHECK constraint. A typo'd
--      status write (e.g., 'quened' instead of 'queued') succeeds silently
--      and then evades reclaim queries that filter by status.
--   2. student_submissions has no (status, grading_started_at) index —
--      the reclaim query pattern used for submissions would be full-scan
--      on student_submissions when Phase 4.1b migrates the class-based
--      path to Celery.
--
-- This migration closes both gaps. Idempotent — safe to re-run.

-- =========================================================================
-- SECTION 1 — submissions.status: NOT NULL + CHECK constraint
-- =========================================================================
-- Allowed values match the Celery dedup / grading lifecycle:
--   queued              — initial state on row insert
--   grading_in_progress — after _claim_submission_for_grading
--   graded              — terminal success (grade_portal_submission_sync last write)
--   failed              — terminal failure (PortalGradingTask.on_failure)

-- 1a. Defensively backfill any remaining NULL status (PR0 already did this
--     but idempotency makes it safe to re-run).
UPDATE submissions SET status = 'queued' WHERE status IS NULL;

-- 1b. NOT NULL (was nullable post-PR0).
ALTER TABLE submissions ALTER COLUMN status SET NOT NULL;

-- 1c. CHECK constraint. Drop first for idempotency.
ALTER TABLE submissions DROP CONSTRAINT IF EXISTS submissions_status_check;
ALTER TABLE submissions
    ADD CONSTRAINT submissions_status_check
    CHECK (status IN ('queued', 'grading_in_progress', 'graded', 'failed'));

-- =========================================================================
-- SECTION 2 — student_submissions reclaim index
-- =========================================================================
-- Mirrors the idx_submissions_status_started index that PR0 added on
-- submissions. When Phase 4.1b migrates the class-based student portal
-- path to Celery, its reclaim query (SELECT ... WHERE status =
-- 'grading_in_progress' AND grading_started_at < now() - interval '30 min')
-- needs an index or it's a full table scan.
CREATE INDEX IF NOT EXISTS idx_student_submissions_status_started
    ON student_submissions (status, grading_started_at);

-- =========================================================================
-- Migration complete.
-- =========================================================================
-- Rollback: apply backend/database/rollback_2026_04_17_phase4.1_schema_tightening.sql
