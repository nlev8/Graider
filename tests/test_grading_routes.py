"""Integration tests for grading API routes."""
import json
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.conftest_routes import app_client, mock_grading_state, grading_lock

from unittest.mock import patch, MagicMock
from flask import Flask, g, request, jsonify


# ---------------------------------------------------------------------------
# Helper fixture: Flask test client that includes the app.py-only routes
# (update-approval, bulk-update-approvals, delete-result) with mocked
# side-effect functions so we can test them without the full app.py imports.
# ---------------------------------------------------------------------------

@pytest.fixture
def app_full_client(mock_grading_state, grading_lock):
    """Flask test client that registers grading blueprint AND app.py routes."""
    app = Flask(__name__)
    app.config['TESTING'] = True

    _state = mock_grading_state

    def get_state(teacher_id='local-dev'):
        return _state

    def get_lock(teacher_id='local-dev'):
        return grading_lock

    def run_grading(state, **kwargs):
        pass

    def reset(teacher_id='local-dev'):
        pass

    # Register the grading blueprint
    from backend.routes.grading_routes import grading_bp, init_grading_routes
    init_grading_routes(get_state, run_grading, reset, get_lock)
    app.register_blueprint(grading_bp)

    # Track calls to side-effect functions
    app._save_results_calls = []
    app._audit_log_calls = []

    # Manually register app.py routes that aren't in the blueprint
    @app.route('/api/update-approval', methods=['POST'])
    def update_approval():
        grading_state = get_state()
        data = request.json
        filename = data.get('filename')
        approval = data.get('approval')
        graded_at = data.get('graded_at')

        if not filename:
            return jsonify({"error": "Missing filename"}), 400

        target = None
        for r in grading_state["results"]:
            if r.get('filename') == filename:
                if graded_at and r.get('graded_at') == graded_at:
                    target = r
                    break
                if target is None:
                    target = r

        if target:
            target['email_approval'] = approval
            app._save_results_calls.append(grading_state["results"])
            return jsonify({"status": "updated", "filename": filename, "approval": approval})

        return jsonify({"error": "Result not found"}), 404

    @app.route('/api/update-approvals-bulk', methods=['POST'])
    def update_approvals_bulk():
        grading_state = get_state()
        data = request.json
        approvals = data.get('approvals', {})

        if not approvals:
            return jsonify({"error": "No approvals provided"}), 400

        updated = 0
        for r in grading_state["results"]:
            filename = r.get('filename')
            if filename in approvals:
                r['email_approval'] = approvals[filename]
                updated += 1

        if updated > 0:
            app._save_results_calls.append(grading_state["results"])

        return jsonify({"status": "updated", "count": updated})

    @app.route('/api/delete-result', methods=['POST'])
    def delete_single_result():
        grading_state = get_state()

        if grading_state["is_running"]:
            return jsonify({"error": "Cannot delete results while grading is in progress"}), 400

        data = request.json
        filename = data.get('filename', '')

        if not filename:
            return jsonify({"error": "Filename is required"}), 400

        original_count = len(grading_state["results"])
        grading_state["results"] = [
            r for r in grading_state["results"]
            if r.get('filename', '') != filename
        ]

        if len(grading_state["results"]) == original_count:
            return jsonify({"status": "already_deleted", "filename": filename})

        app._save_results_calls.append(list(grading_state["results"]))
        app._audit_log_calls.append(("DELETE_RESULT", filename))

        return jsonify({
            "status": "deleted",
            "filename": filename,
            "remaining_count": len(grading_state["results"])
        })

    @app.before_request
    def set_test_user():
        g.user_id = 'test-teacher'

    return app.test_client()


# ===========================================================================
# TestGradingStatus
# ===========================================================================

class TestGradingStatus:
    """Tests for GET /api/status."""

    def test_status_returns_state_snapshot(self, app_client, mock_grading_state):
        """Status endpoint returns a JSON snapshot of grading state."""
        mock_grading_state["progress"] = 3
        mock_grading_state["total"] = 10
        mock_grading_state["current_file"] = "essay.docx"

        response = app_client.get('/api/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["progress"] == 3
        assert data["total"] == 10
        assert data["current_file"] == "essay.docx"

    def test_status_includes_pending_confirmations_count(self, app_client, mock_grading_state):
        """Status computes pending_confirmations from results with emails but no confirmation_sent."""
        mock_grading_state["results"] = [
            {"filename": "a.docx", "student_email": "alice@school.edu", "confirmation_sent": False},
            {"filename": "b.docx", "student_email": "bob@school.edu", "confirmation_sent": True},
            {"filename": "c.docx", "student_email": "carol@school.edu"},
        ]

        response = app_client.get('/api/status')
        data = json.loads(response.data)
        # alice (not sent) and carol (no confirmation_sent key) should be pending
        assert data["pending_confirmations"] == 2

    def test_status_with_results_populated(self, app_client, mock_grading_state):
        """Status includes the results array when populated."""
        mock_grading_state["results"] = [
            {"filename": "test1.docx", "score": 85},
            {"filename": "test2.docx", "score": 92},
        ]

        response = app_client.get('/api/status')
        data = json.loads(response.data)
        assert len(data["results"]) == 2
        assert data["results"][0]["score"] == 85

    def test_status_includes_is_running_flag(self, app_client, mock_grading_state):
        """Status reflects the is_running flag."""
        mock_grading_state["is_running"] = True

        response = app_client.get('/api/status')
        data = json.loads(response.data)
        assert data["is_running"] is True


# ===========================================================================
# TestStopGrading
# ===========================================================================

class TestStopGrading:
    """Tests for POST /api/stop-grading."""

    def test_stop_sets_stop_requested_when_running(self, app_client, mock_grading_state):
        """When grading is running, stop sets stop_requested and returns stopped=True."""
        mock_grading_state["is_running"] = True

        response = app_client.post('/api/stop-grading')
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data["stopped"] is True
        assert mock_grading_state["stop_requested"] is True

    def test_stop_returns_false_when_not_running(self, app_client, mock_grading_state):
        """When grading is not running, returns stopped=False."""
        mock_grading_state["is_running"] = False

        response = app_client.post('/api/stop-grading')
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data["stopped"] is False
        assert mock_grading_state["stop_requested"] is False

    def test_stop_appends_to_log(self, app_client, mock_grading_state):
        """Stopping grading appends log messages about saving progress."""
        mock_grading_state["is_running"] = True
        mock_grading_state["log"] = ["Grading started"]

        app_client.post('/api/stop-grading')

        assert len(mock_grading_state["log"]) > 1
        assert "Stop requested" in mock_grading_state["log"][-1]


# ===========================================================================
# TestClearResults
# ===========================================================================

class TestClearResults:
    """Tests for POST /api/clear-results."""

    def test_clear_all_results_no_filter(self, app_client, mock_grading_state):
        """Without filenames filter, clears all results and resets log/complete."""
        mock_grading_state["results"] = [
            {"filename": "a.docx", "score": 80},
            {"filename": "b.docx", "score": 90},
        ]
        mock_grading_state["log"] = ["Some log entry"]
        mock_grading_state["complete"] = True

        response = app_client.post(
            '/api/clear-results',
            data=json.dumps({}),
            content_type='application/json'
        )
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data["status"] == "cleared"
        assert data["cleared_count"] == 2
        assert mock_grading_state["results"] == []
        assert mock_grading_state["log"] == []
        assert mock_grading_state["complete"] is False

    def test_clear_only_matching_filenames(self, app_client, mock_grading_state):
        """With filenames filter, only removes matching results."""
        mock_grading_state["results"] = [
            {"filename": "a.docx", "score": 80},
            {"filename": "b.docx", "score": 90},
            {"filename": "c.docx", "score": 70},
        ]

        response = app_client.post(
            '/api/clear-results',
            data=json.dumps({"filenames": ["a.docx", "c.docx"]}),
            content_type='application/json'
        )
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data["cleared_count"] == 2
        assert len(mock_grading_state["results"]) == 1
        assert mock_grading_state["results"][0]["filename"] == "b.docx"

    def test_clear_returns_400_when_grading_running(self, app_client, mock_grading_state):
        """Cannot clear results while grading is in progress."""
        mock_grading_state["is_running"] = True

        response = app_client.post(
            '/api/clear-results',
            data=json.dumps({}),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "grading is in progress" in data["error"].lower()

    def test_clear_handles_empty_results(self, app_client, mock_grading_state):
        """Clearing when results are already empty returns cleared_count=0."""
        mock_grading_state["results"] = []

        response = app_client.post(
            '/api/clear-results',
            data=json.dumps({}),
            content_type='application/json'
        )
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data["cleared_count"] == 0


# ===========================================================================
# TestUpdateApproval
# ===========================================================================

class TestUpdateApproval:
    """Tests for POST /api/update-approval."""

    def test_valid_approval_update(self, app_full_client, mock_grading_state):
        """Successfully updates approval status and returns 200."""
        mock_grading_state["results"] = [
            {"filename": "essay1.docx", "score": 88, "email_approval": "pending"},
        ]

        response = app_full_client.post(
            '/api/update-approval',
            data=json.dumps({"filename": "essay1.docx", "approval": "approved"}),
            content_type='application/json'
        )
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data["status"] == "updated"
        assert data["approval"] == "approved"

    def test_missing_filename_returns_400(self, app_full_client, mock_grading_state):
        """Missing filename in request body returns 400."""
        response = app_full_client.post(
            '/api/update-approval',
            data=json.dumps({"approval": "approved"}),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "filename" in data["error"].lower()

    def test_unknown_filename_returns_404(self, app_full_client, mock_grading_state):
        """Filename not found in results returns 404."""
        mock_grading_state["results"] = [
            {"filename": "essay1.docx", "score": 88},
        ]

        response = app_full_client.post(
            '/api/update-approval',
            data=json.dumps({"filename": "nonexistent.docx", "approval": "approved"}),
            content_type='application/json'
        )

        assert response.status_code == 404

    def test_updates_approved_field_on_result(self, app_full_client, mock_grading_state):
        """The email_approval field is set on the matching result object."""
        mock_grading_state["results"] = [
            {"filename": "hw1.docx", "score": 75, "email_approval": "pending"},
            {"filename": "hw2.docx", "score": 92, "email_approval": "pending"},
        ]

        app_full_client.post(
            '/api/update-approval',
            data=json.dumps({"filename": "hw2.docx", "approval": "rejected"}),
            content_type='application/json'
        )

        # hw2 updated, hw1 unchanged
        assert mock_grading_state["results"][0]["email_approval"] == "pending"
        assert mock_grading_state["results"][1]["email_approval"] == "rejected"

    def test_graded_at_disambiguation(self, app_full_client, mock_grading_state):
        """When graded_at is provided, prefers exact match over first-found."""
        mock_grading_state["results"] = [
            {"filename": "essay.docx", "graded_at": "2025-01-01T10:00:00", "email_approval": "pending"},
            {"filename": "essay.docx", "graded_at": "2025-01-02T10:00:00", "email_approval": "pending"},
        ]

        app_full_client.post(
            '/api/update-approval',
            data=json.dumps({
                "filename": "essay.docx",
                "approval": "approved",
                "graded_at": "2025-01-02T10:00:00"
            }),
            content_type='application/json'
        )

        # First result (Jan 1) should remain pending, second (Jan 2) should be approved
        assert mock_grading_state["results"][0]["email_approval"] == "pending"
        assert mock_grading_state["results"][1]["email_approval"] == "approved"

    def test_triggers_save_results(self, app_full_client, mock_grading_state):
        """Successful approval update triggers a save_results call."""
        mock_grading_state["results"] = [
            {"filename": "paper.docx", "score": 95},
        ]

        # Access the app through the client
        app = app_full_client.application
        app._save_results_calls.clear()

        app_full_client.post(
            '/api/update-approval',
            data=json.dumps({"filename": "paper.docx", "approval": "approved"}),
            content_type='application/json'
        )

        assert len(app._save_results_calls) == 1


# ===========================================================================
# TestUpdateApprovalsBulk
# ===========================================================================

class TestUpdateApprovalsBulk:
    """Tests for POST /api/update-approvals-bulk."""

    def test_multi_update_returns_correct_count(self, app_full_client, mock_grading_state):
        """Bulk update returns the number of results actually updated."""
        mock_grading_state["results"] = [
            {"filename": "a.docx", "email_approval": "pending"},
            {"filename": "b.docx", "email_approval": "pending"},
            {"filename": "c.docx", "email_approval": "pending"},
        ]

        response = app_full_client.post(
            '/api/update-approvals-bulk',
            data=json.dumps({
                "approvals": {"a.docx": "approved", "c.docx": "rejected"}
            }),
            content_type='application/json'
        )
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data["count"] == 2
        assert mock_grading_state["results"][0]["email_approval"] == "approved"
        assert mock_grading_state["results"][1]["email_approval"] == "pending"
        assert mock_grading_state["results"][2]["email_approval"] == "rejected"

    def test_400_on_empty_approvals(self, app_full_client, mock_grading_state):
        """Empty approvals dict returns 400."""
        response = app_full_client.post(
            '/api/update-approvals-bulk',
            data=json.dumps({"approvals": {}}),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "no approvals" in data["error"].lower()

    def test_400_on_missing_approvals_field(self, app_full_client, mock_grading_state):
        """Missing approvals field in request body returns 400."""
        response = app_full_client.post(
            '/api/update-approvals-bulk',
            data=json.dumps({"something_else": True}),
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_skips_unknown_filenames(self, app_full_client, mock_grading_state):
        """Unknown filenames in approvals dict are silently skipped."""
        mock_grading_state["results"] = [
            {"filename": "a.docx", "email_approval": "pending"},
        ]

        response = app_full_client.post(
            '/api/update-approvals-bulk',
            data=json.dumps({
                "approvals": {
                    "a.docx": "approved",
                    "nonexistent.docx": "approved",
                    "also_missing.docx": "rejected",
                }
            }),
            content_type='application/json'
        )
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data["count"] == 1
        assert mock_grading_state["results"][0]["email_approval"] == "approved"


# ===========================================================================
# TestDeleteResult
# ===========================================================================

class TestDeleteResult:
    """Tests for POST /api/delete-result."""

    def test_removes_result_and_saves(self, app_full_client, mock_grading_state):
        """Deleting a result removes it from state and triggers save."""
        mock_grading_state["results"] = [
            {"filename": "keep.docx", "score": 90},
            {"filename": "remove.docx", "score": 60},
        ]

        app = app_full_client.application
        app._save_results_calls.clear()

        response = app_full_client.post(
            '/api/delete-result',
            data=json.dumps({"filename": "remove.docx"}),
            content_type='application/json'
        )
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data["status"] == "deleted"
        assert data["remaining_count"] == 1
        assert len(mock_grading_state["results"]) == 1
        assert mock_grading_state["results"][0]["filename"] == "keep.docx"
        assert len(app._save_results_calls) == 1

    def test_returns_already_deleted_when_not_found(self, app_full_client, mock_grading_state):
        """Deleting a non-existent filename returns already_deleted status."""
        mock_grading_state["results"] = [
            {"filename": "existing.docx", "score": 85},
        ]

        response = app_full_client.post(
            '/api/delete-result',
            data=json.dumps({"filename": "ghost.docx"}),
            content_type='application/json'
        )
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data["status"] == "already_deleted"
        assert len(mock_grading_state["results"]) == 1
