"""Assignment-config saving tool.

Pure-move of whole functions out of the former single-file module; bodies
are byte-identical.
"""
import os
import json

from backend.services.assistant_tools import ASSIGNMENTS_DIR
from backend.utils.compliance import require_teacher_id
import sentry_sdk


def save_assignment_config(title, document_text=None, questions=None, totalPoints=None,
                           effortPoints=None, gradingNotes=None, rubricType=None,
                           customMarkers=None, teacher_id='local-dev'):
    """Save or update an assignment config in Grading Setup.

    Merge-updates: loads existing config if present, applies only the
    provided fields, and writes back. This lets the assistant update
    point values or questions without wiping the rest of the config.
    """
    require_teacher_id(teacher_id)
    import time

    if not title or not title.strip():
        return {"error": "Title is required."}

    safe_title = ''.join(c for c in title if c.isalnum() or c in ' -_').strip()
    if not safe_title:
        return {"error": "Title contains no valid characters."}

    os.makedirs(ASSIGNMENTS_DIR, exist_ok=True)
    config_path = os.path.join(ASSIGNMENTS_DIR, safe_title + '.json')

    # Load existing config if present
    existing = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except Exception as e:  # noqa: BLE001  # broad catch: error is logged
            sentry_sdk.capture_exception(e)

    # Merge updates
    existing["title"] = title
    if document_text is not None:
        existing["importedDoc"] = {
            "text": document_text,
            "html": "",
            "filename": safe_title + ".docx",
            "loading": False,
        }
    if questions is not None:
        # Ensure each question has an id
        ts = int(time.time() * 1000)
        for i, q in enumerate(questions):
            if not q.get("id"):
                q["id"] = ts + i
        existing["questions"] = questions
    if totalPoints is not None:
        existing["totalPoints"] = totalPoints
    if effortPoints is not None:
        existing["effortPoints"] = effortPoints
    if gradingNotes is not None:
        existing["gradingNotes"] = gradingNotes
    if rubricType is not None:
        existing["rubricType"] = rubricType
    if customMarkers is not None:
        existing["customMarkers"] = customMarkers

    # Ensure required fields exist with defaults
    defaults = {
        "subject": "", "totalPoints": 100, "instructions": "",
        "aliases": [], "customMarkers": [], "excludeMarkers": [],
        "gradingNotes": "", "questions": [], "responseSections": [],
        "rubricType": "standard", "customRubric": None,
        "useSectionPoints": False, "sectionTemplate": "Custom",
        "effortPoints": 15, "completionOnly": False,
        "countsTowardsGrade": True,
    }
    for key, default_val in defaults.items():
        if key not in existing:
            existing[key] = default_val

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, indent=2)

    q_count = len(existing.get("questions", []))
    q_total = sum(q.get("points", 0) for q in existing.get("questions", []))

    return {
        "status": "saved",
        "config_name": safe_title,
        "title": title,
        "questions_count": q_count,
        "questions_points": q_total,
        "total_points": existing.get("totalPoints", 100),
        "message": "Assignment config saved with " + str(q_count) + " questions (" + str(q_total) + " pts + " + str(existing.get("effortPoints", 15)) + " effort).",
    }
