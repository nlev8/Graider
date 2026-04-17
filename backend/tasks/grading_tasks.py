"""Phase 4.1 PR1 stub — logs and returns.

PR2 replaces the body with the full grading pipeline invocation.
"""
import logging

from backend.celery_app import celery_app

_logger = logging.getLogger(__name__)


@celery_app.task(name='grading.portal_submission', bind=True)
def grade_portal_submission(self, submission_id, teacher_id, supabase_table, **kwargs):
    """PR1 stub — will be replaced in PR2."""
    _logger.info(
        "grade_portal_submission stub invoked: submission_id=%s teacher_id=%s table=%s",
        submission_id, teacher_id, supabase_table,
    )
    return {'status': 'stub', 'submission_id': submission_id}
