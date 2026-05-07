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
        # Round-2 Codex MEDIUM fold: position the email so a truncate-first
        # implementation would leak a recognizable PARTIAL email like
        # "alice@examp" — the original test only checked for the FULL
        # email and would have falsely passed under truncation-first.
        # Now we assert against partials too.
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

        # Position the email so under truncate-first the output[480..500]
        # would be " contact: alice@exam" — a partial leak. Under redact-
        # first the email becomes "a***@example.com" (16 chars) BEFORE
        # truncation, so no "alice" substring survives.
        # Filler sized so the FULL redacted form fits within the 500-char
        # cap — that lets the sanity assertion below verify which order
        # actually ran.
        filler = "x" * 470
        long_details = filler + " contact: alice@example.com extra"

        audit_log(
            action="X",
            details=long_details,
            user="teacher",
            teacher_id="t-1",
        )

        payload = captured['payload']
        # Strong assertion: no recognizable email-shaped fragment ever
        # makes it past the boundary, full OR partial.
        assert "alice@example.com" not in payload['details'], "Full email leaked"
        assert "alice@" not in payload['details'], "Partial email leaked (truncate-first?)"
        assert "alice" not in payload['details'], "Local-part leaked (truncate-first?)"
        # The 500-char Supabase column cap must still hold.
        assert len(payload['details']) <= 500
        # Sanity: the redacted form should be present at the boundary.
        assert "a***@example.com" in payload['details'], (
            "Redacted form should survive truncation since it's shorter than raw"
        )

    def test_names_remain_caller_responsibility_documented_gap(
        self, monkeypatch, tmp_path,
    ):
        """Round-2 Codex HIGH fold #2 (acknowledged gap test):

        The redaction helper does NOT and CANNOT redact arbitrary student
        or teacher names from audit details. Names lack the regex shape
        emails/UUIDs/tokens have. Callers passing name-bearing strings
        (filenames like "Alice_Smith_Math.docx", assignment labels like
        "Bob's Quiz") MUST self-redact.

        This test pins that boundary so a future maintainer who tightens
        the regexes (e.g. with an NLP pass that catches names) doesn't
        accidentally regress something downstream that depends on names
        passing through, AND so the contract scope stays explicit.
        """
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
            action="GRADE_EDIT",
            details="file=Alice_Smith_Math.docx assignment=Bob's_Quiz teacher=Mr. Johnson",
            user="teacher",
            teacher_id="t-99",
        )

        # ACKNOWLEDGED GAP: names pass through unchanged. Callers passing
        # these MUST sanitize at the call site. If a future PR centralizes
        # name redaction, update this test + the contract comment in
        # backend/utils/audit.py.
        details = captured['payload']['details']
        assert "Alice_Smith_Math.docx" in details, (
            "Names are caller-side responsibility — current contract scope"
        )
        assert "Bob's_Quiz" in details
        assert "Mr. Johnson" in details

    def test_clever_audit_logger_info_is_redacted(
        self, monkeypatch, tmp_path, caplog,
    ):
        """Round-3 Codex HIGH fold (PR #227): `_clever_audit` previously
        called `logger.info('AUDIT: ... | %s', details)` BEFORE the
        central redaction. With Sentry's default logging breadcrumbs
        capture, raw PII could reach Sentry exception capture even
        though the central `audit_log()` itself was redaction-safe.

        Now `_clever_audit` redacts via `_redact_for_audit` BEFORE
        emitting the logger.info, so logger / breadcrumb consumers
        never observe raw PII regardless of what fires later.
        """
        from backend.routes.clever_routes import _clever_audit
        import logging

        monkeypatch.setattr(
            'backend.supabase_client.get_supabase',
            lambda: None,  # noop — only the logger.info matters here
        )
        monkeypatch.setattr(
            'backend.utils.audit.AUDIT_LOG_FILE',
            str(tmp_path / "audit.log"),
        )

        with caplog.at_level(logging.INFO, logger="backend.routes.clever_routes"):
            _clever_audit(
                "clever_login",
                "user alice@example.com from id=01234567-89ab-cdef-0123-456789abcdef",
                teacher_id="t-99",
            )

        # Find the AUDIT log record. Assert raw PII is NOT in the message.
        audit_records = [r for r in caplog.records if r.message.startswith("AUDIT:")]
        assert audit_records, "Expected at least one AUDIT logger.info"
        for record in audit_records:
            full_msg = record.getMessage()
            assert "alice@example.com" not in full_msg, (
                f"Raw email leaked to logger: {full_msg!r}"
            )
            assert "01234567-89ab-cdef-0123-456789abcdef" not in full_msg, (
                f"Raw UUID leaked to logger: {full_msg!r}"
            )
            assert "a***@example.com" in full_msg, (
                f"Redacted form should appear: {full_msg!r}"
            )

    def test_bypass_writers_now_delegate_to_central_audit_log(
        self, monkeypatch, tmp_path,
    ):
        """Round-2 Codex HIGH fold #1: the 3 historical bypass writers
        (`_audit_log` in assistant_routes, `audit_log_accommodation` in
        accommodations, `_clever_audit` in clever_routes) used to write
        to audit sinks WITHOUT going through `_redact_for_audit()`. They
        now delegate to the central `audit_log()`. This test confirms
        each delegating wrapper actually invokes redaction by passing PII
        through and verifying the persisted form is redacted.
        """
        from backend.routes.assistant_routes import _audit_log as assistant_audit
        from backend.accommodations import audit_log_accommodation
        from backend.routes.clever_routes import _clever_audit

        captured_payloads = []

        def fake_insert(payload):
            captured_payloads.append(payload)
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

        # Each wrapper passes raw PII; central audit_log must redact.
        assistant_audit("ASSISTANT_QUERY", "session for alice@example.com")
        audit_log_accommodation("LOAD_PRESETS", "loaded for teacher.smith@school.edu")
        _clever_audit(
            "clever_roster_sync",
            "synced 5 students for class id=01234567-89ab-cdef-0123-456789abcdef",
            teacher_id="t-clever",
        )

        # All 3 should have flushed to Supabase via the central path.
        assert len(captured_payloads) == 3, (
            f"Expected 3 audit_log inserts; got {len(captured_payloads)}"
        )
        # No raw PII in any of the 3 payloads.
        for payload in captured_payloads:
            assert "alice@example.com" not in payload['details']
            assert "teacher.smith@school.edu" not in payload['details']
            assert "01234567-89ab-cdef-0123-456789abcdef" not in payload['details']
        # Action labels preserved (no PII in them).
        assert captured_payloads[0]['action'] == "ASSISTANT_QUERY"
        assert captured_payloads[1]['action'] == "ACCOMMODATION_LOAD_PRESETS"
        assert captured_payloads[2]['action'] == "clever_roster_sync"
