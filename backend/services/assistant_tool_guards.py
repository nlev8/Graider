"""
assistant_tool_guards.py — Guarded action registry and helpers.

Provides:
  - GUARDED_ACTIONS: registry of tools requiring verification
  - get_verification_message: returns injection string after guarded tool runs
  - check_false_claims: scans AI response for false delivery claims
"""

import re

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

GUARDED_ACTIONS = {
    "send_focus_comms": {
        "type": "preview_confirm",
        "success_key": "NOT_SENT",
        "confirm_tool": "confirm_and_send",
    },
    "send_parent_emails": {
        "type": "preview_confirm",
        "success_key": "NOT_SENT",
        "confirm_tool": "confirm_and_send",
    },
    "send_behavior_email": {
        "type": "preview_confirm",
        "success_key": "NOT_SENT",
        "confirm_tool": "confirm_and_send",
    },
    "confirm_and_send": {
        "type": "verify_result",
        "success_key": "status",
        "success_value": "started",
        "claim_phrases": [
            "has been sent",
            "was sent",
            "successfully sent",
            "email sent",
            "message sent",
            "email has been delivered",
            "messages were sent",
            "has been delivered",
            "sending via",
            "sending to",
        ],
    },
    "remove_student_from_roster": {
        "type": "preview_confirm",
        "success_key": "PENDING_CONFIRMATION",
        "confirm_tool": "confirm_student_removal",
    },
    "confirm_student_removal": {
        "type": "verify_result",
        "success_key": "status",
        "success_value": "removed",
        "claim_phrases": [
            "has been removed",
            "was removed",
            "successfully removed",
            "data cleared",
            "been deleted",
            "was deleted",
            "successfully deleted",
            "records removed",
        ],
    },
    "create_focus_assignment": {
        "type": "verify_result",
        "success_key": "status",
        "success_value": "launched",
        "claim_phrases": [
            "assignment created",
            "created assignment",
            "has been created in Focus",
        ],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_verification_message(tool_name: str, tool_result: dict) -> str | None:
    """Return a verification string to inject after a guarded tool executes.

    Returns None if the tool is not in GUARDED_ACTIONS.
    """
    entry = GUARDED_ACTIONS.get(tool_name)
    if entry is None:
        return None

    action_type = entry["type"]

    if action_type == "preview_confirm":
        return (
            "[SYSTEM NOTE — NOT visible to the user] "
            "This action has NOT been executed. The tool returned a preview only. "
            "Show the preview to the user and ask for explicit confirmation before proceeding."
        )

    if action_type == "verify_result":
        success_key = entry["success_key"]
        success_value = entry["success_value"]

        error = tool_result.get("error")
        if error:
            return (
                f"[SYSTEM NOTE — NOT visible to the user] "
                f"FAILED: The action did not complete. Error: {error}. "
                f"Do NOT claim success. Inform the user of the failure."
            )

        actual_value = tool_result.get(success_key)
        if actual_value == success_value:
            return (
                f"[SYSTEM NOTE — NOT visible to the user] "
                f"SUCCESS: The action completed with {success_key}={success_value!r}. "
                f"You may confirm success to the user."
            )

        return (
            f"[SYSTEM NOTE — NOT visible to the user] "
            f"UNEXPECTED STATUS: Expected {success_key}={success_value!r} but got "
            f"{success_key}={actual_value!r}. Do NOT claim success. "
            f"Inform the user of the unexpected result."
        )

    return None


def check_false_claims(response_text: str, executed_tools: list) -> str | None:
    """Scan AI response text for false delivery claims.

    Parameters
    ----------
    response_text:
        The text the AI is about to return to the user.
    executed_tools:
        List of dicts with keys ``name`` (str) and ``result`` (dict),
        representing every tool that was called in this turn.

    Returns
    -------
    A correction string if a false claim is detected, otherwise None.
    """
    # Build a quick lookup: tool_name -> result for verify_result tools only
    called_results: dict[str, dict] = {}
    for call in executed_tools:
        name = call.get("name", "")
        if name in GUARDED_ACTIONS and GUARDED_ACTIONS[name]["type"] == "verify_result":
            called_results[name] = call.get("result", {})

    for tool_name, entry in GUARDED_ACTIONS.items():
        if entry["type"] != "verify_result":
            continue

        for phrase in entry["claim_phrases"]:
            pattern = re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
            if not pattern.search(response_text):
                continue

            # Phrase found — check if the tool was actually called and succeeded
            if tool_name not in called_results:
                return (
                    f"[SYSTEM CORRECTION] The response claims '{phrase}' but the tool "
                    f"'{tool_name}' was never called in this turn. "
                    f"Do NOT make this claim. Correct your response."
                )

            result = called_results[tool_name]
            success_key = entry["success_key"]
            success_value = entry["success_value"]
            error = result.get("error")
            actual_value = result.get(success_key)

            if error or actual_value != success_value:
                return (
                    f"[SYSTEM CORRECTION] The response claims '{phrase}' but the tool "
                    f"'{tool_name}' did not succeed (got error={error!r}, "
                    f"{success_key}={actual_value!r}). "
                    f"Do NOT claim success. Correct your response."
                )

    return None
