"""PR7 hardening: real behavioral tests for the deterministic Phase-2 hydration
helpers in assignment_post_processing.py (box/dot/stem plots, transformations,
fraction model, unit circle, protractor, grid match, inline dropdown, matching,
data_table editable-column inference).

All pure arithmetic / regex — no AI client. Each test pins the EXACT computed
structure the frontend renders from (per plan's "assert computed output" guard),
plus a negative/edge case where the helper must NOT alter or must default.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.services.assignment_post_processing import (
    _hydrate_box_plot,
    _hydrate_dot_plot,
    _hydrate_stem_and_leaf,
    _hydrate_transformations,
    _hydrate_fraction_model,
    _hydrate_unit_circle,
    _hydrate_protractor,
    _hydrate_grid_match,
    _hydrate_inline_dropdown,
    _hydrate_matching,
    _hydrate_data_table,
    _infer_editable_columns,
)


class TestBoxPlot:
    def test_five_number_summary(self):
        q = {'data': [2, 4, 6, 8, 10, 12, 14]}
        _hydrate_box_plot(q)
        assert q['correct_values'] == {
            'min': 2, 'max': 14, 'median': 8, 'q1': 4, 'q3': 12,
            'range': 12, 'iqr': 8}

    def test_empty_data_defaults_no_summary(self):
        # Negative: no data → defaults applied, no correct_values computed.
        q = {}
        _hydrate_box_plot(q)
        assert q['labels'] == ['Data']
        assert 'correct_values' not in q


class TestDotPlot:
    def test_frequency_map(self):
        q = {'data': [1, 1, 2, 3, 3, 3]}
        _hydrate_dot_plot(q)
        assert q['correct_dots'] == {'1': 2, '2': 1, '3': 3}

    def test_defaults_when_no_data(self):
        q = {}
        _hydrate_dot_plot(q)
        assert q['min_val'] == 0 and q['max_val'] == 10 and q['step'] == 1
        assert q['correct_dots'] == {}


class TestStemAndLeaf:
    def test_leaves_grouped_by_stem(self):
        q = {'data': [12, 15, 23, 25, 31]}
        _hydrate_stem_and_leaf(q)
        assert q['correct_leaves'] == {'1': '2 5', '2': '3 5', '3': '1'}
        assert q['stems'] == ['1', '2', '3']

    def test_no_data_empty_leaves(self):
        q = {}
        _hydrate_stem_and_leaf(q)
        assert q['correct_leaves'] == {} and q['stems'] == []


class TestTransformations:
    def test_translation(self):
        q = {'original_vertices': [[1, 1], [2, 2]],
             'transformation_type': 'translation',
             'transform_params': {'dx': 3, 'dy': -1}}
        _hydrate_transformations(q)
        assert q['correct_vertices'] == [[4, 0], [5, 1]]

    def test_reflection_over_x_axis(self):
        q = {'original_vertices': [[2, 3]],
             'transformation_type': 'reflection',
             'transform_params': {'axis': 'x-axis'}}
        _hydrate_transformations(q)
        assert q['correct_vertices'] == [[2, -3]]

    def test_dilation_scales_from_center(self):
        q = {'original_vertices': [[2, 2]],
             'transformation_type': 'dilation',
             'transform_params': {'scale': 2, 'centerX': 0, 'centerY': 0}}
        _hydrate_transformations(q)
        assert q['correct_vertices'] == [[4.0, 4.0]]


class TestFractionModel:
    def test_numerator_from_answer(self):
        q = {'answer': '3/8'}
        _hydrate_fraction_model(q)
        assert q['correct_numerator'] == 3
        assert q['denominator'] == 4  # default

    def test_non_fraction_answer_no_numerator(self):
        # Negative: answer without '/' yields no correct_numerator.
        q = {'answer': 'half'}
        _hydrate_fraction_model(q)
        assert 'correct_numerator' not in q


class TestUnitCircle:
    def test_standard_angle_values(self):
        q = {'hidden_values': ['30', '90']}
        _hydrate_unit_circle(q)
        assert q['correct_values'] == {
            '30_cos': '√3/2', '30_sin': '1/2',
            '90_cos': '0', '90_sin': '1'}

    def test_no_hidden_values_empty(self):
        q = {}
        _hydrate_unit_circle(q)
        assert q['correct_values'] == {}


class TestProtractor:
    def test_classify_acute(self):
        q = {'mode': 'classify', 'target_angle': 45}
        _hydrate_protractor(q)
        assert q['answer'] == 'acute'

    def test_classify_obtuse(self):
        q = {'mode': 'classify', 'target_angle': 120}
        _hydrate_protractor(q)
        assert q['answer'] == 'obtuse'

    def test_classify_right(self):
        q = {'mode': 'classify', 'target_angle': 90}
        _hydrate_protractor(q)
        assert q['answer'] == 'right'

    def test_construct_uses_target_angle(self):
        q = {'mode': 'construct', 'target_angle': 75}
        _hydrate_protractor(q)
        assert q['answer'] == '75'

    def test_measure_mode_no_answer_added(self):
        # Negative: default measure mode does not synthesize an answer.
        q = {'mode': 'measure', 'target_angle': 50}
        _hydrate_protractor(q)
        assert 'answer' not in q


class TestGridMatch:
    def test_pads_correct_matrix_to_label_dims(self):
        q = {'row_labels': ['a', 'b'], 'column_labels': ['x', 'y'],
             'correct': [[1, 0]]}
        _hydrate_grid_match(q)
        # one row supplied for two row-labels → padded with a zero row
        assert q['correct'] == [[1, 0], [0, 0]]


class TestInlineDropdown:
    def test_pads_dropdowns_to_placeholder_count(self):
        q = {'question': 'The {0} is bigger than the {1}.', 'dropdowns': []}
        _hydrate_inline_dropdown(q)
        assert q['dropdowns'] == [
            {'options': ['—'], 'correct': 0},
            {'options': ['—'], 'correct': 0}]


class TestMatching:
    def test_index_array_normalized_to_dict(self):
        q = {'terms': ['Cat', 'Dog'], 'definitions': ['Meow', 'Bark'],
             'correct_answer': [0, 1]}
        _hydrate_matching(q)
        assert q['correct_answer'] == {'Cat': 'Meow', 'Dog': 'Bark'}
        assert q['answer'] == {'Cat': 'Meow', 'Dog': 'Bark'}

    def test_string_array_parsed(self):
        q = {'terms': ['A', 'B'], 'definitions': ['x', 'y'],
             'correct_answer': ['A - x', 'B - y']}
        _hydrate_matching(q)
        assert q['correct_answer'] == {'A': 'x', 'B': 'y'}

    def test_fallback_positional_mapping(self):
        # No answer supplied → terms[i] maps to definitions[i] in order.
        q = {'terms': ['One', 'Two'], 'definitions': ['1', '2']}
        _hydrate_matching(q)
        assert q['correct_answer'] == {'One': '1', 'Two': '2'}

    def test_missing_terms_returns_early(self):
        # Negative: no terms → function returns without setting correct_answer.
        q = {'definitions': ['x']}
        _hydrate_matching(q)
        assert 'correct_answer' not in q


class TestDataTableHydration:
    def test_fillable_table_built_from_headers(self):
        q = {'question_type': 'data_table', 'question': 'Complete the table.',
             'headers': ['Name', 'Value'], 'row_labels': ['a', 'b', 'c']}
        _hydrate_data_table(q)
        # builds an empty grid sized to rows x cols
        assert q['expected_data'] == [['', ''], ['', ''], ['', '']]
        assert q['num_rows'] == 3

    def test_no_structure_downgrades_to_short_answer(self):
        # Negative: no headers/row_labels/expected_data → downgrade.
        q = {'question_type': 'data_table', 'question': 'Complete the table.'}
        _hydrate_data_table(q)
        assert q['question_type'] == 'short_answer'

    def test_initial_data_blanks_editable_columns(self):
        q = {'question_type': 'data_table',
             'question': 'Complete the table.',
             'headers': ['Object', 'Speed'],
             'expected_data': [['car', '60'], ['bus', '40']],
             'editable_columns': [1]}
        _hydrate_data_table(q)
        # editable column 1 blanked in initial_data, given column 0 preserved
        assert q['initial_data'] == [['car', ''], ['bus', '']]


class TestInferEditableColumns:
    def test_formula_result_matched_to_header(self):
        q = {'headers': ['Distance', 'Time', 'Speed']}
        cols = _infer_editable_columns(q, 'Calculate speed = distance / time.')
        assert cols == [2]

    def test_no_headers_returns_empty(self):
        # Negative: without headers nothing can be inferred.
        assert _infer_editable_columns({}, 'Calculate the average.') == []
