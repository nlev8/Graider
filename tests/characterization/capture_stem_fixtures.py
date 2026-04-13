"""One-shot capture tool for stem_grading characterization fixtures.

Runs every CASE against the current stem_grading public surface and writes
(input, output) pairs to fixtures/stem_grading/*.json. Re-run MANUALLY when
adding coverage or when SymPy is intentionally bumped. Never run from CI.

stem_grading.py is a pure SymPy/math grader — no OpenAI, no network, no
randomness — so capture is deterministic. Strict JSON serialization (no
default=str): if a public function ever leaks a non-JSON-safe type, the
dump fails loud during capture.

Usage:
    PYTHONPATH=. python tests/characterization/capture_stem_fixtures.py

Design approved by Codex Gate 1 — 37 fixtures total. See the phase plan:
docs/superpowers/plans/2026-04-12-phase2-refactoring-prep.md Task 3.
"""
import json
import pathlib

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures" / "stem_grading"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)


# Each case: (name, fn_name, kwargs). Verified against the 2026-04-13
# public surface of backend/services/stem_grading.py.
CASES = [
    # ============================================================
    # check_math_equivalence — 9 branches
    # ============================================================
    ("math_plain_number_correct",   "check_math_equivalence",
        {"student_answer": "3.14", "correct_answer": "3.14"}),
    ("math_plain_number_wrong",     "check_math_equivalence",
        {"student_answer": "3.15", "correct_answer": "3.14"}),
    ("math_fraction_equivalent",    "check_math_equivalence",
        {"student_answer": "1/2", "correct_answer": "0.5"}),
    ("math_percent_equivalent",     "check_math_equivalence",
        {"student_answer": "50%", "correct_answer": "0.5"}),
    ("math_implicit_mult",          "check_math_equivalence",
        {"student_answer": "2x", "correct_answer": "2*x"}),
    ("math_caret_exponent",         "check_math_equivalence",
        {"student_answer": "x^2", "correct_answer": "x**2"}),
    ("math_latex_equivalent",       "check_math_equivalence",
        {"student_answer": r"\frac{1}{2}", "correct_answer": "0.5"}),
    ("math_unparseable_garbage",    "check_math_equivalence",
        {"student_answer": "@#$", "correct_answer": "3.14"}),
    ("math_empty_answer",           "check_math_equivalence",
        {"student_answer": "", "correct_answer": "3.14"}),
    ("math_numerical_equivalent",   "check_math_equivalence",
        # Fraction vs decimal approximation — symbolic check fails
        # (not exactly equal), SymPy falls through to numerical
        # tolerance and returns method='numerical'.
        {"student_answer": "2/3", "correct_answer": "0.6666666667"}),

    # ============================================================
    # grade_math_question — 8 branches
    # ============================================================
    ("question_math_empty_response",        "grade_math_question",
        # Pins the "no `correct` key" contract on early return.
        {"question": {"correctAnswer": "4", "acceptEquivalent": True,
                       "showWork": False, "points": 5},
         "student_response": ""}),
    ("question_math_missing_correct_answer", "grade_math_question",
        {"question": {"correctAnswer": "", "acceptEquivalent": True,
                       "showWork": False, "points": 5},
         "student_response": "4"}),
    ("question_math_equivalent_symbolic",   "grade_math_question",
        # x^2 vs x**2 → method=symbolic → "mathematically equivalent" feedback.
        {"question": {"correctAnswer": "x**2", "acceptEquivalent": True,
                       "showWork": False, "points": 5},
         "student_response": "x^2"}),
    ("question_math_equivalent_numerical",  "grade_math_question",
        # Fraction vs decimal approximation → SymPy routes through
        # the numerical tolerance fallback (method='numerical'), which
        # triggers the "Your answer is numerically equivalent" feedback
        # at stem_grading.py:275. NOTE: there's ALSO a 'numeric' return
        # value (plain-number fast path) whose feedback branch at :274
        # IS dead code due to the 'numeric' vs 'numerical' typo — but
        # the numerical branch hit here is reachable.
        {"question": {"correctAnswer": "0.6666666667", "acceptEquivalent": True,
                       "showWork": False, "points": 5},
         "student_response": "2/3"}),
    ("question_math_exact_match",           "grade_math_question",
        {"question": {"correctAnswer": "4", "acceptEquivalent": False,
                       "showWork": False, "points": 5},
         "student_response": "4"}),
    ("question_math_exact_mismatch",        "grade_math_question",
        {"question": {"correctAnswer": "4", "acceptEquivalent": False,
                       "showWork": False, "points": 5},
         "student_response": "5"}),
    ("question_math_wrong_showwork_flagged", "grade_math_question",
        # acceptEquivalent=True, response > 20 chars, showWork=True,
        # not equivalent → needs_ai_review
        {"question": {"correctAnswer": "4", "acceptEquivalent": True,
                       "showWork": True, "points": 5},
         "student_response": "I did a lot of work but the answer is 99"}),
    ("question_math_wrong_with_parse_error", "grade_math_question",
        # unparseable student response → "Could not fully parse" note
        {"question": {"correctAnswer": "4", "acceptEquivalent": True,
                       "showWork": False, "points": 5},
         "student_response": "@#$"}),

    # ============================================================
    # grade_data_table — 8 branches
    # ============================================================
    ("table_row_count_mismatch",    "grade_data_table",
        {"expected_table": {"data": [[1.0], [2.0], [3.0]]},
         "student_table":  {"data": [[1.0]]},
         "tolerance_percent": 5.0}),
    ("table_missing_value_in_row",  "grade_data_table",
        {"expected_table": {"data": [[1.0, 2.0]]},
         "student_table":  {"data": [[1.0]]},  # col_idx=1 missing
         "tolerance_percent": 5.0}),
    ("table_exact_cell_match",      "grade_data_table",
        {"expected_table": {"data": [["apple"]]},
         "student_table":  {"data": [["Apple"]]},  # case-insensitive
         "tolerance_percent": 5.0}),
    ("table_zero_equals_zero",      "grade_data_table",
        {"expected_table": {"data": [[0]]},
         "student_table":  {"data": [[0]]},
         "tolerance_percent": 5.0}),
    ("table_within_tolerance",      "grade_data_table",
        {"expected_table": {"data": [[100.0]]},
         "student_table":  {"data": [[103.0]]},  # 3% off, tolerance=5%
         "tolerance_percent": 5.0}),
    ("table_outside_tolerance_and_string_mismatch", "grade_data_table",
        # Row 0: numerical outside tolerance. Row 1: non-numeric mismatch.
        {"expected_table": {"data": [[100.0], ["apple"]]},
         "student_table":  {"data": [[200.0], ["banana"]]},
         "tolerance_percent": 5.0}),
    ("table_missing_row_pads_cells", "grade_data_table",
        # student_data strictly shorter than expected_data — hits
        # lines 385-395 "Missing row" per-cell fill
        {"expected_table": {"data": [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]},
         "student_table":  {"data": [[1.0, 2.0]]},
         "tolerance_percent": 5.0}),
    ("table_empty_expected",        "grade_data_table",
        # Pins score_percent=0 branch when total_cells=0
        {"expected_table": {"data": []},
         "student_table":  {"data": []},
         "tolerance_percent": 5.0}),

    # ============================================================
    # grade_coordinate_question — 7 branches
    # ============================================================
    ("coord_excellent_under_1km",   "grade_coordinate_question",
        # distance < 1 → "Excellent!"
        {"expected": {"latitude": 40.0, "longitude": -75.0},
         "student":  {"latitude": 40.0, "longitude": -75.0},
         "tolerance_km": 50.0}),
    ("coord_great_under_10km",      "grade_coordinate_question",
        # distance < 10 → "Great!"
        {"expected": {"latitude": 40.0,  "longitude": -75.0},
         "student":  {"latitude": 40.05, "longitude": -75.0},  # ~5.5 km
         "tolerance_km": 50.0}),
    ("coord_correct_within_tolerance", "grade_coordinate_question",
        # distance > 10 but <= tolerance → "Correct!"
        {"expected": {"latitude": 40.0, "longitude": -75.0},
         "student":  {"latitude": 40.2, "longitude": -75.0},  # ~22 km
         "tolerance_km": 50.0}),
    ("coord_out_of_tolerance_north_east_hints", "grade_coordinate_question",
        # Student south-west of expected → hint north + east.
        # Deltas > 0.1° so directional hints trigger.
        {"expected": {"latitude": 40.0, "longitude": -75.0},
         "student":  {"latitude": 39.5, "longitude": -75.5},
         "tolerance_km": 10.0}),
    ("coord_out_of_tolerance_south_west_hints", "grade_coordinate_question",
        # Student north-east of expected → hint south + west.
        {"expected": {"latitude": 40.0, "longitude": -75.0},
         "student":  {"latitude": 40.5, "longitude": -74.5},
         "tolerance_km": 10.0}),
    ("coord_out_of_tolerance_no_hint", "grade_coordinate_question",
        # Both deltas well under ±0.1° (0.05°) but distance exceeds a
        # small tolerance_km. 0.05° lat ≈ 5.5 km, tolerance 1 km → over
        # tolerance but no directional hint triggered. Margin per Codex.
        {"expected": {"latitude": 40.0,  "longitude": -75.0},
         "student":  {"latitude": 40.05, "longitude": -75.05},
         "tolerance_km": 1.0}),
    ("coord_parse_failure",         "grade_coordinate_question",
        # Non-numeric latitude → ValueError path
        {"expected": {"latitude": 40.0,     "longitude": -75.0},
         "student":  {"latitude": "not-a-number", "longitude": -75.0},
         "tolerance_km": 50.0}),

    # ============================================================
    # grade_place_name — 5 branches
    # ============================================================
    ("place_empty_answer",          "grade_place_name",
        {"expected_names": ["Paris"], "student_answer": ""}),
    ("place_exact_match_case_insensitive", "grade_place_name",
        {"expected_names": ["Paris"], "student_answer": "paris"}),
    ("place_partial_name_in_student", "grade_place_name",
        # "united kingdom" is inside "the united kingdom"
        {"expected_names": ["United Kingdom"],
         "student_answer": "The United Kingdom"}),
    ("place_partial_student_in_name", "grade_place_name",
        # "uk" is NOT inside "united kingdom" (no substring);
        # use "king" which IS inside "united kingdom"
        {"expected_names": ["United Kingdom"],
         "student_answer": "king"}),
    ("place_no_match",              "grade_place_name",
        {"expected_names": ["Paris"], "student_answer": "London"}),
]


def run():
    from backend.services import stem_grading

    written = 0
    for name, fn_name, kwargs in CASES:
        fn = getattr(stem_grading, fn_name)
        out = fn(**kwargs)
        fixture_path = FIXTURES_DIR / f"{name}.json"
        # Strict JSON: no default=str. If anything non-JSON-safe leaks,
        # this will raise TypeError and we'll surface it.
        fixture_path.write_text(
            json.dumps(
                {"input": {"fn": fn_name, "kwargs": kwargs}, "output": out},
                indent=2,
            )
        )
        written += 1
        print(f"  wrote {name}")

    print(f"\n{written} fixtures written to {FIXTURES_DIR}")


if __name__ == "__main__":
    run()
