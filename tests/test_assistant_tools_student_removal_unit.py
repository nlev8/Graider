"""Unit tests for the student-removal flow in
`backend/services/assistant_tools_student.py`.

Audit MAJOR #4 sprint follow-up to PR #278 (50% target hit). This PR
focuses on the public-API removal flow:

  * `remove_student_from_roster` (preview + pending payload save)
  * `confirm_student_removal` (load pending + delegate)

Tested with `_execute_student_removal` and `_delete_student_supabase`
mocked as black boxes — those internal helpers (195 + 46 LOC) are
out of scope for this PR and will land in a separate one.

Existing coverage in `tests/test_assistant_tools_student_unit.py`
already covers `_parse_csv_name`, `get_student_accommodations`,
`get_student_streak`, `_find_all_student_files`,
`_remove_student_from_csv`. This file is purely additive on those.

Per `feedback_codex_medium_effort_2026-05-09.md` and
`reference_gemini_cli_codex_fallback.md`: Codex is rate-limited until
2026-05-12; Gemini 3.1 Pro is the validated fallback reviewer.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


MODULE = "backend.services.assistant_tools_student"


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def isolated_pending(tmp_path, monkeypatch):
    """Redirect HOME so pending_send.json writes to tmp_path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


# ──────────────────────────────────────────────────────────────────
# remove_student_from_roster — preview flow
# ──────────────────────────────────────────────────────────────────


class TestRemoveStudentFromRoster:
    def test_empty_student_name_returns_error(self, isolated_pending):
        from backend.services.assistant_tools_student import (
            remove_student_from_roster,
        )

        result = remove_student_from_roster(
            student_name="", teacher_id="t",
        )
        assert result == {"error": "student_name is required."}

    def test_no_match_returns_error(self, isolated_pending):
        from backend.services.assistant_tools_student import (
            remove_student_from_roster,
        )

        with patch(f"{MODULE}._load_roster", return_value=[]), \
             patch(f"{MODULE}._find_all_student_files", return_value=[]):
            result = remove_student_from_roster(
                student_name="NonExistent Student",
                teacher_id="t",
            )
        assert "error" in result
        assert "No student found" in result["error"]
        assert "NonExistent Student" in result["error"]

    def test_match_in_roster_returns_pending_confirmation(
        self, isolated_pending,
    ):
        from backend.services.assistant_tools_student import (
            remove_student_from_roster,
        )

        roster = [
            {"student_name": "Alice Smith", "student_id": "s1", "period": "1"},
        ]
        with patch(f"{MODULE}._load_roster", return_value=roster), \
             patch(f"{MODULE}._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in n.lower()), \
             patch("backend.grading.state._get_state",
                   return_value={"results": []}), \
             patch("backend.storage.save") as mock_storage_save:
            result = remove_student_from_roster(
                student_name="alice", teacher_id="teach-1",
            )

        assert result["PENDING_CONFIRMATION"] is True
        assert result["student_name"] == "Alice Smith"
        assert result["results_count"] == 0
        assert "About to permanently delete" in result["message"]
        # Storage save called with the pending payload
        mock_storage_save.assert_called_once()
        args = mock_storage_save.call_args.args
        assert args[0] == "pending_send:remove_student"
        assert args[1]["action"] == "remove_student"
        assert args[1]["student_name"] == "Alice Smith"

    def test_match_via_file_fallback(self, isolated_pending):
        # Roster has nothing → falls through to _find_all_student_files
        from backend.services.assistant_tools_student import (
            remove_student_from_roster,
        )

        with patch(f"{MODULE}._load_roster", return_value=[]), \
             patch(f"{MODULE}._find_all_student_files",
                   return_value=[("Bob Jones", "/tmp/some/path", "Period 2")]), \
             patch("backend.grading.state._get_state",
                   return_value={"results": []}), \
             patch("backend.storage.save"):
            result = remove_student_from_roster(
                student_name="bob", teacher_id="teach-1",
            )

        assert result["PENDING_CONFIRMATION"] is True
        assert result["student_name"] == "Bob Jones"

    def test_results_count_includes_matching_grading_results(
        self, isolated_pending,
    ):
        from backend.services.assistant_tools_student import (
            remove_student_from_roster,
        )

        roster = [{"student_name": "Carol Lee", "student_id": "s3"}]
        # 3 matching grading results, 1 non-matching
        results = [
            {"student_name": "Carol Lee", "score": 80},
            {"student_name": "Carol Lee", "score": 90},
            {"student_name": "Carol Lee", "score": 75},
            {"student_name": "Other Student", "score": 50},
        ]
        with patch(f"{MODULE}._load_roster", return_value=roster), \
             patch(f"{MODULE}._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in (n or "").lower()), \
             patch("backend.grading.state._get_state",
                   return_value={"results": results}), \
             patch("backend.storage.save"):
            result = remove_student_from_roster(
                student_name="Carol", teacher_id="teach-1",
            )

        assert result["results_count"] == 3
        assert "3 grading result" in result["message"]

    def test_grading_state_exception_swallowed(self, isolated_pending):
        # Production wraps the grading-state load in try/except. Pin that
        # the function still returns a valid response when state import
        # raises.
        from backend.services.assistant_tools_student import (
            remove_student_from_roster,
        )

        roster = [{"student_name": "Dan Brown", "student_id": "s4"}]
        with patch(f"{MODULE}._load_roster", return_value=roster), \
             patch(f"{MODULE}._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in (n or "").lower()), \
             patch("backend.grading.state._get_state",
                   side_effect=ImportError("test")), \
             patch("backend.storage.save"):
            result = remove_student_from_roster(
                student_name="Dan", teacher_id="teach-1",
            )

        assert result["PENDING_CONFIRMATION"] is True
        assert result["results_count"] == 0  # exception → fallback to 0

    def test_storage_save_exception_swallowed(self, isolated_pending):
        # Production wraps storage_save in try/except + sentry. The
        # filesystem fallback at viz.py:700 still runs.
        from backend.services.assistant_tools_student import (
            remove_student_from_roster,
        )

        roster = [{"student_name": "Eve Adams", "student_id": "s5"}]
        with patch(f"{MODULE}._load_roster", return_value=roster), \
             patch(f"{MODULE}._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in (n or "").lower()), \
             patch("backend.grading.state._get_state",
                   return_value={"results": []}), \
             patch("backend.storage.save",
                   side_effect=RuntimeError("storage down")), \
             patch(f"{MODULE}.sentry_sdk.capture_exception"):
            result = remove_student_from_roster(
                student_name="Eve", teacher_id="teach-1",
            )

        # Function still completes — pending was written via filesystem
        # fallback (which we can't easily assert without HOME redirect
        # affecting other tests; but the response should still be valid).
        assert result["PENDING_CONFIRMATION"] is True

    def test_teacher_id_threaded_through_to_storage(self, isolated_pending):
        from backend.services.assistant_tools_student import (
            remove_student_from_roster,
        )

        roster = [{"student_name": "Frank Miller", "student_id": "s6"}]
        with patch(f"{MODULE}._load_roster", return_value=roster), \
             patch(f"{MODULE}._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in (n or "").lower()), \
             patch("backend.grading.state._get_state",
                   return_value={"results": []}), \
             patch("backend.storage.save") as mock_save:
            remove_student_from_roster(
                student_name="Frank", teacher_id="teach-tenant-9",
            )

        # Tenant id is the third arg to storage.save
        assert mock_save.call_args.args[2] == "teach-tenant-9"

    def test_pending_payload_persisted_to_filesystem(self, isolated_pending):
        # Verify the json file is written with the right contents
        from backend.services.assistant_tools_student import (
            remove_student_from_roster,
        )

        roster = [{"student_name": "Grace Hill", "student_id": "s7"}]
        with patch(f"{MODULE}._load_roster", return_value=roster), \
             patch(f"{MODULE}._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in (n or "").lower()), \
             patch("backend.grading.state._get_state",
                   return_value={"results": []}), \
             patch("backend.storage.save"):
            remove_student_from_roster(
                student_name="Grace", teacher_id="t",
            )

        pending_path = isolated_pending / ".graider_data" / "pending_send.json"
        assert pending_path.exists()
        payload = json.loads(pending_path.read_text())
        assert payload["action"] == "remove_student"
        assert payload["student_name"] == "Grace Hill"


# ──────────────────────────────────────────────────────────────────
# confirm_student_removal — confirmation flow
# ──────────────────────────────────────────────────────────────────


class TestConfirmStudentRemoval:
    def test_no_pending_returns_error(self, isolated_pending):
        from backend.services.assistant_tools_student import (
            confirm_student_removal,
        )

        with patch("backend.storage.load", return_value=None):
            result = confirm_student_removal(teacher_id="t")
        assert "error" in result
        assert "No pending student removal found" in result["error"]
        assert "remove_student_from_roster first" in result["error"]

    def test_wrong_action_returns_error(self, isolated_pending):
        # If pending payload exists but action != "remove_student",
        # production rejects it. Pin the contract.
        from backend.services.assistant_tools_student import (
            confirm_student_removal,
        )

        with patch("backend.storage.load",
                   return_value={"action": "send_email"}):
            result = confirm_student_removal(teacher_id="t")
        assert "No pending student removal" in result["error"]

    def test_executes_removal_on_pending(self, isolated_pending):
        from backend.services.assistant_tools_student import (
            confirm_student_removal,
        )

        pending = {
            "action": "remove_student",
            "student_name": "Alice Smith",
            "teacher_id": "t",
        }
        with patch("backend.storage.load", return_value=pending), \
             patch("backend.storage.save") as mock_save, \
             patch(f"{MODULE}._execute_student_removal",
                   return_value={"deleted": True}) as mock_exec:
            result = confirm_student_removal(teacher_id="t")

        # Delegate called with the pending student name + tenant
        mock_exec.assert_called_once()
        kwargs = mock_exec.call_args.kwargs
        # student_name is the first positional arg
        assert mock_exec.call_args.args[0] == "Alice Smith"
        assert kwargs.get("teacher_id") == "t"
        # status="removed" added to the result for the verify-result contract
        assert result["status"] == "removed"
        assert result["deleted"] is True

    def test_filesystem_fallback_when_storage_load_fails(
        self, isolated_pending,
    ):
        # If storage.load raises, production falls back to reading the
        # pending file from disk.
        from backend.services.assistant_tools_student import (
            confirm_student_removal,
        )

        # Pre-write the pending file
        pending_dir = isolated_pending / ".graider_data"
        pending_dir.mkdir()
        pending = {
            "action": "remove_student",
            "student_name": "Bob Jones",
            "teacher_id": "t",
        }
        (pending_dir / "pending_send.json").write_text(json.dumps(pending))

        with patch("backend.storage.load",
                   side_effect=RuntimeError("storage down")), \
             patch("backend.storage.save"), \
             patch(f"{MODULE}.sentry_sdk.capture_exception"), \
             patch(f"{MODULE}._execute_student_removal",
                   return_value={"deleted": True}) as mock_exec:
            result = confirm_student_removal(teacher_id="t")

        # Filesystem fallback succeeded → execution proceeded
        mock_exec.assert_called_once()
        assert mock_exec.call_args.args[0] == "Bob Jones"
        assert result["status"] == "removed"

    def test_pending_storage_cleared_after_execution(self, isolated_pending):
        # After successful removal, production calls storage.save with
        # None to clear the pending payload.
        from backend.services.assistant_tools_student import (
            confirm_student_removal,
        )

        pending = {
            "action": "remove_student",
            "student_name": "Carol",
            "teacher_id": "t",
        }
        with patch("backend.storage.load", return_value=pending), \
             patch("backend.storage.save") as mock_save, \
             patch(f"{MODULE}._execute_student_removal",
                   return_value={"deleted": True}):
            confirm_student_removal(teacher_id="t")

        # Look for the cleanup call: save("pending_send:remove_student", None, "t")
        cleanup_calls = [
            c for c in mock_save.call_args_list
            if c.args[0] == "pending_send:remove_student" and c.args[1] is None
        ]
        assert len(cleanup_calls) == 1, (
            f"Expected one cleanup save with None payload; got {mock_save.call_args_list}"
        )

    def test_pending_file_removed_after_execution(self, isolated_pending):
        from backend.services.assistant_tools_student import (
            confirm_student_removal,
        )

        # Pre-write the pending file
        pending_dir = isolated_pending / ".graider_data"
        pending_dir.mkdir()
        pending_file = pending_dir / "pending_send.json"
        pending_file.write_text(json.dumps({
            "action": "remove_student",
            "student_name": "Carol",
            "teacher_id": "t",
        }))

        # Storage returns pending so the function uses storage path,
        # but the filesystem cleanup at viz.py:765-767 should still fire
        with patch("backend.storage.load",
                   return_value={"action": "remove_student",
                                 "student_name": "Carol", "teacher_id": "t"}), \
             patch("backend.storage.save"), \
             patch(f"{MODULE}._execute_student_removal",
                   return_value={"deleted": True}):
            confirm_student_removal(teacher_id="t")

        # The on-disk pending file was removed
        assert not pending_file.exists()

    def test_storage_save_cleanup_exception_swallowed(self, isolated_pending):
        # Production wraps the cleanup save in try/except. Pin that the
        # final result is still returned even if cleanup fails.
        from backend.services.assistant_tools_student import (
            confirm_student_removal,
        )

        pending = {
            "action": "remove_student",
            "student_name": "Dan",
            "teacher_id": "t",
        }
        save_call_count = {"n": 0}

        def selective_save(*args, **kwargs):
            save_call_count["n"] += 1
            # First save call is the cleanup — make it fail
            if save_call_count["n"] == 1:
                raise RuntimeError("cleanup failed")

        with patch("backend.storage.load", return_value=pending), \
             patch("backend.storage.save", side_effect=selective_save), \
             patch(f"{MODULE}.sentry_sdk.capture_exception"), \
             patch(f"{MODULE}._execute_student_removal",
                   return_value={"deleted": True}):
            result = confirm_student_removal(teacher_id="t")

        # Function returned a valid result despite cleanup failure
        assert result["status"] == "removed"
        assert result["deleted"] is True

    def test_uses_pending_teacher_id_for_execution(self, isolated_pending):
        # Pending payload's teacher_id (which may differ from the call's)
        # is used for the actual execution. Pin this contract — important
        # for cross-tenant safety: the user who PREVIEWED the deletion
        # must be the same one whose data gets deleted.
        from backend.services.assistant_tools_student import (
            confirm_student_removal,
        )

        pending = {
            "action": "remove_student",
            "student_name": "Eve",
            "teacher_id": "tenant-original",
        }
        with patch("backend.storage.load", return_value=pending), \
             patch("backend.storage.save"), \
             patch(f"{MODULE}._execute_student_removal",
                   return_value={"deleted": True}) as mock_exec:
            confirm_student_removal(teacher_id="tenant-different")

        # Execution uses the PENDING tenant id, not the call's tenant id
        assert mock_exec.call_args.kwargs.get("teacher_id") == "tenant-original"

    def test_non_dict_result_from_execute_no_status_added(
        self, isolated_pending,
    ):
        # Production: `if isinstance(result, dict): result["status"] = "removed"`
        # If the helper returns a non-dict (defensive guard), no status
        # is added — the raw result flows through.
        from backend.services.assistant_tools_student import (
            confirm_student_removal,
        )

        pending = {
            "action": "remove_student",
            "student_name": "Frank",
            "teacher_id": "t",
        }
        with patch("backend.storage.load", return_value=pending), \
             patch("backend.storage.save"), \
             patch(f"{MODULE}._execute_student_removal",
                   return_value="unexpected string"):
            result = confirm_student_removal(teacher_id="t")

        # Raw string returned, no `["status"] = "removed"` added
        assert result == "unexpected string"


# ──────────────────────────────────────────────────────────────────
# require_teacher_id contract
# ──────────────────────────────────────────────────────────────────


class TestTeacherIdRequired:
    """Pin that the deletion-flow tools both invoke require_teacher_id.
    Cross-tenant safety contract per the assistant_tools_* family
    pattern."""

    def test_remove_student_from_roster_calls_require_teacher_id(
        self, isolated_pending,
    ):
        from backend.services.assistant_tools_student import (
            remove_student_from_roster,
        )

        with patch(f"{MODULE}.require_teacher_id") as mock_req:
            # Empty student_name short-circuits before any work, but
            # require_teacher_id must run first
            remove_student_from_roster(student_name="", teacher_id="t")
        mock_req.assert_called_once_with("t")

    def test_confirm_student_removal_calls_require_teacher_id(
        self, isolated_pending,
    ):
        from backend.services.assistant_tools_student import (
            confirm_student_removal,
        )

        with patch(f"{MODULE}.require_teacher_id") as mock_req, \
             patch("backend.storage.load", return_value=None):
            confirm_student_removal(teacher_id="t")
        mock_req.assert_called_once_with("t")
