"""Coverage backfill for portal_grading.py — state machine + lifecycle tests.

Pins the graded / grading_failed / grading_deferred status transitions
in run_portal_grading_thread so Phase 4 (task queue extraction) can
refactor with confidence.
"""
import pytest
from unittest.mock import patch, MagicMock, call


# ---------------------------------------------------------------------------
# TestHasWrittenQuestions — edge cases not covered by test_portal_grading.py
# ---------------------------------------------------------------------------

class TestHasWrittenQuestionsEdgeCases:
    """Cover WRITTEN_TYPES boundary: essay, written, fill_in_blank is NOT written."""

    def test_essay_returns_true(self):
        from backend.services.portal_grading import has_written_questions
        assessment = {"sections": [{"questions": [{"type": "essay"}]}]}
        assert has_written_questions(assessment) is True

    def test_written_type_returns_true(self):
        from backend.services.portal_grading import has_written_questions
        assessment = {"sections": [{"questions": [{"type": "written"}]}]}
        assert has_written_questions(assessment) is True

    def test_fill_in_blank_only_returns_false(self):
        from backend.services.portal_grading import has_written_questions
        assessment = {"sections": [{"questions": [{"type": "fill_in_blank"}]}]}
        assert has_written_questions(assessment) is False

    def test_default_type_is_mc_returns_false(self):
        """Questions with no explicit type default to multiple_choice."""
        from backend.services.portal_grading import has_written_questions
        assessment = {"sections": [{"questions": [{"question": "Q1"}]}]}
        assert has_written_questions(assessment) is False

    def test_multiple_sections_mixed(self):
        from backend.services.portal_grading import has_written_questions
        assessment = {
            "sections": [
                {"questions": [{"type": "multiple_choice"}]},
                {"questions": [{"type": "true_false"}, {"type": "short_answer"}]},
            ]
        }
        assert has_written_questions(assessment) is True


# ---------------------------------------------------------------------------
# TestScoreToLetter
# ---------------------------------------------------------------------------

class TestScoreToLetter:
    """Cover _score_to_letter boundaries."""

    def test_a_boundary(self):
        from backend.services.portal_grading import _score_to_letter
        assert _score_to_letter(90) == "A"
        assert _score_to_letter(100) == "A"

    def test_b_boundary(self):
        from backend.services.portal_grading import _score_to_letter
        assert _score_to_letter(80) == "B"
        assert _score_to_letter(89) == "B"

    def test_c_boundary(self):
        from backend.services.portal_grading import _score_to_letter
        assert _score_to_letter(70) == "C"
        assert _score_to_letter(79) == "C"

    def test_d_boundary(self):
        from backend.services.portal_grading import _score_to_letter
        assert _score_to_letter(60) == "D"
        assert _score_to_letter(69) == "D"

    def test_f_below_60(self):
        from backend.services.portal_grading import _score_to_letter
        assert _score_to_letter(59) == "F"
        assert _score_to_letter(0) == "F"


# ---------------------------------------------------------------------------
# Helpers for run_portal_grading_thread tests
# ---------------------------------------------------------------------------

def _make_mc_assessment(title="Test Quiz"):
    """MC-only assessment — no written questions, simpler flow."""
    return {
        "title": title,
        "sections": [{
            "name": "Section 1",
            "questions": [
                {"type": "multiple_choice", "question": "Capital of France?",
                 "answer": "B", "points": 5,
                 "options": ["London", "Paris", "Rome", "Berlin"]},
                {"type": "true_false", "question": "The sky is blue.",
                 "answer": "True", "points": 5},
            ],
        }],
    }


def _make_written_assessment(title="Essay Test"):
    """Assessment with a written question to exercise the AI grading path."""
    return {
        "title": title,
        "sections": [{
            "name": "Section 1",
            "questions": [
                {"type": "short_answer", "question": "Explain gravity.",
                 "answer": "Force of attraction", "points": 10},
            ],
        }],
    }


def _base_student_info():
    return {"student_name": "Jane Doe", "student_id": "stu_1", "email": "jane@test.com"}


def _base_teacher_config():
    return {
        "global_ai_notes": "",
        "grade_level": "8",
        "subject": "Science",
        "grading_style": "standard",
        "rubric": None,
        "ai_model": "gpt-4o-mini",
        "period": "P1",
    }


def _mock_supabase():
    """Build a MagicMock that mimics the Supabase fluent API chain."""
    sb = MagicMock()
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    return sb


# Patch targets — these are the module-level locations the function imports from
_PATCHES = {
    "supabase": "backend.services.portal_grading.get_supabase",
    "grade_per_question": "backend.services.portal_grading.grade_per_question",
    "generate_feedback": "assignment_grader.generate_feedback",
    "load_student_history": "backend.storage.load_student_history",
    "save_student_history": "backend.storage.save_student_history",
    "load_saved_results": "backend.app.load_saved_results",
    "save_results": "backend.app.save_results",
    "get_lock": "backend.app._get_lock",
    "set_thread_keys": "backend.api_keys.set_thread_keys",
    "resolve_keys": "backend.api_keys.resolve_keys_for_teacher",
    "build_correction": "backend.services.correction_patterns.build_correction_context",
    "build_standards": "backend.services.portal_grading._build_standards_mastery",
}


class _GradingThreadTestBase:
    """Shared setup for grading thread tests."""

    def _run(self, assessment, answers, student_info=None, teacher_config=None,
             submission_id="sub_1", supabase_table="student_submissions",
             student_accommodations=None, sb_mock=None):
        """Run run_portal_grading_thread with all dependencies mocked."""
        from backend.services.portal_grading import run_portal_grading_thread, _shutdown_event

        # Ensure shutdown event is clear
        _shutdown_event.clear()

        student_info = student_info or _base_student_info()
        teacher_config = teacher_config or _base_teacher_config()
        sb = sb_mock or _mock_supabase()

        # Patch at source modules. run_portal_grading_thread uses local imports
        # inside try/except blocks, so modules that can't load (backend.app,
        # backend.accommodations) just silently fail — no need to mock them.
        with (
            patch("backend.supabase_client.get_supabase", return_value=sb),
            patch("backend.services.portal_grading.grade_per_question", return_value={
                "grade": {"score": 8, "possible": 10, "quality": "good", "reasoning": "OK"}
            }),
            patch("assignment_grader.generate_feedback", return_value={
                "feedback": "Good job.", "rubric_breakdown": {
                    "content_accuracy": 80, "completeness": 85,
                    "writing_quality": 75, "effort_engagement": 80,
                }
            }),
            patch("backend.storage.load_student_history", return_value=None),
            patch("backend.storage.save_student_history"),
            patch("backend.services.portal_grading._build_standards_mastery", return_value={}),
        ):
            run_portal_grading_thread(
                submission_id=submission_id,
                assessment=assessment,
                answers=answers,
                student_info=student_info,
                teacher_config=teacher_config,
                teacher_id="teacher_1",
                supabase_table=supabase_table,
                student_accommodations=student_accommodations,
            )

        return sb


# ---------------------------------------------------------------------------
# TestGradingStateTransitions
# ---------------------------------------------------------------------------

class TestGradingStateTransitions(_GradingThreadTestBase):
    """Verify the status values written to Supabase on each outcome."""

    def test_successful_grading_writes_graded(self):
        """Happy path: MC-only assessment writes status='graded'."""
        sb = self._run(
            assessment=_make_mc_assessment(),
            answers={"0-0": "B", "0-1": "True"},
        )
        # Find the update call that writes status: "graded"
        update_calls = sb.table.return_value.update.call_args_list
        statuses = [c[0][0].get("status") for c in update_calls if "status" in c[0][0]]
        assert "graded" in statuses, f"Expected 'graded' in {statuses}"

    def test_successful_grading_uses_correct_table(self):
        """Verify the default table is student_submissions."""
        sb = self._run(
            assessment=_make_mc_assessment(),
            answers={"0-0": "B", "0-1": "True"},
            supabase_table="student_submissions",
        )
        sb.table.assert_any_call("student_submissions")

    def test_custom_supabase_table_for_join_code(self):
        """Join-code submissions use the 'submissions' table."""
        sb = self._run(
            assessment=_make_mc_assessment(),
            answers={"0-0": "B", "0-1": "True"},
            supabase_table="submissions",
        )
        sb.table.assert_any_call("submissions")

    def test_grading_failure_writes_grading_failed(self):
        """When the entire thread crashes, status must be 'grading_failed'."""
        from backend.services.portal_grading import run_portal_grading_thread, _shutdown_event
        _shutdown_event.clear()

        sb = _mock_supabase()

        with (
            patch("backend.supabase_client.get_supabase", return_value=sb),
            # Crash build_portal_ai_notes — it's called outside try/except
            # so it triggers the outer except handler that writes grading_failed
            patch("backend.services.portal_grading.build_portal_ai_notes",
                  side_effect=RuntimeError("LLM crash")),
        ):
            # This should NOT raise — the function catches internally
            run_portal_grading_thread(
                submission_id="sub_fail",
                assessment=_make_written_assessment(),
                answers={"0-0": "Student answer"},
                student_info=_base_student_info(),
                teacher_config=_base_teacher_config(),
                teacher_id="teacher_1",
            )

        # Verify grading_failed was written
        update_calls = sb.table.return_value.update.call_args_list
        statuses = [c[0][0].get("status") for c in update_calls if "status" in c[0][0]]
        assert "grading_failed" in statuses, f"Expected 'grading_failed' in {statuses}"

    def test_no_exception_raised_on_failure(self):
        """The function must never raise — it catches all exceptions internally."""
        from backend.services.portal_grading import run_portal_grading_thread, _shutdown_event
        _shutdown_event.clear()

        sb = _mock_supabase()

        with (
            patch("backend.supabase_client.get_supabase", return_value=sb),
            # Crash something outside try/except to trigger outer handler
            patch("backend.services.portal_grading.build_portal_ai_notes",
                  side_effect=RuntimeError("crash")),
        ):
            # Must not raise
            run_portal_grading_thread(
                submission_id="sub_x",
                assessment=_make_written_assessment(),
                answers={},
                student_info=_base_student_info(),
                teacher_config=_base_teacher_config(),
                teacher_id="teacher_1",
            )

    def test_shutdown_event_writes_grading_deferred(self):
        """When shutdown is in progress, submission gets status='grading_deferred'."""
        from backend.services.portal_grading import run_portal_grading_thread, _shutdown_event

        sb = _mock_supabase()
        _shutdown_event.set()  # Simulate Railway SIGTERM already received

        try:
            with patch("backend.supabase_client.get_supabase", return_value=sb):
                run_portal_grading_thread(
                    submission_id="sub_deferred",
                    assessment=_make_mc_assessment(),
                    answers={},
                    student_info=_base_student_info(),
                    teacher_config=_base_teacher_config(),
                    teacher_id="teacher_1",
                )

            update_calls = sb.table.return_value.update.call_args_list
            statuses = [c[0][0].get("status") for c in update_calls if "status" in c[0][0]]
            assert "grading_deferred" in statuses, f"Expected 'grading_deferred' in {statuses}"
        finally:
            _shutdown_event.clear()


# ---------------------------------------------------------------------------
# TestThreadLifecycle
# ---------------------------------------------------------------------------

class TestThreadLifecycle(_GradingThreadTestBase):
    """Verify thread registration, cleanup, and DB access patterns."""

    def test_thread_removed_from_active_set_after_success(self):
        """After grading completes, the thread must be removed from _active_threads."""
        from backend.services.portal_grading import _active_threads

        before = len(_active_threads)
        self._run(
            assessment=_make_mc_assessment(),
            answers={"0-0": "B", "0-1": "True"},
        )
        after = len(_active_threads)
        # The current thread should have been added then removed
        assert after <= before, "_active_threads should not grow after completion"

    def test_thread_removed_from_active_set_after_failure(self):
        """Thread cleanup happens even when grading fails."""
        from backend.services.portal_grading import run_portal_grading_thread, _shutdown_event, _active_threads
        _shutdown_event.clear()

        before = len(_active_threads)
        sb = _mock_supabase()

        with (
            patch("backend.supabase_client.get_supabase", return_value=sb),
            patch("backend.services.portal_grading.build_portal_ai_notes",
                  side_effect=RuntimeError("crash")),
        ):
            run_portal_grading_thread(
                submission_id="sub_fail",
                assessment=_make_written_assessment(),
                answers={},
                student_info=_base_student_info(),
                teacher_config=_base_teacher_config(),
                teacher_id="teacher_1",
            )

        after = len(_active_threads)
        assert after <= before, "_active_threads should not grow after failure"

    def test_uses_get_supabase_not_direct_client(self):
        """DB access MUST go through get_supabase() — never direct create_client."""
        sb = self._run(
            assessment=_make_mc_assessment(),
            answers={"0-0": "B", "0-1": "True"},
        )
        # If we got here, the function used our patched get_supabase
        # and called .table() on the mock — confirming the access pattern
        assert sb.table.called, "Expected supabase.table() to be called via get_supabase()"

    def test_accepts_all_documented_parameters(self):
        """Verify the function signature accepts all parameters without TypeError."""
        # This exercises the full parameter list including optional student_accommodations
        sb = self._run(
            assessment=_make_mc_assessment(),
            answers={"0-0": "A"},
            student_info=_base_student_info(),
            teacher_config=_base_teacher_config(),
            submission_id="sub_params",
            supabase_table="student_submissions",
            student_accommodations={"Jane Doe": {"iep": True, "accommodations": "extra time"}},
        )
        # No TypeError means all params accepted


# ---------------------------------------------------------------------------
# TestInstantGradingScoring
# ---------------------------------------------------------------------------

class TestInstantGradingScoring(_GradingThreadTestBase):
    """Verify deterministic scoring for MC/TF/matching in the thread."""

    def test_mc_correct_answer_scores_full_points(self):
        """MC answer 'B' matching expected 'B' should earn full points."""
        sb = self._run(
            assessment=_make_mc_assessment(),
            answers={"0-0": "B", "0-1": "True"},
        )
        # Check the results payload written to Supabase
        update_calls = sb.table.return_value.update.call_args_list
        for c in update_calls:
            payload = c[0][0]
            if "results" in payload:
                questions = payload["results"]["questions"]
                mc_q = [q for q in questions if q["type"] == "multiple_choice"][0]
                assert mc_q["points_earned"] == 5
                assert mc_q["is_correct"] is True
                break

    def test_mc_wrong_answer_scores_zero(self):
        sb = self._run(
            assessment=_make_mc_assessment(),
            answers={"0-0": "A", "0-1": "True"},  # A is wrong, B is correct
        )
        update_calls = sb.table.return_value.update.call_args_list
        for c in update_calls:
            payload = c[0][0]
            if "results" in payload:
                questions = payload["results"]["questions"]
                mc_q = [q for q in questions if q["type"] == "multiple_choice"][0]
                assert mc_q["points_earned"] == 0
                assert mc_q["is_correct"] is False
                break

    def test_true_false_scoring(self):
        sb = self._run(
            assessment=_make_mc_assessment(),
            answers={"0-0": "B", "0-1": "False"},  # TF answer is wrong
        )
        update_calls = sb.table.return_value.update.call_args_list
        for c in update_calls:
            payload = c[0][0]
            if "results" in payload:
                questions = payload["results"]["questions"]
                tf_q = [q for q in questions if q["type"] == "true_false"][0]
                assert tf_q["points_earned"] == 0
                assert tf_q["is_correct"] is False
                break


# ---------------------------------------------------------------------------
# TestBuildPortalAINotesExtended
# ---------------------------------------------------------------------------

class TestBuildPortalAINotesExtended:
    """Cover branches in build_portal_ai_notes not hit by existing tests."""

    def test_includes_accommodation_prompt(self):
        from backend.services.portal_grading import build_portal_ai_notes
        result = build_portal_ai_notes(accommodation_prompt="ACCOMMODATION: Extra time allowed")
        assert "ACCOMMODATION: Extra time allowed" in result

    def test_includes_student_history(self):
        from backend.services.portal_grading import build_portal_ai_notes
        result = build_portal_ai_notes(student_history="Previous scores: 85, 90, 78")
        assert "STUDENT HISTORY" in result
        assert "85, 90, 78" in result

    def test_includes_class_period(self):
        from backend.services.portal_grading import build_portal_ai_notes
        result = build_portal_ai_notes(class_period="P3-Honors")
        assert "CLASS PERIOD: P3-Honors" in result

    def test_includes_correction_context(self):
        from backend.services.portal_grading import build_portal_ai_notes
        result = build_portal_ai_notes(correction_context="Teacher previously corrected X to Y")
        assert "Teacher previously corrected X to Y" in result

    def test_defaults_only_include_grading_style(self):
        from backend.services.portal_grading import build_portal_ai_notes
        result = build_portal_ai_notes()
        # Default grading_style="standard" is always included
        assert "GRADING STYLE: standard" in result
        assert "STUDENT HISTORY" not in result

    def test_grading_style_included(self):
        from backend.services.portal_grading import build_portal_ai_notes
        result = build_portal_ai_notes(grading_style="lenient")
        assert "GRADING STYLE: lenient" in result
