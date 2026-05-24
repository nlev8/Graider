"""Characterization tests for /api/regenerate-questions (Wave 6 Slice 11e).

Written BEFORE extracting the generation logic into planner_generation. Simpler
than the other generation handlers: NO mock fallback, NO _post_process_assignment,
NO _get_openai_context. no-questions -> 400; happy -> {"replacements", "usage"};
any failure -> generic 500. The happy path runs the real classify/hydrate/validate
pipeline on each new question (not mocked).
"""
import json
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture(autouse=True)
def _disable_rate_limiter():
    from backend.extensions import limiter
    prior = limiter.enabled
    limiter.enabled = False
    try:
        yield
    finally:
        limiter.enabled = prior


@pytest.fixture
def app():
    os.environ['FLASK_ENV'] = 'development'
    os.environ['DEV_USER_ID'] = 'test-teacher-001'
    from backend.app import app as flask_app
    flask_app.config['TESTING'] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def headers():
    return {'X-Test-Teacher-Id': 'test-teacher-001', 'Content-Type': 'application/json'}


def _completion(text):
    c = MagicMock()
    c.content_parts = [MagicMock(text=text)]
    c.usage = None
    return c


CONFIG = {"subject": "Math", "grade": "8"}
SPEC = [{"section_index": 0, "question_index": 2, "question_type": "short_answer",
         "points": 5, "dok": 1, "standard": "MA.8.1"}]


def test_regenerate_no_questions_returns_400(client, headers):
    resp = client.post('/api/regenerate-questions',
                      json={"questions_to_replace": [], "config": CONFIG}, headers=headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "No questions specified for regeneration"


def test_regenerate_happy_path_returns_replacements(client, headers):
    ai = json.dumps({"questions": [{"question": "What is 7 x 8?", "answer": "56", "points": 5,
                                    "question_type": "short_answer", "dok": 1, "number": 1}]})
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion(ai)
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        resp = client.post('/api/regenerate-questions',
                          json={"questions_to_replace": SPEC, "existing_questions": ["What is 2+2?"],
                                "config": CONFIG}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["replacements"][0]["section_index"] == 0
    assert body["replacements"][0]["question_index"] == 2
    assert body["replacements"][0]["question"]["question"] == "What is 7 x 8?"
    assert "usage" in body


def test_regenerate_ai_failure_returns_500(client, headers):
    fake_adapter = MagicMock()
    fake_adapter.chat.side_effect = RuntimeError("boom")
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        resp = client.post('/api/regenerate-questions',
                          json={"questions_to_replace": SPEC, "config": CONFIG}, headers=headers)
    assert resp.status_code == 500
    assert resp.get_json()["error"] == "An internal error occurred"


# ── Direct service-level test (pin generate_replacement_questions contract) ──


def test_service_happy_path_returns_replacements_and_usage():
    from backend.services.planner_generation import generate_replacement_questions
    ai = json.dumps({"questions": [{"question": "Solve 3x=9", "answer": "x=3", "points": 5,
                                    "question_type": "short_answer", "dok": 2, "number": 1}]})
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion(ai)
    with patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        out = generate_replacement_questions(
            questions_to_replace=SPEC, existing_questions=["old q"], config=CONFIG, api_key="fake-key")
    assert out["replacements"][0]["question"]["question"] == "Solve 3x=9"
    assert out["replacements"][0]["question"]["dok"] == 1   # DOK preserved from the spec
    assert out["usage"] is None
