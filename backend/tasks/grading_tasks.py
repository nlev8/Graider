"""Phase 4.1 portal grading Celery task."""
import hashlib
import logging

import sentry_sdk
from celery import Task

from backend.celery_app import celery_app

_logger = logging.getLogger(__name__)


# Reserved for future use — kept so callers importing this symbol don't break
# if/when transient-retry gets wired up. Currently not raised anywhere; see
# the decorator comment below for why auto-retry is not active in PR2.
class TransientError(Exception):
    """Transient failures that Celery should retry (OpenAI 5xx, Supabase 503)."""


class PortalGradingTask(Task):
    """Base task class with on_failure hook for terminal 'failed' state.

    Called by Celery after max_retries is exhausted (autoretry path) OR on an
    un-retriable exception. Marks the submission row 'failed' so teacher
    dashboards observe the terminal state instead of a stuck 'grading_in_progress'.
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        submission_id = args[0] if args else kwargs.get('submission_id')
        supabase_table = args[2] if len(args) > 2 else kwargs.get('supabase_table', 'submissions')
        if not submission_id:
            return
        try:
            from backend.services.portal_grading import _safe_update_submission
            from backend.supabase_client import get_supabase
            sb = get_supabase()
            if sb:
                _safe_update_submission(
                    sb,
                    submission_id,
                    {
                        'status': 'failed',
                        'error_message': str(exc)[:500],
                    },
                    table_name=supabase_table,
                )
        except Exception:
            # Sentry already has the original exception; don't mask it by
            # re-raising from the failure hook.
            pass


# Retry semantics (Phase 4.1 PR2):
#   Durability — acks_late=True ensures the broker redelivers the message if
#   the worker dies mid-task. That's the primary defense against Railway
#   deploys and worker crashes.
#
#   Transient retry (e.g., OpenAI 5xx) is NOT wired up in this PR. The pure
#   function grade_portal_submission_sync has a blanket `except Exception`
#   that captures to Sentry and returns normally — nothing bubbles to Celery's
#   retry classifier. Adding `autoretry_for=...` here would be dead config.
#
#   If future work wants auto-retry on transient AI failures, hoist transient
#   classification inside grade_portal_submission_sync and re-raise a
#   TransientError above the blanket catch. Then add autoretry_for,
#   retry_backoff, max_retries, retry_backoff_max to this decorator.
@celery_app.task(
    base=PortalGradingTask,
    name='grading.portal_submission',
    bind=True,
    acks_late=True,
    time_limit=900,
    soft_time_limit=840,
)
def grade_portal_submission(
    self,
    submission_id: str,
    teacher_id: str,
    supabase_table: str,
    *,
    district_id: str | None = None,
    user_id: str | None = None,
) -> None:
    """Phase 4.1 join-code portal grading task.

    Exactly-once semantics via row-level task_id + grading_started_at dedup.
    Fetches submission state from Supabase and runs the pure grading pipeline.

    Args:
        submission_id: Supabase row id for the submission (submissions or
            student_submissions, determined by `supabase_table`).
        teacher_id: Teacher owning the submission (for results storage + api keys).
        supabase_table: "submissions" for join-code, "student_submissions" for class-based.
        district_id: District context for api_keys lookup; passed explicitly so
            the Celery worker doesn't need to reach into flask.g.
        user_id: Acting user id for Sentry scope; hashed before set_user to
            match the before_send scrubber format (see PR #83).
    """
    # Sentry scope tagging. Hash user_id with sha256[:12] so the before_send
    # scrubber preserves it; without the hash, the scrubber rewrites
    # user.id to "anonymous" in worker context (no Flask request).
    if user_id:
        hashed_uid = hashlib.sha256(str(user_id).encode()).hexdigest()[:12]
        sentry_sdk.set_user({"id": hashed_uid})
    if district_id:
        sentry_sdk.set_tag("district", district_id)

    from backend.services.portal_grading import (
        grade_portal_submission_sync,
        fetch_submission_full_context,
    )

    ctx = fetch_submission_full_context(supabase_table, submission_id, teacher_id)
    if not ctx:
        _logger.warning("Submission not found for grading: %s", submission_id)
        return

    grade_portal_submission_sync(
        submission_id=submission_id,
        assessment=ctx['assessment'],
        answers=ctx['answers'],
        student_info=ctx['student_info'],
        teacher_config=ctx['teacher_config'],
        teacher_id=teacher_id,
        supabase_table=supabase_table,
        student_accommodations=ctx.get('student_accommodations'),
        task_id=self.request.id,
        district_id=district_id,
        user_id=user_id,
    )
