"""Shared types + token/cost state for the grading engine: the Pydantic response schemas
(OpenAI structured-output `response_format` targets) and the per-student TokenTracker +
MODEL_PRICING table. Flask-free, no LLM calls — pure data/accounting. Extracted from
assignment_grader.py. Wave 7 Phase B (grading-engine decomposition). These move FIRST so the
LLM-coupled functions (grade_per_question, generate_feedback, grade_assignment, ...) can import
their schemas + tracker from a service rather than from assignment_grader.
"""
import threading
from typing import List

from pydantic import BaseModel


# ── Structured-output response schemas (OpenAI `response_format` targets) ──────

class GradingBreakdown(BaseModel):
    content_accuracy: int
    completeness: int
    writing_quality: int
    effort_engagement: int


class SkillsDemonstrated(BaseModel):
    strengths: List[str]
    developing: List[str]


class AiDetectionResult(BaseModel):
    flag: str  # "none", "unlikely", "possible", "likely"
    confidence: int
    reason: str


class PlagiarismDetectionResult(BaseModel):
    flag: str  # "none", "possible", "likely"
    reason: str


class GradingResponse(BaseModel):
    score: int
    letter_grade: str
    breakdown: GradingBreakdown
    student_responses: List[str]
    unanswered_questions: List[str]
    excellent_answers: List[str]
    needs_improvement: List[str]
    skills_demonstrated: SkillsDemonstrated
    ai_detection: AiDetectionResult
    plagiarism_detection: PlagiarismDetectionResult
    feedback: str


class DetectionResponse(BaseModel):
    ai_detection: AiDetectionResult
    plagiarism_detection: PlagiarismDetectionResult


class QuestionGrade(BaseModel):
    score: int
    possible: int
    reasoning: str
    is_correct: bool
    quality: str  # "excellent", "good", "adequate", "developing", "insufficient"


class PerQuestionResponse(BaseModel):
    grade: QuestionGrade
    excellent: bool
    improvement_note: str


class FeedbackResponse(BaseModel):
    feedback: str
    excellent_answers: List[str]
    needs_improvement: List[str]
    skills_demonstrated: SkillsDemonstrated


# Assignment name (used in output files and emails)
ASSIGNMENT_NAME = ""  # Set dynamically from assignment config; empty = use filename


# =============================================================================
# TOKEN / COST TRACKING
# =============================================================================

MODEL_PRICING = {
    # OpenAI — price per 1M tokens
    "gpt-4o-mini":    {"input": 0.15,  "output": 0.60},
    "gpt-4o":         {"input": 2.50,  "output": 10.00},
    # Claude
    "claude-3-5-haiku-latest":    {"input": 0.80,  "output": 4.00},
    "claude-haiku-4-5-20251001":  {"input": 0.80,  "output": 4.00},
    "claude-sonnet-4-20250514":   {"input": 3.00,  "output": 15.00},
    "claude-opus-4-20250514":     {"input": 15.00, "output": 75.00},
    # Gemini
    "gemini-2.0-flash":    {"input": 0.10,  "output": 0.40},
    "gemini-2.0-pro-exp":  {"input": 1.25,  "output": 5.00},
}

class TokenTracker:
    """Accumulates token usage across multiple API calls for a single student grading."""

    def __init__(self):
        self._lock = threading.Lock()
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.calls = []

    def record_openai(self, response, model: str):
        if not response or not hasattr(response, 'usage') or not response.usage:
            return
        inp = response.usage.prompt_tokens or 0
        out = response.usage.completion_tokens or 0
        self._add(model, inp, out)

    def record_anthropic(self, response, model: str):
        if not response or not hasattr(response, 'usage') or not response.usage:
            return
        inp = response.usage.input_tokens or 0
        out = response.usage.output_tokens or 0
        self._add(model, inp, out)

    def record_gemini(self, response, model: str):
        if not response or not hasattr(response, 'usage_metadata') or not response.usage_metadata:
            return
        inp = getattr(response.usage_metadata, 'prompt_token_count', 0) or 0
        out = getattr(response.usage_metadata, 'candidates_token_count', 0) or 0
        self._add(model, inp, out)

    def _add(self, model: str, input_tokens: int, output_tokens: int):
        pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
        with self._lock:
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.calls.append({
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": round(cost, 6)
            })

    def summary(self) -> dict:
        total_cost = sum(c["cost"] for c in self.calls)
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost": round(total_cost, 6),
            "total_cost_display": f"${total_cost:.4f}",
            "api_calls": len(self.calls),
            "calls": self.calls
        }
