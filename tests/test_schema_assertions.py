"""Database schema assertion tests — Phase 1 safety net.

Pins the Supabase table/column names that route handlers reference so Phase 4's
RLS changes (and any column rename that sneaks through PostgREST's silent
select-list behaviour) can't break queries undetected.

Marked @pytest.mark.live — requires a real Supabase connection. Does NOT run
in CI (no Supabase credentials in CI environment). Run manually before major
releases or Phase 4 RLS changes:

    pytest tests/test_schema_assertions.py -v -m live

Approach: SELECT ... LIMIT 0 on each required column. If a column is missing,
PostgREST raises an error (supabase-py surfaces it via `.execute()`). If
PostgREST ever starts silently ignoring missing columns in the select list,
escalate to a SQL RPC or the Supabase management API.

Phase 2 Hotfix 2 resolved the two drifts surfaced in Phase 1 via migration
backend/database/migration_2026_04_13_schema_reconcile.sql:
    - student_submissions.status CHECK now accepts the union of the original
      5 lifecycle states {in_progress, submitted, grading, graded, returned}
      plus the 4 code-written states {partial, grading_deferred,
      grading_failed, draft}. TestStudentSubmissionsSchema::
      test_status_check_accepts_all_code_written_values round-trips each
      value through a dedicated sentinel row and asserts no CheckViolation.
    - published_assessments.teacher_id is codified as TEXT. The column's
      live type was verified by scripts/probe_teacher_id_type.py before
      the migration was authored.

These tests are the regression guard for Phase 4 RLS work — if RLS
changes break column access or reintroduce drift, the core_columns_exist
tests catch it.
"""
import os

import pytest

pytestmark = pytest.mark.live


def _get_live_supabase():
    from dotenv import load_dotenv
    load_dotenv(
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        override=True,
    )
    from backend.supabase_client import get_raw_supabase
    sb = get_raw_supabase()
    if sb is None:
        pytest.skip("Supabase not configured (no SUPABASE_URL/SUPABASE_SERVICE_KEY)")
    return sb


class TestStudentSubmissionsSchema:
    """Pin student_submissions columns referenced by route handlers."""

    def test_core_columns_exist(self):
        sb = _get_live_supabase()
        result = sb.table("student_submissions").select(
            "id, student_id, content_id, status, answers, results, "
            "score, percentage, attempt_number, time_taken_seconds"
        ).limit(0).execute()
        assert result is not None

    def test_status_check_accepts_all_code_written_values(self):
        """Migration 2026_04_13 widened the CHECK constraint to the union
        of the original 5 lifecycle states and the 4 code-written states.
        Insert a DEDICATED sentinel row (never touch real submissions),
        round-trip each status value through an UPDATE, delete on exit.

        If the test process crashes mid-loop, the worst case is one
        orphan row with NULL FKs and student_name="__schema_probe_sentinel__" —
        trivially identifiable and safe to delete. Never mutates a real
        student's submission."""
        sb = _get_live_supabase()
        sentinel_name = "__schema_probe_sentinel__"

        # Pre-clean any orphans from prior crashed runs.
        sb.table("student_submissions").delete().eq(
            "student_name", sentinel_name
        ).execute()

        all_values = [
            "in_progress", "submitted", "grading", "graded", "returned",
            "partial", "grading_deferred", "grading_failed", "draft",
        ]

        # Insert sentinel with NULL FKs (student_id + content_id both
        # nullable per schema). A SKIP here would let the overall suite
        # report "10/10 green" without the CHECK probe ever having run —
        # defeats the purpose. Hard-fail with explicit messaging instead.
        try:
            insert_result = sb.table("student_submissions").insert({
                "student_name": sentinel_name,
                "status": "submitted",  # known-valid under both old + new CHECK
            }).execute()
        except Exception as e:  # noqa: BLE001  # test harness: failure recorded/asserted
            pytest.fail(
                f"Sentinel INSERT blocked (likely RLS or permissions on "
                f"student_submissions for the service-role key used by the "
                f"test): {e!r}. Grant INSERT/UPDATE/DELETE on rows with "
                f"student_name='{sentinel_name}' to the test role, or "
                f"disable RLS for the probe path, then retry. Do NOT "
                f"downgrade this to pytest.skip — a skip hides whether "
                f"the CHECK widening actually landed in prod."
            )
        if not insert_result.data:
            pytest.fail(
                f"Sentinel INSERT returned no data (PostgREST filtered "
                f"the result, likely RLS). Same remediation as above — "
                f"do NOT downgrade to skip."
            )
        sentinel_id = insert_result.data[0]["id"]

        try:
            for value in all_values:
                # If the CHECK rejects the value, supabase-py raises APIError.
                sb.table("student_submissions").update({"status": value}).eq(
                    "id", sentinel_id
                ).execute()
        finally:
            sb.table("student_submissions").delete().eq(
                "id", sentinel_id
            ).execute()


class TestPublishedAssessmentsSchema:
    def test_core_columns_exist(self):
        sb = _get_live_supabase()
        result = sb.table("published_assessments").select(
            "id, join_code, title, assessment, settings, "
            "teacher_name, teacher_email, is_active, submission_count"
        ).limit(0).execute()
        assert result is not None

    def test_teacher_id_column_exists(self):
        """published_assessments.teacher_id is codified in the SQL-of-record
        as TEXT per migration 2026_04_13. Query must succeed, not error.
        Live type was verified via scripts/probe_teacher_id_type.py."""
        sb = _get_live_supabase()
        result = sb.table("published_assessments").select("teacher_id").limit(0).execute()
        assert result is not None


class TestSubmissionsSchema:
    def test_core_columns_exist(self):
        sb = _get_live_supabase()
        result = sb.table("submissions").select(
            "id, assessment_id, join_code, student_name, answers, "
            "results, score, total_points, percentage"
        ).limit(0).execute()
        assert result is not None


class TestPublishedContentSchema:
    def test_core_columns_exist(self):
        sb = _get_live_supabase()
        result = sb.table("published_content").select(
            "id, class_id, title, content, content_type, teacher_id, "
            "due_date, join_code, settings, is_active"
        ).limit(0).execute()
        assert result is not None


class TestClassesSchema:
    def test_core_columns_exist(self):
        sb = _get_live_supabase()
        result = sb.table("classes").select(
            "id, name, join_code, teacher_id"
        ).limit(0).execute()
        assert result is not None


class TestClassStudentsSchema:
    def test_core_columns_exist(self):
        sb = _get_live_supabase()
        result = sb.table("class_students").select(
            "class_id, student_id"
        ).limit(0).execute()
        assert result is not None


class TestStudentsSchema:
    def test_core_columns_exist(self):
        sb = _get_live_supabase()
        result = sb.table("students").select(
            "id, first_name, last_name, email, student_id_number, accommodations"
        ).limit(0).execute()
        assert result is not None


class TestStudentSessionsSchema:
    def test_core_columns_exist(self):
        sb = _get_live_supabase()
        result = sb.table("student_sessions").select(
            "id, student_id, session_token, expires_at"
        ).limit(0).execute()
        assert result is not None
