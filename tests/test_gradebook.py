"""Tests for the gradebook endpoint and the _coalesce helper.

Spec: docs/superpowers/specs/2026-04-25-phase3a-gradebook-design.md
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


# ============ _coalesce helper unit tests ============

class TestCoalesce:
    """_coalesce: first-non-None semantics (NOT `or`-truthiness)."""

    def test_returns_first_non_none(self):
        from backend.routes.student_portal_routes import _coalesce
        assert _coalesce(None, "fallback", "later") == "fallback"

    def test_returns_default_when_all_none(self):
        from backend.routes.student_portal_routes import _coalesce
        assert _coalesce(None, None, default=42) == 42

    def test_zero_is_kept_not_treated_as_falsy(self):
        """The whole reason this helper exists: legitimate 0 must not fall through."""
        from backend.routes.student_portal_routes import _coalesce
        assert _coalesce(0, 999, default=-1) == 0

    def test_empty_string_is_kept_not_treated_as_falsy(self):
        from backend.routes.student_portal_routes import _coalesce
        assert _coalesce("", "fallback", default="default") == ""


# ============ Test fixtures ============

@pytest.fixture
def app():
    """Flask app in test mode."""
    os.environ['FLASK_ENV'] = 'development'
    os.environ['DEV_USER_ID'] = 'test-teacher-001'
    from backend.app import app as flask_app
    flask_app.config['TESTING'] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def teacher_headers():
    return {'X-Test-Teacher-Id': 'test-teacher-001', 'Content-Type': 'application/json'}


@pytest.fixture
def client_no_auth():
    """Minimal Flask app WITHOUT the dev-mode before_request hook so
    require_teacher can return 401. Mirrors tests/test_sso_contracts.py."""
    from flask import Flask
    from backend.routes.student_portal_routes import student_portal_bp
    isolated = Flask(__name__)
    isolated.config['TESTING'] = True
    isolated.config['SECRET_KEY'] = 'test'
    isolated.register_blueprint(student_portal_bp)
    return isolated.test_client()


def _make_chain(execute_data=None):
    """Chainable Supabase mock that ACTUALLY APPLIES `.eq()` filters when
    `.execute()` is called. This makes a single mock-table answer multiple
    queries with different filters correctly (e.g., looking up one
    submission by id, then later querying for sibling attempts of the
    same student/content). Without this, the same data set is returned
    regardless of filter, which masks query bugs.
    """
    data = list(execute_data) if execute_data else []
    chain = MagicMock()
    chain.select.return_value = chain
    chain.neq.return_value = chain
    chain.in_.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    filters = []  # list of ('eq', field, value)

    def _eq(field, value):
        filters.append(('eq', field, value))
        return chain
    chain.eq.side_effect = _eq

    def _execute():
        result = data
        for op, field, value in filters:
            if op == 'eq':
                result = [r for r in result if r.get(field) == value]
        filters.clear()
        return MagicMock(data=result)
    chain.execute.side_effect = _execute
    return chain


def _multi_table_sb(table_map):
    """Mock supabase that returns a FRESH `_make_chain` per `db.table(name)`
    call (so each query gets its own filter list). Same-table queries are
    distinguished by their `.eq()` filters."""
    mock_sb = MagicMock()
    def table_side_effect(name):
        val = table_map.get(name)
        if val is None:
            return _make_chain([])
        return _make_chain(val)
    mock_sb.table.side_effect = table_side_effect
    return mock_sb


# ============ Authz tests ============

class TestGradebookAuthz:
    """Auth + class-ownership checks."""

    def test_unauthenticated_returns_401(self, client_no_auth):
        resp = client_no_auth.get('/api/teacher/class/cls-1/gradebook')
        assert resp.status_code == 401

    @patch('backend.routes.student_portal_routes._get_teacher_supabase')
    def test_other_teacher_class_returns_403(self, mock_sb_fn, client, teacher_headers):
        mock_sb_fn.return_value = _multi_table_sb({
            'classes': [{'id': 'cls-1', 'name': 'C', 'teacher_id': 'OTHER-teacher'}],
        })
        resp = client.get('/api/teacher/class/cls-1/gradebook', headers=teacher_headers)
        assert resp.status_code == 403
        body = resp.get_json()
        assert body.get('type') == 'https://graider.live/errors/forbidden'
        assert body.get('status') == 403
        assert 'error' in body
