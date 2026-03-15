"""
Student Info Tools
==================
Tools for retrieving individual student accommodation details and performance streaks.
Zero AI API calls — all data from local files.
"""
import csv
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime

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
        "description": "Remove a student from ALL records: roster CSVs, grading results, student history, accommodations, parent contacts, ELL data, master grades CSV, and Supabase. Use when a teacher says a student has transferred, withdrawn, or needs to be completely removed.",
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
    {
        "name": "export_student_data",
        "description": "Export all stored data for a specific student (grades, history, accommodations, etc.) as JSON and PDF files. Use for parent data requests, student transfers, or FERPA compliance.",
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
        "name": "import_student_data",
        "description": "Import a previously exported student data file into Graider. Imports grades, history, accommodations, ELL data, and parent contacts. Use when a student transfers in from another Graider teacher.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the exported student JSON file"
                },
                "period": {
                    "type": "string",
                    "description": "Optional period CSV filename to add the student to"
                },
                "student_id": {
                    "type": "string",
                    "description": "Optional student ID override"
                }
            },
            "required": ["file_path"]
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


def _delete_student_supabase(student_name):
    """Fully delete a student from Supabase (cascade: behavior_events, class_students, students).

    Returns a status message string, or empty string on skip/failure.
    """
    try:
        from flask import g
        teacher_id = getattr(g, 'user_id', None)
        if not teacher_id or teacher_id == 'local-dev':
            teacher_id = os.getenv('DEV_USER_ID')
        if not teacher_id:
            return ""

        from backend.supabase_client import get_supabase
        sb = get_supabase()
        if not sb:
            return ""

        # Parse name into first/last for matching
        parts = student_name.strip().split()
        if not parts:
            return ""

        # Query all students for this teacher (including inactive)
        res = sb.table('students').select('id, first_name, last_name').eq(
            'teacher_id', teacher_id
        ).execute()

        if not res.data:
            return ""

        # Find matching student(s) by fuzzy name match
        deleted = []
        for s in res.data:
            full_name = f"{s.get('first_name', '')} {s.get('last_name', '')}".strip()
            if _fuzzy_name_match(student_name, full_name):
                sid = s['id']
                # Cascade delete: child tables first, then student
                sb.table('behavior_events').delete().eq('student_id', sid).execute()
                sb.table('class_students').delete().eq('student_id', sid).execute()
                sb.table('students').delete().eq('id', sid).execute()
                deleted.append(full_name)

        if deleted:
            return f"Deleted from Supabase: {', '.join(deleted)} (removed from Companion app)."
        return ""
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Supabase student delete failed: %s", e)
        return ""


def remove_student_from_roster(student_name, teacher_id=None):
    """Remove a student from ALL records: rosters, results, history, accommodations, contacts, ELL, master CSV, Supabase."""
    if not student_name:
        return {"error": "student_name is required."}

    if not teacher_id:
        try:
            from flask import g
            teacher_id = getattr(g, 'user_id', 'local-dev')
        except Exception:
            teacher_id = 'local-dev'

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

    # Remove from ALL matched roster files
    matched_name = matches[0][0]
    results = []
    errors = []
    for _name, filepath, label in matches:
        try:
            removed, remaining = _remove_student_from_csv(student_name, filepath)
            results.append({"source": label, "removed": removed, "remaining": remaining})
        except Exception as e:
            errors.append({"source": label, "error": str(e)})

    # --- Derive student ID for file-based lookups ---
    roster = _load_roster()
    matched_id = None
    for entry in roster:
        rname = entry.get("student_name", "") or entry.get("name", "")
        if _fuzzy_name_match(student_name, rname):
            matched_id = entry.get("student_id", "")
            break
    safe_id = matched_id or re.sub(r'[^\w]', '_', matched_name.lower())

    # --- Remove grading results from in-memory state + storage ---
    results_removed = 0
    try:
        from backend.app import _get_state, save_results
        grading_state = _get_state(teacher_id)
        original_count = len(grading_state.get("results", []))
        grading_state["results"] = [
            r for r in grading_state.get("results", [])
            if not _fuzzy_name_match(student_name, r.get("student_name", ""))
        ]
        results_removed = original_count - len(grading_state["results"])
        if results_removed > 0:
            save_results(grading_state["results"], teacher_id)
            results.append({"source": "grading_results", "removed": results_removed})
    except Exception as e:
        errors.append({"source": "grading_results", "error": str(e)})

    # --- Remove from master_grades.csv ---
    try:
        master_paths = [
            os.path.expanduser("~/Downloads/Graider/Results/master_grades.csv"),
            os.path.expanduser("~/.graider_data/output/master_grades.csv"),
        ]
        for master_file in master_paths:
            if not os.path.exists(master_file):
                continue
            with open(master_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                header = reader.fieldnames
                rows = list(reader)
            filtered = [row for row in rows
                        if not (_fuzzy_name_match(student_name, row.get('Student Name', ''))
                                or row.get('Student ID', '') == safe_id)]
            csv_removed = len(rows) - len(filtered)
            if csv_removed > 0:
                with open(master_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=header)
                    writer.writeheader()
                    writer.writerows(filtered)
                results.append({"source": f"master_csv ({os.path.basename(os.path.dirname(master_file))})", "removed": csv_removed})
    except Exception as e:
        errors.append({"source": "master_csv", "error": str(e)})

    # --- Delete student history file ---
    try:
        history_path = os.path.expanduser(f"~/.graider_data/student_history/{safe_id}.json")
        if os.path.exists(history_path):
            os.remove(history_path)
            results.append({"source": "student_history", "removed": 1})
    except Exception as e:
        errors.append({"source": "student_history", "error": str(e)})

    # --- Remove from accommodations ---
    try:
        accomm_file = os.path.expanduser("~/.graider_data/accommodations/student_accommodations.json")
        if os.path.exists(accomm_file):
            with open(accomm_file, 'r') as f:
                all_acc = json.load(f)
            removed_keys = [k for k in list(all_acc.keys())
                           if k == safe_id or k == (matched_id or '')]
            if removed_keys:
                for k in removed_keys:
                    del all_acc[k]
                with open(accomm_file, 'w') as f:
                    json.dump(all_acc, f, indent=2)
                results.append({"source": "accommodations", "removed": len(removed_keys)})
    except Exception as e:
        errors.append({"source": "accommodations", "error": str(e)})

    # --- Remove from parent contacts ---
    try:
        contacts_file = os.path.expanduser("~/.graider_data/parent_contacts.json")
        if os.path.exists(contacts_file):
            with open(contacts_file, 'r') as f:
                all_contacts = json.load(f)
            removed_keys = [k for k in list(all_contacts.keys())
                           if k == safe_id or k == (matched_id or '')]
            if removed_keys:
                for k in removed_keys:
                    del all_contacts[k]
                with open(contacts_file, 'w') as f:
                    json.dump(all_contacts, f, indent=2)
                results.append({"source": "parent_contacts", "removed": len(removed_keys)})
    except Exception as e:
        errors.append({"source": "parent_contacts", "error": str(e)})

    # --- Remove from ELL data ---
    try:
        ell_file = os.path.expanduser("~/.graider_data/ell_students.json")
        if os.path.exists(ell_file):
            with open(ell_file, 'r') as f:
                all_ell = json.load(f)
            removed_keys = [k for k in list(all_ell.keys())
                           if k == safe_id or k == (matched_id or '')]
            if removed_keys:
                for k in removed_keys:
                    del all_ell[k]
                with open(ell_file, 'w') as f:
                    json.dump(all_ell, f, indent=2)
                results.append({"source": "ell_data", "removed": len(removed_keys)})
    except Exception as e:
        errors.append({"source": "ell_data", "error": str(e)})

    # --- Cascade delete from Supabase ---
    supabase_msg = _delete_student_supabase(matched_name)

    # --- Build summary ---
    sources = [r["source"] for r in results]
    total_removed = sum(r.get("removed", 0) for r in results)
    msg = f"Removed {matched_name} from {len(results)} source(s): {', '.join(sources)}. Total records removed: {total_removed}."
    if supabase_msg:
        msg += f" {supabase_msg}"
    if errors:
        msg += f" Failed on {len(errors)} source(s): {', '.join(e['source'] for e in errors)}."

    return {
        "removed": matched_name,
        "files_updated": results,
        "errors": errors if errors else None,
        "message": msg,
    }


def export_student_data(student_name):
    """Export all stored data for a student as JSON + PDF."""
    if not student_name:
        return {"error": "student_name is required."}

    # Find student in roster
    roster = _load_roster()
    matched_name = None
    matched_id = None
    matched_period = None
    matched_email = None

    for entry in roster:
        rname = entry.get("student_name", "") or entry.get("name", "")
        if _fuzzy_name_match(student_name, rname):
            matched_name = rname
            matched_id = entry.get("student_id", "")
            matched_period = entry.get("period", "")
            matched_email = entry.get("email", "")
            break

    # Also try from grades data
    if not matched_name:
        rows = _load_master_csv(period_filter='all')
        for row in rows:
            if _fuzzy_name_match(student_name, row.get("student_name", "")):
                matched_name = row.get("student_name", "")
                matched_id = row.get("student_id", "")
                matched_period = row.get("period", "")
                break

    if not matched_name:
        return {"error": f"No student found matching '{student_name}'.", "hint": "Try the full name as it appears on the roster."}

    safe_id = matched_id or re.sub(r'[^\w]', '_', matched_name.lower())

    export = {
        "export_date": datetime.now().isoformat(),
        "student_name": matched_name,
        "student_id": matched_id or "",
        "period": matched_period or "",
        "email": matched_email or "",
    }

    # Grading results (from saved results file)
    results_file = os.path.expanduser("~/.graider_results.json")
    student_results = []
    if os.path.exists(results_file):
        try:
            with open(results_file, 'r') as f:
                all_results = json.load(f)
            student_results = [r for r in all_results if _fuzzy_name_match(student_name, r.get("student_name", ""))]
        except Exception:
            pass
    export["grading_results"] = student_results

    # Student history
    history_path = os.path.expanduser(f"~/.graider_data/student_history/{safe_id}.json")
    history = None
    if os.path.exists(history_path):
        try:
            with open(history_path, 'r') as f:
                history = json.load(f)
        except Exception:
            pass
    export["student_history"] = history

    # Accommodations
    accomm_file = os.path.expanduser("~/.graider_data/accommodations/student_accommodations.json")
    student_accommodations = None
    if os.path.exists(accomm_file):
        try:
            with open(accomm_file, 'r') as f:
                all_acc = json.load(f)
            student_accommodations = all_acc.get(safe_id) or all_acc.get(matched_id or '')
        except Exception:
            pass
    export["accommodations"] = student_accommodations

    # ELL data
    ell_file = os.path.expanduser("~/.graider_data/ell_students.json")
    ell_data = None
    if os.path.exists(ell_file):
        try:
            with open(ell_file, 'r') as f:
                all_ell = json.load(f)
            ell_data = all_ell.get(safe_id) or all_ell.get(matched_id or '')
        except Exception:
            pass
    export["ell_data"] = ell_data

    # Parent contacts
    contacts_file = os.path.expanduser("~/.graider_data/parent_contacts.json")
    parent_contacts = None
    if os.path.exists(contacts_file):
        try:
            with open(contacts_file, 'r') as f:
                all_contacts = json.load(f)
            parent_contacts = all_contacts.get(safe_id) or all_contacts.get(matched_id or '')
        except Exception:
            pass
    export["parent_contacts"] = parent_contacts

    record_count = len(student_results) + (1 if history else 0) + (1 if student_accommodations else 0) + (1 if ell_data else 0) + (1 if parent_contacts else 0)

    # Save JSON
    export_dir = os.path.expanduser("~/.graider_exports/student")
    os.makedirs(export_dir, exist_ok=True)
    date_str = datetime.now().strftime('%Y-%m-%d')
    safe_fname = re.sub(r'[^\w\s-]', '', matched_name).strip().replace(' ', '_')
    json_path = os.path.join(export_dir, f"{safe_fname}_data_{date_str}.json")
    with open(json_path, 'w') as f:
        json.dump(export, f, indent=2, default=str)

    # Generate PDF
    pdf_path = os.path.join(export_dir, f"{safe_fname}_report_{date_str}.pdf")
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors as rl_colors

        doc = SimpleDocTemplate(pdf_path, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('ExTitle', parent=styles['Title'], fontSize=18, spaceAfter=6)
        subtitle_style = ParagraphStyle('ExSub', parent=styles['Normal'], fontSize=10, textColor=rl_colors.grey, spaceAfter=12)
        section_style = ParagraphStyle('ExSec', parent=styles['Heading2'], fontSize=13, spaceBefore=16, spaceAfter=6)
        body_style = ParagraphStyle('ExBody', parent=styles['Normal'], fontSize=9, leading=12)

        elements = []
        elements.append(Paragraph(f"Student Data Report: {matched_name}", title_style))
        header_parts = [f"Exported {date_str}"]
        if matched_id:
            header_parts.append(f"ID: {matched_id}")
        if matched_period:
            header_parts.append(f"Period: {matched_period}")
        elements.append(Paragraph(" | ".join(header_parts), subtitle_style))
        elements.append(Spacer(1, 12))

        if student_results:
            elements.append(Paragraph("Assignment Scores", section_style))
            table_data = [["Date", "Assignment", "Score", "Grade"]]
            for r in sorted(student_results, key=lambda x: x.get('graded_at', '')):
                table_data.append([
                    (r.get('graded_at') or '')[:10],
                    (r.get('assignment') or r.get('filename', ''))[:40],
                    str(r.get('score', '')),
                    r.get('letter_grade', ''),
                ])
            t = Table(table_data, colWidths=[1*inch, 3.5*inch, 0.8*inch, 0.7*inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), rl_colors.HexColor('#4f46e5')),
                ('TEXTCOLOR', (0, 0), (-1, 0), rl_colors.white),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, rl_colors.lightgrey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [rl_colors.white, rl_colors.HexColor('#f5f5f5')]),
            ]))
            elements.append(t)

        if history and history.get('skill_scores'):
            elements.append(Paragraph("Skill Patterns", section_style))
            for skill, val in history['skill_scores'].items():
                avg = val if isinstance(val, (int, float)) else val.get('average', 'N/A') if isinstance(val, dict) else 'N/A'
                elements.append(Paragraph(f"<b>{skill.replace('_', ' ').title()}:</b> {avg}", body_style))

        if student_accommodations:
            elements.append(Paragraph("Accommodations (IEP/504)", section_style))
            presets = student_accommodations.get('presets', [])
            if presets:
                elements.append(Paragraph("Presets: " + ", ".join(p.replace('_', ' ').title() for p in presets), body_style))
            notes = student_accommodations.get('custom_notes') or student_accommodations.get('notes', '')
            if notes:
                elements.append(Paragraph(f"Notes: {notes}", body_style))

        if ell_data:
            elements.append(Paragraph("ELL Information", section_style))
            lang = ell_data.get('language', '') if isinstance(ell_data, dict) else str(ell_data)
            elements.append(Paragraph(f"Language: {lang}", body_style))

        feedback_results = [r for r in student_results if r.get('feedback')]
        if feedback_results:
            elements.append(Paragraph("Recent Feedback", section_style))
            for r in feedback_results[-3:]:
                assign = r.get('assignment') or r.get('filename', '')
                fb = r.get('feedback', '')[:500]
                elements.append(Paragraph(f"<b>{assign}:</b>", body_style))
                elements.append(Paragraph(fb, body_style))
                elements.append(Spacer(1, 6))

        doc.build(elements)
    except Exception as e:
        pdf_path = None

    # Open folder (macOS local dev only)
    if sys.platform == 'darwin':
        try:
            subprocess.run(['open', export_dir], check=False)
        except Exception:
            pass

    return {
        "status": "success",
        "student_name": matched_name,
        "student_id": matched_id or "",
        "record_count": record_count,
        "json_path": json_path,
        "pdf_path": pdf_path,
        "message": f"Exported {record_count} records for {matched_name}. Files saved to {export_dir}",
    }


def import_student_data(file_path, period=None, student_id=None):
    """Import a previously exported student data file into Graider."""
    if not file_path:
        return {"error": "file_path is required."}

    file_path = os.path.expanduser(file_path)
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}

    if not file_path.endswith('.json'):
        return {"error": "File must be a .json file."}

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return {"error": f"Invalid JSON file: {e}"}

    student_name = data.get("student_name")
    if not student_name:
        return {"error": "Missing 'student_name' in export file. This may not be a Graider export."}

    has_data = any(data.get(k) for k in ('grading_results', 'student_history', 'accommodations', 'ell_data', 'parent_contacts'))
    if not has_data:
        return {"error": "Export file contains no importable data sections."}

    original_id = data.get("student_id", "")
    sid = student_id or original_id or re.sub(r'[^\w]', '_', student_name.lower())

    imported = {"results": 0, "history": False, "accommodations": False, "ell": False, "contacts": False}

    # 1. Grading results — append to saved results file, deduplicate by graded_at
    grading_results = data.get("grading_results") or []
    if grading_results:
        results_file = os.path.expanduser("~/.graider_results.json")
        all_results = []
        if os.path.exists(results_file):
            try:
                with open(results_file, 'r') as f:
                    all_results = json.load(f)
            except Exception:
                pass

        existing_timestamps = set()
        for r in all_results:
            if r.get("student_name", "").lower() == student_name.lower() and r.get("graded_at"):
                existing_timestamps.add(r["graded_at"])

        new_results = []
        for r in grading_results:
            if student_id:
                r["student_id"] = student_id
            if r.get("graded_at") and r["graded_at"] in existing_timestamps:
                continue
            new_results.append(r)

        if new_results:
            all_results.extend(new_results)
            try:
                with open(results_file, 'w') as f:
                    json.dump(all_results, f, indent=2)
            except Exception as e:
                return {"error": f"Failed to save results: {e}"}
            imported["results"] = len(new_results)

    # 2. Student history — merge
    student_history = data.get("student_history")
    if student_history:
        history_dir = os.path.expanduser("~/.graider_data/student_history")
        os.makedirs(history_dir, exist_ok=True)
        safe_sid = re.sub(r'[^\w]', '_', sid.lower())
        history_path = os.path.join(history_dir, f"{safe_sid}.json")

        existing_history = None
        if os.path.exists(history_path):
            try:
                with open(history_path, 'r') as f:
                    existing_history = json.load(f)
            except Exception:
                pass

        if existing_history and existing_history.get("assignments"):
            existing_keys = set()
            for a in existing_history.get("assignments", []):
                existing_keys.add((a.get("date", ""), a.get("assignment", "")))
            for a in student_history.get("assignments", []):
                key = (a.get("date", ""), a.get("assignment", ""))
                if key not in existing_keys:
                    existing_history["assignments"].append(a)
            for skill, val in student_history.get("skill_scores", {}).items():
                if skill not in existing_history.get("skill_scores", {}):
                    existing_history.setdefault("skill_scores", {})[skill] = val
            existing_history["last_updated"] = datetime.now().isoformat()
            with open(history_path, 'w') as f:
                json.dump(existing_history, f, indent=2)
        else:
            student_history["student_id"] = sid
            student_history["last_updated"] = datetime.now().isoformat()
            with open(history_path, 'w') as f:
                json.dump(student_history, f, indent=2)
        imported["history"] = True

    # 3. Accommodations
    accommodations = data.get("accommodations")
    if accommodations:
        accomm_file = os.path.expanduser("~/.graider_data/accommodations/student_accommodations.json")
        os.makedirs(os.path.dirname(accomm_file), exist_ok=True)
        all_acc = {}
        if os.path.exists(accomm_file):
            try:
                with open(accomm_file, 'r') as f:
                    all_acc = json.load(f)
            except Exception:
                pass
        all_acc[sid] = accommodations
        all_acc[sid]["updated"] = datetime.now().isoformat()
        with open(accomm_file, 'w') as f:
            json.dump(all_acc, f, indent=2)
        imported["accommodations"] = True

    # 4. ELL data
    ell_data = data.get("ell_data")
    if ell_data:
        ell_file = os.path.expanduser("~/.graider_data/ell_students.json")
        os.makedirs(os.path.dirname(ell_file), exist_ok=True)
        all_ell = {}
        if os.path.exists(ell_file):
            try:
                with open(ell_file, 'r') as f:
                    all_ell = json.load(f)
            except Exception:
                pass
        all_ell[sid] = ell_data
        with open(ell_file, 'w') as f:
            json.dump(all_ell, f, indent=2)
        imported["ell"] = True

    # 5. Parent contacts
    parent_contacts = data.get("parent_contacts")
    if parent_contacts:
        contacts_file = os.path.expanduser("~/.graider_data/parent_contacts.json")
        os.makedirs(os.path.dirname(contacts_file), exist_ok=True)
        all_contacts = {}
        if os.path.exists(contacts_file):
            try:
                with open(contacts_file, 'r') as f:
                    all_contacts = json.load(f)
            except Exception:
                pass
        all_contacts[sid] = parent_contacts
        with open(contacts_file, 'w') as f:
            json.dump(all_contacts, f, indent=2)
        imported["contacts"] = True

    # 6. Add to period roster if specified
    if period:
        try:
            csv_path = os.path.join(PERIODS_DIR, period)
            if os.path.exists(csv_path):
                existing_names = set()
                with open(csv_path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames or []
                    rows = list(reader)
                    for row in rows:
                        existing_names.add(row.get("student_name", "").lower())
                if student_name.lower() not in existing_names:
                    new_row = {"student_name": student_name}
                    if "student_id" in fieldnames:
                        new_row["student_id"] = sid
                    if "email" in fieldnames:
                        new_row["email"] = data.get("email", "")
                    rows.append(new_row)
                    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)
        except Exception as e:
            print(f"Warning: Could not add student to roster: {e}")

    total = imported["results"] + sum(1 for v in [imported["history"], imported["accommodations"], imported["ell"], imported["contacts"]] if v)
    return {
        "status": "success",
        "student_name": student_name,
        "student_id": sid,
        "imported_sections": imported,
        "message": f"Imported {total} data sections for {student_name}.",
    }


# ═══════════════════════════════════════════════════════
# HANDLER MAP
# ═══════════════════════════════════════════════════════

STUDENT_TOOL_HANDLERS = {
    "get_student_accommodations": get_student_accommodations,
    "get_student_streak": get_student_streak,
    "remove_student_from_roster": remove_student_from_roster,
    "export_student_data": export_student_data,
    "import_student_data": import_student_data,
}
