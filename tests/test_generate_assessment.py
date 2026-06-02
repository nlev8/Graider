"""Characterization tests for /api/generate-assessment (Wave 6 Slice 11c).

Written BEFORE extracting the generation logic into planner_generation. UNLIKE
brainstorm/lesson_plan, this endpoint has NO mock fallback — any failure returns a
real 500 ("Failed to generate assessment: {error_msg}"). The happy path always
runs _post_process_assignment (hard to patch consistently across the route/service
module boundary), so it is pinned by a DIRECT service test post-extraction; these
route tests pin the paths that bail before post-processing.

Handler is @limiter.limit; autouse fixture disables the shared limiter.
"""
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


CONFIG = {"subject": "US History", "grade": "8"}
ACFG = {"type": "quiz", "title": "Ch 5 Quiz", "totalQuestions": 10}


def test_assessment_no_standards_returns_error(client, headers):
    resp = client.post('/api/generate-assessment',
                      json={"standards": [], "config": CONFIG, "assessmentConfig": ACFG},
                      headers=headers)
    assert resp.get_json()["error"] == "No standards provided"  # 200, quirk


def test_assessment_missing_key_returns_500(client, headers):
    with patch('backend.api_keys.get_api_key', return_value=''):
        resp = client.post('/api/generate-assessment',
                          json={"standards": ["SS.8.A.1.1"], "config": CONFIG,
                                "assessmentConfig": ACFG}, headers=headers)
    assert resp.status_code == 500  # NO mock fallback — real 500
    # Generic, non-leaking message: the raw exception ("Missing or placeholder
    # API Key") must NOT reach the client.
    err = resp.get_json()["error"]
    assert err == "Failed to generate assessment"
    assert "Missing or placeholder API Key" not in err


def test_assessment_ai_failure_returns_500(client, headers):
    fake_adapter = MagicMock()
    fake_adapter.chat.side_effect = RuntimeError("upstream 502")
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        resp = client.post('/api/generate-assessment',
                          json={"standards": ["SS.8.A.1.1"], "config": CONFIG,
                                "assessmentConfig": ACFG}, headers=headers)
    assert resp.status_code == 500
    # Generic, non-leaking message: the raw exception ("upstream 502") must NOT
    # reach the client (Security/Error-Handling rubric level-8 [CAP]).
    err = resp.get_json()["error"]
    assert err == "Failed to generate assessment"
    assert "upstream 502" not in err


# ── Direct service-level tests (pin generate_assessment_content + usage-discard wart) ──


def _completion(text):
    c = MagicMock()
    c.content_parts = [MagicMock(text=text)]
    c.usage = None
    return c


def test_service_happy_path_discards_post_process_usage():
    # WART: `assessment, _ = _post_process_assignment(...)` discards the extra usage.
    # result["usage"] reflects ONLY _extract_usage(completion) (None here), NOT the
    # non-trivial extra_usage the post-processor returns.
    import json
    from backend.services.planner_generation import generate_assessment_content
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion(json.dumps({"title": "Quiz", "questions": []}))
    with patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter), \
         patch('backend.services.planner_generation._post_process_assignment',
               return_value=({"title": "Quiz Post"},
                             {"input_tokens": 9, "output_tokens": 9, "total_tokens": 99, "cost": 0.01})) as pp:
        out = generate_assessment_content(
            standards=[{"code": "SS.8.A.1.1"}], config=CONFIG, assessment_config=ACFG,
            content_only=False, content_sources=[], api_key="fake-key",
            openai_context=("uid-7", None))
    assert out["method"] == "AI"
    assert out["assessment"]["title"] == "Quiz Post"          # post-processed assessment
    assert out["assessment"]["grade_level"] == "8"            # metadata added
    assert out["usage"] is None                               # extra_usage DISCARDED (wart)
    assert "warnings" not in out                              # no sections -> no quality warnings
    assert pp.call_args.kwargs["user_id"] == "uid-7"          # injected context used


def test_service_missing_key_raises():
    from backend.services.planner_generation import generate_assessment_content
    with pytest.raises(Exception) as exc:
        generate_assessment_content(standards=[{"code": "x"}], config=CONFIG, assessment_config=ACFG,
                                    content_only=False, content_sources=[], api_key="",
                                    openai_context=("u", None))
    assert "Missing or placeholder API Key" in str(exc.value)
