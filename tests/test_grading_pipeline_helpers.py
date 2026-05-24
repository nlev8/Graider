"""Unit tests for the shared deterministic scoring helpers (Wave 8 slice 1).

`_letter_grade` and `_completeness_cap_table` were extracted from the duplicated inline
ladders/tables in grade_assignment / grade_multipass / grade_with_ensemble. These pin the
exact thresholds + cap tables so the dedup is provably behavior-preserving (the integration
behavior is also pinned by tests/test_grader_golden.py + test_grading_factors.py).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.services.grading_pipeline import (
    _COMPLETENESS_CAPS,
    _completeness_cap_table,
    _letter_grade,
)


def test_letter_grade_boundaries():
    # exact thresholds: >=90 A, >=80 B, >=70 C, >=60 D, else F
    assert _letter_grade(100) == "A"
    assert _letter_grade(90) == "A"
    assert _letter_grade(89) == "B"
    assert _letter_grade(80) == "B"
    assert _letter_grade(79) == "C"
    assert _letter_grade(70) == "C"
    assert _letter_grade(69) == "D"
    assert _letter_grade(60) == "D"
    assert _letter_grade(59) == "F"
    assert _letter_grade(0) == "F"


def test_completeness_cap_tables_exact():
    assert _completeness_cap_table("strict") == {0: 100, 1: 85, 2: 75, 3: 65, 4: 55, 5: 45, 6: 35, 7: 25, 8: 15}
    assert _completeness_cap_table("lenient") == {0: 100, 1: 95, 2: 89, 3: 79, 4: 69, 5: 59, 6: 49, 7: 39, 8: 29}
    assert _completeness_cap_table("standard") == {0: 100, 1: 89, 2: 79, 3: 69, 4: 59, 5: 49, 6: 39, 7: 29, 8: 19}


def test_completeness_cap_unknown_style_falls_back_to_standard():
    # matches the prior `else:` branch — any non-strict/lenient style uses the standard table
    assert _completeness_cap_table("") == _COMPLETENESS_CAPS["standard"]
    assert _completeness_cap_table("weird") == _COMPLETENESS_CAPS["standard"]
    assert _completeness_cap_table(None) == _COMPLETENESS_CAPS["standard"]
