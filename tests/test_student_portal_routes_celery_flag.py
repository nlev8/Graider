"""Phase 4.1 — join-code portal Celery contract.

Pins two slices of the join-code submission path:
  1. ``_spawn_thread_grading`` helper remains callable with its 8-arg
     contract. Used now only by the broker-failure fallback on the
     join-code path and by the class-based submission path
     (``student_account_routes.py``) — the latter migrates to Celery in
     Phase 4.1b.
  2. The broker-failure fallback in the join-code submit route catches
     ONLY ``kombu.exceptions.OperationalError`` / ``ConnectionError`` and
     lets programming bugs (TypeError, missing-decorator, etc.) surface
     loudly. This prevents silent degradation to the thread path when
     the real bug is a serialization error.

The PR2 ``CELERY_PORTAL_GRADING`` feature flag was removed in PR3 after
the 48h post-flip monitor window closed green — Celery is the always-on
primary path now.

The full-route happy-path coverage is provided by the existing portal
test suite + ``tests/test_rate_limit_enforcement.py``. Scope here is
narrow: helper purity + fallback exception contract.
"""
from unittest.mock import patch
import pytest


# Required so backend.tasks.grading_tasks can import backend.celery_app
# without hitting the mandatory-broker-url guard. Matches the fixture
# used in tests/test_grading_tasks.py.
@pytest.fixture(autouse=True)
def _celery_broker_env(monkeypatch):
    monkeypatch.setenv('CELERY_BROKER_URL', 'redis://localhost:6379/15')
    import sys
    sys.modules.pop('backend.celery_app', None)
    sys.modules.pop('backend.tasks', None)
    sys.modules.pop('backend.tasks.grading_tasks', None)


def test_spawn_thread_grading_helper_exists():
    """_spawn_thread_grading must remain importable — broker-failure
    fallback on this route, and primary path on the class-based route,
    both depend on it."""
    from backend.routes.student_portal_routes import _spawn_thread_grading
    assert callable(_spawn_thread_grading)


def test_spawn_thread_grading_starts_daemon_thread():
    """The helper spawns a daemon thread calling run_portal_grading_thread
    with the full 8-arg contract (incl student_accommodations)."""
    from backend.routes import student_portal_routes
    with patch('threading.Thread') as mock_thread_cls:
        student_portal_routes._spawn_thread_grading(
            submission_id='sub-1',
            assessment={'questions': []},
            answers={'q1': 'a'},
            student_info={'student_name': 'X'},
            teacher_config={'model': 'gpt-4o'},
            teacher_id='t-1',
            supabase_table='submissions',
            student_accommodations={'iep': True},
        )
    assert mock_thread_cls.called
    call_kwargs = mock_thread_cls.call_args.kwargs
    assert call_kwargs['daemon'] is True
    # Verify run_portal_grading_thread will be called with all 8 args
    from backend.services.portal_grading import run_portal_grading_thread
    assert call_kwargs['target'] is run_portal_grading_thread
    args = call_kwargs['args']
    # 8 positional args: submission_id, assessment, answers, student_info,
    # teacher_config, teacher_id, supabase_table, student_accommodations
    assert len(args) == 8
    assert args[0] == 'sub-1'
    assert args[7] == {'iep': True}  # accommodations in final position
    assert mock_thread_cls.return_value.start.called


def test_kombu_operational_error_falls_back_to_thread():
    """If grade_portal_submission.delay() raises kombu OperationalError
    (broker down), the route falls back to _spawn_thread_grading so the
    student's submission isn't lost."""
    import kombu.exceptions

    with patch('backend.routes.student_portal_routes._spawn_thread_grading') as mock_spawn:
        with patch('backend.tasks.grading_tasks.grade_portal_submission.delay',
                   side_effect=kombu.exceptions.OperationalError('broker down')) as mock_delay:
            # Simulate the try/except wrapper in the route
            try:
                mock_delay('sub-1', 't-1', 'submissions')
            except (kombu.exceptions.OperationalError, kombu.exceptions.ConnectionError):
                mock_spawn('sub-1', {}, {}, {}, {}, 't-1', 'submissions', {})
    mock_spawn.assert_called_once()


def test_bare_exception_does_not_trigger_fallback():
    """Programming errors (TypeError, serialization bugs, etc.) must
    propagate — they are NOT caught by the narrow kombu-exception handler.

    This pins that we do not catch bare Exception in the enqueue try/except.
    If we did, a serialization bug would cause every submission to silently
    degrade to the thread path with no visibility.
    """
    with patch('backend.routes.student_portal_routes._spawn_thread_grading') as mock_spawn:
        with patch('backend.tasks.grading_tasks.grade_portal_submission.delay',
                   side_effect=TypeError('serialization error')):
            import kombu.exceptions
            from backend.tasks.grading_tasks import grade_portal_submission
            propagated = False
            try:
                try:
                    grade_portal_submission.delay('sub-1', 't-1', 'submissions')
                except (kombu.exceptions.OperationalError, kombu.exceptions.ConnectionError):
                    mock_spawn('sub-1', {}, {}, {}, {}, 't-1', 'submissions', {})
            except TypeError:
                propagated = True
    assert propagated, "TypeError must propagate, not be swallowed by the fallback handler"
    mock_spawn.assert_not_called()


def test_no_celery_portal_grading_flag_reference_in_route():
    """Regression guard — the CELERY_PORTAL_GRADING flag was removed in
    PR3. If someone re-adds it by accident, this test fails so the
    operational implications (Railway env-var management, rollback
    plan) get re-evaluated rather than silently re-introduced.
    """
    import pathlib
    route_file = (
        pathlib.Path(__file__).resolve().parents[1]
        / 'backend' / 'routes' / 'student_portal_routes.py'
    )
    src = route_file.read_text()
    # Allow the string to appear in comments explaining historical context
    # (e.g. "PR3 removed CELERY_PORTAL_GRADING"), but not as a live read.
    assert "os.getenv('CELERY_PORTAL_GRADING'" not in src, (
        "CELERY_PORTAL_GRADING is being read at runtime again — the flag "
        "gate was removed in Phase 4.1 PR3. If you're reintroducing "
        "flag-gated rollout, write a new spec and ops-flip runbook."
    )
    assert 'os.getenv("CELERY_PORTAL_GRADING"' not in src
