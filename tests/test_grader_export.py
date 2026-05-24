"""Characterization tests for generate_email_content (Wave 7 Slice 7 — grader decomposition).

Pins the student-email subject/body formatting BEFORE moving generate_email_content
into a new backend/services/grader_export.py (the home for the email/CSV export
cluster). Pure (string formatting from dicts — no I/O / LLM / Flask). Imported via
`assignment_grader` (re-export shim).
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from assignment_grader import generate_email_content

SI = {"first_name": "Maria Elena", "last_name": "Gonzalez"}
GR = {"letter_grade": "B+", "score": 88, "feedback": "Strong analysis of the causes."}


def test_subject_format():
    subject, _ = generate_email_content(SI, GR, "Civil War Essay")
    assert subject == "Grade for Civil War Essay: B+"


def test_body_golden():
    _, body = generate_email_content(SI, GR, "Civil War Essay")
    assert body == (
        "Hi Maria,\n\n"
        "Here is your grade and feedback for Civil War Essay:\n\n"
        "GRADE: 88/100 (B+)\n\n"
        "FEEDBACK:\n"
        "Strong analysis of the causes.\n\n"
        "If you have any questions about your grade, please see me during class.\n\n"
        "- Mr. Crionas US History\n")


def test_first_name_only_uses_first_token():
    # "Maria Elena" -> "Maria"
    _, body = generate_email_content(SI, GR, "X")
    assert body.startswith("Hi Maria,\n")


def test_missing_first_name_defaults_to_student():
    _, body = generate_email_content({}, GR, "X")
    assert body.startswith("Hi Student,\n")
