#!/usr/bin/env python3
"""
Graider - AI-Powered Assignment Grading
=======================================
Run: python3 backend/app.py
Then open: http://localhost:3000
"""

import os
import sys
import json
import csv
import threading
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
_app_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_app_dir)
load_dotenv(os.path.join(_root_dir, '.env'), override=True)

# Add parent directory to path for importing assignment_grader
sys.path.insert(0, _root_dir)

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# ══════════════════════════════════════════════════════════════
# GRADING STATE MANAGEMENT
# ══════════════════════════════════════════════════════════════

grading_state = {
    "is_running": False,
    "stop_requested": False,
    "progress": 0,
    "total": 0,
    "current_file": "",
    "log": [],
    "results": [],
    "complete": False,
    "error": None
}


def reset_state():
    global grading_state
    grading_state.update({
        "is_running": False,
        "stop_requested": False,
        "progress": 0,
        "total": 0,
        "current_file": "",
        "log": [],
        "results": [],
        "complete": False,
        "error": None
    })


# ══════════════════════════════════════════════════════════════
# GRADING THREAD
# ══════════════════════════════════════════════════════════════

def run_grading_thread(assignments_folder, output_folder, roster_file, assignment_config=None, global_ai_notes='', grading_period='Q3'):
    """Run the grading process in a background thread."""
    global grading_state

    # Load ALL saved assignment configs for auto-matching
    all_configs = {}
    assignments_dir = os.path.expanduser("~/.graider_assignments")
    if os.path.exists(assignments_dir):
        for f in os.listdir(assignments_dir):
            if f.endswith('.json'):
                config_name = f.replace('.json', '')
                try:
                    with open(os.path.join(assignments_dir, f), 'r') as cf:
                        all_configs[config_name.lower()] = json.load(cf)
                except:
                    pass

    def find_matching_config(filename):
        """Find matching config for a filename."""
        filename_lower = filename.lower()
        if ' - ' in filename_lower:
            assignment_part = filename_lower.split(' - ', 1)[1]
        elif '_' in filename_lower:
            parts = filename_lower.split('_')
            assignment_part = '_'.join(parts[2:]) if len(parts) > 2 else filename_lower
        else:
            assignment_part = filename_lower

        assignment_part = os.path.splitext(assignment_part)[0]

        best_match = None
        best_score = 0
        for config_name, config_data in all_configs.items():
            if config_name in assignment_part or assignment_part in config_name:
                score = len(config_name)
                if score > best_score:
                    best_score = score
                    best_match = config_data
            config_title = config_data.get('title', '').lower()
            if config_title and (config_title in assignment_part or assignment_part in config_title):
                score = len(config_title)
                if score > best_score:
                    best_score = score
                    best_match = config_data
        return best_match

    # Extract custom markers and notes from selected config (fallback)
    fallback_markers = []
    fallback_notes = ''
    if assignment_config:
        fallback_markers = assignment_config.get('customMarkers', [])
        fallback_notes = assignment_config.get('gradingNotes', '')

    try:
        from assignment_grader import (
            load_roster, parse_filename, read_assignment_file,
            extract_student_work, grade_assignment, export_focus_csv,
            export_detailed_report, save_emails_to_folder, save_to_master_csv,
            ASSIGNMENT_NAME, STUDENT_WORK_MARKERS
        )

        if all_configs:
            grading_state["log"].append(f"Loaded {len(all_configs)} assignment configs for auto-matching")

        if global_ai_notes:
            grading_state["log"].append(f"Global AI notes loaded")

        os.makedirs(output_folder, exist_ok=True)

        # Load already graded files from master CSV
        already_graded = set()
        master_file = os.path.join(output_folder, "master_grades.csv")
        if os.path.exists(master_file):
            try:
                with open(master_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        filename = row.get('Filename', '')
                        if filename:
                            already_graded.add(filename)
                grading_state["log"].append(f"Found {len(already_graded)} previously graded files")
            except:
                pass

        grading_state["log"].append("Loading student roster...")
        roster = load_roster(roster_file)
        grading_state["log"].append(f"Loaded {len(roster)//2} students")

        assignment_path = Path(assignments_folder)
        all_files = []
        for ext in ['*.docx', '*.txt', '*.jpg', '*.jpeg', '*.png']:
            all_files.extend(assignment_path.glob(ext))

        # Filter out already graded files
        new_files = [f for f in all_files if f.name not in already_graded]
        skipped = len(all_files) - len(new_files)

        if skipped > 0:
            grading_state["log"].append(f"Skipping {skipped} already-graded files")

        grading_state["total"] = len(new_files)
        grading_state["log"].append(f"Found {len(new_files)} NEW files to grade")

        if len(new_files) == 0:
            grading_state["log"].append("")
            grading_state["log"].append("All files have already been graded!")
            grading_state["complete"] = True
            grading_state["is_running"] = False
            return

        all_grades = []

        for i, filepath in enumerate(new_files, 1):
            # Check if stop was requested
            if grading_state.get("stop_requested", False):
                grading_state["log"].append("")
                grading_state["log"].append(f"Stopped at {i-1}/{len(new_files)} files")
                grading_state["log"].append(f"Progress saved! {len(all_grades)} grades completed.")
                break

            grading_state["progress"] = i
            grading_state["current_file"] = filepath.name

            parsed = parse_filename(filepath.name)
            student_name = f"{parsed['first_name']} {parsed['last_name']}"
            lookup_key = parsed['lookup_key']

            if lookup_key in roster:
                student_info = roster[lookup_key].copy()
            else:
                student_info = {"student_id": "UNKNOWN", "student_name": student_name, "first_name": parsed['first_name'], "last_name": parsed['last_name'], "email": ""}

            grading_state["log"].append(f"[{i}/{len(new_files)}] {student_info['student_name']}")

            # Try to auto-match assignment config based on filename
            matched_config = find_matching_config(filepath.name)
            if matched_config:
                file_markers = matched_config.get('customMarkers', [])
                file_notes = matched_config.get('gradingNotes', '')
                matched_title = matched_config.get('title', 'Unknown')
                grading_state["log"].append(f"  Matched config: {matched_title}")
            else:
                file_markers = fallback_markers
                file_notes = fallback_notes

            # Build combined AI notes for this file
            file_ai_notes = ''
            if global_ai_notes:
                file_ai_notes += f"GLOBAL GRADING INSTRUCTIONS:\n{global_ai_notes}\n\n"
            if file_notes:
                file_ai_notes += f"ASSIGNMENT-SPECIFIC INSTRUCTIONS:\n{file_notes}"

            # Add file-specific markers to the markers list temporarily
            original_markers = STUDENT_WORK_MARKERS.copy()
            for marker in file_markers:
                if marker not in STUDENT_WORK_MARKERS:
                    STUDENT_WORK_MARKERS.append(marker)

            file_data = read_assignment_file(filepath)
            if not file_data:
                grading_state["log"].append(f"  Could not read file")
                STUDENT_WORK_MARKERS.clear()
                STUDENT_WORK_MARKERS.extend(original_markers)
                continue

            markers_found = []
            if file_data["type"] == "text":
                student_work, markers_found = extract_student_work(file_data["content"])
                if markers_found:
                    grading_state["log"].append(f"  Markers: {', '.join(markers_found[:2])}")
                grade_data = {"type": "text", "content": student_work}
            else:
                grading_state["log"].append(f"  Image file")
                grade_data = file_data

            grading_state["log"].append(f"  Grading...")
            grade_result = grade_assignment(student_info['student_name'], grade_data, file_ai_notes)

            # Restore original markers
            STUDENT_WORK_MARKERS.clear()
            STUDENT_WORK_MARKERS.extend(original_markers)
            grading_state["log"].append(f"  Score: {grade_result['score']} ({grade_result['letter_grade']})")

            # Extract assignment name from filename
            parts = Path(filepath.name).stem.split('_')
            if len(parts) >= 3:
                assignment_from_file = ' '.join(parts[2:])
            else:
                assignment_from_file = ASSIGNMENT_NAME

            # Get student content for review
            if file_data["type"] == "text":
                student_content = student_work if student_work else file_data.get("content", "")
            else:
                student_content = "[Image file - view in original document]"

            # Build full grade record for export
            grade_record = {
                **student_info,
                **grade_result,
                "filename": filepath.name,
                "assignment": assignment_from_file,
                "grading_period": grading_period,
                "has_markers": len(markers_found) > 0
            }
            all_grades.append(grade_record)

            grading_state["results"].append({
                "student_name": student_info['student_name'],
                "student_id": student_info['student_id'],
                "email": student_info.get('email', ''),
                "filename": filepath.name,
                "filepath": str(filepath),
                "assignment": assignment_from_file,
                "score": grade_result['score'],
                "letter_grade": grade_result['letter_grade'],
                "feedback": grade_result.get('feedback', ''),
                "student_content": student_content[:5000],
                "breakdown": grade_result.get('breakdown', {})
            })

        # Export CSVs and emails
        if len(all_grades) > 0:
            grading_state["log"].append("")
            grading_state["log"].append("Exporting results...")

            # Focus CSVs (by assignment)
            export_focus_csv(all_grades, output_folder, ASSIGNMENT_NAME)
            grading_state["log"].append("  Focus CSVs created")

            # Detailed report
            export_detailed_report(all_grades, output_folder, ASSIGNMENT_NAME)
            grading_state["log"].append("  Detailed report created")

            # Email files
            save_emails_to_folder(all_grades, output_folder)
            grading_state["log"].append("  Email files created")

            # Master tracking CSV
            save_to_master_csv(all_grades, output_folder)
            grading_state["log"].append("  Master grades updated")

        grading_state["log"].append("")
        grading_state["log"].append("=" * 50)

        if grading_state.get("stop_requested", False):
            grading_state["log"].append(f"GRADING STOPPED - {len(all_grades)} files saved")
            grading_state["log"].append("Restart to continue with remaining files")
        else:
            grading_state["log"].append("GRADING COMPLETE!")

        grading_state["log"].append(f"Results saved to: {output_folder}")
        grading_state["complete"] = True

    except Exception as e:
        grading_state["error"] = str(e)
        grading_state["log"].append(f"Error: {str(e)}")
    finally:
        grading_state["is_running"] = False
        grading_state["stop_requested"] = False


# ══════════════════════════════════════════════════════════════
# REGISTER MODULAR ROUTES
# ══════════════════════════════════════════════════════════════

from routes import register_routes
register_routes(app, grading_state, run_grading_thread, reset_state)


# ══════════════════════════════════════════════════════════════
# GRADING START ROUTE (kept here due to thread management)
# ══════════════════════════════════════════════════════════════

@app.route('/api/grade', methods=['POST'])
def start_grading():
    """Start the grading process."""
    global grading_state

    if grading_state["is_running"]:
        return jsonify({"error": "Grading already in progress"}), 400

    data = request.json
    assignments_folder = data.get('assignments_folder', '/Users/alexc/Library/CloudStorage/OneDrive-VolusiaCountySchools/Assignments')
    output_folder = data.get('output_folder', '/Users/alexc/Downloads/Graider/Results')
    roster_file = data.get('roster_file', '/Users/alexc/Downloads/Graider/all_students_updated.xlsx')
    grading_period = data.get('grading_period', 'Q3')

    # Get custom assignment config and global AI notes
    assignment_config = data.get('assignmentConfig')
    global_ai_notes = data.get('globalAINotes', '')

    if not os.path.exists(assignments_folder):
        return jsonify({"error": f"Assignments folder not found: {assignments_folder}"}), 400
    if not os.path.exists(roster_file):
        return jsonify({"error": f"Roster file not found: {roster_file}"}), 400

    reset_state()
    grading_state["is_running"] = True

    thread = threading.Thread(
        target=run_grading_thread,
        args=(assignments_folder, output_folder, roster_file, assignment_config, global_ai_notes, grading_period)
    )
    thread.start()

    return jsonify({"status": "started"})


# ══════════════════════════════════════════════════════════════
# STATIC FILE SERVING
# ══════════════════════════════════════════════════════════════

@app.route('/')
def serve_frontend():
    """Serve the React frontend."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    """Serve static files or fall back to index.html for SPA routing."""
    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import webbrowser

    def open_browser():
        """Open browser after short delay to let server start."""
        import time
        time.sleep(1.5)
        webbrowser.open('http://localhost:3000')

    print()
    print("+" + "=" * 50 + "+")
    print("|  Graider - AI-Powered Assignment Grading         |")
    print("+" + "=" * 50 + "+")
    print("|                                                  |")
    print("|  Open in browser: http://localhost:3000          |")
    print("|                                                  |")
    print("|  Press Ctrl+C to stop                            |")
    print("+" + "=" * 50 + "+")
    print()

    # Auto-open browser
    threading.Thread(target=open_browser, daemon=True).start()

    app.run(host='0.0.0.0', port=3000, debug=False)
