"""Sentry/BetterStack alerting contract tests for portal_grading.

Each NEEDS_ALERT catch identified in docs/exception-audit-2026-04.md
MUST call sentry_sdk.capture_exception so BetterStack sees the failure.
These tests pin the contract — future refactors can't silently strip
the alerting call.

Phase 2 Hotfix 1.
"""
from unittest.mock import patch, MagicMock


def test_import_failure_captures_to_sentry_for_both_symbols():
    """If assignment_grader is unavailable at module load, both the
    grade_per_question and generate_feedback imports must page Sentry.
    Log-only is insufficient because grade_per_question's downstream
    TypeError is swallowed inside grade_written_questions (log + fallback),
    which would hide a config-level "assignment_grader missing" failure."""
    from backend.services import portal_grading

    with patch("backend.services.portal_grading.sentry_sdk") as mock_sentry, \
         patch("backend.services.portal_grading.import_module",
               side_effect=ImportError("no assignment_grader")):
        # Exercise the helper twice, once per symbol
        result1 = portal_grading._import_from_assignment_grader("grade_per_question")
        result2 = portal_grading._import_from_assignment_grader("generate_feedback")
        assert result1 is None
        assert result2 is None
        assert mock_sentry.capture_exception.call_count == 2


def test_feedback_generation_failure_captures_to_sentry():
    """portal_grading.py line 474 region: generate_feedback() throws ->
    exception must be captured, NOT silently swallowed."""
    from backend.services import portal_grading

    with patch("backend.services.portal_grading.sentry_sdk") as mock_sentry, \
         patch("backend.services.portal_grading.generate_feedback",
               side_effect=RuntimeError("feedback boom")):
        result = portal_grading._safe_generate_feedback(
            question="Q", student_answer="A", expected="E",
        )
        assert result is not None  # safe default returned
        mock_sentry.capture_exception.assert_called_once()


def test_save_result_failure_captures_to_sentry():
    """portal_grading.py line 499 region: save_results() throws ->
    must capture_exception, not silently swallow.

    Inject a mock backend.app into sys.modules because the real module
    has app-wide import side effects (route registration) that fail
    in a bare pytest process."""
    import sys
    from backend.services import portal_grading

    mock_app = MagicMock()
    mock_app.save_results.side_effect = RuntimeError("save boom")
    with patch.dict(sys.modules, {"backend.app": mock_app}), \
         patch("backend.services.portal_grading.sentry_sdk") as mock_sentry:
        portal_grading._safe_save_results([{"x": 1}], "teacher-123")
        mock_sentry.capture_exception.assert_called_once()


def test_supabase_submission_update_failure_captures_to_sentry():
    """portal_grading.py line 523 region: sb.table(...).update(...)
    .execute() throws -> must capture_exception."""
    from backend.services import portal_grading
    mock_sb = MagicMock()
    (mock_sb.table.return_value
        .update.return_value
        .eq.return_value
        .execute.side_effect) = RuntimeError("supabase boom")
    with patch("backend.services.portal_grading.sentry_sdk") as mock_sentry:
        portal_grading._safe_update_submission(
            mock_sb, "sub-id", {"status": "graded"},
        )
        mock_sentry.capture_exception.assert_called_once()


def test_supabase_unavailable_with_submission_id_pages():
    """If submission_id is set but Supabase client is None, that's a real
    config/connectivity failure — must page, not silently skip."""
    from backend.services import portal_grading
    with patch("backend.services.portal_grading.sentry_sdk") as mock_sentry:
        portal_grading._safe_update_submission(
            None, "sub-id", {"status": "graded"},
        )
        mock_sentry.capture_message.assert_called_once()


def test_supabase_skip_without_submission_id_is_silent():
    """The anonymous join-code path has no submission row; skip without
    paging when submission_id is falsy even if sb is None."""
    from backend.services import portal_grading
    with patch("backend.services.portal_grading.sentry_sdk") as mock_sentry:
        portal_grading._safe_update_submission(None, "", {"status": "graded"})
        mock_sentry.capture_message.assert_not_called()
        mock_sentry.capture_exception.assert_not_called()


def test_grading_thread_spawn_failure_captures_to_sentry():
    """student_account_routes.py line 872 region: threading.Thread(...)
    .start() raises -> must capture_exception, not just log.warning."""
    from backend.routes import student_account_routes as sar
    with patch("backend.routes.student_account_routes.sentry_sdk") as mock_sentry, \
         patch("backend.routes.student_account_routes.threading.Thread",
               side_effect=RuntimeError("spawn boom")):
        result = sar._spawn_grading_thread_safe(
            target=lambda: None, args=(), kwargs={},
        )
        assert result is None
        mock_sentry.capture_exception.assert_called_once()


def test_grading_thread_top_level_swallowed_exception_still_captures():
    """portal_grading.py line 546 region: the outer except swallows the
    exception so finally{} can still clean up + mark grading_failed.
    Because it's swallowed, @critical_path never fires. The fix: the
    except body MUST call sentry_sdk.capture_exception(e) before the
    cleanup sub-block."""
    from backend.services import portal_grading
    # Force the grading body to blow up early by making the first in-try
    # operation (logger.info) raise. logger.error on the except-body side
    # is unaffected since we only patch .info.
    with patch("backend.services.portal_grading.sentry_sdk") as mock_sentry, \
         patch.object(portal_grading.logger, "info",
                      side_effect=RuntimeError("log boom")):
        portal_grading.run_portal_grading_thread(
            submission_id="s1",
            assessment={"questions": []},
            answers={},
            student_info={"student_name": "x", "student_id": "sid"},
            teacher_config={},
            teacher_id="t1",
        )
        # Must have captured the swallowed exception.
        assert mock_sentry.capture_exception.call_count >= 1
