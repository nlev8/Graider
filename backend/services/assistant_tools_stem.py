"""
STEM Subject Tools
==================
Assistant tools that expose stem_grading.py functions for Math,
Science, and Geography. Zero AI cost — all local computation.
"""

from backend.services.stem_grading import (
    check_math_equivalence,
    grade_math_question,
    grade_data_table,
    grade_coordinate_question,
    grade_place_name,
)


# ═══════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════

STEM_TOOL_DEFINITIONS = [
    {
        "name": "check_math_equivalence",
        "description": "Check if two math expressions are equivalent using SymPy symbolic algebra. Accepts LaTeX or plain numbers. Use when a teacher asks 'is 2x+3 the same as 3+2x?' or needs to verify student answers against an answer key.",
        "input_schema": {
            "type": "object",
            "properties": {
                "student_answer": {
                    "type": "string",
                    "description": "Student's math expression (LaTeX or plain number)"
                },
                "correct_answer": {
                    "type": "string",
                    "description": "Expected correct expression (LaTeX or plain number)"
                },
                "tolerance": {
                    "type": "number",
                    "description": "Numerical tolerance for floating-point comparison (default 0.001)"
                }
            },
            "required": ["student_answer", "correct_answer"]
        }
    },
    {
        "name": "grade_math_question",
        "description": "Grade a single math question with equivalence checking, partial credit for work shown, and detailed feedback. Use when a teacher pastes a student's math answer and wants it scored.",
        "input_schema": {
            "type": "object",
            "properties": {
                "correct_answer": {
                    "type": "string",
                    "description": "The correct answer (LaTeX or plain)"
                },
                "student_answer": {
                    "type": "string",
                    "description": "The student's answer to grade"
                },
                "points": {
                    "type": "integer",
                    "description": "Points possible for this question (default 1)"
                },
                "accept_equivalent": {
                    "type": "boolean",
                    "description": "Accept mathematically equivalent forms (default true)"
                },
                "show_work": {
                    "type": "boolean",
                    "description": "Whether work shown should earn partial credit consideration (default false)"
                }
            },
            "required": ["correct_answer", "student_answer"]
        }
    },
    {
        "name": "grade_data_table",
        "description": "Grade a science data table by comparing student values cell-by-cell against expected values with tolerance for numerical deviation. Use for lab data, experiment results, or any tabular science answers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expected_table": {
                    "type": "object",
                    "description": "Expected table: {headers: ['Col1','Col2'], data: [['row1col1','row1col2'], ...]}",
                    "properties": {
                        "headers": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "data": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        }
                    }
                },
                "student_table": {
                    "type": "object",
                    "description": "Student's table in the same format as expected_table",
                    "properties": {
                        "headers": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "data": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        }
                    }
                },
                "tolerance_percent": {
                    "type": "number",
                    "description": "Acceptable percentage deviation for numerical values (default 5.0)"
                }
            },
            "required": ["expected_table", "student_table"]
        }
    },
    {
        "name": "grade_coordinates",
        "description": "Grade a geography coordinate answer using Haversine distance. Checks if student's lat/lon is within tolerance of the expected location and gives directional hints. Use for map work, geography quizzes, or location-based questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expected_latitude": {
                    "type": "number",
                    "description": "Expected latitude in decimal degrees"
                },
                "expected_longitude": {
                    "type": "number",
                    "description": "Expected longitude in decimal degrees"
                },
                "student_latitude": {
                    "type": "number",
                    "description": "Student's latitude answer"
                },
                "student_longitude": {
                    "type": "number",
                    "description": "Student's longitude answer"
                },
                "tolerance_km": {
                    "type": "number",
                    "description": "Maximum acceptable distance in km (default 50)"
                }
            },
            "required": ["expected_latitude", "expected_longitude", "student_latitude", "student_longitude"]
        }
    },
    {
        "name": "grade_place_name",
        "description": "Grade a geography place name answer, accepting common alternatives (e.g. 'UK', 'United Kingdom', 'Britain' all accepted). Use for geography or history questions where multiple name forms are valid.",
        "input_schema": {
            "type": "object",
            "properties": {
                "accepted_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of acceptable names (e.g. ['United Kingdom', 'UK', 'Britain'])"
                },
                "student_answer": {
                    "type": "string",
                    "description": "Student's answer to check"
                }
            },
            "required": ["accepted_names", "student_answer"]
        }
    },
]


# ═══════════════════════════════════════════════════════
# HANDLERS
# ═══════════════════════════════════════════════════════

def handle_check_math_equivalence(args):
    """Check if two math expressions are equivalent."""
    student = args.get("student_answer", "").strip()
    correct = args.get("correct_answer", "").strip()
    if not student or not correct:
        return {"error": "Both student_answer and correct_answer are required"}

    tolerance = args.get("tolerance", 0.001)
    return check_math_equivalence(student, correct, tolerance)


def handle_grade_math_question(args):
    """Grade a single math question."""
    correct = args.get("correct_answer", "").strip()
    student = args.get("student_answer", "").strip()
    if not correct or not student:
        return {"error": "Both correct_answer and student_answer are required"}

    question = {
        "correctAnswer": correct,
        "points": args.get("points", 1),
        "acceptEquivalent": args.get("accept_equivalent", True),
        "showWork": args.get("show_work", False),
    }
    return grade_math_question(question, student)


def handle_grade_data_table(args):
    """Grade a science data table."""
    expected = args.get("expected_table")
    student = args.get("student_table")
    if not expected or not student:
        return {"error": "Both expected_table and student_table are required"}
    if not expected.get("data") or not student.get("data"):
        return {"error": "Both tables must include a 'data' array of rows"}

    tolerance = args.get("tolerance_percent", 5.0)
    return grade_data_table(expected, student, tolerance)


def handle_grade_coordinates(args):
    """Grade a geography coordinate answer."""
    try:
        exp_lat = float(args["expected_latitude"])
        exp_lon = float(args["expected_longitude"])
        stu_lat = float(args["student_latitude"])
        stu_lon = float(args["student_longitude"])
    except (KeyError, TypeError, ValueError):
        return {"error": "All four coordinate values (expected_latitude, expected_longitude, student_latitude, student_longitude) are required as numbers"}

    tolerance = args.get("tolerance_km", 50)
    return grade_coordinate_question(
        {"latitude": exp_lat, "longitude": exp_lon},
        {"latitude": stu_lat, "longitude": stu_lon},
        tolerance,
    )


def handle_grade_place_name(args):
    """Grade a place name answer."""
    accepted = args.get("accepted_names", [])
    student = args.get("student_answer", "").strip()
    if not accepted:
        return {"error": "accepted_names list is required"}
    if not student:
        return {"error": "student_answer is required"}

    return grade_place_name(accepted, student)


# ═══════════════════════════════════════════════════════
# EXPORT MAP
# ═══════════════════════════════════════════════════════

STEM_TOOL_HANDLERS = {
    "check_math_equivalence": handle_check_math_equivalence,
    "grade_math_question": handle_grade_math_question,
    "grade_data_table": handle_grade_data_table,
    "grade_coordinates": handle_grade_coordinates,
    "grade_place_name": handle_grade_place_name,
}
