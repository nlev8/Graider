-- Phase 4.2 PR1 — Database RLS Hardening (2026-04-17, revised 2026-04-18)
--
-- Purpose: add Row Level Security policies to tenant-owned tables currently
-- lacking them, tighten policies on tables with too-broad access.
--
-- 2026-04-18 REVISION — LIVE DRIFT RECONCILIATION
-- A drift audit run against the live Supabase (2026-04-18) found several
-- tables carry policies under differently-capitalised names ("Teachers
-- manage own X") that predate the canonical ``<table>_own`` / ``<table>_
-- <op>_<actor>`` naming convention. Two of those drifted policies have
-- FUNCTIONAL issues as well:
--
--   * ``published_assessments``: USES ``teacher_email = auth.email()``.
--     Email can change across Supabase OAuth provider switches or admin
--     renames; ``auth.uid()`` cannot. Swapping to uid-based policy.
--   * ``submissions``: inherits the email chain via
--     ``published_assessments.teacher_email = auth.email()``. Same fix.
--   * ``student_sessions``: ``USING (false)`` blocks teacher reads
--     entirely. Migration installs a SELECT-only policy scoped by
--     class ownership so Phase 4.5 teacher dashboards can read sessions.
--
-- To make the migration idempotent against the drifted state, every
-- ``CREATE POLICY`` is preceded by ``DROP POLICY IF EXISTS`` for BOTH
-- the migration's canonical name AND the live drift name.
--
-- Enforcement model: belt-and-suspenders. Graider's backend continues using
-- the Supabase service role key, which bypasses all RLS. The policies
-- defined here activate the day Phase 4.5 introduces per-user JWT clients.
-- Zero production behavior change from this migration alone.
--
-- Idempotent: every CREATE POLICY is preceded by DROP POLICY IF EXISTS.
-- Every ALTER TABLE ... ENABLE ROW LEVEL SECURITY is safe to re-run.
--
-- Rollback: apply backend/database/rollback_2026_04_17_phase4.2_rls.sql.
--
-- Phase 4.5 handoff: integration tests at that phase must verify
--   1. Teacher A JWT cannot CRUD teacher B's rows on any table below
--   2. Multi-hop children return empty (not error) when parent is deleted
--   3. student_sessions is teacher-readable only; no INSERT/UPDATE/DELETE for JWT users
--   4. submissions/published_assessments have NO anonymous access

-- =========================================================================
-- SECTION 1 — Re-verify existing <table>_own policies (idempotent DROP+CREATE)
-- =========================================================================

-- teacher_data (TEXT teacher_id)
DROP POLICY IF EXISTS teacher_data_own ON teacher_data;
CREATE POLICY teacher_data_own ON teacher_data
    FOR ALL
    USING (auth.uid()::text = teacher_id)
    WITH CHECK (auth.uid()::text = teacher_id);

-- student_history (TEXT teacher_id)
DROP POLICY IF EXISTS student_history_own ON student_history;
CREATE POLICY student_history_own ON student_history
    FOR ALL
    USING (auth.uid()::text = teacher_id)
    WITH CHECK (auth.uid()::text = teacher_id);

-- classes (UUID teacher_id)
DROP POLICY IF EXISTS classes_own ON classes;
DROP POLICY IF EXISTS "Teachers manage own classes" ON classes;  -- live drift (2026-04-18 audit)
CREATE POLICY classes_own ON classes
    FOR ALL
    USING (auth.uid()::text = teacher_id::text)
    WITH CHECK (auth.uid()::text = teacher_id::text);

-- students (UUID teacher_id)
DROP POLICY IF EXISTS students_own ON students;
DROP POLICY IF EXISTS "Teachers manage own students" ON students;  -- live drift
CREATE POLICY students_own ON students
    FOR ALL
    USING (auth.uid()::text = teacher_id::text)
    WITH CHECK (auth.uid()::text = teacher_id::text);

-- class_students (multi-hop via class_id -> classes.teacher_id)
DROP POLICY IF EXISTS class_students_own ON class_students;
DROP POLICY IF EXISTS "Teachers manage own class_students" ON class_students;  -- live drift
CREATE POLICY class_students_own ON class_students
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM classes
            WHERE classes.id = class_students.class_id
              AND classes.teacher_id::text = auth.uid()::text
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM classes
            WHERE classes.id = class_students.class_id
              AND classes.teacher_id::text = auth.uid()::text
        )
    );

-- =========================================================================
-- SECTION 2 — Tighten published_assessments (drop broad anon read)
-- =========================================================================
-- published_assessments has teacher_id TEXT (NOT UUID — see
-- backend/database/supabase_schema.sql:15).

ALTER TABLE published_assessments ENABLE ROW LEVEL SECURITY;

-- Drop the existing overly-permissive "Anyone can read active assessments" policy
DROP POLICY IF EXISTS "Anyone can read active assessments" ON published_assessments;

-- Drop the email-based drift policy ("teacher_email = auth.email()" — see header).
-- Replaced below by four uid-based per-operation policies.
DROP POLICY IF EXISTS "Teachers manage own published_assessments" ON published_assessments;

-- Teacher CRUD on own rows
DROP POLICY IF EXISTS published_assessments_select_teacher ON published_assessments;
CREATE POLICY published_assessments_select_teacher ON published_assessments
    FOR SELECT
    USING (teacher_id = auth.uid()::text);

DROP POLICY IF EXISTS published_assessments_insert_teacher ON published_assessments;
CREATE POLICY published_assessments_insert_teacher ON published_assessments
    FOR INSERT
    WITH CHECK (teacher_id = auth.uid()::text);

DROP POLICY IF EXISTS published_assessments_update_teacher ON published_assessments;
CREATE POLICY published_assessments_update_teacher ON published_assessments
    FOR UPDATE
    USING (teacher_id = auth.uid()::text)
    WITH CHECK (teacher_id = auth.uid()::text);

DROP POLICY IF EXISTS published_assessments_delete_teacher ON published_assessments;
CREATE POLICY published_assessments_delete_teacher ON published_assessments
    FOR DELETE
    USING (teacher_id = auth.uid()::text);

-- Service role policy preserved — do not touch "Service role has full access to assessments"

-- =========================================================================
-- SECTION 3 — Tighten submissions (multi-hop via assessment_id)
-- =========================================================================
-- submissions has NO direct teacher_id; ownership flows through
-- published_assessments via assessment_id (backend/database/supabase_schema.sql:32).

ALTER TABLE submissions ENABLE ROW LEVEL SECURITY;

-- Drop the existing overly-permissive "Anyone can insert/read submissions" policies
DROP POLICY IF EXISTS "Anyone can insert submissions" ON submissions;
DROP POLICY IF EXISTS "Anyone can read submissions" ON submissions;

-- Drop the live drift policy that inherits the email chain through
-- published_assessments.teacher_email = auth.email(). Replaced below.
DROP POLICY IF EXISTS "Teachers view own submissions" ON submissions;

-- Teacher reads submissions to their own assessments
DROP POLICY IF EXISTS submissions_select_teacher ON submissions;
CREATE POLICY submissions_select_teacher ON submissions
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM published_assessments
            WHERE published_assessments.id = submissions.assessment_id
              AND published_assessments.teacher_id = auth.uid()::text
        )
    );

-- Teacher updates submissions to their own assessments (regrade)
DROP POLICY IF EXISTS submissions_update_teacher ON submissions;
CREATE POLICY submissions_update_teacher ON submissions
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM published_assessments
            WHERE published_assessments.id = submissions.assessment_id
              AND published_assessments.teacher_id = auth.uid()::text
        )
    );

-- Teacher deletes submissions to their own assessments
DROP POLICY IF EXISTS submissions_delete_teacher ON submissions;
CREATE POLICY submissions_delete_teacher ON submissions
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM published_assessments
            WHERE published_assessments.id = submissions.assessment_id
              AND published_assessments.teacher_id = auth.uid()::text
        )
    );

-- NOTE: No INSERT policy for non-service-role. The anonymous join-code
-- submission path is handled by the Flask backend (service role), which
-- bypasses RLS. A teacher JWT has no need to INSERT submissions directly.

-- Service role policy preserved — do not touch "Service role has full access to submissions"

-- =========================================================================
-- SECTION 4 — published_content (NEW RLS — UUID teacher_id)
-- =========================================================================

ALTER TABLE published_content ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS published_content_own ON published_content;
DROP POLICY IF EXISTS "Teachers manage own published_content" ON published_content;  -- live drift
CREATE POLICY published_content_own ON published_content
    FOR ALL
    USING (auth.uid()::text = teacher_id::text)
    WITH CHECK (auth.uid()::text = teacher_id::text);

-- =========================================================================
-- SECTION 5 — student_submissions (NEW RLS — multi-hop via content_id)
-- =========================================================================

ALTER TABLE student_submissions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS student_submissions_own ON student_submissions;
DROP POLICY IF EXISTS "Teachers manage own student_submissions" ON student_submissions;  -- live drift
CREATE POLICY student_submissions_own ON student_submissions
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM published_content
            WHERE published_content.id = student_submissions.content_id
              AND published_content.teacher_id::text = auth.uid()::text
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM published_content
            WHERE published_content.id = student_submissions.content_id
              AND published_content.teacher_id::text = auth.uid()::text
        )
    );

-- =========================================================================
-- SECTION 6 — student_sessions (NEW RLS — READ-ONLY teacher via class_id)
-- =========================================================================

ALTER TABLE student_sessions ENABLE ROW LEVEL SECURITY;

-- Only SELECT policy — writes must go through the backend (service role).
-- A teacher's JWT cannot create/modify/delete student sessions directly.
DROP POLICY IF EXISTS student_sessions_select_teacher ON student_sessions;
-- Drop the live drift policy USING(false), which blocks teacher reads entirely.
-- Replaced below by a SELECT policy scoped by class ownership.
DROP POLICY IF EXISTS "No direct access to student_sessions" ON student_sessions;
CREATE POLICY student_sessions_select_teacher ON student_sessions
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM classes
            WHERE classes.id = student_sessions.class_id
              AND classes.teacher_id::text = auth.uid()::text
        )
    );

-- =========================================================================
-- SECTION 7 — submission_confirmations (NEW RLS — UUID teacher_id)
-- =========================================================================
-- Gated on table existence: the 2026-04-18 drift audit didn't confirm
-- this table is present on live. If it's not, the section is a no-op.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relname = 'submission_confirmations'
          AND c.relkind = 'r'
    ) THEN
        EXECUTE 'ALTER TABLE submission_confirmations ENABLE ROW LEVEL SECURITY';
        EXECUTE 'DROP POLICY IF EXISTS submission_confirmations_own ON submission_confirmations';
        EXECUTE $policy$
            CREATE POLICY submission_confirmations_own ON submission_confirmations
                FOR ALL
                USING (auth.uid()::text = teacher_id::text)
                WITH CHECK (auth.uid()::text = teacher_id::text)
        $policy$;
    END IF;
END $$;

-- =========================================================================
-- Phase 4.2 PR1 complete.
-- =========================================================================
-- Next phase: 4.2 PR2 — behavior, LTI, OneRoster table policies (deferred).
-- Next roadmap milestone: Phase 4.5 — per-user JWT clients. At that point,
-- the policies above become load-bearing. See design doc at
-- docs/superpowers/specs/2026-04-17-phase4.2-database-rls-design.md
-- for the handoff integration test requirements.
