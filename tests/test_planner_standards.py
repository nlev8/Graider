"""planner_standards service — runs with NO Flask app/test client.
The import itself is the decoupling proof: these functions must be
callable outside the route module."""
from backend.services import planner_standards as ps


def test_extract_grade_from_code_pulls_grade_digits():
    assert ps._extract_grade_from_code("MATH.5.NBT.1") == "5" or \
        ps._extract_grade_from_code("5.NBT.1") == "5"


def test_grade_matches_is_symmetric_on_equal_grades():
    assert ps._grade_matches("5", "5") is True
    assert ps._grade_matches("5", "7") is False


def test_module_has_no_flask_import():
    src = open(ps.__file__, encoding="utf-8").read()
    assert "from flask import" not in src and "import flask" not in src, \
        "planner_standards must not depend on Flask (coupling-reduction rule)"
