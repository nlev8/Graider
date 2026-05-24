"""Characterization tests for /api/adjust-reading-level (Wave 6 Slice 7).

Written BEFORE extracting the rewrite logic into planner_content_tools. The mock
OpenAIAdapter returns a completion with usage=None, so _extract_usage returns None
and _record_planner_cost is a no-op (no patching of those needed; works pre/post).
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
    c.usage = None  # -> _extract_usage returns None, _record_planner_cost no-ops
    return c


AI_JSON = json.dumps({
    "adjusted_text": "The cat sat. It was happy.",
    "reading_level_estimate": "3.1",
    "vocabulary_changes": [{"original": "feline", "replacement": "cat"}],
})


def test_adjust_reading_level_happy_path(client, headers):
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion(AI_JSON)
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        resp = client.post('/api/adjust-reading-level',
                          json={"text": "The feline was content.", "target_level": "3", "subject": "ELA"},
                          headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["adjusted_text"] == "The cat sat. It was happy."
    assert body["reading_level_estimate"] == "3.1"
    assert body["vocabulary_changes"][0]["replacement"] == "cat"


def test_adjust_reading_level_no_text_returns_400(client, headers):
    with patch('backend.api_keys.get_api_key', return_value='fake-key'):
        resp = client.post('/api/adjust-reading-level', json={"text": "  "}, headers=headers)
    assert resp.status_code == 400


def test_adjust_reading_level_missing_key_returns_error(client, headers):
    # Quirk preserved: missing key returns a jsonify error with NO status code (=200).
    with patch('backend.api_keys.get_api_key', return_value=''):
        resp = client.post('/api/adjust-reading-level', json={"text": "hello"}, headers=headers)
    assert 'error' in resp.get_json()
    assert 'API Key' in resp.get_json()['error']
