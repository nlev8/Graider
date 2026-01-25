"""
Grading API routes for Graider.
Handles grading status, starting/stopping grading, and file checking.

NOTE: The actual grading thread logic remains in app.py for Phase 1
due to tight coupling with global state. Full extraction planned for Phase 3.
"""
import os
import csv
from pathlib import Path
from flask import Blueprint, request, jsonify

grading_bp = Blueprint('grading', __name__)

# These will be set by app.py during initialization
grading_state = None
run_grading_thread = None
reset_state = None


def init_grading_routes(state_ref, thread_fn, reset_fn):
    """Initialize grading routes with references from main app."""
    global grading_state, run_grading_thread, reset_state
    grading_state = state_ref
    run_grading_thread = thread_fn
    reset_state = reset_fn


@grading_bp.route('/api/status')
def get_status():
    """Get current grading status."""
    if grading_state is None:
        return jsonify({"error": "Grading not initialized"}), 500
    return jsonify(grading_state)


@grading_bp.route('/api/check-new-files', methods=['POST'])
def check_new_files():
    """Check for new files that haven't been graded yet."""
    data = request.json
    assignments_folder = data.get('folder', '')
    output_folder = data.get('output_folder', '')

    if not assignments_folder or not os.path.exists(assignments_folder):
        return jsonify({"error": "Folder not found", "new_files": 0})

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
        except:
            pass

    # Count new files
    all_files = []
    for ext in ['*.docx', '*.txt', '*.jpg', '*.jpeg', '*.png']:
        all_files.extend(Path(assignments_folder).glob(ext))

    new_files = [f for f in all_files if f.name not in already_graded]

    return jsonify({
        "total_files": len(all_files),
        "already_graded": len(already_graded),
        "new_files": len(new_files),
        "new_file_names": [f.name for f in new_files[:5]]
    })


@grading_bp.route('/api/stop-grading', methods=['POST'])
def stop_grading():
    """Stop grading and save progress."""
    if grading_state is None:
        return jsonify({"error": "Grading not initialized"}), 500

    if grading_state["is_running"]:
        grading_state["stop_requested"] = True
        grading_state["log"].append("")
        grading_state["log"].append("Stop requested... saving progress...")
        return jsonify({"stopped": True, "message": "Stop requested, saving progress..."})

    return jsonify({"stopped": False, "message": "Grading not running"})


# NOTE: The /api/grade POST route and run_grading_thread function
# remain in app.py for Phase 1 due to their complexity and tight
# coupling with global state. They will be extracted in Phase 3
# when we implement proper state management.
