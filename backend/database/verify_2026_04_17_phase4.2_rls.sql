-- Phase 4.2 PR1 — POST-MIGRATION VERIFICATION (2026-04-18)
--
-- Run this AFTER applying migration_2026_04_17_phase4.2_rls.sql.
-- Every section below should return 0 rows on success. If ANY row
-- comes back, the migration didn't land cleanly — compare the result
-- against the migration source to diagnose.
--
-- This is drift-aware: it verifies both that the migration's canonical
-- policies exist AND that the pre-migration drifted policies were
-- removed.

-- =========================================================================
-- SECTION A — Canonical policies that MUST exist after migration
-- =========================================================================
-- Result: rows represent MISSING canonical policies. Expected: 0 rows.

WITH expected_canonical AS (
    SELECT 'teacher_data' AS tablename, 'teacher_data_own' AS policyname
    UNION ALL SELECT 'student_history', 'student_history_own'
    UNION ALL SELECT 'classes', 'classes_own'
    UNION ALL SELECT 'students', 'students_own'
    UNION ALL SELECT 'class_students', 'class_students_own'
    UNION ALL SELECT 'published_assessments', 'published_assessments_select_teacher'
    UNION ALL SELECT 'published_assessments', 'published_assessments_insert_teacher'
    UNION ALL SELECT 'published_assessments', 'published_assessments_update_teacher'
    UNION ALL SELECT 'published_assessments', 'published_assessments_delete_teacher'
    UNION ALL SELECT 'submissions', 'submissions_select_teacher'
    UNION ALL SELECT 'submissions', 'submissions_update_teacher'
    UNION ALL SELECT 'submissions', 'submissions_delete_teacher'
    UNION ALL SELECT 'published_content', 'published_content_own'
    UNION ALL SELECT 'student_submissions', 'student_submissions_own'
    UNION ALL SELECT 'student_sessions', 'student_sessions_select_teacher'
)
SELECT
    '!!! MISSING CANONICAL POLICY' AS verdict,
    e.tablename,
    e.policyname
FROM expected_canonical e
LEFT JOIN pg_policies p
  ON p.schemaname = 'public'
 AND p.tablename = e.tablename
 AND p.policyname = e.policyname
WHERE p.policyname IS NULL;

-- =========================================================================
-- SECTION B — Drift policies that MUST be gone after migration
-- =========================================================================
-- Result: rows represent DRIFT policies that survived. Expected: 0 rows.

WITH expected_gone AS (
    SELECT 'classes' AS tablename, 'Teachers manage own classes' AS policyname
    UNION ALL SELECT 'students', 'Teachers manage own students'
    UNION ALL SELECT 'class_students', 'Teachers manage own class_students'
    UNION ALL SELECT 'published_assessments', 'Teachers manage own published_assessments'
    UNION ALL SELECT 'published_assessments', 'Anyone can read active assessments'
    UNION ALL SELECT 'submissions', 'Teachers view own submissions'
    UNION ALL SELECT 'submissions', 'Anyone can read submissions'
    UNION ALL SELECT 'submissions', 'Anyone can insert submissions'
    UNION ALL SELECT 'published_content', 'Teachers manage own published_content'
    UNION ALL SELECT 'student_submissions', 'Teachers manage own student_submissions'
    UNION ALL SELECT 'student_sessions', 'No direct access to student_sessions'
)
SELECT
    '!!! DRIFT POLICY STILL PRESENT' AS verdict,
    p.tablename,
    p.policyname,
    p.qual AS using_expr
FROM pg_policies p
JOIN expected_gone e
  ON p.schemaname = 'public'
 AND p.tablename = e.tablename
 AND p.policyname = e.policyname;

-- =========================================================================
-- SECTION C — Spot-check the expressions for tables whose drift had
-- functional issues (not just naming)
-- =========================================================================
-- Expected: each of these returns exactly 1 row with the correct
-- uid-based expression. An auth.email() substring in any using_expr
-- means the drift was not fully replaced.

SELECT
    p.tablename,
    p.policyname,
    p.cmd,
    CASE
        WHEN p.qual ILIKE '%auth.email%' THEN '!!! EMAIL-BASED EXPR STILL PRESENT'
        WHEN p.qual = 'false' THEN '!!! USING(false) STILL PRESENT'
        ELSE 'ok'
    END AS health,
    p.qual AS using_expr
FROM pg_policies p
WHERE p.schemaname = 'public'
  AND p.tablename IN ('published_assessments', 'submissions', 'student_sessions')
ORDER BY p.tablename, p.cmd, p.policyname;
