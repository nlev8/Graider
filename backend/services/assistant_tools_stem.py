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

def handle_check_math_equivalence(student_answer="", correct_answer="", tolerance=0.001, **kwargs):
    """Check if two math expressions are equivalent."""
    student = (student_answer or "").strip()
    correct = (correct_answer or "").strip()
    if not student or not correct:
        return {"error": "Both student_answer and correct_answer are required"}

    return check_math_equivalence(student, correct, tolerance)


def handle_grade_math_question(correct_answer="", student_answer="", points=1, accept_equivalent=True, show_work=False, **kwargs):
    """Grade a single math question."""
    correct = (correct_answer or "").strip()
    student = (student_answer or "").strip()
    if not correct or not student:
        return {"error": "Both correct_answer and student_answer are required"}

    question = {
        "correctAnswer": correct,
        "points": points,
        "acceptEquivalent": accept_equivalent,
        "showWork": show_work,
    }
    return grade_math_question(question, student)


def handle_grade_data_table(expected_table=None, student_table=None, tolerance_percent=5.0, **kwargs):
    """Grade a science data table."""
    if not expected_table or not student_table:
        return {"error": "Both expected_table and student_table are required"}
    if not expected_table.get("data") or not student_table.get("data"):
        return {"error": "Both tables must include a 'data' array of rows"}

    return grade_data_table(expected_table, student_table, tolerance_percent)


def handle_grade_coordinates(expected_latitude=None, expected_longitude=None, student_latitude=None, student_longitude=None, tolerance_km=50, **kwargs):
    """Grade a geography coordinate answer."""
    try:
        exp_lat = float(expected_latitude)
        exp_lon = float(expected_longitude)
        stu_lat = float(student_latitude)
        stu_lon = float(student_longitude)
    except (TypeError, ValueError):
        return {"error": "All four coordinate values (expected_latitude, expected_longitude, student_latitude, student_longitude) are required as numbers"}

    return grade_coordinate_question(
        {"latitude": exp_lat, "longitude": exp_lon},
        {"latitude": stu_lat, "longitude": stu_lon},
        tolerance_km,
    )


def handle_grade_place_name(accepted_names=None, student_answer="", **kwargs):
    """Grade a place name answer."""
    accepted = accepted_names or []
    student = (student_answer or "").strip()
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
