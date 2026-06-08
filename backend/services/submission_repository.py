"""Submission persistence abstraction for the dual publish-path consolidation.

Graider has two parallel submission paths that differ ONLY by the Supabase
table they read and write:

  join-code (anonymous portal)  -> table 'submissions'
  class-based (Clever/roster)   -> table 'student_submissions'

This module collapses the per-table branching into one repository with two
thin adapters. The enum values ARE the legacy table-name strings, so the
Celery wire argument (supabase_table=...) and PortalGradingTask.on_failure's
args[2] stay byte-for-byte unchanged. PR1 is purely additive: nothing in
production imports this module yet, so behavior cannot change. PR2 rewires
the legacy seam functions to call through here.

This module imports no Flask, no route blueprints, and no backend.app. It
depends only on the standard library, sentry_sdk, and a Supabase client
object passed in by the caller (so it stays usable from the Celery worker
without a Flask request context).
"""
import enum
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import sentry_sdk

logger = logging.getLogger(__name__)

_UNSET = object()  # Sentinel for sb default in repository_for


def _escape_ilike(value: str) -> str:
    """Escape PostgREST ILIKE wildcards so attacker-controlled values match
    literally, not as patterns (audit #4). Without this, an anonymous caller
    POSTing student_name='%' would ILIKE-match ANY prior submission under a
    join code. Mirrors services/assistant_tools_assessments._escape_ilike;
    duplicated locally to keep this module Flask/route-free."""
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


@dataclass
class ExistingSubmission:
    """Return type of SubmissionRepository.find_existing_submission.

    Each adapter populates the fields its query selects. Caller handles
    None vs hit and uses whatever fields are available. JoinCode populates
    id + results + student_name (the 'submissions' table's id, results,
    student_name columns). Class populates id + student_name (the
    'student_submissions' table's id, student_name columns; results is
    not selected by the class-based dedup pre-check today).

    id is Optional because row.get("id") returns Optional[str]; callers
    must handle None before dereferencing.
    """
    id: Optional[str] = None
    results: Optional[dict] = None
    student_name: Optional[str] = None


class SubmissionPathType(enum.Enum):
    """Publish-path discriminator. Values are the live Supabase table names so
    the Celery wire arg / on_failure args[2] string stays unchanged."""

    JOIN_CODE = "submissions"
    CLASS = "student_submissions"


class SubmissionRepository:
    """Base repository. The two paths differ only by self.table_name, so the
    fetch / claim_for_grading / update / mark_failed seams live here once.
    normalize_context differs structurally per path, so subclasses override
    it (the base raises NotImplementedError)."""

    table_name: str = ""

    def __init__(self, sb):
        self._sb = sb

    def update(self, submission_id, update_fields):
        """Update this path's submission row; capture to Sentry on failure.
        Ported verbatim from portal_grading._safe_update_submission.

        Skips silently when submission_id is falsy (the anonymous join-code
        path doesn't always have a Supabase row). If submission_id IS set but
        the client is None, that's a real config/connectivity problem, page
        it."""
        if not submission_id:
            return  # Intentional skip: join-code path may have no row
        if not self._sb:
            # FERPA: hash submission_id, see Codex audit MAJOR #14 round-5.
            sub_hash = hashlib.sha256(
                str(submission_id).encode()
            ).hexdigest()[:8]
            msg = ("Cannot update submission %s: Supabase client unavailable"
                   % sub_hash)
            logger.error(msg)
            sentry_sdk.capture_message(msg, level="error")
            return
        try:
            self._sb.table(self.table_name).update(update_fields).eq(
                "id", submission_id
            ).execute()
        except Exception as e:
            logger.error("Failed to update Supabase submission: %s", e)
            sentry_sdk.capture_exception(e)

    def claim_for_grading(self, submission_id, task_id):
        """Row-level claim. Mirrors portal_grading._claim_submission_for_grading
        EXACTLY: an UNCONDITIONAL 3-field write. There is no "already claimed"
        guard and no TTL/stale check in this function (the stale check lives in
        the caller, grade_portal_submission_sync, and is out of repository
        scope). Returns None."""
        if not self._sb or not submission_id:
            return
        self.update(submission_id, {
            "status": "grading_in_progress",
            "grading_task_id": task_id,
            "grading_started_at": datetime.now(timezone.utc).isoformat(),
        })

    def mark_failed(self, submission_id, error):
        """Mark this path's submission row terminally failed. Mirrors
        PortalGradingTask.on_failure's write EXACTLY: status is 'failed'
        (NOT 'grading_failed') and error_message is str(error) truncated to
        500 chars. Returns None."""
        self.update(submission_id, {
            "status": "failed",
            "error_message": str(error)[:500],
        })

    def fetch(self, submission_id):
        """Fetch this path's submission row; return dict or None.
        Ported verbatim from portal_grading._fetch_submission_row.

        Returns None on any error so the caller can treat it as "no claim
        found". Captures exceptions to Sentry so broker/schema failures
        surface instead of silently looking like "no row found"."""
        if not self._sb or not submission_id:
            return None
        try:
            result = self._sb.table(self.table_name).select(
                "*"
            ).eq("id", submission_id).single().execute()
            return result.data
        except Exception as e:
            # FERPA: hash submission_id, see Codex audit MAJOR #14 round-4.
            logger.error(
                "Failed to fetch submission row %s: %s",
                hashlib.sha256(str(submission_id).encode()).hexdigest()[:8],
                e,
            )
            sentry_sdk.capture_exception(e)
            return None

    def find_existing_submission(self, lookup_key, student_info):
        """Route-layer dedup pre-check. Returns ExistingSubmission or None.

        Per-adapter implementation preserves each path's exact query mechanism
        (fuzzy ilike for join-code, exact match for class-based).
        """
        raise NotImplementedError("find_existing_submission is path-specific")

    def count_existing_for(self, lookup_key, student_info) -> int:
        """Return the count of submissions matching (lookup_key, student_info).

        Used by the class-based submit route to derive attempt_number
        (count + 1). The join-code path uses this for the equivalent
        per-name count if it ever needs an attempt counter. Returns 0
        if no submissions match or the query fails.
        """
        raise NotImplementedError("count_existing_for is path-specific")

    def _resolve_student_id(self, data):
        """Path-specific student_id resolution. Relocated VERBATIM from the
        portal_grading.fetch_submission_full_context :526 branch; subclasses
        carry the exact branch body. Base has no path, so NotImplementedError.
        """
        raise NotImplementedError(
            "_resolve_student_id is path-specific; use a concrete adapter"
        )

    def normalize_context(self, row, base_context):
        """Build the normalized grading context dict.

        The student_info / return-dict scaffold below is relocated VERBATIM
        from portal_grading.fetch_submission_full_context (lines 524-544 on
        main). The ONLY per-path divergence is the student_id computation
        (original lines 526-529), which lives in _resolve_student_id so each
        adapter carries its exact branch body. `base_context` supplies the
        already-resolved assessment / teacher_config / student_accommodations
        (PR2 wires fetch_submission_full_context to call through here)."""
        data = row

        # student_info must satisfy both:
        #   - test contract (ctx['student_info']['name'])
        #   - grade_portal_submission_sync consumer (reads 'student_name')
        # So populate both keys.
        #
        # student_id normalization: the join-code path's thread spawn in
        # student_portal_routes.py builds student_info with student_id="" (empty
        # string, not None) — the `submissions` table has no student_id column at
        # all, so the thread path has always treated it as unknown. For parity,
        # normalize student_id to empty string when reading from `submissions`
        # so downstream consumers like load_student_history(teacher_id, student_id)
        # see the same input regardless of code path. Class-based path
        # (`student_submissions` table) keeps whatever the row has.
        student_name = data.get('student_name')
        student_email = data.get('student_email')
        student_id = self._resolve_student_id(data)
        student_info = {
            'name': student_name,
            'email': student_email,
            'student_name': student_name,
            'student_email': student_email,
            'student_id': student_id,
        }

        return {
            'assessment': base_context.get('assessment'),
            'answers': data.get('answers') or {},
            'student_info': student_info,
            'teacher_config': base_context.get('teacher_config'),
            'student_accommodations': base_context.get(
                'student_accommodations'
            ),
        }


class JoinCodeSubmissionRepository(SubmissionRepository):
    """Anonymous join-code path -> Supabase 'submissions' table."""

    table_name = SubmissionPathType.JOIN_CODE.value

    def _resolve_student_id(self, data):
        # Relocated VERBATIM from the `if supabase_table == 'submissions':`
        # branch body (portal_grading.py:527 on main).
        student_id = ''
        return student_id

    def find_existing_submission(self, lookup_key, student_info):
        if not self._sb or not lookup_key:
            return None
        try:
            result = self._sb.table(self.table_name).select(
                "id, results, student_name"
            ).eq("join_code", lookup_key).ilike(
                "student_name", _escape_ilike(student_info.get("name") or "")
            ).execute()
        except Exception as e:
            logger.error("find_existing_submission failed for %s", lookup_key)
            sentry_sdk.capture_exception(e)
            return None
        rows = result.data if result else None
        if not rows:
            return None
        # If multiple matches, take the first (the existing route does
        # the same: it reads the first row of the result).
        row = rows[0] if isinstance(rows, list) else rows
        return ExistingSubmission(
            id=row.get("id"),
            results=row.get("results"),
            student_name=row.get("student_name"),
        )

    def count_existing_for(self, lookup_key, student_info) -> int:
        if not self._sb or not lookup_key:
            return 0
        try:
            result = self._sb.table(self.table_name).select(
                "id"
            ).eq("join_code", lookup_key).ilike(
                "student_name", _escape_ilike(student_info.get("name") or "")
            ).execute()
        except Exception as e:
            logger.error("count_existing_for failed for table %s: %s", self.table_name, e)
            sentry_sdk.capture_exception(e)
            return 0
        rows = result.data if result else None
        if not rows:
            return 0
        return len(rows) if isinstance(rows, list) else 1


class ClassSubmissionRepository(SubmissionRepository):
    """Authenticated class-based path -> Supabase 'student_submissions' table."""

    table_name = SubmissionPathType.CLASS.value

    def _resolve_student_id(self, data):
        # Relocated VERBATIM from the `else:` branch body
        # (portal_grading.py:529 on main).
        student_id = data.get('student_id') or ''
        return student_id

    def find_existing_submission(self, lookup_key, student_info):
        if not self._sb or not lookup_key or not student_info.get("student_id"):
            return None
        try:
            # Mirror student_account_routes.py:1137 exactly. The dedup
            # query selects only id today (class path does not return
            # existing results inline); preserve that. Select student_name
            # additionally for the ExistingSubmission dataclass.
            result = self._sb.table(self.table_name).select(
                "id, student_name"
            ).eq(
                "content_id", lookup_key
            ).eq(
                "student_id", student_info["student_id"]
            ).execute()
        except Exception as e:
            logger.error("find_existing_submission failed for %s", lookup_key)
            sentry_sdk.capture_exception(e)
            return None
        rows = result.data if result else None
        if not rows:
            return None
        row = rows[0] if isinstance(rows, list) else rows
        return ExistingSubmission(
            id=row.get("id"),
            results=None,
            student_name=row.get("student_name"),
        )

    def count_existing_for(self, lookup_key, student_info) -> int:
        if not self._sb or not lookup_key or not student_info.get("student_id"):
            return 0
        try:
            # Mirror student_account_routes.submit_student_work body's
            # original attempt-counter query semantics. Selects only "id"
            # to minimize payload.
            result = self._sb.table(self.table_name).select(
                "id"
            ).eq(
                "student_id", student_info["student_id"]
            ).eq(
                "content_id", lookup_key
            ).execute()
        except Exception as e:
            logger.error("count_existing_for failed for table %s: %s", self.table_name, e)
            sentry_sdk.capture_exception(e)
            return 0
        rows = result.data if result else None
        if not rows:
            return 0
        return len(rows) if isinstance(rows, list) else 1


def repository_for(path_type, sb=_UNSET):
    """Return the adapter for a SubmissionPathType (or its legacy table-name
    string). When sb is omitted, resolve it from backend.providers (the DI
    seam). Raises ValueError for anything else."""
    if sb is _UNSET:
        from backend.providers import get_supabase_provider
        sb = get_supabase_provider()
    if isinstance(path_type, str):
        path_type = SubmissionPathType(path_type)
    if path_type is SubmissionPathType.JOIN_CODE:
        return JoinCodeSubmissionRepository(sb)
    if path_type is SubmissionPathType.CLASS:
        return ClassSubmissionRepository(sb)
    raise ValueError("Unknown submission path type: %r" % (path_type,))
