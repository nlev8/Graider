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


def test_stub_task_registered(celery_env):
    from backend.celery_app import celery_app
    # Trigger autodiscover
    celery_app.autodiscover_tasks(['backend.tasks'], force=True)
    # Also force-import the module to register the task decorator
    import backend.tasks.grading_tasks  # noqa: F401
    assert 'grading.portal_submission' in celery_app.tasks


def test_stub_task_runs_in_eager_mode(celery_env):
    """Stub task should log and return when run synchronously via apply()."""
    from backend.celery_app import celery_app
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    try:
        import backend.tasks.grading_tasks  # noqa: F401
        from backend.tasks.grading_tasks import grade_portal_submission
        result = grade_portal_submission.apply(
            args=['test-submission-id', 'test-teacher-id', 'submissions']
        )
        assert result.successful()
        payload = result.get()
        assert payload['status'] == 'stub'
        assert payload['submission_id'] == 'test-submission-id'
    finally:
        celery_app.conf.task_always_eager = False
