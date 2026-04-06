"""Tests for POST /api/oneroster/sync-grades endpoint."""
import os
import sys
import pytest
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


# ── Helpers ───────────────────────────────────────────────────────────────────
#
# The Flask app registers routes via 'from .oneroster_routes import oneroster_bp'
# inside backend/routes/__init__.py.  When sys.path includes both the project
# root AND the backend/ directory, Python may store the same module under two
# keys in sys.modules: 'backend.routes.oneroster_routes' AND
# 'routes.oneroster_routes'.  Both copies have their own name bindings, so we
# must patch both to guarantee the running route function sees the mock.

def _config_targets():
    return [
        'backend.routes.oneroster_routes.get_oneroster_config',
        'routes.oneroster_routes.get_oneroster_config',
    ]


def _gradebook_targets(fn_name):
    return [
        f'backend.routes.oneroster_routes.{fn_name}',
        f'routes.oneroster_routes.{fn_name}',
    ]


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    """Create Flask app in test mode with dev auth bypass."""
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
    """Headers that simulate an authenticated teacher."""
    return {
        'X-Test-Teacher-Id': 'test-teacher-001',
        'Content-Type': 'application/json',
    }


@pytest.fixture
def valid_payload():
    return {
        "assessment_id": "assess-abc",
        "title": "Unit 3 Test",
        "total_points": 100,
        "class_sourced_id": "cls-001",
        "scores": [
            {"student_sourced_id": "stu-1", "score": 85, "max_score": 100, "comment": "Good work"},
        ],
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestSyncGradesNotConfigured:
    def test_returns_error_when_oneroster_not_configured(self, client, teacher_headers, valid_payload):
        """When get_oneroster_config returns None, should return 400 with 'not configured' message."""
        patches = [patch(t, return_value=None) for t in _config_targets()]
        with patches[0], patches[1]:
            resp = client.post(
                '/api/oneroster/sync-grades',
                json=valid_payload,
                headers=teacher_headers,
            )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "not configured" in data.get("error", "").lower()


class TestSyncGradesSuccess:
    def test_returns_sync_counts_on_success(self, client, teacher_headers, valid_payload):
        """When all deps succeed, should return 200 with synced/skipped/failed/errors counts."""
        mock_cfg = {
            "base_url": "https://sis.example.com/ims/oneroster/v1p1",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "token_url": None,
        }
        mock_post_result = {"synced": 1, "skipped": 0, "failed": 0, "errors": []}

        cfg_patches = [patch(t, return_value=mock_cfg) for t in _config_targets()]
        eli_patches = [patch(t, new=AsyncMock(return_value="li-001")) for t in _gradebook_targets("ensure_line_item")]
        pr_patches = [patch(t, new=AsyncMock(return_value=mock_post_result)) for t in _gradebook_targets("post_results")]
        all_patches = cfg_patches + eli_patches + pr_patches

        with all_patches[0], all_patches[1], all_patches[2], all_patches[3], all_patches[4], all_patches[5]:
            resp = client.post(
                '/api/oneroster/sync-grades',
                json=valid_payload,
                headers=teacher_headers,
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert data["line_item_id"] == "li-001"
        assert data["synced"] == 1
        assert data["skipped"] == 0
        assert data["failed"] == 0
        assert data["errors"] == []


class TestSyncGradesMissingFields:
    def test_returns_error_when_missing_required_fields(self, client, teacher_headers):
        """Partial payload missing total_points and class_sourced_id should return 400."""
        partial_payload = {
            "assessment_id": "assess-abc",
            "title": "Unit 3 Test",
            # missing total_points and class_sourced_id
            "scores": [{"student_sourced_id": "stu-1", "score": 85, "max_score": 100}],
        }
        mock_cfg = {
            "base_url": "https://sis.example.com/ims/oneroster/v1p1",
            "client_id": "cid",
            "client_secret": "csecret",
        }
        patches = [patch(t, return_value=mock_cfg) for t in _config_targets()]
        with patches[0], patches[1]:
            resp = client.post(
                '/api/oneroster/sync-grades',
                json=partial_payload,
                headers=teacher_headers,
            )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "missing" in data.get("error", "").lower()
