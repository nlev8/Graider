"""PROMPT-SNAPSHOT NET — pins the ``file_ai_notes`` string each grade fn receives.

The golden net (``test_grading_thread_golden``) mocks the 4 grade dispatch fns
and asserts on the RESULTS, but it ignores the PROMPT each grade fn is handed.
The 247-LOC ``file_ai_notes`` assembly inside ``grade_single_file``
(pipeline.py L964-1210) is the single largest seam in the upcoming PR-3b
decomposition; a dropped grading factor there (per CLAUDE.md "never drop a
factor") would be INVISIBLE to the golden net.

This net captures ``file_ai_notes`` (the 3rd positional arg of every dispatch
fn — ``fn(student_name, grade_data, file_ai_notes, ...)``) and asserts each
grading-factor signature is present, so the decomposition cannot silently drop
one. It must pass identically before and after the PR-3a byte-identical lift
(the prompt-assembly code is unchanged by the lift) and gates PR-3b.

Reuses the hermetic fixtures from the golden net.
"""
from unittest.mock import patch

import pytest

from tests.test_grading_thread_golden import (
    CORNELL_CONFIG,
    CORNELL_SUBMISSION,
    FITB_CONFIG,
    FITB_SUBMISSION,
    GradingEnv,
    fresh_state,
    make_fake_grade_result,
)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Hermetic grading environment (mirrors the golden net's ``env``)."""
    genv = GradingEnv(tmp_path)
    monkeypatch.setenv("HOME", str(genv.home))
    import backend.grading.state as state_mod
    monkeypatch.setattr(state_mod, "storage_load", None)
    monkeypatch.setattr(state_mod, "storage_save", None)
    monkeypatch.setattr(state_mod, "RESULTS_FILE",
                        str(genv.home / ".graider_results.json"))
    return genv


def capture_prompts(env, teacher_id, *, config, submissions, roster,
                    global_ai_notes="", ensemble_models=None,
                    trusted_students=None):
    """Drive the REAL grading thread; capture the ``file_ai_notes`` (positional
    arg index 2) each grade fn receives. Returns the list of captured prompts."""
    from backend.grading.thread import run_grading_thread

    env.write_config(config)
    env.write_roster(roster)
    for fname, content in submissions:
        env.write_submission(fname, content)
    fresh_state(teacher_id)

    captured = []

    def fake(*a, **k):
        # file_ai_notes is the 3rd positional arg in ALL four dispatch fns:
        # grade_with_parallel_detection / grade_multipass / grade_assignment /
        # grade_with_ensemble — see pipeline.py L1271-1307.
        captured.append(a[2])
        return dict(make_fake_grade_result())

    with patch("assignment_grader.grade_with_parallel_detection", side_effect=fake), \
         patch("assignment_grader.grade_multipass", side_effect=fake), \
         patch("assignment_grader.grade_assignment", side_effect=fake), \
         patch("assignment_grader.grade_with_ensemble", side_effect=fake), \
         patch("backend.grading.pipeline.detect_baseline_deviation",
               return_value={"flag": "normal", "reasons": [], "details": {}}), \
         patch("backend.grading.pipeline.add_assignment_to_history", return_value=None):
        run_grading_thread(
            assignments_folder=str(env.inbox),
            output_folder=str(env.output),
            roster_file=str(env.roster_file),
            assignment_config=config,
            global_ai_notes=global_ai_notes,
            grade_level="7",
            subject="Social Studies",
            selected_files=None,
            ai_model="gpt-4o-mini",
            ensemble_models=ensemble_models,
            trusted_students=trusted_students,
            teacher_id=teacher_id,
        )
    return captured


# ---------------------------------------------------------------------------
# Scenario A — Cornell default path carries global notes + assignment notes +
# rubric-type override (3 distinct grading factors in one prompt).
# ---------------------------------------------------------------------------
def test_cornell_prompt_carries_global_assignment_and_rubric_factors(env):
    prompts = capture_prompts(
        env, "snap-cornell",
        config=CORNELL_CONFIG,
        submissions=[("Maria_Garcia_Louisiana Purchase Cornell Notes.txt", CORNELL_SUBMISSION)],
        roster=[("Maria", "Garcia", "STU001", "mg@school.com", "3")],
        global_ai_notes="GLOBAL_NOTE_SENTINEL_42",
    )
    assert len(prompts) == 1, f"expected 1 dispatch, got {len(prompts)}"
    p = prompts[0]
    # Factor 1 — Global AI Instructions (file_ai_notes is seeded from it, L965)
    assert "GLOBAL_NOTE_SENTINEL_42" in p, "global AI notes factor dropped"
    # Factor 2 — Assignment-Specific Grading Notes (L968-969, from config gradingNotes)
    assert "ASSIGNMENT-SPECIFIC INSTRUCTIONS:" in p, "assignment notes header dropped"
    assert "Expected answers" in p, "assignment notes content dropped"
    # Factor 4 — Rubric-Type Override: cornell-notes (L1052-1064)
    assert "ASSIGNMENT RUBRIC TYPE: CORNELL NOTES" in p, "cornell rubric-type override dropped"


# ---------------------------------------------------------------------------
# Scenario B — FITB rubric-type override (a different branch of the same seam).
# ---------------------------------------------------------------------------
def test_fitb_prompt_carries_fitb_rubric_override(env):
    prompts = capture_prompts(
        env, "snap-fitb",
        config=FITB_CONFIG,
        submissions=[("David_Chen_Solving Equations Worksheet.txt", FITB_SUBMISSION)],
        roster=[("David", "Chen", "STU002", "dc@school.com", "1")],
    )
    assert len(prompts) == 1
    assert "ASSIGNMENT RUBRIC TYPE: FILL-IN-THE-BLANK" in prompts[0], \
        "FITB rubric-type override dropped"


# ---------------------------------------------------------------------------
# Scenario C — Model Answers injection (factor 9, a distinct branch L990-997).
# ---------------------------------------------------------------------------
def test_model_answers_factor_present(env):
    cfg = {**CORNELL_CONFIG,
           "modelAnswers": {"QUESTIONS": "Napoleon needed money; the purchase doubled US size."}}
    prompts = capture_prompts(
        env, "snap-modelans",
        config=cfg,
        submissions=[("Maria_Garcia_Louisiana Purchase Cornell Notes.txt", CORNELL_SUBMISSION)],
        roster=[("Maria", "Garcia", "STU001", "mg@school.com", "3")],
    )
    assert len(prompts) == 1
    p = prompts[0]
    assert "MODEL ANSWERS" in p, "model-answers factor dropped"
    assert "Napoleon needed money" in p, "model-answer content dropped"
