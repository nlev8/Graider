"""Cross-module security pins for GH #280 fix.

Closes the IDOR + tenant-clobber vulnerabilities Gemini round-2 caught
on PR #279. The same fix that landed for `confirm_student_removal`
in PR #279 is now applied to:
  * `assistant_tools_reports.send_parent_emails` (writer)
  * `assistant_tools_reports.send_focus_comms` (writer)
  * `assistant_tools_reports.confirm_and_send` (reader — adds IDOR check)
  * `assistant_tools_behavior.send_behavior_email` (writer)

These tests pin:
  1. All writers inject `teacher_id` into the pending payload
  2. All writers persist to the namespaced filesystem path
  3. confirm_and_send rejects payloads from a different tenant
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def isolated_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


# ──────────────────────────────────────────────────────────────────
# confirm_and_send — cross-tenant IDOR check
# ──────────────────────────────────────────────────────────────────


class TestConfirmAndSendCrossTenantBlock:
    def test_storage_pending_from_different_tenant_rejected(
        self, isolated_dirs,
    ):
        # Storage is already tenant-namespaced, but defense-in-depth
        # requires the explicit caller-vs-pending check. Simulate the
        # case where storage somehow surfaces a payload from another
        # tenant (e.g., legacy data, a bug elsewhere).
        from backend.services.assistant_tools_reports import confirm_and_send

        # Pending says tenant-A; caller is tenant-B
        pending = {
            "action": "send_focus_comms",
            "messages": [{"to": "x@y.com"}],
            "teacher_id": "tenant-A",
        }
        with patch("backend.services.assistant_tools_reports.storage_load",
                   return_value=pending), \
             patch("backend.services.assistant_tools_reports.storage_save"), \
             patch("backend.utils.pending_send.sentry_sdk.capture_message") as mock_sentry:
            result = confirm_and_send(teacher_id="tenant-B")

        assert "error" in result
        assert "different teacher" in result["error"]
        # Sentry alert fired
        mock_sentry.assert_called_once()
        msg = mock_sentry.call_args.args[0]
        assert "Cross-tenant" in msg
        assert "tenant-A" in msg
        assert "tenant-B" in msg

    def test_filesystem_fallback_uses_namespaced_path(self, isolated_dirs):
        # Pre-write a pending file at the OLD global path. confirm_and_send
        # MUST NOT find it (would be cross-tenant).
        from backend.services.assistant_tools_reports import confirm_and_send

        legacy_path = isolated_dirs / ".graider_data" / "pending_send.json"
        legacy_path.parent.mkdir()
        legacy_path.write_text(json.dumps({
            "action": "send_focus_comms",
            "messages": [{"to": "x@y.com"}],
            "teacher_id": "some-other-tenant",
        }))

        with patch("backend.services.assistant_tools_reports.storage_load",
                   return_value=None):
            result = confirm_and_send(teacher_id="tenant-X")

        # The legacy global file is ignored — the per-tenant file
        # for "tenant-X" doesn't exist, so we get the standard error
        assert "error" in result
        assert "No pending send action" in result["error"]

    def test_matching_tenant_proceeds(self, isolated_dirs):
        # Symmetric pin: when caller matches, execution proceeds normally
        from backend.services.assistant_tools_reports import confirm_and_send

        pending = {
            "action": "send_focus_comms",
            "messages": [{"to": "x@y.com", "subject": "S", "email_body": "B"}],
            "teacher_id": "tenant-X",
        }
        with patch("backend.services.assistant_tools_reports.storage_load",
                   return_value=pending), \
             patch("backend.services.assistant_tools_reports.storage_save"), \
             patch("backend.routes.email_routes.launch_focus_comms",
                   return_value={"queued": 1}) as mock_launch:
            result = confirm_and_send(teacher_id="tenant-X")

        # Reached execution
        mock_launch.assert_called_once()
        assert "error" not in result or result.get("queued") == 1

    def test_legacy_payload_no_teacher_id_blocked_for_real_caller(
        self, isolated_dirs,
    ):
        # A pre-fix payload (no teacher_id) MUST be rejected when the
        # caller is a real production tenant. (local-dev caller is
        # exempted for backward-compat — see helper docstring.)
        from backend.services.assistant_tools_reports import confirm_and_send

        legacy_pending = {
            "action": "send_focus_comms",
            "messages": [{"to": "x@y.com"}],
            # NO teacher_id field — pre-fix shape
        }
        with patch("backend.services.assistant_tools_reports.storage_load",
                   return_value=legacy_pending), \
             patch("backend.utils.pending_send.sentry_sdk.capture_message"):
            result = confirm_and_send(teacher_id="tenant-real-prod")

        assert "error" in result


# ──────────────────────────────────────────────────────────────────
# Writers — teacher_id injection + namespaced path
# ──────────────────────────────────────────────────────────────────


class TestWritersInjectTeacherId:
    def test_send_parent_emails_writes_teacher_id_to_namespaced_path(
        self, isolated_dirs,
    ):
        # Pin that send_parent_emails (in dry_run mode) saves a pending
        # payload with teacher_id AND writes to the per-tenant file.
        from backend.services.assistant_tools_reports import send_parent_emails

        # Mock all external dependencies — we just want to verify the
        # pending save side effects.
        with patch("backend.services.assistant_tools_reports._load_roster",
                   return_value=[
                       {"student_name": "Alice", "student_id": "s1",
                        "period": "1"},
                   ]), \
             patch("backend.services.assistant_tools_reports._load_parent_contacts",
                   return_value={
                       "s1": {
                           "student_name": "Alice",
                           "parent_emails": ["alice@parent.com"],
                       },
                   }), \
             patch("backend.services.assistant_tools_reports._load_email_config",
                   return_value={"teacher_name": "Mrs. T",
                                 "subject_area": "Math"}), \
             patch("backend.services.assistant_tools_reports.storage_save") as mock_save, \
             patch("backend.services.assistant_tools_reports.audit_tool_action"):
            result = send_parent_emails(
                email_subject="Subject",
                email_body="Body",
                student_names=["Alice"],
                dry_run=True,
                teacher_id="tenant-W",
            )

        # Pending payload saved to storage with teacher_id
        save_calls = [c for c in mock_save.call_args_list
                      if c.args[0] == "pending_send"]
        assert len(save_calls) >= 1
        payload = save_calls[0].args[1]
        assert payload["teacher_id"] == "tenant-W"
        assert payload["action"] == "send_parent_emails"

        # Filesystem fallback at namespaced path
        per_tenant_path = (
            isolated_dirs / ".graider_data" / "pending_send_tenant-W.json"
        )
        assert per_tenant_path.exists()
        # AND the global path is NOT written
        global_path = isolated_dirs / ".graider_data" / "pending_send.json"
        assert not global_path.exists(), (
            "Global pending_send.json still being written — cross-tenant clobber risk."
        )
        # Filesystem payload also has teacher_id
        fs_payload = json.loads(per_tenant_path.read_text())
        assert fs_payload["teacher_id"] == "tenant-W"


class TestSendBehaviorEmailWriter:
    def test_pending_payload_includes_teacher_id_and_namespaced_path(
        self, isolated_dirs,
    ):
        # Pin that send_behavior_email injects teacher_id and uses the
        # per-tenant filesystem path.
        from backend.services.assistant_tools_behavior import (
            send_behavior_email,
        )

        with patch("backend.services.assistant_tools_behavior._load_roster",
                   return_value=[
                       {"student_name": "Alice", "student_id": "s1",
                        "period": "1", "parent_email": "alice@parent.com"},
                   ]), \
             patch("backend.services.assistant_tools_behavior._load_parent_contacts",
                   return_value={"s1": ["alice@parent.com"]}), \
             patch("backend.storage.save") as mock_save, \
             patch("backend.services.assistant_tools_behavior.audit_tool_action"):
            send_behavior_email(
                student_name="Alice",
                subject="Behavior note",
                body="Body",
                method="focus",
                teacher_id="tenant-Y",
            )

        # Pending payload saved with teacher_id field
        save_calls = mock_save.call_args_list
        # Find the calls that wrote a pending payload
        pending_calls = [c for c in save_calls
                         if c.args[0] in ("pending_send",
                                          "pending_send:send_behavior_email")]
        assert len(pending_calls) >= 1
        for c in pending_calls:
            assert c.args[1]["teacher_id"] == "tenant-Y", (
                f"send_behavior_email pending payload missing teacher_id: "
                f"{c.args[1]}"
            )

        # Filesystem fallback at namespaced path
        per_tenant_path = (
            isolated_dirs / ".graider_data" / "pending_send_tenant-Y.json"
        )
        assert per_tenant_path.exists()
        global_path = isolated_dirs / ".graider_data" / "pending_send.json"
        assert not global_path.exists()
        fs_payload = json.loads(per_tenant_path.read_text())
        assert fs_payload["teacher_id"] == "tenant-Y"
