"""
STEM Subject Grading Service
============================
Provides specialized grading logic for Math, Science, and Geography questions.

Features:
- Math: Symbolic equivalence checking using SymPy
- Science: Tolerance-based data table grading
- Geography: Distance-based coordinate grading
"""

from math import radians, sin, cos, sqrt, atan2
import re


# =============================================================================
# MATH INPUT NORMALIZATION
# =============================================================================

def _normalize_math_input(expr_str: str):
    """Normalize student math notation into a SymPy expression.

    Fallback chain:
    1. Plain number: float("3.14")
    2. Percentage: strip %, divide by 100
    3. Fraction string: "1/2" → Rational(1, 2)
    4. Student algebra notation: insert * between coefficient and variable
    5. Caret exponents: x^2 → x**2
    6. LaTeX: parse_latex() as last resort
    7. Give up: return None
    """
    from sympy import sympify, Rational
    from sympy.parsing.latex import parse_latex

    s = expr_str.strip()
    if not s:
        return None

    # 1. Plain number
    try:
        return sympify(float(s))
    except (ValueError, TypeError):
        pass

    # 2. Percentage: "50%" → 0.5
    if s.endswith('%'):
        try:
            return sympify(float(s[:-1].strip()) / 100)
        except (ValueError, TypeError):
            pass

    # 3. Fraction string: "1/2", "-3/4"
    frac_match = re.match(r'^(-?\d+)\s*/\s*(\d+)$', s)
    if frac_match:
        num, den = int(frac_match.group(1)), int(frac_match.group(2))
        if den != 0:
            return Rational(num, den)

    # 4 & 5. Student algebra: insert * for implicit multiplication, convert ^ to **
    algebraic = s.replace('^', '**')
    # Insert * between: digit and letter, letter and digit (for cases like 2x, x2)
    algebraic = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', algebraic)
    algebraic = re.sub(r'([a-zA-Z])(\d)', r'\1*\2', algebraic)
    # Insert * between closing paren and letter/digit, and vice versa
    algebraic = re.sub(r'\)([a-zA-Z\d])', r')*\1', algebraic)
    algebraic = re.sub(r'([a-zA-Z\d])\(', r'\1*(', algebraic)
    try:
        return sympify(algebraic)
    except Exception:
        pass

    # 6. LaTeX fallback
    try:
        return parse_latex(s)
    except Exception:
        pass

    # 7. Give up
    return None


def _compare_numeric_forms(student_str: str, correct_str: str, tolerance: float = 0.001) -> dict:
    """Compare common equivalent numeric forms.

    Handles: 0.5 vs 1/2 vs 50%, 3.14 vs 3.14159 within tolerance, -(-5) vs 5.
    """
    from sympy import N as sympy_N

    student_expr = _normalize_math_input(student_str)
    correct_expr = _normalize_math_input(correct_str)

    if student_expr is None or correct_expr is None:
        return {'equivalent': False, 'method': 'failed', 'error': 'Could not parse one or both expressions'}

    # Try exact symbolic comparison
    from sympy import simplify
    try:
        diff = simplify(student_expr - correct_expr)
        if diff == 0:
            return {'equivalent': True, 'method': 'symbolic'}
    except Exception:
        pass

    # Try numerical comparison
    try:
        student_val = float(sympy_N(student_expr))
        correct_val = float(sympy_N(correct_expr))
        if abs(student_val - correct_val) < tolerance:
            return {
                'equivalent': True,
                'method': 'numerical',
                'student_value': student_val,
                'correct_value': correct_val,
            }
    except (TypeError, ValueError):
        pass

    return {'equivalent': False, 'method': 'symbolic'}


# =============================================================================
# MATH GRADING
# =============================================================================

def check_math_equivalence(student_answer: str, correct_answer: str, tolerance: float = 0.001) -> dict:
    """
    Check if two math expressions are equivalent.

    Uses SymPy for symbolic math comparison. Falls back to numerical
    evaluation if symbolic comparison fails.

    Args:
        student_answer: Student's LaTeX answer
        correct_answer: Expected LaTeX answer
        tolerance: Numerical tolerance for floating-point comparison

    Returns:
        dict with 'equivalent', 'method', and optional details
    """
    try:
        from sympy.parsing.latex import parse_latex
        from sympy import simplify, N
    except ImportError:
        return {
            'equivalent': False,
            'error': 'SymPy not installed. Run: pip install sympy'
        }

    try:
        # Clean up LaTeX input
        student_clean = student_answer.strip()
        correct_clean = correct_answer.strip()

        # Handle simple numeric comparison first
        try:
            student_num = float(student_clean)
            correct_num = float(correct_clean)
            if abs(student_num - correct_num) < tolerance:
                return {
                    'equivalent': True,
                    'method': 'numeric',
                    'student_value': student_num,
                    'correct_value': correct_num
                }
            else:
                return {
                    'equivalent': False,
                    'method': 'numeric',
                    'student_value': student_num,
                    'correct_value': correct_num,
                    'difference': abs(student_num - correct_num)
                }
        except ValueError:
            pass  # Not simple numbers, try symbolic

        # Try normalized student notation (handles 2x+3, x^2, 1/2, 50%)
        norm_result = _compare_numeric_forms(student_clean, correct_clean, tolerance)
        if norm_result.get('equivalent'):
            return norm_result

        # Parse LaTeX to SymPy expressions
        student_expr = parse_latex(student_clean)
        correct_expr = parse_latex(correct_clean)

        # Try symbolic equivalence first
        difference = simplify(student_expr - correct_expr)
        if difference == 0:
            return {
                'equivalent': True,
                'method': 'symbolic',
                'simplified_student': str(simplify(student_expr)),
                'simplified_correct': str(simplify(correct_expr))
            }

        # Try numerical evaluation if symbolic fails
        try:
            student_val = float(N(student_expr))
            correct_val = float(N(correct_expr))
            if abs(student_val - correct_val) < tolerance:
                return {
                    'equivalent': True,
                    'method': 'numerical',
                    'student_value': student_val,
                    'correct_value': correct_val,
                    'difference': abs(student_val - correct_val)
                }
        except (TypeError, ValueError):
            pass

        return {
            'equivalent': False,
            'method': 'symbolic',
            'simplified_student': str(simplify(student_expr)),
            'simplified_correct': str(simplify(correct_expr))
        }

    except Exception as e:
        return {
            'equivalent': False,
            'error': str(e),
            'method': 'failed'
        }


def grade_math_question(question: dict, student_response: str) -> dict:
    """
    Grade a math question with support for:
    - Equivalent forms acceptance
    - Partial credit for work shown
    - Step-by-step solution checking

    Args:
        question: Question config with correctAnswer, acceptEquivalent, showWork, points
        student_response: Student's LaTeX answer

    Returns:
        Grading result with points_earned, feedback, etc.
    """
    result = {
        'question_type': 'math',
        'points_earned': 0,
        'points_possible': question.get('points', 1),
        'feedback': []
    }

    correct_answer = question.get('correctAnswer', '')
    accept_equivalent = question.get('acceptEquivalent', True)
    show_work = question.get('showWork', False)

    if not student_response or not student_response.strip():
        result['feedback'].append('No answer provided.')
        return result

    if not correct_answer:
        result['feedback'].append('No correct answer defined for this question.')
        result['needs_ai_review'] = True
        return result

    # Check the answer
    if accept_equivalent:
        equivalence = check_math_equivalence(student_response, correct_answer)
    else:
        # Exact match only
        equivalence = {
            'equivalent': student_response.strip() == correct_answer.strip(),
            'method': 'exact'
        }

    if equivalence.get('equivalent'):
        result['points_earned'] = result['points_possible']
        result['correct'] = True
        result['feedback'].append('Correct!')

        if equivalence.get('method') == 'numerical':
            result['feedback'].append('Your answer is numerically equivalent to the expected answer.')
        elif equivalence.get('method') == 'symbolic':
            result['feedback'].append('Your answer is mathematically equivalent to the expected answer.')
    else:
        result['correct'] = False

        # If work shown is required and answer is substantial, flag for AI review
        if show_work and len(student_response) > 20:
            result['needs_ai_review'] = True
            result['feedback'].append('Your final answer differs from expected. Work will be reviewed for partial credit.')
        else:
            result['feedback'].append(f'Incorrect. Expected: {correct_answer}')

        if equivalence.get('error'):
            result['feedback'].append('Note: Could not fully parse your answer. Please check notation.')

    return result


# =============================================================================
# SCIENCE DATA TABLE GRADING
# =============================================================================

def check_cell_value(expected: str, student: str, tolerance_percent: float) -> dict:
    """
    Check if a single cell value is correct within tolerance.

    Args:
        expected: Expected cell value
        student: Student's cell value
        tolerance_percent: Acceptable percentage deviation

    Returns:
        dict with 'correct', 'feedback', optional 'deviation'
    """
    expected_clean = str(expected).strip()
    student_clean = str(student).strip()

    # Exact match
    if expected_clean.lower() == student_clean.lower():
        return {'correct': True, 'feedback': 'Correct'}

    # Try numerical comparison
    try:
        expected_num = float(expected_clean.replace(',', ''))
        student_num = float(student_clean.replace(',', ''))

        if expected_num == 0:
            if student_num == 0:
                return {'correct': True, 'feedback': 'Correct'}
            else:
                return {
                    'correct': False,
                    'feedback': f'Expected 0, got {student_clean}'
                }

        percent_diff = abs((student_num - expected_num) / expected_num) * 100

        if percent_diff <= tolerance_percent:
            return {
                'correct': True,
                'feedback': f'Correct (within {tolerance_percent}% tolerance)',
                'deviation': round(percent_diff, 2)
            }
        else:
            return {
                'correct': False,
                'feedback': f'Expected {expected_clean}, got {student_clean} ({percent_diff:.1f}% off)',
                'deviation': round(percent_diff, 2)
            }
    except ValueError:
        pass

    # String comparison failed
    return {
        'correct': False,
        'feedback': f'Expected "{expected_clean}", got "{student_clean}"'
    }


def grade_data_table(expected_table: dict, student_table: dict, tolerance_percent: float = 5.0) -> dict:
    """
    Grade a data table with tolerance for numerical values.

    Args:
        expected_table: {'headers': [...], 'units': [...], 'data': [[...]]}
        student_table: Same structure as expected
        tolerance_percent: Acceptable percentage deviation for numerical values

    Returns:
        Grading result with per-cell feedback
    """
    result = {
        'question_type': 'data_table',
        'total_cells': 0,
        'correct_cells': 0,
        'cell_results': [],
        'feedback': []
    }

    expected_data = expected_table.get('data', [])
    student_data = student_table.get('data', [])

    # Check dimensions
    if len(student_data) != len(expected_data):
        result['feedback'].append(
            f"Row count mismatch: expected {len(expected_data)}, got {len(student_data)}"
        )

    for row_idx, expected_row in enumerate(expected_data):
        if row_idx >= len(student_data):
            result['feedback'].append(f"Missing row {row_idx + 1}")
            for col_idx in range(len(expected_row)):
                result['total_cells'] += 1
                result['cell_results'].append({
                    'row': row_idx,
                    'col': col_idx,
                    'correct': False,
                    'feedback': 'Missing row'
                })
            continue

        student_row = student_data[row_idx]

        for col_idx, expected_val in enumerate(expected_row):
            result['total_cells'] += 1

            if col_idx >= len(student_row):
                result['cell_results'].append({
                    'row': row_idx,
                    'col': col_idx,
                    'correct': False,
                    'feedback': 'Missing value'
                })
                continue

            student_val = student_row[col_idx]
            cell_result = check_cell_value(expected_val, student_val, tolerance_percent)
            cell_result['row'] = row_idx
            cell_result['col'] = col_idx

            if cell_result['correct']:
                result['correct_cells'] += 1

            result['cell_results'].append(cell_result)

    # Calculate score
    if result['total_cells'] > 0:
        result['score_percent'] = round(
            (result['correct_cells'] / result['total_cells']) * 100, 1
        )
    else:
        result['score_percent'] = 0

    return result


# =============================================================================
# GEOGRAPHY COORDINATE GRADING
# =============================================================================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points in kilometers.

    Uses the Haversine formula for accurate distance on a sphere.

    Args:
        lat1, lon1: First point coordinates (decimal degrees)
        lat2, lon2: Second point coordinates (decimal degrees)

    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth's radius in kilometers

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c


def grade_coordinate_question(expected: dict, student: dict, tolerance_km: float = 50) -> dict:
    """
    Grade a coordinate answer with tolerance for distance.

    Args:
        expected: {'latitude': float, 'longitude': float}
        student: Same structure as expected
        tolerance_km: Maximum distance in km for correct answer

    Returns:
        Grading result with distance and feedback
    """
    result = {
        'question_type': 'coordinates',
        'correct': False,
        'feedback': []
    }

    try:
        exp_lat = float(expected.get('latitude', 0))
        exp_lon = float(expected.get('longitude', 0))
        stu_lat = float(student.get('latitude', 0))
        stu_lon = float(student.get('longitude', 0))

        distance = haversine_distance(exp_lat, exp_lon, stu_lat, stu_lon)
        result['distance_km'] = round(distance, 2)

        if distance <= tolerance_km:
            result['correct'] = True
            if distance < 1:
                result['feedback'].append('Excellent! Your coordinates are very precise.')
            elif distance < 10:
                result['feedback'].append(f'Great! Your answer is within {distance:.1f} km of the expected location.')
            else:
                result['feedback'].append(f'Correct! Within {distance:.1f} km of the expected location (tolerance: {tolerance_km} km).')
        else:
            result['correct'] = False
            result['feedback'].append(
                f'Your coordinates are {distance:.1f} km from the expected location (tolerance: {tolerance_km} km).'
            )

            # Provide directional hints
            if stu_lat < exp_lat - 0.1:
                result['feedback'].append('Hint: The correct location is further north.')
            elif stu_lat > exp_lat + 0.1:
                result['feedback'].append('Hint: The correct location is further south.')

            if stu_lon < exp_lon - 0.1:
                result['feedback'].append('Hint: The correct location is further east.')
            elif stu_lon > exp_lon + 0.1:
                result['feedback'].append('Hint: The correct location is further west.')

    except (ValueError, TypeError) as e:
        result['feedback'].append(f'Could not parse coordinates: {str(e)}')

    return result


def grade_place_name(expected_names: list, student_answer: str) -> dict:
    """
    Grade a place name question, accepting common alternatives.

    Args:
        expected_names: List of acceptable names ['United Kingdom', 'UK', 'Britain']
        student_answer: Student's response

    Returns:
        Grading result with correct flag and feedback
    """
    result = {
        'question_type': 'place_name',
        'correct': False,
        'feedback': []
    }

    if not student_answer or not student_answer.strip():
        result['feedback'].append('No answer provided.')
        return result

    student_clean = student_answer.strip().lower()

    # Check for exact matches
    for name in expected_names:
        if name.lower() == student_clean:
            result['correct'] = True
            result['feedback'].append('Correct!')
            return result

    # Check for partial matches
    for name in expected_names:
        name_lower = name.lower()
        if name_lower in student_clean or student_clean in name_lower:
            result['correct'] = True
            result['feedback'].append(f'Correct! (Accepted as matching "{name}")')
            return result

    result['feedback'].append(f'Incorrect. Expected one of: {", ".join(expected_names)}')
    return result
