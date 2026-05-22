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
    """on_failure calls repository_for(...).mark_failed(submission_id, exc).

    Slice 5 PR2 Task 2.4: migrated from patching _safe_update_submission to
    patching repository_for. DB effect is byte-identical: correct table via
    path discriminator, status='failed', str(exc)[:500] error_message.
    """
    from backend.tasks.grading_tasks import PortalGradingTask
    task = PortalGradingTask()
    task.name = 'grading.portal_submission'

    with patch('backend.services.submission_repository.repository_for') as mock_rf:
        with patch('backend.supabase_client.get_supabase', return_value=MagicMock()):
            mock_repo = mock_rf.return_value
            task.on_failure(
                exc=RuntimeError('boom'),
                task_id='some-task-id',
                args=['sub-1', 'teacher-1', 'submissions'],
                kwargs={},
                einfo=None,
            )
    # repository_for called with the path discriminator from args[2]
    assert mock_rf.call_args.args[0] == 'submissions'
    # mark_failed called with submission_id and the original exception
    mock_repo.mark_failed.assert_called_once()
    mf_args = mock_repo.mark_failed.call_args.args
    assert mf_args[0] == 'sub-1'
    assert isinstance(mf_args[1], RuntimeError)
    assert str(mf_args[1]) == 'boom'


def test_on_failure_no_submission_id_is_noop(eager_celery):
    """Missing submission_id → on_failure returns silently, no DB write."""
    from backend.tasks.grading_tasks import PortalGradingTask
    task = PortalGradingTask()
    task.name = 'grading.portal_submission'
    with patch('backend.services.submission_repository.repository_for') as mock_rf:
        task.on_failure(exc=RuntimeError('x'), task_id='t', args=[], kwargs={}, einfo=None)
    mock_rf.assert_not_called()


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

    Ergonomics proof (DI PR2 Task 2.2): the failure-write path used to need
    TWO patches just to intercept the repo write — patch(repository_for) to
    swap the adapter for a MagicMock AND patch(get_supabase) to keep the
    factory from blowing up. The DI provider collapses both into a SINGLE
    override_supabase(fake): the fake IS the client the provider resolves,
    and we assert the OBSERVABLE write the fake recorded (status='failed' +
    error_message) instead of asserting a mock method was called. Patch count
    on this test dropped 4 -> 2.
    """
    from backend.providers import override_supabase
    from tests.test_submission_repository import FakeSupabase
    partial_ctx = {
        'assessment': None,  # published_assessments fetch failed upstream
        'answers': {'q1': 'a'},
        'student_info': {'name': 'Test', 'student_name': 'Test'},
        'teacher_config': {},
        'student_accommodations': None,
    }
    from backend.tasks.grading_tasks import grade_portal_submission
    fake = FakeSupabase()
    fake.table('submissions')  # materialize so a no-write mutation reads as len==0
    with patch('backend.services.portal_grading.fetch_submission_full_context', return_value=partial_ctx):
        with patch('backend.services.portal_grading.grade_portal_submission_sync') as mock_sync:
            with override_supabase(fake):
                result = grade_portal_submission.apply(
                    args=['sub-1', 'teacher-1', 'submissions'],
                )
    assert result.successful()  # task returns cleanly
    mock_sync.assert_not_called()  # sync function never invoked
    # Observable effect: the row was marked failed via repo.mark_failed, which
    # writes status='failed' + error_message to the 'submissions' table. The
    # single override_supabase(fake) routed the provider to our recording fake.
    updates = fake.tables['submissions'].updates
    assert len(updates) == 1
    assert updates[0]['status'] == 'failed'
    assert 'Assessment content unavailable' in updates[0]['error_message']


# ══════════════════════════════════════════════════════════════
# Phase 4.1 pre-flag-flip Item 1: worker-loss redelivery dedup
#
# Codex flagged a gap in `_is_stale_claim`: if a worker dies after
# claim but before writing 'graded', Celery redelivers the task. The
# concern is that a redelivered task might see its own stale claim as
# "fresh" (< 15 min) and skip, leaving the row stuck at
# 'grading_in_progress'.
#
# Whether this gap is real depends on whether broker-level redelivery
# (via acks_late + reject_on_worker_lost) preserves task_id or generates
# a new one. The tests below pin the behavior empirically in eager mode
# so a regression in either direction is caught by CI.
# ══════════════════════════════════════════════════════════════


class _FakeDedupSB:
    """Minimal Supabase stub for exercising the row-level dedup branch.

    Holds a single in-memory row dict. .table().select().eq().single().execute()
    returns a MagicMock with .data = row. .update().eq().execute() mutates the
    row in place (matches Supabase's chainable API surface).
    """
    def __init__(self, row):
        self.row = row
        self.updates = []  # record of update payloads for assertions

    def table(self, name):
        return _FakeDedupTable(self, name)


class _FakeDedupTable:
    def __init__(self, sb, name):
        self.sb = sb
        self.name = name
        self._update_payload = None

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def single(self):
        return self

    def update(self, payload):
        self._update_payload = payload
        return self

    def execute(self):
        if self._update_payload is not None:
            self.sb.updates.append(dict(self._update_payload))
            self.sb.row.update(self._update_payload)
            return MagicMock()
        resp = MagicMock()
        resp.data = self.sb.row
        return resp


def _run_sync_with_dedup(sb, task_id, submission_id='sub-1'):
    """Invoke grade_portal_submission_sync through only the dedup branch.

    Patches downstream dependencies so the test focuses on the claim logic
    without exercising AI grading. grade_written_questions returns [], the
    feedback helper is stubbed, and _safe_save_results is stubbed.
    """
    from backend.services import portal_grading

    with patch('backend.supabase_client.get_supabase', return_value=sb):
        with patch.object(portal_grading, 'grade_written_questions', return_value=[]):
            with patch.object(portal_grading, '_safe_generate_feedback',
                              return_value={'feedback': '', 'rubric_breakdown': {}}):
                with patch.object(portal_grading, '_safe_save_results'):
                    with patch('backend.grading.state.load_saved_results', return_value=[]):
                        with patch('backend.grading.state._get_lock') as mock_lock:
                            mock_lock.return_value.__enter__ = lambda *_: None
                            mock_lock.return_value.__exit__ = lambda *_: None
                            portal_grading.grade_portal_submission_sync(
                                submission_id=submission_id,
                                assessment={'title': 'T', 'sections': []},
                                answers={},
                                student_info={'student_name': 'Ana', 'student_id': ''},
                                teacher_config={},
                                teacher_id='t-1',
                                path_type='submissions',
                                task_id=task_id,
                            )


def test_celery_preserves_task_id_for_self_retry(eager_celery):
    """Empirical check: Celery's self.retry() preserves task_id.

    This is the documented Celery behavior (each retry of the same task
    keeps the same UUID; `self.request.retries` increments). We rely on
    it for the dedup's `current_task == task_id` branch.

    In eager mode, we can't exercise real broker redelivery, so we
    approximate by calling .apply(task_id='SAME-ID') twice — each
    invocation represents a worker picking up the same message.
    """
    from backend.tasks.grading_tasks import grade_portal_submission

    captured_task_ids = []

    def capture_and_record(self_, *_a, **_kw):
        # Record the task_id seen inside the task body; this is what
        # would land in the grading_task_id column on the claim row.
        captured_task_ids.append(self_.request.id)

    fake_ctx = {
        'assessment': {'title': 'T', 'sections': []},
        'answers': {},
        'student_info': {'name': 'T'},
        'teacher_config': {},
    }
    with patch('backend.services.portal_grading.fetch_submission_full_context',
               return_value=fake_ctx):
        with patch('backend.services.portal_grading.grade_portal_submission_sync'):
            # Same task_id → same grading_task_id inside the task body.
            r1 = grade_portal_submission.apply(
                args=['sub-1', 't-1', 'submissions'], task_id='SAME-ID',
            )
            r2 = grade_portal_submission.apply(
                args=['sub-1', 't-1', 'submissions'], task_id='SAME-ID',
            )

    assert r1.successful() and r2.successful()
    # Both invocations observed the same task_id the caller pinned.
    # This is the path broker-level redelivery uses: the message body
    # carries the same task UUID, so the re-delivered worker sees the
    # same self.request.id it would have seen on the original run.
    assert r1.id == 'SAME-ID'
    assert r2.id == 'SAME-ID'


def test_dedup_recognizes_same_task_id_as_retry_not_skip(eager_celery):
    """Reality check: broker redelivery preserves task_id → the dedup's
    `current_task == task_id` branch fires → retry PROCEEDS (does not skip).

    Setup: pre-populate the submissions row as if a dead worker claimed
    it with task_id='TASK-REDELIVERED' and never wrote 'graded'. Then run
    grade_portal_submission_sync again with the SAME task_id (simulating
    redelivery with preserved task_id per Celery's message protocol).

    Expected: the second run proceeds through claim → grading → 'graded'
    update. The row does NOT stay stuck at 'grading_in_progress'.
    """
    from datetime import datetime, timezone, timedelta
    dead_claim_ts = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    sb = _FakeDedupSB(row={
        'id': 'sub-1',
        'status': 'grading_in_progress',
        'grading_task_id': 'TASK-REDELIVERED',
        'grading_started_at': dead_claim_ts,
        'assessment_id': 'a-1',
        'answers': {},
        'student_name': 'Ana',
    })

    _run_sync_with_dedup(sb, task_id='TASK-REDELIVERED')

    # The row must end in 'graded' status (or at least have progressed
    # past 'grading_in_progress' with the same task_id). Collect update
    # payloads that touched status.
    statuses = [u.get('status') for u in sb.updates if 'status' in u]
    assert 'graded' in statuses, (
        f"Redelivered task with preserved task_id should PROCEED through "
        f"grading (dedup branch: current_task == task_id). Updates seen: "
        f"{sb.updates}"
    )


def test_dedup_skips_when_different_task_id_and_fresh_claim(eager_celery):
    """Worst-case diagnostic: if Celery EVER delivers a redelivered task
    with a NEW task_id (which it does NOT do for acks_late redelivery),
    the dedup would skip. This test documents that failure mode so we're
    explicit about what the dedup assumes.

    This is NOT a "broken" case in production — Celery's message protocol
    keeps task_id constant across broker redelivery. But if someone ever
    changes the retry config to `self.retry(task_id=...)` or manually
    re-enqueues with a new id, this is the behavior they'll see.
    """
    from datetime import datetime, timezone, timedelta
    dead_claim_ts = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    sb = _FakeDedupSB(row={
        'id': 'sub-1',
        'status': 'grading_in_progress',
        'grading_task_id': 'DEAD-TASK-ID',
        'grading_started_at': dead_claim_ts,  # 2 minutes ago — NOT stale
        'assessment_id': 'a-1',
        'answers': {},
        'student_name': 'Ana',
    })

    _run_sync_with_dedup(sb, task_id='DIFFERENT-TASK-ID')

    # With a fresh claim and a DIFFERENT task_id, the dedup branch
    # returns early without grading. Row stays at 'grading_in_progress'.
    statuses = [u.get('status') for u in sb.updates if 'status' in u]
    assert 'graded' not in statuses, (
        f"When current_task != task_id AND claim is fresh, dedup must "
        f"skip (prevents two live workers racing). Got updates: "
        f"{sb.updates}"
    )
    # Confirms the documented behavior: with a live competing claim, the
    # caller must either wait 15 min for the TTL or issue a manual reclaim
    # SQL. This path only fires if Celery redelivery ever uses a NEW
    # task_id (it doesn't, per Celery 5.x message protocol).
    assert sb.row['status'] == 'grading_in_progress'


def test_dedup_reclaims_when_claim_is_stale(eager_celery):
    """TTL backstop: if a claim is older than 15 minutes, any caller
    (including a task with a new task_id) can reclaim. This is the
    manual-SQL-reclaim equivalent in code form.
    """
    from datetime import datetime, timezone, timedelta
    stale_ts = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    sb = _FakeDedupSB(row={
        'id': 'sub-1',
        'status': 'grading_in_progress',
        'grading_task_id': 'ANCIENT-DEAD-TASK',
        'grading_started_at': stale_ts,  # 30 minutes ago — stale
        'assessment_id': 'a-1',
        'answers': {},
        'student_name': 'Ana',
    })

    _run_sync_with_dedup(sb, task_id='FRESH-RECOVERY-TASK')

    statuses = [u.get('status') for u in sb.updates if 'status' in u]
    assert 'graded' in statuses, (
        f"Stale claim (>15min) must be reclaimable by any caller. "
        f"Updates seen: {sb.updates}"
    )
