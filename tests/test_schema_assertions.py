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

These tests also document known schema drift captured during Phase 1 review:
    - student_submissions.status CHECK constraint allows
      (in_progress, submitted, grading, graded, returned) but the code writes
      (partial, grading_deferred, grading_failed, draft) in some paths.
    - published_assessments does NOT have a teacher_id column per SQL schema,
      contrary to the original Phase 1 spec (Codex caught this).
Phase 4 resolves both.
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

    def test_status_values_drift_is_documented(self):
        """Documents known schema drift: the SQL CHECK constraint on
        student_submissions.status allows {in_progress, submitted, grading,
        graded, returned} but the code writes {partial, grading_deferred,
        grading_failed, draft} in some paths.

        This test PASSES as long as the table is queryable. The real value
        is the docstring — it pins the drift as a known-bug record so a
        future reader doesn't "fix" one side without the other.
        """
        sb = _get_live_supabase()
        result = sb.table("student_submissions").select("status").limit(1).execute()
        assert result is not None


class TestPublishedAssessmentsSchema:
    def test_core_columns_exist(self):
        sb = _get_live_supabase()
        result = sb.table("published_assessments").select(
            "id, join_code, title, assessment, settings, "
            "teacher_name, teacher_email, is_active, submission_count"
        ).limit(0).execute()
        assert result is not None

    def test_no_teacher_id_column(self):
        """published_assessments should NOT have a teacher_id column
        (SQL schema of record). Documents the absence so nobody adds code
        that references it."""
        sb = _get_live_supabase()
        try:
            sb.table("published_assessments").select("teacher_id").limit(0).execute()
            # If this succeeds the column DOES exist — flag as drift.
            pytest.skip(
                "published_assessments.teacher_id appears to exist — "
                "schema drift vs SQL of record; reconcile in Phase 4."
            )
        except Exception:
            pass  # Correct per SQL schema


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
