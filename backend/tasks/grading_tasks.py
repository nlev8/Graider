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

    Fires only on exceptions that escape to Celery's framework layer:
      - SoftTimeLimitExceeded (after 14 min — BaseException subclass, not caught
        by grade_portal_submission_sync's blanket `except Exception`)
      - TimeLimitExceeded (after 15 min — hard kill)
      - Celery framework errors (worker shutdown during task, serialization
        failures, etc.)

    This does NOT fire on grading pipeline errors — those are swallowed inside
    grade_portal_submission_sync's outer try/except, captured to Sentry, and
    leave the submission row with whatever partial state was written. If a
    future PR hoists transient-error classification above that blanket catch
    (adding autoretry_for back), on_failure will also fire on retry exhaustion.

    Marks the submission row 'failed' so teacher dashboards observe a
    terminal state instead of a stuck 'grading_in_progress' claim.
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        submission_id = args[0] if args else kwargs.get('submission_id')
        # args[2] is the path discriminator. Callers pass
        # SubmissionPathType.<X>.value; its value IS the legacy table-name
        # string, so kwargs fallback default ('submissions') stays unchanged.
        supabase_table = args[2] if len(args) > 2 else kwargs.get('supabase_table', 'submissions')
        if not submission_id:
            return
        try:
            # Slice 5 PR2 Task 2.4: terminal-failure write now goes through the
            # repository abstraction (repo.mark_failed) instead of the legacy
            # _safe_update_submission helper. The DB effect is byte-identical
            # (status='failed', error_message=str(exc)[:500], correct table by
            # path discriminator). TestFailureSeam patches the repo method's
            # update in lockstep with this change.
            from backend.services.submission_repository import repository_for
            from backend.supabase_client import get_supabase
            sb = get_supabase()
            if sb:
                repository_for(supabase_table, sb).mark_failed(submission_id, exc)
        except Exception:
            # Sentry already has the original exception; don't mask it.
            pass


# Retry semantics:
#   Durability — acks_late=True ensures the broker redelivers the message if
#   the worker dies mid-task. That's the primary defense against Railway
#   deploys and worker crashes.
#
#   Transient retry — wired up by closing audit MAJOR #7 (Codex 2026-05-06).
#   The Celery body calls grade_portal_submission_sync with raise_transient=True;
#   the sync function's blanket catch classifies via backend.retry.is_retryable_error
#   (httpx timeout, OpenAI 5xx, supabase 503, ConnectionError, OSError, status
#   408/429/5xx, retryable string keywords) and re-raises as TransientError.
#   Celery's autoretry_for=(TransientError,) catches it.
#
#   Backoff: Celery's `retry_backoff=True` schedules delays at 2**(attempt-1)
#   seconds: attempt 1 retry waits 1s, attempt 2 retry waits 2s, attempt 3
#   retry waits 4s. With `retry_backoff_max=600` the cap matters only for
#   higher max_retries; current 3-retry setup tops out at 4s. `retry_jitter=True`
#   randomizes the actual delay uniformly in [0, scheduled), so 0-7s spread
#   before terminal failure. After retry exhaustion, PortalGradingTask.on_failure
#   marks the row 'failed'.
#
#   Permanent errors (KeyError, ValueError, etc.) are NOT classified as
#   transient — the sync function's blanket catch swallows them as before
#   and marks the row 'grading_failed' synchronously.
@celery_app.task(
    base=PortalGradingTask,
    name='grading.portal_submission',
    bind=True,
    acks_late=True,
    time_limit=900,
    soft_time_limit=840,
    autoretry_for=(TransientError,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def grade_portal_submission(
    self,
    submission_id: str,
    teacher_id: str,
    path_type=None,
    *,
    district_id: str | None = None,
    user_id: str | None = None,
) -> None:
    """Phase 4.1 join-code portal grading task.

    Exactly-once semantics via row-level task_id + grading_started_at dedup.
    Fetches submission state from Supabase and runs the pure grading pipeline.

    Args:
        submission_id: Supabase row id for the submission (submissions or
            student_submissions, determined by `path_type`).
        teacher_id: Teacher owning the submission (for results storage + api keys).
        path_type: SubmissionPathType OR its legacy table-name string
            ("submissions" for join-code, "student_submissions" for
            class-based). Celery enqueue sites pass SubmissionPathType.X.value
            so the wire arg / on_failure args[2] stays the byte-identical
            legacy string; downstream repository_for() coerces either form.
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

    # Closes audit MAJOR #7 round-1 finding 3 (Codex 2026-05-06): if the
    # context fetch raises a transient supabase error, surface it to
    # Celery's autoretry by re-raising as TransientError. The fetch helper
    # only re-raises retryable exceptions (per backend.retry.is_retryable_error);
    # permanent errors return None and fall through to the existing
    # "no ctx → mark failed" path below.
    try:
        ctx = fetch_submission_full_context(path_type, submission_id, teacher_id)
    except Exception as e:
        from backend.retry import is_retryable_error
        if is_retryable_error(e):
            raise TransientError(str(e)[:500]) from e
        raise  # permanent — let it propagate to PortalGradingTask.on_failure
    if not ctx:
        _logger.warning("Submission not found for grading: %s", submission_id)
        return

    # Guard against partial context: if published_assessments fetch failed
    # (captured to Sentry by fetch_submission_full_context) we'd end up with
    # assessment=None. The sync function would dereference `.get(...)` on None,
    # hit its outer except, and mark the row grading_failed. Better to short-
    # circuit with a clear log + Sentry signal than to silently corrupt the
    # submission status.
    if not ctx.get('assessment'):
        # FERPA: hash submission_id before logging — Sentry's logging integration
        # captures `params` and `event["message"]` raw, leaking the bare ID
        # otherwise (Codex audit MAJOR #14 round-4).
        sub_hash = hashlib.sha256(str(submission_id).encode()).hexdigest()[:8]
        _logger.error(
            "grade_portal_submission: assessment unavailable for submission %s (published_assessments fetch likely failed). Aborting task.",
            sub_hash,
        )
        sentry_sdk.capture_message(
            f"grade_portal_submission: no assessment for submission {sub_hash}",
            level='error',
        )
        # Mark row as failed so ops can re-enqueue once the root cause is fixed
        try:
            from backend.services.submission_repository import repository_for
            from backend.supabase_client import get_supabase
            sb = get_supabase()
            if sb:
                repository_for(path_type, sb).mark_failed(
                    submission_id,
                    'Assessment content unavailable at grading time',
                )
        except Exception:
            pass
        return

    grade_portal_submission_sync(
        submission_id=submission_id,
        assessment=ctx['assessment'],
        answers=ctx['answers'],
        student_info=ctx['student_info'],
        teacher_config=ctx['teacher_config'],
        teacher_id=teacher_id,
        # Slice 5 PR2 Task 2.4: grade_portal_submission_sync's param renamed
        # supabase_table -> path_type; the Celery task's own param keeps the
        # name path_type (set in Tasks 2.1-2.3); forward unchanged.
        path_type=path_type,
        student_accommodations=ctx.get('student_accommodations'),
        task_id=self.request.id,
        district_id=district_id,
        user_id=user_id,
        # Closes audit MAJOR #7 (Codex 2026-05-06): transient failures
        # (httpx timeout, OpenAI 5xx, supabase 503, etc.) bubble up as
        # TransientError so Celery's autoretry_for kicks in. The thread-
        # path callers leave this default False to preserve their swallow-
        # and-mark-failed behavior.
        raise_transient=True,
    )
