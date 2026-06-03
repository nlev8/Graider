"""Grading-results CRUD API routes for Graider.

Tier 2 Slice 3 PR1 — verbatim extraction of the grading-results CRUD route
cluster out of the app module: four routes (``/api/grade-individual``,
``/api/delete-result``, ``/api/update-approval``,
``/api/update-approvals-bulk``) plus the two cluster-internal master_grades.csv
sync helpers (``_remove_from_master_csv``, ``_sync_approval_to_master_csv``).

This is a pure relocation with ZERO behavior change. Route bodies and the
full stacked decorator order are byte-identical to the pre-move app-module
code; the ONLY change is the decorator token ``@app.route`` ->
``@grading_results_bp.route``.

Import discipline: this module imports every symbol the moved bodies
reference that pre-move ``backend/app.py`` resolved in its namespace
(logging, os, csv, datetime, flask, the auth/error decorators, _get_state,
graider_export_dir, sentry_sdk, limiter, plus ``audit_log`` and the
student-history helpers ``add_assignment_to_history`` /
``build_history_context``). Pre-move ``app.py`` bound ``audit_log`` directly
(``from backend.utils.audit import audit_log``) and bound the student-history
helpers via a try/except ImportError fallback; this module replicates that
resolution exactly (audit_log direct; the two history helpers via the same
try/except ImportError fallback) so the namespace is equivalent and the move
introduces no behavior change. ``save_results`` and
``grade_with_parallel_detection`` are intentionally left unimported because
pre-move ``app.py`` never bound them either (no import or def site, only
usage refs), so their pre-existing NameError is faithfully preserved (a
separate documented follow-up, out of scope for this verbatim move).
``base64`` / ``re`` are imported inside the bodies (unchanged) and need no
module-level import. This module must never import the app module (no cycle).
"""
import csv
import json
import logging
import os
from datetime import datetime

import sentry_sdk
from flask import Blueprint, g, jsonify, request

from backend.extensions import limiter
from backend.grading.state import _get_state
from backend.paths import graider_export_dir
from backend.utils.audit import audit_log
from backend.utils.auth_decorators import require_teacher
from backend.utils.errors import handle_route_errors

try:
    from backend.student_history import add_assignment_to_history, build_history_context
except ImportError:  # pragma: no cover - fallback mirrors pre-move app.py
    from student_history import add_assignment_to_history, build_history_context

grading_results_bp = Blueprint('grading_results', __name__)
_logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# INDIVIDUAL FILE GRADING (for paper/handwritten assignments)
# ══════════════════════════════════════════════════════════════

@grading_results_bp.route('/api/grade-individual', methods=['POST'])
@limiter.limit("5 per minute")
@require_teacher
@handle_route_errors
def grade_individual():
    """Grade a single uploaded image file (for paper/handwritten assignments).

    Automatically uses GPT-4o for better handwriting recognition.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    student_name = request.form.get('student_name', 'Unknown Student')
    grade_level = request.form.get('grade_level', '7')
    subject = request.form.get('subject', 'Social Studies')
    output_folder = request.form.get('output_folder', '')
    global_ai_notes = request.form.get('globalAINotes', '')
    assignment_config_str = request.form.get('assignmentConfig', '')
    student_info_str = request.form.get('studentInfo', '')
    teacher_name = request.form.get('teacher_name', '')
    school_name = request.form.get('school_name', '')
    class_period = request.form.get('classPeriod', '')

    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    # Parse student info from CSV if provided
    student_info = None
    if student_info_str:
        try:
            student_info = json.loads(student_info_str)
        except Exception as e:
            _logger.debug("student info JSON parse failed: %s", type(e).__name__)

    # Parse assignment config if provided
    assignment_config = None
    if assignment_config_str:
        try:
            assignment_config = json.loads(assignment_config_str)
        except Exception:
            _logger.debug("assignment config JSON parse failed", exc_info=True)

    # Build AI notes from config
    file_ai_notes = global_ai_notes or ''
    assignment_template = ''
    file_exclude_markers = []
    if class_period:
        file_ai_notes += f"\nCLASS PERIOD BEING GRADED: {class_period}\n(Apply any period-specific grading expectations from the instructions above)\n"
    if assignment_config:
        if assignment_config.get('gradingNotes'):
            file_ai_notes = assignment_config['gradingNotes'] + '\n\n' + file_ai_notes
        # Get assignment template for question context
        imported_doc = assignment_config.get('importedDoc') or {}
        assignment_template = imported_doc.get('text', '')
        # Get exclude markers
        file_exclude_markers = assignment_config.get('excludeMarkers', [])

    try:
        import base64

        # Read file content
        file_content = file.read()
        file_ext = os.path.splitext(file.filename)[1].lower()

        # Determine media type
        media_type_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.heic': 'image/heic',
            '.heif': 'image/heif',
        }
        media_type = media_type_map.get(file_ext, 'image/jpeg')

        # Encode as base64
        base64_content = base64.b64encode(file_content).decode('utf-8')

        # Create grade data for image
        grade_data = {
            "type": "image",
            "content": base64_content,
            "media_type": media_type
        }

        # ALWAYS use GPT-4o for images (better handwriting recognition)
        ai_model = 'gpt-4o'

        # Get student ID for history tracking
        individual_student_id = student_info.get('id', '') if student_info else None

        # Build student history context (passed separately to feedback)
        history_context = ""
        if individual_student_id:
            history_context = build_history_context(individual_student_id)

        # Grade the assignment (no custom rubric for individual grading yet)
        # Pass None for marker_config and 15 for effort_points (defaults)
        grade_result = grade_with_parallel_detection(student_name, grade_data, file_ai_notes, grade_level, subject, ai_model, individual_student_id, assignment_template, None, None, file_exclude_markers, None, 15, student_history=history_context)

        if grade_result.get('letter_grade') == 'ERROR':
            return jsonify({"error": grade_result.get('feedback', 'Grading failed')}), 500

        # Save original image to output folder
        original_image_path = None
        if output_folder and os.path.exists(output_folder):
            safe_name = student_name.replace(' ', '_').replace('/', '_')
            timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Save the original image
            image_filename = f"{safe_name}_handwritten_{timestamp_str}{file_ext}"
            original_image_path = os.path.join(output_folder, image_filename)
            with open(original_image_path, 'wb') as img_file:
                img_file.write(file_content)

        # Build result object (matching regular grading structure)
        result = {
            "student_name": student_name,
            "filename": file.filename,
            "assignment": assignment_config.get('title', 'Individual Upload') if assignment_config else 'Individual Upload',
            "score": int(float(grade_result.get('score', 0) or 0)),
            "letter_grade": grade_result.get('letter_grade', 'N/A'),
            "feedback": grade_result.get('feedback', ''),
            "breakdown": grade_result.get('breakdown', {}),
            "ai_detection": grade_result.get('ai_detection', {}),
            "plagiarism_detection": grade_result.get('plagiarism_detection', {}),
            "student_responses": grade_result.get('student_responses', []),
            "excellent_answers": grade_result.get('excellent_answers', []),
            "needs_improvement": grade_result.get('needs_improvement', []),
            "unanswered_questions": grade_result.get('unanswered_questions', []),
            "timestamp": datetime.now().isoformat(),
            "model_used": ai_model,
            # Handwritten/image-specific fields
            "is_handwritten": True,
            "original_image_path": original_image_path,
            # Student info from CSV (if matched)
            "student_id": student_info.get('id', '') if student_info else '',
            "student_email": student_info.get('email', '') if student_info else '',
            # Teacher/school info
            "teacher_name": teacher_name,
            "school_name": school_name,
        }

        # Save result JSON to output folder if specified
        if output_folder and os.path.exists(output_folder):
            result_filename = f"{safe_name}_individual_{timestamp_str}.json"
            result_path = os.path.join(output_folder, result_filename)
            with open(result_path, 'w') as f:
                json.dump(result, f, indent=2)

        # Save to student history for progress tracking
        if result.get('student_id'):
            try:
                add_assignment_to_history(result['student_id'], result)
            except Exception as e:
                _logger.warning("Could not update student history: %s", e)
                sentry_sdk.capture_exception(e)

        # FERPA audit log
        audit_log("GRADE_INDIVIDUAL", f"Graded individual upload for student (image-based, GPT-4o)")

        return jsonify(result)

    except Exception as e:
        _logger.exception("Individual grading error")
        return jsonify({"error": "An internal error occurred"}), 500


def _remove_from_master_csv(result):
    """Remove a deleted result from master_grades.csv so the Assistant sees fresh data."""
    import re
    output_folder = graider_export_dir("Results")
    master_file = os.path.join(output_folder, "master_grades.csv")
    if not os.path.exists(master_file):
        return

    student_id = str(result.get('student_id', ''))
    assignment = result.get('assignment', '')
    if not student_id or not assignment:
        return

    def normalize(name):
        n = name.strip()
        n = re.sub(r'\s*\(\d+\)\s*$', '', n)
        n = re.sub(r'\.docx?\s*$', '', n, flags=re.IGNORECASE)
        n = re.sub(r'\.pdf\s*$', '', n, flags=re.IGNORECASE)
        return n.strip().lower()

    def matches(csv_assign, target):
        csv_norm = normalize(csv_assign)
        target_norm = normalize(target)
        if csv_norm == target_norm:
            return True
        if len(csv_norm) >= 20 and target_norm.startswith(csv_norm):
            return True
        if len(target_norm) >= 20 and csv_norm.startswith(target_norm):
            return True
        return False

    try:
        with open(master_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames
            rows = list(reader)

        filtered = [row for row in rows
                     if not (row.get('Student ID', '') == student_id
                             and matches(row.get('Assignment', ''), assignment))]

        if len(filtered) < len(rows):
            with open(master_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=header)
                writer.writeheader()
                writer.writerows(filtered)
    except Exception as e:
        _logger.error("Could not remove from master_grades.csv: %s", e)
        sentry_sdk.capture_exception(e)


def _sync_approval_to_master_csv(result, approval_status):
    """Update the Approved column in master_grades.csv for a specific result."""
    import re
    output_folder = graider_export_dir("Results")
    master_file = os.path.join(output_folder, "master_grades.csv")
    if not os.path.exists(master_file):
        return

    student_id = str(result.get('student_id', ''))
    assignment = result.get('assignment', '')
    if not student_id or not assignment:
        return

    def normalize(name):
        n = name.strip()
        n = re.sub(r'\s*\(\d+\)\s*$', '', n)
        n = re.sub(r'\.docx?\s*$', '', n, flags=re.IGNORECASE)
        n = re.sub(r'\.pdf\s*$', '', n, flags=re.IGNORECASE)
        return n.strip().lower()

    try:
        with open(master_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            header = list(reader.fieldnames or [])
            rows = list(reader)

        # Add Approved column if missing (legacy CSV)
        if 'Approved' not in header:
            feedback_idx = header.index('Feedback') if 'Feedback' in header else -1
            if feedback_idx >= 0:
                header.insert(feedback_idx + 1, 'Approved')
            else:
                header.append('Approved')
            for row in rows:
                row['Approved'] = ''

        updated = False
        target_norm = normalize(assignment)
        for row in rows:
            row_sid = row.get('Student ID', '')
            row_assign_norm = normalize(row.get('Assignment', ''))
            if row_sid == student_id and row_assign_norm == target_norm:
                row['Approved'] = approval_status
                updated = True

        if updated:
            with open(master_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=header)
                writer.writeheader()
                writer.writerows(rows)
    except Exception as e:
        _logger.error("Could not sync approval to master_grades.csv: %s", e)
        sentry_sdk.capture_exception(e)


# ══════════════════════════════════════════════════════════════
# DELETE SINGLE RESULT
# ══════════════════════════════════════════════════════════════

@grading_results_bp.route('/api/delete-result', methods=['POST'])
@require_teacher
@handle_route_errors
def delete_single_result():
    """Delete a single grading result by filename."""
    teacher_id = getattr(g, 'user_id', 'local-dev')
    grading_state = _get_state(teacher_id)

    if grading_state["is_running"]:
        return jsonify({"error": "Cannot delete results while grading is in progress"}), 400

    data = request.json
    filename = data.get('filename', '')

    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    # Find the result before removing (need student_id + assignment for master CSV sync)
    deleted_result = None
    for r in grading_state["results"]:
        if r.get('filename', '') == filename:
            deleted_result = r
            break

    original_count = len(grading_state["results"])
    grading_state["results"] = [
        r for r in grading_state["results"]
        if r.get('filename', '') != filename
    ]

    # If result wasn't found, that's OK - it's already deleted
    if len(grading_state["results"]) == original_count:
        return jsonify({"status": "already_deleted", "filename": filename})

    # Save updated results to storage
    save_results(grading_state["results"], teacher_id)

    # Also remove from master_grades.csv so the Assistant sees fresh data
    if deleted_result:
        _remove_from_master_csv(deleted_result)

    # FERPA: Audit log the deletion
    audit_log("DELETE_RESULT", f"Deleted result for file: {filename[:30]}...")

    return jsonify({
        "status": "deleted",
        "filename": filename,
        "remaining_count": len(grading_state["results"])
    })


@grading_results_bp.route('/api/update-approval', methods=['POST'])
@require_teacher
@handle_route_errors
def update_approval():
    """Update email approval status for a result."""
    teacher_id = getattr(g, 'user_id', 'local-dev')
    grading_state = _get_state(teacher_id)

    data = request.json
    filename = data.get('filename')
    approval = data.get('approval')  # 'approved', 'rejected', or 'pending'
    graded_at = data.get('graded_at')  # optional — disambiguate duplicates

    if not filename:
        return jsonify({"error": "Missing filename"}), 400

    # Find and update the result (prefer exact match on graded_at for duplicates)
    target = None
    for r in grading_state["results"]:
        if r.get('filename') == filename:
            if graded_at and r.get('graded_at') == graded_at:
                target = r
                break  # exact match
            if target is None:
                target = r  # fallback to first match

    if target:
        target['email_approval'] = approval
        save_results(grading_state["results"], teacher_id)
        _sync_approval_to_master_csv(target, approval)
        return jsonify({"status": "updated", "filename": filename, "approval": approval})

    return jsonify({"error": "Result not found"}), 404


@grading_results_bp.route('/api/update-approvals-bulk', methods=['POST'])
@require_teacher
@handle_route_errors
def update_approvals_bulk():
    """Update email approval status for multiple results at once."""
    teacher_id = getattr(g, 'user_id', 'local-dev')
    grading_state = _get_state(teacher_id)

    data = request.json
    approvals = data.get('approvals', {})  # { filename: approval_status }

    if not approvals:
        return jsonify({"error": "No approvals provided"}), 400

    updated = 0
    for r in grading_state["results"]:
        filename = r.get('filename')
        if filename in approvals:
            r['email_approval'] = approvals[filename]
            _sync_approval_to_master_csv(r, approvals[filename])
            updated += 1

    if updated > 0:
        save_results(grading_state["results"], teacher_id)

    return jsonify({"status": "updated", "count": updated})
