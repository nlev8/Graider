"""
Lesson Plan storage routes for Graider.
Saves lesson plans for later use in assessment generation.
Includes teaching calendar endpoints for scheduling lessons.
"""
import os
import json
import uuid
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify

try:
    import anthropic
except ImportError:
    anthropic = None

from backend.services.assistant_tools import _extract_pdf_text, _extract_docx_text

logger = logging.getLogger(__name__)

lesson_bp = Blueprint('lesson', __name__)

LESSONS_DIR = os.path.expanduser("~/.graider_lessons")
GRAIDER_DATA_DIR = os.path.expanduser("~/.graider_data")
CALENDAR_FILE = os.path.join(GRAIDER_DATA_DIR, "teaching_calendar.json")
DOCUMENTS_DIR = os.path.join(GRAIDER_DATA_DIR, "documents")


def _safe_filename(name):
    """Convert name to safe filename."""
    return "".join(c for c in name if c.isalnum() or c in ' -_').strip()


@lesson_bp.route('/api/save-lesson', methods=['POST'])
def save_lesson():
    """Save a lesson plan for later use in assessment generation."""
    data = request.json
    lesson = data.get('lesson', {})
    unit_name = data.get('unitName', 'General')

    os.makedirs(LESSONS_DIR, exist_ok=True)

    # Create unit subfolder
    unit_folder = os.path.join(LESSONS_DIR, _safe_filename(unit_name))
    os.makedirs(unit_folder, exist_ok=True)

    # Use lesson title for filename
    title = lesson.get('title', 'Untitled Lesson')
    safe_title = _safe_filename(title)
    filepath = os.path.join(unit_folder, f"{safe_title}.json")

    # Add metadata
    lesson['_saved_at'] = datetime.now().isoformat()
    lesson['_unit'] = unit_name

    try:
        with open(filepath, 'w') as f:
            json.dump(lesson, f, indent=2)
        return jsonify({"status": "saved", "path": filepath, "unit": unit_name})
    except Exception as e:
        return jsonify({"error": str(e)})


@lesson_bp.route('/api/list-lessons')
def list_lessons():
    """List all saved lessons organized by unit."""
    if not os.path.exists(LESSONS_DIR):
        return jsonify({"units": {}, "lessons": []})

    units = {}
    all_lessons = []

    for unit_name in os.listdir(LESSONS_DIR):
        unit_path = os.path.join(LESSONS_DIR, unit_name)
        if not os.path.isdir(unit_path):
            continue

        units[unit_name] = []

        for f in os.listdir(unit_path):
            if f.endswith('.json'):
                try:
                    with open(os.path.join(unit_path, f), 'r') as lf:
                        lesson = json.load(lf)
                        lesson_info = {
                            "filename": f.replace('.json', ''),
                            "title": lesson.get('title', f.replace('.json', '')),
                            "unit": unit_name,
                            "standards": lesson.get('standards', []),
                            "objectives": lesson.get('learning_objectives', []),
                            "saved_at": lesson.get('_saved_at', '')
                        }
                        units[unit_name].append(lesson_info)
                        all_lessons.append(lesson_info)
                except Exception:
                    pass

    return jsonify({"units": units, "lessons": all_lessons})


@lesson_bp.route('/api/load-lesson')
def load_lesson():
    """Load a specific lesson by unit and filename."""
    unit = request.args.get('unit', '')
    filename = request.args.get('filename', '')

    filepath = os.path.join(LESSONS_DIR, _safe_filename(unit), f"{filename}.json")

    if not os.path.exists(filepath):
        return jsonify({"error": "Lesson not found"})

    try:
        with open(filepath, 'r') as f:
            lesson = json.load(f)
        return jsonify({"lesson": lesson})
    except Exception as e:
        return jsonify({"error": str(e)})


@lesson_bp.route('/api/delete-lesson', methods=['DELETE'])
def delete_lesson():
    """Delete a saved lesson."""
    unit = request.args.get('unit', '')
    filename = request.args.get('filename', '')

    filepath = os.path.join(LESSONS_DIR, _safe_filename(unit), f"{filename}.json")

    if not os.path.exists(filepath):
        return jsonify({"error": "Lesson not found"})

    try:
        os.remove(filepath)
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)})


@lesson_bp.route('/api/list-units')
def list_units():
    """List all unit names."""
    if not os.path.exists(LESSONS_DIR):
        return jsonify({"units": []})

    units = [d for d in os.listdir(LESSONS_DIR)
             if os.path.isdir(os.path.join(LESSONS_DIR, d))]
    return jsonify({"units": sorted(units)})


# ═══════════════════════════════════════════════════════
# TEACHING CALENDAR
# ═══════════════════════════════════════════════════════

_DEFAULT_CALENDAR = {
    "scheduled_lessons": [],
    "holidays": [],
    "school_days": {
        "monday": True, "tuesday": True, "wednesday": True,
        "thursday": True, "friday": True, "saturday": False, "sunday": False
    }
}


def _load_calendar():
    """Load calendar data from disk."""
    if not os.path.exists(CALENDAR_FILE):
        return dict(_DEFAULT_CALENDAR)
    try:
        with open(CALENDAR_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Ensure all keys exist
        for key, default in _DEFAULT_CALENDAR.items():
            if key not in data:
                data[key] = default
        return data
    except Exception:
        return dict(_DEFAULT_CALENDAR)


def _save_calendar(data):
    """Persist calendar data to disk."""
    os.makedirs(GRAIDER_DATA_DIR, exist_ok=True)
    with open(CALENDAR_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


@lesson_bp.route('/api/calendar', methods=['GET'])
def get_calendar():
    """Return full calendar data."""
    return jsonify(_load_calendar())


@lesson_bp.route('/api/calendar/schedule', methods=['PUT'])
def schedule_lesson():
    """Add or update a scheduled lesson on the calendar."""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    date = data.get('date')
    if not date:
        return jsonify({"error": "date is required"}), 400

    cal = _load_calendar()

    entry_id = data.get('id') or str(uuid.uuid4())

    entry = {
        "id": entry_id,
        "date": date,
        "unit": data.get('unit', ''),
        "lesson_title": data.get('lesson_title', ''),
        "day_number": data.get('day_number'),
        "lesson_file": data.get('lesson_file', ''),
        "color": data.get('color', '#6366f1'),
    }

    # Update existing or append new
    existing_idx = next(
        (i for i, s in enumerate(cal["scheduled_lessons"]) if s["id"] == entry_id),
        None
    )
    if existing_idx is not None:
        cal["scheduled_lessons"][existing_idx] = entry
    else:
        cal["scheduled_lessons"].append(entry)

    _save_calendar(cal)
    return jsonify({"status": "scheduled", "entry": entry})


@lesson_bp.route('/api/calendar/schedule/<entry_id>', methods=['DELETE'])
def unschedule_lesson(entry_id):
    """Remove a scheduled lesson from the calendar."""
    cal = _load_calendar()
    before = len(cal["scheduled_lessons"])
    cal["scheduled_lessons"] = [s for s in cal["scheduled_lessons"] if s["id"] != entry_id]
    if len(cal["scheduled_lessons"]) == before:
        return jsonify({"error": "Entry not found"}), 404
    _save_calendar(cal)
    return jsonify({"status": "removed"})


@lesson_bp.route('/api/calendar/holiday', methods=['POST'])
def add_holiday():
    """Add a holiday or break to the calendar."""
    data = request.json
    if not data or not data.get('date'):
        return jsonify({"error": "date and name are required"}), 400

    cal = _load_calendar()

    holiday = {
        "date": data["date"],
        "name": data.get("name", "Holiday"),
    }
    if data.get("end_date"):
        holiday["end_date"] = data["end_date"]

    # Avoid duplicate dates
    cal["holidays"] = [h for h in cal["holidays"] if h["date"] != data["date"]]
    cal["holidays"].append(holiday)
    cal["holidays"].sort(key=lambda h: h["date"])

    _save_calendar(cal)
    return jsonify({"status": "added", "holiday": holiday})


@lesson_bp.route('/api/calendar/holiday', methods=['DELETE'])
def remove_holiday():
    """Remove a holiday by date."""
    date = request.args.get('date')
    if not date:
        return jsonify({"error": "date parameter required"}), 400

    cal = _load_calendar()
    before = len(cal["holidays"])
    cal["holidays"] = [h for h in cal["holidays"] if h["date"] != date]
    if len(cal["holidays"]) == before:
        return jsonify({"error": "Holiday not found for that date"}), 404
    _save_calendar(cal)
    return jsonify({"status": "removed"})


@lesson_bp.route('/api/calendar/school-days', methods=['PUT'])
def update_school_days():
    """Update which days of the week are school days."""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    cal = _load_calendar()
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        if day in data:
            cal["school_days"][day] = bool(data[day])
    _save_calendar(cal)
    return jsonify({"status": "updated", "school_days": cal["school_days"]})


@lesson_bp.route('/api/calendar/parse-document', methods=['POST'])
def parse_document_for_calendar():
    """Parse an uploaded document and extract calendar events using AI."""
    data = request.json
    if not data or not data.get('filename'):
        return jsonify({"error": "filename is required"}), 400

    filename = data['filename']
    filepath = os.path.join(DOCUMENTS_DIR, filename)

    if not os.path.exists(filepath):
        return jsonify({"error": "Document not found"}), 404

    try:
        ext = os.path.splitext(filename)[1].lower()
        if ext == '.pdf':
            text, _ = _extract_pdf_text(filepath)
        elif ext in ('.docx', '.doc'):
            text = _extract_docx_text(filepath)
        else:
            return jsonify({"error": "Unsupported file type. Use PDF or DOCX."}), 400

        if not text or text.startswith('['):
            return jsonify({"error": "Could not extract text from document"}), 400
    except Exception as e:
        logger.error("Failed to extract text from %s: %s", filename, e)
        return jsonify({"error": "Failed to read document: " + str(e)}), 500

    if anthropic is None:
        return jsonify({"error": "anthropic package is not installed"}), 500

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not configured"}), 500

    prompt = (
        "You are a calendar data extractor for a teaching pacing guide.\n"
        "Extract every dated event from the following document text.\n"
        "Return ONLY a JSON array (no markdown, no explanation) where each element has:\n"
        '  {"date": "YYYY-MM-DD", "title": "short event title", '
        '"type": "lesson" or "holiday", "unit": "unit name or empty string"}\n\n'
        "Rules:\n"
        "- Convert all dates to YYYY-MM-DD format\n"
        "- Use type 'holiday' for breaks, holidays, no-school days, PD days\n"
        "- Use type 'lesson' for lessons, topics, units, activities, tests, quizzes\n"
        "- For multi-day events, create one entry per day\n"
        "- If a unit/chapter name is mentioned, include it in the 'unit' field\n"
        "- Keep titles concise (under 60 characters)\n"
        "- If no specific date is found for an item, skip it\n\n"
        "Document text:\n" + text[:15000]
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text.strip()

        # Strip markdown code fences if present
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            lines = [l for l in lines if not l.strip().startswith('```')]
            response_text = '\n'.join(lines)

        events = json.loads(response_text)
        if not isinstance(events, list):
            return jsonify({"error": "AI returned invalid format"}), 500

        return jsonify({"events": events, "count": len(events)})

    except json.JSONDecodeError:
        logger.error("AI returned non-JSON response for %s", filename)
        return jsonify({"error": "AI could not parse events from this document"}), 500
    except Exception as e:
        logger.error("AI parsing failed for %s: %s", filename, e)
        return jsonify({"error": "AI parsing failed: " + str(e)}), 500


@lesson_bp.route('/api/calendar/import-events', methods=['POST'])
def import_calendar_events():
    """Bulk import events into the teaching calendar."""
    data = request.json
    if not data or not isinstance(data.get('events'), list):
        return jsonify({"error": "events array is required"}), 400

    events = data['events']
    cal = _load_calendar()

    lessons_added = 0
    holidays_added = 0

    for event in events:
        date = event.get('date')
        title = event.get('title', '')
        event_type = event.get('type', 'lesson')
        unit = event.get('unit', '')

        if not date or not title:
            continue

        if event_type == 'holiday':
            # Deduplicate by date
            cal["holidays"] = [h for h in cal["holidays"] if h["date"] != date]
            cal["holidays"].append({"date": date, "name": title})
            holidays_added += 1
        else:
            entry = {
                "id": str(uuid.uuid4()),
                "date": date,
                "unit": unit,
                "lesson_title": title,
                "day_number": None,
                "lesson_file": "",
                "color": "#6366f1",
            }
            cal["scheduled_lessons"].append(entry)
            lessons_added += 1

    cal["holidays"].sort(key=lambda h: h["date"])
    _save_calendar(cal)

    return jsonify({
        "status": "imported",
        "lessons_added": lessons_added,
        "holidays_added": holidays_added,
        "calendar": cal,
    })
