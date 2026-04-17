"""Phase 4.1 PR2 Subtask 3a — grade_portal_submission_sync pure function extraction.

The pure function must accept all dependencies as params (no Flask g) so the
Celery task can call it without a Flask context. The legacy wrapper
run_portal_grading_thread keeps working for the class-based path and any
Celery-enqueue fallback to threads.
"""
import inspect
from unittest.mock import patch, MagicMock


def test_grade_portal_submission_sync_exists():
    """The pure function must be importable directly."""
    from backend.services.portal_grading import grade_portal_submission_sync
    assert callable(grade_portal_submission_sync)


def test_grade_portal_submission_sync_accepts_explicit_context():
    """Must accept task_id, district_id, user_id as keyword-only; student_accommodations preserved."""
    from backend.services.portal_grading import grade_portal_submission_sync
    sig = inspect.signature(grade_portal_submission_sync)
    for name in ('task_id', 'district_id', 'user_id'):
        assert name in sig.parameters, f"Missing param: {name}"
        assert sig.parameters[name].kind == inspect.Parameter.KEYWORD_ONLY, (
            f"{name} must be keyword-only"
        )
    assert 'student_accommodations' in sig.parameters


def test_run_portal_grading_thread_keeps_original_signature():
    """Legacy wrapper must preserve signature — class-based path + thread fallback depend on it."""
    from backend.services.portal_grading import run_portal_grading_thread
    sig = inspect.signature(run_portal_grading_thread)
    assert 'student_accommodations' in sig.parameters
    # Default is 'student_submissions' for supabase_table (existing behavior)
    assert sig.parameters['supabase_table'].default == 'student_submissions'
    # Should NOT require task_id / district_id / user_id (those are pulled from flask.g in the wrapper)
    for name in ('task_id', 'district_id', 'user_id'):
        assert name not in sig.parameters, (
            f"Wrapper should not require {name} — it lives on the pure function"
        )


def test_wrapper_passes_accommodations_to_sync():
    """Wrapper must pass student_accommodations through to grade_portal_submission_sync."""
    with patch('backend.services.portal_grading.grade_portal_submission_sync') as mock_sync:
        from backend.services.portal_grading import run_portal_grading_thread
        run_portal_grading_thread(
            submission_id='test-id',
            assessment={'questions': []},
            answers={},
            student_info={'name': 'Test'},
            teacher_config={},
            teacher_id='test-teacher',
            supabase_table='submissions',
            student_accommodations={'iep': True, 'extended_time': 1.5},
        )
        mock_sync.assert_called_once()
        call_kwargs = mock_sync.call_args.kwargs
        assert call_kwargs.get('student_accommodations') == {'iep': True, 'extended_time': 1.5}
        # Wrapper passes task_id=None (legacy thread path skips dedup)
        assert call_kwargs.get('task_id') is None


def test_dedup_helpers_exist():
    """Row-level dedup helpers must be present for the Celery path."""
    from backend.services.portal_grading import (
        _fetch_submission_row, _claim_submission_for_grading, _is_stale_claim,
    )
    assert callable(_fetch_submission_row)
    assert callable(_claim_submission_for_grading)
    assert callable(_is_stale_claim)


def test_is_stale_claim_behavior():
    """_is_stale_claim returns True for old/unparseable/None timestamps, False for recent."""
    from backend.services.portal_grading import _is_stale_claim
    from datetime import datetime, timezone, timedelta
    assert _is_stale_claim(None) is True
    assert _is_stale_claim('') is True
    assert _is_stale_claim('not-a-date') is True  # unparseable → stale
    old_iso = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    assert _is_stale_claim(old_iso) is True
    fresh_iso = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    assert _is_stale_claim(fresh_iso) is False


def test_sync_has_no_flask_context_references():
    """AST/source check: grade_portal_submission_sync must not reference flask.g or _active_threads/_shutdown_event.

    Those belong in the wrapper only.
    """
    import inspect
    from backend.services.portal_grading import grade_portal_submission_sync
    src = inspect.getsource(grade_portal_submission_sync)
    assert 'from flask import g' not in src, "pure function must not import flask.g"
    assert '_active_threads' not in src, "_active_threads belongs in the wrapper"
    assert '_shutdown_event' not in src, "_shutdown_event belongs in the wrapper"
    # Note: 'g.user_id' / 'g.district_id' access should also be absent.
    # But 'g' alone might appear in strings/comments; check for specific access patterns.
    assert 'getattr(g,' not in src
    assert 'flask_g' not in src or 'from flask import' not in src
