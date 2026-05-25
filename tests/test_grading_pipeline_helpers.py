"""Unit tests for the shared deterministic scoring helpers (Wave 8 slice 1).

`_letter_grade` and `_completeness_cap_table` were extracted from the duplicated inline
ladders/tables in grade_assignment / grade_multipass / grade_with_ensemble. These pin the
exact thresholds + cap tables so the dedup is provably behavior-preserving (the integration
behavior is also pinned by tests/test_grader_golden.py + test_grading_factors.py).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.services.grading_pipeline import (
    _COMPLETENESS_CAPS,
    _analyze_submission_writing_style,
    _apply_single_pass_post_processing,
    _completeness_cap_table,
    _detect_blank_submission,
    _detect_fitb_assignment,
    _letter_grade,
    _load_ell_language,
    _pre_extract_responses,
)


def test_letter_grade_boundaries():
    # exact thresholds: >=90 A, >=80 B, >=70 C, >=60 D, else F
    assert _letter_grade(100) == "A"
    assert _letter_grade(90) == "A"
    assert _letter_grade(89) == "B"
    assert _letter_grade(80) == "B"
    assert _letter_grade(79) == "C"
    assert _letter_grade(70) == "C"
    assert _letter_grade(69) == "D"
    assert _letter_grade(60) == "D"
    assert _letter_grade(59) == "F"
    assert _letter_grade(0) == "F"


def test_completeness_cap_tables_exact():
    assert _completeness_cap_table("strict") == {0: 100, 1: 85, 2: 75, 3: 65, 4: 55, 5: 45, 6: 35, 7: 25, 8: 15}
    assert _completeness_cap_table("lenient") == {0: 100, 1: 95, 2: 89, 3: 79, 4: 69, 5: 59, 6: 49, 7: 39, 8: 29}
    assert _completeness_cap_table("standard") == {0: 100, 1: 89, 2: 79, 3: 69, 4: 59, 5: 49, 6: 39, 7: 29, 8: 19}


def test_completeness_cap_unknown_style_falls_back_to_standard():
    # matches the prior `else:` branch — any non-strict/lenient style uses the standard table
    assert _completeness_cap_table("") == _COMPLETENESS_CAPS["standard"]
    assert _completeness_cap_table("weird") == _COMPLETENESS_CAPS["standard"]
    assert _completeness_cap_table(None) == _COMPLETENESS_CAPS["standard"]


# ── _apply_single_pass_post_processing (Wave 8 slice 3) ───────────────────────
# The grade_assignment golden uses a fully-answered, no-rubric-weights fixture, so its
# post-processing block is a no-op there. These directly exercise the caps + weights paths.

def test_post_processing_completeness_cap_lowers_score():
    result = {"score": 95, "letter_grade": "A", "breakdown": {}, "unanswered_questions": []}
    extraction = {"blank_questions": ["Q1", "Q2"], "missing_sections": []}
    _apply_single_pass_post_processing(result, None, "standard", extraction)
    # 2 blanks → standard cap table {2: 79}; 95 > 79 → capped to 79 (C)
    assert result["score"] == 79
    assert result["letter_grade"] == "C"
    assert set(result["unanswered_questions"]) == {"Q1", "Q2"}


def test_post_processing_rubric_weights_recompute_score():
    result = {"score": 80, "letter_grade": "B",
              "breakdown": {"content_accuracy": 40, "completeness": 25,
                            "writing_quality": 20, "effort_engagement": 15}}
    _apply_single_pass_post_processing(result, [40, 25, 20, 15], "standard", None)
    # all categories at full → weighted score 100 (A)
    assert result["score"] == 100
    assert result["letter_grade"] == "A"


def test_post_processing_noop_when_no_weights_and_no_blanks():
    result = {"score": 85, "letter_grade": "B", "breakdown": {}, "unanswered_questions": ["x"]}
    _apply_single_pass_post_processing(result, None, "standard",
                                       {"blank_questions": [], "missing_sections": []})
    assert result["score"] == 85
    assert result["letter_grade"] == "B"
    assert result["unanswered_questions"] == ["x"]


# ── _detect_blank_submission (Wave 8 slice: extracted from grade_assignment) ──────────────────
# Returns an INCOMPLETE result dict for blank submissions, else None. Pure heuristics, no LLM.

def test_detect_blank_submission_all_underscore_lines_is_blank():
    # Many question lines with only underscores after them → blank.
    content = "\n".join([
        "1. What caused the war?", "______________________",
        "2. Name a key figure:", "______________________",
        "3. Summarize the outcome:", "______________________",
        "4. Why did it matter?", "______________________",
    ])
    out = _detect_blank_submission(content)
    assert out is not None
    assert out["score"] == 0
    assert out["letter_grade"] == "INCOMPLETE"
    assert out["student_responses"] == []
    assert "blank assignment" in out["feedback"].lower()


def test_detect_blank_submission_with_written_answers_returns_none():
    # Real paragraph-length responses → not blank.
    content = (
        "1. What caused the war?\n"
        "The war was caused by rising tensions over territory and trade, which built up "
        "over many years until conflict finally broke out between the two sides.\n"
        "2. Name a key figure:\nGeneral Washington led the troops effectively.\n"
    )
    assert _detect_blank_submission(content) is None


def test_detect_blank_submission_filled_blanks_returns_none():
    # Two+ filled-in blanks → not blank.
    content = "The capital is ___Paris___ and the year was ___1789___ in this lesson."
    assert _detect_blank_submission(content) is None


# ── _analyze_submission_writing_style (Wave 8 slice: extracted from grade_assignment) ─────────
# Returns (writing_style_context, current_writing_style, style_comparison). Context + comparison
# stay empty/None without a historical profile; non-text submissions short-circuit entirely.

def test_analyze_writing_style_non_text_returns_empty_tuple():
    assert _analyze_submission_writing_style("irrelevant", {"type": "image"}, None) == ('', None, None)


def test_analyze_writing_style_no_history_yields_no_context_or_comparison():
    content = ("This is a reasonably long student paragraph with several sentences. "
               "It explains the causes and effects of the event in the student's own words.")
    ctx, _style, comparison = _analyze_submission_writing_style(content, {"type": "text"}, None)
    assert ctx == ''          # no deviation prompt fragment without a historical baseline
    assert comparison is None  # no comparison without >= 2 prior samples


# ── _detect_fitb_assignment (Wave 8 slice: extracted from grade_assignment) ───────────────────

def test_detect_fitb_by_content_keyword():
    assert _detect_fitb_assignment("This is a fill-in-the-blank worksheet.", "") is True


def test_detect_fitb_by_rubric_override():
    assert _detect_fitb_assignment("Plain content", "RUBRIC: FILL-IN-THE-BLANK") is True


def test_detect_fitb_by_timestamps_and_filled_underscores():
    # video-worksheet pattern: "N. (M:SS)" timestamps + >=2 filled underscore blanks
    content = "1. (0:15) The capital is ___Paris___\n2. (1:30) The year was ___1789___"
    assert _detect_fitb_assignment(content, "") is True


def test_detect_fitb_false_for_normal_assignment():
    assert _detect_fitb_assignment("Explain the causes of the war in a paragraph.", "") is False


# ── _pre_extract_responses (Wave 8 slice: extracted from grade_assignment; 3-AI-agreed 4-tuple) ─
# Returns (is_fitb, extraction_result, extracted_responses_text, early_result). early_result is
# None unless no responses were extracted (then it's the 0-score INCOMPLETE dict to return).

def test_pre_extract_fitb_packages_full_content():
    is_fitb, er, text, early = _pre_extract_responses(
        True, {"type": "text"}, "The capital is ___Paris___ and the year ___1789___",
        None, None, None, None, "structured")
    assert is_fitb is True and early is None
    assert er["answered_questions"] == 1 and er["extracted_responses"][0]["type"] == "fitb_full"
    assert "FILL-IN-THE-BLANK SUBMISSION" in text and "Paris" in text


def test_pre_extract_markers_override_fitb_flag():
    # custom markers present → FITB is overridden to False (markers take priority). type=image
    # short-circuits the extraction body so only the is_fitb-resolution runs.
    is_fitb, er, text, early = _pre_extract_responses(
        True, {"type": "image"}, "anything", [{"start": "X"}], None, None, None, "structured")
    assert is_fitb is False
    assert (er, text, early) == (None, '', None)


def test_pre_extract_non_text_returns_empty_continue_values():
    assert _pre_extract_responses(
        False, {"type": "image"}, "", None, None, None, None, "structured") == (False, None, '', None)


# ── _load_ell_language (Wave 8 slice: extracted from grade_assignment) ─────────────────────────

def test_load_ell_language_none_for_unknown_or_missing_student():
    assert _load_ell_language(None) is None
    assert _load_ell_language("UNKNOWN") is None


def test_load_ell_language_reads_from_file(tmp_path, monkeypatch):
    import json as _json
    import os as _os
    data_dir = tmp_path / ".graider_data"
    data_dir.mkdir()
    (data_dir / "ell_students.json").write_text(_json.dumps({"stu-1": {"language": "Spanish"}}))
    monkeypatch.setattr(_os.path, "expanduser",
                        lambda p: p.replace("~", str(tmp_path)) if p.startswith("~") else p)
    assert _load_ell_language("stu-1") == "Spanish"
    # 'none' sentinel and unknown students yield None
    assert _load_ell_language("stu-missing") is None
