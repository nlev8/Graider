"""
FERPA audit-log coverage tests.

Verifies that the high-risk endpoints instrumented in the
audit-log-coverage PR (email send, grade edit, SIS exports) actually
emit an audit_log() call with a recognizable action tag.

These are NOT testing the audit_log function itself (covered elsewhere)
— only that the instrumented call sites still fire after refactors.
"""
from unittest.mock import patch, MagicMock

from flask import Flask, g


def _make_app(*blueprints):
    app = Flask(__name__)
    app.config['TESTING'] = True
    for bp in blueprints:
        app.register_blueprint(bp)

    @app.before_request
    def _set_user():
        g.user_id = 'teacher-1'

    return app


class TestEmailAuditLog:
    @patch('backend.routes.email_routes.audit_log')
    @patch('backend.services.email_service.GraiderEmailer', create=True)
    def test_send_emails_logs_audit(self, MockEmailer, mock_audit):
        mock_instance = MagicMock()
        mock_instance.resend_available = True
        mock_instance.config = {'teacher_name': 'Mr. T', 'teacher_email': 't@s.edu'}
        mock_instance.send_email.return_value = True
        MockEmailer.return_value = mock_instance

        from backend.routes.email_routes import email_bp
        app = _make_app(email_bp)

        with app.test_client() as c:
            c.post('/api/send-emails', json={
                'results': [{
                    'student_email': 's@s.edu',
                    'student_name': 'Jane Doe',
                    'score': 90,
                    'letter_grade': 'A',
                    'feedback': 'Good',
                    'assignment': 'Q1',
                }],
                'teacher_email': 't@s.edu',
                'teacher_name': 'Mr. T',
            })

        # audit_log was called with EMAIL_SEND_GRADES action tag
        actions = [call.args[0] for call in mock_audit.call_args_list]
        assert 'EMAIL_SEND_GRADES' in actions

    @patch('backend.routes.email_routes.audit_log')
    @patch('backend.services.email_service.GraiderEmailer', create=True)
    def test_test_email_logs_audit(self, MockEmailer, mock_audit):
        mock_instance = MagicMock()
        mock_instance.test_connection.return_value = True
        MockEmailer.return_value = mock_instance

        from backend.routes.email_routes import email_bp
        app = _make_app(email_bp)

        with app.test_client() as c:
            c.post('/api/test-email', json={'email': 'x@x.com'})

        actions = [call.args[0] for call in mock_audit.call_args_list]
        assert 'EMAIL_TEST_SEND' in actions


class TestGradingAuditLog:
    @patch('backend.routes.grading_routes.audit_log')
    def test_update_result_score_edit_logs_audit(self, mock_audit):
        from backend.routes.grading_routes import grading_bp, init_grading_routes

        state = {
            'is_running': False,
            'results': [{'filename': 'q1.pdf', 'score': 80, 'feedback': 'ok'}],
            'log': [],
        }
        import threading
        lock = threading.Lock()
        init_grading_routes(
            get_state_fn=lambda _t: state,
            thread_fn=lambda *a, **k: None,
            reset_fn=lambda: None,
            get_lock_fn=lambda _t: lock,
        )

        app = _make_app(grading_bp)
        with app.test_client() as c:
            c.post('/api/update-result', json={
                'filename': 'q1.pdf',
                'score': 95,
                'feedback': 'great',
            })

        actions = [call.args[0] for call in mock_audit.call_args_list]
        assert 'GRADE_EDIT' in actions

    @patch('backend.routes.grading_routes.audit_log')
    def test_update_result_verified_only_does_NOT_log(self, mock_audit):
        """Setting just `verified` (no PII change) should not emit a GRADE_EDIT audit entry."""
        from backend.routes.grading_routes import grading_bp, init_grading_routes

        state = {
            'is_running': False,
            'results': [{'filename': 'q1.pdf', 'score': 80, 'feedback': 'ok'}],
            'log': [],
        }
        import threading
        lock = threading.Lock()
        init_grading_routes(
            get_state_fn=lambda _t: state,
            thread_fn=lambda *a, **k: None,
            reset_fn=lambda: None,
            get_lock_fn=lambda _t: lock,
        )

        app = _make_app(grading_bp)
        with app.test_client() as c:
            c.post('/api/update-result', json={
                'filename': 'q1.pdf',
                'verified': True,
            })

        actions = [call.args[0] for call in mock_audit.call_args_list]
        assert 'GRADE_EDIT' not in actions
