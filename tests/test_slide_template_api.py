import os, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

@pytest.fixture
def app():
    os.environ['FLASK_ENV'] = 'development'; os.environ['DEV_USER_ID'] = 'test-teacher-001'
    from backend.app import app as flask_app
    flask_app.config['TESTING'] = True
    return flask_app

@pytest.fixture
def client(app): return app.test_client()

@pytest.fixture
def headers(): return {'X-Test-Teacher-Id': 'test-teacher-001', 'Content-Type': 'application/json'}


def test_slide_templates_endpoint_returns_grouped_registry(client, headers):
    resp = client.get('/api/slide-templates', headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "groups" in data
    keys = [t["key"] for g in data["groups"] for t in g["templates"]]
    assert "editorial-bold" in keys and "minimal" in keys
    # each template exposes key + name + group
    sample = data["groups"][0]["templates"][0]
    assert {"key", "name"} <= set(sample)
