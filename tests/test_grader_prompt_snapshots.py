"""Prompt-snapshot net for the grading core (Wave 8 — guards the upcoming grade_assignment
phase-split, esp. the prompt-assembly extraction).

CRITICAL: the SDK-fake golden net (test_grader_golden.py) routes on response_format TYPE +
coarse content markers and returns a canned result REGARDLESS of the exact prompt wording — so
it does NOT catch prompt-text drift. The 18 AI grading factors flow through these prompts, so a
silent prompt regression = silent mis-grading. These snapshots pin the EXACT prompt text (sha256)
the grading functions send, plus the durable semantic invariants each prompt must contain.

When a prompt is changed INTENTIONALLY, re-capture the hash (run the capture snippet at the
bottom of this file) and update it here in the same commit — that's the explicit re-baseline.
"""
import hashlib
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tests/ for grading_fakes

import assignment_grader as g  # noqa: E402
from grading_fakes import patched_llm  # noqa: E402

_FIX = os.path.join(os.path.dirname(__file__), 'fixtures', 'grading')


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


@pytest.fixture(scope="module")
def ss():
    with open(os.path.join(_FIX, "submission_social_studies.txt")) as f:
        return f.read()


@pytest.fixture(scope="module")
def cfg():
    with open(os.path.join(_FIX, "config_social_studies.json")) as f:
        return json.load(f)


def test_grade_assignment_prompt_snapshot(ss, cfg):
    with patched_llm() as book:
        g.grade_assignment(
            student_name="Maria Garcia", assignment_data={"type": "text", "content": ss},
            custom_ai_instructions=cfg["gradingNotes"], grade_level="6", subject="Social Studies",
            ai_model="gpt-4o-mini", marker_config=cfg["customMarkers"], effort_points=15,
            grading_style="standard",
        )
    prompts = book.prompts(schema="GradingResponse")
    assert len(prompts) == 1
    prompt = prompts[0]
    # Exact-snapshot guard (re-baseline intentionally if the prompt changes on purpose):
    assert _h(prompt) == "c5ab6a530c4306a1", "grade_assignment prompt changed — re-baseline if intentional"
    # Durable semantic invariants (the grading factors that MUST be present):
    assert "Louisiana Purchase" in prompt          # the student's extracted responses
    assert "Napoleon needed money" in cfg["gradingNotes"]  # gradingNotes are passed through
    assert cfg["gradingNotes"][:40] in prompt       # teacher instructions in the prompt
    assert "CONTENT ACCURACY" in prompt             # the default rubric
    assert "GRADE LEVEL" in prompt.upper() or "grade 6" in prompt.lower()


def test_multipass_per_question_prompt_snapshot(ss, cfg):
    with patched_llm() as book:
        g.grade_multipass(
            student_name="Maria Garcia", assignment_data={"type": "text", "content": ss},
            custom_ai_instructions=cfg["gradingNotes"], grade_level="6", subject="Social Studies",
            ai_model="gpt-4o-mini", marker_config=cfg["customMarkers"], effort_points=15,
            grading_style="standard",
        )
        pq = book.prompts(schema="PerQuestionResponse")
        fb = book.prompts(schema="FeedbackResponse")
    assert len(pq) == 10
    # grade_multipass grades questions in PARALLEL threads → record order is non-deterministic.
    # Hash the SORTED set of prompts for an order-independent exact-snapshot.
    assert _h("\n===\n".join(sorted(pq))) == "1b23010a2a19d365", \
        "per-question prompts changed — re-baseline if intentional"
    assert all("QUESTION:" in p for p in pq)
    assert all("STUDENT ANSWER:" in p for p in pq)
    assert all("POINTS POSSIBLE:" in p for p in pq)
    assert all("GRADING APPROACH: STANDARD" in p for p in pq)

    assert len(fb) == 1
    assert _h(fb[0]) == "5fa64c107dde0ef8", "feedback prompt changed — re-baseline if intentional"
    assert "FEEDBACK STRUCTURE" in fb[0]
    assert "UNIVERSAL RULES" in fb[0]


# To re-baseline after an intentional prompt change:
#   from grading_fakes import patched_llm; import assignment_grader as g, hashlib, json
#   ... run the function under patched_llm(), then
#   hashlib.sha256(book.prompts(schema="GradingResponse")[0].encode()).hexdigest()[:16]
