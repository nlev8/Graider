"""Direct-import tests for backend/services/planner_assessments.py (Wave 6 Slice 5).

The deterministic grading paths are characterized by tests/test_grade_assessment_answers.py
(endpoint). This pins the open-ended AI-grading path directly with a mocked adapter,
and the Flask-free contract of grade_assessment_answers_logic.
"""
from unittest.mock import patch, MagicMock


def test_deterministic_mc_grading_no_ai():
    from backend.services.planner_assessments import grade_assessment_answers_logic
    assessment = {"sections": [{"questions": [
        {"number": 1, "type": "multiple_choice", "options": ["3", "4"], "answer": "B", "points": 5},
    ]}]}
    out = grade_assessment_answers_logic(assessment, {"0-0": "B"})
    assert out["results"]["score"] == 5
    assert out["results"]["percentage"] == 100
    assert out["usage"] is None  # no AI ran


def test_open_ended_uses_ai_score():
    from backend.services.planner_assessments import grade_assessment_answers_logic
    assessment = {"sections": [{"questions": [
        {"number": 1, "type": "short_answer", "question": "Why?", "answer": "because", "points": 10},
    ]}]}
    fake_completion = MagicMock()
    fake_completion.content_parts = [MagicMock(text='{"points_earned": 8, "feedback": "Solid reasoning.", "is_correct": true}')]
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = fake_completion

    with patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter), \
         patch('backend.services.planner_assessments._extract_usage',
               return_value={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30, "cost": 0.001}), \
         patch('backend.services.planner_assessments._record_planner_cost'):
        out = grade_assessment_answers_logic(assessment, {"0-0": "My answer is because of X."})

    q = out["results"]["questions"][0]
    assert q["points_earned"] == 8  # AI score applied (capped at points)
    assert q["feedback"] == "Solid reasoning."
    assert q["is_correct"] is True
    assert out["usage"]["total_tokens"] == 30


def test_open_ended_ai_failure_falls_back_to_manual_review():
    from backend.services.planner_assessments import grade_assessment_answers_logic
    assessment = {"sections": [{"questions": [
        {"number": 1, "type": "extended_response", "question": "Explain.", "answer": "x", "points": 10},
    ]}]}
    fake_adapter = MagicMock()
    fake_adapter.chat.side_effect = RuntimeError("LLM down")

    with patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        out = grade_assessment_answers_logic(assessment, {"0-0": "an answer"})

    q = out["results"]["questions"][0]
    assert q["points_earned"] == 0
    assert "Manual review" in q["feedback"]  # graceful fallback preserved


def test_matching_partial_credit():
    from backend.services.planner_assessments import grade_assessment_answers_logic
    # 4 terms, student gets 2 right -> round(10 * 2/4) = 5 points
    assessment = {"sections": [{"questions": [
        {"number": 1, "type": "matching", "points": 10,
         "terms": ["t0", "t1", "t2", "t3"],
         "definitions": ["d0", "d1", "d2", "d3"],
         "answer": {"t0": "d0", "t1": "d1", "t2": "d2", "t3": "d3"}},
    ]}]}
    # "0-0" must be non-empty so the question is not skipped by the no-answer guard;
    # the per-term "0-0-match-<tIdx>" keys drive partial credit (t0=A, t1=B correct).
    answers = {"0-0": "matching", "0-0-match-0": "A", "0-0-match-1": "B",
               "0-0-match-2": "Z", "0-0-match-3": "Z"}
    out = grade_assessment_answers_logic(assessment, answers)
    q = out["results"]["questions"][0]
    assert q["points_earned"] == 5          # round(10 * 2/4)
    assert q["is_correct"] is False          # not all 4 matched
