"""
tests/test_assistant_tool_guards.py — Tests for the guarded action registry and helpers.
"""

import pytest
from backend.services.assistant_tool_guards import (
    GUARDED_ACTIONS,
    check_false_claims,
    get_verification_message,
)


# ---------------------------------------------------------------------------
# TestGuardedActionsRegistry
# ---------------------------------------------------------------------------

class TestGuardedActionsRegistry:
    EXPECTED_TOOLS = [
        "send_focus_comms",
        "send_parent_emails",
        "send_behavior_email",
        "confirm_and_send",
        "remove_student_from_roster",
        "confirm_student_removal",
        "create_focus_assignment",
    ]

    def test_all_expected_tools_present(self):
        for tool in self.EXPECTED_TOOLS:
            assert tool in GUARDED_ACTIONS, f"Expected tool '{tool}' missing from GUARDED_ACTIONS"
        assert len(GUARDED_ACTIONS) == 7

    def test_preview_confirm_entries_have_confirm_tool(self):
        for name, entry in GUARDED_ACTIONS.items():
            if entry["type"] == "preview_confirm":
                assert "confirm_tool" in entry, (
                    f"preview_confirm entry '{name}' missing 'confirm_tool'"
                )
                assert entry["confirm_tool"], f"'{name}' confirm_tool is empty"

    def test_verify_result_entries_have_non_empty_claim_phrases(self):
        for name, entry in GUARDED_ACTIONS.items():
            if entry["type"] == "verify_result":
                assert "claim_phrases" in entry, (
                    f"verify_result entry '{name}' missing 'claim_phrases'"
                )
                assert isinstance(entry["claim_phrases"], list) and len(entry["claim_phrases"]) > 0, (
                    f"'{name}' claim_phrases must be a non-empty list"
                )


# ---------------------------------------------------------------------------
# TestGetVerificationMessage
# ---------------------------------------------------------------------------

class TestGetVerificationMessage:
    def test_preview_confirm_returns_not_executed_message(self):
        result = get_verification_message("send_parent_emails", {"NOT_SENT": True})
        assert result is not None
        assert "NOT been executed" in result

    def test_verify_result_success_returns_success_message(self):
        result = get_verification_message("confirm_and_send", {"status": "started"})
        assert result is not None
        assert "SUCCESS" in result

    def test_verify_result_with_error_returns_failed_message(self):
        result = get_verification_message("confirm_and_send", {"error": "SMTP timeout"})
        assert result is not None
        assert "FAILED" in result
        assert "SMTP timeout" in result

    def test_unguarded_tool_returns_none(self):
        result = get_verification_message("list_students", {"students": []})
        assert result is None

    def test_verify_result_wrong_status_returns_failure_message(self):
        result = get_verification_message("confirm_and_send", {"status": "queued"})
        assert result is not None
        assert "UNEXPECTED STATUS" in result
        assert "queued" in result

    def test_unknown_action_type_falls_through_to_none(self):
        # Hit line 131 — the defensive `return None` after both branches.
        # Triggered when an entry has a `type` value that's neither
        # "preview_confirm" nor "verify_result". A regression that adds a
        # third action type without a corresponding handler would produce
        # a silent no-op on this path; this test pins the contract that
        # unknown action types currently return None.
        from backend.services.assistant_tool_guards import (
            get_verification_message, GUARDED_ACTIONS,
        )

        # Inject a temporary entry with an unrecognized type
        GUARDED_ACTIONS["__test_unknown_type__"] = {
            "type": "future_action_type_not_yet_handled",
        }
        try:
            result = get_verification_message("__test_unknown_type__", {})
            assert result is None
        finally:
            # Always clean up the registry
            del GUARDED_ACTIONS["__test_unknown_type__"]


# ---------------------------------------------------------------------------
# TestCheckFalseClaims
# ---------------------------------------------------------------------------

class TestCheckFalseClaims:
    def test_detects_false_send_claim_no_tools_called(self):
        response = "The email has been sent to all parents."
        correction = check_false_claims(response, [])
        assert correction is not None
        assert "confirm_and_send" in correction

    def test_no_false_positive_on_future_tense(self):
        response = "I plan to send the emails once you confirm."
        correction = check_false_claims(response, [])
        assert correction is None

    def test_no_correction_when_tool_succeeded(self):
        response = "The message has been sent successfully."
        executed_tools = [
            {"name": "confirm_and_send", "result": {"status": "started"}},
        ]
        correction = check_false_claims(response, executed_tools)
        assert correction is None

    def test_detects_false_removal_claim(self):
        response = "The student has been removed from the roster."
        correction = check_false_claims(response, [])
        assert correction is not None
        assert "confirm_student_removal" in correction

    def test_detects_claim_when_tool_returned_error(self):
        response = "The student was removed successfully."
        executed_tools = [
            {"name": "confirm_student_removal", "result": {"error": "DB connection failed"}},
        ]
        correction = check_false_claims(response, executed_tools)
        assert correction is not None
        assert "confirm_student_removal" in correction
