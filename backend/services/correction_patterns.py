"""
Correction Patterns Service
============================
Records teacher grade corrections, computes patterns, and builds
prompt injection context to calibrate AI grading over time.
"""

import os
import hashlib
import logging
from datetime import datetime, timezone

try:
    from backend.storage import load, save
except ImportError:
    from storage import load, save

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
MAX_CORRECTIONS = 100        # Per-teacher log cap
MIN_PATTERN_COUNT = 3        # Minimum corrections before a pattern surfaces
MAX_PROMPT_TYPES = 3         # Max question types in injection
MAX_PROMPT_CHARS = 800       # Total injection length cap

QUESTION_TYPE_LABELS = {
    "short_answer": "Short Answer",
    "essay": "Essay",
    "multiple_choice": "Multiple Choice",
    "true_false": "True/False",
    "matching": "Matching",
    "fill_in_blank": "Fill in the Blank",
    "open_ended": "Open Ended",
    "constructed_response": "Constructed Response",
    "vocabulary": "Vocabulary",
    "summary": "Summary",
}


# ── Storage helpers ────────────────────────────────────────────────────────────

def _load_corrections(teacher_id):
    """Load per-teacher correction log from storage."""
    data = load("grading_corrections", teacher_id)
    if not data:
        return {"corrections": [], "patterns": {}, "updated_at": ""}
    return data


def _save_corrections(teacher_id, data):
    """Save per-teacher correction log to storage."""
    save("grading_corrections", data, teacher_id)


def _load_global():
    """Load global (anonymized) correction log from storage."""
    data = load("grading_corrections:global", "system")
    if not data:
        return {"corrections": [], "patterns": {}, "teacher_hashes": {}, "updated_at": ""}
    return data


def _save_global(data):
    """Save global (anonymized) correction log to storage."""
    save("grading_corrections:global", data, "system")


def _hash_teacher(teacher_id):
    """Produce a 12-char anonymized hash of the teacher ID."""
    salt = os.environ.get("FLASK_SECRET_KEY", "graider-default-salt")
    return hashlib.sha256((teacher_id + salt).encode()).hexdigest()[:12]


# ── Pattern computation ────────────────────────────────────────────────────────

def _compute_patterns(corrections):
    """Group corrections by question_type and compute avg delta, count, direction.

    Returns a dict keyed by question_type:
        {
            "short_answer": {
                "count": 5,
                "avg_delta": -1.2,
                "direction": "down"   # "up" / "down" / "none"
            },
            ...
        }
    """
    grouped = {}
    for c in corrections:
        qt = c.get("question_type", "unknown")
        grouped.setdefault(qt, []).append(c.get("delta", 0))

    patterns = {}
    for qt, deltas in grouped.items():
        avg = sum(deltas) / len(deltas)
        if avg > 0.1:
            direction = "up"
        elif avg < -0.1:
            direction = "down"
        else:
            direction = "none"
        patterns[qt] = {
            "count": len(deltas),
            "avg_delta": round(avg, 2),
            "direction": direction,
        }
    return patterns


# ── Public API ─────────────────────────────────────────────────────────────────

def record_correction(
    teacher_id,
    ai_score,
    teacher_score,
    max_points,
    question_type,
    subject,
    grade_level,
    assignment,
    student_answer_snippet="",
):
    """Record a single teacher grade correction and update patterns.

    Args:
        teacher_id: Teacher's unique ID (Supabase UUID or 'local-dev')
        ai_score: The score the AI originally assigned
        teacher_score: The score the teacher corrected it to
        max_points: Maximum possible points for this question
        question_type: e.g. 'short_answer', 'essay'
        subject: e.g. 'English'
        grade_level: e.g. '8'
        assignment: Assignment name/title
        student_answer_snippet: Short excerpt of student answer (optional)
    """
    delta = teacher_score - ai_score
    timestamp = datetime.now(tz=timezone.utc).isoformat()

    entry = {
        "ai_score": ai_score,
        "teacher_score": teacher_score,
        "max_points": max_points,
        "delta": delta,
        "question_type": question_type,
        "subject": subject,
        "grade_level": grade_level,
        "assignment": assignment,
        "student_answer_snippet": student_answer_snippet,
        "timestamp": timestamp,
    }

    # ── Per-teacher update ────────────────────────────────────────────────────
    teacher_data = _load_corrections(teacher_id)
    teacher_data["corrections"].append(entry)
    # Cap at MAX_CORRECTIONS (keep most recent)
    if len(teacher_data["corrections"]) > MAX_CORRECTIONS:
        teacher_data["corrections"] = teacher_data["corrections"][-MAX_CORRECTIONS:]
    teacher_data["patterns"] = _compute_patterns(teacher_data["corrections"])
    teacher_data["updated_at"] = timestamp
    _save_corrections(teacher_id, teacher_data)

    # ── Global anonymized update ──────────────────────────────────────────────
    anon_entry = {
        "ai_score": ai_score,
        "teacher_score": teacher_score,
        "max_points": max_points,
        "delta": delta,
        "question_type": question_type,
        "subject": subject,
        "grade_level": grade_level,
        "assignment": assignment,
        # Deliberately omit: teacher_id, student_answer_snippet
        "timestamp": timestamp,
    }

    global_data = _load_global()
    global_data["corrections"].append(anon_entry)
    if len(global_data["corrections"]) > MAX_CORRECTIONS:
        global_data["corrections"] = global_data["corrections"][-MAX_CORRECTIONS:]

    # Track unique teacher hashes per question type
    teacher_hash = _hash_teacher(teacher_id)
    hashes_by_type = global_data.setdefault("teacher_hashes", {})
    type_hashes = hashes_by_type.setdefault(question_type, [])
    if teacher_hash not in type_hashes:
        type_hashes.append(teacher_hash)

    global_data["patterns"] = _compute_patterns(global_data["corrections"])
    global_data["updated_at"] = timestamp
    _save_global(global_data)


def build_correction_context(teacher_id, subject, question_types):
    """Build a prompt injection string from recorded correction patterns.

    Args:
        teacher_id: Teacher's unique ID
        subject: Current assignment subject (for context)
        question_types: List of question type strings present in this assignment

    Returns:
        A string to inject into the grading prompt, or "" if no patterns qualify.
    """
    teacher_data = _load_corrections(teacher_id)
    global_data = _load_global()

    teacher_patterns = teacher_data.get("patterns", {})
    global_patterns = global_data.get("patterns", {})
    global_hashes = global_data.get("teacher_hashes", {})
    teacher_corrections = teacher_data.get("corrections", [])

    lines = []

    # ── Per-teacher patterns ──────────────────────────────────────────────────
    # Find qualifying patterns for the question types in this assignment
    qualifying = []
    for qt in question_types:
        pattern = teacher_patterns.get(qt)
        if pattern and pattern.get("count", 0) >= MIN_PATTERN_COUNT:
            qualifying.append((qt, pattern))

    # Sort by count descending, take top MAX_PROMPT_TYPES
    qualifying.sort(key=lambda x: x[1]["count"], reverse=True)
    qualifying = qualifying[:MAX_PROMPT_TYPES]

    if qualifying:
        lines.append("GRADING CALIBRATION (based on your past corrections):")
        for qt, pattern in qualifying:
            label = QUESTION_TYPE_LABELS.get(qt, qt.replace("_", " ").title())
            direction = pattern["direction"]
            avg_delta = pattern["avg_delta"]
            count = pattern["count"]
            direction_str = "higher" if direction == "up" else "lower" if direction == "down" else "similar"
            line = (
                f"- {label}: You tend to score {direction_str} than the AI "
                f"(avg {avg_delta:+.1f} pts, based on {count} corrections)."
            )
            # Add one example snippet if available
            example = next(
                (
                    c.get("student_answer_snippet", "")
                    for c in reversed(teacher_corrections)
                    if c.get("question_type") == qt and c.get("student_answer_snippet")
                ),
                "",
            )
            if example:
                snippet = example[:80] + ("..." if len(example) > 80 else "")
                line += f' Example: "{snippet}"'
            lines.append(line)

    # ── Global patterns ───────────────────────────────────────────────────────
    global_qualifying = []
    for qt in question_types:
        g_pattern = global_patterns.get(qt)
        if not g_pattern:
            continue
        unique_teachers = len(global_hashes.get(qt, []))
        if unique_teachers >= MIN_PATTERN_COUNT:
            global_qualifying.append((qt, g_pattern, unique_teachers))

    global_qualifying.sort(key=lambda x: x[2], reverse=True)
    global_qualifying = global_qualifying[:MAX_PROMPT_TYPES]

    if global_qualifying:
        lines.append("ACCURACY NOTE (cross-teacher trend):")
        for qt, g_pattern, unique_teachers in global_qualifying:
            label = QUESTION_TYPE_LABELS.get(qt, qt.replace("_", " ").title())
            direction = g_pattern["direction"]
            avg_delta = g_pattern["avg_delta"]
            direction_str = "higher" if direction == "up" else "lower" if direction == "down" else "similar"
            lines.append(
                f"- {label}: Teachers across {unique_teachers} classrooms score "
                f"{direction_str} than AI (avg {avg_delta:+.1f} pts)."
            )

    if not lines:
        return ""

    result = "\n".join(lines)

    # ── Cap at MAX_PROMPT_CHARS ───────────────────────────────────────────────
    if len(result) > MAX_PROMPT_CHARS:
        result = result[:MAX_PROMPT_CHARS]

    return result
