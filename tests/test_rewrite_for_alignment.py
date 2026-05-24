"""Characterization tests for /api/rewrite-for-alignment (Wave 6 Slice 8).

Written BEFORE extracting the AI rewrite into planner_standards. Mock OpenAIAdapter
(completion.usage=None so _extract_usage->None / _record_planner_cost no-ops).
load_standards tolerates an unknown state/subject (returns empty), so the enrich
step needs no mock — std_detail just falls back to {}.
"""
import json
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


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


QUESTIONS = [{"original_text": "What is a noun?", "target_standard": "ELA.1",
              "rewrite_goal": "increase rigor"}]


def test_rewrite_happy_path_returns_rewrites(client, headers):
    ai = json.dumps({"rewrites": [{"original_text": "What is a noun?",
                                   "rewritten_text": "Analyze the function of nouns in a sentence.",
                                   "standard_code": "ELA.1", "change_explanation": "raised DOK"}]})
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion(ai)
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        resp = client.post('/api/rewrite-for-alignment',
                          json={"questions": QUESTIONS, "grade": "7", "subject": "ELA", "state": "FL"},
                          headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["rewrites"][0]["rewritten_text"].startswith("Analyze the function")


def test_rewrite_no_questions_returns_error(client, headers):
    resp = client.post('/api/rewrite-for-alignment', json={"questions": []}, headers=headers)
    # Pin the exact branch (not just "an error") — guards against the api-key /
    # generic-500 paths masquerading as this one. 200, quirk.
    assert resp.get_json()["error"] == "No questions provided for rewriting"


def test_rewrite_non_json_ai_response_returns_error(client, headers):
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion("not json — rate limited maybe")
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        resp = client.post('/api/rewrite-for-alignment',
                          json={"questions": QUESTIONS}, headers=headers)
    body = resp.get_json()
    assert 'error' in body and 'non-JSON' in body['error']  # preserved quirk


# ── Direct service-level tests (pin rewrite_for_alignment_content contract) ──

ENRICHED = [{"original_text": "What is a noun?", "target_standard_code": "ELA.1",
             "target_benchmark": "", "target_topics": [], "target_vocabulary": [],
             "essential_questions": [], "rewrite_goal": "increase rigor"}]


def test_service_happy_path_returns_result_and_usage():
    from backend.services.planner_standards import rewrite_for_alignment_content
    ai = json.dumps({"rewrites": [{"original_text": "What is a noun?",
                                   "rewritten_text": "Analyze the function of nouns.",
                                   "standard_code": "ELA.1", "change_explanation": "raised DOK"}]})
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion(ai)
    with patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        out = rewrite_for_alignment_content(enriched_questions=ENRICHED, doc_text="ctx",
                                            grade="7", subject="ELA", api_key="fake-key")
    assert out["rewrites"][0]["rewritten_text"].startswith("Analyze")
    assert out["usage"] is None  # _completion sets usage=None -> _extract_usage None


def test_service_non_json_returns_error_dict():
    from backend.services.planner_standards import rewrite_for_alignment_content
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion("definitely not json")
    with patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        out = rewrite_for_alignment_content(enriched_questions=ENRICHED, doc_text="",
                                            grade="7", subject="ELA", api_key="fake-key")
    assert out == {"error": "AI returned non-JSON response. Possibly rate limited."}
