"""FERPA data-operations API routes for Graider.

Tier 2 Slice 3 PR2: verbatim extraction of the FERPA compliance
data-operations route cluster out of the app module: six routes
(``/api/ferpa/delete-all-data``, ``/api/ferpa/audit-log``,
``/api/ferpa/data-summary``, ``/api/ferpa/export-data``,
``/api/ferpa/export-student``, ``/api/ferpa/import-student``) plus the
cluster-internal ``get_audit_logs`` reader helper (its sole production
caller is the ferpa audit-log route).

This is a pure relocation with ZERO behavior change. Route bodies and the
full stacked decorator order are byte-identical to the pre-move app-module
code; the ONLY change is the decorator token ``@app.route`` ->
``@ferpa_bp.route``. ``get_audit_logs`` is byte-identical too, except its
``AUDIT_LOG_FILE`` now resolves via the canonical ``backend.utils.audit``
import (the pre-move app.py copy was byte-equal:
``os.path.expanduser("~/.graider_audit.log")``), so its logic bytes are
otherwise unchanged.

Import discipline: this module imports every symbol the moved bodies
reference that pre-move ``backend/app.py`` resolved in its namespace (os,
sys, csv, json, datetime, flask request/jsonify/g, the auth/error
decorators, audit_log, AUDIT_LOG_FILE, _get_state, sentry_sdk, a
module-local logger, plus the student-history helpers
``load_student_history`` / ``save_student_history`` and the accommodations
helpers ``load_student_accommodations`` / ``save_student_accommodations``).
Pre-move ``app.py`` bound ``audit_log`` directly
(``from backend.utils.audit import audit_log``) and bound the
history/accommodations helpers via nested try/except ImportError fallbacks;
this module replicates that resolution exactly (audit_log direct; the four
helpers via the same nested try/except ImportError fallbacks, importing only
the FERPA-used subset and copying app.py's fallback bodies verbatim for
exactly those names) so the namespace is equivalent and the move introduces
no behavior change. The ``RESULTS_FILE`` / ``SETTINGS_FILE`` constants were
FERPA-cluster-only app.py-local constants with no canonical home; they are
co-moved here byte-identically (see SPEC REFINEMENT note below).

``save_results`` is intentionally left unimported because pre-move
``app.py`` never bound it either (no import or def site, only a usage ref at
the line that becomes ``import_individual_student_data``'s grading-results
save). Its pre-existing NameError -> ``@handle_route_errors`` 500 is
faithfully preserved by this verbatim move (issue #423; fixing it is a
behavior change requiring its own characterization PR, out of scope for this
verbatim relocation). ``re`` / ``subprocess`` are imported inside the bodies
(unchanged) and need no module-level import. This module must never import
the app module (no cycle).

SPEC REFINEMENT (recorded for the PR3 slice closeout): the slice spec
explicitly named only ``AUDIT_LOG_FILE`` for canonical-import + dead-constant
removal. ``RESULTS_FILE`` and ``SETTINGS_FILE`` need the identical mechanical
pattern (they are FERPA-cluster-only app.py-local constants with no canonical
home): co-moved here byte-identically, and the now-dead app.py copies
removed once the grep gate confirms zero remaining uses. The coarser
pre-scan in the spec did not enumerate them; the plan anticipates
implementation-time re-derivation with the grep gate as authoritative.
"""
import csv
import json
import logging
import os
import sys
from datetime import datetime

import sentry_sdk
from flask import Blueprint, g, jsonify, request

from backend.grading.state import _get_state
from backend.utils.audit import AUDIT_LOG_FILE, audit_log
from backend.utils.auth_decorators import require_teacher
from backend.utils.errors import handle_route_errors

# Student-history helpers: replicate pre-move app.py's nested try/except
# ImportError resolution exactly, importing only the FERPA-used subset and
# copying app.py's fallback bodies verbatim for exactly those names.
try:
    from backend.student_history import load_student_history, save_student_history
except ImportError:
    try:
        from student_history import load_student_history, save_student_history
    except ImportError:
        # Fallback if module not available
        def load_student_history(student_id):
            return None
        def save_student_history(student_id, history):
            pass

# Accommodation helpers: same nested try/except ImportError resolution as
# pre-move app.py, FERPA-used subset only, fallback bodies verbatim.
try:
    from backend.accommodations import load_student_accommodations, save_student_accommodations
except ImportError:
    try:
        from accommodations import load_student_accommodations, save_student_accommodations
    except ImportError:
        # Fallback if module not available
        def load_student_accommodations():
            return {}
        def save_student_accommodations(mappings):
            return False

ferpa_bp = Blueprint('ferpa', __name__)
_logger = logging.getLogger(__name__)

# FERPA-cluster-only app.py-local constants, co-moved byte-identically (see
# the module-docstring SPEC REFINEMENT note). AUDIT_LOG_FILE is the canonical
# backend.utils.audit value (byte-equal to the removed app.py copy).
RESULTS_FILE = os.path.expanduser("~/.graider_results.json")
SETTINGS_FILE = os.path.expanduser("~/.graider_settings.json")


def get_audit_logs(limit: int = 100):
    """Retrieve recent audit log entries."""
    if not os.path.exists(AUDIT_LOG_FILE):
        return []

    try:
        with open(AUDIT_LOG_FILE, 'r') as f:
            lines = f.readlines()
            # Return last N entries
            recent = lines[-limit:] if len(lines) > limit else lines
            logs = []
            for line in recent:
                parts = line.strip().split(' | ')
                if len(parts) >= 4:
                    entry = {
                        'timestamp': parts[0],
                        'user': parts[1],
                        'action': parts[2],
                        'details': parts[3] if len(parts) > 3 else ''
                    }
                    # 5th field (added 2026-05-06 PR #214) carries
                    # `teacher=<id>` for new entries; absent on legacy lines.
                    if len(parts) >= 5 and parts[4].startswith('teacher='):
                        entry['teacher_id'] = parts[4][len('teacher='):]
                    logs.append(entry)
            return logs[::-1]  # Newest first
    except Exception as e:
        _logger.error("Error reading audit logs: %s", e)
        sentry_sdk.capture_exception(e)
        return []


@ferpa_bp.route('/api/ferpa/delete-all-data', methods=['POST'])
@require_teacher
@handle_route_errors
def delete_all_student_data():
    """
    FERPA Compliance: Securely delete all student data.
    This includes grading results, settings, and cached data.
    """
    teacher_id = getattr(g, 'user_id', 'local-dev')
    grading_state = _get_state(teacher_id)

    if grading_state["is_running"]:
        return jsonify({"error": "Cannot delete data while grading is in progress"}), 400

    data = request.json or {}
    confirm = data.get('confirm', False)

    if not confirm:
        return jsonify({
            "error": "Confirmation required",
            "message": "Send {confirm: true} to proceed with deletion"
        }), 400

    deleted_items = []

    try:
        # Delete grading results
        if os.path.exists(RESULTS_FILE):
            result_count = len(grading_state.get("results", []))
            os.remove(RESULTS_FILE)
            deleted_items.append(f"Grading results ({result_count} records)")

        # Clear in-memory results
        grading_state["results"] = []
        grading_state["log"] = []
        grading_state["progress"] = 0
        grading_state["total"] = 0
        grading_state["complete"] = False

        # Delete settings (optional - based on request)
        if data.get('include_settings', False) and os.path.exists(SETTINGS_FILE):
            os.remove(SETTINGS_FILE)
            deleted_items.append("Settings")

        # Audit log the deletion (this is kept for compliance)
        audit_log("DELETE_ALL_DATA", f"Deleted: {', '.join(deleted_items)}")

        return jsonify({
            "status": "success",
            "message": "All student data has been securely deleted",
            "deleted": deleted_items,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        _logger.exception("Failed to delete all student data")
        audit_log("DELETE_ALL_DATA_ERROR", "internal error")
        return jsonify({"error": "An internal error occurred"}), 500


@ferpa_bp.route('/api/ferpa/audit-log', methods=['GET'])
@require_teacher
@handle_route_errors
def get_audit_log():
    """
    FERPA Compliance: Retrieve audit log entries.
    Shows who accessed what data and when.
    """
    limit = request.args.get('limit', 100, type=int)
    logs = get_audit_logs(limit)

    return jsonify({
        "logs": logs,
        "total": len(logs),
        "file": AUDIT_LOG_FILE
    })


@ferpa_bp.route('/api/ferpa/data-summary', methods=['GET'])
@require_teacher
@handle_route_errors
def get_data_summary():
    """
    FERPA Compliance: Get summary of stored student data.
    Helps teachers understand what data is stored locally.
    """
    teacher_id = getattr(g, 'user_id', 'local-dev')
    grading_state = _get_state(teacher_id)
    summary = {
        "results": {
            "count": len(grading_state.get("results", [])),
            "file": RESULTS_FILE,
            "exists": os.path.exists(RESULTS_FILE)
        },
        "settings": {
            "file": SETTINGS_FILE,
            "exists": os.path.exists(SETTINGS_FILE)
        },
        "audit_log": {
            "file": AUDIT_LOG_FILE,
            "exists": os.path.exists(AUDIT_LOG_FILE)
        },
        "data_locations": [
            "~/.graider_results.json - Grading results",
            "~/.graider_settings.json - App settings",
            "~/.graider_audit.log - Audit trail",
            "Output folder (configured in settings) - Exported grades"
        ],
        "ferpa_notes": {
            "pii_handling": "Student names are sanitized before AI processing",
            "data_storage": "All data stored locally on teacher's computer",
            "ai_training": "OpenAI API does not train on API-submitted data",
            "deletion": "Use DELETE /api/ferpa/delete-all-data to remove all data"
        }
    }

    # Audit log access to data summary
    audit_log("VIEW_DATA_SUMMARY", "Teacher viewed data storage summary")

    return jsonify(summary)


@ferpa_bp.route('/api/ferpa/export-data', methods=['GET'])
@require_teacher
@handle_route_errors
def export_student_data():
    """
    FERPA Compliance: Export all student data for portability.
    Supports parent/guardian data requests.
    """
    teacher_id = getattr(g, 'user_id', 'local-dev')
    grading_state = _get_state(teacher_id)
    student_name = request.args.get('student', '')

    if student_name:
        # Export specific student's data
        student_results = [
            r for r in grading_state.get("results", [])
            if r.get("student_name", "").lower() == student_name.lower()
        ]
        audit_log("EXPORT_STUDENT_DATA", f"Exported data for student (name redacted)")
    else:
        # Export all data
        student_results = grading_state.get("results", [])
        audit_log("EXPORT_ALL_DATA", f"Exported all {len(student_results)} records")

    return jsonify({
        "export_date": datetime.now().isoformat(),
        "record_count": len(student_results),
        "data": student_results
    })


@ferpa_bp.route('/api/ferpa/export-student', methods=['POST'])
@require_teacher
@handle_route_errors
def export_individual_student_data():
    """
    FERPA Compliance: Export all stored data for a specific student.
    Generates JSON (raw data) + PDF (formatted report) saved to ~/.graider_exports/student/.
    """
    import re
    import subprocess

    teacher_id = getattr(g, 'user_id', 'local-dev')
    grading_state = _get_state(teacher_id)

    data = request.json or {}
    student_name = data.get('student_name', '').strip()
    if not student_name:
        return jsonify({"error": "student_name is required"}), 400

    # --- fuzzy match helper (inline, mirrors assistant_tools) ---
    def _fuzzy(search, full_name):
        clean = lambda s: re.sub(r'[,;.\'"]+', ' ', s.lower()).split()
        sw = clean(search)
        nw = clean(full_name)
        if not sw:
            return False
        return all(any(n.startswith(s) or s.startswith(n) for n in nw) for s in sw)

    # --- locate student across roster CSVs ---
    periods_dir = os.path.expanduser("~/.graider_data/periods")
    matched_name = None
    matched_id = None
    matched_period = None
    matched_email = None

    if os.path.isdir(periods_dir):
        for fname in sorted(os.listdir(periods_dir)):
            if not fname.endswith('.csv'):
                continue
            meta_path = os.path.join(periods_dir, fname + '.meta.json')
            period_label = fname.replace('.csv', '').replace('_', ' ')
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r') as mf:
                        meta = json.load(mf)
                    period_label = meta.get('period_name', period_label)
                except Exception:
                    _logger.warning("period metadata read failed", exc_info=True)
            try:
                with open(os.path.join(periods_dir, fname), 'r', encoding='utf-8') as pf:
                    reader = csv.DictReader(pf)
                    for row in reader:
                        raw = row.get('Student', '').strip().strip('"')
                        # Parse "Last; First" or "Last, First"
                        display = raw
                        if '; ' in raw:
                            parts = raw.split('; ', 1)
                            display = (parts[1].strip() + ' ' + parts[0].strip()).strip()
                        elif ', ' in raw:
                            parts = raw.split(', ', 1)
                            display = (parts[1].strip() + ' ' + parts[0].strip()).strip()
                        if _fuzzy(student_name, display) or _fuzzy(student_name, raw):
                            matched_name = display
                            matched_id = row.get('Student ID', row.get('student_id', row.get('ID', '')))
                            matched_email = row.get('Email', row.get('email', ''))
                            matched_period = period_label
                            break
            except Exception:
                _logger.warning("period roster scan failed", exc_info=True)
                continue
            if matched_name:
                break

    # Also try matching from grading results if roster didn't match
    if not matched_name:
        for r in grading_state.get("results", []):
            rn = r.get("student_name", "")
            if _fuzzy(student_name, rn):
                matched_name = rn
                matched_id = r.get("student_id", "")
                matched_period = r.get("period", "")
                matched_email = r.get("student_email", "")
                break

    if not matched_name:
        return jsonify({
            "error": f"No student found matching '{student_name}'.",
            "hint": "Try the student's full name as it appears on the roster."
        }), 404

    safe_id = matched_id or re.sub(r'[^\w]', '_', matched_name.lower())

    # --- collect data from all sources ---
    export = {
        "export_date": datetime.now().isoformat(),
        "student_name": matched_name,
        "student_id": matched_id or "",
        "period": matched_period or "",
        "email": matched_email or "",
    }

    # 1. Grading results
    student_results = [
        r for r in grading_state.get("results", [])
        if _fuzzy(student_name, r.get("student_name", ""))
    ]
    export["grading_results"] = student_results

    # 2. Student history
    history = load_student_history(safe_id) if safe_id else None
    export["student_history"] = history

    # 3. Accommodations
    accomm_file = os.path.expanduser("~/.graider_data/accommodations/student_accommodations.json")
    student_accommodations = None
    if os.path.exists(accomm_file):
        try:
            with open(accomm_file, 'r') as f:
                all_acc = json.load(f)
            student_accommodations = all_acc.get(safe_id) or all_acc.get(matched_id or '')
        except Exception as e:
            sentry_sdk.capture_exception(e)
    export["accommodations"] = student_accommodations

    # 4. ELL data
    ell_file = os.path.expanduser("~/.graider_data/ell_students.json")
    ell_data = None
    if os.path.exists(ell_file):
        try:
            with open(ell_file, 'r') as f:
                all_ell = json.load(f)
            ell_data = all_ell.get(safe_id) or all_ell.get(matched_id or '')
        except Exception as e:
            sentry_sdk.capture_exception(e)
    export["ell_data"] = ell_data

    # 5. Parent contacts
    contacts_file = os.path.expanduser("~/.graider_data/parent_contacts.json")
    parent_contacts = None
    if os.path.exists(contacts_file):
        try:
            with open(contacts_file, 'r') as f:
                all_contacts = json.load(f)
            parent_contacts = all_contacts.get(safe_id) or all_contacts.get(matched_id or '')
        except Exception as e:
            sentry_sdk.capture_exception(e)
    export["parent_contacts"] = parent_contacts

    record_count = len(student_results) + (1 if history else 0) + (1 if student_accommodations else 0) + (1 if ell_data else 0) + (1 if parent_contacts else 0)

    # --- save JSON ---
    export_dir = os.path.expanduser("~/.graider_exports/student")
    os.makedirs(export_dir, exist_ok=True)
    date_str = datetime.now().strftime('%Y-%m-%d')
    safe_fname = re.sub(r'[^\w\s-]', '', matched_name).strip().replace(' ', '_')
    json_path = os.path.join(export_dir, f"{safe_fname}_data_{date_str}.json")
    with open(json_path, 'w') as f:
        json.dump(export, f, indent=2, default=str)

    # --- generate PDF ---
    pdf_path = os.path.join(export_dir, f"{safe_fname}_report_{date_str}.pdf")
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors as rl_colors

        doc = SimpleDocTemplate(pdf_path, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('ExportTitle', parent=styles['Title'], fontSize=18, spaceAfter=6)
        subtitle_style = ParagraphStyle('ExportSub', parent=styles['Normal'], fontSize=10, textColor=rl_colors.grey, spaceAfter=12)
        section_style = ParagraphStyle('ExportSection', parent=styles['Heading2'], fontSize=13, spaceBefore=16, spaceAfter=6)
        body_style = ParagraphStyle('ExportBody', parent=styles['Normal'], fontSize=9, leading=12)

        elements = []

        # Header
        elements.append(Paragraph(f"Student Data Report: {matched_name}", title_style))
        header_parts = [f"Exported {date_str}"]
        if matched_id:
            header_parts.append(f"ID: {matched_id}")
        if matched_period:
            header_parts.append(f"Period: {matched_period}")
        elements.append(Paragraph(" | ".join(header_parts), subtitle_style))
        elements.append(Spacer(1, 12))

        # Scores table
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

        # Skill patterns (from history)
        if history and history.get('skill_scores'):
            elements.append(Paragraph("Skill Patterns", section_style))
            skills = history['skill_scores']
            for skill, val in skills.items():
                avg = val if isinstance(val, (int, float)) else val.get('average', 'N/A') if isinstance(val, dict) else 'N/A'
                elements.append(Paragraph(f"<b>{skill.replace('_', ' ').title()}:</b> {avg}", body_style))

        # Accommodations
        if student_accommodations:
            elements.append(Paragraph("Accommodations (IEP/504)", section_style))
            presets = student_accommodations.get('presets', [])
            if presets:
                elements.append(Paragraph("Presets: " + ", ".join(p.replace('_', ' ').title() for p in presets), body_style))
            notes = student_accommodations.get('custom_notes') or student_accommodations.get('notes', '')
            if notes:
                elements.append(Paragraph(f"Notes: {notes}", body_style))

        # ELL
        if ell_data:
            elements.append(Paragraph("ELL Information", section_style))
            lang = ell_data.get('language', '') if isinstance(ell_data, dict) else str(ell_data)
            elements.append(Paragraph(f"Language: {lang}", body_style))

        # Recent feedback (last 3)
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
        sentry_sdk.capture_exception(e)
        _logger.error("PDF generation error: %s", e)

    # Open folder (macOS local dev only)
    if sys.platform == 'darwin':
        try:
            subprocess.run(['open', export_dir], check=False)
        except Exception:
            _logger.warning("export folder open (local dev) failed", exc_info=True)

    audit_log("EXPORT_STUDENT_DATA", f"Exported full data for student (name redacted), {record_count} records")

    return jsonify({
        "status": "success",
        "student_name": matched_name,
        "student_id": matched_id or "",
        "record_count": record_count,
        "json_path": json_path,
        "pdf_path": pdf_path,
    })


@ferpa_bp.route('/api/ferpa/import-student', methods=['POST'])
@require_teacher
@handle_route_errors
def import_individual_student_data():
    """FERPA-compliant: Import a previously exported student data file."""
    import re as _re

    teacher_id = getattr(g, 'user_id', 'local-dev')
    grading_state = _get_state(teacher_id)

    preview = request.form.get('preview', 'false').lower() == 'true'
    period_filename = request.form.get('period_filename', '')
    student_id_override = request.form.get('student_id', '')

    # Get uploaded file
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    if not file.filename or not file.filename.endswith('.json'):
        return jsonify({"error": "File must be a .json file"}), 400

    try:
        data = json.loads(file.read().decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        _logger.exception("Invalid JSON file uploaded")
        return jsonify({"error": "Invalid JSON file"}), 400

    # Validate required fields
    student_name = data.get('student_name')
    if not student_name:
        return jsonify({"error": "Missing 'student_name' in export file. This may not be a Graider export."}), 400

    has_data = any(data.get(k) for k in ('grading_results', 'student_history', 'accommodations', 'ell_data', 'parent_contacts'))
    if not has_data:
        return jsonify({"error": "Export file contains no importable data sections."}), 400

    original_id = data.get('student_id', '')
    original_period = data.get('period', '')
    student_id = student_id_override or original_id or _re.sub(r'[^\w]', '_', student_name.lower())

    grading_results = data.get('grading_results') or []
    student_history = data.get('student_history')
    accommodations = data.get('accommodations')
    ell_data = data.get('ell_data')
    parent_contacts = data.get('parent_contacts')

    # Build preview summary
    summary = {
        "student_name": student_name,
        "original_period": original_period,
        "original_id": original_id,
        "sections": {
            "results": len(grading_results),
            "history": bool(student_history),
            "accommodations": bool(accommodations),
            "ell": bool(ell_data),
            "contacts": bool(parent_contacts),
        },
    }

    # Add human-readable details for preview
    details = []
    if grading_results:
        details.append(f"{len(grading_results)} grades")
    if student_history:
        details.append("history")
    if accommodations:
        presets = accommodations.get('presets', [])
        if presets:
            details.append(f"IEP accommodations ({', '.join(p.replace('_', ' ') for p in presets[:3])})")
        else:
            details.append("accommodations")
    if ell_data:
        lang = ell_data.get('language', '') if isinstance(ell_data, dict) else str(ell_data)
        details.append(f"ELL ({lang})" if lang and lang != 'none' else "ELL")
    if parent_contacts:
        details.append("parent contacts")
    summary["detail_text"] = ", ".join(details) if details else "no data"

    if preview:
        return jsonify({"status": "preview", **summary})

    # ── Import mode ──────────────────────────────────────────
    imported = {"results": 0, "history": False, "accommodations": False, "ell": False, "contacts": False}

    # 1. Grading results — append, deduplicate by graded_at timestamp
    if grading_results:
        existing_timestamps = set()
        for r in grading_state.get("results", []):
            ts = r.get("graded_at", "")
            nm = r.get("student_name", "")
            if nm.lower() == student_name.lower() and ts:
                existing_timestamps.add(ts)

        new_results = []
        for r in grading_results:
            # Update period/ID if overrides provided
            if student_id_override:
                r["student_id"] = student_id_override
            if period_filename:
                r["period"] = period_filename.replace('.csv', '').replace('_', ' ')
            # Deduplicate by timestamp
            if r.get("graded_at") and r["graded_at"] in existing_timestamps:
                continue
            new_results.append(r)

        if new_results:
            grading_state["results"].extend(new_results)
            save_results(grading_state["results"], teacher_id)
            imported["results"] = len(new_results)

    # 2. Student history — merge assignments lists
    if student_history:
        existing_history = load_student_history(student_id)
        if existing_history and existing_history.get("assignments"):
            # Merge: add assignments not already present (by date + assignment name)
            existing_keys = set()
            for a in existing_history.get("assignments", []):
                existing_keys.add((a.get("date", ""), a.get("assignment", "")))
            for a in student_history.get("assignments", []):
                key = (a.get("date", ""), a.get("assignment", ""))
                if key not in existing_keys:
                    existing_history["assignments"].append(a)
            # Merge skill_scores — keep existing, add new
            for skill, val in student_history.get("skill_scores", {}).items():
                if skill not in existing_history.get("skill_scores", {}):
                    existing_history.setdefault("skill_scores", {})[skill] = val
            save_student_history(student_id, existing_history)
        else:
            # No existing history — save the imported one with updated ID
            student_history["student_id"] = student_id
            save_student_history(student_id, student_history)
        imported["history"] = True

    # 3. Accommodations
    if accommodations:
        tid = getattr(g, 'user_id', 'local-dev')
        all_acc = load_student_accommodations(tid)
        all_acc[student_id] = accommodations
        all_acc[student_id]["updated"] = datetime.now().isoformat()
        save_student_accommodations(all_acc, tid)
        imported["accommodations"] = True

    # 4. ELL data
    if ell_data:
        ell_file = os.path.expanduser("~/.graider_data/ell_students.json")
        all_ell = {}
        if os.path.exists(ell_file):
            try:
                with open(ell_file, 'r') as f:
                    all_ell = json.load(f)
            except Exception as e:
                sentry_sdk.capture_exception(e)
        all_ell[student_id] = ell_data
        os.makedirs(os.path.dirname(ell_file), exist_ok=True)
        with open(ell_file, 'w') as f:
            json.dump(all_ell, f, indent=2)
        imported["ell"] = True

    # 5. Parent contacts
    if parent_contacts:
        contacts_file = os.path.expanduser("~/.graider_data/parent_contacts.json")
        all_contacts = {}
        if os.path.exists(contacts_file):
            try:
                with open(contacts_file, 'r') as f:
                    all_contacts = json.load(f)
            except Exception as e:
                sentry_sdk.capture_exception(e)
        all_contacts[student_id] = parent_contacts
        os.makedirs(os.path.dirname(contacts_file), exist_ok=True)
        with open(contacts_file, 'w') as f:
            json.dump(all_contacts, f, indent=2)
        imported["contacts"] = True

    # 6. Roster — add student to period CSV if specified
    if period_filename:
        try:
            periods_dir = os.path.expanduser("~/.graider_data/periods")
            csv_path = os.path.join(periods_dir, period_filename)
            if os.path.exists(csv_path):
                # Read existing rows to avoid duplicate
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
                        new_row["student_id"] = student_id
                    if "email" in fieldnames:
                        new_row["email"] = data.get("email", "")
                    rows.append(new_row)
                    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)
        except Exception as e:
            _logger.warning("Could not add student to roster: %s", e)
            sentry_sdk.capture_exception(e)

    audit_log("IMPORT_STUDENT_DATA", f"Imported data for student (name redacted), sections: {imported}")

    return jsonify({
        "status": "success",
        "student_name": student_name,
        "student_id": student_id,
        "imported_sections": imported,
    })
