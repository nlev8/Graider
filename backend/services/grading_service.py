"""
Shared grading utilities for Graider.

Contains helper functions used by multiple grading paths
(join-code, class-based, teacher regrade).
"""
import logging

logger = logging.getLogger(__name__)


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
