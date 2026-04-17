"""Phase 4.1 PR2 — teacher-results upsert-by-submission_id contract.

The Celery task may retry mid-grade. Without idempotency, each retry would
append a duplicate teacher result record. Fix is a pure helper that
filter-then-appends by submission_id before save.
"""
from unittest.mock import patch


def test_upsert_result_by_submission_id_replaces_existing():
    """When a record with same submission_id already exists, it's replaced, not appended."""
    from backend.services.portal_grading import _upsert_result_by_submission_id

    existing_results = [
        {'submission_id': 's-1', 'student_name': 'Ana', 'score': 70},
        {'submission_id': 's-2', 'student_name': 'Bob', 'score': 80},
    ]
    new_record = {'submission_id': 's-1', 'student_name': 'Ana', 'score': 85}

    result = _upsert_result_by_submission_id(existing_results, new_record)

    assert len(result) == 2
    s1 = [r for r in result if r.get('submission_id') == 's-1']
    assert len(s1) == 1
    assert s1[0]['score'] == 85
    s2 = [r for r in result if r.get('submission_id') == 's-2']
    assert s2[0]['score'] == 80


def test_upsert_result_appends_new_submission_id():
    from backend.services.portal_grading import _upsert_result_by_submission_id
    existing = [{'submission_id': 's-1', 'score': 70}]
    new_record = {'submission_id': 's-2', 'score': 80}
    result = _upsert_result_by_submission_id(existing, new_record)
    assert len(result) == 2
    assert sorted([r['submission_id'] for r in result]) == ['s-1', 's-2']


def test_upsert_result_without_submission_id_appends_unconditionally():
    """Legacy records (no submission_id) append without dedup — safe, just not de-duped."""
    from backend.services.portal_grading import _upsert_result_by_submission_id
    existing = [{'student_name': 'Legacy', 'score': 60}]
    new_record = {'student_name': 'New (no submission_id)', 'score': 85}
    result = _upsert_result_by_submission_id(existing, new_record)
    assert len(result) == 2


def test_upsert_is_pure_does_not_mutate_input():
    """Helper must return a new list, not mutate existing_results in place."""
    from backend.services.portal_grading import _upsert_result_by_submission_id
    original = [{'submission_id': 's-1', 'score': 70}]
    original_snapshot = list(original)
    _ = _upsert_result_by_submission_id(original, {'submission_id': 's-1', 'score': 99})
    assert original == original_snapshot  # input untouched


def test_build_result_record_includes_submission_id():
    """build_result_record must now accept keyword-only submission_id and include it in output."""
    from backend.services.portal_grading import build_result_record
    record = build_result_record(
        student_name='Test Student',
        student_id='sid-1',
        assignment_title='Test Quiz',
        score=85,
        total_possible=100,
        period='P1',
        feedback='Good work',
        breakdown={},
        per_question_scores=[],
        submission_id='test-submission-id',
    )
    assert record.get('submission_id') == 'test-submission-id'


def test_build_result_record_omits_submission_id_when_none():
    """When submission_id=None (default), it must NOT appear in the record.

    Rationale: legacy code paths (batch grading) don't pass submission_id.
    Including a None key would pollute the data shape. Absence == not-deduped.
    """
    from backend.services.portal_grading import build_result_record
    record = build_result_record(
        student_name='Test',
        student_id='x',
        assignment_title='Q',
        score=100,
        total_possible=100,
        period='P1',
        feedback='',
        breakdown={},
        per_question_scores=[],
    )
    assert 'submission_id' not in record


def test_build_result_record_positional_signature_backward_compatible():
    """Existing callers that pass 9 positional args must still work unchanged."""
    from backend.services.portal_grading import build_result_record
    record = build_result_record(
        'Name', 'id', 'Title', 90, 100, 'P1', 'fb', {}, []
    )
    assert record['student_name'] == 'Name'
    assert record['score'] == 90
    assert 'submission_id' not in record
