"""Characterization tests for build_section_rubric (Wave 7 Slice 4 — grader decomposition).

Pins the rubric-string invariants BEFORE moving build_section_rubric into
backend/services/grading_prep.py. Pure (string building from marker_config — no
LLM / I/O / Flask). Combined with the AST byte-identical-move verification, these
invariants lock the dict-marker / str-marker / total / JSON-example logic.
Imported via `assignment_grader` (re-export shim).
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from assignment_grader import build_section_rubric

MC = [{"start": "Part A", "points": 20, "type": "vocab"},
      {"start": "Part B", "points": 30, "type": "written"}]


def test_empty_marker_config_returns_empty_string():
    assert build_section_rubric([]) == ""
    assert build_section_rubric(None) == ""


def test_dict_markers_section_lines_total_and_json_example():
    r = build_section_rubric(MC)  # default effort_points=15
    assert "- Part A: 20 points (vocab)" in r
    assert "- Part B: 30 points (written)" in r
    assert "- Effort & Engagement: 15 points" in r
    assert "TOTAL: 65 points" in r                      # 20 + 30 + 15
    # section_scores JSON example carries each section's `possible`
    assert '"Part A": {"earned": <pts>, "possible": 20}' in r
    assert '"Part B": {"earned": <pts>, "possible": 30}' in r
    assert '"Effort & Engagement": {"earned": <pts>, "possible": 15}' in r


def test_custom_effort_points_changes_total():
    r = build_section_rubric(MC, effort_points=10)
    assert "- Effort & Engagement: 10 points" in r
    assert "TOTAL: 60 points" in r                      # 20 + 30 + 10


def test_string_markers_default_10_points():
    r = build_section_rubric(["Quiz", "Essay"])
    assert "- Quiz: 10 points" in r
    assert "- Essay: 10 points" in r
    assert "TOTAL: 35 points" in r                      # 10 + 10 + 15
    assert '"Quiz": {"earned": <pts>, "possible": 10}' in r
