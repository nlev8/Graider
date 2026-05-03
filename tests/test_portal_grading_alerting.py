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

    Patch at the canonical import path (backend.grading.state) used by
    _safe_save_results after PR4 migration off the backend.app shim."""
    from backend.services import portal_grading

    with patch("backend.grading.state.save_results", side_effect=RuntimeError("save boom")), \
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


def test_history_context_block_works_when_strategy_1_succeeds_without_student_id():
    """Regression for Codex MAJOR finding on the portal-grading observability
    PR (chore/portal-grading-observability):

    When Strategy 1 (embedded student_accommodations) builds the
    accommodation_prompt successfully and student_info has no student_id,
    the downstream load_student_history call must still see a defined
    `student_id`. Pre-fix it raised UnboundLocalError because student_id
    was only initialized inside the Strategy 2 branch — when Strategy 1
    succeeded, the variable was never bound, and the subsequent
    `load_student_history(teacher_id, student_id)` call (now wrapped in
    a logging except) would NameError.

    The fix: initialize `student_id = student_info.get("student_id", "")`
    at the top of the body, before either strategy runs.
    """
    import sys
    from backend.services import portal_grading

    # Mock accommodations module: Strategy 1 success path.
    accommodations_mod = MagicMock()
    accommodations_mod.build_prompt_from_student_accommodations.return_value = "accom prompt"

    # Mock storage: load_student_history fails. This is the line that
    # would have raised UnboundLocalError pre-fix.
    storage_mod = MagicMock()
    storage_mod.load_student_history.side_effect = RuntimeError("history boom")

    correction_mod = MagicMock()
    correction_mod.build_correction_context.return_value = ""

    saved_modules = {}
    for name in ("backend.accommodations", "backend.storage", "backend.services.correction_patterns"):
        saved_modules[name] = sys.modules.get(name)
    sys.modules["backend.accommodations"] = accommodations_mod
    sys.modules["backend.storage"] = storage_mod
    sys.modules["backend.services.correction_patterns"] = correction_mod

    try:
        with patch("backend.supabase_client.get_supabase", return_value=None), \
             patch.object(portal_grading.logger, "debug") as mock_debug, \
             patch.object(portal_grading.logger, "info"):
            # No submission_id, no flask context — minimal call to drive the
            # accommodations + history-context block. Anything downstream
            # that fails is caught by the function's outer try/except.
            portal_grading.run_portal_grading_thread(
                submission_id=None,
                assessment={"questions": []},
                answers={},
                student_info={"student_name": "Alice"},  # NO student_id
                teacher_config={"global_ai_notes": "", "grade_level": "",
                                "subject": "", "grading_style": "standard"},
                teacher_id="t1",
                student_accommodations={"Alice": {"text": "x"}},
            )

            # Pre-fix the test would raise UnboundLocalError before reaching
            # the assertion. Post-fix, the load_student_history failure is
            # caught and logged at debug level with student_id="" in the msg.
            debug_msgs = [c.args[0] for c in mock_debug.call_args_list if c.args]
            history_logs = [m for m in debug_msgs if "load_student_history failed" in m]
            assert history_logs, (
                f"Expected load_student_history debug log to fire (proves "
                f"student_id was bound). Got debug calls: {debug_msgs!r}"
            )
    finally:
        # Restore original sys.modules entries.
        for name, mod in saved_modules.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod
