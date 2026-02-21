"""
Assignment Player API routes for Graider.
Handles interactive assignment serving and auto-grading.
"""
import os
import json
import time
from flask import Blueprint, request, jsonify
from pathlib import Path

assignment_player_bp = Blueprint('assignment_player', __name__)

# Store active assignments (in production, use database)
ASSIGNMENTS_DIR = os.path.expanduser("~/.graider_data/active_assignments")


@assignment_player_bp.route('/api/assignment/<assignment_id>', methods=['GET'])
def get_assignment(assignment_id):
    """Get an assignment for a student to complete."""
    try:
        filepath = os.path.join(ASSIGNMENTS_DIR, f"{assignment_id}.json")
        if not os.path.exists(filepath):
            return jsonify({"error": "Assignment not found"}), 404

        with open(filepath, 'r') as f:
            assignment = json.load(f)

        # Remove answer keys for student version
        student_assignment = strip_answers(assignment)
        return jsonify({"assignment": student_assignment})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@assignment_player_bp.route('/api/assignment', methods=['POST'])
def create_assignment():
    """Create/publish an assignment for students."""
    try:
        data = request.json
        assignment = data.get('assignment', {})

        if not assignment:
            return jsonify({"error": "No assignment provided"}), 400

        # Generate unique ID
        assignment_id = f"assign_{int(time.time() * 1000)}"
        assignment['id'] = assignment_id
        assignment['created_at'] = time.strftime('%Y-%m-%d %H:%M:%S')

        # Save assignment
        os.makedirs(ASSIGNMENTS_DIR, exist_ok=True)
        filepath = os.path.join(ASSIGNMENTS_DIR, f"{assignment_id}.json")
        with open(filepath, 'w') as f:
            json.dump(assignment, f, indent=2)

        # Generate shareable link (in production, use actual domain)
        share_url = f"/student/assignment/{assignment_id}"

        return jsonify({
            "status": "success",
            "assignment_id": assignment_id,
            "share_url": share_url
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@assignment_player_bp.route('/api/assignment/<assignment_id>/submit', methods=['POST'])
def submit_assignment(assignment_id):
    """Submit and grade an assignment."""
    try:
        # Load the assignment with answers
        filepath = os.path.join(ASSIGNMENTS_DIR, f"{assignment_id}.json")
        if not os.path.exists(filepath):
            return jsonify({"error": "Assignment not found"}), 404

        with open(filepath, 'r') as f:
            assignment = json.load(f)

        # Get student answers
        data = request.json
        student_answers = data.get('answers', {})
        student_name = data.get('student_name', 'Unknown')

        # Grade the assignment
        results = grade_assignment(assignment, student_answers)
        results['student_name'] = student_name
        results['submitted_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        results['assignment_id'] = assignment_id

        # Save submission
        submissions_dir = os.path.join(ASSIGNMENTS_DIR, 'submissions', assignment_id)
        os.makedirs(submissions_dir, exist_ok=True)
        submission_file = os.path.join(submissions_dir, f"{student_name}_{int(time.time())}.json")
        with open(submission_file, 'w') as f:
            json.dump({
                'student_name': student_name,
                'answers': student_answers,
                'results': results
            }, f, indent=2)

        return jsonify({"results": results})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@assignment_player_bp.route('/api/assignment/<assignment_id>/submissions', methods=['GET'])
def get_submissions(assignment_id):
    """Get all submissions for an assignment (teacher view)."""
    try:
        submissions_dir = os.path.join(ASSIGNMENTS_DIR, 'submissions', assignment_id)
        if not os.path.exists(submissions_dir):
            return jsonify({"submissions": []})

        submissions = []
        for filename in os.listdir(submissions_dir):
            if filename.endswith('.json'):
                with open(os.path.join(submissions_dir, filename), 'r') as f:
                    submissions.append(json.load(f))

        # Sort by submission time
        submissions.sort(key=lambda x: x.get('results', {}).get('submitted_at', ''), reverse=True)

        return jsonify({"submissions": submissions})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def strip_answers(assignment):
    """Remove answer keys from assignment for student version."""
    stripped = {**assignment}
    stripped['sections'] = []

    for section in assignment.get('sections', []):
        stripped_section = {**section}
        stripped_section['questions'] = []

        for q in section.get('questions', []):
            # Copy question without answer fields
            stripped_q = {k: v for k, v in q.items()
                         if k not in ['answer', 'expected_data', 'points_to_plot',
                                      'expected_values', 'correct_answer']}
            stripped_section['questions'].append(stripped_q)

        stripped['sections'].append(stripped_section)

    return stripped


def grade_assignment(assignment, student_answers):
    """Grade all student answers against the assignment."""
    total_points = 0
    earned_points = 0
    question_results = {}

    for sIdx, section in enumerate(assignment.get('sections', [])):
        section_type = section.get('type', 'short_answer')

        for qIdx, question in enumerate(section.get('questions', [])):
            key = f"{sIdx}-{qIdx}"
            student_answer = student_answers.get(key, {})
            q_type = question.get('question_type', section_type)
            q_points = question.get('points', 10)
            total_points += q_points

            result = grade_question(question, student_answer, q_type)
            result['points_possible'] = q_points
            result['points_earned'] = q_points if result['correct'] else (
                q_points * result.get('partial_credit', 0)
            )
            earned_points += result['points_earned']

            question_results[key] = result

    percent = round((earned_points / total_points) * 100) if total_points > 0 else 0

    return {
        'score': round(earned_points, 1),
        'total': total_points,
        'percent': percent,
        'questions': question_results,
        'grade': get_letter_grade(percent)
    }


def grade_question(question, student_answer, q_type):
    """Grade a single question based on its type."""
    correct_answer = question.get('answer', '')

    # Handle different answer formats
    if isinstance(student_answer, dict):
        answer_value = student_answer.get('value', student_answer)
    else:
        answer_value = student_answer

    try:
        if q_type == 'number_line':
            return grade_number_line(question, answer_value)

        elif q_type == 'coordinate_plane':
            return grade_coordinate_plane(question, answer_value)

        elif q_type in ['geometry', 'triangle', 'rectangle']:
            return grade_geometry(question, answer_value)

        elif q_type == 'box_plot':
            return grade_box_plot(question, answer_value)

        elif q_type == 'math_equation':
            return grade_math_equation(question, answer_value)

        elif q_type == 'coordinates':
            return grade_coordinates(question, answer_value)

        elif q_type == 'data_table':
            return grade_data_table(question, answer_value)

        elif q_type == 'bar_chart':
            return grade_bar_chart(question, answer_value)

        elif q_type == 'function_graph':
            return grade_function_graph(question, answer_value)

        elif q_type in ['multiple_choice', 'true_false']:
            correct = str(answer_value).strip().lower() == str(correct_answer).strip().lower()
            return {'correct': correct, 'feedback': 'Correct!' if correct else f'Incorrect. The answer was: {correct_answer}'}

        else:  # short_answer and others
            return grade_short_answer(question, answer_value)

    except Exception as e:
        return {'correct': False, 'feedback': f'Error grading: {str(e)}', 'error': True}


def grade_number_line(question, answer):
    """Grade number line plotting."""
    expected = question.get('points_to_plot', [])
    if not expected or not answer:
        return {'correct': False, 'feedback': 'No points plotted'}

    # Check if all expected points are plotted (within tolerance)
    tolerance = 0.5
    correct_count = 0
    for exp_pt in expected:
        if any(abs(pt - exp_pt) < tolerance for pt in answer):
            correct_count += 1

    if correct_count == len(expected) and len(answer) == len(expected):
        return {'correct': True, 'feedback': 'All points correctly plotted!'}
    elif correct_count > 0:
        return {
            'correct': False,
            'partial_credit': correct_count / len(expected),
            'feedback': f'{correct_count}/{len(expected)} points correct'
        }
    else:
        return {'correct': False, 'feedback': 'No points correctly plotted'}


def grade_coordinate_plane(question, answer):
    """Grade coordinate plane plotting."""
    expected = question.get('points_to_plot', [])
    if not expected or not answer:
        return {'correct': False, 'feedback': 'No points plotted'}

    correct_count = 0
    for exp_pt in expected:
        if any(pt[0] == exp_pt[0] and pt[1] == exp_pt[1] for pt in answer):
            correct_count += 1

    if correct_count == len(expected) and len(answer) == len(expected):
        return {'correct': True, 'feedback': 'All points correctly plotted!'}
    elif correct_count > 0:
        return {
            'correct': False,
            'partial_credit': correct_count / len(expected),
            'feedback': f'{correct_count}/{len(expected)} points correct'
        }
    else:
        return {'correct': False, 'feedback': 'No points correctly plotted'}


def grade_geometry(question, answer):
    """Grade geometry/area questions."""
    base = question.get('base', 6)
    height = question.get('height', 4)
    q_type = question.get('question_type', 'triangle')

    if q_type == 'triangle':
        expected = (base * height) / 2
    else:  # rectangle
        expected = base * height

    # Get the numeric answer
    if isinstance(answer, dict):
        answer_val = answer.get('value', '')
    else:
        answer_val = answer

    try:
        student_val = float(str(answer_val).replace(' ', ''))
        if abs(student_val - expected) < 0.01:
            return {'correct': True, 'feedback': f'Correct! Area = {expected} square units'}
        else:
            return {'correct': False, 'feedback': f'Incorrect. Area = {expected} square units'}
    except:
        return {'correct': False, 'feedback': f'Could not parse answer. Expected: {expected}'}


def grade_box_plot(question, answer):
    """Grade box plot five-number summary."""
    data = question.get('data', [[50, 60, 70, 80, 90]])[0]
    sorted_data = sorted(data)
    n = len(sorted_data)

    # Calculate expected values
    expected = {
        'min': sorted_data[0],
        'max': sorted_data[-1],
        'median': (sorted_data[n // 2 - 1] + sorted_data[n // 2]) / 2 if n % 2 == 0 else sorted_data[n // 2],
    }

    lower = sorted_data[:n // 2]
    upper = sorted_data[(n + 1) // 2:]
    expected['q1'] = lower[len(lower) // 2] if len(lower) % 2 else (lower[len(lower) // 2 - 1] + lower[len(lower) // 2]) / 2
    expected['q3'] = upper[len(upper) // 2] if len(upper) % 2 else (upper[len(upper) // 2 - 1] + upper[len(upper) // 2]) / 2
    expected['range'] = expected['max'] - expected['min']
    expected['iqr'] = expected['q3'] - expected['q1']

    if not answer or not isinstance(answer, dict):
        return {'correct': False, 'feedback': 'No answers provided'}

    correct_count = 0
    total = len(expected)
    tolerance = 0.5

    for key, exp_val in expected.items():
        try:
            student_val = float(answer.get(key, 0))
            if abs(student_val - exp_val) < tolerance:
                correct_count += 1
        except:
            pass

    if correct_count == total:
        return {'correct': True, 'feedback': 'All values correct!'}
    else:
        return {
            'correct': False,
            'partial_credit': correct_count / total,
            'feedback': f'{correct_count}/{total} values correct'
        }


def grade_math_equation(question, answer):
    """Grade math equation using SymPy equivalence."""
    correct_answer = question.get('answer', '')

    if isinstance(answer, dict):
        answer_val = answer.get('final', '')
    else:
        answer_val = answer

    if not answer_val:
        return {'correct': False, 'feedback': 'No answer provided'}

    # Try using STEM grading service
    try:
        from backend.services.stem_grading import check_math_equivalence
        result = check_math_equivalence(str(answer_val), str(correct_answer))
        if result.get('equivalent'):
            return {'correct': True, 'feedback': 'Correct!'}
        else:
            return {'correct': False, 'feedback': f'Incorrect. Expected: {correct_answer}'}
    except:
        # Fallback to string comparison
        if str(answer_val).strip() == str(correct_answer).strip():
            return {'correct': True, 'feedback': 'Correct!'}
        else:
            return {'correct': False, 'feedback': f'Incorrect. Expected: {correct_answer}'}


def grade_coordinates(question, answer):
    """Grade coordinate/geography answers using distance."""
    correct = question.get('answer', {})
    tolerance_km = question.get('tolerance_km', 50)

    if not answer or not isinstance(answer, dict):
        return {'correct': False, 'feedback': 'No coordinates provided'}

    try:
        from backend.services.stem_grading import haversine_distance
        student_lat = float(answer.get('lat', 0))
        student_lng = float(answer.get('lng', 0))
        correct_lat = float(correct.get('lat', 0))
        correct_lng = float(correct.get('lng', 0))

        distance = haversine_distance(student_lat, student_lng, correct_lat, correct_lng)

        if distance <= tolerance_km:
            return {'correct': True, 'feedback': f'Correct! Within {distance:.1f} km'}
        else:
            return {'correct': False, 'feedback': f'Off by {distance:.1f} km. Expected: ({correct_lat}, {correct_lng})'}
    except Exception as e:
        return {'correct': False, 'feedback': f'Error: {str(e)}'}


def grade_data_table(question, answer):
    """Grade data table with tolerance."""
    expected = question.get('expected_data', [])
    tolerance = question.get('tolerance', 0.05)

    if not answer or not expected:
        return {'correct': False, 'feedback': 'No data provided'}

    try:
        correct_cells = 0
        total_cells = 0

        for i, row in enumerate(expected):
            if i >= len(answer):
                continue
            for j, exp_val in enumerate(row):
                total_cells += 1
                if j >= len(answer[i]):
                    continue
                try:
                    student_val = float(answer[i][j])
                    expected_val = float(exp_val)
                    if abs(student_val - expected_val) <= abs(expected_val * tolerance):
                        correct_cells += 1
                except:
                    if str(answer[i][j]).strip() == str(exp_val).strip():
                        correct_cells += 1

        if correct_cells == total_cells:
            return {'correct': True, 'feedback': 'All values correct!'}
        else:
            return {
                'correct': False,
                'partial_credit': correct_cells / total_cells if total_cells > 0 else 0,
                'feedback': f'{correct_cells}/{total_cells} cells correct'
            }
    except Exception as e:
        return {'correct': False, 'feedback': f'Error: {str(e)}'}


def grade_bar_chart(question, answer):
    """Grade bar chart interpretation questions (text-based answer)."""
    correct = str(question.get('answer', '')).strip().lower()
    student = str(answer).strip().lower() if answer else ''

    if not student:
        return {'correct': False, 'feedback': 'No answer provided'}

    # Exact match
    if student == correct:
        return {'correct': True, 'feedback': 'Correct!'}

    # Keyword overlap — bar chart answers are interpretation/analysis text
    correct_words = set(correct.split())
    student_words = set(student.split())
    overlap = len(correct_words & student_words)

    if correct_words and overlap >= len(correct_words) * 0.7:
        return {'correct': True, 'partial_credit': 0.8, 'feedback': 'Mostly correct'}

    return {'correct': False, 'feedback': f'Incorrect. Expected: {question.get("answer", "")}'}


def grade_function_graph(question, answer):
    """Grade function graph by comparing student expressions to expected expressions."""
    expected = question.get('correct_expressions', [])
    if not expected:
        expected_str = question.get('answer', '')
        expected = [expected_str] if expected_str else []

    if not answer or not expected:
        return {'correct': False, 'feedback': 'No expressions provided'}

    student_exprs = answer if isinstance(answer, list) else [answer]

    try:
        from sympy import sympify, simplify, Symbol
        x = Symbol('x')

        def normalize_expr(expr_str):
            """Normalize a math expression string for comparison."""
            s = str(expr_str).strip().lower()
            s = s.replace('^', '**')
            s = s.replace(' ', '')
            # Remove leading 'y=' or 'f(x)='
            for prefix in ['y=', 'f(x)=']:
                if s.startswith(prefix):
                    s = s[len(prefix):]
            return s

        matched = 0
        for exp_expr in expected:
            exp_norm = normalize_expr(exp_expr)
            try:
                exp_sym = sympify(exp_norm)
            except Exception:
                continue

            for stu_expr in student_exprs:
                stu_norm = normalize_expr(stu_expr)
                try:
                    stu_sym = sympify(stu_norm)
                    if simplify(exp_sym - stu_sym) == 0:
                        matched += 1
                        break
                except Exception:
                    # Fall back to string comparison
                    if exp_norm == stu_norm:
                        matched += 1
                        break

        if matched == len(expected) and len(student_exprs) == len(expected):
            return {'correct': True, 'feedback': 'All functions correctly graphed!'}
        elif matched > 0:
            return {
                'correct': False,
                'partial_credit': matched / len(expected),
                'feedback': f'{matched}/{len(expected)} functions correct'
            }
        else:
            return {'correct': False, 'feedback': f'Incorrect. Expected: {", ".join(expected)}'}

    except ImportError:
        # SymPy not available — fall back to normalized string comparison
        def normalize_expr(expr_str):
            s = str(expr_str).strip().lower().replace('^', '**').replace(' ', '')
            for prefix in ['y=', 'f(x)=']:
                if s.startswith(prefix):
                    s = s[len(prefix):]
            return s

        expected_norm = [normalize_expr(e) for e in expected]
        student_norm = [normalize_expr(s) for s in student_exprs]

        matched = sum(1 for e in expected_norm if e in student_norm)

        if matched == len(expected) and len(student_norm) == len(expected):
            return {'correct': True, 'feedback': 'All functions correctly graphed!'}
        elif matched > 0:
            return {
                'correct': False,
                'partial_credit': matched / len(expected),
                'feedback': f'{matched}/{len(expected)} functions correct'
            }
        else:
            return {'correct': False, 'feedback': f'Incorrect. Expected: {", ".join(expected)}'}


def grade_short_answer(question, answer):
    """Grade short answer questions."""
    correct = str(question.get('answer', '')).strip().lower()
    student = str(answer).strip().lower() if answer else ''

    if not student:
        return {'correct': False, 'feedback': 'No answer provided'}

    # Exact match
    if student == correct:
        return {'correct': True, 'feedback': 'Correct!'}

    # Check for key words
    correct_words = set(correct.split())
    student_words = set(student.split())
    overlap = len(correct_words & student_words)

    if overlap >= len(correct_words) * 0.7:
        return {'correct': True, 'partial_credit': 0.8, 'feedback': 'Mostly correct'}

    return {'correct': False, 'feedback': f'Incorrect. Expected: {question.get("answer", "")}'}


def get_letter_grade(percent):
    """Convert percentage to letter grade."""
    if percent >= 90:
        return 'A'
    elif percent >= 80:
        return 'B'
    elif percent >= 70:
        return 'C'
    elif percent >= 60:
        return 'D'
    else:
        return 'F'
