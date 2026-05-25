"""FERPA: tests for sanitize_grading_prompt_for_ai + end-to-end prompt-PII assertions.

The grading-prompt sanitizer must redact student PII from text about to be sent to an external
LLM WITHOUT corrupting legitimate gradeable content (naked numbers/dates are answers, not PII).
Strictness (user-approved): name parts + emails/phones/SSNs/addresses + CONTEXT-LABELED IDs/DOB/
zip; naked numbers/dates preserved.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tests/ for grading_fakes

from backend.services.grader_text_prep import sanitize_grading_prompt_for_ai
from grading_fakes import patched_llm


# ── Unit: what it redacts ─────────────────────────────────────────────────────

def test_redacts_student_name_parts_case_insensitive():
    out = sanitize_grading_prompt_for_ai("Maria Garcia", "maria thinks MARIA and Garcia wrote this")
    assert "maria" not in out.lower()
    assert "garcia" not in out.lower()
    assert "[STUDENT]" in out


def test_does_not_redact_short_name_fragments():
    # parts of length <= 2 are not redacted (avoid nuking "I"/"Al")
    out = sanitize_grading_prompt_for_ai("Al Bo", "I think Albania is a country")
    assert "Albania" in out  # "Al"/"Bo" too short → no redaction, and \b protects substrings


def test_redacts_email_phone_ssn_address():
    txt = ("contact me at jane.doe@school.edu or 555-123-4567, SSN 123-45-6789, "
           "I live at 1600 Pennsylvania Avenue")
    out = sanitize_grading_prompt_for_ai("Jane Doe", txt)
    assert "@school.edu" not in out and "[EMAIL-REMOVED]" in out
    assert "555-123-4567" not in out and "[PHONE-REMOVED]" in out
    assert "123-45-6789" not in out and "[SSN-REMOVED]" in out
    assert "[ADDRESS-REMOVED]" in out


def test_redacts_labeled_id_dob_zip():
    txt = "Student ID: 1234567  DOB: 02/15/2009  Zip: 33101"
    out = sanitize_grading_prompt_for_ai("", txt)
    assert "1234567" not in out and "[ID-REMOVED]" in out
    assert "02/15/2009" not in out and "[DOB-REMOVED]" in out
    assert "33101" not in out and "[ZIP-REMOVED]" in out


# ── Unit: what it PRESERVES (grading correctness) ─────────────────────────────

def test_preserves_naked_numeric_and_date_answers():
    txt = ("The Louisiana Purchase added 828,000 square miles (8280000 acres) in 1803. "
           "The battle was on 2/15/1861 and the population reached 12345 by 1850.")
    out = sanitize_grading_prompt_for_ai("Maria Garcia", txt)
    for val in ["828,000", "8280000", "1803", "2/15/1861", "12345", "1850"]:
        assert val in out, f"legitimate answer value {val!r} was wrongly redacted"


def test_empty_text_passthrough():
    assert sanitize_grading_prompt_for_ai("Maria Garcia", "") == ""
    assert sanitize_grading_prompt_for_ai("", "no pii here, just 1803") == "no pii here, just 1803"


# ── End-to-end: PII seeded IN ANSWERS must never reach the captured LLM prompt ─
# (the static fixtures strip the name header during extraction, so these seed PII directly into
# the student answers/responses that DO reach the prompt — the real proof the fix works.)

_NAME = "Maria Garcia"
# A student answer that embeds the student's own name + an email + a labeled ID, plus a
# legitimate naked numeric answer that MUST survive (grading correctness).
_PII_ANSWER = ("My name is Maria Garcia, email maria.garcia@school.edu, Student ID: 1234567 — "
               "the Louisiana Purchase added 828000 acres in 1803.")


def _assert_no_pii_preserves_numbers(prompt: str):
    for leak in ["Maria", "Garcia", "maria.garcia@school.edu", "1234567"]:
        assert leak not in prompt, f"PII leaked into prompt: {leak!r}"
    assert "[STUDENT]" in prompt
    # legitimate answer values preserved
    assert "828000" in prompt and "1803" in prompt


def test_grade_per_question_strips_pii_from_prompt():
    from backend.services.grading_leaves import grade_per_question
    with patched_llm() as book:
        grade_per_question(
            question="Explain the Louisiana Purchase.", student_answer=_PII_ANSWER,
            expected_answer="", points=10, grade_level="6", subject="Social Studies",
            teacher_instructions="", grading_style="standard",
            ai_model="gpt-4o-mini", ai_provider="openai", student_name=_NAME,
        )
    _assert_no_pii_preserves_numbers(book.prompts(schema="PerQuestionResponse")[0])


def test_detect_ai_plagiarism_strips_pii_from_prompt():
    from backend.services.grading_leaves import detect_ai_plagiarism
    with patched_llm() as book:
        detect_ai_plagiarism(_PII_ANSWER + " " + _PII_ANSWER, grade_level="6", student_name=_NAME)
    _assert_no_pii_preserves_numbers(book.prompts(schema="DetectionResponse")[0])


def test_generate_feedback_strips_pii_from_prompt():
    from backend.services.grading_leaves import generate_feedback
    qr = [{"grade": {"score": 8, "possible": 10, "reasoning": "ok", "quality": "good"},
           "excellent": False, "improvement_note": ""}]
    with patched_llm() as book:
        generate_feedback(
            question_results=qr, total_score=80, total_possible=100, letter_grade="B",
            grade_level="6", subject="Social Studies", ai_model="gpt-4o", ai_provider="openai",
            student_responses=[{"question": "Q1", "answer": _PII_ANSWER}], student_name=_NAME,
        )
    _assert_no_pii_preserves_numbers(book.prompts(schema="FeedbackResponse")[0])


def test_grade_multipass_threads_student_name_to_all_prompts():
    """End-to-end: a GRAIDER submission whose answer embeds PII — no captured prompt may leak it."""
    import assignment_grader as g
    submission = (
        "Vocabulary\n\n[GRAIDER:VOCAB:Louisiana Purchase]\n"
        "Louisiana Purchase: (5 pts)\n" + _PII_ANSWER + "\n"
    )
    with patched_llm() as book:
        g.grade_multipass(
            student_name=_NAME, assignment_data={"type": "text", "content": submission},
            custom_ai_instructions="", grade_level="6", subject="Social Studies",
            ai_model="gpt-4o-mini", effort_points=15, grading_style="standard",
        )
    all_prompts = book.prompts(provider="openai")
    assert all_prompts, "expected at least one captured prompt"
    for p in all_prompts:
        for leak in ["Maria", "Garcia", "maria.garcia@school.edu", "1234567"]:
            assert leak not in p, f"PII {leak!r} leaked in a multipass prompt"


def test_portal_grade_written_questions_strips_pii():
    from backend.services import portal_grading
    questions = [{"type": "short_answer", "question": "Explain the purchase.",
                  "answer": "", "points": 10, "_answer_key": "0-0", "section_name": "Q"}]
    answers = {"0-0": _PII_ANSWER}
    with patched_llm() as book:
        portal_grading.grade_written_questions(
            questions, answers, ai_notes="", grade_level="6", subject="Social Studies",
            grading_style="standard", ai_model="gpt-4o-mini", student_name=_NAME,
        )
    _assert_no_pii_preserves_numbers(book.prompts(schema="PerQuestionResponse")[0])


def test_assignment_player_grade_with_ai_strips_pii_from_prompt():
    """Boundary #6: the assignment-player route grades per-question via grade_per_question —
    threading student_name through it must redact the name from the captured prompt."""
    from backend.routes.assignment_player_routes import _grade_with_ai
    with patched_llm() as book:
        _grade_with_ai(
            question={"question": "Explain the Louisiana Purchase.", "answer": ""},
            student_answer=_PII_ANSWER, q_type="short_answer", q_points=10,
            grade_level="6", subject="Social Studies", teacher_instructions="",
            grading_style="standard", section_name="Q", ai_model="gpt-4o-mini",
            ai_provider="openai", student_name=_NAME,
        )
    _assert_no_pii_preserves_numbers(book.prompts(schema="PerQuestionResponse")[0])
