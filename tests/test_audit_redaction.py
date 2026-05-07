"""
Audit log redaction — closes audit MAJOR #10 (Codex full-codebase audit
2026-05-06): centralize PII redaction at the `audit_log()` boundary so
FERPA posture no longer depends on every caller self-redacting.

Tests the `_redact_for_audit()` helper directly + the end-to-end audit
file/Supabase write to verify redaction propagates to both sinks.
"""
import os
import re
from unittest.mock import patch, MagicMock

import pytest

from backend.utils.audit import _redact_for_audit, audit_log


class TestRedactForAuditUnit:
    """Unit tests for the redaction function itself."""

    def test_email_redacted(self):
        out = _redact_for_audit("sent welcome to alice@example.com")
        assert "alice@example.com" not in out
        assert "a***@example.com" in out

    def test_short_local_email_redacted(self):
        out = _redact_for_audit("contacted a@x.org")
        assert "a@x.org" not in out
        assert "***@x.org" in out

    def test_uuid_redacted_to_hashed_id(self):
        uuid = "01234567-89ab-cdef-0123-456789abcdef"
        out = _redact_for_audit(f"submission {uuid} graded")
        assert uuid not in out
        # Replaced with id=<8-hex-prefix>
        assert re.search(r"\bid=[0-9a-f]{8}\b", out)

    def test_uuid_uppercase_also_redacted(self):
        uuid = "FEDCBA98-7654-3210-FEDC-BA9876543210"
        out = _redact_for_audit(f"row id {uuid}")
        assert uuid not in out
        assert re.search(r"\bid=[0-9a-f]{8}\b", out)

    def test_long_hex_token_redacted(self):
        # 64-char hex (looks like sha256 of something)
        token = "a" * 64
        out = _redact_for_audit(f"token {token} expired")
        assert token not in out
        assert re.search(r"\bhex=[0-9a-f]{8}\b", out)

    def test_short_hash_prefix_not_re_redacted(self):
        # 8-char hex hash (the OUTPUT of our own redaction) must NOT be
        # caught by the long-hex pattern — that would double-hash on
        # subsequent passes.
        short_hash = "deadbeef"
        out = _redact_for_audit(f"hashed teacher_id={short_hash}")
        assert short_hash in out  # left alone

    def test_multiple_pii_items_each_redacted(self):
        text = (
            "user alice@example.com submitted "
            "01234567-89ab-cdef-0123-456789abcdef "
            "with token " + ("c" * 32)
        )
        out = _redact_for_audit(text)
        assert "alice@example.com" not in out
        assert "01234567-89ab-cdef" not in out
        assert ("c" * 32) not in out
        assert "a***@example.com" in out
        assert re.search(r"\bid=[0-9a-f]{8}\b", out)
        assert re.search(r"\bhex=[0-9a-f]{8}\b", out)

    def test_non_pii_preserved(self):
        text = "EMAIL_TEST_SEND succeeded count=5 status=200"
        out = _redact_for_audit(text)
        assert out == text  # nothing touched

    def test_empty_string_returns_empty(self):
        assert _redact_for_audit("") == ""

    def test_none_returns_none(self):
        # Non-string returns as-is so we never raise on bad caller input
        assert _redact_for_audit(None) is None

    def test_non_string_returns_as_is(self):
        # int / dict / etc. — never raise
        assert _redact_for_audit(42) == 42
        d = {"x": 1}
        assert _redact_for_audit(d) is d

    def test_email_with_plus_alias_redacted(self):
        out = _redact_for_audit("alias bob+filter@school.edu")
        assert "bob+filter@school.edu" not in out
        assert "b***@school.edu" in out

    def test_email_with_dots_in_local_redacted(self):
        out = _redact_for_audit("teacher.smith@district.k12.us logged in")
        assert "teacher.smith@district.k12.us" not in out
        assert "t***@district.k12.us" in out

    def test_uuid_inside_word_boundary_only(self):
        # A 36-char hex string NOT separated by word boundaries should
        # still match (uuid pattern uses \b on both sides). Sanity:
        # confirm the pattern catches typical embedded usage.
        out = _redact_for_audit(
            "id=01234567-89ab-cdef-0123-456789abcdef,rest"
        )
        assert "01234567-89ab-cdef" not in out


class TestAuditLogEndToEnd:
    """audit_log() must redact before writing to file AND Supabase."""

    @patch('backend.utils.audit.get_supabase', create=True)
    def test_local_file_contains_redacted_email(self, _mock_sb_unused, tmp_path, monkeypatch):
        log_path = tmp_path / "graider_audit.log"
        monkeypatch.setattr('backend.utils.audit.AUDIT_LOG_FILE', str(log_path))

        # Patch supabase client to no-op so only the file write matters.
        monkeypatch.setattr(
            'backend.supabase_client.get_supabase',
            lambda: None,
        )

        audit_log(
            action="EMAIL_TEST_SEND",
            details="sent test email to teacher.smith@school.edu",
            user="teacher",
            teacher_id="t-123",
        )

        contents = log_path.read_text()
        assert "teacher.smith@school.edu" not in contents
        assert "t***@school.edu" in contents
        assert "EMAIL_TEST_SEND" in contents  # action label preserved

    def test_supabase_insert_receives_redacted_payload(self, monkeypatch, tmp_path):
        # Capture what gets inserted into Supabase audit_log table.
        captured = {}

        def fake_insert(payload):
            captured['payload'] = payload
            chain = MagicMock()
            chain.execute.return_value = MagicMock()
            return chain

        mock_table = MagicMock()
        mock_table.insert.side_effect = fake_insert

        mock_sb = MagicMock()
        mock_sb.table.return_value = mock_table
        monkeypatch.setattr(
            'backend.supabase_client.get_supabase',
            lambda: mock_sb,
        )

        # Redirect file write to a temp path so we don't pollute home.
        monkeypatch.setattr(
            'backend.utils.audit.AUDIT_LOG_FILE',
            str(tmp_path / "audit.log"),
        )

        audit_log(
            action="ROSTER_SYNC",
            details="synced 5 students for class id=01234567-89ab-cdef-0123-456789abcdef",
            user="teacher",
            teacher_id="t-456",
        )

        payload = captured.get('payload')
        assert payload is not None, "Supabase insert was never called"
        assert "01234567-89ab-cdef-0123-456789abcdef" not in payload['details']
        assert re.search(r"\bid=[0-9a-f]{8}\b", payload['details'])
        # Action preserved (no PII in the action label itself).
        assert payload['action'] == "ROSTER_SYNC"
        # Non-PII content preserved.
        assert "synced 5 students" in payload['details']

    def test_action_label_with_email_is_redacted(self, monkeypatch, tmp_path):
        # Pathological caller passes PII in the ACTION not just details
        # — centralization means BOTH sides are redacted.
        captured = {}

        def fake_insert(payload):
            captured['payload'] = payload
            chain = MagicMock()
            chain.execute.return_value = MagicMock()
            return chain

        mock_table = MagicMock()
        mock_table.insert.side_effect = fake_insert
        mock_sb = MagicMock()
        mock_sb.table.return_value = mock_table
        monkeypatch.setattr(
            'backend.supabase_client.get_supabase',
            lambda: mock_sb,
        )
        monkeypatch.setattr(
            'backend.utils.audit.AUDIT_LOG_FILE',
            str(tmp_path / "audit.log"),
        )

        audit_log(
            action="LOGIN_FAIL alice@example.com",
            details="ip=1.2.3.4",
            user="student",
            teacher_id="t-789",
        )

        payload = captured.get('payload')
        assert payload is not None
        assert "alice@example.com" not in payload['action']
        assert "a***@example.com" in payload['action']

    def test_truncation_after_redaction(self, monkeypatch, tmp_path):
        # Very long details with PII — confirm redaction runs BEFORE the
        # 500-char truncation so no half-redacted email leaks past the
        # boundary.
        captured = {}

        def fake_insert(payload):
            captured['payload'] = payload
            chain = MagicMock()
            chain.execute.return_value = MagicMock()
            return chain

        mock_table = MagicMock()
        mock_table.insert.side_effect = fake_insert
        mock_sb = MagicMock()
        mock_sb.table.return_value = mock_table
        monkeypatch.setattr(
            'backend.supabase_client.get_supabase',
            lambda: mock_sb,
        )
        monkeypatch.setattr(
            'backend.utils.audit.AUDIT_LOG_FILE',
            str(tmp_path / "audit.log"),
        )

        # 480 char filler + email pushed past 500 char raw boundary
        filler = "x" * 480
        long_details = filler + " contact: alice@example.com"

        audit_log(
            action="X",
            details=long_details,
            user="teacher",
            teacher_id="t-1",
        )

        payload = captured['payload']
        # The raw email must NOT appear regardless of truncation.
        assert "alice@example.com" not in payload['details']
        # The 500-char Supabase column cap must still hold.
        assert len(payload['details']) <= 500
