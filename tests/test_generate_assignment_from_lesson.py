"""Characterization tests for /api/generate-assignment-from-lesson (Wave 6 Slice 11d).

Written BEFORE extracting the generation logic into planner_generation. Pins:
- no-lesson-plan error
- the essay/project EARLY-RETURN wart: {"assignment": result} with NO usage/method
  (essay/project use dedicated prompts and skip _post_process_assignment)
- the mock-fallback wart on missing key / generic AI failure -> {"assignment":
  mock_assignment, "method": "Mock", "error"} at 200
- the network-error branch -> 503 with network_error

The assignment-type happy path (which runs _post_process_assignment) is covered by
a direct service test post-extraction.

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


LESSON = {"title": "The Bill of Rights", "overview": "A unit on the first 10 amendments.",
          "days": [{"objective": "Explain the 1st Amendment", "vocabulary": ["amendment"]}]}
CONFIG = {"subject": "Civics", "grade": "7"}


def test_assignment_no_lesson_plan_returns_error(client, headers):
    resp = client.post('/api/generate-assignment-from-lesson',
                      json={"lessonPlan": {}, "config": CONFIG}, headers=headers)
    assert resp.get_json()["error"] == "No lesson plan provided"


def test_assignment_essay_early_return_omits_usage_and_method(client, headers):
    # WART: essay/project use dedicated prompts and return {"assignment": result}
    # early — NO "usage", NO "method".
    ai = json.dumps({"title": "Essay: The Bill of Rights", "essay_prompt": "Analyze ...",
                     "total_points": 100})
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion(ai)
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        resp = client.post('/api/generate-assignment-from-lesson',
                          json={"lessonPlan": LESSON, "config": CONFIG,
                                "assignmentType": "essay"}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["assignment"]["sections"][0]["type"] == "essay"  # wrapped for frontend
    assert "method" not in body   # wart: early return omits these
    assert "usage" not in body


def test_assignment_missing_key_returns_mock_fallback(client, headers):
    with patch('backend.api_keys.get_api_key', return_value=''):
        resp = client.post('/api/generate-assignment-from-lesson',
                          json={"lessonPlan": LESSON, "config": CONFIG}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["method"] == "Mock"
    assert "Missing or placeholder API Key" in body["error"]
    assert body["assignment"]["sections"]  # mock has sections


def test_assignment_ai_failure_returns_mock_fallback(client, headers):
    fake_adapter = MagicMock()
    fake_adapter.chat.side_effect = RuntimeError("model overloaded")
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        resp = client.post('/api/generate-assignment-from-lesson',
                          json={"lessonPlan": LESSON, "config": CONFIG}, headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["method"] == "Mock"
    assert "model overloaded" in body["error"]


def test_assignment_network_error_returns_503(client, headers):
    fake_adapter = MagicMock()
    fake_adapter.chat.side_effect = RuntimeError("Connection refused by upstream")
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        resp = client.post('/api/generate-assignment-from-lesson',
                          json={"lessonPlan": LESSON, "config": CONFIG}, headers=headers)
    assert resp.status_code == 503
    assert resp.get_json()["network_error"] is True


# ── Direct service-level tests (pin the assignment-path post-processing + usage MERGE) ──


def test_service_assignment_path_merges_post_process_usage():
    # CONTRAST with generate_assessment (which DISCARDS): the assignment path MERGES
    # the _post_process_assignment extra usage into the returned usage.
    from backend.services.planner_generation import generate_assignment_from_lesson_content
    extra = {"input_tokens": 5, "output_tokens": 5, "total_tokens": 10, "cost": 0.002}
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion(json.dumps({"title": "HW", "sections": []}))
    with patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter), \
         patch('backend.services.planner_generation._post_process_assignment',
               return_value=({"title": "HW", "post": True}, extra)) as pp:
        out = generate_assignment_from_lesson_content(
            lesson_plan=LESSON, config=CONFIG, assignment_type="assignment",
            content_only=False, config_standards=[], reference_docs=[],
            api_key="fake-key", openai_context=("uid-9", None))
    assert out["method"] == "AI"
    assert out["content_only_mode"] is False
    assert out["assignment"]["post"] is True
    assert out["usage"] == extra                         # merged (vs assessment's discard)
    assert pp.call_args.kwargs["user_id"] == "uid-9"     # injected context used


def test_service_essay_early_return_omits_usage():
    # The essay path returns {"assignment": result} with NO usage/method, and never
    # calls _post_process_assignment.
    from backend.services.planner_generation import generate_assignment_from_lesson_content
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion(json.dumps({"essay_prompt": "Analyze ...",
                                                             "total_points": 100}))
    with patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter), \
         patch('backend.services.planner_generation._post_process_assignment') as pp:
        out = generate_assignment_from_lesson_content(
            lesson_plan=LESSON, config=CONFIG, assignment_type="essay",
            content_only=False, config_standards=[], reference_docs=[],
            api_key="fake-key", openai_context=("u", None))
    assert set(out.keys()) == {"assignment"}             # ONLY assignment (wart)
    assert out["assignment"]["sections"][0]["type"] == "essay"
    pp.assert_not_called()                                # essay skips post-processing


def test_service_missing_key_raises():
    from backend.services.planner_generation import generate_assignment_from_lesson_content
    with pytest.raises(Exception) as exc:
        generate_assignment_from_lesson_content(
            lesson_plan=LESSON, config=CONFIG, assignment_type="assignment",
            content_only=False, config_standards=[], reference_docs=[],
            api_key="", openai_context=("u", None))
    assert "Missing or placeholder API Key" in str(exc.value)
