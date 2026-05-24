"""Characterization tests for the pure per-question grading-prep helpers
(Wave 7 Slice 3 — assignment_grader.py decomposition).

Pins the EXACT output of _parse_expected_answers, _distribute_points, and
_is_math_subject (+ the MATH_SUBJECTS constant) BEFORE extracting them into
backend/services/grading_prep.py. All pure (regex / list-dict math — no LLM /
I/O / Flask). Imported via `assignment_grader` so they stay valid through the
re-export shim.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from assignment_grader import (
    _parse_expected_answers, _distribute_points, _is_math_subject)


def test_parse_expected_answers_golden():
    ci = ("Q1: Paris\n- Q2: 1492\n\n"
          "VOCABULARY EXPECTED DEFINITIONS:\n"
          "- democracy: rule by the people\n- republic: representative government\n")
    assert _parse_expected_answers(ci) == {
        0: "Paris", 1: "1492",
        "democracy": "rule by the people", "republic": "representative government"}


def test_parse_expected_answers_empty():
    assert _parse_expected_answers("") == {}
    assert _parse_expected_answers(None) == {}


def test_distribute_points_marker_match_and_default():
    resps = [{"question": "Part A: Vocabulary term"}, {"question": "some other response"}]
    mc = [{"start": "Part A", "points": 20, "type": "vocab"}]
    assert _distribute_points(resps, mc, 100) == [
        {"points": 20, "section_name": "Part A", "section_type": "vocab"},
        {"points": 50, "section_name": "", "section_type": "written"}]  # 100//2 default


def test_distribute_points_empty_and_no_marker():
    assert _distribute_points([], [{"start": "X"}], 100) == []
    assert _distribute_points([{"question": "x"}], None, 50) == [
        {"points": 50, "section_name": "", "section_type": "written"}]


def test_is_math_subject():
    assert _is_math_subject("Algebra") is True
    assert _is_math_subject(" math 7 ") is True       # strip + lower
    assert _is_math_subject("Social Studies") is False
    assert _is_math_subject("") is False


def test_math_subjects_constant_preserved():
    # the constant moves with _is_math_subject; pin a couple of members
    from assignment_grader import MATH_SUBJECTS
    assert "geometry" in MATH_SUBJECTS and "ap calculus" in MATH_SUBJECTS
    assert "social studies" not in MATH_SUBJECTS
