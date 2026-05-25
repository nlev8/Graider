"""Golden characterization net for the LLM-coupled grading core (Wave 7 Phase B).

These tests pin the EXACT output of the grading scoring core against deterministic provider-SDK
fakes (tests/grading_fakes.py), BEFORE that core is extracted from assignment_grader.py into
backend/services/. They run the REAL functions (real extraction, real with_retry, real parse +
_try_parse_json_fallback, real aggregation/caps/rounding) — only the 3 raw SDK entrypoints are
faked. A regression anywhere in the scoring pipeline during extraction will flip a pinned value.

Design + rationale: docs/superpowers/specs/2026-05-24-wave7-phaseb-grader-golden-net.md
(3-model reconciled consensus). The fakes' scores are arbitrary-but-deterministic; what matters
is that the pinned values stay STABLE through the behavior-preserving extraction.

Imported via `assignment_grader` so the tests stay valid through the re-export shims.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tests/ for grading_fakes

import assignment_grader as g  # noqa: E402
from grading_fakes import GEMINI_SDK_AVAILABLE, patched_llm  # noqa: E402

_FIX = os.path.join(os.path.dirname(__file__), 'fixtures', 'grading')


def _fixture(name):
    with open(os.path.join(_FIX, name)) as f:
        return f.read()


@pytest.fixture(scope="module")
def social_studies():
    return _fixture("submission_social_studies.txt")


@pytest.fixture(scope="module")
def ss_config():
    with open(os.path.join(_FIX, "config_social_studies.json")) as f:
        return json.load(f)


# ── grade_multipass (end-to-end orchestrator) ─────────────────────────────────

def test_multipass_social_studies_golden(social_studies, ss_config):
    with patched_llm() as book:
        r = g.grade_multipass(
            student_name="Maria Garcia",
            assignment_data={"type": "text", "content": social_studies},
            custom_ai_instructions=ss_config["gradingNotes"],
            grade_level="6", subject="Social Studies", ai_model="gpt-4o-mini",
            marker_config=ss_config["customMarkers"], effort_points=15, grading_style="standard",
        )

    assert r["score"] == 88
    assert r["letter_grade"] == "B"
    assert r["breakdown"] == {
        "content_accuracy": 34, "completeness": 25, "writing_quality": 18, "effort_engagement": 15,
    }
    assert r["multipass_grading"] is True
    # 10 content-matched per-question grades (distinct scores) + summary worth 18/20
    assert [q["score"] for q in r["per_question_scores"]] == [6, 7, 8, 6, 6, 6, 8, 6, 8, 18]
    assert r["feedback"].startswith("FAKE_FEEDBACK:")
    # Token tracking: 10 per-question (gpt-4o-mini) + 1 feedback (gpt-4o upgrade)
    assert r["token_usage"]["api_calls"] == 11
    assert r["token_usage"]["total_input_tokens"] == 1320
    assert r["token_usage"]["total_output_tokens"] == 660
    # Call shape: 10 PerQuestion parses + 1 Feedback parse, all OpenAI
    assert book.count(provider="openai", method="parse", schema="PerQuestionResponse") == 10
    assert book.count(provider="openai", method="parse", schema="FeedbackResponse") == 1
    assert book.total == 11
    # Feedback model upgrade landmine: feedback call uses gpt-4o even though grading used -mini
    fb_calls = [c for c in book.calls if c["schema"] == "FeedbackResponse"]
    assert fb_calls and all(c["model"] == "gpt-4o" for c in fb_calls)
    pq_calls = [c for c in book.calls if c["schema"] == "PerQuestionResponse"]
    assert all(c["model"] == "gpt-4o-mini" for c in pq_calls)


def test_multipass_blank_short_circuits_before_any_llm_call(ss_config):
    blank = _fixture("submission_blank.txt")
    with patched_llm() as book:
        r = g.grade_multipass(
            student_name="Blank",
            assignment_data={"type": "text", "content": blank},
            custom_ai_instructions="", grade_level="6", subject="Social Studies",
            ai_model="gpt-4o-mini", marker_config=ss_config["customMarkers"], effort_points=15,
        )
    assert r["score"] == 0
    assert r["letter_grade"] == "INCOMPLETE"
    assert "nearly blank" in r["feedback"].lower()
    # Landmine: blank/near-blank short-circuits BEFORE constructing any client
    assert book.total == 0


# ── grade_with_parallel_detection (detection + grading in parallel threads) ───

def test_parallel_detection_golden(social_studies, ss_config):
    with patched_llm() as book:
        r = g.grade_with_parallel_detection(
            student_name="Maria Garcia",
            assignment_data={"type": "text", "content": social_studies},
            custom_ai_instructions=ss_config["gradingNotes"],
            grade_level="6", subject="Social Studies", ai_model="gpt-4o-mini",
            marker_config=ss_config["customMarkers"], effort_points=15, grading_style="standard",
        )
    assert r["score"] == 88
    assert r["letter_grade"] == "B"
    assert r["breakdown"] == {
        "content_accuracy": 34, "completeness": 25, "writing_quality": 18, "effort_engagement": 15,
    }
    assert r["ai_detection"] == {"flag": "none", "confidence": 0, "reason": ""}
    # 1 detection + 10 per-question + 1 feedback, recorded thread-safely across parallel threads
    assert book.count(schema="DetectionResponse") == 1
    assert book.count(schema="PerQuestionResponse") == 10
    assert book.count(schema="FeedbackResponse") == 1
    assert book.total == 12


# ── grade_assignment (single-pass alternative) ────────────────────────────────

def test_grade_assignment_openai_golden(social_studies, ss_config):
    with patched_llm() as book:
        r = g.grade_assignment(
            student_name="Maria Garcia",
            assignment_data={"type": "text", "content": social_studies},
            custom_ai_instructions=ss_config["gradingNotes"],
            grade_level="6", subject="Social Studies", ai_model="gpt-4o-mini",
            marker_config=ss_config["customMarkers"], effort_points=15, grading_style="standard",
        )
    assert r["score"] == 85
    assert r["letter_grade"] == "B"
    assert r["breakdown"] == {
        "content_accuracy": 34, "completeness": 22, "writing_quality": 17, "effort_engagement": 12,
    }
    assert r["feedback"].startswith("FAKE_FEEDBACK:")
    assert r["ai_detection"] == {"flag": "none", "confidence": 0, "reason": ""}
    assert r["plagiarism_detection"] == {"flag": "none", "reason": ""}
    assert book.count(provider="openai", method="parse", schema="GradingResponse") == 1
    assert book.total == 1


def test_grade_assignment_recovers_via_text_when_parsed_is_none(social_studies, ss_config):
    # Landmine: grade_assignment falls back to .content text parse when .parsed is None
    # (it RECOVERS — unlike grade_per_question which falls through to an error score).
    with patched_llm(force_text=True):
        r = g.grade_assignment(
            student_name="Maria Garcia", assignment_data={"type": "text", "content": social_studies},
            custom_ai_instructions=ss_config["gradingNotes"], grade_level="6",
            subject="Social Studies", ai_model="gpt-4o-mini",
            marker_config=ss_config["customMarkers"], effort_points=15,
        )
    assert r["score"] == 85
    assert r["letter_grade"] == "B"


# ── detect_ai_plagiarism ──────────────────────────────────────────────────────

def test_detect_ai_plagiarism_real_content():
    with patched_llm() as book:
        d = g.detect_ai_plagiarism(
            "The student wrote a thoughtful paragraph about the Louisiana Purchase and its "
            "effects on the country over many years.",
            grade_level="6",
        )
    assert d == {
        "ai_detection": {"flag": "none", "confidence": 0, "reason": ""},
        "plagiarism_detection": {"flag": "none", "reason": ""},
    }
    assert book.count(schema="DetectionResponse") == 1
    assert book.total == 1


def test_detect_ai_plagiarism_short_circuit_no_llm():
    # Landmine: <50 chars is exempt (no LLM call)
    with patched_llm() as book:
        d = g.detect_ai_plagiarism("idk", grade_level="6")
    assert d["ai_detection"]["flag"] == "none"
    assert "exempt from AI detection" in d["ai_detection"]["reason"]
    assert "exempt from plagiarism detection" in d["plagiarism_detection"]["reason"]
    assert book.total == 0


# ── grade_per_question (provider routing + .parsed-None landmine) ──────────────

def _gpq(provider, ai_model):
    with patched_llm() as book:
        r = g.grade_per_question(
            question="2) Why did Napoleon sell?", student_answer="He needed money for wars.",
            expected_answer="", points=10, grade_level="6", subject="Social Studies",
            teacher_instructions="", grading_style="standard",
            ai_model=ai_model, ai_provider=provider,
        )
    return r, book


def test_grade_per_question_openai():
    r, book = _gpq("openai", "gpt-4o-mini")
    assert r["grade"]["score"] == 10
    assert r["grade"]["quality"] == "excellent"
    assert r["excellent"] is True
    assert book.count(provider="openai", method="parse", schema="PerQuestionResponse") == 1


def test_grade_per_question_anthropic_routing():
    r, book = _gpq("anthropic", "claude-haiku")
    assert r["grade"]["score"] == 10
    assert r["grade"]["quality"] == "excellent"
    assert book.count(provider="anthropic") == 1


@pytest.mark.skipif(not GEMINI_SDK_AVAILABLE, reason="google.generativeai not installed in this env")
def test_grade_per_question_gemini_routing():
    r, book = _gpq("gemini", "gemini-flash")
    assert r["grade"]["score"] == 10
    assert book.count(provider="gemini") == 1


def test_grade_per_question_falls_through_to_error_when_parsed_none():
    # Landmine: grade_per_question does NOT recover from .parsed None — it returns the
    # error fallback (score 0), unlike grade_assignment.
    with patched_llm(force_text=True):
        r = g.grade_per_question(
            question="2) Why did Napoleon sell?", student_answer="He needed money.",
            expected_answer="", points=10, grade_level="6", subject="Social Studies",
            teacher_instructions="", grading_style="standard",
            ai_model="gpt-4o-mini", ai_provider="openai",
        )
    assert r["grade"]["score"] == 0
    assert "Grading error" in r["grade"]["reasoning"]
    assert r["excellent"] is False


# ── generate_feedback + _translate_feedback ───────────────────────────────────

def test_generate_feedback_openai():
    qr = [{"grade": {"score": 8, "possible": 10, "reasoning": "good", "quality": "good"},
           "excellent": False, "improvement_note": ""}]
    with patched_llm() as book:
        r = g.generate_feedback(
            question_results=qr, total_score=80, total_possible=100, letter_grade="B",
            grade_level="6", subject="Social Studies", ai_model="gpt-4o", ai_provider="openai",
        )
    assert set(r.keys()) == {"feedback", "excellent_answers", "needs_improvement", "skills_demonstrated"}
    assert r["feedback"].startswith("FAKE_FEEDBACK:")
    assert r["skills_demonstrated"] == {"strengths": ["factual recall"], "developing": ["analysis"]}
    assert book.count(provider="openai", method="parse", schema="FeedbackResponse") == 1


def test_translate_feedback_openai():
    with patched_llm() as book:
        t = g._translate_feedback("Great job on your essay!", "Spanish", ai_model="gpt-4o-mini")
    assert t == "FAKE_TRANSLATION: traducción simulada."
    assert book.count(provider="openai", method="create") == 1


# ── grade_assignment provider routing (Wave 8 — harden before provider-resolution extraction) ──
# The default grade_assignment golden above exercises only the OpenAI branch. These cover the
# anthropic/gemini provider branches + their text-parse paths, so the upcoming
# _resolve_grading_client extraction (which unifies claude_client/gemini_client/openai_client →
# one `client` at the call sites) is guarded for ALL providers, not just OpenAI.

def test_grade_assignment_anthropic_branch_golden(social_studies, ss_config):
    with patched_llm() as book:
        r = g.grade_assignment(
            student_name="Maria Garcia", assignment_data={"type": "text", "content": social_studies},
            custom_ai_instructions=ss_config["gradingNotes"], grade_level="6",
            subject="Social Studies", ai_model="claude-haiku",
            marker_config=ss_config["customMarkers"], effort_points=15, grading_style="standard",
        )
    assert r["score"] == 85
    assert r["letter_grade"] == "B"
    assert r["breakdown"] == {
        "content_accuracy": 34, "completeness": 22, "writing_quality": 17, "effort_engagement": 12,
    }
    assert r["feedback"].startswith("FAKE_FEEDBACK:")
    assert book.count(provider="anthropic") == 1
    assert book.count(provider="openai") == 0  # routed to anthropic, not openai


@pytest.mark.skipif(not GEMINI_SDK_AVAILABLE, reason="google.generativeai not installed in this env")
def test_grade_assignment_gemini_branch_golden(social_studies, ss_config):
    with patched_llm() as book:
        r = g.grade_assignment(
            student_name="Maria Garcia", assignment_data={"type": "text", "content": social_studies},
            custom_ai_instructions=ss_config["gradingNotes"], grade_level="6",
            subject="Social Studies", ai_model="gemini-flash",
            marker_config=ss_config["customMarkers"], effort_points=15, grading_style="standard",
        )
    assert r["score"] == 85
    assert r["letter_grade"] == "B"
    assert book.count(provider="gemini") == 1
    assert book.count(provider="openai") == 0
