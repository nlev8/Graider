-- Phase 2 Hotfix 2: Schema drift reconciliation.
--
-- Two reconciliations in one migration:
--
-- 1. student_submissions.status CHECK — live DB currently enforces the
--    5-value set {in_progress, submitted, grading, graded, returned}.
--    Code writes the 4 additional values {partial, grading_deferred,
--    grading_failed, draft} in the portal grading paths. Widen the
--    CHECK to the union set so Phase 4 RLS work can proceed on a
--    constraint that matches reality.
--    Source: grep -rn "'status':" backend/ surfaces:
--      backend/routes/student_account_routes.py:508   'partial' / 'graded'
--      backend/routes/student_account_routes.py:1276  'draft'
--      backend/routes/student_account_routes.py:1299  'draft'
--      backend/routes/student_portal_routes.py:1020   'submitted'
--      backend/services/portal_grading.py:314         'grading_deferred'
--      backend/services/portal_grading.py:589         'graded'
--      backend/services/portal_grading.py:623         'grading_failed'
--      backend/app.py:202                             'grading_failed'
--
-- 2. published_assessments.teacher_id — column is present in live DB with
--    TEXT storage but was missing from the SQL-of-record files. Codify.
--    Verified live type on 2026-04-13 via scripts/probe_teacher_id_type.py:
--      * Filtering `teacher_id = 'not-a-uuid-at-all'` returned 0 rows
--        with no "invalid input syntax for type uuid" error — confirms
--        the column accepts arbitrary text.
--      * 93 of 270 rows carry non-UUID values like 'playwright-teacher'
--        and 'teacher-test-004', further confirming TEXT.
--
-- Safe to apply: the CHECK expansion only loosens; the column ADD is
-- idempotent and NOT NULL is NOT enforced (177 of 270 existing rows
-- have a NULL teacher_id). No data migration required.

BEGIN;

-- 1. Widen student_submissions.status CHECK to the union set.
ALTER TABLE student_submissions
    DROP CONSTRAINT IF EXISTS student_submissions_status_check;

ALTER TABLE student_submissions
    ADD CONSTRAINT student_submissions_status_check
    CHECK (status IN (
        'in_progress', 'submitted', 'grading', 'graded', 'returned',
        'partial', 'grading_deferred', 'grading_failed', 'draft'
    ));

-- 2. Codify published_assessments.teacher_id as TEXT.
--    Idempotent: only adds if missing.
ALTER TABLE published_assessments
    ADD COLUMN IF NOT EXISTS teacher_id TEXT;

CREATE INDEX IF NOT EXISTS idx_published_assessments_teacher
    ON published_assessments(teacher_id);

COMMIT;
