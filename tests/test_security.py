"""Security tests — path traversal, input validation."""
import pytest
import re


class TestPathTraversalProtection:
    """Verify file endpoints reject path traversal attempts."""

    def test_assignment_name_rejects_traversal(self):
        """The regex validation should reject '../' in assignment names."""
        pattern = r'^[\w\s\-\.]+$'
        assert re.match(pattern, 'Valid Assignment Name') is not None
        assert re.match(pattern, '../../etc/passwd') is None
        assert re.match(pattern, 'test/../../../secret') is None
        assert re.match(pattern, 'normal-name_v2.1') is not None

    def test_secure_filename_strips_traversal(self):
        """werkzeug.utils.secure_filename should strip directory separators."""
        from werkzeug.utils import secure_filename
        assert secure_filename('../../../etc/passwd') == 'etc_passwd'
        assert secure_filename('normal_file.pdf') == 'normal_file.pdf'
        assert secure_filename('') == ''
        assert secure_filename('file with spaces.docx') == 'file_with_spaces.docx'


class TestPublicPrefixes:
    """Verify auth bypass is properly scoped."""

    def test_student_join_is_public(self):
        from backend.auth import is_public_route
        assert is_public_route('/api/student/join/ABC123') is True

    def test_student_submit_is_public(self):
        from backend.auth import is_public_route
        assert is_public_route('/api/student/submit/ABC123') is True

    def test_student_login_is_public(self):
        from backend.auth import is_public_route
        assert is_public_route('/api/student/login') is True

    def test_student_session_is_public(self):
        from backend.auth import is_public_route
        assert is_public_route('/api/student/session') is True

    def test_clever_callback_is_public(self):
        from backend.auth import is_public_route
        assert is_public_route('/api/clever/callback') is True

    def test_teacher_assessments_is_NOT_public(self):
        """Teacher endpoints should NOT be in the public list."""
        from backend.auth import is_public_route
        assert is_public_route('/api/teacher/assessments') is False

    def test_publish_assessment_is_NOT_public(self):
        from backend.auth import is_public_route
        assert is_public_route('/api/publish-assessment') is False

    def test_save_assessment_is_NOT_public(self):
        from backend.auth import is_public_route
        assert is_public_route('/api/save-assessment') is False

    def test_grade_endpoint_is_NOT_public(self):
        from backend.auth import is_public_route
        assert is_public_route('/api/grade') is False

    def test_settings_is_NOT_public(self):
        from backend.auth import is_public_route
        assert is_public_route('/api/load-rubric') is False

    def test_analytics_is_NOT_public(self):
        from backend.auth import is_public_route
        assert is_public_route('/api/analytics/student-progress') is False


class TestRequireTeacher:
    """Test the shared require_teacher decorator."""

    def test_returns_401_without_user_id(self):
        from backend.utils.auth_decorators import require_teacher
        from flask import Flask, g

        app = Flask(__name__)

        @app.route('/test')
        @require_teacher
        def test_route():
            return 'OK'

        with app.test_request_context('/test'):
            # Don't set g.user_id
            response = test_route()
            assert response[1] == 401

    def test_sets_teacher_id_with_user_id(self):
        from backend.utils.auth_decorators import require_teacher
        from flask import Flask, g

        app = Flask(__name__)

        @app.route('/test')
        @require_teacher
        def test_route():
            return g.teacher_id

        with app.test_request_context('/test'):
            g.user_id = 'teacher-123'
            result = test_route()
            assert result == 'teacher-123'
