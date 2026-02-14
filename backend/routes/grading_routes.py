"""
Grading API routes for Graider.
Handles grading status, starting/stopping grading, and file checking.

NOTE: The actual grading thread logic remains in app.py for Phase 1
due to tight coupling with global state. Full extraction planned for Phase 3.
"""
import os
import csv
import json
from pathlib import Path
from datetime import datetime
from flask import Blueprint, request, jsonify

grading_bp = Blueprint('grading', __name__)

EXPORTS_DIR = os.path.expanduser("~/.graider_exports")
FOCUS_EXPORTS_DIR = os.path.join(EXPORTS_DIR, "focus")
OUTLOOK_EXPORTS_DIR = os.path.join(EXPORTS_DIR, "outlook")

for _dir in [EXPORTS_DIR, FOCUS_EXPORTS_DIR, OUTLOOK_EXPORTS_DIR]:
    os.makedirs(_dir, exist_ok=True)

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
        return jsonify({"error": f"Folder not found: {assignments_folder}", "new_files": 0})

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

    # Also check in-memory results (from grading_state)
    if grading_state and grading_state.get("results"):
        for r in grading_state["results"]:
            if r.get("filename"):
                already_graded.add(r["filename"])

    # Count new files
    all_files = []
    for ext in ['*.docx', '*.txt', '*.jpg', '*.jpeg', '*.png']:
        all_files.extend(Path(assignments_folder).glob(ext))

    new_files = [f for f in all_files if f.name not in already_graded]

    return jsonify({
        "total_files": len(all_files),
        "already_graded": len(already_graded),
        "new_files": len(new_files),
        "new_file_names": [f.name for f in new_files[:5]],
        "folder_checked": assignments_folder
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


@grading_bp.route('/api/clear-results', methods=['POST'])
def clear_results():
    """Clear grading results. Optionally filter by assignment name."""
    if grading_state is None:
        return jsonify({"error": "Grading not initialized"}), 500

    if grading_state["is_running"]:
        return jsonify({"error": "Cannot clear results while grading is in progress"}), 400

    data = request.get_json() or {}
    filenames_filter = data.get("filenames")  # Optional: only clear specific filenames

    import os
    import json
    results_file = os.path.expanduser("~/.graider_results.json")
    output_folder = os.path.expanduser("~/Downloads/Graider/Results")
    master_file = os.path.join(output_folder, "master_grades.csv")

    if filenames_filter and isinstance(filenames_filter, list):
        # Clear only results matching specific filenames
        filenames_set = set(filenames_filter)
        original_count = len(grading_state.get("results", []))

        grading_state["results"] = [
            r for r in grading_state.get("results", [])
            if r.get("filename") not in filenames_set
        ]
        cleared_count = original_count - len(grading_state["results"])

        # Also update the saved JSON file
        if os.path.exists(results_file):
            try:
                with open(results_file, 'r') as f:
                    saved_results = json.load(f)
                saved_results = [r for r in saved_results if r.get("filename") not in filenames_set]
                with open(results_file, 'w') as f:
                    json.dump(saved_results, f)
            except:
                pass

        # Also remove from master_grades.csv
        if os.path.exists(master_file) and filenames_set:
            try:
                rows_to_keep = []
                with open(master_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames
                    for row in reader:
                        if row.get('Filename') not in filenames_set:
                            rows_to_keep.append(row)

                with open(master_file, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows_to_keep)
                print(f"Removed {cleared_count} entries from master_grades.csv")
            except Exception as e:
                print(f"Could not update master_grades.csv: {e}")

        return jsonify({"status": "cleared", "cleared_count": cleared_count})
    else:
        # Clear all results
        cleared_count = len(grading_state.get("results", []))
        grading_state["results"] = []
        grading_state["log"] = []
        grading_state["complete"] = False

        # Clear saved results file
        if os.path.exists(results_file):
            try:
                os.remove(results_file)
            except:
                pass

        # Also clear master_grades.csv so files can be regraded
        if os.path.exists(master_file):
            try:
                os.remove(master_file)
                print(f"🗑️ Removed master_grades.csv")
            except Exception as e:
                print(f"⚠️ Could not remove master_grades.csv: {e}")

        return jsonify({"status": "cleared", "cleared_count": cleared_count})


# NOTE: delete-result route is in app.py to avoid duplication


def _normalize_assign_for_csv(name):
    """Normalize assignment name for CSV matching — strips (1), .docx, .pdf suffixes."""
    import re
    n = name.strip()
    n = re.sub(r'\s*\(\d+\)\s*$', '', n)
    n = re.sub(r'\.docx?\s*$', '', n, flags=re.IGNORECASE)
    n = re.sub(r'\.pdf\s*$', '', n, flags=re.IGNORECASE)
    return n.strip().lower()


def _match_assignment_in_csv(csv_assign, target_assign):
    """Match assignment names, handling truncated CSV names.
    Returns True if csv_assign matches target_assign (exact or prefix)."""
    csv_norm = _normalize_assign_for_csv(csv_assign)
    target_norm = _normalize_assign_for_csv(target_assign)
    if csv_norm == target_norm:
        return True
    # Handle truncated CSV names: if CSV name is a prefix of the target (min 20 chars)
    if len(csv_norm) >= 20 and target_norm.startswith(csv_norm):
        return True
    if len(target_norm) >= 20 and csv_norm.startswith(target_norm):
        return True
    return False


def _sync_result_to_master_csv(result):
    """Sync an updated result back to master_grades.csv so the Assistant sees fresh data."""
    output_folder = os.path.expanduser("~/Downloads/Graider/Results")
    master_file = os.path.join(output_folder, "master_grades.csv")
    if not os.path.exists(master_file):
        return

    student_id = str(result.get('student_id', ''))
    assignment = result.get('assignment', '')
    if not student_id or not assignment:
        return

    breakdown = result.get('breakdown', {})
    score = result.get('score', 0)
    letter_grade = result.get('letter_grade', '')
    feedback = result.get('feedback', '')

    try:
        with open(master_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames
            rows = list(reader)

        updated = False
        for row in rows:
            if row.get('Student ID', '') == student_id and _match_assignment_in_csv(row.get('Assignment', ''), assignment):
                row['Overall Score'] = str(score)
                row['Letter Grade'] = letter_grade
                row['Content Accuracy'] = str(breakdown.get('content_accuracy', row.get('Content Accuracy', '')))
                row['Completeness'] = str(breakdown.get('completeness', row.get('Completeness', '')))
                row['Writing Quality'] = str(breakdown.get('writing_quality', row.get('Writing Quality', '')))
                row['Effort Engagement'] = str(breakdown.get('effort_engagement', row.get('Effort Engagement', '')))
                row['Feedback'] = feedback
                updated = True
                break

        if updated:
            with open(master_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=header)
                writer.writeheader()
                writer.writerows(rows)
    except Exception as e:
        print(f"Could not sync to master_grades.csv: {e}")


@grading_bp.route('/api/update-result', methods=['POST'])
def update_result():
    """Update a single grading result (score, feedback, etc.)."""
    import json

    if grading_state is None:
        return jsonify({"error": "Grading not initialized"}), 500

    data = request.json
    filename = data.get('filename', '')

    if not filename:
        return jsonify({"error": "Filename is required"}), 400

    # Find the result to update
    result_index = None
    for i, r in enumerate(grading_state["results"]):
        if r.get('filename', '') == filename:
            result_index = i
            break

    if result_index is None:
        return jsonify({"error": "Result not found"}), 404

    # Update allowed fields
    allowed_fields = ['score', 'letter_grade', 'feedback', 'verified']
    for field in allowed_fields:
        if field in data:
            grading_state["results"][result_index][field] = data[field]

    # Recalculate letter grade if score changed
    if 'score' in data:
        score = int(data['score'])
        grading_state["results"][result_index]['letter_grade'] = (
            'A' if score >= 90 else
            'B' if score >= 80 else
            'C' if score >= 70 else
            'D' if score >= 60 else 'F'
        )

    # Save to results JSON
    results_file = os.path.expanduser("~/.graider_results.json")
    try:
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(grading_state["results"], f, indent=2)
    except Exception:
        pass

    # Sync updated fields to master_grades.csv so the Assistant sees fresh data
    updated_result = grading_state["results"][result_index]
    _sync_result_to_master_csv(updated_result)

    return jsonify({
        "status": "updated",
        "result": updated_result
    })


# NOTE: The /api/grade POST route and run_grading_thread function
# remain in app.py for Phase 1 due to their complexity and tight
# coupling with global state. They will be extracted in Phase 3
# when we implement proper state management.


# =============================================================================
# STEM SUBJECT GRADING ENDPOINTS
# =============================================================================

@grading_bp.route('/api/grade-math', methods=['POST'])
def grade_math():
    """
    Grade a math question using SymPy for equivalence checking.

    Request body:
    {
        "question": {
            "correctAnswer": "\\frac{1}{2}",
            "acceptEquivalent": true,
            "showWork": false,
            "points": 1
        },
        "studentAnswer": "0.5"
    }
    """
    try:
        from backend.services.stem_grading import grade_math_question
    except ImportError:
        return jsonify({"error": "STEM grading service not available"}), 500

    data = request.json
    question = data.get('question', {})
    student_answer = data.get('studentAnswer', '')

    result = grade_math_question(question, student_answer)
    return jsonify(result)


@grading_bp.route('/api/grade-data-table', methods=['POST'])
def grade_data_table():
    """
    Grade a science data table with tolerance for numerical values.

    Request body:
    {
        "expectedTable": {
            "headers": ["Time (s)", "Temperature (°C)"],
            "units": ["s", "°C"],
            "data": [["0", "20"], ["30", "25"], ["60", "28"]]
        },
        "studentTable": {
            "headers": ["Time (s)", "Temperature (°C)"],
            "units": ["s", "°C"],
            "data": [["0", "20"], ["30", "24.5"], ["60", "29"]]
        },
        "tolerancePercent": 5
    }
    """
    try:
        from backend.services.stem_grading import grade_data_table as grade_table
    except ImportError:
        return jsonify({"error": "STEM grading service not available"}), 500

    data = request.json
    expected_table = data.get('expectedTable', {})
    student_table = data.get('studentTable', {})
    tolerance = data.get('tolerancePercent', 5.0)

    result = grade_table(expected_table, student_table, tolerance)
    return jsonify(result)


@grading_bp.route('/api/grade-coordinates', methods=['POST'])
def grade_coordinates():
    """
    Grade a geography coordinate question with distance tolerance.

    Request body:
    {
        "expected": {"latitude": 40.7128, "longitude": -74.0060},
        "student": {"latitude": 40.72, "longitude": -74.01},
        "toleranceKm": 50
    }
    """
    try:
        from backend.services.stem_grading import grade_coordinate_question
    except ImportError:
        return jsonify({"error": "STEM grading service not available"}), 500

    data = request.json
    expected = data.get('expected', {})
    student = data.get('student', {})
    tolerance_km = data.get('toleranceKm', 50)

    result = grade_coordinate_question(expected, student, tolerance_km)
    return jsonify(result)


@grading_bp.route('/api/grade-place-name', methods=['POST'])
def grade_place_name():
    """
    Grade a geography place name question accepting alternatives.

    Request body:
    {
        "expectedNames": ["United Kingdom", "UK", "Britain", "Great Britain"],
        "studentAnswer": "UK"
    }
    """
    try:
        from backend.services.stem_grading import grade_place_name as grade_name
    except ImportError:
        return jsonify({"error": "STEM grading service not available"}), 500

    data = request.json
    expected_names = data.get('expectedNames', [])
    student_answer = data.get('studentAnswer', '')

    result = grade_name(expected_names, student_answer)
    return jsonify(result)


@grading_bp.route('/api/check-math-equivalence', methods=['POST'])
def check_math_equivalence():
    """
    Check if two math expressions are equivalent (utility endpoint).

    Request body:
    {
        "expression1": "\\frac{1}{2}",
        "expression2": "0.5"
    }
    """
    try:
        from backend.services.stem_grading import check_math_equivalence as check_equiv
    except ImportError:
        return jsonify({"error": "STEM grading service not available"}), 500

    data = request.json
    expr1 = data.get('expression1', '')
    expr2 = data.get('expression2', '')

    result = check_equiv(expr1, expr2)
    return jsonify(result)


@grading_bp.route('/api/export-focus-csv', methods=['POST'])
def export_focus_csv():
    """
    Export grades as CSV for Focus SIS import.
    Uses Claude AI to match student names to IDs from roster data.

    Format: Student_ID,Score
    """
    import json
    import anthropic

    data = request.json
    results = data.get('results', [])
    assignment = data.get('assignment', 'Assignment')
    period = data.get('period', 'all')
    include_letter_grade = data.get('include_letter_grade', False)

    if not results:
        return jsonify({"error": "No results to export"})

    # Load API key
    api_key = None
    env_path = Path(__file__).parent.parent.parent / '.env'
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith('ANTHROPIC_API_KEY='):
                api_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                break

    # Load roster data to get student IDs
    rosters_dir = Path.home() / '.graider_data' / 'rosters'
    periods_dir = Path.home() / '.graider_data' / 'periods'

    roster_students = []
    # Load from rosters
    if rosters_dir.exists():
        for f in rosters_dir.glob('*.csv'):
            try:
                with open(f, 'r') as csvfile:
                    reader = csv.DictReader(csvfile)
                    if not reader.fieldnames:
                        continue
                    id_col = None
                    name_col = None
                    for col in reader.fieldnames:
                        col_lower = col.strip().lower()
                        if col_lower in ('student id', 'student_id', 'id'):
                            id_col = col
                        if col_lower in ('student', 'student_name', 'student name', 'name'):
                            name_col = col
                    for row in reader:
                        student_id = row.get(id_col, '').strip() if id_col else ''
                        name = ''
                        if name_col:
                            raw_name = row.get(name_col, '').strip()
                            if ';' in raw_name:
                                parts = raw_name.split(';', 1)
                                last = parts[0].strip()
                                first = parts[1].strip().split()[0] if parts[1].strip() else ''
                                name = f"{first} {last}"
                            else:
                                name = raw_name
                        if not name:
                            first = row.get('First_Name') or row.get('first_name') or row.get('First') or ''
                            last = row.get('Last_Name') or row.get('last_name') or row.get('Last') or ''
                            if first and last:
                                name = f"{first} {last}"
                        if student_id and name:
                            roster_students.append({'id': student_id, 'name': name})
            except:
                pass

    # Load from periods
    if periods_dir.exists():
        for f in periods_dir.glob('*.csv'):
            try:
                with open(f, 'r') as csvfile:
                    reader = csv.DictReader(csvfile)
                    if not reader.fieldnames:
                        continue
                    # Find the ID column (handles "Student ID" with space, "Student_ID", etc.)
                    id_col = None
                    name_col = None
                    for col in reader.fieldnames:
                        col_lower = col.strip().lower()
                        if col_lower in ('student id', 'student_id', 'id'):
                            id_col = col
                        if col_lower in ('student', 'student_name', 'student name', 'name'):
                            name_col = col
                    for row in reader:
                        student_id = row.get(id_col, '').strip() if id_col else ''
                        # Try dedicated name columns first, then fall back to generic lookups
                        name = ''
                        if name_col:
                            raw_name = row.get(name_col, '').strip()
                            # Handle "Last; First Middle" format from Focus SIS
                            if ';' in raw_name:
                                parts = raw_name.split(';', 1)
                                last = parts[0].strip()
                                first = parts[1].strip().split()[0] if parts[1].strip() else ''
                                name = f"{first} {last}"
                            else:
                                name = raw_name
                        if not name:
                            first = row.get('First_Name') or row.get('first_name') or row.get('First') or ''
                            last = row.get('Last_Name') or row.get('last_name') or row.get('Last') or ''
                            if first and last:
                                name = f"{first} {last}"
                        if student_id and name:
                            roster_students.append({'id': student_id, 'name': name})
            except:
                pass

    # Build list of students to match
    students_to_match = []
    for r in results:
        student_name = r.get('student_name', '')
        student_id = r.get('student_id', '')
        score = r.get('score', 0)
        # Treat "UNKNOWN" as no ID so it triggers re-matching
        if student_id and student_id != 'UNKNOWN':
            students_to_match.append({'name': student_name, 'id': student_id, 'score': score})
        else:
            students_to_match.append({'name': student_name, 'id': None, 'score': score})

    # --- Local fuzzy matching first (fast, no API call) ---
    import re as re_mod
    from difflib import SequenceMatcher

    def _normalize_name(n):
        return re_mod.sub(r'[^a-z ]', '', n.lower()).strip()

    def _fuzzy_match_student(name, roster):
        """Match a student name against the roster using multiple strategies."""
        norm = _normalize_name(name)
        norm_words = set(norm.split())

        best_match = None
        best_score = 0

        for rs in roster:
            rn = _normalize_name(rs['name'])
            rn_words = set(rn.split())

            # Exact match
            if norm == rn:
                return rs['id']

            # All words from the shorter name appear in the longer name
            if norm_words and rn_words:
                if norm_words.issubset(rn_words) or rn_words.issubset(norm_words):
                    return rs['id']

            # SequenceMatcher for fuzzy matching (handles misspellings)
            ratio = SequenceMatcher(None, norm, rn).ratio()
            if ratio > best_score:
                best_score = ratio
                best_match = rs['id']

            # Word-level prefix matching (handles "breden" -> "brenden")
            if len(norm_words) >= 2 and len(rn_words) >= 2:
                match_count = 0
                for nw in norm_words:
                    for rw in rn_words:
                        if nw[:3] == rw[:3] and SequenceMatcher(None, nw, rw).ratio() > 0.7:
                            match_count += 1
                            break
                if match_count == len(norm_words):
                    if best_score < 0.85:
                        best_score = 0.85
                        best_match = rs['id']

        # Only accept fuzzy match if confidence is high enough
        if best_score >= 0.75:
            return best_match
        return None

    needs_matching = [s for s in students_to_match if not s['id']]
    still_unmatched = []

    for s in needs_matching:
        matched_id = _fuzzy_match_student(s['name'], roster_students)
        if matched_id:
            s['id'] = matched_id
        else:
            still_unmatched.append(s)

    # --- Fall back to Claude AI for remaining unmatched ---
    if still_unmatched and roster_students and api_key:
        try:
            client = anthropic.Anthropic(api_key=api_key)

            prompt = f"""Match these student names from grading results to their Student IDs from the roster.
Names may be misspelled, truncated, or in different order.

ROSTER (Student_ID, Name):
{chr(10).join(f"{s['id']}, {s['name']}" for s in roster_students)}

STUDENTS TO MATCH:
{chr(10).join(s['name'] for s in still_unmatched)}

Return ONLY a JSON object mapping each student name to their ID. If no match found, use "UNMATCHED".
Example: {{"John Smith": "12345", "Jane Doe": "67890", "Unknown Student": "UNMATCHED"}}"""

            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = message.content[0].text
            json_match = re_mod.search(r'\{[^{}]+\}', response_text, re_mod.DOTALL)
            if json_match:
                matches = json.loads(json_match.group())
                for s in students_to_match:
                    if not s['id'] and s['name'] in matches:
                        matched_id = matches[s['name']]
                        if matched_id != 'UNMATCHED':
                            s['id'] = matched_id
        except Exception as e:
            print(f"Claude matching error: {e}")
            # Continue without matching

    # Generate CSV
    header = 'Student_ID,Score,Letter_Grade' if include_letter_grade else 'Student_ID,Score'
    csv_lines = [header]
    matched_count = 0
    for s in students_to_match:
        score = s['score']
        if include_letter_grade:
            lg = 'A' if score >= 90 else 'B' if score >= 80 else 'C' if score >= 70 else 'D' if score >= 60 else 'F'
        if s['id'] and s['id'] not in ('UNMATCHED', 'UNKNOWN'):
            row = f"{s['id']},{score},{lg}" if include_letter_grade else f"{s['id']},{score}"
            csv_lines.append(row)
            matched_count += 1
        else:
            # Include with name as fallback
            row = f"# {s['name']},{score},{lg}" if include_letter_grade else f"# {s['name']},{score}"
            csv_lines.append(row)

    csv_content = '\n'.join(csv_lines)

    # Generate filename
    safe_assignment = ''.join(c if c.isalnum() or c in ' -_' else '' for c in assignment).strip().replace(' ', '_')
    filename = f"focus_{safe_assignment}_{period}.csv"

    return jsonify({
        "csv": csv_content,
        "filename": filename,
        "count": matched_count,
        "total": len(students_to_match),
        "unmatched": len(students_to_match) - matched_count
    })


@grading_bp.route('/api/export-focus-batch', methods=['POST'])
def export_focus_batch():
    """
    Export grades as per-period CSV files for Focus SIS bulk import.

    Format per file: "Student_ID,Score"
    Files written to ~/.graider_exports/focus/

    Input JSON: { results?, assignment?, include_letter_grade? }
    Defaults to grading_state["results"] if results not provided.
    """
    data = request.json or {}
    results = data.get('results') or (grading_state.get("results", []) if grading_state else [])
    assignment = data.get('assignment', 'Assignment')
    include_letter_grade = data.get('include_letter_grade', False)

    if not results:
        return jsonify({"error": "No results to export"}), 400

    # Group by period
    by_period = {}
    for r in results:
        period = r.get('period', 'All')
        if period not in by_period:
            by_period[period] = []
        by_period[period].append(r)

    safe_assignment = ''.join(
        c if c.isalnum() or c in ' -_' else '' for c in assignment
    ).strip().replace(' ', '_')

    period_results = []
    for period, period_items in by_period.items():
        safe_period = period.replace(' ', '_').replace('/', '-')
        filename = f"{safe_assignment}_{safe_period}.csv"
        filepath = os.path.join(FOCUS_EXPORTS_DIR, filename)

        matched = 0
        unmatched = 0
        header = 'Student_ID,Score,Letter_Grade' if include_letter_grade else 'Student_ID,Score'
        csv_lines = [header]

        for r in period_items:
            student_id = r.get('student_id', '')
            score = r.get('score', 0)
            if include_letter_grade:
                lg = 'A' if score >= 90 else 'B' if score >= 80 else 'C' if score >= 70 else 'D' if score >= 60 else 'F'
            if student_id:
                row = f"{student_id},{score},{lg}" if include_letter_grade else f"{student_id},{score}"
                csv_lines.append(row)
                matched += 1
            else:
                # Comment out unmatched students
                name = r.get('student_name', 'Unknown')
                row = f"# {name},{score},{lg}" if include_letter_grade else f"# {name},{score}"
                csv_lines.append(row)
                unmatched += 1

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(csv_lines))

        period_results.append({
            "period": period,
            "file": filename,
            "count": matched,
            "unmatched": unmatched,
        })

    # Write manifest
    manifest = {
        "assignment": assignment,
        "exported_at": datetime.now().isoformat(),
        "periods": period_results,
        "export_dir": FOCUS_EXPORTS_DIR,
    }

    manifest_path = os.path.join(FOCUS_EXPORTS_DIR, "manifest.json")
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    return jsonify(manifest)


@grading_bp.route('/api/export-focus-comments', methods=['POST'])
def export_focus_comments():
    """
    Export per-student comments/feedback for Focus SIS.
    Writes per-period JSON files to ~/.graider_exports/focus/

    Input JSON: { results?, assignment? }
    """
    data = request.json or {}
    results = data.get('results') or (grading_state.get("results", []) if grading_state else [])
    assignment = data.get('assignment', 'Assignment')

    if not results:
        return jsonify({"error": "No results to export"}), 400

    # Group by period
    by_period = {}
    for r in results:
        period = r.get('period', 'All')
        if period not in by_period:
            by_period[period] = []
        by_period[period].append({
            "student_id": r.get('student_id', ''),
            "student_name": r.get('student_name', ''),
            "comment": r.get('feedback', ''),
            "score": r.get('score', 0),
            "letter_grade": r.get('letter_grade', ''),
        })

    safe_assignment = ''.join(
        c if c.isalnum() or c in ' -_' else '' for c in assignment
    ).strip().replace(' ', '_')

    period_results = []
    for period, students in by_period.items():
        safe_period = period.replace(' ', '_').replace('/', '-')
        filename = f"comments_{safe_assignment}_{safe_period}.json"
        filepath = os.path.join(FOCUS_EXPORTS_DIR, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(students, f, indent=2)

        period_results.append({
            "period": period,
            "file": filename,
            "count": len(students),
        })

    manifest = {
        "assignment": assignment,
        "type": "comments",
        "exported_at": datetime.now().isoformat(),
        "periods": period_results,
        "export_dir": FOCUS_EXPORTS_DIR,
    }

    manifest_path = os.path.join(FOCUS_EXPORTS_DIR, "comments_manifest.json")
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    return jsonify(manifest)


# ══════════════════════════════════════════════════════════════
# STUDENT HISTORY MANAGEMENT
# ══════════════════════════════════════════════════════════════

ELL_DATA_FILE = os.path.expanduser("~/.graider_data/ell_students.json")


@grading_bp.route('/api/ell-students', methods=['GET'])
def get_ell_students():
    """Get all ELL student designations."""
    if os.path.exists(ELL_DATA_FILE):
        try:
            with open(ELL_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify(data)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({})


@grading_bp.route('/api/ell-students', methods=['POST'])
def save_ell_students():
    """Save ELL student designations."""
    data = request.json
    if data is None:
        return jsonify({"error": "No data provided"}), 400

    os.makedirs(os.path.dirname(ELL_DATA_FILE), exist_ok=True)
    try:
        with open(ELL_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return jsonify({"status": "saved", "count": len(data)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@grading_bp.route('/api/student-history', methods=['GET'])
def list_student_history():
    """List all students with saved history/writing profiles."""
    import json

    history_dir = os.path.expanduser("~/.graider_data/student_history")
    students = []

    # Build ID -> name lookup from roster and period files
    id_to_name = _build_student_name_lookup()

    if os.path.exists(history_dir):
        for f in os.listdir(history_dir):
            if f.endswith('.json'):
                student_id = f.replace('.json', '')
                filepath = os.path.join(history_dir, f)
                try:
                    with open(filepath, 'r') as hf:
                        data = json.load(hf)
                        # Get summary info
                        profile = data.get('writing_profile', {})
                        submissions = profile.get('sample_count', 0)
                        last_updated = data.get('last_updated', 'Unknown')
                        avg_complexity = profile.get('avg_complexity_score', 0)

                        # Get name: from profile, then roster lookup, then ID as fallback
                        name = data.get('name') or id_to_name.get(student_id) or student_id

                        students.append({
                            'student_id': student_id,
                            'name': name,
                            'submissions_analyzed': submissions,
                            'last_updated': last_updated,
                            'avg_complexity': round(avg_complexity, 1) if avg_complexity else 0,
                            'file_size': os.path.getsize(filepath)
                        })
                except Exception as e:
                    students.append({
                        'student_id': student_id,
                        'name': id_to_name.get(student_id, student_id),
                        'error': str(e)
                    })

    # Sort by name
    students.sort(key=lambda x: x.get('name', '').lower())

    return jsonify({
        "students": students,
        "total": len(students),
        "history_dir": history_dir
    })


def _build_student_name_lookup():
    """Build a student_id -> name lookup from roster and period files."""
    import csv

    id_to_name = {}

    def parse_student_name(row):
        """Parse student name from various formats."""
        # Try separate first/last columns first
        first = row.get('FirstName', row.get('First Name', row.get('first_name', ''))).strip()
        last = row.get('LastName', row.get('Last Name', row.get('last_name', ''))).strip()
        if first and last:
            return f"{first} {last}"

        # Try combined "Student" column with "LastName; FirstName" format
        student = row.get('Student', row.get('Name', row.get('Student Name', ''))).strip()
        if student and '; ' in student:
            parts = student.split('; ', 1)
            if len(parts) == 2:
                return f"{parts[1]} {parts[0]}"  # "FirstName LastName"

        # Try combined name column as-is
        if student:
            return student

        return None

    def get_student_id(row):
        """Get student ID from various column names."""
        for col in ['Student ID', 'StudentID', 'ID', 'student_id']:
            if col in row and row[col]:
                return str(row[col]).strip()
        return None

    # Try main roster
    roster_file = os.path.expanduser("~/.graider_data/roster.csv")
    if os.path.exists(roster_file):
        try:
            with open(roster_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    student_id = get_student_id(row)
                    name = parse_student_name(row)
                    if student_id and name:
                        id_to_name[student_id] = name
        except Exception:
            pass

    # Also try period CSVs
    periods_dir = os.path.expanduser("~/.graider_data/periods")
    if os.path.exists(periods_dir):
        for period_file in os.listdir(periods_dir):
            if period_file.endswith('.csv'):
                try:
                    with open(os.path.join(periods_dir, period_file), 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            student_id = get_student_id(row)
                            name = parse_student_name(row)
                            if student_id and name:
                                id_to_name[student_id] = name
                except Exception:
                    pass

    return id_to_name


@grading_bp.route('/api/student-history/<student_id>', methods=['GET'])
def get_student_history(student_id):
    """Get detailed history for a specific student."""
    import json

    history_dir = os.path.expanduser("~/.graider_data/student_history")
    filepath = os.path.join(history_dir, f"{student_id}.json")

    if not os.path.exists(filepath):
        return jsonify({"error": "Student history not found"}), 404

    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@grading_bp.route('/api/student-history/<student_id>', methods=['DELETE'])
def delete_student_history(student_id):
    """Delete history for a specific student."""
    history_dir = os.path.expanduser("~/.graider_data/student_history")
    filepath = os.path.join(history_dir, f"{student_id}.json")

    if not os.path.exists(filepath):
        return jsonify({"error": "Student history not found"}), 404

    try:
        os.remove(filepath)
        return jsonify({"status": "deleted", "student_id": student_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@grading_bp.route('/api/student-history', methods=['DELETE'])
def delete_all_student_history():
    """Delete ALL student history (fresh start)."""
    history_dir = os.path.expanduser("~/.graider_data/student_history")

    if not os.path.exists(history_dir):
        return jsonify({"status": "cleared", "deleted": 0})

    deleted_count = 0
    errors = []

    for f in os.listdir(history_dir):
        if f.endswith('.json'):
            try:
                os.remove(os.path.join(history_dir, f))
                deleted_count += 1
            except Exception as e:
                errors.append(f"{f}: {e}")

    return jsonify({
        "status": "cleared",
        "deleted": deleted_count,
        "errors": errors if errors else None
    })


@grading_bp.route('/api/student-history/migrate-names', methods=['POST'])
def migrate_student_names():
    """Add student names to existing profiles by looking up from roster."""
    import json
    import csv

    history_dir = os.path.expanduser("~/.graider_data/student_history")
    roster_file = os.path.expanduser("~/.graider_data/roster.csv")

    # Also check for period CSVs which have student names
    periods_dir = os.path.expanduser("~/.graider_data/periods")

    if not os.path.exists(history_dir):
        return jsonify({"error": "No student history directory found"}), 404

    # Build a lookup of student_id -> name from all sources
    id_to_name = {}

    # Try main roster first
    if os.path.exists(roster_file):
        try:
            with open(roster_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    student_id = row.get('StudentID', row.get('Student ID', row.get('ID', row.get('student_id', ''))))
                    first = row.get('FirstName', row.get('First Name', row.get('first_name', ''))).strip()
                    last = row.get('LastName', row.get('Last Name', row.get('last_name', ''))).strip()
                    if student_id and first and last:
                        id_to_name[str(student_id).strip()] = f"{first} {last}"
        except Exception as e:
            print(f"Could not read roster: {e}")

    # Also try period CSVs
    if os.path.exists(periods_dir):
        for period_file in os.listdir(periods_dir):
            if period_file.endswith('.csv'):
                try:
                    with open(os.path.join(periods_dir, period_file), 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            student_id = row.get('StudentID', row.get('Student ID', row.get('ID', row.get('student_id', ''))))
                            first = row.get('FirstName', row.get('First Name', row.get('first_name', ''))).strip()
                            last = row.get('LastName', row.get('Last Name', row.get('last_name', ''))).strip()
                            if student_id and first and last:
                                id_to_name[str(student_id).strip()] = f"{first} {last}"
                except Exception:
                    pass

    # Update profiles with names
    updated = 0
    for f in os.listdir(history_dir):
        if f.endswith('.json'):
            student_id = f.replace('.json', '')
            filepath = os.path.join(history_dir, f)
            try:
                with open(filepath, 'r') as hf:
                    data = json.load(hf)

                # Check if name already exists
                if data.get('name') and data['name'] != student_id:
                    continue  # Already has a name

                # Look up name
                name = id_to_name.get(student_id)
                if name:
                    data['name'] = name
                    with open(filepath, 'w') as hf:
                        json.dump(data, hf, indent=2)
                    updated += 1
            except Exception:
                pass

    return jsonify({
        "status": "migrated",
        "updated": updated,
        "roster_entries": len(id_to_name)
    })
