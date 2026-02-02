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
    """Clear all grading results (keeps student history intact)."""
    if grading_state is None:
        return jsonify({"error": "Grading not initialized"}), 500

    if grading_state["is_running"]:
        return jsonify({"error": "Cannot clear results while grading is in progress"}), 400

    # Clear results in state
    grading_state["results"] = []
    grading_state["log"] = []
    grading_state["complete"] = False

    # Clear saved results file
    import os
    results_file = os.path.expanduser("~/.graider_results.json")
    if os.path.exists(results_file):
        try:
            os.remove(results_file)
        except:
            pass

    return jsonify({"status": "cleared"})


@grading_bp.route('/api/delete-result', methods=['POST'])
def delete_result():
    """Delete a single grading result by filename."""
    import json
    import csv

    if grading_state is None:
        return jsonify({"error": "Grading not initialized"}), 500

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
    results_file = os.path.expanduser("~/.graider_results.json")
    try:
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(grading_state["results"], f, indent=2)
    except Exception as e:
        # Log but don't fail - state is already updated
        pass

    # Also remove from master_grades.csv if it exists
    settings_file = os.path.expanduser("~/.graider_settings.json")
    try:
        with open(settings_file, 'r') as f:
            settings = json.load(f)
        output_folder = settings.get('config', {}).get('output_folder', '')
        if output_folder:
            master_file = os.path.join(output_folder, "master_grades.csv")
            if os.path.exists(master_file):
                # Read all rows, filter out the deleted one
                rows = []
                fieldnames = None
                with open(master_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames
                    rows = [row for row in reader if row.get('Filename', '') != filename]

                # Write back without the deleted row
                if fieldnames and len(rows) > 0:
                    with open(master_file, 'w', encoding='utf-8', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)
                elif len(rows) == 0:
                    # If no rows left, delete the file
                    os.remove(master_file)
    except Exception as e:
        # Log but don't fail
        pass

    return jsonify({"status": "deleted"})


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

    # Save to file
    results_file = os.path.expanduser("~/.graider_results.json")
    try:
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(grading_state["results"], f, indent=2)
    except Exception as e:
        pass

    return jsonify({
        "status": "updated",
        "result": grading_state["results"][result_index]
    })

    return jsonify({
        "status": "deleted",
        "filename": filename,
        "remaining_count": len(grading_state["results"])
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
                    for row in reader:
                        # Try common column names for ID and name
                        student_id = row.get('Student_ID') or row.get('student_id') or row.get('ID') or row.get('id') or ''
                        name = row.get('Student_Name') or row.get('student_name') or row.get('Name') or row.get('name') or ''
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
                    for row in reader:
                        student_id = row.get('Student_ID') or row.get('student_id') or row.get('ID') or row.get('id') or ''
                        name = row.get('Student_Name') or row.get('student_name') or row.get('Name') or row.get('name') or ''
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
        if student_id:
            students_to_match.append({'name': student_name, 'id': student_id, 'score': score})
        else:
            students_to_match.append({'name': student_name, 'id': None, 'score': score})

    # Use Claude to match names to IDs if we have roster data and missing IDs
    needs_matching = [s for s in students_to_match if not s['id']]

    if needs_matching and roster_students and api_key:
        try:
            client = anthropic.Anthropic(api_key=api_key)

            prompt = f"""Match these student names from grading results to their Student IDs from the roster.

ROSTER (Student_ID, Name):
{chr(10).join(f"{s['id']}, {s['name']}" for s in roster_students[:100])}

STUDENTS TO MATCH:
{chr(10).join(s['name'] for s in needs_matching)}

Return ONLY a JSON object mapping each student name to their ID. If no match found, use "UNMATCHED".
Example: {{"John Smith": "12345", "Jane Doe": "67890", "Unknown Student": "UNMATCHED"}}"""

            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse response
            response_text = message.content[0].text
            # Extract JSON from response
            import re
            json_match = re.search(r'\{[^{}]+\}', response_text, re.DOTALL)
            if json_match:
                matches = json.loads(json_match.group())
                # Apply matches
                for s in students_to_match:
                    if not s['id'] and s['name'] in matches:
                        matched_id = matches[s['name']]
                        if matched_id != 'UNMATCHED':
                            s['id'] = matched_id
        except Exception as e:
            print(f"Claude matching error: {e}")
            # Continue without matching

    # Generate CSV
    csv_lines = ['Student_ID,Score']
    matched_count = 0
    for s in students_to_match:
        if s['id'] and s['id'] != 'UNMATCHED':
            csv_lines.append(f"{s['id']},{s['score']}")
            matched_count += 1
        else:
            # Include with name as fallback
            csv_lines.append(f"# {s['name']},{s['score']}")

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


# ══════════════════════════════════════════════════════════════
# STUDENT HISTORY MANAGEMENT
# ══════════════════════════════════════════════════════════════

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
