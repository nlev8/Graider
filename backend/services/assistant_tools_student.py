"""
Student Info Tools
==================
Tools for retrieving individual student accommodation details and performance streaks.
Zero AI API calls — all data from local files.
"""
from backend.services.assistant_tools import (
    _load_master_csv, _load_accommodations, _load_roster,
    _fuzzy_name_match, _safe_int_score, ACCOMMODATIONS_DIR,
)


# ═══════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════

STUDENT_TOOL_DEFINITIONS = [
    {
        "name": "get_student_accommodations",
        "description": "Get a specific student's IEP/504 accommodation details — presets, notes, and how they affect grading. Use when the teacher asks about a student's accommodations or needs to review support plans.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {
                    "type": "string",
                    "description": "Student name (fuzzy match)"
                }
            },
            "required": ["student_name"]
        }
    },
    {
        "name": "get_student_streak",
        "description": "Show a student's consecutive improvement or decline streaks across recent assignments. Returns assignment-by-assignment scores with direction indicators.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {
                    "type": "string",
                    "description": "Student name (fuzzy match)"
                }
            },
            "required": ["student_name"]
        }
    },
]


# ═══════════════════════════════════════════════════════
# TOOL HANDLERS
# ═══════════════════════════════════════════════════════

def get_student_accommodations(student_name):
    """Pull specific IEP/504 presets, notes, and grading impact for a student."""
    if not student_name:
        return {"error": "student_name is required."}

    # Find the student in the roster to get their ID
    roster = _load_roster()
    student_id = None
    matched_name = None
    for entry in roster:
        rname = entry.get("student_name", "") or entry.get("name", "")
        if _fuzzy_name_match(student_name, rname):
            student_id = entry.get("student_id", "")
            matched_name = rname
            break

    # Also try from grades data if roster is empty
    if not student_id:
        rows = _load_master_csv(period_filter='all')
        for row in rows:
            if _fuzzy_name_match(student_name, row.get("student_name", "")):
                student_id = row.get("student_id", "")
                matched_name = row.get("student_name", "")
                break

    if not student_id:
        return {"error": f"No student found matching '{student_name}'."}

    accommodations = _load_accommodations()
    accomm = accommodations.get(student_id)

    if not accomm:
        return {
            "student_name": matched_name,
            "student_id": student_id,
            "has_accommodations": False,
            "message": f"{matched_name} does not have IEP/504 accommodations on file."
        }

    presets = accomm.get("presets", [])
    notes = accomm.get("notes", "")

    # Map presets to grading impact descriptions (compact)
    impact_map = {
        "extended_time": "Extra time on assignments/tests",
        "reduced_workload": "Fewer questions required for full credit",
        "simplified_prompts": "Simplified language in prompts",
        "graphic_organizer": "Graphic organizers provided",
        "oral_responses": "Oral responses accepted for written work",
        "preferential_seating": "Seating accommodation (no grading impact)",
        "chunked_assignments": "Assignments broken into smaller sections",
        "read_aloud": "Test/assignment read aloud",
        "word_bank": "Word bank provided on assessments",
        "calculator": "Calculator allowed",
    }

    grading_impacts = []
    for p in presets:
        desc = impact_map.get(p, p.replace("_", " ").title())
        grading_impacts.append(desc)

    return {
        "student_name": matched_name,
        "student_id": student_id,
        "has_accommodations": True,
        "presets": presets,
        "grading_impacts": grading_impacts,
        "notes": notes,
    }


def get_student_streak(student_name):
    """Show consecutive improvement/decline streaks with assignment history."""
    if not student_name:
        return {"error": "student_name is required."}

    rows = _load_master_csv(period_filter='all')

    # Find all grades for this student
    student_rows = []
    matched_name = None
    for row in rows:
        if _fuzzy_name_match(student_name, row.get("student_name", "")):
            if not matched_name:
                matched_name = row.get("student_name", "")
            student_rows.append(row)

    if not student_rows:
        return {"error": f"No grades found for '{student_name}'."}

    # Sort by date
    student_rows.sort(key=lambda r: r.get("date", ""))

    # Build assignment history with direction
    history = []
    prev_score = None
    improving_streak = 0
    declining_streak = 0
    current_streak_type = None  # "improving", "declining", "stable"

    for row in student_rows:
        score = _safe_int_score(row.get("score"))
        entry = {
            "assignment": row.get("assignment", ""),
            "score": score,
            "date": row.get("date", ""),
        }

        if prev_score is not None:
            diff = score - prev_score
            if diff > 0:
                entry["direction"] = "up"
                entry["change"] = f"+{diff}"
                if current_streak_type == "improving":
                    improving_streak += 1
                else:
                    improving_streak = 1
                    declining_streak = 0
                current_streak_type = "improving"
            elif diff < 0:
                entry["direction"] = "down"
                entry["change"] = str(diff)
                if current_streak_type == "declining":
                    declining_streak += 1
                else:
                    declining_streak = 1
                    improving_streak = 0
                current_streak_type = "declining"
            else:
                entry["direction"] = "stable"
                entry["change"] = "0"
                current_streak_type = "stable"
                improving_streak = 0
                declining_streak = 0

        prev_score = score
        history.append(entry)

    scores = [_safe_int_score(r.get("score")) for r in student_rows]
    avg = round(sum(scores) / len(scores), 1) if scores else 0

    return {
        "student_name": matched_name,
        "assignment_count": len(history),
        "average": avg,
        "current_streak": current_streak_type or "n/a",
        "improving_streak": improving_streak,
        "declining_streak": declining_streak,
        "history": history,
    }


# ═══════════════════════════════════════════════════════
# HANDLER MAP
# ═══════════════════════════════════════════════════════

STUDENT_TOOL_HANDLERS = {
    "get_student_accommodations": get_student_accommodations,
    "get_student_streak": get_student_streak,
}
