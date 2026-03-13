"""
Flask test client fixtures for route integration tests.
Provides lightweight Flask app instances with mocked state functions.
"""
import os
import json
import threading
import pytest
from flask import Flask, g


@pytest.fixture
def mock_grading_state():
    """Return a fresh grading state dict matching _create_default_state."""
    return {
        "is_running": False,
        "stop_requested": False,
        "progress": 0,
        "total": 0,
        "current_file": "",
        "log": [],
        "results": [],
        "complete": False,
        "error": None,
        "session_cost": {
            "total_cost": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_api_calls": 0,
        },
        "cost_limit": 0,
        "cost_warning_pct": 80,
        "cost_limit_hit": False,
        "cost_warning_sent": False,
    }


@pytest.fixture
def grading_lock():
    """Return a threading lock for grading state."""
    return threading.Lock()


@pytest.fixture
def flask_app(mock_grading_state, grading_lock, tmp_path):
    """Create a Flask app with route blueprints registered using mock state functions."""
    app = Flask(__name__)
    app.config['TESTING'] = True

    # Create required directories in tmp_path
    assignments_dir = tmp_path / "assignments"
    assignments_dir.mkdir()
    exports_dir = tmp_path / "exports"
    exports_dir.mkdir()

    def get_state(teacher_id='local-dev'):
        return mock_grading_state

    def get_lock(teacher_id='local-dev'):
        return grading_lock

    def run_grading(state, **kwargs):
        pass

    def reset(teacher_id='local-dev'):
        pass

    from backend.routes import register_routes
    register_routes(app, get_state, run_grading, reset, get_lock)

    @app.before_request
    def set_test_user():
        g.user_id = 'test-teacher'

    return app


@pytest.fixture
def client(flask_app):
    """Flask test client for route integration tests."""
    return flask_app.test_client()


@pytest.fixture
def app_client(mock_grading_state, grading_lock, tmp_path):
    """Flask test client for app.py routes (grading, approvals, FERPA).

    This fixture creates a minimal Flask app that registers only the
    grading blueprint with mock state, suitable for testing grading
    status, start/stop, and approval endpoints.
    """
    app = Flask(__name__)
    app.config['TESTING'] = True

    def get_state(teacher_id='local-dev'):
        return mock_grading_state

    def get_lock(teacher_id='local-dev'):
        return grading_lock

    def run_grading(state, **kwargs):
        pass

    def reset(teacher_id='local-dev'):
        pass

    from backend.routes.grading_routes import grading_bp, init_grading_routes
    init_grading_routes(get_state, run_grading, reset, get_lock)
    app.register_blueprint(grading_bp)

    @app.before_request
    def set_test_user():
        g.user_id = 'test-teacher'

    return app.test_client()
