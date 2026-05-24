"""Characterization tests for /api/generate-lesson-plan (Wave 6 Slice 11b).

Written BEFORE extracting the generation logic into planner_generation. Pins:
- single non-Assignment happy path -> {"plan", "method": "AI", "usage"}
- variations happy path -> {"variations": [3], "method": "AI", "usage"} (each
  variation gets an "approach")
- no-standards error
- the mock-fallback wart: ANY failure (missing key, AI error) -> {"plan":
  mock_plan, "method": "Mock", "error"} at 200.

The Assignment content_type branch (which calls _post_process_assignment +
_get_openai_context) is covered by a direct service test post-extraction — it's
hard to patch consistently across the route/service module boundary here.

Handler is @limiter.limit; autouse fixture disables the shared limiter.
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


CONFIG = {"subject": "Civics", "grade": "7", "type": "Lesson Plan", "duration": 3}
PLAN_JSON = json.dumps({"title": "The Bill of Rights", "overview": "A 3-day unit.",
                        "days": [{"day": 1, "topic": "Amendments 1-5"}]})


def test_lesson_plan_single_happy_path(client, headers):
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion(PLAN_JSON)
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        resp = client.post('/api/generate-lesson-plan',
                          json={"standards": ["SS.7.C.2.4"], "config": CONFIG}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["method"] == "AI"
    assert body["plan"]["title"] == "The Bill of Rights"
    assert "usage" in body


def test_lesson_plan_variations_happy_path(client, headers):
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion(PLAN_JSON)
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        resp = client.post('/api/generate-lesson-plan',
                          json={"standards": ["SS.7.C.2.4"], "config": CONFIG,
                                "generateVariations": True}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["method"] == "AI"
    assert len(body["variations"]) == 3  # 3 approaches for non-Assignment
    assert all("approach" in v for v in body["variations"])


def test_lesson_plan_no_standards_returns_error(client, headers):
    resp = client.post('/api/generate-lesson-plan', json={"standards": [], "config": CONFIG},
                      headers=headers)
    assert resp.get_json()["error"] == "Please select standards or upload reference documents"


def test_lesson_plan_missing_key_returns_mock_fallback(client, headers):
    with patch('backend.api_keys.get_api_key', return_value=''):
        resp = client.post('/api/generate-lesson-plan',
                          json={"standards": ["SS.7.C.2.4"], "config": CONFIG}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["method"] == "Mock"
    assert "Missing or placeholder API Key" in body["error"]
    assert body["plan"]["days"]  # mock_plan has fallback days


def test_lesson_plan_ai_failure_returns_mock_fallback(client, headers):
    fake_adapter = MagicMock()
    fake_adapter.chat.side_effect = RuntimeError("upstream 503")
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        resp = client.post('/api/generate-lesson-plan',
                          json={"standards": ["SS.7.C.2.4"], "config": CONFIG}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["method"] == "Mock"
    assert "upstream 503" in body["error"]


# ── Direct service-level tests (pin generate_lesson_plan_content contract) ──


def test_service_missing_key_raises():
    from backend.services.planner_generation import generate_lesson_plan_content
    with pytest.raises(Exception) as exc:
        generate_lesson_plan_content(selected_standards=["x"], config=CONFIG, selected_idea=None,
                                     generate_variations=False, reference_docs=[], api_key="",
                                     openai_context=("u", None))
    assert "Missing or placeholder API Key" in str(exc.value)


def test_service_assignment_path_runs_post_processing_with_injected_context():
    # The Assignment branch calls _post_process_assignment with the user_id from
    # the injected openai_context (the g-reading shim, resolved route-side).
    from backend.services.planner_generation import generate_lesson_plan_content
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion(json.dumps(
        {"title": "Quiz", "sections": [{"name": "A", "questions": []}]}))
    cfg = {"subject": "Civics", "grade": "7", "type": "Assignment", "totalQuestions": 5}
    with patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter), \
         patch('backend.services.planner_generation._post_process_assignment',
               return_value=({"title": "Quiz", "post": True},
                             {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "cost": 0.0})) as pp:
        out = generate_lesson_plan_content(
            selected_standards=["SS.7.C.2.4: Civics"], config=cfg, selected_idea=None,
            generate_variations=False, reference_docs=[], api_key="fake-key",
            openai_context=("uid-xyz", None))
    assert out["method"] == "AI"
    assert out["plan"]["post"] is True              # post-processed plan returned
    assert pp.call_args.kwargs["user_id"] == "uid-xyz"  # injected context used
