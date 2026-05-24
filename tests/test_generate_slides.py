"""Characterization tests for /api/generate-slides (Wave 6 Slice 6).

Written BEFORE extracting the orchestration into planner_study_aids, since the
endpoint had no CI-scoped test. Mocks the slide_generator service functions.
"""
import os
import sys
from unittest.mock import patch

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


SLIDE_DATA = {"title": "Cells", "theme": {"bg": "white"},
              "slides": [{"heading": "Intro"}, {"heading": "Detail"}]}


def test_generate_slides_no_content_returns_400(client, headers):
    resp = client.post('/api/generate-slides', json={}, headers=headers)
    assert resp.status_code == 400


def test_generate_slides_happy_path_no_images(client, headers):
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.slide_generator.generate_slide_content', return_value=SLIDE_DATA), \
         patch('backend.services.slide_generator.generate_slide_images') as mock_imgs:
        resp = client.post('/api/generate-slides',
                          json={"content": "cells are units of life", "generateImages": False},
                          headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['title'] == 'Cells'
    assert body['slide_count'] == 2
    assert body['images_generated'] == 0
    mock_imgs.assert_not_called()  # generateImages=False skips image gen


def test_generate_slides_with_images(client, headers):
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.slide_generator.generate_slide_content', return_value=dict(SLIDE_DATA)), \
         patch('backend.services.slide_generator.generate_slide_images', return_value={0: b"imgbytes", 1: b"more"}):
        resp = client.post('/api/generate-slides',
                          json={"content": "cells", "generateImages": True},
                          headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()['images_generated'] == 2


def test_generate_slides_image_failure_continues(client, headers):
    # Image-gen failure is swallowed; slides still returned with 0 images.
    with patch('backend.api_keys.get_api_key', return_value='fake-key'), \
         patch('backend.services.slide_generator.generate_slide_content', return_value=dict(SLIDE_DATA)), \
         patch('backend.services.slide_generator.generate_slide_images', side_effect=RuntimeError("img fail")):
        resp = client.post('/api/generate-slides',
                          json={"content": "cells", "generateImages": True},
                          headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()['images_generated'] == 0
