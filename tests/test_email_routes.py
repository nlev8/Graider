"""Integration tests for email API routes."""
import json
import pytest
import sys
import os
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tests.conftest_routes import client, flask_app, mock_grading_state, grading_lock
from flask import Flask, g, request, jsonify


# ═══════════════════════════════════════════════════════════════
# Helper fixture: minimal Flask app with just the email blueprint
# and app.py approval routes manually registered with mocked state.
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def email_client(mock_grading_state, grading_lock):
    """Flask test client with email blueprint + approval routes."""
    app = Flask(__name__)
    app.config['TESTING'] = True

    _state = mock_grading_state

    def get_state(teacher_id='local-dev'):
        return _state

    def get_lock(teacher_id='local-dev'):
        return grading_lock

    # Register email blueprint
    from backend.routes.email_routes import email_bp
    app.register_blueprint(email_bp)

    # Track save calls
    app._save_results_calls = []

    # Manually register approval routes (these live in app.py, not a blueprint)
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

    @app.before_request
    def set_test_user():
        g.user_id = 'test-teacher'

    return app.test_client()


# ═══════════════════════════════════════════════════════════════
# TestSendEmails (5 tests)
# ═══════════════════════════════════════════════════════════════

class TestSendEmails:
    """Tests for POST /api/send-emails."""

    @patch('backend.routes.email_routes.GraiderEmailer', create=True)
    def test_no_resend_available_returns_error(self, MockEmailer, client):
        """When Resend is not configured, return an error message."""
        mock_instance = MagicMock()
        mock_instance.resend_available = False
        MockEmailer.return_value = mock_instance

        with patch('backend.services.email_service.GraiderEmailer', MockEmailer, create=True):
            resp = client.post('/api/send-emails', json={
                'results': [{'student_email': 'a@b.com', 'student_name': 'Test'}]
            })

        data = resp.get_json()
        assert 'error' in data
        assert 'not configured' in data['error'].lower() or 'email' in data['error'].lower()

    @patch('backend.services.email_service.GraiderEmailer', create=True)
    def test_no_results_returns_error(self, MockEmailer):
        """Empty results list should return error."""
        mock_instance = MagicMock()
        mock_instance.resend_available = True
        mock_instance.config = {}
        MockEmailer.return_value = mock_instance

        app = Flask(__name__)
        app.config['TESTING'] = True
        from backend.routes.email_routes import email_bp
        # Re-register blueprint on a fresh app
        app.register_blueprint(email_bp)

        @app.before_request
        def set_user():
            g.user_id = 'test'

        with app.test_client() as c:
            resp = c.post('/api/send-emails', json={'results': []})

        data = resp.get_json()
        assert 'error' in data
        assert 'no results' in data['error'].lower()

    @patch('backend.services.email_service.GraiderEmailer', create=True)
    def test_valid_results_calls_emailer(self, MockEmailer):
        """Valid results with student emails should call send_email."""
        mock_instance = MagicMock()
        mock_instance.resend_available = True
        mock_instance.config = {'teacher_name': 'Mr. Test', 'teacher_email': 'teacher@test.com'}
        mock_instance.send_email.return_value = True
        MockEmailer.return_value = mock_instance

        app = Flask(__name__)
        app.config['TESTING'] = True
        from backend.routes.email_routes import email_bp
        app.register_blueprint(email_bp)

        @app.before_request
        def set_user():
            g.user_id = 'test'

        with app.test_client() as c:
            resp = c.post('/api/send-emails', json={
                'results': [{
                    'student_email': 'student@school.edu',
                    'student_name': 'Jane Doe',
                    'score': 85,
                    'letter_grade': 'B',
                    'feedback': 'Great work!',
                    'assignment': 'Chapter 5 Quiz'
                }],
                'teacher_email': 'teacher@test.com',
                'teacher_name': 'Mr. Test',
            })

        data = resp.get_json()
        assert data.get('sent') == 1
        assert data.get('failed') == 0
        assert data.get('total') == 1
        mock_instance.send_email.assert_called_once()
        call_args = mock_instance.send_email.call_args
        assert call_args[0][0] == 'student@school.edu'  # to email
        assert 'Jane' in call_args[0][1]  # first name

    @patch('backend.services.email_service.GraiderEmailer', create=True)
    def test_teacher_info_passed_through(self, MockEmailer):
        """Teacher name, email, and signature should appear in the email."""
        mock_instance = MagicMock()
        mock_instance.resend_available = True
        mock_instance.config = {}
        mock_instance.send_email.return_value = True
        MockEmailer.return_value = mock_instance

        app = Flask(__name__)
        app.config['TESTING'] = True
        from backend.routes.email_routes import email_bp
        app.register_blueprint(email_bp)

        @app.before_request
        def set_user():
            g.user_id = 'test'

        with app.test_client() as c:
            resp = c.post('/api/send-emails', json={
                'results': [{
                    'student_email': 'student@school.edu',
                    'student_name': 'Bob Smith',
                    'score': 90,
                    'letter_grade': 'A',
                    'feedback': 'Excellent!',
                    'assignment': 'Essay'
                }],
                'teacher_email': 'mrs.jones@school.edu',
                'teacher_name': 'Mrs. Jones',
                'email_signature': 'Best regards,\nMrs. Jones\nRoom 204',
            })

        data = resp.get_json()
        assert data.get('sent') == 1
        # Verify reply_to was teacher email
        call_args = mock_instance.send_email.call_args
        assert call_args[0][4] == 'mrs.jones@school.edu'  # reply_to
        # Verify body contains signature
        body = call_args[0][3]
        assert 'Best regards' in body

    @patch('backend.services.email_service.GraiderEmailer', create=True)
    def test_results_grouped_by_student_email(self, MockEmailer):
        """Multiple results for same student email are grouped into one email."""
        mock_instance = MagicMock()
        mock_instance.resend_available = True
        mock_instance.config = {'teacher_name': 'Teacher'}
        mock_instance.send_email.return_value = True
        MockEmailer.return_value = mock_instance

        app = Flask(__name__)
        app.config['TESTING'] = True
        from backend.routes.email_routes import email_bp
        app.register_blueprint(email_bp)

        @app.before_request
        def set_user():
            g.user_id = 'test'

        with app.test_client() as c:
            resp = c.post('/api/send-emails', json={
                'results': [
                    {
                        'student_email': 'alice@school.edu',
                        'student_name': 'Alice Wonderland',
                        'score': 80,
                        'letter_grade': 'B',
                        'feedback': 'Good job',
                        'assignment': 'Quiz 1',
                    },
                    {
                        'student_email': 'alice@school.edu',
                        'student_name': 'Alice Wonderland',
                        'score': 95,
                        'letter_grade': 'A',
                        'feedback': 'Excellent',
                        'assignment': 'Quiz 2',
                    },
                    {
                        'student_email': 'bob@school.edu',
                        'student_name': 'Bob Builder',
                        'score': 70,
                        'letter_grade': 'C',
                        'feedback': 'Needs improvement',
                        'assignment': 'Quiz 1',
                    },
                ],
            })

        data = resp.get_json()
        # 2 unique emails: alice and bob
        assert data.get('total') == 2
        assert data.get('sent') == 2
        # send_email should be called twice (once per unique email)
        assert mock_instance.send_email.call_count == 2


# ═══════════════════════════════════════════════════════════════
# TestConfirmation (4 tests) — mark-confirmations-sent-file endpoint
# ═══════════════════════════════════════════════════════════════

class TestConfirmation:
    """Tests for POST /api/mark-confirmations-sent-file."""

    @staticmethod
    def _setup_grading_module(mock_state, lock):
        """Inject grading_state and grading_lock onto the grading_routes module.

        The email routes use a deferred import:
            from backend.routes.grading_routes import grading_state, grading_lock
        But those names are local variables inside each route function, not
        module-level attributes.  We monkey-patch them onto the module so the
        import succeeds in tests.
        """
        import backend.routes.grading_routes as gr_mod
        gr_mod.grading_state = mock_state
        gr_mod.grading_lock = lock

    @staticmethod
    def _teardown_grading_module():
        import backend.routes.grading_routes as gr_mod
        for attr in ('grading_state', 'grading_lock'):
            if hasattr(gr_mod, attr):
                delattr(gr_mod, attr)

    def test_valid_confirmation_marks_result(self, mock_grading_state, grading_lock, tmp_path):
        """Marking a filename as confirmed updates grading_state results."""
        mock_grading_state["results"] = [
            {"filename": "student1_essay.docx", "student_name": "Student One", "confirmation_sent": False},
            {"filename": "student2_essay.docx", "student_name": "Student Two", "confirmation_sent": False},
        ]

        self._setup_grading_module(mock_grading_state, grading_lock)
        try:
            app = Flask(__name__)
            app.config['TESTING'] = True

            from backend.routes.email_routes import email_bp
            app.register_blueprint(email_bp)

            @app.before_request
            def set_user():
                g.user_id = 'test'

            with patch('backend.routes.email_routes.CONFIRMATIONS_FILE', str(tmp_path / 'confirmations.json')), \
                 patch('backend.routes.email_routes.RESULTS_FILE', str(tmp_path / 'results.json')):
                with app.test_client() as c:
                    resp = c.post('/api/mark-confirmations-sent-file', json={
                        'filenames': ['student1_essay.docx']
                    })

            data = resp.get_json()
            assert data.get('status') == 'ok'
            assert data.get('updated') == 1
            assert mock_grading_state["results"][0]["confirmation_sent"] is True
            assert mock_grading_state["results"][1].get("confirmation_sent") is False
        finally:
            self._teardown_grading_module()

    def test_nonexistent_filename_returns_zero_updated(self, mock_grading_state, grading_lock, tmp_path):
        """Marking a filename not in results returns updated=0 but still persists."""
        mock_grading_state["results"] = [
            {"filename": "student1_essay.docx", "student_name": "Student One"},
        ]

        self._setup_grading_module(mock_grading_state, grading_lock)
        try:
            app = Flask(__name__)
            app.config['TESTING'] = True
            from backend.routes.email_routes import email_bp
            app.register_blueprint(email_bp)

            @app.before_request
            def set_user():
                g.user_id = 'test'

            with patch('backend.routes.email_routes.CONFIRMATIONS_FILE', str(tmp_path / 'confirmations.json')), \
                 patch('backend.routes.email_routes.RESULTS_FILE', str(tmp_path / 'results.json')):
                with app.test_client() as c:
                    resp = c.post('/api/mark-confirmations-sent-file', json={
                        'filenames': ['nonexistent_file.docx']
                    })

            data = resp.get_json()
            assert data.get('status') == 'ok'
            assert data.get('updated') == 0
            # Confirmation still recorded in the confirmations file
            assert data.get('total_confirmed') >= 1
        finally:
            self._teardown_grading_module()

    def test_confirmation_idempotent(self, mock_grading_state, grading_lock, tmp_path):
        """Marking the same file twice is idempotent."""
        mock_grading_state["results"] = [
            {"filename": "essay.docx", "student_name": "Student", "confirmation_sent": True},
        ]

        self._setup_grading_module(mock_grading_state, grading_lock)
        try:
            app = Flask(__name__)
            app.config['TESTING'] = True
            from backend.routes.email_routes import email_bp
            app.register_blueprint(email_bp)

            @app.before_request
            def set_user():
                g.user_id = 'test'

            confirmations_file = str(tmp_path / 'confirmations.json')
            # Pre-populate confirmations file
            with open(confirmations_file, 'w') as f:
                json.dump(['essay.docx'], f)

            with patch('backend.routes.email_routes.CONFIRMATIONS_FILE', confirmations_file), \
                 patch('backend.routes.email_routes.RESULTS_FILE', str(tmp_path / 'results.json')):
                with app.test_client() as c:
                    resp = c.post('/api/mark-confirmations-sent-file', json={
                        'filenames': ['essay.docx']
                    })

            data = resp.get_json()
            assert data.get('status') == 'ok'
            # total_confirmed should still be 1, not 2
            assert data.get('total_confirmed') == 1
        finally:
            self._teardown_grading_module()

    def test_no_filenames_returns_400(self, mock_grading_state, grading_lock, tmp_path):
        """Empty filenames list returns 400 error."""
        app = Flask(__name__)
        app.config['TESTING'] = True
        from backend.routes.email_routes import email_bp
        app.register_blueprint(email_bp)

        @app.before_request
        def set_user():
            g.user_id = 'test'

        with app.test_client() as c:
            resp = c.post('/api/mark-confirmations-sent-file', json={
                'filenames': []
            })

        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data


# ═══════════════════════════════════════════════════════════════
# TestApproval (3 tests) — update-approval and bulk approval
# ═══════════════════════════════════════════════════════════════

class TestApproval:
    """Tests for POST /api/update-approval and /api/update-approvals-bulk."""

    def test_approve_flow_returns_success(self, mock_grading_state, email_client):
        """Approving a result sets email_approval to 'approved'."""
        mock_grading_state["results"] = [
            {"filename": "essay.docx", "student_name": "Student One", "email_approval": "pending"},
        ]

        resp = email_client.post('/api/update-approval', json={
            'filename': 'essay.docx',
            'approval': 'approved',
        })

        data = resp.get_json()
        assert data.get('status') == 'updated'
        assert data.get('approval') == 'approved'
        assert mock_grading_state["results"][0]["email_approval"] == "approved"

    def test_reject_flow_returns_success(self, mock_grading_state, email_client):
        """Rejecting a result sets email_approval to 'rejected'."""
        mock_grading_state["results"] = [
            {"filename": "quiz.docx", "student_name": "Student Two", "email_approval": "pending"},
        ]

        resp = email_client.post('/api/update-approval', json={
            'filename': 'quiz.docx',
            'approval': 'rejected',
        })

        data = resp.get_json()
        assert data.get('status') == 'updated'
        assert data.get('approval') == 'rejected'
        assert mock_grading_state["results"][0]["email_approval"] == "rejected"

    def test_nonexistent_result_returns_404(self, mock_grading_state, email_client):
        """Approving a non-existent result returns 404."""
        mock_grading_state["results"] = []

        resp = email_client.post('/api/update-approval', json={
            'filename': 'missing.docx',
            'approval': 'approved',
        })

        assert resp.status_code == 404
        data = resp.get_json()
        assert 'error' in data
        assert 'not found' in data['error'].lower()
