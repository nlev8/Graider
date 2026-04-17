"""Phase 4.1 Celery application for Graider.

Instantiates the Celery app, reads CELERY_BROKER_URL from env (fails fast if unset),
and wires the Sentry CeleryIntegration + Supabase client reset at worker process init.
"""
import logging
import os

from celery import Celery
from celery.signals import worker_process_init

_logger = logging.getLogger(__name__)

_broker_url = os.environ.get('CELERY_BROKER_URL')
if not _broker_url:
    raise RuntimeError(
        "CELERY_BROKER_URL env var is required to start the Celery worker. "
        "Set it on the Railway worker service (default: redis://...:6379/1 to keep "
        "flask-limiter/flask-session on DB 0 undisturbed)."
    )

celery_app = Celery('graider')
celery_app.conf.broker_url = _broker_url
celery_app.conf.task_serializer = 'json'
celery_app.conf.accept_content = ['json']
celery_app.conf.result_backend = None  # Supabase row is source of truth
celery_app.conf.worker_send_task_events = True
celery_app.conf.task_send_sent_event = True

# Durability settings — required for PR2's row-level dedup to work.
#
# task_acks_late=True:
#   Broker acknowledges the message only AFTER the task function returns
#   (or is handled by an exception handler). Without this, messages are
#   acked on delivery — a worker SIGKILL or OOM mid-grade would silently
#   drop the task, and the row-level dedup columns (grading_task_id +
#   grading_started_at) never get a chance to reclaim the submission.
#
# task_reject_on_worker_lost=True:
#   When a worker dies mid-task (Railway OOM kill, SIGKILL, segfault),
#   Celery's default is to *implicitly ack* the task to avoid poison-pill
#   loops. That defeats acks_late for the worker-lost case specifically.
#   Rejecting instead re-queues the task for redelivery.
#
# The pair is safe because Phase 4.1 PR0 added grading_task_id +
# grading_started_at to submissions and student_submissions. PR2's task
# body claims the row idempotently via these columns, so redelivery cannot
# double-grade the same submission.
celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True

celery_app.autodiscover_tasks(['backend.tasks'])


@worker_process_init.connect
def _init_worker_process(**kwargs):
    """Initialize Sentry + reset Supabase client on each worker process spawn.

    Prefork pool forks fresh processes; each needs:
      1. Its own Sentry init (swap FlaskIntegration -> CeleryIntegration via environment='worker').
      2. A fresh Supabase client -- supabase-py uses httpx.Client whose connection
         pool is not fork-safe. Explicitly reset the module-global singletons so
         the next get_supabase() / get_raw_supabase() call rebuilds against this
         process's fd table.
    """
    from backend.observability.sentry import init_sentry
    init_sentry(environment='worker')

    # Explicit reset of Supabase client singletons (Codex Gotcha #5 -- fork-safety)
    import backend.supabase_client as _sb
    _sb._supabase_raw = None
    _sb._supabase_resilient = None

    _logger.info("Celery worker process init: Sentry + Supabase client globals reset")
