"""Grade export + Focus assignment creation + student-info lookup tools.

Pure-move of whole functions out of the former single-file module; bodies
are byte-identical.
"""
import os
import io
import base64
import subprocess
from collections import defaultdict

from backend.services.assistant_tools import (
    _load_results, _load_roster, _load_parent_contacts, _fuzzy_name_match,
)
from backend.utils.compliance import audit_tool_action, require_teacher_id

from ._paths import PROJECT_ROOT


def create_focus_assignment(name, category=None, points=None, date=None, description=None, teacher_id='local-dev'):
    """Launch Focus automation to create an assignment."""
    require_teacher_id(teacher_id)
    # Write per-teacher creds to temp file for subprocess access
    from backend.routes.assistant_routes import (
        write_temp_creds_file,
        _portal_credentials_file_for,
    )
    if not write_temp_creds_file(teacher_id):
        return {"error": "VPortal credentials not configured. Go to Settings > Tools to set them up."}

    script_path = os.path.join(PROJECT_ROOT, "focus-automation.js")
    if not os.path.exists(script_path):
        return {"error": "focus-automation.js not found in project root."}

    cmd = ["node", script_path, "assignment", "--name", name]
    if category:
        cmd.extend(["--category", category])
    if points:
        cmd.extend(["--points", str(points)])
    if date:
        cmd.extend(["--date", date])
    if description:
        cmd.extend(["--description", description])

    # Closes GH #245: focus-automation.js subprocess must read
    # per-teacher creds, not the legacy shared file.
    creds_path = _portal_credentials_file_for(teacher_id)
    sub_env = {**os.environ, 'GRAIDER_PORTAL_CREDS_FILE': creds_path}

    try:
        process = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=sub_env,
        )
        return {
            "status": "launched",
            "message": f"Browser automation started for '{name}'. Check your phone for 2FA approval, then review the form before saving.",
            "pid": process.pid
        }
    except FileNotFoundError:
        return {"error": "Node.js not found. Make sure Node.js is installed."}
    except Exception as e:  # noqa: BLE001  # broad catch: returns fallback
        return {"error": f"Failed to launch automation: {str(e)}"}


def export_grades_csv(assignment=None, period=None, teacher_id='local-dev'):
    """Export grades as Focus-compatible CSV (in-memory, base64-encoded)."""
    require_teacher_id(teacher_id)
    results = _load_results(teacher_id)
    if not results:
        return {"error": "No grading results to export"}

    # Filter
    filtered = results
    if assignment:
        filtered = [r for r in filtered
                    if assignment.lower() in r.get('assignment', '').lower()]
    if period:
        filtered = [r for r in filtered
                    if r.get('period', '') == period or r.get('quarter', '') == period]

    if not filtered:
        return {"error": "No results match the specified filters"}

    # Group by period
    by_period = defaultdict(list)
    for r in filtered:
        p = r.get('period', r.get('quarter', 'All'))
        by_period[p].append(r)

    safe_name = assignment or 'grades'
    safe_name = ''.join(c if c.isalnum() or c in ' -_' else '' for c in safe_name).strip().replace(' ', '_')

    exported_files = []
    total_rows = 0
    for p, items in by_period.items():
        safe_period = p.replace(' ', '_').replace('/', '-')
        filename = f"{safe_name}_{safe_period}.csv"

        # Build CSV in memory
        buf = io.StringIO()
        buf.write('Student ID,Score\n')
        matched = 0
        for r in items:
            student_id = r.get('student_id', '')
            score = r.get('score', 0)
            if student_id:
                buf.write(f"{student_id},{score}\n")
                matched += 1
            else:
                name = r.get('student_name', 'Unknown')
                buf.write(f"# {name},{score}\n")

        csv_string = buf.getvalue()

        exported_files.append({
            "file": filename,
            "period": p,
            "rows": matched,
            "csv_base64": base64.b64encode(csv_string.encode()).decode(),
        })
        total_rows += matched

    audit_tool_action(teacher_id, 'export_grades_csv', 'EXPORT')

    result = {
        "status": "exported",
        "files": exported_files,
        "total_rows": total_rows,
    }

    # Single-file convenience
    if len(exported_files) == 1:
        result["csv_base64"] = exported_files[0]["csv_base64"]
        result["filename"] = exported_files[0]["file"]

    return result


def lookup_student_info(student_name=None, student_id=None, student_ids=None, period=None, teacher_id='local-dev'):
    """Look up student roster and contact information.
    Supports batch lookup via student_ids (list of IDs)."""
    require_teacher_id(teacher_id)
    roster = _load_roster(teacher_id)
    parent_contacts = _load_parent_contacts(teacher_id)
    results_json = _load_results(teacher_id)

    # Build email lookup from grading results (student_id -> email)
    email_lookup = {}
    for r in results_json:
        sid = r.get('student_id', '')
        email = r.get('student_email', '')
        if sid and email:
            email_lookup[sid] = email

    if not roster and not parent_contacts:
        return {"error": "No student roster data found. Import from Focus SIS or upload class period CSVs in Settings."}

    # Batch lookup by student_ids list
    if student_ids and isinstance(student_ids, list):
        id_set = set(str(sid) for sid in student_ids)
        matches = [s for s in roster if s["student_id"] in id_set]
        # Also check parent contacts for IDs not found in roster
        found_ids = set(s["student_id"] for s in matches)
        for sid in id_set - found_ids:
            contact = parent_contacts.get(sid)
            if contact:
                matches.append({
                    "name": contact.get("student_name", "Unknown"),
                    "student_id": sid,
                    "local_id": "",
                    "grade": "",
                    "period": contact.get("period", ""),
                })
    else:
        # Single lookup mode
        matches = roster
        if student_id:
            matches = [s for s in matches if s["student_id"] == str(student_id)]
        if student_name:
            matches = [s for s in matches if _fuzzy_name_match(student_name, s["name"])]
        if period:
            # Normalize period input: "1" -> matches "Period 1", "Period 1" -> matches "Period 1"
            period_lower = period.lower().strip()
            matches = [s for s in matches
                       if period_lower in s["period"].lower()
                       or (period_lower.isdigit() and f"period {period_lower}" in s["period"].lower())]

        if not matches and student_id:
            # Try parent contacts as fallback (has student_id keys even without roster)
            contact = parent_contacts.get(str(student_id))
            if contact:
                matches = [{
                    "name": contact.get("student_name", "Unknown"),
                    "student_id": str(student_id),
                    "local_id": "",
                    "grade": "",
                    "period": contact.get("period", ""),
                }]

        if not matches and student_name:
            # Try parent contacts by name (fuzzy word match)
            for sid, contact in parent_contacts.items():
                if _fuzzy_name_match(student_name, contact.get("student_name", "")):
                    matches.append({
                        "name": contact.get("student_name", "Unknown"),
                        "student_id": sid,
                        "local_id": "",
                        "grade": "",
                        "period": contact.get("period", ""),
                    })

    if not matches:
        return {"error": "No students found matching the search criteria.", "searched": {
            "name": student_name, "id": student_id, "ids": student_ids, "period": period
        }}

    # Deduplicate by student_id (batch mode may have overlap)
    seen_ids = set()
    unique_matches = []
    for s in matches:
        sid = s["student_id"]
        if sid not in seen_ids:
            seen_ids.add(sid)
            unique_matches.append(s)

    # Enrich each match with contact info, email, 504 status, schedule, and course codes
    students = []
    for s in unique_matches:
        sid = s["student_id"]
        contact = parent_contacts.get(sid, {})
        student_email = email_lookup.get(sid, "")

        entry = {
            "name": s["name"],
            "student_id": sid,
            "local_id": s.get("local_id", ""),
            "grade_level": s.get("grade", ""),
            "period": s["period"],
            "course_codes": s.get("course_codes", []),
            "student_email": student_email,
            "parent_emails": contact.get("parent_emails", []),
            "parent_phones": contact.get("parent_phones", []),
            "has_504": contact.get("has_504", False),
            "contacts": contact.get("contacts", []),
            "schedule": contact.get("schedule", []),
        }
        students.append(entry)

    # Fuzzy match transparency: if the search name differs from matched name(s),
    # include both so the model/teacher can verify the right student was found.
    result = {
        "students": students,
        "total_found": len(students),
    }

    if student_name:
        result["searched_name"] = student_name
        matched_names = [s["name"] for s in students]
        result["matched_names"] = matched_names

        # Disambiguation warning: multiple students matched a single name search
        if len(students) > 1:
            result["disambiguation_required"] = True
            result["message"] = (
                f"Multiple students match '{student_name}': "
                + ", ".join(f"{s['name']} ({s['period']})" for s in students)
                + ". Specify which student you mean before proceeding."
            )
        # Fuzzy match warning: matched name differs significantly from search
        elif len(students) == 1 and student_name.lower().strip() != students[0]["name"].lower().strip():
            result["fuzzy_matched"] = True
            result["message"] = (
                f"Searched for '{student_name}', matched to '{students[0]['name']}' "
                f"in {students[0]['period']}. Verify this is the correct student."
            )

    return result
