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


# ── export_detailed_report (writes a detailed grades CSV) ──

import os  # noqa: E402

from assignment_grader import export_detailed_report  # noqa: E402

DETAIL_GRADES = [{
    "student_id": "S1", "student_name": "Alice", "email": "a@x.edu", "assignment": "Quiz",
    "score": 88, "letter_grade": "B+",
    "breakdown": {"content_accuracy": 35, "completeness": 22, "writing_quality": 18,
                  "effort_engagement": 13},
    "feedback": "Good work", "filename": "alice.docx"}]


def test_export_detailed_report_writes_csv(tmp_path):
    path = export_detailed_report(DETAIL_GRADES, str(tmp_path), "Unit 1 Quiz!")
    assert path.endswith(".csv")
    assert os.path.basename(path).startswith("Detailed_Report_Unit_1_Quiz_")  # sanitized name
    with open(path) as f:
        content = f.read()
    assert content == (
        "Student ID,Student Name,Email,Assignment,Score,Letter Grade,"
        "Content (40),Completeness (25),Writing (20),Effort (15),Feedback,Filename\n"
        "S1,Alice,a@x.edu,Quiz,88,B+,35,22,18,13,Good work,alice.docx\n")


# ── export_focus_csv (per-assignment Focus CSVs; random opener patched for determinism) ──

from unittest.mock import patch  # noqa: E402

from assignment_grader import export_focus_csv  # noqa: E402

FOCUS_GRADES = [
    {"student_id": "1950304", "first_name": "Alice", "score": 88, "feedback": "Good   work here.",
     "filename": "Alice_Smith_Unit1_Quiz.docx"},
    {"student_id": "UNKNOWN", "first_name": "Bob", "score": 50, "feedback": "x",
     "filename": "Bob_Jones_Unit1_Quiz.docx"},
]


def test_export_focus_csv_groups_by_assignment_skips_unknown(tmp_path):
    # patch random.choice (stdlib) so the opener is deterministic across pre/post extraction
    with patch("random.choice", lambda seq: seq[0]):
        files = export_focus_csv(FOCUS_GRADES, str(tmp_path), "ignored")
    assert len(files) == 1                                   # both grades → one "Unit1 Quiz" group
    assert os.path.basename(files[0]).startswith("Unit1_Quiz_")
    with open(files[0]) as f:
        content = f.read()
    # UNKNOWN student is skipped; comment = opener[0] (score>=80 "Nice work") + cleaned feedback
    assert content == (
        "Student ID,Score,Comment\n"
        '1950304,88,"Nice work, Alice! Good work here."\n')


# ── save_to_master_csv (upsert master_grades.csv with score-based dedup) ──

from datetime import datetime  # noqa: E402

from assignment_grader import save_to_master_csv  # noqa: E402

MASTER_HEADER = (
    "Date,Student ID,Student Name,First Name,Last Name,Period,Assignment,Unit,Quarter,"
    "Overall Score,Letter Grade,Content Accuracy,Completeness,Writing Quality,"
    "Effort Engagement,Feedback,Approved,API Cost,Input Tokens,Output Tokens,API Calls,AI Model")


def _master_rows(folder):
    import os
    with open(os.path.join(folder, "master_grades.csv")) as f:
        return f.read().strip().split("\n")


def test_master_csv_fresh_write(tmp_path):
    g = [{"student_id": "S1", "student_name": "Alice", "first_name": "Alice", "last_name": "Smith",
          "period": "3", "assignment": "Quiz 1.docx", "score": 80, "letter_grade": "B-",
          "breakdown": {"content_accuracy": 30, "completeness": 20, "writing_quality": 18,
                        "effort_engagement": 12}, "feedback": "ok"}]
    save_to_master_csv(g, str(tmp_path))
    rows = _master_rows(str(tmp_path))
    assert rows[0] == MASTER_HEADER
    assert len(rows) == 2  # header + 1
    cells = rows[1].split(",")
    assert cells[0] == datetime.now().strftime('%Y-%m-%d')  # Date
    assert cells[1] == "S1" and cells[6] == "Quiz 1.docx" and cells[9] == "80"


def test_master_csv_dedup_higher_score_replaces(tmp_path):
    base = {"student_id": "S1", "first_name": "A", "student_name": "A", "assignment": "Quiz 1.docx",
            "breakdown": {}}
    save_to_master_csv([{**base, "score": 80}], str(tmp_path))
    save_to_master_csv([{**base, "score": 95, "letter_grade": "A"}], str(tmp_path))
    rows = _master_rows(str(tmp_path))
    assert len(rows) == 2  # header + 1 (replaced, not duplicated)
    assert rows[1].split(",")[9] == "95"


def test_master_csv_dedup_lower_score_keeps_old(tmp_path):
    base = {"student_id": "S1", "first_name": "A", "student_name": "A", "assignment": "Quiz 1.docx",
            "breakdown": {}}
    save_to_master_csv([{**base, "score": 90}], str(tmp_path))
    save_to_master_csv([{**base, "score": 60}], str(tmp_path))
    rows = _master_rows(str(tmp_path))
    assert len(rows) == 2
    assert rows[1].split(",")[9] == "90"  # old higher score kept


def test_master_csv_skips_unknown(tmp_path):
    save_to_master_csv([{"student_id": "UNKNOWN", "assignment": "Q", "score": 50, "breakdown": {}}],
                       str(tmp_path))
    assert len(_master_rows(str(tmp_path))) == 1  # header only
