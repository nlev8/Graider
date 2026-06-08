"""Per-student writing-profile persistence for the grading pipeline: maintain a running-average
writing-style profile under ~/.graider_data/student_history/ for AI-detection context. Flask-free
(json / file I/O — no LLM) extracted from assignment_grader.py. Wave 7 (grading-engine
decomposition). The one diagnostic print became a _logger call on extraction (return values and
written JSON are unchanged).
"""
import json
import logging
import os
from datetime import datetime

_logger = logging.getLogger(__name__)


def _safe_sid(student_id: str) -> str:
    """Sanitize a student_id for safe use as a filename component.

    VB2b: matches storage.py / student_history.py — strips path separators so
    a crafted student_id (e.g. '../../other-tenant') can't escape the
    per-teacher history directory.
    """
    return str(student_id).replace('/', '_').replace('\\', '_')


def _history_dir_for(teacher_id: str = 'local-dev') -> str:
    """Resolve the per-teacher writing-profile/history directory.

    VB2b (audit #3): writing profiles live inside the same per-student
    history files as grade history, so they must be scoped per teacher too.
    `local-dev` keeps the legacy global path (honors a monkeypatched HOME in
    tests); any real teacher routes to their `_tenant_home` shard.
    """
    if not teacher_id or teacher_id == 'local-dev':
        return os.path.expanduser("~/.graider_data/student_history")
    try:
        from backend.storage import _tenant_home
    except ImportError:
        from storage import _tenant_home  # type: ignore[no-redef]
    return os.path.join(_tenant_home(teacher_id), ".graider_data", "student_history")


def update_writing_profile(student_id: str, current_style: dict, student_name: str = None,
                           teacher_id: str = 'local-dev'):
    """
    Update student's writing profile with new submission data.
    Maintains running averages across assignments.
    """
    if not current_style or not student_id:
        return

    history_dir = _history_dir_for(teacher_id)
    history_file = os.path.join(history_dir, f"{_safe_sid(student_id)}.json")

    try:
        if os.path.exists(history_file):
            with open(history_file, 'r') as f:
                history = json.load(f)
        else:
            history = {"student_id": student_id, "assignments": []}

        # Always update the student name if provided
        if student_name:
            history["name"] = student_name

        # Get or initialize writing profile
        profile = history.get("writing_profile", {
            "avg_word_length": 0,
            "avg_sentence_length": 0,
            "avg_complexity_score": 0,
            "avg_academic_words": 0,
            "uses_contractions": False,
            "sample_count": 0
        })

        # Update running averages
        n = profile.get("sample_count", 0)
        if n > 0:
            profile["avg_word_length"] = (profile["avg_word_length"] * n + current_style["avg_word_length"]) / (n + 1)
            profile["avg_sentence_length"] = (profile["avg_sentence_length"] * n + current_style["avg_sentence_length"]) / (n + 1)
            profile["avg_complexity_score"] = (profile["avg_complexity_score"] * n + current_style["complexity_score"]) / (n + 1)
            profile["avg_academic_words"] = (profile["avg_academic_words"] * n + current_style["academic_word_count"]) / (n + 1)
        else:
            profile["avg_word_length"] = current_style["avg_word_length"]
            profile["avg_sentence_length"] = current_style["avg_sentence_length"]
            profile["avg_complexity_score"] = current_style["complexity_score"]
            profile["avg_academic_words"] = current_style["academic_word_count"]

        profile["uses_contractions"] = profile.get("uses_contractions", False) or current_style["uses_contractions"]
        profile["sample_count"] = n + 1

        # Round values
        for key in ["avg_word_length", "avg_sentence_length", "avg_complexity_score", "avg_academic_words"]:
            if key in profile:
                profile[key] = round(profile[key], 2)

        history["writing_profile"] = profile
        history["last_updated"] = datetime.now().isoformat()

        # Save updated history
        os.makedirs(history_dir, exist_ok=True)
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)

    except Exception as e:
        _logger.warning("Could not update writing profile: %s", e)


def get_writing_profile(student_id: str, teacher_id: str = 'local-dev') -> dict:
    """
    Retrieve student's historical writing profile.
    """
    if not student_id:
        return None

    history_dir = _history_dir_for(teacher_id)
    history_file = os.path.join(history_dir, f"{_safe_sid(student_id)}.json")

    try:
        if os.path.exists(history_file):
            with open(history_file, 'r') as f:
                history = json.load(f)
                return history.get("writing_profile")
    except Exception as e:
        _logger.debug("writing profile history load failed: %s", type(e).__name__)

    return None
