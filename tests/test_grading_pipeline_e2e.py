"""Phase 4.1 pre-flag-flip Item 2 — end-to-end grading pipeline integration test.

The existing suite stubs the seams:
  - test_grading_tasks.py stubs fetch_submission_full_context + grade_portal_submission_sync
  - test_grade_portal_submission_sync.py stubs the sync body
  - test_student_portal_routes_celery_flag.py stubs grade_portal_submission.delay

No test exercises the full chain: task invoked → context fetched from a Supabase
mock → grade_portal_submission_sync runs → Supabase row written with
'graded' status → teacher results storage upserted.

This test pins the SHAPE of the end-to-end flow in eager mode. It verifies
that dispatching grade_portal_submission.apply(...) does in fact produce:
  1. A fetch from the submissions table
  2. A fetch from the published_assessments table
  3. A call into grade_portal_submission_sync (the pure grading body)
  4. A terminal Supabase update with status='graded'
  5. A save to teacher results storage

AI grading itself (grade_per_question / generate_feedback) is stubbed — the
goal is pipeline wiring, not scoring accuracy. tests/test_assignment_grader.py
covers the AI layer.
"""
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def celery_env(monkeypatch):
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


class FakeSupabase:
    """Fake Supabase client holding in-memory submissions + published_assessments.

    Exposes .table(name) → FakeTable with the chainable API surface used by
    portal_grading.py: .select().eq().single().execute() → MagicMock with .data
    and .update().eq().execute() → mutates the row.

    Records all state mutations on `self.updates` for test assertions.
    """
    def __init__(self, submission_row, published_assessment_row):
        self.rows = {
            'submissions': submission_row,
            'published_assessments': published_assessment_row,
        }
        # (table_name, payload) tuples — ordered so tests can assert the
        # sequence of writes the pipeline performs.
        self.updates = []

    def table(self, name):
        return FakeTable(self, name)


class FakeTable:
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
            self.sb.updates.append((self.name, dict(self._update_payload)))
            # Mutate the in-memory row so subsequent reads observe the write
            if self.name in self.sb.rows and self.sb.rows[self.name] is not None:
                self.sb.rows[self.name].update(self._update_payload)
            return MagicMock()
        # Read path: return a MagicMock with .data populated
        resp = MagicMock()
        resp.data = self.sb.rows.get(self.name)
        return resp


def _build_fake_supabase():
    """Build a Supabase mock with one submission + one published_assessment.

    The assessment has one multiple-choice question (instantly gradable)
    and one short-answer question (AI-graded, will be stubbed).
    """
    submission_row = {
        'id': 'sub-e2e-1',
        'assessment_id': 'asm-e2e-1',
        'student_name': 'E2E Student',
        'student_email': 'e2e@example.com',
        'answers': {
            '0-0': 'A',         # MC answer (correct)
            '0-1': 'My essay',  # short-answer text
        },
        'status': 'submitted',
        # Not yet claimed or graded
        'grading_task_id': None,
        'grading_started_at': None,
    }
    published_assessment_row = {
        'id': 'asm-e2e-1',
        'assessment': {
            'title': 'E2E Integration Test Assignment',
            'sections': [
                {
                    'name': 'Mixed section',
                    'questions': [
                        {
                            'type': 'multiple_choice',
                            'question': 'Pick A',
                            'answer': 'A',
                            'points': 5,
                        },
                        {
                            'type': 'short_answer',
                            'question': 'Explain X',
                            'answer': 'X is ...',
                            'points': 10,
                        },
                    ],
                },
            ],
        },
        'settings': {},  # no accommodations for this baseline test
    }
    return FakeSupabase(submission_row, published_assessment_row)


def test_full_chain_task_to_supabase_write(eager_celery):
    """End-to-end: task.apply → fetch_submission_full_context → sync →
    _safe_update_submission writes 'graded' → teacher results upserted.

    Mocks only the AI grading internals and the teacher-storage save (we
    verify the call happens; storage integration is covered elsewhere).
    Everything else — context fetch, dedup claim, per-question scoring
    loop, overall feedback path, standards mastery builder, Supabase
    update — runs for real.
    """
    fake_sb = _build_fake_supabase()

    # Stub out the AI calls. grade_per_question is imported at module load
    # in portal_grading, so patch the attribute directly.
    def fake_grade_per_question(**kwargs):
        return {
            'grade': {
                'score': kwargs.get('points', 10),
                'possible': kwargs.get('points', 10),
                'quality': 'good',
                'reasoning': 'stub',
            },
        }

    def fake_generate_feedback(**kwargs):
        return {
            'feedback': 'Nice work overall.',
            'rubric_breakdown': {
                'content_accuracy': 95,
                'completeness': 100,
                'writing_quality': 90,
                'effort_engagement': 100,
            },
        }

    teacher_results_saved = []

    def record_save_results(results, teacher_id):
        teacher_results_saved.append((teacher_id, list(results)))

    with patch('backend.supabase_client.get_supabase', return_value=fake_sb):
        with patch('backend.services.grading_service.load_teacher_config',
                   return_value={
                       'global_ai_notes': '',
                       'grade_level': '10',
                       'subject': 'English',
                       'grading_style': 'standard',
                       'rubric': None,
                       'ai_model': 'gpt-4o-mini',
                       'period': '3',
                   }):
            with patch('backend.services.portal_grading.grade_per_question',
                       side_effect=fake_grade_per_question):
                with patch('backend.services.portal_grading.generate_feedback',
                           side_effect=fake_generate_feedback):
                    # Confirm the pipeline's "save teacher results" call happens
                    # by stubbing the underlying save_results. load_saved_results
                    # returns [] so upsert starts fresh.
                    with patch('backend.grading.state.load_saved_results',
                               return_value=[]):
                        with patch('backend.grading.state.save_results',
                                   side_effect=record_save_results):
                            with patch('backend.grading.state._get_lock') as mock_lock:
                                mock_lock.return_value.__enter__ = lambda *_: None
                                mock_lock.return_value.__exit__ = lambda *_: None

                                from backend.tasks.grading_tasks import grade_portal_submission
                                result = grade_portal_submission.apply(
                                    args=['sub-e2e-1', 'teacher-e2e',
                                          'submissions'],
                                    kwargs={'district_id': 'd-1',
                                            'user_id': 'u-1'},
                                )

    # 1. Task completed successfully
    assert result.successful(), f"Task failed: {result.traceback}"

    # 2. Submissions row went through the expected state transitions:
    #    grading_in_progress (claim) → graded (final write)
    submissions_updates = [p for (tbl, p) in fake_sb.updates if tbl == 'submissions']
    statuses_seen = [u.get('status') for u in submissions_updates if 'status' in u]
    assert 'grading_in_progress' in statuses_seen, (
        f"Dedup claim missing from update sequence: {submissions_updates}"
    )
    assert 'graded' in statuses_seen, (
        f"Terminal 'graded' status never written: {submissions_updates}"
    )
    assert statuses_seen.index('grading_in_progress') < statuses_seen.index('graded'), (
        "Claim must happen BEFORE the terminal graded write"
    )

    # 3. Final 'graded' update carries the expected result envelope shape.
    graded_update = next(
        u for u in submissions_updates if u.get('status') == 'graded'
    )
    assert 'results' in graded_update
    results_blob = graded_update['results']
    assert results_blob['score'] == 15  # 5 (MC) + 10 (short-answer stub)
    assert results_blob['total_points'] == 15
    assert results_blob['percentage'] == 100
    assert results_blob['grading_source'] == 'multipass'
    assert 'questions' in results_blob  # per-question breakdown
    assert len(results_blob['questions']) == 2  # both sections' questions

    # 4. Teacher results storage received a record with submission_id for
    #    idempotent upsert (the Phase 4.1 PR2 contract).
    assert len(teacher_results_saved) == 1, (
        "Expected exactly one save_results call from the grading thread"
    )
    teacher_id, saved_records = teacher_results_saved[0]
    assert teacher_id == 'teacher-e2e'
    assert len(saved_records) == 1
    record = saved_records[0]
    assert record['submission_id'] == 'sub-e2e-1', (
        "submission_id must flow through build_result_record for idempotent "
        "upsert across Celery retries"
    )
    assert record['student_name'] == 'E2E Student'
    assert record['assignment'] == 'E2E Integration Test Assignment'
    assert record['score'] == 100  # percentage
    assert record['source'] == 'portal'


def test_full_chain_honors_dedup_on_second_invocation(eager_celery):
    """Idempotency contract for the full chain: calling .apply() twice with
    the same task_id produces exactly ONE teacher result record (not two).

    This is the in-code equivalent of "a Celery worker died and the broker
    redelivered the message with the same task_id". The dedup branch
    (current_task == task_id) fires on the second run and re-grades
    idempotently; _upsert_result_by_submission_id replaces the prior
    record rather than appending.
    """
    fake_sb = _build_fake_supabase()

    def fake_grade_per_question(**kwargs):
        return {'grade': {'score': kwargs.get('points', 10),
                          'possible': kwargs.get('points', 10),
                          'quality': 'good',
                          'reasoning': 'stub'}}

    def fake_generate_feedback(**kwargs):
        return {'feedback': 'ok', 'rubric_breakdown': {}}

    teacher_storage = []  # simulates on-disk results list

    def load_existing(teacher_id):
        return list(teacher_storage)

    def save_new(results, teacher_id):
        teacher_storage.clear()
        teacher_storage.extend(results)

    with patch('backend.supabase_client.get_supabase', return_value=fake_sb):
        with patch('backend.services.grading_service.load_teacher_config',
                   return_value={
                       'global_ai_notes': '', 'grade_level': '10',
                       'subject': 'English', 'grading_style': 'standard',
                       'rubric': None, 'ai_model': 'gpt-4o-mini', 'period': '3',
                   }):
            with patch('backend.services.portal_grading.grade_per_question',
                       side_effect=fake_grade_per_question):
                with patch('backend.services.portal_grading.generate_feedback',
                           side_effect=fake_generate_feedback):
                    with patch('backend.grading.state.load_saved_results',
                               side_effect=load_existing):
                        with patch('backend.grading.state.save_results',
                                   side_effect=save_new):
                            with patch('backend.grading.state._get_lock') as mock_lock:
                                mock_lock.return_value.__enter__ = lambda *_: None
                                mock_lock.return_value.__exit__ = lambda *_: None

                                from backend.tasks.grading_tasks import grade_portal_submission
                                # First invocation
                                grade_portal_submission.apply(
                                    args=['sub-e2e-1', 'teacher-e2e', 'submissions'],
                                    task_id='DUPLICATE-TASK-UUID',
                                )
                                # Simulated broker redelivery — same task_id
                                grade_portal_submission.apply(
                                    args=['sub-e2e-1', 'teacher-e2e', 'submissions'],
                                    task_id='DUPLICATE-TASK-UUID',
                                )

    # Teacher storage has exactly one record (upsert replaced, not appended)
    assert len(teacher_storage) == 1, (
        f"Idempotency violated: expected 1 record per submission_id, "
        f"got {len(teacher_storage)}: {teacher_storage}"
    )
    assert teacher_storage[0]['submission_id'] == 'sub-e2e-1'
