"""Tests for the Assessment Results route helper functions."""
import pytest

from backend.routes.assessment_results_routes import (
    _compute_letter_grade,
    _compute_question_analysis,
)


class TestComputeLetterGrade:
    def test_a_grade_at_95(self):
        assert _compute_letter_grade(95) == 'A'

    def test_a_grade_at_90(self):
        assert _compute_letter_grade(90) == 'A'

    def test_b_grade_at_85(self):
        assert _compute_letter_grade(85) == 'B'

    def test_b_grade_at_80(self):
        assert _compute_letter_grade(80) == 'B'

    def test_c_grade_at_75(self):
        assert _compute_letter_grade(75) == 'C'

    def test_c_grade_at_70(self):
        assert _compute_letter_grade(70) == 'C'

    def test_d_grade_at_65(self):
        assert _compute_letter_grade(65) == 'D'

    def test_d_grade_at_60(self):
        assert _compute_letter_grade(60) == 'D'

    def test_f_grade_at_55(self):
        assert _compute_letter_grade(55) == 'F'

    def test_f_grade_at_0(self):
        assert _compute_letter_grade(0) == 'F'

    def test_none_returns_none(self):
        assert _compute_letter_grade(None) is None

    def test_boundary_89_is_b(self):
        assert _compute_letter_grade(89) == 'B'

    def test_boundary_79_is_c(self):
        assert _compute_letter_grade(79) == 'C'

    def test_boundary_69_is_d(self):
        assert _compute_letter_grade(69) == 'D'

    def test_boundary_59_is_f(self):
        assert _compute_letter_grade(59) == 'F'


class TestComputeQuestionAnalysisMC:
    def _make_assessment(self, q_type='multiple_choice', answer='A', options=None):
        if options is None:
            options = ['Option A', 'Option B', 'Option C', 'Option D']
        return {
            'sections': [
                {
                    'questions': [
                        {
                            'number': 1,
                            'question': 'What is 2+2?',
                            'type': q_type,
                            'answer': answer,
                            'options': options,
                            'points': 1,
                        }
                    ]
                }
            ]
        }

    def test_mc_percent_correct_two_out_of_three(self):
        assessment = self._make_assessment(answer='A')
        subs = [
            {'answers': {'0-0': 'A'}},
            {'answers': {'0-0': 'A'}},
            {'answers': {'0-0': 'B'}},
        ]
        result = _compute_question_analysis(assessment, subs)
        assert len(result) == 1
        assert result[0]['percent_correct'] == 67

    def test_mc_response_distribution_counts(self):
        assessment = self._make_assessment(answer='B')
        subs = [
            {'answers': {'0-0': 'A'}},
            {'answers': {'0-0': 'B'}},
            {'answers': {'0-0': 'B'}},
            {'answers': {'0-0': 'C'}},
        ]
        result = _compute_question_analysis(assessment, subs)
        dist = result[0]['response_distribution']
        assert dist['A']['count'] == 1
        assert dist['B']['count'] == 2
        assert dist['C']['count'] == 1
        assert dist['D']['count'] == 0

    def test_mc_correct_answer_marked_in_distribution(self):
        assessment = self._make_assessment(answer='C')
        subs = [{'answers': {'0-0': 'C'}}]
        result = _compute_question_analysis(assessment, subs)
        dist = result[0]['response_distribution']
        assert dist['C']['is_correct'] is True
        assert dist['A']['is_correct'] is False

    def test_mc_distribution_percentages(self):
        assessment = self._make_assessment(answer='A')
        subs = [
            {'answers': {'0-0': 'A'}},
            {'answers': {'0-0': 'A'}},
            {'answers': {'0-0': 'B'}},
            {'answers': {'0-0': 'B'}},
        ]
        result = _compute_question_analysis(assessment, subs)
        dist = result[0]['response_distribution']
        assert dist['A']['percent'] == 50
        assert dist['B']['percent'] == 50

    def test_mc_integer_answer_index(self):
        """Submissions can use integer indices (0-based) instead of letters."""
        assessment = self._make_assessment(answer='A')
        subs = [
            {'answers': {'0-0': 0}},   # index 0 → 'A'
            {'answers': {'0-0': 1}},   # index 1 → 'B'
        ]
        result = _compute_question_analysis(assessment, subs)
        assert result[0]['percent_correct'] == 50

    def test_mc_empty_submissions(self):
        assessment = self._make_assessment(answer='A')
        result = _compute_question_analysis(assessment, [])
        assert result[0]['percent_correct'] == 0
        assert result[0]['total_responses'] == 0


class TestComputeQuestionAnalysisTF:
    def _make_tf_assessment(self, answer='True'):
        return {
            'sections': [
                {
                    'questions': [
                        {
                            'number': 1,
                            'question': 'The sky is blue.',
                            'type': 'true_false',
                            'answer': answer,
                            'points': 1,
                        }
                    ]
                }
            ]
        }

    def test_tf_true_false_distribution(self):
        assessment = self._make_tf_assessment(answer='True')
        subs = [
            {'answers': {'0-0': 'True'}},
            {'answers': {'0-0': 'True'}},
            {'answers': {'0-0': 'False'}},
        ]
        result = _compute_question_analysis(assessment, subs)
        dist = result[0]['response_distribution']
        assert dist['True']['count'] == 2
        assert dist['False']['count'] == 1

    def test_tf_correct_answer_marked(self):
        assessment = self._make_tf_assessment(answer='False')
        subs = [{'answers': {'0-0': 'False'}}]
        result = _compute_question_analysis(assessment, subs)
        dist = result[0]['response_distribution']
        assert dist['False']['is_correct'] is True
        assert dist['True']['is_correct'] is False

    def test_tf_percent_correct(self):
        assessment = self._make_tf_assessment(answer='True')
        subs = [
            {'answers': {'0-0': 'True'}},
            {'answers': {'0-0': 'False'}},
        ]
        result = _compute_question_analysis(assessment, subs)
        assert result[0]['percent_correct'] == 50

    def test_tf_empty_submissions(self):
        assessment = self._make_tf_assessment(answer='True')
        result = _compute_question_analysis(assessment, [])
        assert result[0]['percent_correct'] == 0
        assert result[0]['total_responses'] == 0


class TestComputeQuestionAnalysisShortAnswer:
    def _make_sa_assessment(self, q_type='short_answer'):
        return {
            'sections': [
                {
                    'questions': [
                        {
                            'number': 1,
                            'question': 'Explain photosynthesis.',
                            'type': q_type,
                            'points': 5,
                        }
                    ]
                }
            ]
        }

    def test_sa_graded_count(self):
        assessment = self._make_sa_assessment()
        subs = [
            {'answers': {}, 'results': {'questions': [{'number': 1, 'points_earned': 4}]}},
            {'answers': {}, 'results': {'questions': [{'number': 1, 'points_earned': 3}]}},
        ]
        result = _compute_question_analysis(assessment, subs)
        assert result[0]['graded_count'] == 2

    def test_sa_pending_count(self):
        assessment = self._make_sa_assessment()
        subs = [
            {'answers': {}, 'results': {'questions': [{'number': 1, 'points_earned': 4}]}},
            {'answers': {}, 'results': {'questions': [{'number': 1, 'points_earned': None}]}},
            {'answers': {}, 'results': {}},
        ]
        result = _compute_question_analysis(assessment, subs)
        assert result[0]['graded_count'] == 1
        assert result[0]['pending_count'] == 2

    def test_sa_average_score(self):
        assessment = self._make_sa_assessment()
        subs = [
            {'answers': {}, 'results': {'questions': [{'number': 1, 'points_earned': 4}]}},
            {'answers': {}, 'results': {'questions': [{'number': 1, 'points_earned': 2}]}},
        ]
        result = _compute_question_analysis(assessment, subs)
        assert result[0]['average_score'] == 3.0

    def test_sa_percent_correct_is_none(self):
        assessment = self._make_sa_assessment()
        subs = [
            {'answers': {}, 'results': {'questions': [{'number': 1, 'points_earned': 5}]}},
        ]
        result = _compute_question_analysis(assessment, subs)
        assert result[0]['percent_correct'] is None

    def test_sa_max_points(self):
        assessment = self._make_sa_assessment()
        result = _compute_question_analysis(assessment, [])
        assert result[0]['max_points'] == 5

    def test_sa_empty_submissions(self):
        assessment = self._make_sa_assessment()
        result = _compute_question_analysis(assessment, [])
        assert result[0]['graded_count'] == 0
        assert result[0]['pending_count'] == 0
        assert result[0]['average_score'] is None

    def test_extended_response_treated_same_as_short_answer(self):
        assessment = self._make_sa_assessment(q_type='extended_response')
        subs = [
            {'answers': {}, 'results': {'questions': [{'number': 1, 'points_earned': 3}]}},
        ]
        result = _compute_question_analysis(assessment, subs)
        assert result[0]['graded_count'] == 1
        assert result[0]['percent_correct'] is None


class TestComputeQuestionAnalysisEmpty:
    def test_empty_assessment_returns_empty_list(self):
        result = _compute_question_analysis({}, [])
        assert result == []

    def test_assessment_with_no_sections(self):
        result = _compute_question_analysis({'sections': []}, [])
        assert result == []

    def test_section_with_no_questions(self):
        assessment = {'sections': [{'questions': []}]}
        result = _compute_question_analysis(assessment, [])
        assert result == []

    def test_submissions_with_no_answers_field(self):
        assessment = {
            'sections': [
                {
                    'questions': [
                        {'number': 1, 'type': 'multiple_choice', 'answer': 'A', 'options': ['A', 'B'], 'points': 1}
                    ]
                }
            ]
        }
        # Submissions without 'answers' key — should not crash
        subs = [{'student_name': 'Alice'}, {'student_name': 'Bob'}]
        result = _compute_question_analysis(assessment, subs)
        assert result[0]['percent_correct'] == 0
        assert result[0]['total_responses'] == 0
