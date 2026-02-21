"""
Student Info Tools
==================
Tools for retrieving individual student accommodation details and performance streaks.
Zero AI API calls — all data from local files.
"""
import csv
import io
import os

from backend.services.assistant_tools import (
    _load_master_csv, _load_accommodations, _load_roster,
    _fuzzy_name_match, _safe_int_score, ACCOMMODATIONS_DIR, PERIODS_DIR,
)

ROSTERS_DIR = os.path.expanduser("~/.graider_data/rosters")


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
    {
        "name": "remove_student_from_roster",
        "description": "Remove a student from the class roster. Finds the student by name (fuzzy match) across all period CSV files and removes their row. Use when a teacher says a student has transferred, withdrawn, or needs to be removed from the roster.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_name": {
                    "type": "string",
                    "description": "Student name to remove (fuzzy match)"
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


def _parse_csv_name(raw_name):
    """Parse 'Last; First' or 'Last, First' into display name."""
    raw_name = raw_name.strip().strip('"')
    if ';' in raw_name:
        parts = raw_name.split(';', 1)
        return (parts[1].strip() + ' ' + parts[0].strip()).strip()
    elif ',' in raw_name:
        parts = raw_name.split(',', 1)
        return (parts[1].strip() + ' ' + parts[0].strip()).strip()
    return raw_name


def _find_all_student_files(student_name, dirs):
    """Search for a student across CSV files in multiple directories.

    Returns list of (matched_name, filepath, label) for ALL files containing the student.
    """
    matches = []
    seen_files = set()
    for directory, label_prefix in dirs:
        if not os.path.exists(directory):
            continue
        for f in sorted(os.listdir(directory)):
            if not f.endswith('.csv'):
                continue
            filepath = os.path.join(directory, f)
            if filepath in seen_files:
                continue
            try:
                with open(filepath, 'r', encoding='utf-8') as fh:
                    reader = csv.DictReader(fh)
                    for row in reader:
                        raw_name = row.get('Student', '').strip().strip('"')
                        display_name = _parse_csv_name(raw_name)
                        if _fuzzy_name_match(student_name, display_name) or _fuzzy_name_match(student_name, raw_name):
                            if label_prefix == "periods":
                                meta_path = filepath.replace('.csv', '.meta.json')
                                if os.path.exists(meta_path):
                                    import json
                                    with open(meta_path, 'r') as mf:
                                        meta = json.load(mf)
                                    label = meta.get('period_name', f.replace('.csv', ''))
                                else:
                                    label = f.replace('.csv', '').replace('_', ' ')
                            else:
                                label = f.replace('.csv', '').replace('_', ' ')
                            matches.append((display_name, filepath, label))
                            seen_files.add(filepath)
                            break  # found in this file, move to next
            except Exception:
                continue
    return matches


def _remove_student_from_csv(student_name, filepath):
    """Remove a student from a single CSV file. Returns (removed_count, remaining_count)."""
    with open(filepath, 'r', encoding='utf-8') as fh:
        content = fh.read()
    reader = csv.DictReader(io.StringIO(content))
    fieldnames = reader.fieldnames
    rows_to_keep = []
    removed_count = 0
    for row in reader:
        raw_name = row.get('Student', '').strip().strip('"')
        display_name = _parse_csv_name(raw_name)
        if _fuzzy_name_match(student_name, display_name) or _fuzzy_name_match(student_name, raw_name):
            removed_count += 1
            continue
        rows_to_keep.append(row)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows_to_keep)
    with open(filepath, 'w', encoding='utf-8', newline='') as fh:
        fh.write(output.getvalue())

    return removed_count, len(rows_to_keep)


def remove_student_from_roster(student_name):
    """Remove a student from ALL roster CSV files where they appear."""
    if not student_name:
        return {"error": "student_name is required."}

    search_dirs = [
        (PERIODS_DIR, "periods"),
        (ROSTERS_DIR, "rosters"),
    ]

    matches = _find_all_student_files(student_name, search_dirs)

    if not matches:
        # Provide diagnostic info
        roster_info = []
        for directory, prefix in search_dirs:
            if not os.path.exists(directory):
                continue
            for f in sorted(os.listdir(directory)):
                if not f.endswith('.csv'):
                    continue
                filepath = os.path.join(directory, f)
                try:
                    with open(filepath, 'r', encoding='utf-8') as fh:
                        reader = csv.DictReader(fh)
                        names = [row.get('Student', '').strip().strip('"') for row in reader]
                        roster_info.append({"file": f, "directory": prefix, "count": len(names), "sample": names[:5]})
                except Exception:
                    roster_info.append({"file": f, "directory": prefix, "error": "Could not read"})
        return {
            "error": f"No student found matching '{student_name}' in any roster.",
            "rosters_searched": roster_info if roster_info else "No CSV files found",
            "hint": "Check the name format in the roster files above."
        }

    # Remove from ALL matched files
    matched_name = matches[0][0]
    results = []
    errors = []
    for _name, filepath, label in matches:
        try:
            removed, remaining = _remove_student_from_csv(student_name, filepath)
            results.append({"source": label, "removed": removed, "remaining": remaining})
        except Exception as e:
            errors.append({"source": label, "error": str(e)})

    sources = [r["source"] for r in results]
    msg = f"Removed {matched_name} from {len(results)} file(s): {', '.join(sources)}."
    if errors:
        msg += f" Failed on {len(errors)} file(s)."

    return {
        "removed": matched_name,
        "files_updated": results,
        "errors": errors if errors else None,
        "message": msg,
    }


# ═══════════════════════════════════════════════════════
# HANDLER MAP
# ═══════════════════════════════════════════════════════

STUDENT_TOOL_HANDLERS = {
    "get_student_accommodations": get_student_accommodations,
    "get_student_streak": get_student_streak,
    "remove_student_from_roster": remove_student_from_roster,
}
