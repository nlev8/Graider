"""
Lesson Plan storage routes for Graider.
Saves lesson plans for later use in assessment generation.
"""
import os
import json
from datetime import datetime
from flask import Blueprint, request, jsonify

lesson_bp = Blueprint('lesson', __name__)

LESSONS_DIR = os.path.expanduser("~/.graider_lessons")


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
