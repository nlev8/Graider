"""
Behavior Tracking Routes
========================
REST endpoints for persisting classroom behavior data.
Data stored in Supabase (behavior_sessions + behavior_events tables).
Syncs with both the Graider web app and iOS companion app.
"""
import os
from collections import defaultdict
from datetime import datetime

from flask import Blueprint, request, jsonify, g

behavior_bp = Blueprint('behavior', __name__)

# ── Supabase client (lazy init, same pattern as other routes) ──

_supabase = None


def _get_supabase():
    global _supabase
    if _supabase is None:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise Exception("Supabase credentials not configured")
        _supabase = create_client(url, key)
    return _supabase


def _get_teacher_id():
    """Get current teacher's UUID from auth middleware."""
    return getattr(g, 'user_id', None)


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
    """
    try:
        teacher_id = _get_teacher_id()
        if not teacher_id:
            return jsonify({"error": "Not authenticated"}), 401

        data = request.json
        events = data.get('events', [])
        period = data.get('period', '')
        date_str = data.get('date', datetime.now().strftime('%Y-%m-%d'))

        if not events:
            return jsonify({"error": "No events to save"})

        sb = _get_supabase()

        # Create a session record
        session_res = sb.table('behavior_sessions').insert({
            "teacher_id": teacher_id,
            "period": period,
            "date": date_str,
            "device": "web",
            "is_active": False,
        }).execute()

        session_id = session_res.data[0]['id'] if session_res.data else None
        if not session_id:
            return jsonify({"error": "Failed to create session"})

        # Insert individual events
        event_rows = []
        for evt in events:
            name = evt.get('student_name', '')
            if not name:
                continue

            timestamp_str = evt.get('timestamp', '')
            # Build event_time from date + timestamp (e.g. "09:15")
            event_time = date_str
            if timestamp_str:
                event_time = f"{date_str}T{timestamp_str}:00"

            event_rows.append({
                "session_id": session_id,
                "teacher_id": teacher_id,
                "student_name": name,
                "type": evt.get('type', 'correction'),
                "note": evt.get('note', '') or None,
                "source": "manual",
                "event_time": event_time,
            })

        if event_rows:
            sb.table('behavior_events').insert(event_rows).execute()

        return jsonify({"status": "success", "message": f"Saved {len(event_rows)} events"})

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

    Returns the same response shape as the old JSON-based API for frontend
    compatibility:
    {
        "status": "success",
        "data": {
            "student_key": {
                "name": "...",
                "entries": [ { date, period, type, count, notes, timestamps } ],
                "total_corrections": N,
                "total_praise": N
            }
        }
    }
    """
    try:
        teacher_id = _get_teacher_id()
        if not teacher_id:
            return jsonify({"error": "Not authenticated"}), 401

        sb = _get_supabase()
        student_filter = request.args.get('student_name', '').strip().lower()
        period_filter = request.args.get('period', '').strip()
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')

        # Query events for this teacher, joined with session for period/date
        query = sb.table('behavior_events').select(
            'student_name, type, note, transcript, event_time, source, '
            'behavior_sessions!inner(period, date)'
        ).eq('teacher_id', teacher_id)

        if date_from:
            query = query.gte('behavior_sessions.date', date_from)
        if date_to:
            query = query.lte('behavior_sessions.date', date_to)
        if period_filter:
            query = query.eq('behavior_sessions.period', period_filter)

        res = query.execute()
        rows = res.data or []

        # Filter by student name (case-insensitive substring) in Python
        # since Supabase doesn't have great ILIKE on non-indexed text
        if student_filter:
            rows = [r for r in rows if student_filter in r.get('student_name', '').lower()]

        # Aggregate into the legacy response shape:
        # group by student → by (date, period, type) → count + notes + timestamps
        students = defaultdict(lambda: {"name": "", "entries_map": {}})

        for row in rows:
            name = row.get('student_name', '')
            sid = name.lower().replace(' ', '_')
            evt_type = row.get('type', 'correction')
            note = row.get('note', '')
            transcript = row.get('transcript', '')
            session = row.get('behavior_sessions', {})
            date_val = session.get('date', '')
            period_val = session.get('period', '')

            # Parse event_time for HH:MM timestamp
            event_time_str = row.get('event_time', '')
            timestamp = ''
            if event_time_str:
                try:
                    dt = datetime.fromisoformat(event_time_str.replace('Z', '+00:00'))
                    timestamp = dt.strftime('%H:%M')
                except Exception:
                    pass

            student = students[sid]
            student["name"] = name

            entry_key = (date_val, period_val, evt_type)
            if entry_key not in student["entries_map"]:
                student["entries_map"][entry_key] = {
                    "date": date_val,
                    "period": period_val,
                    "type": evt_type,
                    "count": 0,
                    "notes": [],
                    "transcripts": [],
                    "timestamps": [],
                }

            entry = student["entries_map"][entry_key]
            entry["count"] += 1
            if note and note not in entry["notes"]:
                entry["notes"].append(note)
            if transcript and transcript not in entry["transcripts"]:
                entry["transcripts"].append(transcript)
            if timestamp:
                entry["timestamps"].append(timestamp)

        # Build final result
        result = {}
        for sid, sdata in students.items():
            entries = list(sdata["entries_map"].values())
            result[sid] = {
                "name": sdata["name"],
                "entries": entries,
                "total_corrections": sum(e["count"] for e in entries if e["type"] == "correction"),
                "total_praise": sum(e["count"] for e in entries if e["type"] == "praise"),
            }

        return jsonify({"status": "success", "data": result})

    except Exception as e:
        return jsonify({"error": str(e)})


@behavior_bp.route('/api/behavior/events', methods=['GET'])
def get_behavior_events():
    """Get individual behavior events (not aggregated).

    Query params:
    - student_name: filter to a specific student (optional)
    - period: filter to a specific period (optional)
    - date_from: start date YYYY-MM-DD (optional)
    - date_to: end date YYYY-MM-DD (optional)
    - limit: max events to return (default 50, max 200)

    Returns individual events with full detail for the event viewer.
    """
    try:
        teacher_id = _get_teacher_id()
        if not teacher_id:
            return jsonify({"error": "Not authenticated"}), 401

        sb = _get_supabase()
        student_filter = request.args.get('student_name', '').strip().lower()
        period_filter = request.args.get('period', '').strip()
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        limit = min(int(request.args.get('limit', '50')), 200)

        query = sb.table('behavior_events').select(
            'id, student_name, type, note, transcript, source, event_time, '
            'behavior_sessions!inner(period, date)'
        ).eq('teacher_id', teacher_id).order('event_time', desc=True).limit(limit)

        if date_from:
            query = query.gte('behavior_sessions.date', date_from)
        if date_to:
            query = query.lte('behavior_sessions.date', date_to)
        if period_filter:
            query = query.eq('behavior_sessions.period', period_filter)

        res = query.execute()
        rows = res.data or []

        if student_filter:
            rows = [r for r in rows if student_filter in r.get('student_name', '').lower()]

        events = []
        for row in rows:
            session = row.get('behavior_sessions', {})
            events.append({
                "id": row.get('id', ''),
                "student_name": row.get('student_name', ''),
                "type": row.get('type', 'correction'),
                "note": row.get('note', '') or '',
                "transcript": row.get('transcript', '') or '',
                "source": row.get('source', 'manual') or 'manual',
                "event_time": row.get('event_time', ''),
                "period": session.get('period', ''),
                "date": session.get('date', ''),
            })

        return jsonify({"status": "success", "data": {"events": events, "total": len(events)}})

    except Exception as e:
        return jsonify({"error": str(e)})


@behavior_bp.route('/api/behavior/data', methods=['DELETE'])
def delete_behavior_data():
    """Delete behavior data.

    Query params:
    - student_id: delete data for a specific student name-key (optional)
    - all: set to "true" to clear all data
    """
    try:
        teacher_id = _get_teacher_id()
        if not teacher_id:
            return jsonify({"error": "Not authenticated"}), 401

        student_id = request.args.get('student_id', '')
        clear_all = request.args.get('all', '').lower() == 'true'

        sb = _get_supabase()

        if clear_all:
            # Delete all sessions (cascade deletes events)
            sb.table('behavior_sessions').delete().eq(
                'teacher_id', teacher_id
            ).execute()
            return jsonify({"status": "success", "message": "All behavior data cleared"})

        if student_id:
            # student_id is name-based key like "john_smith" — convert to name
            student_name_guess = student_id.replace('_', ' ')
            # Delete events matching this student name (case-insensitive)
            sb.table('behavior_events').delete().eq(
                'teacher_id', teacher_id
            ).ilike('student_name', student_name_guess).execute()
            return jsonify({"status": "success", "message": f"Cleared data for {student_id}"})

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
