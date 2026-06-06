"""GOLDEN CHARACTERIZATION NET for the file-based grading thread.

Pins CURRENT end-to-end behavior of the public entry point
``run_grading_thread`` (backend/grading/thread.py) so the upcoming
behavior-preserving split of ``_run_grading_thread_inner`` (1492 LOC) and
its nested closure ``grade_single_file`` (626 LOC) in
backend/grading/pipeline.py can be proven behavior-preserving.

WHAT IS REAL (exercised, never mocked) — these are the exact code paths the
refactor moves, so the net MUST run them for real:
  - the whole orchestrator ``_run_grading_thread_inner``
  - the nested closure ``grade_single_file`` (submitted to ThreadPoolExecutor)
  - ``find_matching_config`` / ``fuzzy_match_score`` / ``extract_content_fingerprints``
  - ``calculate_late_penalty``
  - ``parse_filename`` + ``read_assignment_file`` (real .txt fixtures on disk)
  - ``stage_files`` (canonicalize + dedup + resubmission detection)
  - ``load_roster`` (real CSV fixtures on disk)
  - the 4-way grade dispatch (ensemble / multipass / grade_assignment / parallel-detection)
  - the per-result assembly (new_result dict, pipeline.py L1543-1574)
  - late-penalty application, resubmission keep-higher, missing-config skip,
    API-error stop.

WHAT IS MOCKED (only these, per the faithfulness constraints):
  - the 4 AI grading fns on ``assignment_grader`` (the only network/LLM IO):
    grade_with_parallel_detection, grade_multipass, grade_assignment,
    grade_with_ensemble — each returns a deterministic grade_result dict.
  - the student-history DB fns (external IO):
    backend.student_history.detect_baseline_deviation + add_assignment_to_history.

ISOLATION: HOME is redirected to a tmp dir so ~/.graider_assignments,
~/.graider_data and ~/.graider_results.json resolve under tmp; the
backend.grading.state storage layer is forced to None so results route to
the tmp file (no Supabase). Each test uses a unique teacher_id and the
per-teacher state dict is reset, so no cross-test contamination.
"""
import csv
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Deterministic fake grade_result (richer than the prod minimum, so every
# field the result-assembly copies is observable on the pinned result entry).
# ---------------------------------------------------------------------------
def make_fake_grade_result(score=82, letter_grade="B"):
    """A grade_result dict carrying every field grade_single_file + the
    result-assembly read. Mirrors the real grade fns' return contract."""
    return {
        "score": score,
        "letter_grade": letter_grade,
        "feedback": "Solid work — clear reasoning throughout.",
        "breakdown": {
            "content_accuracy": 34,
            "completeness": 22,
            "writing_quality": 16,
            "effort_engagement": 10,
        },
        "student_responses": [
            {"question": "Q1", "answer": "Napoleon needed money.", "type": "numbered_question"},
        ],
        "unanswered_questions": [],
        "ai_detection": {"flag": "none", "confidence": 0, "reason": ""},
        "plagiarism_detection": {"flag": "none", "reason": ""},
        "skills_demonstrated": {"strengths": ["content knowledge"], "developing": ["writing clarity"]},
        "token_usage": {
            "total_cost": 0.0021,
            "total_input_tokens": 1200,
            "total_output_tokens": 350,
            "api_calls": 2,
        },
    }


# ---------------------------------------------------------------------------
# Fixture data — small, self-contained, flows through the REAL extraction /
# marker / matching pipeline. Mirrors tests/fixtures/grading shapes.
# ---------------------------------------------------------------------------
CORNELL_CONFIG = {
    "title": "Louisiana Purchase Cornell Notes",
    "rubricType": "cornell-notes",
    "useSectionPoints": True,
    "effortPoints": 15,
    "customMarkers": [
        {"start": "QUESTIONS", "points": 40, "type": "written"},
        {"start": "SUMMARY", "points": 20, "type": "written"},
        {"start": "VOCABULARY", "points": 25, "type": "vocab"},
    ],
    "excludeMarkers": [],
    "gradingNotes": (
        "Expected answers:\n"
        "Q1: Napoleon needed money for European wars.\n"
        "Q2: Doubled the size of the US.\n"
        "Summary should mention the $15 million price and doubled size."
    ),
    "importedDoc": {
        "text": (
            "Louisiana Purchase Cornell Notes\n\n"
            "QUESTIONS:\n1) Why did Napoleon sell the Louisiana Territory?\n"
            "2) How did the purchase affect US size?\n\n"
            "SUMMARY:\n[Write a summary of the Louisiana Purchase]\n\n"
            "VOCABULARY:\nLouisiana Purchase -\nTreaty -"
        )
    },
    "completionOnly": False,
    "modelAnswers": {},
    "customRubric": None,
}

CORNELL_SUBMISSION = (
    "Student Name: Maria Garcia\n"
    "Period: 3\n"
    "Assignment: Louisiana Purchase Cornell Notes\n\n"
    "QUESTIONS:\n"
    "1) Napoleon needed money for European wars and lost Haiti.\n"
    "2) It doubled the size of the United States.\n\n"
    "SUMMARY:\n"
    "The US bought the Louisiana Territory from France in 1803 for $15 million, "
    "doubling the size of the country.\n\n"
    "VOCABULARY:\n"
    "Louisiana Purchase - When the US bought land from France in 1803.\n"
    "Treaty - An official agreement between two countries.\n"
)

FITB_CONFIG = {
    "title": "Solving Equations Worksheet",
    "rubricType": "fill-in-blank",
    "useSectionPoints": True,
    "effortPoints": 15,
    "customMarkers": [
        {"start": "PROBLEMS", "points": 50, "type": "fill-in-blank"},
    ],
    "excludeMarkers": [],
    "gradingNotes": "Answer key:\nQ1: x = 5\nQ2: x = 9\n",
    "importedDoc": {
        "text": "Solving Equations Worksheet\n\nPROBLEMS:\n1) 3x + 7 = 22\n2) 2(x - 4) = 10\n"
    },
    "completionOnly": False,
    "modelAnswers": {},
    "customRubric": None,
}

FITB_SUBMISSION = (
    "Student Name: David Chen\n"
    "Period: 1\n"
    "Assignment: Solving Equations Worksheet\n\n"
    "PROBLEMS:\n"
    "1) 3x + 7 = 22\n3x = 15\nx = 5\n"
    "2) 2(x - 4) = 10\n2x - 8 = 10\nx = 9\n"
)


# ---------------------------------------------------------------------------
# Environment harness: redirect HOME to tmp, neuter the storage layer, place
# assignment configs under ~/.graider_assignments, build roster + submissions.
# ---------------------------------------------------------------------------
class GradingEnv:
    """Holds the tmp dirs + paths the thread entry point needs."""

    def __init__(self, tmp_path):
        self.home = tmp_path / "home"
        self.home.mkdir()
        self.assignments_dir = self.home / ".graider_assignments"
        self.assignments_dir.mkdir()
        self.inbox = tmp_path / "inbox"
        self.inbox.mkdir()
        self.output = tmp_path / "output"
        self.output.mkdir()
        self.roster_file = tmp_path / "roster.csv"

    def write_config(self, config):
        if config is None:
            return
        path = self.assignments_dir / f"{config['title']}.json"
        path.write_text(json.dumps(config))

    def write_submission(self, filename, content):
        (self.inbox / filename).write_text(content)

    def write_roster(self, rows):
        """rows: list of (first, last, student_id, email[, period])."""
        with open(self.roster_file, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["FirstName", "LastName", "StudentID", "Email", "Period"])
            for r in rows:
                period = r[4] if len(r) > 4 else ""
                w.writerow([r[0], r[1], r[2], r[3], period])


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Hermetic grading environment: HOME → tmp, storage layer → None."""
    genv = GradingEnv(tmp_path)
    # Redirect HOME so ~/.graider_assignments / ~/.graider_results.json resolve
    # under tmp. expanduser("~") reads $HOME on POSIX.
    monkeypatch.setenv("HOME", str(genv.home))
    # Route results persistence to the local file (under tmp HOME), not Supabase.
    import backend.grading.state as state_mod
    monkeypatch.setattr(state_mod, "storage_load", None)
    monkeypatch.setattr(state_mod, "storage_save", None)
    monkeypatch.setattr(state_mod, "RESULTS_FILE",
                        str(genv.home / ".graider_results.json"))
    return genv


def fresh_state(teacher_id):
    """Reset (and return) the per-teacher state dict for an isolated run.

    Drops any cached state from a prior test so each scenario starts with
    an empty results list. Returns the live state dict so the test can read
    ['results'] after the run.
    """
    import backend.grading.state as state_mod
    # Drop cached state + lock so _get_state rebuilds a clean default.
    state_mod._grading_states.pop(teacher_id, None)
    state_mod._grading_locks.pop(teacher_id, None)
    return state_mod._get_state(teacher_id)


def run_thread(env, teacher_id, *, config, submissions, roster,
               ensemble_models=None, trusted_students=None,
               selected_files=None, seed_results=None,
               fake_grade_results=None):
    """Drive the REAL run_grading_thread with the given fixtures.

    Mocks ONLY the 4 AI grade fns + the 2 student-history DB fns. Returns the
    per-teacher state dict (read ['results'] on it). ``fake_grade_results`` is
    an optional dict mapping fn-name -> grade_result so a scenario can pin a
    specific score per dispatch path.
    """
    from backend.grading.thread import run_grading_thread

    env.write_config(config)
    env.write_roster(roster)
    for fname, content in submissions:
        env.write_submission(fname, content)

    state = fresh_state(teacher_id)
    if seed_results is not None:
        state["results"] = list(seed_results)

    fgr = fake_grade_results or {}

    # Which-dispatch recorder: each fake records that it was called so the
    # test can assert the 4-way dispatch chose the expected function.
    called = {"parallel": 0, "multipass": 0, "assignment": 0, "ensemble": 0}

    def fake_parallel(*a, **k):
        called["parallel"] += 1
        return dict(fgr.get("parallel", make_fake_grade_result()))

    def fake_multipass(*a, **k):
        called["multipass"] += 1
        return dict(fgr.get("multipass", make_fake_grade_result()))

    def fake_assignment(*a, **k):
        called["assignment"] += 1
        return dict(fgr.get("assignment", make_fake_grade_result()))

    def fake_ensemble(*a, **k):
        called["ensemble"] += 1
        return dict(fgr.get("ensemble", make_fake_grade_result()))

    # NOTE on patch targets:
    #  - The 4 grade fns are LAZY-imported inside _run_grading_thread_inner via
    #    `from assignment_grader import (...)`, so patching them on
    #    `assignment_grader` (the source namespace they're pulled from at call
    #    time) is correct.
    #  - The student-history fns are imported at MODULE LOAD into
    #    backend.grading.pipeline's namespace (pipeline.py line 29), so the call
    #    sites resolve them from the pipeline module globals — they MUST be
    #    patched on backend.grading.pipeline, not backend.student_history.
    with patch("assignment_grader.grade_with_parallel_detection", side_effect=fake_parallel), \
         patch("assignment_grader.grade_multipass", side_effect=fake_multipass), \
         patch("assignment_grader.grade_assignment", side_effect=fake_assignment), \
         patch("assignment_grader.grade_with_ensemble", side_effect=fake_ensemble), \
         patch("backend.grading.pipeline.detect_baseline_deviation",
               return_value={"flag": "normal", "reasons": [], "details": {}}), \
         patch("backend.grading.pipeline.add_assignment_to_history", return_value=None):
        run_grading_thread(
            assignments_folder=str(env.inbox),
            output_folder=str(env.output),
            roster_file=str(env.roster_file),
            assignment_config=config,
            global_ai_notes="",
            grade_level="7",
            subject="Social Studies",
            selected_files=selected_files,
            ai_model="gpt-4o-mini",
            ensemble_models=ensemble_models,
            trusted_students=trusted_students,
            teacher_id=teacher_id,
        )
    return state, called


def find_result(state, filename):
    """Return the single result entry for ``filename`` (canonical match)."""
    for r in state["results"]:
        if r.get("filename") == filename:
            return r
    return None


# ===========================================================================
# Scenario 1 — default path → grade_with_parallel_detection
# ===========================================================================
def test_default_path_uses_parallel_detection(env):
    state, called = run_thread(
        env, "golden-default",
        config=CORNELL_CONFIG,
        submissions=[("Maria_Garcia_Louisiana Purchase Cornell Notes.txt", CORNELL_SUBMISSION)],
        roster=[("Maria", "Garcia", "STU001", "mg@school.com", "3")],
    )

    assert called["parallel"] == 1
    assert called["multipass"] == 0
    assert called["ensemble"] == 0
    assert called["assignment"] == 0

    r = find_result(state, "Maria_Garcia_Louisiana Purchase Cornell Notes.txt")
    assert r is not None, f"no result; results={state['results']}"
    # Result-entry shape + key values (the new_result dict the split must preserve)
    assert r["student_name"] == "Maria Garcia"
    assert r["student_id"] == "STU001"
    assert r["student_email"] == "mg@school.com"
    assert r["assignment"] == "Louisiana Purchase Cornell Notes"
    assert r["score"] == 82
    assert r["letter_grade"] == "B"
    assert r["feedback"] == "Solid work — clear reasoning throughout."
    assert r["breakdown"] == {
        "content_accuracy": 34, "completeness": 22,
        "writing_quality": 16, "effort_engagement": 10,
    }
    assert r["student_responses"] == [
        {"question": "Q1", "answer": "Napoleon needed money.", "type": "numbered_question"},
    ]
    assert r["unanswered_questions"] == []
    assert r["ai_detection"] == {"flag": "none", "confidence": 0, "reason": ""}
    assert r["plagiarism_detection"] == {"flag": "none", "reason": ""}
    assert r["baseline_deviation"] == {"flag": "normal", "reasons": [], "details": {}}
    assert r["skills_demonstrated"] == {
        "strengths": ["content knowledge"], "developing": ["writing clarity"],
    }
    assert r["marker_status"] == "verified"  # config matched → verified
    assert r["is_resubmission"] is False
    assert r["previous_score"] is None
    assert r["kept_higher"] is False
    assert r["token_usage"]["total_cost"] == 0.0021
    # No late penalty in the default path
    assert r["original_score"] is None
    assert r["late_penalty"] is None
    # Thread lifecycle reached completion
    assert state["complete"] is True
    assert state["is_running"] is False


# ===========================================================================
# Scenario 2 — trusted student → grade_multipass, detection skipped
# ===========================================================================
def test_trusted_student_uses_multipass_and_skips_detection(env):
    state, called = run_thread(
        env, "golden-trusted",
        config=CORNELL_CONFIG,
        submissions=[("Maria_Garcia_Louisiana Purchase Cornell Notes.txt", CORNELL_SUBMISSION)],
        roster=[("Maria", "Garcia", "STU001", "mg@school.com", "3")],
        trusted_students=["STU001"],
    )

    assert called["multipass"] == 1
    assert called["parallel"] == 0
    assert called["ensemble"] == 0

    r = find_result(state, "Maria_Garcia_Louisiana Purchase Cornell Notes.txt")
    assert r is not None
    assert r["score"] == 82
    # Trusted writer → detection overwritten with the trusted-skip sentinel
    assert r["ai_detection"] == {
        "flag": "none", "confidence": 0, "reason": "Trusted writer - detection skipped",
    }
    assert r["plagiarism_detection"] == {
        "flag": "none", "reason": "Trusted writer - detection skipped",
    }


# ===========================================================================
# Scenario 3 — FITB (rubric_type=fill-in-blank) → grade_assignment, detection N/A
# ===========================================================================
def test_fitb_uses_grade_assignment_and_marks_detection_na(env):
    state, called = run_thread(
        env, "golden-fitb",
        config=FITB_CONFIG,
        submissions=[("David_Chen_Solving Equations Worksheet.txt", FITB_SUBMISSION)],
        roster=[("David", "Chen", "STU002", "dc@school.com", "1")],
    )

    assert called["assignment"] == 1
    assert called["parallel"] == 0
    assert called["multipass"] == 0
    assert called["ensemble"] == 0

    r = find_result(state, "David_Chen_Solving Equations Worksheet.txt")
    assert r is not None
    assert r["student_name"] == "David Chen"
    assert r["assignment"] == "Solving Equations Worksheet"
    assert r["ai_detection"] == {"flag": "none", "confidence": 0, "reason": "N/A - Fill-in-the-blank"}
    assert r["plagiarism_detection"] == {"flag": "none", "reason": "N/A - Fill-in-the-blank"}


# ===========================================================================
# Scenario 3b — completion-only assignment → early return, NO AI dispatch
# (a distinct branch inside grade_single_file, pipeline.py L937-959, that the
# split MOVES; bypasses the 4-way dispatch entirely and yields a SUBMITTED shape)
# ===========================================================================
def test_completion_only_returns_submitted_without_grading(env):
    completion_config = {**CORNELL_CONFIG, "completionOnly": True}
    state, called = run_thread(
        env, "golden-completion",
        config=completion_config,
        submissions=[("Maria_Garcia_Louisiana Purchase Cornell Notes.txt", CORNELL_SUBMISSION)],
        roster=[("Maria", "Garcia", "STU001", "mg@school.com", "3")],
    )

    # Early return fires BEFORE the 4-way dispatch — no AI grade fn is called.
    assert called == {"parallel": 0, "multipass": 0, "assignment": 0, "ensemble": 0}

    r = find_result(state, "Maria_Garcia_Louisiana Purchase Cornell Notes.txt")
    assert r is not None, f"no result; results={state['results']}"
    assert r["score"] == 100
    assert r["letter_grade"] == "SUBMITTED"
    assert r["marker_status"] == "completion_only"
    assert r["breakdown"] == {}
    assert "Completion-only" in r["feedback"]


# ===========================================================================
# Scenario 4 — ensemble (>=2 models) → grade_with_ensemble
# ===========================================================================
def test_ensemble_models_use_grade_with_ensemble(env):
    state, called = run_thread(
        env, "golden-ensemble",
        config=CORNELL_CONFIG,
        submissions=[("Maria_Garcia_Louisiana Purchase Cornell Notes.txt", CORNELL_SUBMISSION)],
        roster=[("Maria", "Garcia", "STU001", "mg@school.com", "3")],
        ensemble_models=["gpt-4o-mini", "claude-haiku"],
    )

    assert called["ensemble"] == 1
    assert called["parallel"] == 0
    assert called["multipass"] == 0
    assert called["assignment"] == 0

    r = find_result(state, "Maria_Garcia_Louisiana Purchase Cornell Notes.txt")
    assert r is not None
    assert r["score"] == 82


# ===========================================================================
# Scenario 7 — multiple files (>=4) → ThreadPoolExecutor parallel path
# ===========================================================================
def test_multiple_files_parallel_executor(env):
    students = [
        ("Maria", "Garcia", "STU001", "mg@school.com"),
        ("David", "Chen", "STU002", "dc@school.com"),
        ("Aisha", "Khan", "STU003", "ak@school.com"),
        ("Liam", "Obrien", "STU004", "lo@school.com"),
        ("Noah", "Smith", "STU005", "ns@school.com"),
    ]
    subs = []
    for first, last, _sid, _email in students:
        fname = f"{first}_{last}_Louisiana Purchase Cornell Notes.txt"
        subs.append((fname, CORNELL_SUBMISSION))

    state, called = run_thread(
        env, "golden-parallel",
        config=CORNELL_CONFIG,
        submissions=subs,
        roster=[(f, l, s, e, "3") for (f, l, s, e) in students],
    )

    # All 5 files dispatched through the default (parallel-detection) path.
    assert called["parallel"] == 5
    assert len(state["results"]) == 5
    names = sorted(r["student_name"] for r in state["results"])
    assert names == ["Aisha Khan", "David Chen", "Liam Obrien",
                     "Maria Garcia", "Noah Smith"]
    assert state["complete"] is True


# ===========================================================================
# Scenario 5 — late penalty reduces score + sets original_score / late_penalty
# ===========================================================================
def test_late_penalty_applied(env):
    # Config with a due date in the past + points_per_day penalty. The staged
    # file's mtime (set below) is after the due date → late.
    import copy
    late_config = copy.deepcopy(CORNELL_CONFIG)
    late_config["dueDate"] = "2020-01-01T00:00:00"
    late_config["latePenalty"] = {
        "enabled": True,
        "type": "points_per_day",
        "amount": 10,
        "maxPenalty": 50,
        "gracePeriodHours": 0,
    }

    fname = "Maria_Garcia_Louisiana Purchase Cornell Notes.txt"
    state, called = run_thread(
        env, "golden-late",
        config=late_config,
        submissions=[(fname, CORNELL_SUBMISSION)],
        roster=[("Maria", "Garcia", "STU001", "mg@school.com", "3")],
        fake_grade_results={"parallel": make_fake_grade_result(score=90, letter_grade="A")},
    )

    r = find_result(state, fname)
    assert r is not None
    # Penalty caps at maxPenalty=50, so a years-late file drops score to
    # max(0, 90 - 50) = 40. original_score preserved.
    assert r["original_score"] == 90
    assert r["score"] == 40
    assert r["late_penalty"] is not None
    assert r["late_penalty"]["penalty_type"] == "points_per_day"
    assert r["late_penalty"]["penalty_applied"] == 50
    assert r["late_penalty"]["days_late"] > 0


# ===========================================================================
# Scenario 6 — resubmission kept-higher (lower resubmission keeps the original)
# ===========================================================================
def test_resubmission_lower_score_keeps_original(env):
    fname = "Maria_Garcia_Louisiana Purchase Cornell Notes.txt"
    teacher_id = "golden-resub"

    # Seed a prior, higher-scoring result for the same student+assignment so
    # the resubmission keep-higher branch (pipeline L1532-1538) fires. The
    # filename must be flagged as a resubmission by stage_files; we drive that
    # by running once (seeds staging manifest + state), then re-running with
    # changed content + a lower fake score.
    #
    # First pass: original submission scores 90 (real run seeds state).
    state, _ = run_thread(
        env, teacher_id,
        config=CORNELL_CONFIG,
        submissions=[(fname, CORNELL_SUBMISSION)],
        roster=[("Maria", "Garcia", "STU001", "mg@school.com", "3")],
        fake_grade_results={"parallel": make_fake_grade_result(score=90, letter_grade="A")},
    )
    first = find_result(state, fname)
    assert first is not None and first["score"] == 90

    # Second pass: new (longer) content so stage_files sees a size change →
    # resubmission. Lower fake score (60). Keep the SAME state (do not reset)
    # so the prior result is visible to the keep-higher logic.
    import backend.grading.state as state_mod

    def second_run():
        from backend.grading.thread import run_grading_thread
        # Bigger content → different file size → stage_files flags resubmission.
        new_content = CORNELL_SUBMISSION + ("\nExtra revised paragraph. " * 20)
        env.write_submission(fname, new_content)

        def fake_parallel(*a, **k):
            return make_fake_grade_result(score=60, letter_grade="D")

        with patch("assignment_grader.grade_with_parallel_detection", side_effect=fake_parallel), \
             patch("assignment_grader.grade_multipass", side_effect=fake_parallel), \
             patch("assignment_grader.grade_assignment", side_effect=fake_parallel), \
             patch("assignment_grader.grade_with_ensemble", side_effect=fake_parallel), \
             patch("backend.grading.pipeline.detect_baseline_deviation",
                   return_value={"flag": "normal", "reasons": [], "details": {}}), \
             patch("backend.grading.pipeline.add_assignment_to_history", return_value=None):
            run_grading_thread(
                assignments_folder=str(env.inbox),
                output_folder=str(env.output),
                roster_file=str(env.roster_file),
                assignment_config=CORNELL_CONFIG,
                global_ai_notes="",
                grade_level="7",
                subject="Social Studies",
                selected_files=None,
                ai_model="gpt-4o-mini",
                teacher_id=teacher_id,
            )

    second_run()
    state = state_mod._get_state(teacher_id)

    kept = find_result(state, fname)
    assert kept is not None
    # Lower resubmission (60) → original (90) is KEPT, flagged kept_higher.
    assert kept["score"] == 90
    assert kept["is_resubmission"] is True
    assert kept["resubmission_score"] == 60
    assert kept["kept_higher"] is True


# ===========================================================================
# Scenario 8a — missing-config skip (no config, no markers → SKIPPED, no result)
# ===========================================================================
def test_missing_config_file_is_skipped(env):
    # A submission whose assignment title matches NO saved config and has no
    # fallback markers → grade_single_file returns is_config_missing, the file
    # is skipped, and no result entry is produced.
    fname = "Maria_Garcia_Totally Unrelated Handout.txt"
    state, called = run_thread(
        env, "golden-missing",
        config=None,  # no fallback assignment_config
        submissions=[(fname, "Some passage text with no markers or config match.")],
        roster=[("Maria", "Garcia", "STU001", "mg@school.com", "3")],
    )

    assert called == {"parallel": 0, "multipass": 0, "assignment": 0, "ensemble": 0}
    assert find_result(state, fname) is None
    assert state["complete"] is True
    # The skip is logged.
    assert any("SKIPPED" in line or "No assignment config" in line
               for line in state["log"]), state["log"]


# ===========================================================================
# Scenario 8b — API error stop (letter_grade == ERROR halts the run)
# ===========================================================================
def test_api_error_stops_grading(env):
    fname = "Maria_Garcia_Louisiana Purchase Cornell Notes.txt"
    err_result = make_fake_grade_result()
    err_result["letter_grade"] = "ERROR"
    err_result["feedback"] = "OpenAI API connection refused"

    state, called = run_thread(
        env, "golden-apierror",
        config=CORNELL_CONFIG,
        submissions=[(fname, CORNELL_SUBMISSION)],
        roster=[("Maria", "Garcia", "STU001", "mg@school.com", "3")],
        fake_grade_results={"parallel": err_result},
    )

    assert called["parallel"] == 1
    # ERROR grade → no result entry, run halts, error recorded on state.
    assert find_result(state, fname) is None
    assert state["error"] is not None
    assert "Error" in state["error"]
    assert state["complete"] is True
    assert state["is_running"] is False


# ===========================================================================
# Scenario 9 — config_mismatch threads from the shell config block through to
# _assemble_post_grade. The other golden scenarios never set config_mismatch=True
# (the missing-config case returns BEFORE assembly), so this is the only coverage
# of the cross-seam config_mismatch / config_mismatch_reason thread that the
# PR-3b decomposition introduced (config produced inline; consumed in the helper).
# ===========================================================================
def test_config_mismatch_threads_through_to_assembly(env):
    # A submitted file whose title matches NO saved config, but the fallback
    # assignment_config supplies markers (so it is NOT skipped) → config_mismatch=True.
    # The fallback keeps Cornell's markers/importedDoc; the submission content is
    # deliberately unrelated (Rome) so neither filename NOR content fingerprinting
    # matches the (renamed) config → matched_config stays None.
    mismatch_config = {**CORNELL_CONFIG, "title": "Photosynthesis Quiz Unit 4"}
    rome_submission = (
        "QUESTIONS:\n1) Why did the Roman Republic fall?\n"
        "Power struggles and civil wars weakened it.\n\n"
        "SUMMARY:\nThe Republic gave way to the Empire under Augustus.\n\n"
        "VOCABULARY:\nSenate - the governing council of Rome.\n"
    )
    state, called = run_thread(
        env, "golden-cfg-mismatch",
        config=mismatch_config,
        submissions=[("Maria_Garcia_Ancient Rome Essay.txt", rome_submission)],
        roster=[("Maria", "Garcia", "STU001", "mg@school.com", "3")],
    )

    # A result IS produced (fallback markers prevent the skip).
    r = find_result(state, "Maria_Garcia_Ancient Rome Essay.txt")
    assert r is not None, f"no result; results={state['results']}"

    # Producer — the shell config block set config_mismatch_reason and logged it:
    assert any("CONFIG MISMATCH:" in line and "Ancient Rome Essay" in line
               for line in state["log"]), state["log"]
    # Consumer — _assemble_post_grade's log_messages appends the "wrong rubric"
    # warning ONLY when the config_mismatch param it received is True. Its presence
    # proves config_mismatch was threaded shell-block → helper param correctly.
    assert any("CONFIG MISMATCH - may have wrong rubric" in line
               for line in state["log"]), state["log"]
