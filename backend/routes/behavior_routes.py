"""
Behavior Tracking Routes
========================
REST endpoints for persisting classroom behavior data.
Data stored at ~/.graider_data/behavior_tracking.json — cumulative + per-session.
"""
import csv
import json
import os
from datetime import datetime

from flask import Blueprint, request, jsonify

behavior_bp = Blueprint('behavior', __name__)

GRAIDER_DATA_DIR = os.path.expanduser("~/.graider_data")
BEHAVIOR_FILE = os.path.join(GRAIDER_DATA_DIR, "behavior_tracking.json")
PERIODS_DIR = os.path.expanduser("~/.graider_data/periods")


def _load_behavior_data():
    """Load behavior tracking data from disk."""
    if not os.path.exists(BEHAVIOR_FILE):
        return {"version": 1, "students": {}}
    try:
        with open(BEHAVIOR_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"version": 1, "students": {}}


def _save_behavior_data(data):
    """Save behavior tracking data to disk."""
    os.makedirs(GRAIDER_DATA_DIR, exist_ok=True)
    with open(BEHAVIOR_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@behavior_bp.route('/api/behavior/session', methods=['POST'])
def save_behavior_session():
    """Save a completed behavior tracking session.

    Expects JSON body:
    {
        "events": [
            {
                "student_id": "...",
                "student_name": "John Smith",
                "type": "correction" | "praise",
                "note": "Talking during instruction",
                "timestamp": "09:15",
                "period": "Period 3"
            }
        ],
        "period": "Period 3",
        "date": "2026-02-27"
    }

    Merges into cumulative data per student.
    """
    try:
        data = request.json
        events = data.get('events', [])
        period = data.get('period', '')
        date = data.get('date', datetime.now().strftime('%Y-%m-%d'))

        if not events:
            return jsonify({"error": "No events to save"})

        behavior = _load_behavior_data()
        students = behavior.setdefault("students", {})

        for evt in events:
            sid = evt.get('student_id', evt.get('student_name', '').lower().replace(' ', '_'))
            name = evt.get('student_name', '')
            evt_type = evt.get('type', 'correction')
            note = evt.get('note', '')
            timestamp = evt.get('timestamp', '')
            evt_period = evt.get('period', period)

            if not name:
                continue

            student = students.setdefault(sid, {"name": name, "entries": []})
            # Update name in case of casing differences
            student["name"] = name

            # Find or create today's entry for this period + type
            existing = None
            for entry in student["entries"]:
                if entry.get("date") == date and entry.get("period") == evt_period and entry.get("type") == evt_type:
                    existing = entry
                    break

            if existing:
                existing["count"] = existing.get("count", 0) + 1
                if note and note not in existing.get("notes", []):
                    existing.setdefault("notes", []).append(note)
                if timestamp:
                    existing.setdefault("timestamps", []).append(timestamp)
            else:
                student["entries"].append({
                    "date": date,
                    "period": evt_period,
                    "type": evt_type,
                    "count": 1,
                    "notes": [note] if note else [],
                    "timestamps": [timestamp] if timestamp else [],
                })

        _save_behavior_data(behavior)
        return jsonify({"status": "success", "message": f"Saved {len(events)} events"})

    except Exception as e:
        return jsonify({"error": str(e)})


@behavior_bp.route('/api/behavior/data', methods=['GET'])
def get_behavior_data():
    """Get behavior tracking data.

    Query params:
    - student_name: filter to a specific student (optional)
    - period: filter to a specific period (optional)
    - date_from: start date filter YYYY-MM-DD (optional)
    - date_to: end date filter YYYY-MM-DD (optional)
    """
    try:
        behavior = _load_behavior_data()
        student_filter = request.args.get('student_name', '').strip().lower()
        period_filter = request.args.get('period', '').strip()
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')

        result = {}
        for sid, student in behavior.get("students", {}).items():
            name = student.get("name", "")

            # Student name filter (case-insensitive substring)
            if student_filter and student_filter not in name.lower():
                continue

            filtered_entries = []
            for entry in student.get("entries", []):
                # Period filter
                if period_filter and entry.get("period", "") != period_filter:
                    continue
                # Date filters
                entry_date = entry.get("date", "")
                if date_from and entry_date < date_from:
                    continue
                if date_to and entry_date > date_to:
                    continue
                filtered_entries.append(entry)

            if filtered_entries:
                result[sid] = {
                    "name": name,
                    "entries": filtered_entries,
                    "total_corrections": sum(e.get("count", 0) for e in filtered_entries if e.get("type") == "correction"),
                    "total_praise": sum(e.get("count", 0) for e in filtered_entries if e.get("type") == "praise"),
                }

        return jsonify({"status": "success", "data": result})

    except Exception as e:
        return jsonify({"error": str(e)})


@behavior_bp.route('/api/behavior/data', methods=['DELETE'])
def delete_behavior_data():
    """Delete behavior data.

    Query params:
    - student_id: delete data for a specific student (optional)
    - all: set to "true" to clear all data
    """
    try:
        student_id = request.args.get('student_id', '')
        clear_all = request.args.get('all', '').lower() == 'true'

        if clear_all:
            _save_behavior_data({"version": 1, "students": {}})
            return jsonify({"status": "success", "message": "All behavior data cleared"})

        if student_id:
            behavior = _load_behavior_data()
            if student_id in behavior.get("students", {}):
                del behavior["students"][student_id]
                _save_behavior_data(behavior)
                return jsonify({"status": "success", "message": f"Cleared data for {student_id}"})
            return jsonify({"error": f"Student {student_id} not found"})

        return jsonify({"error": "Specify student_id or all=true"})

    except Exception as e:
        return jsonify({"error": str(e)})


@behavior_bp.route('/api/behavior/roster', methods=['GET'])
def get_roster_for_behavior():
    """Return a lightweight roster for name matching in the behavior panel.
    Reads from the same period CSVs used by the assistant tools."""
    try:
        roster = []
        if not os.path.exists(PERIODS_DIR):
            return jsonify(roster)

        period_meta = {}
        for f in os.listdir(PERIODS_DIR):
            if f.endswith('.meta.json'):
                try:
                    with open(os.path.join(PERIODS_DIR, f), 'r') as fh:
                        meta = json.load(fh)
                    csv_name = f.replace('.meta.json', '')
                    period_meta[csv_name] = meta
                except Exception:
                    pass

        for f in sorted(os.listdir(PERIODS_DIR)):
            if not f.endswith('.csv'):
                continue
            meta = period_meta.get(f, {})
            period_name = meta.get('period_name', f.replace('.csv', '').replace('_', ' '))
            filepath = os.path.join(PERIODS_DIR, f)
            try:
                with open(filepath, 'r', encoding='utf-8') as fh:
                    reader = csv.DictReader(fh)
                    for row in reader:
                        raw_name = row.get('Student', '').strip().strip('"')
                        student_id = row.get('Student ID', '').strip().strip('"')
                        if ';' in raw_name:
                            parts = raw_name.split(';', 1)
                            display_name = (parts[1].strip() + ' ' + parts[0].strip()).strip()
                        elif ',' in raw_name:
                            parts = raw_name.split(',', 1)
                            display_name = (parts[1].strip() + ' ' + parts[0].strip()).strip()
                        else:
                            display_name = raw_name
                        if display_name:
                            roster.append({
                                "name": display_name,
                                "student_id": student_id,
                                "period": period_name,
                            })
            except Exception:
                pass

        return jsonify(roster)
    except Exception as e:
        return jsonify({"error": str(e)})
