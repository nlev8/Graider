"""Characterization tests for /api/brainstorm-lesson-ideas (Wave 6 Slice 11a).

Written BEFORE extracting the generation logic into planner_generation. Pins the
endpoint's mock-fallback wart: the whole body is wrapped in try/except where ANY
failure (including a missing key) returns {**mock_ideas, "error": ..., "method":
"Mock"} at 200 — NOT an error status. The happy path returns {**ideas, "usage"}.

The handler is @limiter.limit("10 per minute"); an autouse fixture disables the
shared limiter so adding these tests can't trip a cumulative-429 elsewhere in the
suite (same lever as test_admin_routes.py).
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


CONFIG = {"subject": "Civics", "grade": "7", "requirements": "focus on the Bill of Rights"}


def test_brainstorm_happy_path_returns_ideas(client, headers):
    ai = json.dumps({"ideas": [{"id": 1, "title": "Mock Trial", "approach": "Simulation",
                                "brief": "Students role-play a court case."}]})
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion(ai)
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        resp = client.post('/api/brainstorm-lesson-ideas',
                          json={"standards": ["SS.7.C.2.4"], "config": CONFIG}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ideas"][0]["title"] == "Mock Trial"
    assert "usage" in body
    assert "method" not in body  # not the mock fallback


def test_brainstorm_no_standards_no_docs_returns_error(client, headers):
    resp = client.post('/api/brainstorm-lesson-ideas', json={"standards": [], "config": CONFIG},
                      headers=headers)
    assert resp.get_json()["error"] == "Please select standards or upload reference documents"


def test_brainstorm_missing_key_returns_mock_fallback(client, headers):
    with patch('backend.api_keys.get_api_key', return_value=''):
        resp = client.post('/api/brainstorm-lesson-ideas',
                          json={"standards": ["SS.7.C.2.4"], "config": CONFIG}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["method"] == "Mock"  # wart: mock fallback at 200
    assert "Missing or placeholder API Key" in body["error"]
    assert len(body["ideas"]) == 3  # the 3 hardcoded fallback ideas


def test_brainstorm_ai_failure_returns_mock_fallback(client, headers):
    fake_adapter = MagicMock()
    fake_adapter.chat.side_effect = RuntimeError("upstream 500")
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        resp = client.post('/api/brainstorm-lesson-ideas',
                          json={"standards": ["SS.7.C.2.4"], "config": CONFIG}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["method"] == "Mock"
    assert "upstream 500" in body["error"]
    assert len(body["ideas"]) == 3


# ── Direct service-level tests (pin brainstorm_lesson_ideas_content contract) ──


def test_service_happy_path_returns_ideas_and_usage():
    from backend.services.planner_generation import brainstorm_lesson_ideas_content
    ai = json.dumps({"ideas": [{"id": 1, "title": "Debate"}]})
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion(ai)
    with patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        out = brainstorm_lesson_ideas_content(selected_standards=["SS.7.C.2.4"],
                                              config=CONFIG, api_key="fake-key")
    assert out["ideas"][0]["title"] == "Debate"
    assert out["usage"] is None


def test_service_missing_key_raises():
    from backend.services.planner_generation import brainstorm_lesson_ideas_content
    with pytest.raises(Exception) as exc:
        brainstorm_lesson_ideas_content(selected_standards=["SS.7.C.2.4"], config=CONFIG, api_key="")
    assert "Missing or placeholder API Key" in str(exc.value)
