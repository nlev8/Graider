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
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Import student history for progress tracking
try:
    from backend.student_history import add_assignment_to_history, load_student_history, detect_baseline_deviation, get_baseline_summary
except ImportError:
    try:
        from student_history import add_assignment_to_history, load_student_history, detect_baseline_deviation, get_baseline_summary
    except ImportError:
        # Fallback if module not available
        def add_assignment_to_history(student_id, result):
            return None
        def load_student_history(student_id):
            return None
        def detect_baseline_deviation(student_id, result):
            return {"flag": "normal", "reasons": [], "details": {}}
        def get_baseline_summary(student_id):
            return None

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

RESULTS_FILE = os.path.expanduser("~/.graider_results.json")
AUDIT_LOG_FILE = os.path.expanduser("~/.graider_audit.log")
SETTINGS_FILE = os.path.expanduser("~/.graider_settings.json")

# ══════════════════════════════════════════════════════════════
# FERPA COMPLIANCE - AUDIT LOGGING
# ══════════════════════════════════════════════════════════════

def audit_log(action: str, details: str = "", user: str = "teacher"):
    """
    FERPA Compliance: Log all data access and modifications.
    Logs are kept locally and do not contain actual student data.
    """
    try:
        timestamp = datetime.now().isoformat()
        log_entry = f"{timestamp} | {user} | {action} | {details}\n"

        with open(AUDIT_LOG_FILE, 'a') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Audit log error: {e}")


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
                    logs.append({
                        'timestamp': parts[0],
                        'user': parts[1],
                        'action': parts[2],
                        'details': parts[3] if len(parts) > 3 else ''
                    })
            return logs[::-1]  # Newest first
    except Exception as e:
        print(f"Error reading audit logs: {e}")
        return []


def load_saved_results():
    """Load results from file on startup."""
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, 'r') as f:
                results = json.load(f)
                # Add placeholder timestamp to results that don't have one
                for r in results:
                    if 'graded_at' not in r:
                        r['graded_at'] = None  # Will show as '-' in frontend
                return results
        except:
            pass
    return []

def save_results(results):
    """Save results to file for persistence."""
    try:
        with open(RESULTS_FILE, 'w') as f:
            json.dump(results, f, indent=2)
    except Exception as e:
        print(f"Error saving results: {e}")

grading_state = {
    "is_running": False,
    "stop_requested": False,
    "progress": 0,
    "total": 0,
    "current_file": "",
    "log": [],
    "results": load_saved_results(),  # Load saved results on startup
    "complete": False,
    "error": None
}


def reset_state(clear_results=False):
    global grading_state
    grading_state.update({
        "is_running": False,
        "stop_requested": False,
        "progress": 0,
        "total": 0,
        "current_file": "",
        "log": [],
        "results": [] if clear_results else grading_state.get("results", []),
        "complete": False,
        "error": None
    })


# ══════════════════════════════════════════════════════════════
# GRADING THREAD
# ══════════════════════════════════════════════════════════════

def run_grading_thread(assignments_folder, output_folder, roster_file, assignment_config=None, global_ai_notes='', grading_period='Q3', grade_level='7', subject='Social Studies', teacher_name='', school_name='', selected_files=None, ai_model='gpt-4o-mini', skip_verified=False):
    """Run the grading process in a background thread.

    Args:
        selected_files: List of filenames to grade, or None to grade all files
        ai_model: OpenAI model to use ('gpt-4o' or 'gpt-4o-mini')
        skip_verified: If True, skip files that were previously graded with verified status
    """
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

    # Extract custom markers, notes, and response sections from selected config (fallback)
    fallback_markers = []
    fallback_notes = ''
    fallback_sections = []
    if assignment_config:
        fallback_markers = assignment_config.get('customMarkers', [])
        fallback_notes = assignment_config.get('gradingNotes', '')
        fallback_sections = assignment_config.get('responseSections', [])

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

        # Load already graded files from master CSV AND in-memory results
        already_graded = set()

        # Check master CSV
        master_file = os.path.join(output_folder, "master_grades.csv")
        if os.path.exists(master_file):
            try:
                with open(master_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        filename = row.get('Filename', '')
                        if filename:
                            already_graded.add(filename)
            except:
                pass

        # Also check in-memory results (loaded from saved JSON)
        # Track which files are verified (have markers/config) for skip_verified option
        verified_files = set()
        for r in grading_state.get("results", []):
            if r.get("filename"):
                already_graded.add(r["filename"])
                # Track verified status for skip_verified filtering
                if r.get("marker_status") == "verified":
                    verified_files.add(r["filename"])

        if already_graded:
            grading_state["log"].append(f"Found {len(already_graded)} previously graded files")
            if verified_files:
                grading_state["log"].append(f"  ({len(verified_files)} verified, {len(already_graded) - len(verified_files)} unverified)")

        grading_state["log"].append("Loading student roster...")
        roster = load_roster(roster_file)
        grading_state["log"].append(f"Loaded {len(roster)//2} students")

        assignment_path = Path(assignments_folder)
        all_files = []
        for ext in ['*.docx', '*.txt', '*.jpg', '*.jpeg', '*.png', '*.pdf']:
            all_files.extend(assignment_path.glob(ext))

        # Filter by selected files if provided
        if selected_files is not None and len(selected_files) > 0:
            selected_set = set(selected_files)
            all_files = [f for f in all_files if f.name in selected_set]
            grading_state["log"].append(f"Grading {len(all_files)} selected files")
        else:
            grading_state["log"].append(f"Found {len(all_files)} total files")

        # Filter out already graded files (only if not using selection)
        if selected_files is None:
            new_files = [f for f in all_files if f.name not in already_graded]
            skipped = len(all_files) - len(new_files)
            if skipped > 0:
                grading_state["log"].append(f"Skipping {skipped} already-graded files")
        else:
            # When files are selected, grade them even if previously graded (re-grade)
            # BUT if skip_verified is True, skip files that were previously verified
            if skip_verified and verified_files:
                new_files = [f for f in all_files if f.name not in verified_files]
                skipped_verified = len(all_files) - len(new_files)
                if skipped_verified > 0:
                    grading_state["log"].append(f"Skipping {skipped_verified} verified grades (regrading only unverified)")
            else:
                new_files = all_files

        grading_state["total"] = len(new_files)
        grading_state["log"].append(f"Queued {len(new_files)} files for grading")

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
                file_sections = matched_config.get('responseSections', [])
                matched_title = matched_config.get('title', 'Unknown')
                is_completion_only = matched_config.get('completionOnly', False)
                grading_state["log"].append(f"  Matched config: {matched_title}")
            else:
                file_markers = fallback_markers
                file_notes = fallback_notes
                file_sections = fallback_sections
                is_completion_only = False

            # Handle completion-only assignments (track submission without AI grading)
            if is_completion_only:
                grading_state["log"].append(f"  Completion only - recording submission")
                # Use assignment title from matched config
                assignment_title = matched_title if matched_config else ASSIGNMENT_NAME
                # Record as submitted with full points
                grading_state["results"].append({
                    "student_name": student_info['student_name'],
                    "student_id": student_info['student_id'],
                    "email": student_info.get('email', ''),
                    "filename": filepath.name,
                    "filepath": str(filepath),
                    "assignment": assignment_title,
                    "score": 100,
                    "letter_grade": "SUBMITTED",
                    "feedback": "Completion-only assignment - submitted successfully.",
                    "student_content": "",
                    "full_content": "",
                    "breakdown": {},
                    "student_responses": [],
                    "unanswered_questions": [],
                    "authenticity_flag": "clean",
                    "authenticity_reason": "",
                    "baseline_deviation": {"flag": "normal", "reasons": [], "details": {}},
                    "skills_demonstrated": {},
                    "marker_status": "completion_only",
                    "graded_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                # Add to grades for CSV export
                all_grades.append({
                    **student_info,
                    "score": 100,
                    "letter_grade": "SUBMITTED",
                    "feedback": "Completion-only assignment - submitted successfully.",
                    "filename": filepath.name,
                    "assignment": assignment_title,
                    "grading_period": grading_period,
                    "has_markers": False
                })
                continue  # Skip to next file

            # Build combined AI notes for this file
            file_ai_notes = ''
            if global_ai_notes:
                file_ai_notes += f"GLOBAL GRADING INSTRUCTIONS:\n{global_ai_notes}\n\n"
            if file_notes:
                file_ai_notes += f"ASSIGNMENT-SPECIFIC INSTRUCTIONS:\n{file_notes}\n\n"

            # Add response sections (highlighted areas where student work should be found)
            if file_sections:
                sections_text = "HIGHLIGHTED RESPONSE SECTIONS (Focus on content within these ranges):\n"
                for idx, section in enumerate(file_sections, 1):
                    start = section.get('start', '')
                    end = section.get('end')
                    if end:
                        sections_text += f"  {idx}. From \"{start}\" to \"{end}\"\n"
                    else:
                        sections_text += f"  {idx}. From \"{start}\" to end of document\n"
                sections_text += "\nStudent responses should be found WITHIN these highlighted sections. Content outside these sections is likely teacher instructions or questions.\n"
                file_ai_notes += sections_text

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
                # Send FULL document to AI - let it identify student work
                # The AI is better at distinguishing questions from answers
                full_doc_content = file_data["content"]
                grade_data = {"type": "text", "content": full_doc_content}
                grading_state["log"].append(f"  Document: {len(full_doc_content)} chars")
            else:
                grading_state["log"].append(f"  Image file")
                grade_data = file_data

            grading_state["log"].append(f"  Grading with {ai_model}...")
            grade_result = grade_assignment(student_info['student_name'], grade_data, file_ai_notes, grade_level, subject, ai_model, student_info.get('student_id'))

            # Restore original markers
            STUDENT_WORK_MARKERS.clear()
            STUDENT_WORK_MARKERS.extend(original_markers)

            # Check for API/network errors - stop grading to prevent bad grades
            if grade_result.get('letter_grade') == 'ERROR':
                error_msg = grade_result.get('feedback', 'Unknown API error')
                grading_state["log"].append("")
                grading_state["log"].append("=" * 50)
                grading_state["log"].append("⚠️  GRADING STOPPED - API ERROR")
                grading_state["log"].append("=" * 50)
                grading_state["log"].append(f"Error: {error_msg}")
                grading_state["log"].append("")
                grading_state["log"].append("Please check:")
                grading_state["log"].append("  • Internet connection")
                grading_state["log"].append("  • OpenAI API key is valid")
                grading_state["log"].append("  • API service is available")
                grading_state["log"].append("")
                grading_state["log"].append(f"Progress saved: {len(all_grades)} assignments graded")
                grading_state["log"].append("Fix the issue and restart to continue.")
                grading_state["error"] = f"API Error: {error_msg}"
                grading_state["complete"] = True
                grading_state["is_running"] = False
                # Save any progress made
                if grading_state["results"]:
                    save_results(grading_state["results"])
                return

            grading_state["log"].append(f"  Score: {grade_result['score']} ({grade_result['letter_grade']})")

            # Use assignment title from matched config (full name, not truncated filename)
            assignment_title = matched_title if matched_config else ASSIGNMENT_NAME

            # Get student content for review - show full document
            if file_data["type"] == "text":
                full_content = file_data.get("content", "")
                # Show full document - AI grades the whole thing
                student_content = full_content
            else:
                student_content = "[Image file - view in original document]"
                full_content = "[Image file - view in original document]"

            # Build full grade record for export
            grade_record = {
                **student_info,
                **grade_result,
                "filename": filepath.name,
                "assignment": assignment_title,
                "grading_period": grading_period,
                "has_markers": len(markers_found) > 0
            }
            all_grades.append(grade_record)

            # Check for baseline deviation BEFORE saving to history (compare to existing baseline)
            baseline_deviation = {"flag": "normal", "reasons": [], "details": {}}
            if student_info.get('student_id') and student_info['student_id'] != "UNKNOWN":
                try:
                    baseline_deviation = detect_baseline_deviation(student_info['student_id'], grade_result)
                    if baseline_deviation.get('flag') != 'normal':
                        grading_state["log"].append(f"  ⚠️  Baseline deviation: {baseline_deviation.get('flag')}")
                except Exception as e:
                    print(f"  Note: Could not check baseline deviation: {e}")

            # Save to student history for progress tracking
            if student_info.get('student_id') and student_info['student_id'] != "UNKNOWN":
                try:
                    add_assignment_to_history(student_info['student_id'], grade_record)
                except Exception as e:
                    print(f"  Note: Could not update student history: {e}")

            # Determine marker status: verified if has config with markers/notes/sections
            # A file is "verified" if graded with an assignment config (markers, notes, or response sections)
            has_config = matched_config is not None
            has_custom_markers = len(file_markers) > 0
            has_grading_notes = bool(file_notes.strip()) if file_notes else False
            has_response_sections = len(file_sections) > 0
            is_verified = has_config or has_custom_markers or has_grading_notes or has_response_sections
            marker_status = "verified" if is_verified else "unverified"

            if marker_status == "unverified":
                grading_state["log"].append(f"  ⚠️  UNVERIFIED: No assignment config - grade may be inaccurate")

            grading_state["results"].append({
                "student_name": student_info['student_name'],
                "student_id": student_info['student_id'],
                "email": student_info.get('email', ''),
                "filename": filepath.name,
                "filepath": str(filepath),
                "assignment": assignment_title,
                "score": grade_result['score'],
                "letter_grade": grade_result['letter_grade'],
                "feedback": grade_result.get('feedback', ''),
                "student_content": student_content[:5000],
                "full_content": full_content[:10000],
                "breakdown": grade_result.get('breakdown', {}),
                "student_responses": grade_result.get('student_responses', []),
                "unanswered_questions": grade_result.get('unanswered_questions', []),
                "authenticity_flag": grade_result.get('authenticity_flag', 'clean'),
                "authenticity_reason": grade_result.get('authenticity_reason', ''),
                "baseline_deviation": baseline_deviation,
                "skills_demonstrated": grade_result.get('skills_demonstrated', {}),
                "marker_status": marker_status,
                "graded_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
            save_emails_to_folder(all_grades, output_folder, teacher_name, subject, school_name)
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

        # Save results to file for persistence across restarts
        save_results(grading_state["results"])

    except Exception as e:
        grading_state["error"] = str(e)
        grading_state["log"].append(f"Error: {str(e)}")
    finally:
        grading_state["is_running"] = False
        grading_state["stop_requested"] = False
        # Also save on stop/error to preserve partial results
        if grading_state["results"]:
            save_results(grading_state["results"])


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
    grade_level = data.get('grade_level', '7')
    subject = data.get('subject', 'US History')
    teacher_name = data.get('teacher_name', '')
    school_name = data.get('school_name', '')
    ai_model = data.get('ai_model', 'gpt-4o-mini')

    # Get custom assignment config and global AI notes
    assignment_config = data.get('assignmentConfig')
    global_ai_notes = data.get('globalAINotes', '')

    # Get selected files (if any) for selective grading
    selected_files = data.get('selectedFiles', None)  # None means grade all

    # Skip verified grades on regrade (only regrade unverified assignments)
    skip_verified = data.get('skipVerified', False)

    if not os.path.exists(assignments_folder):
        return jsonify({"error": f"Assignments folder not found: {assignments_folder}"}), 400
    if not os.path.exists(roster_file):
        return jsonify({"error": f"Roster file not found: {roster_file}"}), 400

    reset_state()
    grading_state["is_running"] = True

    # FERPA: Audit log grading session start
    file_count = len(selected_files) if selected_files else "all"
    audit_log("START_GRADING", f"Started grading session for {subject} grade {grade_level} ({file_count} files)")

    thread = threading.Thread(
        target=run_grading_thread,
        args=(assignments_folder, output_folder, roster_file, assignment_config, global_ai_notes, grading_period, grade_level, subject, teacher_name, school_name, selected_files, ai_model, skip_verified)
    )
    thread.start()

    return jsonify({"status": "started"})


# ══════════════════════════════════════════════════════════════
# INDIVIDUAL FILE GRADING (for paper/handwritten assignments)
# ══════════════════════════════════════════════════════════════

@app.route('/api/grade-individual', methods=['POST'])
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

    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    # Parse student info from CSV if provided
    student_info = None
    if student_info_str:
        try:
            student_info = json.loads(student_info_str)
        except:
            pass

    # Parse assignment config if provided
    assignment_config = None
    if assignment_config_str:
        try:
            assignment_config = json.loads(assignment_config_str)
        except:
            pass

    # Build AI notes from config
    file_ai_notes = global_ai_notes or ''
    if assignment_config:
        if assignment_config.get('gradingNotes'):
            file_ai_notes = assignment_config['gradingNotes'] + '\n\n' + file_ai_notes

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

        # Grade the assignment
        grade_result = grade_assignment(student_name, grade_data, file_ai_notes, grade_level, subject, ai_model, individual_student_id)

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
            "score": grade_result.get('score', 0),
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
                print(f"  Note: Could not update student history: {e}")

        # FERPA audit log
        audit_log("GRADE_INDIVIDUAL", f"Graded individual upload for student (image-based, GPT-4o)")

        return jsonify(result)

    except Exception as e:
        print(f"Individual grading error: {e}")
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
# LIST FILES IN FOLDER
# ══════════════════════════════════════════════════════════════

@app.route('/api/list-files', methods=['POST'])
def list_files():
    """List assignment files in a folder for selective grading."""
    data = request.json
    folder = data.get('folder', '')

    if not folder or not os.path.exists(folder):
        return jsonify({"files": [], "error": "Folder not found"})

    # Get already graded files
    already_graded = set()
    for result in grading_state.get("results", []):
        if result.get("filename"):
            already_graded.add(result["filename"])

    # Scan folder for supported files
    supported_extensions = ['.docx', '.txt', '.jpg', '.jpeg', '.png', '.pdf']
    files = []

    try:
        for f in os.listdir(folder):
            ext = os.path.splitext(f)[1].lower()
            if ext in supported_extensions:
                filepath = os.path.join(folder, f)
                stat = os.stat(filepath)
                files.append({
                    "name": f,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "graded": f in already_graded
                })

        # Sort by name
        files.sort(key=lambda x: x["name"].lower())
        return jsonify({"files": files})
    except Exception as e:
        return jsonify({"files": [], "error": str(e)})


# ══════════════════════════════════════════════════════════════
# DELETE SINGLE RESULT
# ══════════════════════════════════════════════════════════════

@app.route('/api/delete-result', methods=['POST'])
def delete_single_result():
    """Delete a single grading result by filename."""
    global grading_state

    if grading_state["is_running"]:
        return jsonify({"error": "Cannot delete results while grading is in progress"}), 400

    data = request.json
    filename = data.get('filename', '')

    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    # Find and remove the result from state
    original_count = len(grading_state["results"])
    grading_state["results"] = [
        r for r in grading_state["results"]
        if r.get('filename', '') != filename
    ]

    if len(grading_state["results"]) == original_count:
        return jsonify({"error": "Result not found"}), 404

    # Save updated results to file
    save_results(grading_state["results"])

    # FERPA: Audit log the deletion
    audit_log("DELETE_RESULT", f"Deleted result for file: {filename[:30]}...")

    return jsonify({
        "status": "deleted",
        "filename": filename,
        "remaining_count": len(grading_state["results"])
    })


# ══════════════════════════════════════════════════════════════
# FERPA COMPLIANCE - DATA MANAGEMENT
# ══════════════════════════════════════════════════════════════

@app.route('/api/ferpa/delete-all-data', methods=['POST'])
def delete_all_student_data():
    """
    FERPA Compliance: Securely delete all student data.
    This includes grading results, settings, and cached data.
    """
    global grading_state

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
        audit_log("DELETE_ALL_DATA_ERROR", str(e))
        return jsonify({"error": f"Failed to delete data: {str(e)}"}), 500


@app.route('/api/ferpa/audit-log', methods=['GET'])
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


@app.route('/api/ferpa/data-summary', methods=['GET'])
def get_data_summary():
    """
    FERPA Compliance: Get summary of stored student data.
    Helps teachers understand what data is stored locally.
    """
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


@app.route('/api/ferpa/export-data', methods=['GET'])
def export_student_data():
    """
    FERPA Compliance: Export all student data for portability.
    Supports parent/guardian data requests.
    """
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


# ══════════════════════════════════════════════════════════════
# STUDENT PROGRESS HISTORY
# ══════════════════════════════════════════════════════════════

@app.route('/api/student-history/<student_id>', methods=['GET'])
def get_student_history_api(student_id):
    """Get a student's grading history and progress patterns."""
    history = load_student_history(student_id)
    if not history:
        return jsonify({"error": "No history found"}), 404

    # FERPA: Audit log access
    audit_log("VIEW_STUDENT_HISTORY", f"Viewed history for student ID: {student_id[:6]}...")

    return jsonify(history)


@app.route('/api/student-baseline/<student_id>', methods=['GET'])
def get_student_baseline_api(student_id):
    """Get a student's baseline performance metrics for deviation detection."""
    baseline = get_baseline_summary(student_id)
    if not baseline:
        return jsonify({"error": "Insufficient history for baseline (need 3+ assignments)"}), 404

    # FERPA: Audit log access
    audit_log("VIEW_STUDENT_BASELINE", f"Viewed baseline for student ID: {student_id[:6]}...")

    return jsonify(baseline)


@app.route('/api/retranslate-feedback', methods=['POST'])
def retranslate_feedback():
    """Re-translate English feedback to the target language."""
    import openai

    data = request.json
    english_feedback = data.get('english_feedback', '')
    target_language = data.get('target_language', 'spanish')

    if not english_feedback:
        return jsonify({"error": "No feedback provided"})

    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"Translate the following teacher feedback to {target_language}. Keep the same warm, encouraging tone. Only output the translation, nothing else.\n\nFeedback:\n{english_feedback}"
            }],
            temperature=0.3
        )

        translation = response.choices[0].message.content.strip()
        return jsonify({"translation": translation})

    except Exception as e:
        return jsonify({"error": str(e)})


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
