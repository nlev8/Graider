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


DECK = {"title": "Cells", "template": "academic", "theme": {"primary_color": "#1a7f43"},
        "slides": [{"layout": "title", "title": "Cells"}]}


def test_slides_html_returns_html(client, headers):
    resp = client.post('/api/slides/html', json={"slides": DECK}, headers=headers)
    assert resp.status_code == 200
    assert resp.mimetype == "text/html"
    assert b"Cells" in resp.data and b"<!DOCTYPE html>" in resp.data


def test_slides_pdf_success(client, headers, monkeypatch):
    monkeypatch.setattr("backend.routes.planner_routes.html_to_pdf", lambda html: b"%PDF-1.4 fake")
    resp = client.post('/api/slides/pdf', json={"slides": DECK}, headers=headers)
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data[:5] == b"%PDF-"


def test_slides_pdf_unavailable_returns_clean_error(client, headers, monkeypatch):
    from backend.services.slide_pdf import SlidePdfError

    def boom(html):
        raise SlidePdfError("no chromium")
    monkeypatch.setattr("backend.routes.planner_routes.html_to_pdf", boom)
    resp = client.post('/api/slides/pdf', json={"slides": DECK}, headers=headers)
    assert resp.status_code == 503
    assert "PowerPoint" in resp.get_json().get("error", "")


def test_slides_html_empty_deck_returns_400(client, headers):
    resp = client.post('/api/slides/html', json={"slides": {"slides": []}}, headers=headers)
    assert resp.status_code == 400
