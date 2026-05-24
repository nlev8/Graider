"""Characterization tests for /api/align-document-to-standards (Wave 6 Slice 9).

Written BEFORE extracting the AI alignment call into planner_standards. Same
shape as the rewrite_for_alignment slice: mock OpenAIAdapter (completion.usage=None
so _extract_usage->None / _record_planner_cost no-ops). Unlike rewrite, this
endpoint hard-errors when load_standards returns no standards, so the happy path
patches planner_routes.load_standards to return a non-empty list.
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


STANDARDS = {'standards': [{"code": "SS.7.C.1.1", "benchmark": "Analyze ...",
                            "topics": ["gov"], "vocabulary": ["republic"], "dok": "2"}]}


def test_align_happy_path_returns_matched_standards(client, headers):
    ai = json.dumps({"matched_standards": [{"code": "SS.7.C.1.1", "benchmark": "Analyze ...",
                                            "confidence": 0.8, "evidence": "para 1",
                                            "alignment_notes": "covered"}],
                     "unmatched_standards": [], "overall_alignment_score": 0.8,
                     "suggestions": [], "question_analysis": []})
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion(ai)
    with patch('backend.routes.planner_routes.load_standards', return_value=STANDARDS), \
         patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        resp = client.post('/api/align-document-to-standards',
                          json={"documentText": "The republic is a form of government.",
                                "grade": "7", "subject": "Civics", "state": "FL"},
                          headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["matched_standards"][0]["code"] == "SS.7.C.1.1"
    assert body["usage"] is None


def test_align_no_document_text_returns_error(client, headers):
    resp = client.post('/api/align-document-to-standards',
                      json={"documentText": "  ", "subject": "Civics"}, headers=headers)
    assert resp.get_json()["error"] == "No document text provided"  # 200, quirk


def test_align_no_subject_returns_error(client, headers):
    resp = client.post('/api/align-document-to-standards',
                      json={"documentText": "some text"}, headers=headers)
    assert resp.get_json()["error"] == "Subject is required. Set it in Settings."


def test_align_no_standards_returns_error(client, headers):
    with patch('backend.routes.planner_routes.load_standards', return_value={'standards': []}):
        resp = client.post('/api/align-document-to-standards',
                          json={"documentText": "text", "subject": "Civics",
                                "state": "ZZ", "grade": "7"}, headers=headers)
    assert "No standards found" in resp.get_json()["error"]


def test_align_non_json_ai_response_returns_error(client, headers):
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion("not json — maybe rate limited")
    with patch('backend.routes.planner_routes.load_standards', return_value=STANDARDS), \
         patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        resp = client.post('/api/align-document-to-standards',
                          json={"documentText": "text", "subject": "Civics"}, headers=headers)
    body = resp.get_json()
    assert 'error' in body and 'non-JSON' in body['error']


# ── Direct service-level tests (pin align_document_to_standards_content contract) ──

STANDARDS_REF = [{"code": "SS.7.C.1.1", "benchmark": "Analyze ...", "topics": ["gov"],
                  "vocabulary": ["republic"], "dok": "2"}]


def test_service_happy_path_returns_result_and_usage():
    from backend.services.planner_standards import align_document_to_standards_content
    ai = json.dumps({"matched_standards": [{"code": "SS.7.C.1.1", "confidence": 0.7}],
                     "unmatched_standards": [], "overall_alignment_score": 0.7,
                     "suggestions": [], "question_analysis": []})
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion(ai)
    with patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        out = align_document_to_standards_content(doc_text="The republic ...",
                                                  standards_ref=STANDARDS_REF, api_key="fake-key")
    assert out["matched_standards"][0]["code"] == "SS.7.C.1.1"
    assert out["usage"] is None


def test_service_non_json_returns_error_dict():
    from backend.services.planner_standards import align_document_to_standards_content
    fake_adapter = MagicMock()
    fake_adapter.chat.return_value = _completion("definitely not json")
    with patch('backend.services.llm_adapter.OpenAIAdapter', return_value=fake_adapter):
        out = align_document_to_standards_content(doc_text="x", standards_ref=STANDARDS_REF,
                                                  api_key="fake-key")
    assert out == {"error": "AI returned non-JSON response. Possibly rate limited."}
