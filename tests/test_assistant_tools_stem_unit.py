"""Unit tests for backend/services/assistant_tools_stem.py.

Audit MAJOR #4 sprint follow-up. Targets 31 uncovered LOC (21% baseline).

Strategy
--------
Five thin handler functions that validate inputs and delegate to
`backend.services.stem_grading`. Each test patches the underlying grader
(returning a sentinel result) and asserts:

  1. Input validation: empty/missing args → error dict, no delegation
  2. Forwarding: valid args → delegate called with normalized values
  3. Result passthrough: sentinel from delegate flows back to caller

`TestExports` pins `STEM_TOOL_DEFINITIONS` ↔ `STEM_TOOL_HANDLERS` parity.

Note: this module has NO `require_teacher_id` calls — all five handlers
are pure local computation (zero AI cost) and the underlying graders
don't need teacher scoping. So no TestTeacherIdRequired class.

Per `feedback_codex_always_high_effort.md`, the merge review uses Codex
high-effort.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


# ──────────────────────────────────────────────────────────────────
# handle_check_math_equivalence
# ──────────────────────────────────────────────────────────────────


class TestHandleCheckMathEquivalence:
    def test_empty_student_answer_returns_error(self):
        from backend.services.assistant_tools_stem import handle_check_math_equivalence

        result = handle_check_math_equivalence(
            student_answer="", correct_answer="2x+3",
        )
        assert "error" in result
        assert "required" in result["error"]

    def test_empty_correct_answer_returns_error(self):
        from backend.services.assistant_tools_stem import handle_check_math_equivalence

        result = handle_check_math_equivalence(
            student_answer="2x+3", correct_answer="",
        )
        assert "error" in result

    def test_whitespace_args_treated_as_empty(self):
        from backend.services.assistant_tools_stem import handle_check_math_equivalence

        with patch("backend.services.assistant_tools_stem.check_math_equivalence") as mock:
            result = handle_check_math_equivalence(
                student_answer="   ", correct_answer="\t\n",
            )
        assert "error" in result
        mock.assert_not_called()

    def test_delegates_with_stripped_args_and_default_tolerance(self):
        from backend.services.assistant_tools_stem import handle_check_math_equivalence

        sentinel = {"equivalent": True, "score": 1.0}
        with patch("backend.services.assistant_tools_stem.check_math_equivalence",
                   return_value=sentinel) as mock:
            result = handle_check_math_equivalence(
                student_answer="  2x + 3  ",
                correct_answer="\t3+2x\n",
            )
        assert result is sentinel
        mock.assert_called_once_with("2x + 3", "3+2x", 0.001)

    def test_custom_tolerance_forwarded(self):
        from backend.services.assistant_tools_stem import handle_check_math_equivalence

        with patch("backend.services.assistant_tools_stem.check_math_equivalence",
                   return_value={}) as mock:
            handle_check_math_equivalence(
                student_answer="3.14",
                correct_answer="3.14159",
                tolerance=0.01,
            )
        mock.assert_called_once_with("3.14", "3.14159", 0.01)


# ──────────────────────────────────────────────────────────────────
# handle_grade_math_question
# ──────────────────────────────────────────────────────────────────


class TestHandleGradeMathQuestion:
    def test_empty_correct_answer_returns_error(self):
        from backend.services.assistant_tools_stem import handle_grade_math_question

        result = handle_grade_math_question(
            correct_answer="", student_answer="42",
        )
        assert "error" in result

    def test_empty_student_answer_returns_error(self):
        from backend.services.assistant_tools_stem import handle_grade_math_question

        result = handle_grade_math_question(
            correct_answer="42", student_answer="",
        )
        assert "error" in result

    def test_delegates_with_default_question_payload(self):
        from backend.services.assistant_tools_stem import handle_grade_math_question

        sentinel = {"score": 1, "feedback": "correct"}
        with patch("backend.services.assistant_tools_stem.grade_math_question",
                   return_value=sentinel) as mock:
            result = handle_grade_math_question(
                correct_answer="42", student_answer="42",
            )
        assert result is sentinel
        # Question payload uses production keys
        question, student = mock.call_args.args
        assert question == {
            "correctAnswer": "42",
            "points": 1,
            "acceptEquivalent": True,
            "showWork": False,
        }
        assert student == "42"

    def test_custom_options_threaded_into_question(self):
        from backend.services.assistant_tools_stem import handle_grade_math_question

        with patch("backend.services.assistant_tools_stem.grade_math_question",
                   return_value={}) as mock:
            handle_grade_math_question(
                correct_answer="2x+3",
                student_answer="3+2x",
                points=5,
                accept_equivalent=False,
                show_work=True,
            )
        question, _student = mock.call_args.args
        assert question == {
            "correctAnswer": "2x+3",
            "points": 5,
            "acceptEquivalent": False,
            "showWork": True,
        }

    def test_strips_whitespace_from_args(self):
        from backend.services.assistant_tools_stem import handle_grade_math_question

        with patch("backend.services.assistant_tools_stem.grade_math_question",
                   return_value={}) as mock:
            handle_grade_math_question(
                correct_answer="  42  ",
                student_answer="\t42\n",
            )
        question, student = mock.call_args.args
        assert question["correctAnswer"] == "42"
        assert student == "42"


# ──────────────────────────────────────────────────────────────────
# handle_grade_data_table
# ──────────────────────────────────────────────────────────────────


class TestHandleGradeDataTable:
    def test_missing_expected_table_returns_error(self):
        from backend.services.assistant_tools_stem import handle_grade_data_table

        result = handle_grade_data_table(
            expected_table=None,
            student_table={"data": [["1", "2"]]},
        )
        assert "error" in result

    def test_missing_student_table_returns_error(self):
        from backend.services.assistant_tools_stem import handle_grade_data_table

        result = handle_grade_data_table(
            expected_table={"data": [["1", "2"]]},
            student_table=None,
        )
        assert "error" in result

    def test_empty_data_array_returns_error(self):
        from backend.services.assistant_tools_stem import handle_grade_data_table

        result = handle_grade_data_table(
            expected_table={"data": []},
            student_table={"data": [["1"]]},
        )
        assert "error" in result
        assert "data" in result["error"]

    def test_delegates_with_default_tolerance(self):
        from backend.services.assistant_tools_stem import handle_grade_data_table

        expected = {"headers": ["A"], "data": [["10"]]}
        student = {"headers": ["A"], "data": [["10.5"]]}
        sentinel = {"score": 0.95}
        with patch("backend.services.assistant_tools_stem.grade_data_table",
                   return_value=sentinel) as mock:
            result = handle_grade_data_table(
                expected_table=expected, student_table=student,
            )
        assert result is sentinel
        mock.assert_called_once_with(expected, student, 5.0)

    def test_custom_tolerance_forwarded(self):
        from backend.services.assistant_tools_stem import handle_grade_data_table

        with patch("backend.services.assistant_tools_stem.grade_data_table",
                   return_value={}) as mock:
            handle_grade_data_table(
                expected_table={"data": [["1"]]},
                student_table={"data": [["1"]]},
                tolerance_percent=10.0,
            )
        _exp, _stu, tol = mock.call_args.args
        assert tol == 10.0


# ──────────────────────────────────────────────────────────────────
# handle_grade_coordinates
# ──────────────────────────────────────────────────────────────────


class TestHandleGradeCoordinates:
    def test_none_arg_returns_error(self):
        from backend.services.assistant_tools_stem import handle_grade_coordinates

        result = handle_grade_coordinates(
            expected_latitude=None, expected_longitude=0,
            student_latitude=0, student_longitude=0,
        )
        assert "error" in result

    def test_non_numeric_arg_returns_error(self):
        from backend.services.assistant_tools_stem import handle_grade_coordinates

        result = handle_grade_coordinates(
            expected_latitude="not_a_number",
            expected_longitude=0,
            student_latitude=0,
            student_longitude=0,
        )
        assert "error" in result
        assert "number" in result["error"]

    def test_delegates_with_dict_payload_and_default_tolerance(self):
        from backend.services.assistant_tools_stem import handle_grade_coordinates

        sentinel = {"distance_km": 12.3, "score": 1}
        with patch("backend.services.assistant_tools_stem.grade_coordinate_question",
                   return_value=sentinel) as mock:
            result = handle_grade_coordinates(
                expected_latitude=51.5,
                expected_longitude=-0.1,
                student_latitude=51.6,
                student_longitude=-0.05,
            )
        assert result is sentinel
        expected_arg, student_arg, tol = mock.call_args.args
        assert expected_arg == {"latitude": 51.5, "longitude": -0.1}
        assert student_arg == {"latitude": 51.6, "longitude": -0.05}
        assert tol == 50

    def test_custom_tolerance_km_forwarded(self):
        from backend.services.assistant_tools_stem import handle_grade_coordinates

        with patch("backend.services.assistant_tools_stem.grade_coordinate_question",
                   return_value={}) as mock:
            handle_grade_coordinates(
                expected_latitude=0, expected_longitude=0,
                student_latitude=0, student_longitude=0,
                tolerance_km=5,
            )
        _exp, _stu, tol = mock.call_args.args
        assert tol == 5

    def test_string_numbers_coerced_to_float(self):
        from backend.services.assistant_tools_stem import handle_grade_coordinates

        with patch("backend.services.assistant_tools_stem.grade_coordinate_question",
                   return_value={}) as mock:
            handle_grade_coordinates(
                expected_latitude="1.5",
                expected_longitude="2.5",
                student_latitude="3.5",
                student_longitude="4.5",
            )
        expected_arg, student_arg, _tol = mock.call_args.args
        assert expected_arg == {"latitude": 1.5, "longitude": 2.5}
        assert student_arg == {"latitude": 3.5, "longitude": 4.5}


# ──────────────────────────────────────────────────────────────────
# handle_grade_place_name
# ──────────────────────────────────────────────────────────────────


class TestHandleGradePlaceName:
    def test_empty_accepted_names_returns_error(self):
        from backend.services.assistant_tools_stem import handle_grade_place_name

        result = handle_grade_place_name(
            accepted_names=[], student_answer="UK",
        )
        assert "error" in result
        assert "accepted_names" in result["error"]

    def test_none_accepted_names_returns_error(self):
        from backend.services.assistant_tools_stem import handle_grade_place_name

        result = handle_grade_place_name(
            accepted_names=None, student_answer="UK",
        )
        assert "error" in result

    def test_empty_student_answer_returns_error(self):
        from backend.services.assistant_tools_stem import handle_grade_place_name

        result = handle_grade_place_name(
            accepted_names=["UK", "Britain"], student_answer="",
        )
        assert "error" in result
        assert "student_answer" in result["error"]

    def test_whitespace_student_answer_returns_error(self):
        from backend.services.assistant_tools_stem import handle_grade_place_name

        result = handle_grade_place_name(
            accepted_names=["UK"], student_answer="   ",
        )
        assert "error" in result

    def test_delegates_with_stripped_student_answer(self):
        from backend.services.assistant_tools_stem import handle_grade_place_name

        sentinel = {"correct": True}
        with patch("backend.services.assistant_tools_stem.grade_place_name",
                   return_value=sentinel) as mock:
            result = handle_grade_place_name(
                accepted_names=["United Kingdom", "UK", "Britain"],
                student_answer="  UK  ",
            )
        assert result is sentinel
        mock.assert_called_once_with(
            ["United Kingdom", "UK", "Britain"], "UK",
        )


# ──────────────────────────────────────────────────────────────────
# Module-level exports
# ──────────────────────────────────────────────────────────────────


class TestExports:
    def test_definitions_count_matches_handlers(self):
        from backend.services.assistant_tools_stem import (
            STEM_TOOL_DEFINITIONS, STEM_TOOL_HANDLERS,
        )
        defined = {td["name"] for td in STEM_TOOL_DEFINITIONS}
        handled = set(STEM_TOOL_HANDLERS.keys())
        assert defined == handled, (
            f"Tool registry drift: definitions={defined}, handlers={handled}"
        )

    def test_handlers_are_callable(self):
        from backend.services.assistant_tools_stem import STEM_TOOL_HANDLERS

        for name, h in STEM_TOOL_HANDLERS.items():
            assert callable(h), f"Handler for {name} not callable"

    def test_expected_handler_names(self):
        from backend.services.assistant_tools_stem import STEM_TOOL_HANDLERS

        # All five expected handlers present
        assert set(STEM_TOOL_HANDLERS.keys()) == {
            "check_math_equivalence",
            "grade_math_question",
            "grade_data_table",
            "grade_coordinates",
            "grade_place_name",
        }
