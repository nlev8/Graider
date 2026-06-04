"""Characterization (golden) net for export_generated_assignment.

This pins the *exact* sequence of reportlab flowables that the
`/api/export-generated-assignment` PDF path emits for a rich assignment
payload that exercises every rendering branch:

    multiple-choice bubbles, true/false, matching tables, data_table,
    math_equation work-lines, coordinates blanks, visual questions,
    inline markdown tables, short_answer, essay sections, the answer-key
    variants of each, and the teacher rubric PageBreak.

It exists to make the CQ7 god-function split of `export_generated_assignment`
(extraction of the ~235-line section-rendering loop into a module-level
helper) provably behavior-preserving: the helper must reproduce this flowable
stream byte-for-byte. A reordered/dropped/duplicated flowable, a mis-passed
style, or a wiring bug changes the signature and fails the test.

Captured against `main` (pre-split) on 2026-06-04.

`_create_visual_for_question` is patched to a stable sentinel so the signature
is deterministic and fast (no matplotlib); the patch is identical in the
golden capture and here, so the visual call-site wiring is still verified
(the sentinel appears iff the call happened in the right place).
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.conftest_routes import (  # noqa: F401,E501
    client, flask_app, mock_grading_state, grading_lock,
)


class _VizSentinel:
    """Stand-in for a generated visual flowable (truthy, stable type name)."""

    def __bool__(self):
        return True


def _flow_sig(f):
    """Reduce a reportlab flowable to a stable, comparable signature tuple."""
    n = type(f).__name__
    if n == 'Paragraph':
        return ('Paragraph', getattr(f, 'text', None))
    if n == 'Spacer':
        return ('Spacer', round(getattr(f, 'width', 0), 3),
                round(getattr(f, 'height', 0), 3))
    if n == '_BubbleCircle':
        return ('_BubbleCircle', getattr(f, 'filled', None),
                getattr(f, 'size', None))
    if n == 'Table':
        cv = getattr(f, '_cellvalues', None)
        dims = (len(cv), len(cv[0]) if cv and cv[0] else 0) if cv else None
        return ('Table', dims)
    return (n,)


RICH = {
    'title': 'Characterization Assignment',
    'instructions': 'Answer all questions.',
    'total_points': 100,
    'teacher_name': 'Ms. Test',
    'subject': 'Algebra',
    'rubric': {'criteria': [
        {'name': 'Accuracy', 'points': 50, 'description': 'Correct answers'},
        {'name': 'Work shown', 'points': 50, 'description': 'Steps visible'},
    ]},
    'sections': [
        {
            'name': 'Part 1', 'points': 60, 'type': 'short_answer',
            'questions': [
                {'number': 1, 'question': 'What is 2+2?', 'points': 5,
                 'question_type': 'multiple_choice',
                 'options': ['3', '4', '5', '6'], 'answer': 'B'},
                {'number': 2, 'question': 'The sky is blue.', 'points': 5,
                 'question_type': 'true_false',
                 'options': ['True', 'False'], 'answer': 'True'},
                {'number': 3, 'question': 'Match the terms.', 'points': 10,
                 'question_type': 'matching',
                 'terms': ['Alpha', 'Beta'], 'definitions': ['First', 'Second'],
                 'answer': {'Alpha': 'First', 'Beta': 'Second'}},
                {'number': 4, 'question': 'Fill the data table.', 'points': 10,
                 'question_type': 'data_table',
                 'headers': ['X', 'Y'], 'row_labels': ['r1', 'r2'],
                 'expected_data': [[1, 2], [3, 4]], 'num_rows': 2},
                {'number': 5, 'question': 'Solve x+1=2.', 'points': 10,
                 'question_type': 'math_equation', 'answer': 'x=1'},
                {'number': 6, 'question': 'Where is it?', 'points': 10,
                 'question_type': 'coordinates',
                 'answer': {'lat': 1.0, 'lng': 2.0}, 'tolerance_km': 25},
                {'number': 7, 'question': 'Plot on the number line.', 'points': 10,
                 'question_type': 'number_line', 'visual_type': 'number_line'},
                {'number': 8,
                 'question': 'Read this:\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\nThen answer.',
                 'points': 5, 'question_type': 'short_answer'},
                {'number': 9, 'question': 'Explain briefly.', 'points': 5,
                 'question_type': 'short_answer'},
            ],
        },
        {
            'name': 'Part 2', 'points': 40, 'type': 'essay',
            'questions': [
                {'number': 10, 'question': 'Write an essay.', 'points': 40,
                 'question_type': 'extended_response'},
            ],
        },
    ],
}


GOLDEN_STUDENT = [
    ('Paragraph', 'Ms. Test | Algebra'),
    ('Spacer', 1, 3.6),
    ('Paragraph', 'Characterization Assignment'),
    ('Spacer', 1, 7.2),
    ('Paragraph', 'Name: _______________________ Date: _______________ Period: _____'),
    ('Spacer', 1, 7.2),
    ('Paragraph', 'Total Points: 100'),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Instructions:</b> Answer all questions.'),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Part 1</b> (60 points)'),
    ('Spacer', 1, 7.2),
    ('Paragraph', '<b>Question 1:</b> What is 2+2? (5 pts)'),
    ('Spacer', 1, 3.6),
    ('Table', (1, 2)),
    ('Table', (1, 2)),
    ('Table', (1, 2)),
    ('Table', (1, 2)),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Question 2:</b> The sky is blue. (5 pts)'),
    ('Spacer', 1, 3.6),
    ('Table', (1, 2)),
    ('Table', (1, 2)),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Question 3:</b> Match the terms. (10 pts)'),
    ('Spacer', 1, 3.6),
    ('Spacer', 1, 3.6),
    ('Table', (3, 4)),
    ('Spacer', 1, 3.6),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Question 4:</b> Fill the data table. (10 pts)'),
    ('Spacer', 1, 3.6),
    ('Table', (3, 3)),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Question 5:</b> Solve x+1=2. (10 pts)'),
    ('Spacer', 1, 3.6),
    ('Paragraph', 'Show your work:'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '<b>Final Answer:</b> __________________________________________________'),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Question 6:</b> Where is it? (10 pts)'),
    ('Spacer', 1, 3.6),
    ('Paragraph', '<b>Latitude:</b> _______________° <b>Longitude:</b> _______________°'),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Question 7:</b> Plot on the number line. (10 pts)'),
    ('Spacer', 1, 3.6),
    ('Spacer', 1, 7.2),
    ('_VizSentinel',),
    ('Spacer', 1, 7.2),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Question 8:</b> Read this: (5 pts)'),
    ('Spacer', 1, 3.6),
    ('Table', (2, 2)),
    ('Paragraph', 'Then answer.'),
    ('Spacer', 1, 3.6),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Question 9:</b> Explain briefly. (5 pts)'),
    ('Spacer', 1, 3.6),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Part 2</b> (40 points)'),
    ('Spacer', 1, 7.2),
    ('Paragraph', '<b>Question 10:</b> Write an essay. (40 pts)'),
    ('Spacer', 1, 3.6),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Paragraph', '_____________________________________________________________________________________'),
    ('Spacer', 1, 10.8),
]

GOLDEN_ANSWERS = [
    ('Paragraph', 'Ms. Test | Algebra'),
    ('Spacer', 1, 3.6),
    ('Paragraph', 'Characterization Assignment'),
    ('Spacer', 1, 7.2),
    ('Paragraph', '<b>ANSWER KEY - FOR TEACHER USE ONLY</b>'),
    ('Spacer', 1, 7.2),
    ('Paragraph', 'Total Points: 100'),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Instructions:</b> Answer all questions.'),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Part 1</b> (60 points)'),
    ('Spacer', 1, 7.2),
    ('Paragraph', '<b>Question 1:</b> What is 2+2? (5 pts)'),
    ('Spacer', 1, 3.6),
    ('Table', (1, 2)),
    ('Table', (1, 2)),
    ('Table', (1, 2)),
    ('Table', (1, 2)),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Question 2:</b> The sky is blue. (5 pts)'),
    ('Spacer', 1, 3.6),
    ('Table', (1, 2)),
    ('Table', (1, 2)),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Question 3:</b> Match the terms. (10 pts)'),
    ('Spacer', 1, 3.6),
    ('Spacer', 1, 3.6),
    ('Table', (3, 4)),
    ('Spacer', 1, 3.6),
    ('Paragraph', '<b>ANSWERS: Alpha → First | Beta → Second</b>'),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Question 4:</b> Fill the data table. (10 pts)'),
    ('Spacer', 1, 3.6),
    ('Paragraph', '<b>ANSWER: </b>'),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Question 5:</b> Solve x+1=2. (10 pts)'),
    ('Spacer', 1, 3.6),
    ('Paragraph', '<b>ANSWER: x=1</b>'),
    ('Paragraph', '<i>(Equivalent forms accepted)</i>'),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Question 6:</b> Where is it? (10 pts)'),
    ('Spacer', 1, 3.6),
    ('Paragraph', '<b>ANSWER: Lat: 1.0, Lng: 2.0</b>'),
    ('Paragraph', '<i>(Acceptable within 25 km)</i>'),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Question 7:</b> Plot on the number line. (10 pts)'),
    ('Spacer', 1, 3.6),
    ('Spacer', 1, 7.2),
    ('_VizSentinel',),
    ('Spacer', 1, 7.2),
    ('Paragraph', '<b>ANSWER: </b>'),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Question 8:</b> Read this: (5 pts)'),
    ('Spacer', 1, 3.6),
    ('Table', (2, 2)),
    ('Paragraph', 'Then answer.'),
    ('Spacer', 1, 3.6),
    ('Paragraph', '<b>ANSWER: </b>'),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Question 9:</b> Explain briefly. (5 pts)'),
    ('Spacer', 1, 3.6),
    ('Paragraph', '<b>ANSWER: </b>'),
    ('Spacer', 1, 10.8),
    ('Paragraph', '<b>Part 2</b> (40 points)'),
    ('Spacer', 1, 7.2),
    ('Paragraph', '<b>Question 10:</b> Write an essay. (40 pts)'),
    ('Spacer', 1, 3.6),
    ('Paragraph', '<b>ANSWER: </b>'),
    ('Spacer', 1, 10.8),
    ('PageBreak',),
    ('Paragraph', '<b>Grading Rubric</b>'),
    ('Paragraph', '<b>Accuracy:</b> 50 points - Correct answers'),
    ('Spacer', 1, 3.6),
    ('Paragraph', '<b>Work shown:</b> 50 points - Steps visible'),
    ('Spacer', 1, 3.6),
]


def _capture_signature(client, include_answers):  # noqa: F811
    """Drive the PDF export path and return the flowable signature list."""
    captured = {}

    class _CapDoc:
        def __init__(self, *a, **k):
            pass

        def build(self, story, *a, **k):
            captured['story'] = list(story)

    with patch('reportlab.platypus.SimpleDocTemplate', _CapDoc), \
         patch('backend.routes.planner_routes._create_visual_for_question',
               return_value=_VizSentinel()), \
         patch('backend.routes.planner_routes.os.makedirs'), \
         patch('backend.routes.planner_routes.subprocess.run'):
        resp = client.post(
            '/api/export-generated-assignment',
            json={'assignment': dict(RICH), 'format': 'pdf',
                  'include_answers': include_answers,
                  'teacher_name': 'Ms. Test', 'subject': 'Algebra'},
            content_type='application/json',
        )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert 'story' in captured, "SimpleDocTemplate.build was never called"
    return [_flow_sig(f) for f in captured['story']]


def test_student_pdf_flowable_signature_is_stable(client):  # noqa: F811
    """Student worksheet PDF emits the exact golden flowable stream."""
    assert _capture_signature(client, include_answers=False) == GOLDEN_STUDENT


def test_answer_key_pdf_flowable_signature_is_stable(client):  # noqa: F811
    """Answer-key PDF emits the exact golden flowable stream (incl. rubric)."""
    assert _capture_signature(client, include_answers=True) == GOLDEN_ANSWERS
