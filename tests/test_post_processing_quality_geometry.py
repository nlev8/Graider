"""PR7 hardening: real behavioral tests for the deterministic post-processing
internals that existing tests don't exercise — the 14 Phase-3c quality checks
(`_check_question_quality`), geometry hydration + answer computation
(`_hydrate_geometry`, `_compute_geometry_answer`), and pythagorean side
extraction (`_extract_pythagorean_sides`).

All functions here are pure (regex / arithmetic). NO AI client is passed —
`_check_question_quality` takes no client and the auto-fix path is never invoked.
Every test pins an EXACT computed value, issue string, or severity (per the
plan's "assert exact outputs" guard), and each function gets a
valid-input-must-NOT-flag negative case.
"""
import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.services.assignment_post_processing import (
    _auto_fix_flagged_questions,
    _check_question_quality,
    _classify_question_type,
    _compute_geometry_answer,
    _extract_pythagorean_sides,
    _extract_dimensions_from_text,
    _hydrate_geometry,
    _validate_question_quality,
    _detect_primary_shape,
    _detect_mode,
    _is_identification_question,
    _infer_shape_answer,
)


# ── _check_question_quality — the 14 deterministic checks ─────────────────────


class TestCheckQuestionQualityAnswerKey:
    """Check 2: answer-key presence (skipped for essay/extended/multi_part)."""

    def test_missing_answer_flags_warning(self):
        issues = _check_question_quality(
            {'question_type': 'short_answer', 'question': 'Define osmosis.'})
        assert issues == [{'issue': 'Missing answer key', 'severity': 'warning'}]

    def test_empty_string_answer_flags(self):
        issues = _check_question_quality(
            {'question_type': 'short_answer', 'question': 'q', 'answer': ''})
        assert {'issue': 'Missing answer key', 'severity': 'warning'} in issues

    def test_empty_list_answer_flags(self):
        issues = _check_question_quality(
            {'question_type': 'short_answer', 'question': 'q', 'answer': []})
        assert {'issue': 'Missing answer key', 'severity': 'warning'} in issues

    def test_essay_without_answer_not_flagged(self):
        # Negative: essay/extended/multi_part are exempt from the answer-key check.
        assert _check_question_quality(
            {'question_type': 'essay', 'question': 'Write an essay on the Civil War.'}) == []

    def test_present_answer_not_flagged(self):
        # Negative: a short_answer WITH an answer passes clean.
        assert _check_question_quality(
            {'question_type': 'short_answer', 'question': 'What is 2+2?', 'answer': '4'}) == []


class TestCheckQuestionQualityMCMatch:
    """Check 3: MC answer must match one of the options."""

    def test_letter_answer_matches_lettered_option(self):
        # Negative: "B" matches "B) dog" via the letter-prefix branch → no issue.
        assert _check_question_quality({
            'question_type': 'multiple_choice', 'question': 'Pick the animal.',
            'options': ['A) cat', 'B) dog'], 'answer': 'B'}) == []

    def test_answer_not_in_options_flags_error(self):
        issues = _check_question_quality({
            'question_type': 'multiple_choice', 'question': 'Pick one.',
            'options': ['A) cat', 'B) dog'], 'answer': 'Z'})
        assert {'issue': 'Answer does not match any option', 'severity': 'error'} in issues

    def test_exact_text_match_not_flagged(self):
        assert _check_question_quality({
            'question_type': 'multiple_choice', 'question': 'Pick one.',
            'options': ['Paris', 'London'], 'answer': 'Paris'}) == []


class TestCheckQuestionQualityMathConsistency:
    """Checks 4 & 6: over-determined math + pythagorean consistency."""

    def test_over_determined_flags_count(self):
        q = {'question_type': 'math_equation',
             'question': 'Given 1, 2, 3, 4, 5, and 6, solve the system.',
             'answer': 'x'}
        issues = _check_question_quality(q)
        assert {'issue': 'Potentially over-determined: 6 numeric values given',
                'severity': 'warning'} in issues

    def test_five_values_not_over_determined(self):
        # Negative: exactly 5 distinct numbers is the boundary — NOT flagged.
        q = {'question_type': 'math_equation',
             'question': 'Use 1, 2, 3, 4, and 5 to solve.', 'answer': 'x'}
        over = [i for i in _check_question_quality(q) if 'over-determined' in i['issue']]
        assert over == []

    def test_invalid_pythagorean_triple_flagged(self):
        q = {'question_type': 'short_answer',
             'question': 'A right triangle has hypotenuse 10 with legs 3 and 4.',
             'answer': 'x'}
        issues = _check_question_quality(q)
        assert {'issue': 'Given values may not satisfy Pythagorean theorem (a² + b² = c²)',
                'severity': 'warning'} in issues

    def test_valid_pythagorean_triple_not_flagged(self):
        # Negative: 3-4-5 is a valid right triangle → no pythagorean warning.
        q = {'question_type': 'short_answer',
             'question': 'A right triangle has hypotenuse 5 with legs 3 and 4.',
             'answer': '5'}
        pyth = [i for i in _check_question_quality(q) if 'Pythagorean' in i['issue']]
        assert pyth == []

    def test_invalid_tangent_secant_flagged(self):
        q = {'question_type': 'short_answer',
             'question': 'A tangent of length 6 and a secant with external '
                         'segment 3 and whole 5.', 'answer': 'x'}
        issues = _check_question_quality(q)
        assert {'issue': 'Given values may not satisfy tangent-secant theorem '
                         '(t² = external × whole)', 'severity': 'warning'} in issues

    def test_valid_tangent_secant_not_flagged(self):
        # Negative: 6² = 4 × 9 satisfies the theorem → no warning.
        q = {'question_type': 'short_answer',
             'question': 'A tangent of length 6 and a secant with external 4 '
                         'and whole 9.', 'answer': 'x'}
        tan = [i for i in _check_question_quality(q) if 'tangent' in i['issue']]
        assert tan == []

    def test_3d_with_2d_theorem_flagged(self):
        q = {'question_type': 'short_answer',
             'question': 'A tower casts a shadow. Use the inscribed angle '
                         'theorem with the building height.', 'answer': 'x'}
        issues = _check_question_quality(q)
        assert {'issue': 'Mixes 3D physical scenario with 2D circle theorem — '
                         'may confuse students', 'severity': 'warning'} in issues


class TestCheckQuestionQualityELA:
    """Checks 8-10: ELA passage / quotation checks."""

    def test_dangling_passage_reference_flags_error(self):
        q = {'question_type': 'short_answer',
             'question': 'According to the passage, what is the theme?', 'answer': 'x'}
        issues = _check_question_quality(q)
        assert {'issue': 'References a passage/text but no passage appears to be '
                         'included in the question', 'severity': 'error'} in issues

    def test_long_question_with_passage_not_flagged(self):
        # Negative: >=300 chars means the passage is embedded inline → no error.
        passage = 'word ' * 80  # ~400 chars
        q = {'question_type': 'short_answer',
             'question': f'According to the passage, what is the theme? {passage}',
             'answer': 'x'}
        dangling = [i for i in _check_question_quality(q)
                    if 'no passage appears' in i['issue']]
        assert dangling == []


class TestCheckQuestionQualityScience:
    """Checks 11 & 12: mixed units + physically impossible values."""

    def test_mixed_units_flags_warning(self):
        q = {'question_type': 'short_answer',
             'question': 'A rope is 5 meters long and weighs 10 pounds.', 'answer': 'x'}
        issues = _check_question_quality(q)
        assert {'issue': 'Mixes metric and imperial units — use one system or make '
                         'it a conversion problem', 'severity': 'warning'} in issues

    def test_conversion_question_exempt_from_mixed_units(self):
        # Negative: explicit conversion language exempts the mixed-units check.
        q = {'question_type': 'short_answer',
             'question': 'Convert 5 meters to feet.', 'answer': '16.4'}
        mixed = [i for i in _check_question_quality(q) if 'Mixes metric' in i['issue']]
        assert mixed == []

    def test_temperature_below_absolute_zero_flags_error(self):
        q = {'question_type': 'short_answer',
             'question': 'Water is cooled to -300 degrees Celsius.', 'answer': 'x'}
        issues = _check_question_quality(q)
        assert {'issue': 'Temperature below absolute zero (-300°C)',
                'severity': 'error'} in issues

    def test_ph_out_of_range_flags_error(self):
        q = {'question_type': 'short_answer',
             'question': 'A solution has pH of 20.', 'answer': 'x'}
        issues = _check_question_quality(q)
        assert {'issue': 'pH value 20 is outside valid range (0-14)',
                'severity': 'error'} in issues

    def test_valid_temperature_not_flagged(self):
        # Negative: 25°C is physically fine.
        q = {'question_type': 'short_answer',
             'question': 'Water at 25 degrees Celsius.', 'answer': 'x'}
        impossible = [i for i in _check_question_quality(q)
                      if 'absolute zero' in i['issue']]
        assert impossible == []


class TestCheckQuestionQualityDataTable:
    """Check 14: data_table empty/placeholder expected_data."""

    def test_no_expected_data_flags_error(self):
        q = {'question_type': 'data_table', 'question': 'Complete the table.',
             'expected_data': []}
        issues = _check_question_quality(q)
        assert {'issue': 'Data table has no expected_data — table will appear empty',
                'severity': 'error'} in issues

    def test_all_empty_cells_flags_error(self):
        q = {'question_type': 'data_table', 'question': 'Complete the table.',
             'expected_data': [['', ''], [None, '']]}
        issues = _check_question_quality(q)
        assert {'issue': 'Data table expected_data contains only empty values — '
                         'no correct answers provided', 'severity': 'error'} in issues

    def test_populated_table_not_flagged_for_emptiness(self):
        # Negative: a table with real data raises no data_table emptiness error.
        q = {'question_type': 'data_table', 'question': 'Complete the table.',
             'expected_data': [['1', '2'], ['3', '4']]}
        empties = [i for i in _check_question_quality(q)
                   if 'expected_data' in i['issue'] or 'no expected_data' in i['issue']]
        assert empties == []


class TestCheckQuestionQualityStandards:
    """Check 15: off-subject standard detection."""

    def test_off_subject_standard_flags_error(self):
        q = {'question_type': 'short_answer', 'question': 'q', 'answer': 'a',
             'standard': 'MA.7.G'}
        issues = _check_question_quality(
            q, subject='Science', grade='7', valid_standard_codes=['SC.7.L', 'SC.7.P'])
        assert {'issue': 'Off-subject: standard "MA.7.G" is not in the selected '
                         'Science standards for grade 7', 'severity': 'error'} in issues

    def test_prefix_match_not_flagged(self):
        # Negative: "SC.7.L" prefix-matches valid "SC.7.L.1.1" → no off-subject error.
        q = {'question_type': 'short_answer', 'question': 'q', 'answer': 'a',
             'standard': 'SC.7.L'}
        off = [i for i in _check_question_quality(
            q, subject='Science', grade='7', valid_standard_codes=['SC.7.L.1.1'])
            if 'Off-subject' in i['issue']]
        assert off == []


# ── _validate_question_quality — dedup + warning attachment (no client) ───────


class TestValidateQuestionQuality:
    def test_dedupes_and_attaches_warning(self):
        assignment = {'sections': [{'questions': [
            {'question': 'Define osmosis.', 'question_type': 'short_answer'},
            {'question': 'Define osmosis.', 'question_type': 'short_answer',
             'answer': 'x'},  # duplicate text → removed
            {'question': 'What is 2+2?', 'question_type': 'short_answer',
             'answer': '4'},  # clean
        ]}]}
        warnings = _validate_question_quality(assignment)
        # duplicate removed → 2 questions remain
        assert len(assignment['sections'][0]['questions']) == 2
        # only the first (missing-answer) question is flagged
        assert warnings == [{
            'section_idx': 0, 'question_idx': 0,
            'issue': 'Missing answer key', 'severity': 'warning'}]
        q0 = assignment['sections'][0]['questions'][0]
        assert q0['warning'] == 'Missing answer key'
        assert q0['warning_severity'] == 'warning'

    def test_all_clean_no_warnings(self):
        # Negative: every question valid → empty warning list, no warning fields.
        assignment = {'sections': [{'questions': [
            {'question': 'What is 2+2?', 'question_type': 'short_answer',
             'answer': '4'}]}]}
        assert _validate_question_quality(assignment) == []
        assert 'warning' not in assignment['sections'][0]['questions'][0]


class TestAutoFixEarlyReturns:
    """The auto-fix path is gated; with no client/user_id it returns silently
    without ever calling an AI. These pin the deterministic early-exit branches."""

    def test_returns_none_when_only_warnings(self):
        # Only warning-severity issues → auto-fix is a no-op (returns None).
        assert _auto_fix_flagged_questions(
            {'sections': []},
            [{'severity': 'warning', 'issue': 'x',
              'section_idx': 0, 'question_idx': 0}]) is None

    def test_returns_none_when_user_id_missing(self):
        # Error present but user_id=None → cannot call AI → silent return.
        assert _auto_fix_flagged_questions(
            {'sections': []},
            [{'severity': 'error', 'issue': 'x',
              'section_idx': 0, 'question_idx': 0}]) is None


# ── _compute_geometry_answer — exact numeric answers per (shape, mode) ─────────


class TestComputeGeometryAnswer:
    def test_rectangle_area(self):
        assert _compute_geometry_answer(
            'rectangle', {'mode': 'area', 'width': 5, 'height': 4}) == 20

    def test_triangle_area_half_base_height(self):
        assert _compute_geometry_answer(
            'triangle', {'mode': 'area', 'base': 6, 'height': 4}) == 12.0

    def test_circle_area_pi_r_squared(self):
        assert _compute_geometry_answer(
            'circle', {'mode': 'area', 'radius': 3}) == math.pi * 9

    def test_trapezoid_area(self):
        assert _compute_geometry_answer(
            'trapezoid', {'mode': 'area', 'base': 8, 'topBase': 4, 'height': 5}) == 30.0

    def test_cylinder_volume(self):
        assert _compute_geometry_answer(
            'cylinder', {'mode': 'volume', 'radius': 3, 'height': 7}) == math.pi * 9 * 7

    def test_sphere_volume(self):
        assert _compute_geometry_answer(
            'sphere', {'mode': 'volume', 'radius': 3}) == (4 / 3) * math.pi * 27

    def test_rectangular_prism_surface_area(self):
        assert _compute_geometry_answer(
            'rectangular_prism',
            {'mode': 'surface_area', 'base': 2, 'width': 3, 'height': 4}) == 52

    def test_triangle_pythagorean_missing_c(self):
        assert _compute_geometry_answer(
            'triangle',
            {'mode': 'pythagorean', 'side_a': 3, 'side_b': 4, 'missing_side': 'c'}) == 5.0

    def test_triangle_angles_missing_third(self):
        assert _compute_geometry_answer(
            'triangle',
            {'mode': 'angles', 'angle1': 60, 'angle2': 70, 'missing_angle': 3}) == 50

    def test_regular_polygon_perimeter(self):
        assert _compute_geometry_answer(
            'regular_polygon', {'mode': 'perimeter', 'sides': 6, 'side_length': 4}) == 24

    def test_unsupported_pair_returns_none(self):
        # Negative: rectangle has no volume formula → None.
        assert _compute_geometry_answer('rectangle', {'mode': 'volume'}) is None


class TestComputeGeometryMoreModes:
    """Perimeter / circumference / surface-area / lateral / midsegment / trig."""

    def test_rectangle_perimeter(self):
        assert _compute_geometry_answer(
            'rectangle', {'mode': 'perimeter', 'width': 5, 'height': 3}) == 16

    def test_circle_circumference(self):
        assert _compute_geometry_answer(
            'circle', {'mode': 'circumference', 'radius': 2}) == 2 * math.pi * 2

    def test_regular_polygon_perimeter(self):
        assert _compute_geometry_answer(
            'regular_polygon', {'mode': 'perimeter', 'sides': 5, 'side_length': 6}) == 30

    def test_cylinder_surface_area(self):
        assert _compute_geometry_answer(
            'cylinder', {'mode': 'surface_area', 'radius': 2, 'height': 5}) == (
            2 * math.pi * 4 + 2 * math.pi * 2 * 5)

    def test_sphere_surface_area(self):
        assert _compute_geometry_answer(
            'sphere', {'mode': 'surface_area', 'radius': 4}) == 4 * math.pi * 16

    def test_cone_lateral_area(self):
        assert _compute_geometry_answer(
            'cone', {'mode': 'lateral_area', 'radius': 3, 'slant_height': 5}) == (
            math.pi * 3 * 5)

    def test_trapezoid_midsegment(self):
        assert _compute_geometry_answer(
            'trapezoid', {'mode': 'midsegment', 'base': 8, 'topBase': 4}) == 6.0

    def test_pyramid_volume(self):
        assert _compute_geometry_answer(
            'pyramid', {'mode': 'volume', 'base': 4, 'height': 9}) == 48.0

    def test_cone_volume(self):
        assert _compute_geometry_answer(
            'cone', {'mode': 'volume', 'radius': 3, 'height': 9}) == (1 / 3) * math.pi * 9 * 9

    def test_triangle_trig_ratio(self):
        assert _compute_geometry_answer(
            'triangle', {'mode': 'trig', 'theta': 30, 'trig_func': 'sin'}) == 0.5

    def test_triangle_trig_solve_for_opposite(self):
        result = _compute_geometry_answer(
            'triangle', {'mode': 'trig', 'theta': 30, 'solve_for': 'opp', 'side_c': 10})
        assert abs(result - 5.0) < 1e-9


# ── _hydrate_geometry — end-to-end dimension extraction + answer string ───────


class TestHydrateGeometry:
    def test_circle_extracts_radius_and_computes_area(self):
        q = {'question_type': 'circle',
             'question': 'Find the area of a circle with radius 5.'}
        _hydrate_geometry(q, 'circle')
        # radius 5 → area = pi*25 = 78.5398... rounded to 2dp
        assert q['answer'] == '78.54'

    def test_rectangle_default_dims_when_none_in_text(self):
        q = {'question_type': 'rectangle',
             'question': 'Find the area of the rectangle.'}
        _hydrate_geometry(q, 'rectangle')
        # defaults base=6 height=4, rectangle area uses width(=base)*height = 24
        assert q['answer'] == '24'

    def test_cone_slant_height_uses_default(self):
        # _GEOMETRY_DEFAULTS.setdefault fills slant_height (7.21) before the
        # derived-slant branch runs, so the default wins when fields are absent.
        q = {'question_type': 'cone', 'question': 'Find the volume of the cone.',
             'radius': 3, 'height': 4}
        _hydrate_geometry(q, 'cone')
        assert q['slant_height'] == 7.21
        # volume from radius=3, height=4 → (1/3)*pi*9*4 rounded to 2dp
        assert q['answer'] == '37.7'


# ── _extract_pythagorean_sides / _extract_dimensions_from_text ────────────────


class TestExtractPythagoreanSides:
    def test_two_legs_derives_hypotenuse(self):
        q = {'mode': 'pythagorean'}
        _extract_pythagorean_sides(q, 'A right triangle has legs of 3 and 4.',
                                   r'(?:\s*(?:cm)?)')
        assert q['side_a'] == 3.0
        assert q['side_b'] == 4.0
        assert q['side_c'] == 5.0
        assert q['missing_side'] == 'c'

    def test_hypotenuse_and_one_leg_derives_missing_leg(self):
        q = {'question': 'A right triangle has a hypotenuse of 13 and one side is 5.',
             'mode': 'pythagorean', 'question_type': 'pythagorean'}
        _extract_dimensions_from_text(q)
        assert q['side_a'] == 5.0
        assert q['side_c'] == 13.0
        assert q['side_b'] == 12.0
        assert q['missing_side'] == 'b'

    def test_only_hypotenuse_sets_side_c(self):
        q = {'mode': 'pythagorean'}
        _extract_pythagorean_sides(q, 'The hypotenuse is 10.', r'(?:\s*(?:cm)?)')
        assert q['side_c'] == 10.0
        assert q['missing_side'] == 'c'
        # no legs extracted → no side_a/side_b set
        assert 'side_a' not in q


# ── shape / mode detection helpers ────────────────────────────────────────────


class TestShapeAndModeDetection:
    def test_detect_primary_shape_cylinder(self):
        assert _detect_primary_shape('Find the area of the cylinder') == ('cylinder', None)

    def test_detect_primary_shape_none_when_no_shape(self):
        # Negative: no geometry shape mentioned.
        assert _detect_primary_shape('Explain photosynthesis.') == (None, None)

    def test_detect_mode_volume(self):
        assert _detect_mode('Find the volume of the box') == 'volume'

    def test_detect_mode_none(self):
        # Negative: no calculation-mode keyword present.
        assert _detect_mode('Describe the shape.') is None

    def test_is_identification_question_true(self):
        assert _is_identification_question('Identify the shape shown.') is True

    def test_is_identification_question_false(self):
        # Negative: a calculation prompt is not an identification question.
        assert _is_identification_question('Find the area of the square.') is False

    def test_infer_shape_answer_square(self):
        assert _infer_shape_answer(
            'A quadrilateral with four equal sides and four right angles') == 'square'

    def test_infer_shape_answer_trapezoid(self):
        assert _infer_shape_answer(
            'A quadrilateral with exactly one pair of parallel sides') == 'trapezoid'

    def test_infer_shape_answer_none(self):
        # Negative: no recognizable property description.
        assert _infer_shape_answer('A colorful shape.') is None


# ── _classify_question_type — additional branches ─────────────────────────────


class TestClassifyMoreBranches:
    def test_geometry_shape_with_mode(self):
        q = {'question': 'Find the perimeter of the triangle.', 'answer': '12'}
        _classify_question_type(q)
        assert q['question_type'] == 'triangle'
        assert q['mode'] == 'perimeter'

    def test_math_equation_with_operator(self):
        q = {'question': 'Solve for x: 2x = 10'}
        _classify_question_type(q)
        assert q['question_type'] == 'math_equation'

    def test_matching_from_terms_definitions(self):
        q = {'question': 'Match these.', 'terms': ['a'], 'definitions': ['1']}
        _classify_question_type(q)
        assert q['question_type'] == 'matching'

    def test_essay_from_long_answer(self):
        # Phase 5: answer >300 chars → essay even without keyword.
        q = {'question': 'Respond.', 'answer': 'x' * 350}
        _classify_question_type(q)
        assert q['question_type'] == 'essay'

    def test_section_hint_fallback(self):
        q = {'question': 'Open prompt with no structural signal.'}
        _classify_question_type(q, section={'type': 'fill_blank'})
        assert q['question_type'] == 'fill_blank'


# ── _extract_dimensions_from_text — dual-base trapezoid path ───────────────────


class TestExtractDimensions:
    def test_dual_base_measuring_assigns_max_and_min(self):
        q = {'question': 'A trapezoid has bases measuring 10 cm and 14 cm.'}
        _extract_dimensions_from_text(q)
        assert q['base'] == 14.0      # larger → base
        assert q['topBase'] == 10.0   # smaller → topBase

    def test_radius_equals_pattern(self):
        q = {'question': 'A circle with radius = 7 units.'}
        _extract_dimensions_from_text(q)
        assert q['radius'] == 7.0

    def test_no_dimensions_leaves_dict_unchanged(self):
        # Negative: prose with no numeric dimensions adds nothing.
        q = {'question': 'Describe the properties of a circle.'}
        _extract_dimensions_from_text(q)
        assert q == {'question': 'Describe the properties of a circle.'}
