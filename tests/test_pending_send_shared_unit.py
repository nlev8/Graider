"""Unit tests for `backend/utils/pending_send.py` shared helpers.

Closes GH #280: cross-tenant IDOR + tenant-clobber in pending_send.json
across 4 modules. The helpers consolidate per-tenant filesystem paths
and IDOR validation that previously existed only in
`assistant_tools_student.py` (per PR #279).

Tests cover:
  * `sanitize_tenant_for_path` — path-traversal defense + non-string coercion
  * `pending_send_path` — per-tenant naming
  * `assert_pending_belongs_to` — IDOR validation with sentry alert
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


# ──────────────────────────────────────────────────────────────────
# sanitize_tenant_for_path
# ──────────────────────────────────────────────────────────────────


class TestSanitize:
    def test_uuid_preserved(self):
        from backend.utils.pending_send import sanitize_tenant_for_path
        assert sanitize_tenant_for_path("abc-123-uuid_xyz") == "abc-123-uuid_xyz"

    def test_local_dev_preserved(self):
        from backend.utils.pending_send import sanitize_tenant_for_path
        assert sanitize_tenant_for_path("local-dev") == "local-dev"

    def test_path_traversal_neutralized(self):
        from backend.utils.pending_send import sanitize_tenant_for_path
        assert sanitize_tenant_for_path("../etc/passwd") == "___etc_passwd"
        assert sanitize_tenant_for_path("/etc/shadow") == "_etc_shadow"
        assert sanitize_tenant_for_path("a/b/c") == "a_b_c"
        # `..\\windows\\system32` → 3 special chars (..\\) at start = 3 underscores
        assert sanitize_tenant_for_path("..\\windows\\system32") == "___windows_system32"

    def test_special_chars_replaced(self):
        from backend.utils.pending_send import sanitize_tenant_for_path
        assert sanitize_tenant_for_path("user@email.com") == "user_email_com"
        assert sanitize_tenant_for_path("a b c") == "a_b_c"
        assert sanitize_tenant_for_path("$$$") == "___"

    def test_length_capped_at_64(self):
        from backend.utils.pending_send import sanitize_tenant_for_path
        long_id = "x" * 200
        result = sanitize_tenant_for_path(long_id)
        assert len(result) == 64
        assert result == "x" * 64

    def test_empty_string_falls_back(self):
        from backend.utils.pending_send import sanitize_tenant_for_path
        assert sanitize_tenant_for_path("") == "local-dev"

    def test_none_falls_back(self):
        from backend.utils.pending_send import sanitize_tenant_for_path
        assert sanitize_tenant_for_path(None) == "local-dev"

    def test_int_coerced_to_str(self):
        # Buggy callers may pass ints; should not raise TypeError
        from backend.utils.pending_send import sanitize_tenant_for_path
        assert sanitize_tenant_for_path(12345) == "12345"

    def test_zero_int_falls_back(self):
        # 0 is falsy → uses "local-dev" fallback
        from backend.utils.pending_send import sanitize_tenant_for_path
        assert sanitize_tenant_for_path(0) == "local-dev"

    def test_chars_outside_allowed_class(self):
        # Anything not [a-zA-Z0-9_-] gets replaced
        from backend.utils.pending_send import sanitize_tenant_for_path
        assert sanitize_tenant_for_path("a.b") == "a_b"
        assert sanitize_tenant_for_path("a:b") == "a_b"
        assert sanitize_tenant_for_path("a;b") == "a_b"


# ──────────────────────────────────────────────────────────────────
# pending_send_path
# ──────────────────────────────────────────────────────────────────


class TestPendingSendPath:
    def test_basic_namespaced_filename(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        from backend.utils.pending_send import pending_send_path

        path = pending_send_path("teach-1")
        assert path.endswith("/.graider_data/pending_send_teach-1.json")
        # Path is under HOME/.graider_data
        assert str(tmp_path) in path

    def test_different_tenants_different_paths(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        from backend.utils.pending_send import pending_send_path

        path_a = pending_send_path("tenant-a")
        path_b = pending_send_path("tenant-b")
        assert path_a != path_b
        assert "tenant-a" in path_a
        assert "tenant-b" in path_b

    def test_unsafe_tenant_id_sanitized_in_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        from backend.utils.pending_send import pending_send_path

        # Path traversal attempt → sanitized
        path = pending_send_path("../../etc/passwd")
        # The path stays within .graider_data
        assert "/.graider_data/pending_send_" in path
        # The dangerous chars are gone
        assert ".." not in path.replace("/.graider_data/", "/")

    def test_local_dev_default_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        from backend.utils.pending_send import pending_send_path

        path = pending_send_path("local-dev")
        assert path.endswith("/pending_send_local-dev.json")


# ──────────────────────────────────────────────────────────────────
# assert_pending_belongs_to
# ──────────────────────────────────────────────────────────────────


class TestAssertPendingBelongsTo:
    def test_matching_tenant_returns_none(self):
        from backend.utils.pending_send import assert_pending_belongs_to

        pending = {"action": "send_focus_comms", "teacher_id": "teach-1"}
        assert assert_pending_belongs_to(pending, "teach-1") is None

    def test_mismatched_tenant_returns_error(self):
        from backend.utils.pending_send import assert_pending_belongs_to

        pending = {"action": "send_focus_comms", "teacher_id": "teach-A"}
        with patch("backend.utils.pending_send.sentry_sdk.capture_message") as mock_sentry:
            err = assert_pending_belongs_to(pending, "teach-B")

        assert err is not None
        assert "error" in err
        assert "different teacher" in err["error"]
        # Sentry alert fired with both ids
        mock_sentry.assert_called_once()
        msg = mock_sentry.call_args.args[0]
        assert "Cross-tenant" in msg
        assert "teach-A" in msg
        assert "teach-B" in msg

    def test_legacy_payload_with_local_dev_caller_allowed(self):
        # Backward-compat: pre-injection payloads (no teacher_id) are
        # treated as legacy/dev payloads ONLY when the caller is
        # local-dev. Production callers MUST have a tenant id in the
        # payload — see the next test.
        from backend.utils.pending_send import assert_pending_belongs_to

        pending = {"action": "send_parent_emails"}  # no teacher_id field
        assert assert_pending_belongs_to(pending, "local-dev") is None

    def test_legacy_payload_with_real_caller_rejected(self):
        # Critical: a legacy payload without teacher_id MUST be rejected
        # for non-local-dev callers. Otherwise an attacker could craft
        # a payload without teacher_id and still trigger the action.
        from backend.utils.pending_send import assert_pending_belongs_to

        pending = {"action": "send_parent_emails"}  # no teacher_id field
        with patch("backend.utils.pending_send.sentry_sdk.capture_message"):
            err = assert_pending_belongs_to(pending, "teach-real-prod")
        assert err is not None
        assert "error" in err

    def test_empty_string_pending_id_rejected_for_real_caller(self):
        from backend.utils.pending_send import assert_pending_belongs_to

        pending = {"action": "x", "teacher_id": ""}
        with patch("backend.utils.pending_send.sentry_sdk.capture_message"):
            err = assert_pending_belongs_to(pending, "teach-real")
        assert err is not None

    def test_none_pending_id_rejected_for_real_caller(self):
        from backend.utils.pending_send import assert_pending_belongs_to

        pending = {"action": "x", "teacher_id": None}
        with patch("backend.utils.pending_send.sentry_sdk.capture_message"):
            err = assert_pending_belongs_to(pending, "teach-real")
        assert err is not None

    def test_extra_payload_fields_ignored(self):
        # Only the teacher_id field matters for the contract
        from backend.utils.pending_send import assert_pending_belongs_to

        pending = {
            "action": "send_focus_comms",
            "teacher_id": "teach-1",
            "messages": [{"to": "a@b.com"}],
            "secret_token": "doesnt-matter",
        }
        assert assert_pending_belongs_to(pending, "teach-1") is None
