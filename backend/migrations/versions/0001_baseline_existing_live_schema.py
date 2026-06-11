"""Baseline — REAL expression of the live Supabase public schema.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-04-18 (no-op anchor) / 2026-06-11 (rewritten in place
with the real schema — hardening sprint PR7, Data Integrity level 8:
"full live schema expressed in migrations; up tested in CI")

Classification: additive, idempotent (CREATE ... IF NOT EXISTS / guarded
DO blocks only — no DROP / ALTER-tighten / UPDATE / DELETE anywhere).

Provenance: generated from read-only introspection of the LIVE Supabase
database (PostgreSQL 17.6) on 2026-06-11 — pg_catalog/information_schema
queries over all 15 app-owned public tables (columns, defaults, NOT
NULLs, PKs, FKs, UNIQUEs, CHECKs, indexes, RLS policies, functions,
triggers). The committed raw SQL files under backend/database/ and the
repo root had drifted from live (4 whole tables missing, 6 columns
missing, divergent CHECK/UNIQUE constraints and RLS policies); LIVE is
the source of truth here, per the PR7 spec.

Why a real body in 0001 is safe against production
---------------------------------------------------
Production was stamped (`alembic stamp 0001_baseline`) on 2026-04-18 —
verified 2026-06-11: prod alembic_version contains exactly one row
(pg_stat n_live_tup=1/n_tup_ins=1; the row itself is hidden from the
introspection role by Supabase's ensure_rls event trigger, which enabled
RLS on the table). Alembic never re-runs revisions at or below the
current head, so this body can never execute DDL against prod. Even if
it somehow did, every statement is IF-NOT-EXISTS idempotent and would
no-op against the schema it was generated from.

Two execution contexts this body MUST support (both CI-verified):
1. Truly empty database — `alembic upgrade head` bootstraps the full
   live schema (tables in FK-topological order), then 0002 applies.
2. CI Migrations Smoke — .github/ci/supabase_stubs.sql plus the five
   frozen backend/database//root SQL files are applied FIRST, then
   `alembic upgrade head` runs WITHOUT a stamp. IF NOT EXISTS makes
   every statement a no-op where the seeded schema already provides the
   object; the drift-convergence section below additionally brings the
   seeded schema up to live truth where the frozen files lag it.

Intentional exclusions (not expressed here):
- alembic_version — owned by Alembic itself.
- Extensions (pgcrypto, uuid-ossp, supabase_vault, pg_stat_statements)
  — Supabase platform concerns; gen_random_uuid() is built-in since
  PostgreSQL 13, so the defaults below need no extension on a bare
  postgres:15-alpine.
- The `ensure_rls` EVENT TRIGGER — event triggers require superuser and
  are Supabase-platform-managed; its function enable_rls_on_new_table()
  IS expressed (it lives in public and is live truth).
- Grants / roles — Supabase-managed.
- RLS POLICIES are expressed, but each is guarded on the presence of
  auth.uid(): on a bare empty Postgres (no Supabase auth schema) the
  policy bodies cannot resolve and are skipped; in CI the stubs provide
  auth.uid()/auth.role() so policies are created. RLS ENABLE itself is
  unconditional (no dependency, idempotent).

Note on revision ID length: Alembic's default alembic_version.version_num
column is VARCHAR(32). The short "0001_baseline" ID (13 chars) fits with
margin. Do NOT change the ``revision`` literal below — production's
alembic_version row references it.

downgrade() remains forward-only: un-creating the baseline would drop
the entire schema.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- Functions (live truth; needed before triggers) ----------------------

_FUNCTIONS = [
    # Auto-generates classes.join_code on INSERT when blank (live trigger
    # classes_auto_join_code depends on it).
    """
    CREATE OR REPLACE FUNCTION public.generate_class_join_code()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $fn$
    BEGIN
        IF NEW.join_code IS NULL OR NEW.join_code = '' THEN
            NEW.join_code := upper(substr(md5(random()::text), 1, 6));
        END IF;
        RETURN NEW;
    END;
    $fn$
    """,
    # Body of the Supabase `ensure_rls` event trigger. The EVENT TRIGGER
    # itself is intentionally NOT created here (superuser-only,
    # platform-managed); the function is expressed because it lives in
    # the public schema on live.
    """
    CREATE OR REPLACE FUNCTION public.enable_rls_on_new_table()
    RETURNS event_trigger
    LANGUAGE plpgsql
    AS $fn$
    DECLARE
        obj record;
    BEGIN
        FOR obj IN SELECT * FROM pg_event_trigger_ddl_commands()
            WHERE object_type = 'table'
        LOOP
            EXECUTE format(
                'ALTER TABLE %s ENABLE ROW LEVEL SECURITY',
                obj.object_identity
            );
        END LOOP;
    END;
    $fn$
    """,
]


# --- Tables (FK-topological order; constraint names match live) ----------

_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS public.teacher_data (
        teacher_id text NOT NULL,
        data_key   text NOT NULL,
        data       jsonb NOT NULL,
        updated_at timestamptz DEFAULT now(),
        CONSTRAINT teacher_data_pkey PRIMARY KEY (teacher_id, data_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.audit_log (
        id          uuid NOT NULL DEFAULT gen_random_uuid(),
        "timestamp" text NOT NULL,
        teacher_id  text,
        action      text NOT NULL,
        details     text,
        user_type   text DEFAULT 'teacher'::text,
        created_at  timestamptz DEFAULT now(),
        CONSTRAINT audit_log_pkey PRIMARY KEY (id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.student_history (
        teacher_id text NOT NULL,
        student_id text NOT NULL,
        history    jsonb NOT NULL,
        updated_at timestamptz DEFAULT now(),
        CONSTRAINT student_history_pkey PRIMARY KEY (teacher_id, student_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.classes (
        id                uuid NOT NULL DEFAULT gen_random_uuid(),
        teacher_id        uuid NOT NULL,
        name              text NOT NULL,
        join_code         text NOT NULL,
        subject           text,
        grade_level       text,
        is_active         boolean DEFAULT true,
        created_at        timestamptz DEFAULT now(),
        clever_section_id text,
        CONSTRAINT classes_pkey PRIMARY KEY (id),
        CONSTRAINT classes_join_code_key UNIQUE (join_code),
        CONSTRAINT classes_teacher_clever_section_unique
            UNIQUE (teacher_id, clever_section_id),
        CONSTRAINT classes_teacher_id_name_key UNIQUE (teacher_id, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.students (
        id                uuid NOT NULL DEFAULT gen_random_uuid(),
        teacher_id        uuid NOT NULL,
        student_id_number text NOT NULL,
        first_name        text NOT NULL,
        last_name         text NOT NULL,
        period            text,
        class_code        text,
        accommodations    jsonb DEFAULT '{}'::jsonb,
        ell_language      text,
        is_active         boolean DEFAULT true,
        created_at        timestamptz DEFAULT now(),
        updated_at        timestamptz DEFAULT now(),
        email             text,
        CONSTRAINT students_pkey PRIMARY KEY (id),
        CONSTRAINT students_teacher_id_student_id_number_key
            UNIQUE (teacher_id, student_id_number)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.class_students (
        id          uuid NOT NULL DEFAULT gen_random_uuid(),
        class_id    uuid,
        student_id  uuid,
        enrolled_at timestamptz DEFAULT now(),
        CONSTRAINT class_students_pkey PRIMARY KEY (id),
        CONSTRAINT class_students_class_id_student_id_key
            UNIQUE (class_id, student_id),
        CONSTRAINT class_students_class_id_fkey FOREIGN KEY (class_id)
            REFERENCES public.classes(id) ON DELETE CASCADE,
        CONSTRAINT class_students_student_id_fkey FOREIGN KEY (student_id)
            REFERENCES public.students(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.student_sessions (
        id            uuid NOT NULL DEFAULT gen_random_uuid(),
        student_id    uuid,
        class_id      uuid,
        session_token text NOT NULL,
        expires_at    timestamptz NOT NULL,
        created_at    timestamptz DEFAULT now(),
        CONSTRAINT student_sessions_pkey PRIMARY KEY (id),
        CONSTRAINT student_sessions_session_token_key UNIQUE (session_token),
        CONSTRAINT student_sessions_class_id_fkey FOREIGN KEY (class_id)
            REFERENCES public.classes(id) ON DELETE CASCADE,
        CONSTRAINT student_sessions_student_id_fkey FOREIGN KEY (student_id)
            REFERENCES public.students(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.published_assessments (
        id               uuid NOT NULL DEFAULT gen_random_uuid(),
        join_code        varchar(10) NOT NULL,
        title            text NOT NULL,
        assessment       jsonb NOT NULL,
        settings         jsonb DEFAULT '{}'::jsonb,
        teacher_name     text,
        teacher_email    text,
        is_active        boolean DEFAULT true,
        submission_count integer DEFAULT 0,
        created_at       timestamptz DEFAULT now(),
        updated_at       timestamptz DEFAULT now(),
        teacher_id       text,
        CONSTRAINT published_assessments_pkey PRIMARY KEY (id),
        CONSTRAINT published_assessments_join_code_key UNIQUE (join_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.submissions (
        id                 uuid NOT NULL DEFAULT gen_random_uuid(),
        assessment_id      uuid,
        join_code          varchar(10) NOT NULL,
        student_name       text NOT NULL,
        student_email      text,
        answers            jsonb NOT NULL,
        results            jsonb,
        score              numeric(5,2),
        total_points       numeric(5,2),
        percentage         numeric(5,2),
        time_taken_seconds integer,
        submitted_at       timestamptz DEFAULT now(),
        graded_at          timestamptz,
        status             text NOT NULL DEFAULT 'queued'::text,
        grading_task_id    text,
        grading_started_at timestamptz,
        error_message      text,
        CONSTRAINT submissions_pkey PRIMARY KEY (id),
        CONSTRAINT unique_submission_per_student
            UNIQUE (join_code, student_name),
        CONSTRAINT submissions_status_check CHECK (
            status = ANY (ARRAY['queued'::text,
                                'grading_in_progress'::text,
                                'graded'::text,
                                'failed'::text])
        ),
        CONSTRAINT submissions_assessment_id_fkey FOREIGN KEY (assessment_id)
            REFERENCES public.published_assessments(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.drafts (
        id               uuid NOT NULL DEFAULT gen_random_uuid(),
        assessment_id    uuid,
        join_code        varchar(10) NOT NULL,
        student_name     text NOT NULL,
        answers          jsonb NOT NULL DEFAULT '{}'::jsonb,
        progress_percent numeric(5,2) DEFAULT 0,
        last_saved_at    timestamptz DEFAULT now(),
        created_at       timestamptz DEFAULT now(),
        CONSTRAINT drafts_pkey PRIMARY KEY (id),
        CONSTRAINT drafts_join_code_student_name_key
            UNIQUE (join_code, student_name),
        CONSTRAINT drafts_assessment_id_fkey FOREIGN KEY (assessment_id)
            REFERENCES public.published_assessments(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.published_content (
        id                 uuid NOT NULL DEFAULT gen_random_uuid(),
        teacher_id         uuid NOT NULL,
        class_id           uuid,
        content_type       text NOT NULL,
        title              text NOT NULL,
        join_code          text,
        content            jsonb NOT NULL,
        settings           jsonb DEFAULT '{}'::jsonb,
        is_active          boolean DEFAULT true,
        due_date           timestamptz,
        created_at         timestamptz DEFAULT now(),
        target_student_ids jsonb,
        CONSTRAINT published_content_pkey PRIMARY KEY (id),
        CONSTRAINT published_content_join_code_key UNIQUE (join_code),
        CONSTRAINT published_content_content_type_check CHECK (
            content_type = ANY (ARRAY['assessment'::text,
                                      'assignment'::text,
                                      'study_guide'::text,
                                      'flashcards'::text,
                                      'slide_deck'::text])
        ),
        CONSTRAINT published_content_class_id_fkey FOREIGN KEY (class_id)
            REFERENCES public.classes(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.student_submissions (
        id                 uuid NOT NULL DEFAULT gen_random_uuid(),
        student_id         uuid,
        content_id         uuid,
        student_name       text NOT NULL,
        student_id_number  text,
        period             text,
        answers            jsonb,
        results            jsonb,
        score              numeric,
        total_points       numeric,
        percentage         numeric,
        letter_grade       text,
        status             text DEFAULT 'submitted'::text,
        time_taken_seconds integer,
        submitted_at       timestamptz DEFAULT now(),
        graded_at          timestamptz,
        attempt_number     integer DEFAULT 1,
        draft_answers      jsonb,
        marked_for_review  jsonb DEFAULT '[]'::jsonb,
        time_started_at    timestamptz,
        question_times     jsonb,
        grading_task_id    text,
        grading_started_at timestamptz,
        error_message      text,
        CONSTRAINT student_submissions_pkey PRIMARY KEY (id),
        CONSTRAINT student_submissions_status_check CHECK (
            status = ANY (ARRAY['in_progress'::text,
                                'submitted'::text,
                                'grading'::text,
                                'graded'::text,
                                'returned'::text,
                                'partial'::text,
                                'grading_deferred'::text,
                                'grading_failed'::text,
                                'draft'::text])
        ),
        CONSTRAINT student_submissions_content_id_fkey FOREIGN KEY (content_id)
            REFERENCES public.published_content(id),
        CONSTRAINT student_submissions_student_id_fkey FOREIGN KEY (student_id)
            REFERENCES public.students(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.submission_confirmations (
        id                  uuid NOT NULL DEFAULT gen_random_uuid(),
        submission_id       uuid NOT NULL,
        teacher_id          uuid NOT NULL,
        student_email       text NOT NULL,
        student_name        text NOT NULL,
        assignment_title    text NOT NULL,
        attempt_number      integer DEFAULT 1,
        missing_assignments jsonb DEFAULT '[]'::jsonb,
        submitted_at        timestamptz NOT NULL,
        sent_at             timestamptz,
        status              text DEFAULT 'pending'::text,
        created_at          timestamptz DEFAULT now(),
        CONSTRAINT submission_confirmations_pkey PRIMARY KEY (id),
        CONSTRAINT submission_confirmations_submission_id_key
            UNIQUE (submission_id),
        CONSTRAINT submission_confirmations_status_check CHECK (
            status = ANY (ARRAY['pending'::text,
                                'processing'::text,
                                'sent'::text,
                                'failed'::text])
        ),
        CONSTRAINT submission_confirmations_submission_id_fkey
            FOREIGN KEY (submission_id)
            REFERENCES public.student_submissions(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.behavior_sessions (
        id         uuid NOT NULL DEFAULT gen_random_uuid(),
        teacher_id uuid NOT NULL,
        class_id   uuid,
        period     text NOT NULL,
        date       date NOT NULL DEFAULT CURRENT_DATE,
        started_at timestamptz NOT NULL DEFAULT now(),
        ended_at   timestamptz,
        device     text,
        is_active  boolean DEFAULT true,
        created_at timestamptz DEFAULT now(),
        CONSTRAINT behavior_sessions_pkey PRIMARY KEY (id),
        CONSTRAINT behavior_sessions_id_teacher_id_key
            UNIQUE (id, teacher_id),
        CONSTRAINT behavior_sessions_teacher_id_date_period_started_at_key
            UNIQUE (teacher_id, date, period, started_at),
        CONSTRAINT behavior_sessions_class_id_fkey FOREIGN KEY (class_id)
            REFERENCES public.classes(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.behavior_events (
        id           uuid NOT NULL DEFAULT gen_random_uuid(),
        session_id   uuid NOT NULL,
        teacher_id   uuid NOT NULL,
        student_id   uuid,
        student_name text NOT NULL,
        type         text NOT NULL,
        note         text,
        transcript   text,
        source       text DEFAULT 'manual'::text,
        event_time   timestamptz NOT NULL DEFAULT now(),
        created_at   timestamptz DEFAULT now(),
        synced_at    timestamptz,
        client_id    uuid,
        CONSTRAINT behavior_events_pkey PRIMARY KEY (id),
        CONSTRAINT behavior_events_client_id_key UNIQUE (client_id),
        CONSTRAINT behavior_events_source_check CHECK (
            source = ANY (ARRAY['manual'::text, 'stt'::text, 'watch'::text])
        ),
        CONSTRAINT behavior_events_type_check CHECK (
            type = ANY (ARRAY['correction'::text, 'praise'::text])
        ),
        CONSTRAINT behavior_events_session_id_teacher_id_fkey
            FOREIGN KEY (session_id, teacher_id)
            REFERENCES public.behavior_sessions(id, teacher_id)
            ON DELETE CASCADE,
        CONSTRAINT behavior_events_student_id_fkey FOREIGN KEY (student_id)
            REFERENCES public.students(id)
    )
    """,
]


# --- Drift convergence over the CI-seeded committed SQL files ------------
# When the frozen backend/database//root SQL files are applied BEFORE
# `alembic upgrade head` (CI Migrations Smoke), the tables above already
# exist and CREATE TABLE IF NOT EXISTS no-ops — so live-only columns and
# the Clever upsert constraint must be converged explicitly. All
# statements are additive and idempotent; on an empty DB (where the
# CREATE TABLEs above just ran) they are no-ops.

_DRIFT_CONVERGENCE = [
    # classes.clever_section_id — Clever roster sync (roster_sync.py).
    "ALTER TABLE public.classes ADD COLUMN IF NOT EXISTS clever_section_id text",
    # published_content.target_student_ids — per-student publishing.
    "ALTER TABLE public.published_content "
    "ADD COLUMN IF NOT EXISTS target_student_ids jsonb",
    # student_submissions portal-progress columns.
    "ALTER TABLE public.student_submissions "
    "ADD COLUMN IF NOT EXISTS draft_answers jsonb",
    "ALTER TABLE public.student_submissions "
    "ADD COLUMN IF NOT EXISTS marked_for_review jsonb DEFAULT '[]'::jsonb",
    "ALTER TABLE public.student_submissions "
    "ADD COLUMN IF NOT EXISTS time_started_at timestamptz",
    "ALTER TABLE public.student_submissions "
    "ADD COLUMN IF NOT EXISTS question_times jsonb",
    # roster_sync.py upserts classes with
    # on_conflict="teacher_id,clever_section_id" — Postgres requires a
    # matching UNIQUE constraint/index. Live has it; the frozen SQL files
    # do not. ADD CONSTRAINT has no IF NOT EXISTS, so guard via catalog.
    """
    DO $do$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'classes_teacher_clever_section_unique'
              AND conrelid = 'public.classes'::regclass
        ) THEN
            ALTER TABLE public.classes
                ADD CONSTRAINT classes_teacher_clever_section_unique
                UNIQUE (teacher_id, clever_section_id);
        END IF;
    END
    $do$
    """,
]


# --- Indexes (live truth; IF NOT EXISTS converges both contexts) ---------
# Note: live carries BOTH idx_assessments_teacher and
# idx_published_assessments_teacher (duplicate btree on teacher_id) —
# expressed faithfully; deduplication would be a destructive follow-up.

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_teacher_data_key_prefix "
    "ON public.teacher_data (teacher_id, data_key text_pattern_ops)",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_teacher "
    "ON public.audit_log (teacher_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp "
    "ON public.audit_log (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_classes_join_code "
    "ON public.classes (join_code)",
    "CREATE INDEX IF NOT EXISTS idx_students_email "
    "ON public.students (email, teacher_id)",
    "CREATE INDEX IF NOT EXISTS idx_students_lookup "
    "ON public.students (student_id_number, teacher_id)",
    "CREATE INDEX IF NOT EXISTS idx_students_teacher "
    "ON public.students (teacher_id)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_token "
    "ON public.student_sessions (session_token)",
    "CREATE INDEX IF NOT EXISTS idx_assessments_join_code "
    "ON public.published_assessments (join_code)",
    "CREATE INDEX IF NOT EXISTS idx_assessments_teacher "
    "ON public.published_assessments (teacher_id)",
    "CREATE INDEX IF NOT EXISTS idx_published_assessments_teacher "
    "ON public.published_assessments (teacher_id)",
    "CREATE INDEX IF NOT EXISTS idx_submissions_join_code "
    "ON public.submissions (join_code)",
    "CREATE INDEX IF NOT EXISTS idx_submissions_status_started "
    "ON public.submissions (status, grading_started_at)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_submissions_unique_student "
    "ON public.submissions (join_code, student_name) "
    "WHERE (student_name IS NOT NULL)",
    "CREATE INDEX IF NOT EXISTS idx_drafts_join_code "
    "ON public.drafts (join_code)",
    "CREATE INDEX IF NOT EXISTS idx_drafts_student "
    "ON public.drafts (student_name)",
    "CREATE INDEX IF NOT EXISTS idx_published_class "
    "ON public.published_content (class_id, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_student_submissions_status_started "
    "ON public.student_submissions (status, grading_started_at)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_student_submissions_unique "
    "ON public.student_submissions (student_id, content_id) "
    "WHERE (attempt_number = 1)",
    "CREATE INDEX IF NOT EXISTS idx_submissions_content "
    "ON public.student_submissions (content_id)",
    "CREATE INDEX IF NOT EXISTS idx_submissions_status "
    "ON public.student_submissions (status)",
    "CREATE INDEX IF NOT EXISTS idx_submissions_student "
    "ON public.student_submissions (student_id)",
    "CREATE INDEX IF NOT EXISTS idx_confirmations_status "
    "ON public.submission_confirmations (status)",
    "CREATE INDEX IF NOT EXISTS idx_confirmations_teacher "
    "ON public.submission_confirmations (teacher_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_teacher_active "
    "ON public.behavior_sessions (teacher_id, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_teacher_date "
    "ON public.behavior_sessions (teacher_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_events_session "
    "ON public.behavior_events (session_id)",
    "CREATE INDEX IF NOT EXISTS idx_events_student "
    "ON public.behavior_events (student_id)",
    "CREATE INDEX IF NOT EXISTS idx_events_teacher_date "
    "ON public.behavior_events (teacher_id, event_time)",
    "CREATE INDEX IF NOT EXISTS idx_events_teacher_session_time "
    "ON public.behavior_events (teacher_id, session_id, event_time)",
]


# --- Triggers (CREATE OR REPLACE TRIGGER requires PG14+; CI is PG15) -----

_TRIGGERS = [
    """
    CREATE OR REPLACE TRIGGER classes_auto_join_code
        BEFORE INSERT ON public.classes
        FOR EACH ROW EXECUTE FUNCTION public.generate_class_join_code()
    """,
]


# --- Row Level Security ---------------------------------------------------
# ENABLE is unconditional (idempotent, no dependencies). Policies match
# live; each CREATE POLICY is wrapped in a DO block that (a) skips when
# auth.uid() does not exist (bare Postgres without Supabase auth stubs)
# and (b) swallows duplicate_object so a pre-seeded policy of the same
# name (the frozen SQL files create some) wins — additive only.

_RLS_ENABLE = [
    f"ALTER TABLE public.{t} ENABLE ROW LEVEL SECURITY"
    for t in (
        "teacher_data", "audit_log", "student_history", "classes",
        "students", "class_students", "student_sessions",
        "published_assessments", "submissions", "drafts",
        "published_content", "student_submissions",
        "submission_confirmations", "behavior_sessions", "behavior_events",
    )
]

# (policy_name_sql, table, FOR clause, USING expr or None, WITH CHECK expr
# or None) — transcribed from live pg_policy on 2026-06-11.
_POLICIES: list[tuple[str, str, str, str | None, str | None]] = [
    ('"Teachers manage own events"', "behavior_events", "ALL",
     "(auth.uid() = teacher_id)", "(auth.uid() = teacher_id)"),
    ('"Teachers manage own sessions"', "behavior_sessions", "ALL",
     "(auth.uid() = teacher_id)", "(auth.uid() = teacher_id)"),
    ("class_students_own", "class_students", "ALL",
     "(EXISTS (SELECT 1 FROM classes WHERE classes.id = "
     "class_students.class_id AND (classes.teacher_id)::text = "
     "(auth.uid())::text))",
     "(EXISTS (SELECT 1 FROM classes WHERE classes.id = "
     "class_students.class_id AND (classes.teacher_id)::text = "
     "(auth.uid())::text))"),
    ("classes_own", "classes", "ALL",
     "((auth.uid())::text = (teacher_id)::text)",
     "((auth.uid())::text = (teacher_id)::text)"),
    ('"Anyone can delete drafts"', "drafts", "DELETE", "true", None),
    ('"Anyone can insert drafts"', "drafts", "INSERT", None, "true"),
    ('"Anyone can read drafts"', "drafts", "SELECT", "true", None),
    ('"Anyone can update drafts"', "drafts", "UPDATE", "true", None),
    ('"Service role has full access to drafts"', "drafts", "ALL",
     "(auth.role() = 'service_role'::text)", None),
    ("published_assessments_delete_teacher", "published_assessments",
     "DELETE", "(teacher_id = (auth.uid())::text)", None),
    ("published_assessments_insert_teacher", "published_assessments",
     "INSERT", None, "(teacher_id = (auth.uid())::text)"),
    ("published_assessments_select_teacher", "published_assessments",
     "SELECT", "(teacher_id = (auth.uid())::text)", None),
    ("published_assessments_update_teacher", "published_assessments",
     "UPDATE", "(teacher_id = (auth.uid())::text)",
     "(teacher_id = (auth.uid())::text)"),
    ("published_content_own", "published_content", "ALL",
     "((auth.uid())::text = (teacher_id)::text)",
     "((auth.uid())::text = (teacher_id)::text)"),
    ("student_history_own", "student_history", "ALL",
     "((auth.uid())::text = teacher_id)",
     "((auth.uid())::text = teacher_id)"),
    ("student_sessions_select_teacher", "student_sessions", "SELECT",
     "(EXISTS (SELECT 1 FROM classes WHERE classes.id = "
     "student_sessions.class_id AND (classes.teacher_id)::text = "
     "(auth.uid())::text))", None),
    ("student_submissions_own", "student_submissions", "ALL",
     "(EXISTS (SELECT 1 FROM published_content WHERE published_content.id"
     " = student_submissions.content_id AND "
     "(published_content.teacher_id)::text = (auth.uid())::text))",
     "(EXISTS (SELECT 1 FROM published_content WHERE published_content.id"
     " = student_submissions.content_id AND "
     "(published_content.teacher_id)::text = (auth.uid())::text))"),
    ("students_own", "students", "ALL",
     "((auth.uid())::text = (teacher_id)::text)",
     "((auth.uid())::text = (teacher_id)::text)"),
    # Live carries BOTH of these overlapping policies — expressed
    # faithfully; consolidation would be a destructive follow-up.
    ('"Teachers manage own submission_confirmations"',
     "submission_confirmations", "ALL", "(teacher_id = auth.uid())", None),
    ("submission_confirmations_own", "submission_confirmations", "ALL",
     "((auth.uid())::text = (teacher_id)::text)",
     "((auth.uid())::text = (teacher_id)::text)"),
    ("submissions_delete_teacher", "submissions", "DELETE",
     "(EXISTS (SELECT 1 FROM published_assessments WHERE "
     "published_assessments.id = submissions.assessment_id AND "
     "published_assessments.teacher_id = (auth.uid())::text))", None),
    ("submissions_select_teacher", "submissions", "SELECT",
     "(EXISTS (SELECT 1 FROM published_assessments WHERE "
     "published_assessments.id = submissions.assessment_id AND "
     "published_assessments.teacher_id = (auth.uid())::text))", None),
    ("submissions_update_teacher", "submissions", "UPDATE",
     "(EXISTS (SELECT 1 FROM published_assessments WHERE "
     "published_assessments.id = submissions.assessment_id AND "
     "published_assessments.teacher_id = (auth.uid())::text))", None),
    ("teacher_data_own", "teacher_data", "ALL",
     "((auth.uid())::text = teacher_id)",
     "((auth.uid())::text = teacher_id)"),
]


def _policy_sql(name: str, table: str, cmd: str,
                using: str | None, check: str | None) -> str:
    clauses = f"CREATE POLICY {name} ON public.{table} FOR {cmd}"
    if using is not None:
        clauses += f" USING ({using})"
    if check is not None:
        clauses += f" WITH CHECK ({check})"
    return (
        "DO $pol$\n"
        "BEGIN\n"
        "    IF to_regproc('auth.uid') IS NULL THEN\n"
        "        RETURN;  -- bare Postgres: no Supabase auth; skip policy\n"
        "    END IF;\n"
        f"    {clauses};\n"
        "EXCEPTION WHEN duplicate_object THEN\n"
        "    NULL;  -- pre-seeded policy of the same name wins\n"
        "END\n"
        "$pol$"
    )


def upgrade() -> None:
    for stmt in _FUNCTIONS:
        op.execute(stmt)
    for stmt in _TABLES:
        op.execute(stmt)
    for stmt in _DRIFT_CONVERGENCE:
        op.execute(stmt)
    for stmt in _INDEXES:
        op.execute(stmt)
    for stmt in _TRIGGERS:
        op.execute(stmt)
    for stmt in _RLS_ENABLE:
        op.execute(stmt)
    for name, table, cmd, using, check in _POLICIES:
        op.execute(_policy_sql(name, table, cmd, using, check))


def downgrade() -> None:
    raise NotImplementedError("forward-only")
