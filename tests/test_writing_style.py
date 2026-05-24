"""Characterization tests for the pure writing-style analysis helpers
(Wave 7 Slice 1 — assignment_grader.py decomposition).

These pin the EXACT output of analyze_writing_style / compare_writing_styles BEFORE
extracting them into backend/services/writing_style.py. Both are pure (regex + dict
math, no LLM / I/O / Flask), so per-function golden tests are the correct safety net.
Imported via `assignment_grader` so the test stays valid through the re-export shim.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from assignment_grader import analyze_writing_style, compare_writing_styles

TXT = ("The American Revolution was a significant turning point in history. "
       "Colonists fought for their independence because they believed taxation without "
       "representation was fundamentally unjust. Furthermore, the establishment of a new "
       "government required careful deliberation and compromise among the founders.")

ANALYZE_GOLDEN = {
    "avg_word_length": 6.69, "avg_sentence_length": 13.0, "word_count": 39,
    "sentence_count": 3, "complex_word_ratio": 0.41, "simple_word_ratio": 0.256,
    "academic_word_count": 2, "uses_contractions": False, "complexity_score": 10,
}

HIST = {"avg_complexity_score": 3.0, "avg_sentence_length": 8.0,
        "avg_academic_words": 0, "avg_word_length": 4.0}


def test_analyze_writing_style_golden():
    assert analyze_writing_style(TXT) == ANALYZE_GOLDEN


def test_analyze_writing_style_too_short_returns_none():
    assert analyze_writing_style("too short") is None
    assert analyze_writing_style("") is None
    assert analyze_writing_style(None) is None


def test_analyze_writing_style_too_few_words_returns_none():
    assert analyze_writing_style("a b c d") is None  # <5 words


def test_compare_writing_styles_deviation_golden():
    assert compare_writing_styles(ANALYZE_GOLDEN, HIST) == {
        "deviation": "significant", "ai_likelihood": "possible",
        "deviations": ["Complexity jumped from 3.0 to 10.0",
                       "Word length increased from 4.0 to 6.7"],
        "reason": "Complexity jumped from 3.0 to 10.0; Word length increased from 4.0 to 6.7",
    }


def test_compare_writing_styles_empty_returns_unknown():
    assert compare_writing_styles(None, HIST) == {
        "deviation": "unknown", "ai_likelihood": "unknown", "reason": "Insufficient data"}
    assert compare_writing_styles(ANALYZE_GOLDEN, None) == {
        "deviation": "unknown", "ai_likelihood": "unknown", "reason": "Insufficient data"}


def test_compare_writing_styles_consistent_returns_none():
    consistent = {"complexity_score": 3.1, "avg_sentence_length": 8.2,
                  "academic_word_count": 0, "avg_word_length": 4.1}
    assert compare_writing_styles(consistent, HIST) == {
        "deviation": "none", "ai_likelihood": "none", "deviations": [],
        "reason": "Writing style consistent with history"}
