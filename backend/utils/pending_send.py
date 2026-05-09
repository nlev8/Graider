"""Shared pending-send helpers (per-tenant filesystem fallback paths).

Several assistant tools save a "pending action" preview to disk that the
teacher then confirms via a follow-up tool call:

  * `assistant_tools_student.remove_student_from_roster` →
    `confirm_student_removal`
  * `assistant_tools_reports.send_parent_emails` /
    `send_focus_comms` → `confirm_and_send`
  * `assistant_tools_behavior.send_behavior_email` → `confirm_and_send`

The supabase-backed storage layer is already tenant-namespaced, but
prior to GH #280 every writer also wrote to a single global filesystem
fallback at `~/.graider_data/pending_send.json`. That global file was
the source of two CRITICAL vulnerabilities:

  1. **Tenant clobber** — Teacher A's preview overwrote Teacher B's.
  2. **Cross-tenant IDOR** — confirm-tools that fell back to filesystem
     could read another teacher's pending action and execute it under
     the caller's session.

`pending_send_path(teacher_id)` returns a per-tenant filesystem path
(`~/.graider_data/pending_send_{sanitized_tid}.json`). The
`sanitize_tenant_for_path()` helper guards against path traversal
(`..`, `/`, etc.) and caps length so a malicious or buggy teacher_id
can't escape `.graider_data`.

Defense-in-depth note: callers MUST also validate
`pending.get("teacher_id") == caller_teacher_id` before executing —
namespacing alone doesn't protect against payloads that may have
been written before the refactor or from other code paths. See
`assert_pending_belongs_to(...)` for the validation helper.

Originally introduced for student-removal in PR #279, then extracted
to this shared module in the GH #280 cross-module fix PR.
"""
from __future__ import annotations

import os
import re

import sentry_sdk


def sanitize_tenant_for_path(teacher_id) -> str:
    """Return a filesystem-safe representation of a teacher_id.

    Replaces any character that isn't alphanumeric / hyphen / underscore
    with `_` and caps length at 64. Coerces to `str` first so non-string
    inputs (int, None) don't raise TypeError.

    Returns "local-dev" if input is empty or None.
    """
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", str(teacher_id or "local-dev"))
    return safe[:64] or "local-dev"


def pending_send_path(teacher_id) -> str:
    """Return the per-tenant filesystem fallback path.

    Example: teacher_id="abc-123" → "~/.graider_data/pending_send_abc-123.json"
    Example: teacher_id="../etc"  → "~/.graider_data/pending_send____etc.json"

    Always namespaced — never returns the legacy global path.
    """
    safe_tid = sanitize_tenant_for_path(teacher_id)
    return os.path.expanduser(f"~/.graider_data/pending_send_{safe_tid}.json")


def assert_pending_belongs_to(pending: dict, caller_teacher_id) -> dict | None:
    """Validate that a pending payload's `teacher_id` matches the caller's.

    Args:
        pending: the loaded pending payload dict (from storage or file)
        caller_teacher_id: the teacher_id of the user invoking the
            confirm tool

    Returns:
        - None if the pending belongs to the caller (proceed)
        - An error dict (`{"error": "..."}`) if there's a tenant mismatch.
          Also fires a sentry warning capture so cross-tenant attempts
          are visible in observability.

    Caller pattern:
        err = assert_pending_belongs_to(pending, teacher_id)
        if err is not None:
            return err
        # ... proceed with execution

    Defense-in-depth: this check is required EVEN when the storage
    layer is already tenant-namespaced. If a malformed or legacy
    pending payload bypasses the storage filter (or arrives via the
    filesystem fallback before this PR's namespacing), the check at
    confirm-time is the last defense.

    Backward-compat: if `pending.get("teacher_id")` is missing or
    falsy AND `caller_teacher_id` is also "local-dev", we treat it
    as a legacy/dev payload and allow it (so existing dev workflows
    don't break). For any non-local-dev caller, missing tenant info
    in the payload is an error (because newer writers always inject it).
    """
    pending_tid = pending.get("teacher_id")

    # Legacy / local-dev path: missing pending teacher_id + local-dev
    # caller is allowed (pre-injection payloads, dev mode).
    if not pending_tid and caller_teacher_id == "local-dev":
        return None

    if pending_tid != caller_teacher_id:
        sentry_sdk.capture_message(
            f"Cross-tenant pending-send attempt blocked: "
            f"caller={caller_teacher_id} pending={pending_tid!r}",
            level="warning",
        )
        return {
            "error": (
                "Pending action belongs to a different teacher. "
                "Only the teacher who initiated the preview can confirm it. "
                "Generate a new preview first."
            )
        }
    return None
