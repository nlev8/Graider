-- Phase 4.2 PR1 — ROLLBACK (2026-04-17)
--
-- Reverts every change in migration_2026_04_17_phase4.2_rls.sql.
-- Idempotent. Safe to run against a DB where the migration was never
-- applied (all DROP statements use IF EXISTS).
--
-- What this does:
--   1. Drops every PR1-added policy on all 11 tables
--   2. Re-creates the original permissive policies on submissions and
--      published_assessments that PR1 tightened away (these are the
--      safety fallback for a production teacher-dashboard regression)
--   3. Disables RLS on the 4 tables PR1 newly enabled
--      (published_content, student_submissions, student_sessions,
--      submission_confirmations)
--   4. Leaves existing-RLS tables (teacher_data, student_history,
--      classes, students, class_students) unchanged — those had RLS
--      before PR1 and keep it after rollback

-- =========================================================================
-- SECTION 1 — Drop PR1 policies on re-verify tables
-- =========================================================================
DROP POLICY IF EXISTS teacher_data_own ON teacher_data;
DROP POLICY IF EXISTS student_history_own ON student_history;
DROP POLICY IF EXISTS classes_own ON classes;
DROP POLICY IF EXISTS students_own ON students;
DROP POLICY IF EXISTS class_students_own ON class_students;

-- =========================================================================
-- SECTION 2 — Restore original published_assessments policies
-- =========================================================================
DROP POLICY IF EXISTS published_assessments_select_teacher ON published_assessments;
DROP POLICY IF EXISTS published_assessments_insert_teacher ON published_assessments;
DROP POLICY IF EXISTS published_assessments_update_teacher ON published_assessments;
DROP POLICY IF EXISTS published_assessments_delete_teacher ON published_assessments;

-- Re-create the pre-PR1 anonymous read policy that PR1 dropped
CREATE POLICY "Anyone can read active assessments" ON published_assessments
    FOR SELECT
    USING (is_active = true);

-- =========================================================================
-- SECTION 3 — Restore original submissions policies
-- =========================================================================
DROP POLICY IF EXISTS submissions_select_teacher ON submissions;
DROP POLICY IF EXISTS submissions_update_teacher ON submissions;
DROP POLICY IF EXISTS submissions_delete_teacher ON submissions;

-- Re-create the pre-PR1 permissive policies that PR1 dropped
CREATE POLICY "Anyone can insert submissions" ON submissions
    FOR INSERT
    WITH CHECK (true);

CREATE POLICY "Anyone can read submissions" ON submissions
    FOR SELECT
    USING (true);

-- =========================================================================
-- SECTION 4 — Drop PR1 policies on new-RLS tables AND disable RLS
-- =========================================================================
DROP POLICY IF EXISTS published_content_own ON published_content;
ALTER TABLE published_content DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS student_submissions_own ON student_submissions;
ALTER TABLE student_submissions DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS student_sessions_select_teacher ON student_sessions;
ALTER TABLE student_sessions DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS submission_confirmations_own ON submission_confirmations;
ALTER TABLE submission_confirmations DISABLE ROW LEVEL SECURITY;

-- =========================================================================
-- Rollback complete. submissions and published_assessments revert to
-- their pre-PR1 policy set. The 4 new-RLS tables have RLS fully disabled.
-- =========================================================================
