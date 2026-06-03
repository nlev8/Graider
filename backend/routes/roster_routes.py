"""Student-history and roster-management API routes for Graider.

Tier 2 Slice 3 PR3: verbatim extraction of the student-history/roster
route cluster out of the app module. Six routes:
``GET /api/student-history/<student_id>`` (get_student_history_api),
``GET /api/student-baseline/<student_id>`` (get_student_baseline_api),
``POST /api/retranslate-feedback`` (retranslate_feedback),
``POST /api/extract-student-from-image`` (extract_student_from_image),
``POST /api/add-student-to-roster`` (add_student_to_roster),
``GET /api/list-periods`` (list_periods).

This is a pure relocation with ZERO behavior change. Route bodies and the
full stacked decorator order are byte-identical to the pre-move app-module
code; the ONLY change is the decorator token ``@app.route`` ->
``@roster_bp.route``. The two ``<student_id>`` routes preserve both the path
string and the ``def f(student_id)`` signature exactly.

Import discipline: this module imports every free name the moved bodies
reference that pre-move ``backend/app.py`` resolved in its namespace.
Pre-move ``app.py`` bound ``audit_log`` directly
(``from backend.utils.audit import audit_log``), bound ``require_teacher`` /
``handle_route_errors`` directly, used stdlib ``os`` / ``csv`` / ``json``,
the flask ``request`` / ``jsonify`` / ``g`` names, and a module logger; it
bound the student-history helpers via a nested try/except ImportError chain.
This module replicates that resolution exactly: ``audit_log`` and the two
decorators imported directly; ``os`` / ``csv`` / ``json`` stdlib; flask names
imported directly; a blueprint-local ``_logger`` equivalent to app.py's
module logger; and ``load_student_history`` / ``get_baseline_summary`` (the
only two student-history names this cluster uses) resolved via the SAME
nested try/except ImportError fallback chain pre-move ``app.py`` uses,
importing only that subset and copying app.py's fallback bodies verbatim for
exactly those two names, so the namespace is equivalent and the move
introduces no behavior change. The LLM-adapter classes
(``AnthropicAdapter`` / ``OpenAIAdapter`` / ``LLMRequest`` / ``Message`` /
``TextPart`` / ``ImagePart``) and ``get_api_key`` are imported inside the
route bodies (unchanged) and need no module-level import. This module must
never import the app module (no cycle).

PRE-EXISTING SHADOWING (faithfully preserved, not "fixed"). Two of the six
URLs are already shadowed in production and were before this PR:
``backend/routes/grading_routes.py`` registers
``GET /api/student-history/<student_id>`` (endpoint
``grading.get_student_history``) and ``backend/routes/settings_routes.py``
registers ``GET /api/list-periods`` (endpoint ``settings.list_periods``).
app.py calls ``register_routes()`` before its cluster ``@app.route``
decorators, so Werkzeug's first-added-rule-wins matching already made the
grading/settings views the live production handlers and the app.py copies
(``get_student_history_api`` / ``list_periods``) dead/shadowed on the real
app. ``roster_bp`` is registered AFTER both ``grading_bp`` and
``settings_bp`` in ``register_routes()``, so the moved copies stay shadowed
by exactly the same winners post-move: the production contract for those two
URLs is unchanged. The four other routes are production-live and served by
these (byte-identical) bodies before and after the move. This is the same
honest discipline PR2 applied to its pre-existing ``save_results`` NameError
(issue #423): a verbatim relocation preserves pre-existing latent conditions
rather than changing them.
"""
import csv
import json
import logging
import os

from flask import Blueprint, g, jsonify, request

from backend.utils.audit import audit_log
from backend.utils.auth_decorators import require_teacher
from backend.utils.errors import handle_route_errors

# Student-history helpers: replicate pre-move app.py's nested try/except
# ImportError resolution exactly, importing only the two names this cluster
# uses and copying app.py's fallback bodies verbatim for exactly those names.
try:
    from backend.student_history import load_student_history, get_baseline_summary
except ImportError:
    try:
        from student_history import load_student_history, get_baseline_summary
    except ImportError:
        # Fallback if module not available
        def load_student_history(student_id):
            return None
        def get_baseline_summary(student_id):
            return None

roster_bp = Blueprint('roster', __name__)
_logger = logging.getLogger(__name__)


@roster_bp.route('/api/student-history/<student_id>', methods=['GET'])
@require_teacher
@handle_route_errors
def get_student_history_api(student_id):
    """Get a student's grading history and progress patterns."""
    history = load_student_history(student_id)
    if not history:
        return jsonify({"error": "No history found"}), 404

    # FERPA: Audit log access
    audit_log("VIEW_STUDENT_HISTORY", f"Viewed history for student ID: {student_id[:6]}...")

    return jsonify(history)


@roster_bp.route('/api/student-baseline/<student_id>', methods=['GET'])
@require_teacher
@handle_route_errors
def get_student_baseline_api(student_id):
    """Get a student's baseline performance metrics for deviation detection."""
    baseline = get_baseline_summary(student_id)
    if not baseline:
        return jsonify({"error": "Insufficient history for baseline (need 3+ assignments)"}), 404

    # FERPA: Audit log access
    audit_log("VIEW_STUDENT_BASELINE", f"Viewed baseline for student ID: {student_id[:6]}...")

    return jsonify(baseline)


@roster_bp.route('/api/retranslate-feedback', methods=['POST'])
@require_teacher
@handle_route_errors
def retranslate_feedback():
    """Re-translate English feedback to the target language."""
    data = request.json
    english_feedback = data.get('english_feedback', '')
    target_language = data.get('target_language', 'spanish')

    if not english_feedback:
        return jsonify({"error": "No feedback provided"})

    try:
        from backend.api_keys import get_api_key
        from backend.services.llm_adapter import LLMRequest, Message, OpenAIAdapter, TextPart
        adapter = OpenAIAdapter(api_key=get_api_key('openai', getattr(g, 'user_id', 'local-dev')))
        response = adapter.chat(LLMRequest(
            model="gpt-4o-mini",
            messages=[Message(role="user", content=[TextPart(
                text=f"Translate the following teacher feedback to {target_language}. Keep the same warm, encouraging tone. Only output the translation, nothing else.\n\nFeedback:\n{english_feedback}"
            )])],
            temperature=0.3,
            metadata={"feature_label": "retranslate_feedback"},
        ))
        translation = (response.content_parts[0].text if response.content_parts else "").strip()
        return jsonify({"translation": translation})

    except Exception as e:
        _logger.exception("Failed to translate feedback")
        return jsonify({"error": "An internal error occurred"}), 500


# ══════════════════════════════════════════════════════════════
# ROSTER MANAGEMENT - Add student from screenshot
# ══════════════════════════════════════════════════════════════

@roster_bp.route('/api/extract-student-from-image', methods=['POST'])
@require_teacher
@handle_route_errors
def extract_student_from_image():
    """Use Claude Opus 4.5 to extract student info from a screenshot."""
    try:
        data = request.json
        image_data = data.get('image')  # Base64 encoded image

        if not image_data:
            return jsonify({"error": "No image provided"})

        from backend.api_keys import get_api_key
        from backend.services.llm_adapter import (
            AnthropicAdapter, ImagePart, LLMRequest, Message, TextPart,
        )
        api_key = get_api_key('anthropic', getattr(g, 'user_id', 'local-dev'))
        if not api_key:
            return jsonify({"error": "ANTHROPIC_API_KEY not configured"})

        # Remove data URL prefix if present
        if ',' in image_data:
            image_data = image_data.split(',')[1]

        prompt = """Extract student information from this screenshot. Return ONLY a JSON object with these fields:
{
    "first_name": "Student's first name",
    "middle_name": "Student's middle name (if visible, otherwise empty string)",
    "last_name": "Student's last name",
    "student_id": "Student ID number (if visible, otherwise empty string)",
    "email": "Student's email address (if visible, otherwise empty string)",
    "grade": "Grade level (if visible, otherwise empty string)",
    "period": "Class period number only, e.g., '2' not 'Period 2' (if visible, otherwise empty string)"
}

Important:
- Extract exactly what you see, don't guess
- For names with multiple parts, include all parts (e.g., middle names)
- Return ONLY the JSON, no other text"""

        adapter = AnthropicAdapter(api_key=api_key)
        response = adapter.chat(LLMRequest(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[Message(
                role="user",
                content=[
                    ImagePart(url=None, base64=image_data, mime_type="image/png"),
                    TextPart(text=prompt),
                ],
            )],
            metadata={"feature_label": "extract_student_from_image"},
        ))

        response_text = (response.content_parts[0].text if response.content_parts else "").strip()

        # Parse JSON from response
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1])

        student_info = json.loads(response_text)
        return jsonify({"success": True, "student": student_info})

    except json.JSONDecodeError as e:
        _logger.exception("Failed to parse AI response for student extraction")
        return jsonify({"error": "Failed to parse AI response"})
    except Exception as e:
        _logger.exception("Failed to extract student from image")
        return jsonify({"error": "An internal error occurred"}), 500


@roster_bp.route('/api/add-student-to-roster', methods=['POST'])
@require_teacher
@handle_route_errors
def add_student_to_roster():
    """Add a student to the appropriate period CSV and optionally the main roster."""
    try:
        data = request.json
        student = data.get('student', {})
        period = data.get('period', '').strip()

        if not period:
            return jsonify({"error": "Period is required"})

        first_name = student.get('first_name', '').strip()
        middle_name = student.get('middle_name', '').strip()
        last_name = student.get('last_name', '').strip()
        student_id = student.get('student_id', '').strip()
        email = student.get('email', '').strip()
        grade = student.get('grade', '06').strip()

        if not first_name or not last_name:
            return jsonify({"error": "First name and last name are required"})

        # Build full first name with middle name
        full_first = f"{first_name} {middle_name}".strip() if middle_name else first_name

        # Format: "LastName; FirstName MiddleName"
        student_name = f"{last_name}; {full_first}"

        # Find the period CSV file
        periods_dir = os.path.expanduser("~/.graider_data/periods")
        period_file = None

        for f in os.listdir(periods_dir):
            if f.endswith('.csv'):
                # Match "Period 2.csv", "Period_2.csv", "Period2.csv", etc.
                f_lower = f.lower().replace('_', ' ').replace('.csv', '')
                if f"period {period}" in f_lower or f"period{period}" in f_lower:
                    period_file = os.path.join(periods_dir, f)
                    break

        if not period_file:
            # Create new period file
            period_file = os.path.join(periods_dir, f"Period {period}.csv")
            with open(period_file, 'w', newline='', encoding='utf-8') as pf:
                writer = csv.writer(pf)
                writer.writerow(["Student", "Student ID", "Local ID", "Grade", "Local Student ID", "Team"])

        # Check if student already exists
        existing_students = []
        with open(period_file, 'r', encoding='utf-8') as pf:
            reader = csv.reader(pf)
            existing_students = list(reader)

        for row in existing_students[1:]:  # Skip header
            if row and row[0].lower() == student_name.lower():
                return jsonify({"error": f"Student '{student_name}' already exists in Period {period}"})

        # Add student to period CSV
        with open(period_file, 'a', newline='', encoding='utf-8') as pf:
            writer = csv.writer(pf)
            writer.writerow([student_name, student_id, student_id, grade, student_id, ""])

        return jsonify({
            "success": True,
            "message": f"Added {full_first} {last_name} to Period {period}",
            "student_name": student_name,
            "period_file": period_file
        })

    except Exception as e:
        _logger.exception("Failed to add student")
        return jsonify({"error": "An error occurred while adding the student"}), 500


@roster_bp.route('/api/list-periods', methods=['GET'])
@require_teacher
@handle_route_errors
def list_periods():
    """List available period CSV files."""
    try:
        periods_dir = os.path.expanduser("~/.graider_data/periods")
        periods = []

        if os.path.exists(periods_dir):
            for f in os.listdir(periods_dir):
                if f.endswith('.csv'):
                    period_name = f.replace('.csv', '').replace('_', ' ')
                    # Count students
                    count = 0
                    try:
                        with open(os.path.join(periods_dir, f), 'r', encoding='utf-8') as pf:
                            count = sum(1 for _ in pf) - 1  # Subtract header
                    except Exception:
                        _logger.debug("period student count failed", exc_info=True)
                    periods.append({"name": period_name, "file": f, "student_count": count})

        periods.sort(key=lambda x: x['name'])
        return jsonify({"periods": periods})

    except Exception as e:
        _logger.exception("Failed to list periods")
        return jsonify({"error": "An internal error occurred"}), 500
