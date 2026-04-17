"""Phase 4.1 PR1 -- verify celery app configures correctly under test."""
import os
import sys

import pytest


@pytest.fixture
def celery_env(monkeypatch):
    """Set broker URL to a test-only Redis DB and force re-import."""
    monkeypatch.setenv('CELERY_BROKER_URL', 'redis://localhost:6379/15')
    sys.modules.pop('backend.celery_app', None)
    sys.modules.pop('backend.tasks', None)
    sys.modules.pop('backend.tasks.grading_tasks', None)


def test_celery_app_imports_with_broker_url(celery_env):
    """celery_app should import cleanly when CELERY_BROKER_URL is set."""
    from backend.celery_app import celery_app
    assert celery_app is not None
    assert celery_app.conf.broker_url == 'redis://localhost:6379/15'


def test_celery_app_fails_without_broker_url(monkeypatch):
    """Importing celery_app without CELERY_BROKER_URL raises RuntimeError."""
    monkeypatch.delenv('CELERY_BROKER_URL', raising=False)
    sys.modules.pop('backend.celery_app', None)
    with pytest.raises(RuntimeError, match='CELERY_BROKER_URL'):
        import backend.celery_app  # noqa: F401


def test_celery_app_has_json_serializer(celery_env):
    from backend.celery_app import celery_app
    assert celery_app.conf.task_serializer == 'json'
    assert celery_app.conf.accept_content == ['json']


def test_celery_app_no_result_backend(celery_env):
    from backend.celery_app import celery_app
    assert celery_app.conf.result_backend is None


def test_celery_app_durability_settings(celery_env):
    """Worker crash durability — PR2's row-level dedup only works if the
    message survives a worker SIGKILL. Both flags must be set.

    - task_acks_late: broker acks after task completion, not on delivery.
    - task_reject_on_worker_lost: worker-death case re-queues instead of
      implicit-ack (Celery's poison-pill-safe default would silently drop).
    """
    from backend.celery_app import celery_app
    assert celery_app.conf.task_acks_late is True, (
        "task_acks_late must be True so worker SIGKILL/OOM mid-grade redelivers "
        "the message. Without it, the Phase 4.1 row-level dedup columns "
        "(grading_task_id + grading_started_at) never get a chance to reclaim."
    )
    assert celery_app.conf.task_reject_on_worker_lost is True, (
        "task_reject_on_worker_lost must be True. Celery's default for lost "
        "workers is implicit-ack to avoid poison-pill loops — that defeats "
        "acks_late in exactly the Railway-OOM scenario we care about."
    )


def test_stub_task_registered(celery_env):
    from backend.celery_app import celery_app
    # Trigger autodiscover
    celery_app.autodiscover_tasks(['backend.tasks'], force=True)
    # Also force-import the module to register the task decorator
    import backend.tasks.grading_tasks  # noqa: F401
    assert 'grading.portal_submission' in celery_app.tasks


def test_task_registered_and_callable_in_eager_mode(celery_env):
    """Phase 4.1 PR2 subtask 3b: the real task returns None (Supabase row is
    source of truth). Verify the task is registered, reachable in eager mode,
    and succeeds when its downstream context fetch is stubbed out.

    This replaces PR1's test_stub_task_runs_in_eager_mode, which asserted the
    stub-return shape (`{'status': 'stub', ...}`). The real task no longer
    returns that dict — it delegates to grade_portal_submission_sync and
    returns None.
    """
    from unittest.mock import patch
    from backend.celery_app import celery_app
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    try:
        import backend.tasks.grading_tasks  # noqa: F401
        from backend.tasks.grading_tasks import grade_portal_submission
        assert 'grading.portal_submission' in celery_app.tasks

        # Stub out the downstream fetch so the task returns cleanly without
        # needing a live Supabase client.
        with patch(
            'backend.services.portal_grading.fetch_submission_full_context',
            return_value=None,
        ):
            result = grade_portal_submission.apply(
                args=['test-submission-id', 'test-teacher-id', 'submissions']
            )
        assert result.successful()
    finally:
        celery_app.conf.task_always_eager = False
