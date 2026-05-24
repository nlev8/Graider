"""Characterization tests for the Graider marker/table parsers
(Wave 7 — assignment_grader.py decomposition, complex file-reader parsers).

Pins the EXACT extraction output of extract_from_graider_text (+ extract_from_tables)
on a REAL Graider-formatted submission BEFORE moving them into
backend/services/submission_parsing.py. These are print-heavy → the prints become
_logger calls on extraction (the validated print→logger pattern); RETURN VALUES are
unchanged (what these tests pin). Imported via `assignment_grader` (re-export shim).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from assignment_grader import extract_from_graider_text

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "grading",
                       "submission_social_studies.txt")


def _content():
    with open(FIXTURE) as f:
        return f.read()


def test_graider_text_empty_or_no_markers_returns_none():
    assert extract_from_graider_text("") is None
    assert extract_from_graider_text("just plain text, no GRAIDER markers") is None


def test_graider_text_extracts_all_responses_from_real_fixture():
    out = extract_from_graider_text(_content())
    assert out["total_questions"] == 10
    assert out["answered_questions"] == 10
    assert len(out["extracted_responses"]) == 10
    assert out["extraction_summary"] == "Graider text fallback: Found 10 responses out of 10 sections."
    assert set(out.keys()) == {
        "extracted_responses", "blank_questions", "total_questions",
        "answered_questions", "extraction_summary", "excluded_sections", "missing_sections"}


def test_graider_text_first_response_is_vocab_term():
    out = extract_from_graider_text(_content())
    assert out["extracted_responses"][0] == {
        "question": "Louisiana Purchase",
        "answer": "When the US bought a huge piece of land from France in 1803 for $15 million",
        "type": "vocab_term", "section": "VOCAB", "tag_id": "Louisiana Purchase"}


def test_graider_text_last_response_is_summary():
    out = extract_from_graider_text(_content())
    last = out["extracted_responses"][-1]
    assert last["type"] == "summary"
    assert last["section"] == "SUMMARY"
    assert last["tag_id"] == "main"
    assert last["question"] == "Summary"
    assert last["answer"].startswith("The Louisiana Purchase of 1803 was one of the most important")


def test_graider_text_numbered_question_parsed():
    out = extract_from_graider_text(_content())
    numbered = [r for r in out["extracted_responses"] if r["type"] == "numbered_question"]
    assert len(numbered) == 4  # the fixture has 4 numbered questions
    assert numbered[0]["section"] == "QUESTION"
    assert numbered[0]["tag_id"] == "1"
