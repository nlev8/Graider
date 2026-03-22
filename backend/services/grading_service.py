"""
Shared grading utilities for Graider.

Contains helper functions used by multiple grading paths
(join-code, class-based, teacher regrade).
"""
import logging

logger = logging.getLogger(__name__)


def grade_deterministic_question(question, student_answer, answer_key, answers):
    """Grade a single MC/TF/matching question deterministically.

    Returns (points_earned, is_correct, feedback) tuple.
    """
    q_type = question.get('type') or question.get('question_type', 'multiple_choice')
    points = question.get('points', 1)
    correct_answer = question.get('answer')

    if q_type == "multiple_choice":
        options = question.get('options', [])
        student_letter = None
        if isinstance(student_answer, int) and student_answer < len(options):
            student_letter = chr(65 + student_answer)
        elif isinstance(student_answer, str):
            student_letter = student_answer.upper().strip()
            if len(student_letter) > 1 and student_letter[1] == ')':
                student_letter = student_letter[0]
        correct_letter = correct_answer.upper().strip() if correct_answer else ""
        if len(correct_letter) > 1 and correct_letter[1] == ')':
            correct_letter = correct_letter[0]
        is_correct = student_letter == correct_letter
        earned = points if is_correct else 0
        feedback = "Correct!" if is_correct else f"Incorrect. The correct answer is {correct_answer}."
        return earned, is_correct, feedback

    elif q_type == "true_false":
        is_correct = str(student_answer).lower() == str(correct_answer).lower()
        earned = points if is_correct else 0
        explanation = question.get('explanation', '')
        feedback = "Correct!" if is_correct else f"Incorrect. The answer is {correct_answer}. {explanation}"
        return earned, is_correct, feedback

    elif q_type == "matching":
        correct_matches = question.get('answer', {})
        terms = question.get('terms', [])
        definitions = question.get('definitions', [])
        total_matches = len(terms)
        correct_count = 0
        for tIdx in range(total_matches):
            match_key = f"{answer_key}-match-{tIdx}"
            student_match = answers.get(match_key, "")
            term = terms[tIdx] if tIdx < len(terms) else ""
            correct_letter = None
            if term in correct_matches:
                correct_def = correct_matches[term]
                try:
                    def_idx = definitions.index(correct_def)
                    correct_letter = chr(65 + def_idx)
                except ValueError:
                    pass
            if correct_letter and student_match.upper() == correct_letter:
                correct_count += 1
        earned = round(points * (correct_count / total_matches)) if total_matches > 0 else 0
        is_correct = correct_count == total_matches
        feedback = f"Got {correct_count}/{total_matches} matches correct."
        return earned, is_correct, feedback

    return 0, False, ""


def load_teacher_config(teacher_id):
    """Load teacher's grading configuration from storage.

    Returns a dict with: global_ai_notes, grade_level, subject,
    grading_style, rubric, ai_model, period.

    This pattern was previously duplicated in 3 places:
    - student_portal_routes.py (join-code grading thread)
    - student_account_routes.py (class-based grading thread)
    - student_account_routes.py (teacher regrade)
    """
    teacher_config = {
        "global_ai_notes": "",
        "grade_level": "",
        "subject": "",
        "grading_style": "standard",
        "rubric": None,
        "ai_model": "gpt-4o-mini",
        "period": "",
    }

    try:
        from backend.storage import load as storage_load
        settings = storage_load("settings", teacher_id)
        if settings:
            teacher_config["global_ai_notes"] = settings.get("global_ai_notes", "")
            teacher_config["grade_level"] = settings.get("grade_level", "")
            teacher_config["subject"] = settings.get("subject", "")
        rubric_data = storage_load("rubric", teacher_id)
        if rubric_data:
            teacher_config["rubric"] = rubric_data
            teacher_config["grading_style"] = rubric_data.get("gradingStyle", "standard")
    except Exception as e:
        logger.debug("Failed to load teacher config for %s: %s", teacher_id, e)

    return teacher_config
