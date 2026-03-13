"""Tests for the deterministic post-processing pipeline in planner_routes.py.
Pure functions — no Flask app, no I/O, no AI calls."""
import pytest
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.routes.planner_routes import (
    _classify_question_type,
    _hydrate_question,
    _validate_question,
    _normalize_points,
    _post_process_assignment,
    _is_project_question,
    _DEFAULT_POINTS,
    _REQUIRED_FIELDS,
)


# ── TestClassifyQuestionType ──────────────────────────────────────────────


class TestClassifyQuestionType:
    """Phase 1: Deterministic type classification."""

    def test_mc_with_options(self):
        q = {'question': 'What color is the sky?', 'options': ['Blue', 'Red', 'Green']}
        _classify_question_type(q, None)
        assert q['question_type'] == 'multiple_choice'

    def test_true_false_answer(self):
        q = {'question': 'The earth is round.', 'answer': 'True'}
        _classify_question_type(q, None)
        assert q['question_type'] == 'true_false'

    def test_fill_blank_underscores(self):
        q = {'question': 'The capital of France is ___.', 'answer': 'Paris'}
        _classify_question_type(q, None)
        assert q['question_type'] == 'fill_blank'

    def test_matching_terms_definitions(self):
        q = {
            'question': 'Match the terms.',
            'terms': ['Photosynthesis', 'Respiration'],
            'definitions': ['Makes food', 'Breaks down food'],
        }
        _classify_question_type(q, None)
        assert q['question_type'] == 'matching'

    def test_geometry_rectangle_area(self):
        q = {'question': 'Find the area of the rectangle.', 'answer': '24'}
        _classify_question_type(q, None)
        assert q['question_type'] == 'rectangle'
        assert q['mode'] == 'area'

    def test_geometry_no_mode_downgrades(self):
        """Shape detected but no mode keyword → downgrade to short_answer."""
        q = {'question': 'Describe the rectangle.', 'question_type': 'rectangle'}
        _classify_question_type(q, None)
        assert q['question_type'] == 'short_answer'

    def test_function_graph(self):
        q = {'question': 'Graph the equation y = 2x + 1.'}
        _classify_question_type(q, None)
        assert q['question_type'] == 'function_graph'

    def test_coordinate_plane(self):
        q = {'question': 'Plot the point on the coordinate plane.'}
        _classify_question_type(q, None)
        assert q['question_type'] == 'coordinate_plane'

    def test_number_line(self):
        q = {'question': 'Plot 3 on the number line.'}
        _classify_question_type(q, None)
        assert q['question_type'] == 'number_line'

    def test_math_equation(self):
        q = {'question': 'Solve 3x + 5 = 20.'}
        _classify_question_type(q, None)
        assert q['question_type'] == 'math_equation'

    def test_essay(self):
        q = {'question': 'Write a paragraph explaining in detail why the Civil War started.'}
        _classify_question_type(q, None)
        assert q['question_type'] == 'essay'

    def test_trusted_ai_type_preserved(self):
        q = {'question': 'Complete the table.', 'question_type': 'data_table'}
        _classify_question_type(q, None)
        assert q['question_type'] == 'data_table'

    def test_default_short_answer(self):
        q = {'question': 'What is democracy?'}
        _classify_question_type(q, None)
        assert q['question_type'] == 'short_answer'


# ── TestHydrateQuestion ───────────────────────────────────────────────────


class TestHydrateQuestion:
    """Phase 2: Populate rendering fields."""

    def test_function_graph_defaults(self):
        q = {'question_type': 'function_graph', 'correct_expressions': ['y = x']}
        _hydrate_question(q)
        assert q['x_range'] == [-10, 10]
        assert q['y_range'] == [-10, 10]
        assert q['max_expressions'] == 3

    def test_coordinate_plane_defaults(self):
        q = {'question_type': 'coordinate_plane'}
        _hydrate_question(q)
        assert q['x_range'] == [-10, 10]
        assert q['y_range'] == [-10, 10]
        assert q['points_to_plot'] == []

    def test_number_line_defaults(self):
        q = {'question_type': 'number_line'}
        _hydrate_question(q)
        assert q['min_val'] == -10
        assert q['max_val'] == 10
        assert q['points_to_plot'] == []

    def test_bar_chart_defaults(self):
        q = {'question_type': 'bar_chart'}
        _hydrate_question(q)
        assert 'chart_data' in q
        assert q['chart_data'] == {'labels': [], 'values': [], 'title': ''}

    def test_venn_diagram_defaults(self):
        q = {'question_type': 'venn_diagram'}
        _hydrate_question(q)
        assert q['sets'] == 2
        assert q['set_labels'] == ['Set A', 'Set B']
        assert q['correct_values'] == {}
        assert q['mode'] == 'count'

    def test_tape_diagram_defaults(self):
        q = {'question_type': 'tape_diagram'}
        _hydrate_question(q)
        assert q['tapes'] == []
        assert q['correct_values'] == {}

    def test_probability_tree_defaults(self):
        q = {'question_type': 'probability_tree'}
        _hydrate_question(q)
        assert q['tree'] is None
        assert q['correct_values'] == {}

    def test_multiselect_float_indices_to_int(self):
        q = {'question_type': 'multiselect', 'options': ['A', 'B', 'C'], 'correct': [0.0, 2.0]}
        _hydrate_question(q)
        assert q['correct'] == [0, 2]
        assert all(isinstance(c, int) for c in q['correct'])


# ── TestValidateQuestion ──────────────────────────────────────────────────


class TestValidateQuestion:
    """Phase 3: Downgrade broken questions to short_answer."""

    def test_mc_with_options_stays(self):
        q = {'question_type': 'multiple_choice', 'options': ['A', 'B', 'C']}
        _validate_question(q)
        assert q['question_type'] == 'multiple_choice'

    def test_mc_without_options_downgraded(self):
        q = {'question_type': 'multiple_choice'}
        _validate_question(q)
        assert q['question_type'] == 'short_answer'

    def test_matching_without_terms_downgraded(self):
        q = {'question_type': 'matching', 'definitions': ['def1']}
        _validate_question(q)
        assert q['question_type'] == 'short_answer'

    def test_geometry_without_mode_downgraded(self):
        q = {'question_type': 'rectangle'}
        _validate_question(q)
        assert q['question_type'] == 'short_answer'

    def test_short_answer_no_required_fields(self):
        q = {'question_type': 'short_answer', 'question': 'Explain photosynthesis.'}
        _validate_question(q)
        assert q['question_type'] == 'short_answer'

    def test_data_table_without_headers_downgraded(self):
        q = {'question_type': 'data_table', 'expected_data': [[1, 2]]}
        _validate_question(q)
        assert q['question_type'] == 'short_answer'


# ── TestNormalizePoints ───────────────────────────────────────────────────


class TestNormalizePoints:
    """Phase 5: Ensure points sum correctly."""

    def _make_assignment(self, questions, section_count=1):
        """Helper: wrap questions into an assignment dict."""
        if section_count == 1:
            return {'sections': [{'name': 'Section 1', 'questions': questions}]}
        # Split questions across sections
        per_sec = max(1, len(questions) // section_count)
        sections = []
        for i in range(section_count):
            chunk = questions[i * per_sec:(i + 1) * per_sec]
            if chunk:
                sections.append({'name': f'Section {i + 1}', 'questions': chunk})
        return {'sections': sections}

    def test_missing_points_assigned_defaults(self):
        qs = [{'question_type': 'multiple_choice'}, {'question_type': 'essay'}]
        a = self._make_assignment(qs)
        _normalize_points(a)
        assert qs[0]['points'] == _DEFAULT_POINTS['multiple_choice']  # 1
        assert qs[1]['points'] == _DEFAULT_POINTS['essay']  # 4

    def test_zero_points_replaced(self):
        qs = [{'question_type': 'short_answer', 'points': 0}]
        a = self._make_assignment(qs)
        _normalize_points(a)
        assert qs[0]['points'] == _DEFAULT_POINTS['short_answer']

    def test_negative_points_replaced(self):
        qs = [{'question_type': 'short_answer', 'points': -5}]
        a = self._make_assignment(qs)
        _normalize_points(a)
        assert qs[0]['points'] == _DEFAULT_POINTS['short_answer']

    def test_string_points_replaced(self):
        qs = [{'question_type': 'short_answer', 'points': 'five'}]
        a = self._make_assignment(qs)
        _normalize_points(a)
        assert qs[0]['points'] == _DEFAULT_POINTS['short_answer']

    def test_section_points_recalculated(self):
        qs = [{'question_type': 'short_answer', 'points': 3},
              {'question_type': 'short_answer', 'points': 5}]
        a = self._make_assignment(qs)
        _normalize_points(a)
        assert a['sections'][0]['points'] == 8

    def test_total_points_recalculated(self):
        qs1 = [{'question_type': 'short_answer', 'points': 3}]
        qs2 = [{'question_type': 'short_answer', 'points': 7}]
        a = {'sections': [
            {'name': 'S1', 'questions': qs1},
            {'name': 'S2', 'questions': qs2},
        ]}
        _normalize_points(a)
        assert a['total_points'] == 10

    def test_target_total_scales_proportionally(self):
        qs = [{'question_type': 'short_answer', 'points': 5},
              {'question_type': 'short_answer', 'points': 5}]
        a = self._make_assignment(qs)
        _normalize_points(a, target_total=20)
        assert a['total_points'] == 20

    def test_scaling_preserves_minimum_1(self):
        qs = [{'question_type': 'multiple_choice', 'points': 1},
              {'question_type': 'essay', 'points': 99}]
        a = self._make_assignment(qs)
        _normalize_points(a, target_total=10)
        # The small question must be at least 1 point
        assert qs[0]['points'] >= 1

    def test_rounding_drift_absorbed_by_largest(self):
        # 3 questions at 3 points each = 9, scale to 10
        qs = [{'question_type': 'short_answer', 'points': 3},
              {'question_type': 'short_answer', 'points': 3},
              {'question_type': 'short_answer', 'points': 3}]
        a = self._make_assignment(qs)
        _normalize_points(a, target_total=10)
        assert a['total_points'] == 10

    def test_empty_sections_no_crash(self):
        a = {'sections': []}
        _normalize_points(a)
        # Should not raise; total_points may not be set with no sections
        assert a.get('total_points', 0) == 0 or 'total_points' not in a


# ── TestPostProcessAssignment ─────────────────────────────────────────────


class TestPostProcessAssignment:
    """Full pipeline e2e (mocking AI-dependent phases)."""

    @patch('backend.routes.planner_routes._validate_question_quality', return_value=[])
    @patch('backend.routes.planner_routes._auto_fix_flagged_questions')
    def test_mc_question_full_pipeline(self, mock_fix, mock_validate):
        assignment = {
            'sections': [{
                'name': 'Quiz',
                'questions': [{
                    'question': 'What is 2+2?',
                    'options': ['3', '4', '5'],
                    'answer': '4',
                }],
            }],
        }
        result, extra = _post_process_assignment(assignment)
        q = result['sections'][0]['questions'][0]
        assert q['question_type'] == 'multiple_choice'
        assert q['points'] == _DEFAULT_POINTS['multiple_choice']

    @patch('backend.routes.planner_routes._validate_question_quality', return_value=[])
    @patch('backend.routes.planner_routes._auto_fix_flagged_questions')
    def test_project_question_filtered_out(self, mock_fix, mock_validate):
        assignment = {
            'sections': [{
                'name': 'Activities',
                'questions': [
                    {'question': 'Create an infographic about volcanoes.'},
                    {'question': 'What causes volcanoes to erupt?'},
                ],
            }],
        }
        result, _ = _post_process_assignment(assignment)
        questions = result['sections'][0]['questions']
        assert len(questions) == 1
        assert 'infographic' not in questions[0]['question']

    @patch('backend.routes.planner_routes._validate_question_quality', return_value=[])
    @patch('backend.routes.planner_routes._auto_fix_flagged_questions')
    def test_empty_section_removed_after_filtering(self, mock_fix, mock_validate):
        assignment = {
            'sections': [
                {
                    'name': 'Projects',
                    'questions': [{'question': 'Create a poster about the water cycle.'}],
                },
                {
                    'name': 'Knowledge',
                    'questions': [{'question': 'Define evaporation.'}],
                },
            ],
        }
        result, _ = _post_process_assignment(assignment)
        assert len(result['sections']) == 1
        assert result['sections'][0]['name'] == 'Knowledge'

    def test_none_assignment_returns_as_is(self):
        result, extra = _post_process_assignment(None)
        assert result is None
        assert extra is None

    def test_non_dict_assignment_returns_as_is(self):
        result, extra = _post_process_assignment("not a dict")
        assert result == "not a dict"
        assert extra is None

    @patch('backend.routes.planner_routes._validate_question_quality', return_value=[])
    @patch('backend.routes.planner_routes._auto_fix_flagged_questions')
    def test_empty_assignment_no_sections(self, mock_fix, mock_validate):
        assignment = {'sections': []}
        result, _ = _post_process_assignment(assignment)
        assert result['sections'] == []

    @patch('backend.routes.planner_routes._validate_question_quality', return_value=[])
    @patch('backend.routes.planner_routes._auto_fix_flagged_questions')
    def test_multiple_sections_mixed_types(self, mock_fix, mock_validate):
        assignment = {
            'sections': [
                {
                    'name': 'MC',
                    'questions': [
                        {'question': 'Pick one.', 'options': ['A', 'B']},
                    ],
                },
                {
                    'name': 'Open',
                    'questions': [
                        {'question': 'Explain gravity.'},
                    ],
                },
            ],
        }
        result, _ = _post_process_assignment(assignment)
        assert len(result['sections']) == 2
        assert result['sections'][0]['questions'][0]['question_type'] == 'multiple_choice'
        assert result['sections'][1]['questions'][0]['question_type'] == 'short_answer'
        assert result.get('total_points', 0) > 0


# ── TestIsProjectQuestion ─────────────────────────────────────────────────


class TestIsProjectQuestion:
    """Phase 3b: Project/activity filter."""

    def test_create_infographic_is_project(self):
        q = {'question': 'Create an infographic about the solar system.'}
        assert _is_project_question(q) is True

    def test_using_google_slides_is_project(self):
        q = {'question': 'Using Google Slides, present your research findings.'}
        assert _is_project_question(q) is True

    def test_normal_question_is_not_project(self):
        q = {'question': 'What is the area of the triangle?'}
        assert _is_project_question(q) is False
