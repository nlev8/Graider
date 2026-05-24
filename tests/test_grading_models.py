"""Characterization tests for the shared grading types/state (Wave 7 Phase B).

Pins the Pydantic response schemas + TokenTracker + MODEL_PRICING BEFORE moving them into
backend/services/grading_models.py. These are pure data/accounting (no LLM, no I/O). The
end-to-end golden net (test_grader_golden.py) already exercises them through the real grading
functions; this file adds direct shape/identity/behavior pins. Imported via `assignment_grader`
(re-export shims) so it stays valid through the extraction.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import assignment_grader as g


def test_response_models_construct_and_dump():
    pq = g.PerQuestionResponse(
        grade=g.QuestionGrade(score=8, possible=10, reasoning="ok", is_correct=True, quality="good"),
        excellent=False, improvement_note="add detail",
    )
    assert pq.model_dump() == {
        "grade": {"score": 8, "possible": 10, "reasoning": "ok", "is_correct": True, "quality": "good"},
        "excellent": False, "improvement_note": "add detail",
    }

    det = g.DetectionResponse(
        ai_detection=g.AiDetectionResult(flag="none", confidence=0, reason=""),
        plagiarism_detection=g.PlagiarismDetectionResult(flag="none", reason=""),
    )
    assert det.model_dump()["ai_detection"]["flag"] == "none"

    fb = g.FeedbackResponse(
        feedback="good", excellent_answers=["a"], needs_improvement=["b"],
        skills_demonstrated=g.SkillsDemonstrated(strengths=["x"], developing=["y"]),
    )
    assert fb.model_dump()["skills_demonstrated"] == {"strengths": ["x"], "developing": ["y"]}


def test_token_tracker_openai_accumulation_and_cost():
    from types import SimpleNamespace
    t = g.TokenTracker()
    resp = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50))
    t.record_openai(resp, "gpt-4o-mini")
    t.record_openai(resp, "gpt-4o")
    s = t.summary()
    assert s["total_input_tokens"] == 200
    assert s["total_output_tokens"] == 100
    assert s["api_calls"] == 2
    # gpt-4o-mini: (100*0.15 + 50*0.60)/1e6 = 4.5e-05 ; gpt-4o: (100*2.5 + 50*10)/1e6 = 7.5e-04
    assert s["total_cost"] == round(4.5e-05 + 7.5e-04, 6)


def test_token_tracker_ignores_missing_usage():
    t = g.TokenTracker()
    t.record_openai(None, "gpt-4o-mini")
    t.record_anthropic(object(), "claude-haiku")  # no .usage attr
    assert t.summary()["api_calls"] == 0


def test_model_pricing_table_present():
    assert g.MODEL_PRICING["gpt-4o-mini"] == {"input": 0.15, "output": 0.60}
    assert "gemini-2.0-flash" in g.MODEL_PRICING
