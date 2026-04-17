"""Phase 4.1 PR2 Subtask 3b — grading_tasks integration tests in Celery eager mode."""
from unittest.mock import patch, MagicMock
import pytest


# NOTE: fixture named `grading_tasks_env` (not `celery_env`) to avoid collision
# with tests/test_celery_app.py's fixture. Pops backend.tasks for full isolation.
@pytest.fixture(autouse=True)
def grading_tasks_env(monkeypatch):
    monkeypatch.setenv('CELERY_BROKER_URL', 'redis://localhost:6379/15')
    import sys
    sys.modules.pop('backend.celery_app', None)
    sys.modules.pop('backend.tasks', None)
    sys.modules.pop('backend.tasks.grading_tasks', None)


@pytest.fixture
def eager_celery():
    from backend.celery_app import celery_app
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield celery_app
    celery_app.conf.task_always_eager = False


def test_task_calls_grade_portal_submission_sync(eager_celery):
    """Happy path: task fetches context, calls sync, returns."""
    from backend.tasks.grading_tasks import grade_portal_submission
    fake_ctx = {
        'assessment': {'questions': []},
        'answers': {},
        'student_info': {'name': 'Test'},
        'teacher_config': {},
    }
    with patch('backend.services.portal_grading.fetch_submission_full_context', return_value=fake_ctx):
        with patch('backend.services.portal_grading.grade_portal_submission_sync') as mock_sync:
            grade_portal_submission.apply(
                args=['sub-1', 'teacher-1', 'submissions'],
                kwargs={'district_id': 'd-1', 'user_id': 'u-1'},
            )
    mock_sync.assert_called_once()
    ck = mock_sync.call_args.kwargs
    assert ck['district_id'] == 'd-1'
    assert ck['user_id'] == 'u-1'
    assert ck['task_id'] is not None


def test_task_returns_early_when_submission_missing(eager_celery):
    from backend.tasks.grading_tasks import grade_portal_submission
    with patch('backend.services.portal_grading.fetch_submission_full_context', return_value=None):
        result = grade_portal_submission.apply(args=['nope', 'teacher-1', 'submissions'])
    assert result.successful()


def test_task_sets_sentry_user_with_hashed_uid(eager_celery):
    """user_id is HASHED (sha256[:12]) before set_user to match before_send scrubber format.
    Without the hash, the scrubber would stomp it — fix shipped in PR #83.
    """
    import hashlib
    from backend.tasks.grading_tasks import grade_portal_submission
    with patch('backend.services.portal_grading.fetch_submission_full_context', return_value={
        'assessment': {'questions': []}, 'answers': {}, 'student_info': {}, 'teacher_config': {},
    }):
        with patch('backend.services.portal_grading.grade_portal_submission_sync'):
            with patch('sentry_sdk.set_user') as mock_user:
                with patch('sentry_sdk.set_tag') as mock_tag:
                    grade_portal_submission.apply(
                        args=['sub-1', 'teacher-1', 'submissions'],
                        kwargs={'district_id': 'd-123', 'user_id': 'u-456'},
                    )
    expected = hashlib.sha256(b'u-456').hexdigest()[:12]
    mock_user.assert_called_with({"id": expected})
    mock_tag.assert_called_with("district", "d-123")


def test_on_failure_marks_submission_failed(eager_celery):
    """on_failure calls _safe_update_submission directly (update_submission doesn't exist)."""
    from backend.tasks.grading_tasks import PortalGradingTask
    task = PortalGradingTask()
    task.name = 'grading.portal_submission'

    with patch('backend.services.portal_grading._safe_update_submission') as mock_update:
        with patch('backend.supabase_client.get_supabase', return_value=MagicMock()):
            task.on_failure(
                exc=RuntimeError('boom'),
                task_id='some-task-id',
                args=['sub-1', 'teacher-1', 'submissions'],
                kwargs={},
                einfo=None,
            )
    assert mock_update.called
    ca = mock_update.call_args
    # _safe_update_submission(sb, submission_id, update_fields_dict, table_name=...)
    update_fields = ca.args[2]
    assert update_fields['status'] == 'failed'
    assert update_fields['error_message'] == 'boom'
    assert ca.kwargs['table_name'] == 'submissions'


def test_on_failure_no_submission_id_is_noop(eager_celery):
    """Missing submission_id → on_failure returns silently, no DB write."""
    from backend.tasks.grading_tasks import PortalGradingTask
    task = PortalGradingTask()
    task.name = 'grading.portal_submission'
    with patch('backend.services.portal_grading._safe_update_submission') as mock_update:
        task.on_failure(exc=RuntimeError('x'), task_id='t', args=[], kwargs={}, einfo=None)
    mock_update.assert_not_called()


def test_fetch_submission_full_context_reads_accommodations_from_published_settings():
    """CRITICAL: accommodations live on published_assessments.settings.student_accommodations,
    NOT on the submissions row (that column doesn't exist — verified against schema).
    """
    from backend.services.portal_grading import fetch_submission_full_context

    # Build a mock Supabase client that returns:
    #   - submission row with assessment_id='a-1', answers, student_name
    #   - published_assessments row with settings.student_accommodations={'iep': True}
    sub_row = MagicMock()
    sub_row.data = {
        'id': 'sub-1',
        'assessment_id': 'a-1',
        'answers': {'q1': 'answer'},
        'student_name': 'Ana',
        'student_email': 'ana@example.com',
    }
    pub_row = MagicMock()
    pub_row.data = {
        'id': 'a-1',
        'assessment': {'questions': [{'id': 'q1'}]},
        'settings': {'student_accommodations': {'iep': True, 'extended_time': 1.5}},
    }

    class FakeTable:
        def __init__(self, name): self.name = name
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def single(self): return self
        def execute(self):
            if self.name == 'submissions':
                return sub_row
            return pub_row
    class FakeSB:
        def table(self, name): return FakeTable(name)

    with patch('backend.supabase_client.get_supabase', return_value=FakeSB()):
        with patch('backend.services.grading_service.load_teacher_config', return_value={}):
            ctx = fetch_submission_full_context('submissions', 'sub-1', 'teacher-1')

    assert ctx is not None
    assert ctx['student_accommodations'] == {'iep': True, 'extended_time': 1.5}
    assert ctx['assessment'] == {'questions': [{'id': 'q1'}]}
    assert ctx['student_info']['name'] == 'Ana'


def test_fetch_submission_full_context_returns_none_when_submission_missing():
    from backend.services.portal_grading import fetch_submission_full_context
    empty = MagicMock()
    empty.data = None

    class FakeTable:
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def single(self): return self
        def execute(self): return empty
    class FakeSB:
        def table(self, name): return FakeTable()

    with patch('backend.supabase_client.get_supabase', return_value=FakeSB()):
        assert fetch_submission_full_context('submissions', 'nope', 't-1') is None


def test_fetch_submission_full_context_none_when_no_sb():
    """If Supabase client isn't available, return None gracefully."""
    from backend.services.portal_grading import fetch_submission_full_context
    with patch('backend.supabase_client.get_supabase', return_value=None):
        assert fetch_submission_full_context('submissions', 'sub-1', 't-1') is None


def test_fetch_submission_full_context_captures_published_assessments_errors_to_sentry():
    """When the published_assessments lookup raises, we capture to Sentry
    and continue with fallback accommodations path (not silently swallow)."""
    from backend.services.portal_grading import fetch_submission_full_context

    sub_row = MagicMock()
    sub_row.data = {
        'id': 'sub-1',
        'assessment_id': 'a-1',
        'answers': {},
        'student_name': 'Test',
        'accommodations': {'iep': True},  # class-based fallback source
    }

    class FakeTable:
        def __init__(self, name): self.name = name
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def single(self): return self
        def execute(self):
            if self.name == 'submissions':
                return sub_row
            raise RuntimeError('published_assessments unreachable')
    class FakeSB:
        def table(self, name): return FakeTable(name)

    with patch('backend.supabase_client.get_supabase', return_value=FakeSB()):
        with patch('backend.services.grading_service.load_teacher_config', return_value={}):
            with patch('backend.services.portal_grading.sentry_sdk.capture_exception') as mock_cap:
                ctx = fetch_submission_full_context('submissions', 'sub-1', 'teacher-1')

    assert ctx is not None  # fetch did not fail overall
    assert mock_cap.called  # Sentry captured the published_assessments error
    # Fallback accommodations came from data.get('accommodations')
    assert ctx['student_accommodations'] == {'iep': True}


def test_fetch_submission_full_context_normalizes_student_id_on_submissions_table():
    """Join-code path: the `submissions` table has NO student_id column. The
    legacy thread spawn in student_portal_routes hard-codes student_id=""
    (empty string) when building student_info. fetch_submission_full_context
    must match that contract to avoid divergence between the Celery and
    thread code paths (consumers like load_student_history(teacher_id, id)
    would see None vs "" depending on path otherwise).
    """
    sub_row = MagicMock()
    sub_row.data = {
        'id': 'sub-1',
        'assessment_id': 'a-1',
        'answers': {},
        'student_name': 'Ana',
        # Note: no student_id — submissions table has no such column
    }
    pub_row = MagicMock()
    pub_row.data = {'id': 'a-1', 'assessment': {'questions': []}, 'settings': {}}

    class FakeTable:
        def __init__(self, name): self.name = name
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def single(self): return self
        def execute(self):
            return sub_row if self.name == 'submissions' else pub_row
    class FakeSB:
        def table(self, name): return FakeTable(name)

    from backend.services.portal_grading import fetch_submission_full_context
    with patch('backend.supabase_client.get_supabase', return_value=FakeSB()):
        with patch('backend.services.grading_service.load_teacher_config', return_value={}):
            ctx = fetch_submission_full_context('submissions', 'sub-1', 'teacher-1')

    assert ctx is not None
    # CRITICAL parity check: empty string, NOT None
    assert ctx['student_info']['student_id'] == ''
    assert isinstance(ctx['student_info']['student_id'], str)


def test_fetch_submission_full_context_preserves_student_id_on_student_submissions_table():
    """Class-based path: the `student_submissions` table DOES have real
    student_ids. Normalization only applies to the join-code `submissions`
    table — class-based path keeps whatever the row has.
    """
    sub_row = MagicMock()
    sub_row.data = {
        'id': 'sub-1',
        'assessment_id': 'a-1',
        'answers': {},
        'student_name': 'Ana',
        'student_id': 'real-student-id-42',
    }
    pub_row = MagicMock()
    pub_row.data = {'id': 'a-1', 'assessment': {'questions': []}, 'settings': {}}

    class FakeTable:
        def __init__(self, name): self.name = name
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def single(self): return self
        def execute(self):
            return sub_row if self.name == 'student_submissions' else pub_row
    class FakeSB:
        def table(self, name): return FakeTable(name)

    from backend.services.portal_grading import fetch_submission_full_context
    with patch('backend.supabase_client.get_supabase', return_value=FakeSB()):
        with patch('backend.services.grading_service.load_teacher_config', return_value={}):
            ctx = fetch_submission_full_context('student_submissions', 'sub-1', 'teacher-1')

    assert ctx is not None
    assert ctx['student_info']['student_id'] == 'real-student-id-42'


def test_task_aborts_when_assessment_is_none(eager_celery):
    """Guard against partial context from fetch_submission_full_context.

    If published_assessments fetch fails (captured to Sentry inside the
    helper), ctx is non-None but ctx['assessment'] is None. Without this
    guard, the pure function dereferences None and mark the row
    grading_failed via its outer except — but that's a noisier failure path
    than short-circuiting with a clear signal. Task now logs + Sentry-captures
    + writes status='failed' + error_message + returns early.
    """
    partial_ctx = {
        'assessment': None,  # published_assessments fetch failed upstream
        'answers': {'q1': 'a'},
        'student_info': {'name': 'Test', 'student_name': 'Test'},
        'teacher_config': {},
        'student_accommodations': None,
    }
    from backend.tasks.grading_tasks import grade_portal_submission
    with patch('backend.services.portal_grading.fetch_submission_full_context', return_value=partial_ctx):
        with patch('backend.services.portal_grading.grade_portal_submission_sync') as mock_sync:
            with patch('backend.services.portal_grading._safe_update_submission') as mock_update:
                with patch('backend.supabase_client.get_supabase', return_value=MagicMock()):
                    result = grade_portal_submission.apply(
                        args=['sub-1', 'teacher-1', 'submissions'],
                    )
    assert result.successful()  # task returns cleanly
    mock_sync.assert_not_called()  # sync function never invoked
    # Row was marked failed with explanatory error_message
    assert mock_update.called
    call_args = mock_update.call_args
    update_fields = call_args.args[2]
    assert update_fields['status'] == 'failed'
    assert 'Assessment content unavailable' in update_fields['error_message']
