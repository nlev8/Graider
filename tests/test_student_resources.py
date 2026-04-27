"""Tests for student portal resources -- publish + list + view."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask


def _make_app():
    """Create a minimal Flask app with student account routes."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test'
    app.config['RATELIMIT_ENABLED'] = False

    from backend.extensions import limiter
    limiter.init_app(app)

    from backend.routes.student_account_routes import student_account_bp
    app.register_blueprint(student_account_bp)
    return app


def _mock_supabase(content_data, enrolled=True):
    """Mock Supabase that returns published content.

    Phase 4: also returns a non-empty class_students lookup by default so the
    visibility helper passes the enrollment check. Pass enrolled=False to
    simulate a removed student.
    """
    mock_sb = MagicMock()

    def table_router(name):
        mock_table = MagicMock()
        result = MagicMock()
        if name == 'published_content':
            result.data = content_data
        elif name == 'class_students':
            result.data = [{'student_id': 'student-1'}] if enrolled else []
        else:
            result.data = []
        for method in ('select', 'eq', 'neq', 'ilike', 'like', 'order',
                       'limit', 'offset', 'gt', 'gte', 'lt', 'lte', 'in_',
                       'insert', 'update', 'delete', 'or_'):
            getattr(mock_table, method).return_value = mock_table
        mock_table.execute.return_value = result
        return mock_table

    mock_sb.table = table_router
    return mock_sb


VALID_SESSION = ('student-1', 'class-1')

MIXED_CONTENT = [
    {"id": "res-1", "title": "Unit 3 Study Guide", "content_type": "study_guide",
     "created_at": "2026-04-04T10:00:00", "is_active": True, "settings": {}},
    {"id": "res-2", "title": "Vocab Flashcards", "content_type": "flashcards",
     "created_at": "2026-04-04T11:00:00", "is_active": True, "settings": {}},
    {"id": "res-3", "title": "Chapter 5 Slides", "content_type": "slide_deck",
     "created_at": "2026-04-04T12:00:00", "is_active": True, "settings": {}},
    {"id": "res-4", "title": "Chapter 5 Quiz", "content_type": "assessment",
     "created_at": "2026-04-04T09:00:00", "is_active": True, "settings": {}},
]


class TestStudentResources:
    def test_returns_only_resource_types(self):
        """Should return study_guide/flashcards/slide_deck but NOT assessments."""
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.routes.student_account_routes._validate_student_session',
                       return_value=VALID_SESSION), \
                 patch('backend.routes.student_account_routes._get_supabase',
                       return_value=_mock_supabase(MIXED_CONTENT)):
                resp = client.get('/api/student/resources',
                                  headers={"X-Student-Token": "valid-token"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["resources"]) == 3
        types = [r["content_type"] for r in data["resources"]]
        assert "assessment" not in types
        assert "study_guide" in types
        assert "flashcards" in types
        assert "slide_deck" in types

    def test_rejects_missing_token(self):
        """Should return 401 without student token."""
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.routes.student_account_routes._validate_student_session',
                       return_value=None):
                resp = client.get('/api/student/resources')
        assert resp.status_code == 401

    def test_rejects_invalid_session(self):
        """Should return 401 with expired/invalid session."""
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.routes.student_account_routes._validate_student_session',
                       return_value=None):
                resp = client.get('/api/student/resources',
                                  headers={"X-Student-Token": "expired-token"})
        assert resp.status_code == 401

    def test_returns_empty_when_no_resources(self):
        """Should return empty list when only assessments published."""
        assessments_only = [
            {"id": "a1", "title": "Quiz", "content_type": "assessment",
             "created_at": "2026-04-04T09:00:00", "is_active": True, "settings": {}},
        ]
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.routes.student_account_routes._validate_student_session',
                       return_value=VALID_SESSION), \
                 patch('backend.routes.student_account_routes._get_supabase',
                       return_value=_mock_supabase(assessments_only)):
                resp = client.get('/api/student/resources',
                                  headers={"X-Student-Token": "valid-token"})
        data = resp.get_json()
        assert data["resources"] == []


class TestStudentResourceContent:
    def test_returns_resource_content(self):
        """Should return full resource content for a valid resource ID."""
        resource_data = [{
            "id": "res-1", "title": "Study Guide", "content_type": "study_guide",
            "content": {"sections": [{"heading": "Key Concepts", "content": ["Point 1"]}]},
            "settings": {}, "is_active": True,
        }]
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.routes.student_account_routes._validate_student_session',
                       return_value=VALID_SESSION), \
                 patch('backend.routes.student_account_routes._get_supabase',
                       return_value=_mock_supabase(resource_data)):
                resp = client.get('/api/student/resource/res-1',
                                  headers={"X-Student-Token": "valid-token"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["resource"]["title"] == "Study Guide"
        assert "sections" in data["resource"]["content"]

    def test_rejects_assessment_as_resource(self):
        """Should return 400 when requesting an assessment via resource endpoint."""
        assessment_data = [{
            "id": "a1", "title": "Quiz", "content_type": "assessment",
            "content": {}, "settings": {}, "is_active": True,
        }]
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.routes.student_account_routes._validate_student_session',
                       return_value=VALID_SESSION), \
                 patch('backend.routes.student_account_routes._get_supabase',
                       return_value=_mock_supabase(assessment_data)):
                resp = client.get('/api/student/resource/a1',
                                  headers={"X-Student-Token": "valid-token"})
        assert resp.status_code == 400

    def test_returns_404_for_missing_resource(self):
        """Should return 404 when resource doesn't exist."""
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.routes.student_account_routes._validate_student_session',
                       return_value=VALID_SESSION), \
                 patch('backend.routes.student_account_routes._get_supabase',
                       return_value=_mock_supabase([])):
                resp = client.get('/api/student/resource/nonexistent',
                                  headers={"X-Student-Token": "valid-token"})
        assert resp.status_code == 404


# ============ TARGETING LIST-FILTER (Phase 4) ============


@patch('backend.routes.student_account_routes._get_supabase')
def test_student_resources_filters_target_student_ids(mock_sb):
    """Phase 4: resource list excludes published_content targeting other students."""
    from datetime import datetime, timezone, timedelta
    expires = (datetime.now(tz=timezone.utc) + timedelta(hours=1)).isoformat().replace('+00:00', 'Z')
    STU_ME = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
    or_filter = {}
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.in_.return_value = chain
    chain.order.return_value = chain

    def _or_clause(clause):
        or_filter['clause'] = clause
        return chain

    chain.or_ = MagicMock(side_effect=_or_clause)
    # 3 calls: session lookup, session enrollment recheck (Task 11), resources query.
    chain.execute.side_effect = [
        MagicMock(data=[{'student_id': STU_ME, 'class_id': 'cls-1', 'expires_at': expires}]),
        MagicMock(data=[{'student_id': STU_ME}]),  # session enrollment recheck
        MagicMock(data=[]),  # resources query result
    ]
    sb = MagicMock()
    sb.table.return_value = chain
    mock_sb.return_value = sb

    app = _make_app()
    with app.test_client() as client:
        resp = client.get('/api/student/resources', headers={'X-Student-Token': 'tok'})
    assert resp.status_code == 200
    assert 'target_student_ids' in or_filter.get('clause', '')
    assert 'is.null' in or_filter['clause']
