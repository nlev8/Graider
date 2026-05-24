"""Characterization tests for /api/export-assessment-platform (Wave 6 Slice 4).

Written BEFORE extracting the platform-dispatch into planner_export, since the
endpoint had no CI-scoped test. Pins each platform's base64 output shape + the
unknown-platform 400. No mocking needed — pure data→format conversion.
"""
import base64
import os
import sys

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


ASSESSMENT = {
    "title": "Cells Quiz",
    "sections": [{
        "name": "Part A",
        "questions": [
            {"number": 1, "question": "What is a cell?", "type": "multiple_choice",
             "options": ["unit of life", "a prison", "a phone", "a battery"],
             "answer": "unit of life", "points": 2, "dok": 1, "standard": "SCI.1"},
            {"number": 2, "question": "Define mitochondria.", "type": "short_answer",
             "answer": "powerhouse of the cell", "points": 3, "dok": 2, "standard": "SCI.2"},
        ],
    }],
}


def _post(client, headers, platform):
    return client.post('/api/export-assessment-platform',
                       json={"assessment": ASSESSMENT, "platform": platform}, headers=headers)


def test_csv_export_returns_base64_csv_with_questions(client, headers):
    resp = _post(client, headers, 'csv')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['format'] == 'csv' and body['mime_type'] == 'text/csv'
    decoded = base64.b64decode(body['document']).decode('utf-8')
    assert "What is a cell?" in decoded
    assert "unit of life" in decoded
    assert "Cells_Quiz" in body['filename']


def test_wayground_aliases_csv(client, headers):
    resp = _post(client, headers, 'wayground')
    assert resp.status_code == 200
    assert resp.get_json()['format'] == 'csv'


def test_canvas_qti_returns_base64_xml(client, headers):
    resp = _post(client, headers, 'canvas_qti')
    assert resp.status_code == 200
    body = resp.get_json()
    decoded = base64.b64decode(body['document']).decode('utf-8')
    assert "<" in decoded and "qti" in body['filename'].lower()


def test_kahoot_export_succeeds(client, headers):
    resp = _post(client, headers, 'kahoot')
    assert resp.status_code == 200
    assert 'document' in resp.get_json()


def test_unknown_platform_returns_400(client, headers):
    resp = _post(client, headers, 'nonsense-platform')
    assert resp.status_code == 400
    assert 'Unknown platform' in resp.get_json().get('error', '')


def test_no_assessment_returns_400(client, headers):
    resp = client.post('/api/export-assessment-platform',
                      json={"platform": "csv"}, headers=headers)
    assert resp.status_code == 400


# ── Direct service tests for build_platform_export (Wave 6 Slice 4) ──

def test_build_platform_export_csv_returns_dict():
    from backend.services.planner_export import build_platform_export
    out = build_platform_export(ASSESSMENT, "csv", None)
    assert out["format"] == "csv" and out["mime_type"] == "text/csv"
    decoded = base64.b64decode(out["document"]).decode("utf-8")
    assert "What is a cell?" in decoded


def test_build_platform_export_unknown_returns_none():
    from backend.services.planner_export import build_platform_export
    assert build_platform_export(ASSESSMENT, "nonsense", None) is None
