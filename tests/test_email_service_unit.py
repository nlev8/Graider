"""
Unit tests for backend/services/email_service.py.

Audit MAJOR #4 sprint follow-up to PR #262. Targets the 117 uncovered
LOC in email_service.py (13% baseline).

Strategy:
- HOME redirect from `isolated_dirs` fixture so `~/.graider_email_config.json`
  writes don't pollute the user's real home.
- Patch `resend.Emails.send` to control responses without real API calls.
- Patch `RESEND_AVAILABLE` and the api_key env var to exercise both
  configured / unconfigured branches.

Pattern matches PR #261 / #262 (HOME redirect + patch.object).
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def isolated_dirs(tmp_path, monkeypatch):
    """Redirect HOME so config writes go to tmp_path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Clear any RESEND_API_KEY env var so tests start from a clean state
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("RESEND_FROM_EMAIL", raising=False)
    return tmp_path


# ──────────────────────────────────────────────────────────────────
# __init__ + _init_resend
# ──────────────────────────────────────────────────────────────────


class TestInit:
    def test_resend_unavailable_when_package_missing(self, isolated_dirs):
        """When `resend` package isn't installed, _init_resend sets
        resend_available=False (production bug previously: this attr was
        never set, causing AttributeError downstream)."""
        from backend.services.email_service import GraiderEmailer
        with patch("backend.services.email_service.RESEND_AVAILABLE", False):
            emailer = GraiderEmailer(config_path=str(isolated_dirs / "cfg.json"))
        # The fix (PR #263 in scope per Rule #11): attr is always set
        # in _init_resend before any early return.
        assert hasattr(emailer, "resend_available")
        assert emailer.resend_available is False

    def test_resend_unavailable_when_no_api_key(self, isolated_dirs, monkeypatch):
        """resend installed but no RESEND_API_KEY → resend_available=False."""
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        from backend.services.email_service import GraiderEmailer
        # Block .env file fallback so we test the no-key path deterministically
        with patch("backend.services.email_service.RESEND_AVAILABLE", True), \
             patch("backend.services.email_service.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            mock_path.return_value.parent.parent.parent.__truediv__ = (
                lambda self, x: MagicMock(exists=lambda: False)
            )
            emailer = GraiderEmailer(config_path=str(isolated_dirs / "cfg.json"))
        assert emailer.resend_available is False

    def test_api_key_from_env(self, isolated_dirs, monkeypatch):
        """API key in env → resend_available=True, from_email defaults set."""
        monkeypatch.setenv("RESEND_API_KEY", "test-key-from-env")
        from backend.services.email_service import GraiderEmailer
        with patch("backend.services.email_service.RESEND_AVAILABLE", True), \
             patch("backend.services.email_service.resend") as mock_resend:
            emailer = GraiderEmailer(config_path=str(isolated_dirs / "cfg.json"))
        assert emailer.resend_available is True
        assert emailer.from_email == "Graider <noreply@graider.live>"
        # API key set on the resend module
        assert mock_resend.api_key == "test-key-from-env"

    def test_custom_from_email_via_env(self, isolated_dirs, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", "k")
        monkeypatch.setenv("RESEND_FROM_EMAIL", "Custom <c@example.com>")
        from backend.services.email_service import GraiderEmailer
        with patch("backend.services.email_service.RESEND_AVAILABLE", True), \
             patch("backend.services.email_service.resend"):
            emailer = GraiderEmailer(config_path=str(isolated_dirs / "cfg.json"))
        assert emailer.from_email == "Custom <c@example.com>"


# ──────────────────────────────────────────────────────────────────
# _load_config + save_config
# ──────────────────────────────────────────────────────────────────


class TestLoadAndSaveConfig:
    def test_no_file_returns_empty_dict(self, isolated_dirs, monkeypatch):
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        from backend.services.email_service import GraiderEmailer
        with patch("backend.services.email_service.RESEND_AVAILABLE", False):
            emailer = GraiderEmailer(config_path=str(isolated_dirs / "missing.json"))
        assert emailer.config == {}

    def test_reads_existing_config(self, isolated_dirs, monkeypatch):
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        config_path = isolated_dirs / "cfg.json"
        with open(config_path, 'w') as f:
            json.dump({"teacher_name": "Ms. Alice", "teacher_email": "a@x.com"}, f)
        from backend.services.email_service import GraiderEmailer
        with patch("backend.services.email_service.RESEND_AVAILABLE", False):
            emailer = GraiderEmailer(config_path=str(config_path))
        assert emailer.config == {"teacher_name": "Ms. Alice", "teacher_email": "a@x.com"}

    def test_save_writes_json_with_restricted_perms(self, isolated_dirs, monkeypatch):
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        config_path = isolated_dirs / "saved.json"
        from backend.services.email_service import GraiderEmailer
        with patch("backend.services.email_service.RESEND_AVAILABLE", False):
            emailer = GraiderEmailer(config_path=str(config_path))
        emailer.save_config("Ms. Bob", "b@x.com")

        # File contents
        with open(config_path) as f:
            data = json.load(f)
        assert data == {"teacher_name": "Ms. Bob", "teacher_email": "b@x.com"}
        # In-memory config also updated
        assert emailer.config["teacher_name"] == "Ms. Bob"
        # On Unix, file mode is 0o600 (read+write only for owner)
        if os.name != 'nt':
            mode = os.stat(config_path).st_mode & 0o777
            assert mode == 0o600

    def test_save_creates_parent_dirs(self, isolated_dirs, monkeypatch):
        """save_config makes the parent dir if missing."""
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        config_path = isolated_dirs / "nested" / "deep" / "cfg.json"
        from backend.services.email_service import GraiderEmailer
        with patch("backend.services.email_service.RESEND_AVAILABLE", False):
            emailer = GraiderEmailer(config_path=str(config_path))
        emailer.save_config("X", "y@x.com")
        assert os.path.exists(config_path)


# ──────────────────────────────────────────────────────────────────
# send_email
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def configured_emailer(isolated_dirs, monkeypatch):
    """Return a GraiderEmailer with resend_available=True (Resend mocked)."""
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    from backend.services.email_service import GraiderEmailer
    with patch("backend.services.email_service.RESEND_AVAILABLE", True), \
         patch("backend.services.email_service.resend"):
        emailer = GraiderEmailer(config_path=str(isolated_dirs / "cfg.json"))
    return emailer


class TestSendEmail:
    def test_returns_false_when_resend_package_missing(self, isolated_dirs, monkeypatch):
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        from backend.services.email_service import GraiderEmailer
        with patch("backend.services.email_service.RESEND_AVAILABLE", False):
            emailer = GraiderEmailer(config_path=str(isolated_dirs / "cfg.json"))
        result = emailer.send_email("a@x.com", "Alice", "Subj", "Body")
        assert result is False

    def test_returns_false_when_api_key_not_configured(self, isolated_dirs, monkeypatch):
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        from backend.services.email_service import GraiderEmailer
        with patch("backend.services.email_service.RESEND_AVAILABLE", True), \
             patch("backend.services.email_service.Path") as mock_path:
            # Block .env file fallback
            mock_path.return_value.exists.return_value = False
            mock_path.return_value.parent.parent.parent.__truediv__ = (
                lambda self, x: MagicMock(exists=lambda: False)
            )
            emailer = GraiderEmailer(config_path=str(isolated_dirs / "cfg.json"))
        # If by chance the test env has RESEND_API_KEY in a parent .env, this
        # test may not fail-close; assert on the path that's truly under our
        # control: explicitly clear resend_available.
        emailer.resend_available = False
        result = emailer.send_email("a@x.com", "Alice", "Subj", "Body")
        assert result is False

    def test_happy_path_returns_true(self, configured_emailer):
        emailer = configured_emailer
        with patch("backend.services.email_service.resend") as mock_resend:
            mock_resend.Emails.send.return_value = {"id": "re_xyz"}
            result = emailer.send_email("a@x.com", "Alice", "Subj", "Body")

        assert result is True
        # Verify resend.Emails.send was called with the right params shape
        params = mock_resend.Emails.send.call_args.args[0]
        assert params["to"] == ["a@x.com"]
        assert params["subject"] == "Subj"
        assert params["text"] == "Body"
        assert "from" in params

    def test_uses_explicit_reply_to_when_provided(self, configured_emailer):
        emailer = configured_emailer
        with patch("backend.services.email_service.resend") as mock_resend:
            mock_resend.Emails.send.return_value = {"id": "re_x"}
            emailer.send_email("a@x.com", "Alice", "Subj", "Body",
                               reply_to="teacher@school.edu")
        params = mock_resend.Emails.send.call_args.args[0]
        assert params["reply_to"] == "teacher@school.edu"

    def test_falls_back_to_config_teacher_email_for_reply_to(self, configured_emailer):
        emailer = configured_emailer
        emailer.config["teacher_email"] = "from-config@school.edu"
        with patch("backend.services.email_service.resend") as mock_resend:
            mock_resend.Emails.send.return_value = {"id": "re_x"}
            emailer.send_email("a@x.com", "Alice", "Subj", "Body")
        params = mock_resend.Emails.send.call_args.args[0]
        assert params["reply_to"] == "from-config@school.edu"

    def test_no_reply_to_when_neither_provided(self, configured_emailer):
        emailer = configured_emailer
        # No reply_to arg, no teacher_email in config
        emailer.config = {}
        with patch("backend.services.email_service.resend") as mock_resend:
            mock_resend.Emails.send.return_value = {"id": "re_x"}
            emailer.send_email("a@x.com", "Alice", "Subj", "Body")
        params = mock_resend.Emails.send.call_args.args[0]
        assert "reply_to" not in params

    def test_response_without_id_returns_false(self, configured_emailer):
        emailer = configured_emailer
        with patch("backend.services.email_service.resend") as mock_resend:
            mock_resend.Emails.send.return_value = {}  # no 'id'
            result = emailer.send_email("a@x.com", "Alice", "Subj", "Body")
        assert result is False

    def test_response_none_returns_false(self, configured_emailer):
        emailer = configured_emailer
        with patch("backend.services.email_service.resend") as mock_resend:
            mock_resend.Emails.send.return_value = None
            result = emailer.send_email("a@x.com", "Alice", "Subj", "Body")
        assert result is False

    def test_exception_returns_false(self, configured_emailer):
        emailer = configured_emailer
        with patch("backend.services.email_service.resend") as mock_resend:
            mock_resend.Emails.send.side_effect = RuntimeError("API error")
            result = emailer.send_email("a@x.com", "Alice", "Subj", "Body")
        assert result is False


# ──────────────────────────────────────────────────────────────────
# send_grade_email
# ──────────────────────────────────────────────────────────────────


class TestSendGradeEmail:
    def test_no_email_returns_false(self, configured_emailer):
        emailer = configured_emailer
        result = emailer.send_grade_email(
            student_info={"student_name": "Alice", "first_name": "Alice", "email": ""},
            grade_result={"score": 90, "letter_grade": "A", "feedback": "Good"},
            assignment_name="Quiz",
        )
        assert result is False

    def test_happy_path_passes_assembled_email_to_send_email(self, configured_emailer):
        emailer = configured_emailer
        emailer.config["teacher_name"] = "Ms. Smith"

        with patch.object(emailer, "send_email", return_value=True) as mock_send:
            result = emailer.send_grade_email(
                student_info={"student_name": "Alice", "first_name": "Alice",
                              "email": "alice@school.edu"},
                grade_result={"score": 85, "letter_grade": "B",
                              "feedback": "Good effort"},
                assignment_name="Unit 3 Quiz",
            )

        assert result is True
        # send_email called with the right args shape
        args = mock_send.call_args.args
        assert args[0] == "alice@school.edu"  # to
        assert args[1] == "Alice"  # first name
        assert "Unit 3 Quiz" in args[2]  # subject
        assert "B" in args[2]
        body = args[3]
        # Body has score + grade + feedback + teacher
        assert "85/100" in body
        assert "Good effort" in body
        assert "Ms. Smith" in body
        assert "graider.live" in body  # footer link

    def test_default_teacher_name_when_not_in_config(self, configured_emailer):
        emailer = configured_emailer
        emailer.config = {}  # no teacher_name
        with patch.object(emailer, "send_email", return_value=True) as mock_send:
            emailer.send_grade_email(
                student_info={"first_name": "Alice", "email": "a@x.com"},
                grade_result={"score": 90, "letter_grade": "A", "feedback": "x"},
                assignment_name="Q",
            )
        body = mock_send.call_args.args[3]
        assert "Your Teacher" in body

    def test_first_name_takes_first_word(self, configured_emailer):
        emailer = configured_emailer
        with patch.object(emailer, "send_email", return_value=True) as mock_send:
            emailer.send_grade_email(
                student_info={"first_name": "Alice Marie", "email": "a@x.com"},
                grade_result={"score": 80, "letter_grade": "B", "feedback": ""},
                assignment_name="X",
            )
        # "Alice Marie".split()[0] == "Alice"
        assert mock_send.call_args.args[1] == "Alice"

    def test_missing_feedback_uses_default(self, configured_emailer):
        emailer = configured_emailer
        with patch.object(emailer, "send_email", return_value=True) as mock_send:
            emailer.send_grade_email(
                student_info={"first_name": "Alice", "email": "a@x.com"},
                grade_result={"score": 90, "letter_grade": "A"},  # no feedback
                assignment_name="Q",
            )
        body = mock_send.call_args.args[3]
        assert "No feedback available" in body


# ──────────────────────────────────────────────────────────────────
# send_bulk_grades
# ──────────────────────────────────────────────────────────────────


class TestSendBulkGrades:
    def test_skips_grades_with_no_email(self, configured_emailer):
        emailer = configured_emailer
        grades = [
            {"student_name": "Alice", "email": "alice@x.com", "score": 90,
             "letter_grade": "A", "feedback": "x", "assignment": "Q"},
            {"student_name": "Bob", "email": "", "score": 80,
             "letter_grade": "B", "feedback": "y", "assignment": "Q"},
            {"student_name": "Carol", "score": 70,
             "letter_grade": "C", "feedback": "z", "assignment": "Q"},  # no email key
        ]
        with patch.object(emailer, "send_email", return_value=True):
            result = emailer.send_bulk_grades(grades)

        assert result["sent"] == 1
        assert result["skipped"] == 2

    def test_skips_unknown_student_id(self, configured_emailer):
        emailer = configured_emailer
        grades = [
            {"student_name": "Alice", "email": "alice@x.com", "student_id": "UNKNOWN",
             "score": 0, "letter_grade": "F", "feedback": "", "assignment": "Q"},
        ]
        with patch.object(emailer, "send_email", return_value=True):
            result = emailer.send_bulk_grades(grades)
        assert result["sent"] == 0
        assert result["skipped"] == 1

    def test_counts_failures(self, configured_emailer):
        emailer = configured_emailer
        grades = [
            {"student_name": "Alice", "email": "alice@x.com", "score": 90,
             "letter_grade": "A", "feedback": "x", "assignment": "Q"},
            {"student_name": "Bob", "email": "bob@x.com", "score": 80,
             "letter_grade": "B", "feedback": "y", "assignment": "Q"},
        ]
        # send_email returns False for the 2nd call only
        with patch.object(emailer, "send_email", side_effect=[True, False]):
            result = emailer.send_bulk_grades(grades)
        assert result["sent"] == 1
        assert result["failed"] == 1

    def test_assignment_override(self, configured_emailer):
        emailer = configured_emailer
        grades = [
            {"student_name": "Alice", "email": "a@x.com", "score": 90,
             "letter_grade": "A", "feedback": "x", "assignment": "Original Quiz"},
        ]
        with patch.object(emailer, "send_email", return_value=True) as mock_send:
            emailer.send_bulk_grades(grades, assignment_name="Overridden")
        # subject in send_email call uses overridden name
        subject = mock_send.call_args.args[2]
        assert "Overridden" in subject
        assert "Original Quiz" not in subject


# ──────────────────────────────────────────────────────────────────
# test_connection
# ──────────────────────────────────────────────────────────────────


class TestTestConnection:
    def test_resend_unavailable_returns_false(self, isolated_dirs, monkeypatch):
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        from backend.services.email_service import GraiderEmailer
        with patch("backend.services.email_service.RESEND_AVAILABLE", False):
            emailer = GraiderEmailer(config_path=str(isolated_dirs / "cfg.json"))
        assert emailer.test_connection() is False

    def test_no_api_key_returns_false(self, configured_emailer):
        emailer = configured_emailer
        emailer.resend_available = False
        assert emailer.test_connection() is False

    def test_uses_default_test_address_when_none_provided(self, configured_emailer):
        emailer = configured_emailer
        with patch.object(emailer, "send_email", return_value=True) as mock_send:
            emailer.test_connection()
        # send_email called with delivered@resend.dev (Resend's test sink)
        assert mock_send.call_args.args[0] == "delivered@resend.dev"

    def test_uses_provided_test_address(self, configured_emailer):
        emailer = configured_emailer
        with patch.object(emailer, "send_email", return_value=True) as mock_send:
            emailer.test_connection(test_email="custom@x.com")
        assert mock_send.call_args.args[0] == "custom@x.com"

    def test_returns_send_email_result(self, configured_emailer):
        emailer = configured_emailer
        with patch.object(emailer, "send_email", return_value=False):
            assert emailer.test_connection() is False
        with patch.object(emailer, "send_email", return_value=True):
            assert emailer.test_connection() is True
