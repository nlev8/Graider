"""Regression guard: Sentry PII scrubbing hardening (Phase 4 review findings).

Claude 4.7's fresh-eyes pass found that the original `_PII_LOCAL_NAMES`
allowlist (in backend/observability/sentry.py) missed several locals used
by roster and assistant-tool code paths — on any exception, literal
student names + SIS IDs would appear in Sentry frame `vars`. FERPA risk.

Primary fix: `include_local_variables=False` in sentry_sdk.init() — drops
ALL frame locals from events, regardless of name. The allowlist is
belt-and-suspenders for any future toggle.

These tests pin both layers.
"""
from __future__ import annotations

import ast
import pathlib


def _sentry_source() -> str:
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    return (repo_root / "backend" / "observability" / "sentry.py").read_text(encoding="utf-8")


def test_sentry_init_passes_include_local_variables_false():
    """`include_local_variables=False` must be present in the sentry_sdk.init() call.

    Without it, sentry-sdk's default is to attach frame locals to events, which
    would leak PII regardless of how comprehensive the scrubber allowlist is.
    """
    source = _sentry_source()
    tree = ast.parse(source)

    init_calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Match both `sentry_sdk.init(...)` and `init(...)` after `from sentry_sdk import init`.
        matched = (
            (isinstance(func, ast.Attribute) and func.attr == "init"
             and isinstance(func.value, ast.Name) and func.value.id == "sentry_sdk")
            or (isinstance(func, ast.Name) and func.id == "init")
        )
        if matched:
            init_calls.append(node)

    assert init_calls, "No sentry_sdk.init() call found in backend/observability/sentry.py"

    for call in init_calls:
        kwarg_names = {kw.arg for kw in call.keywords if kw.arg is not None}
        assert "include_local_variables" in kwarg_names, (
            "sentry_sdk.init() must pass include_local_variables=False to prevent "
            "FERPA-protected student data from leaking into Sentry frame vars."
        )
        # Also assert the value is literal False
        for kw in call.keywords:
            if kw.arg == "include_local_variables":
                assert isinstance(kw.value, ast.Constant) and kw.value.value is False, (
                    "include_local_variables must be the literal False, not a computed value."
                )


def test_pii_allowlist_covers_known_leak_sites():
    """`_PII_LOCAL_NAMES` must include every local variable the reviewer flagged.

    These names were empirically reachable by Sentry's default frame capture
    in backend/services/assistant_tools.py (roster CSV loop at :705-728) and
    backend/services/assistant_tools_student.py (delete_student_data at :498-528).
    """
    from backend.observability.sentry import _PII_LOCAL_NAMES

    required = {
        # Roster CSV loop locals
        "first", "last", "display_name", "student_id", "grade",
        # delete_student_data locals
        "matched_name", "matched_id", "safe_id", "roster", "grading_state",
        # Fuzzy match iteration locals
        "rname", "entry",
    }
    missing = required - _PII_LOCAL_NAMES
    assert not missing, (
        f"`_PII_LOCAL_NAMES` is missing PII variable names surfaced by the "
        f"Phase-4 review: {sorted(missing)}. Add them to the allowlist in "
        f"backend/observability/sentry.py."
    )


def test_scrubber_masks_new_pii_names():
    """Runtime check: the scrubber replaces every newly-added PII name with the sentinel."""
    from backend.observability.sentry import before_send

    event = {
        "exception": {"values": [{
            "type": "RuntimeError",
            "value": "test",
            "stacktrace": {"frames": [{"vars": {
                "first": "Ana",
                "last": "Ramirez",
                "display_name": "Ana Ramirez",
                "student_id": "SID12345",
                "grade": "10",
                "matched_name": "Ana Ramirez",
                "matched_id": "SID12345",
                "safe_id": "ana_ramirez",
                "roster": [{"name": "Ana", "student_id": "SID12345"}],
                "grading_state": {"results": [{"student_name": "Ana"}]},
                "rname": "Ana Ramirez",
                "entry": {"student_id": "SID12345", "name": "Ana"},
                # Non-PII local — must survive
                "retry_count": 3,
            }}]},
        }]},
        "user": {},
    }

    result = before_send(event, {})
    assert result is not None
    frame_vars = result["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]

    pii_keys = {
        "first", "last", "display_name", "student_id", "grade",
        "matched_name", "matched_id", "safe_id", "roster", "grading_state",
        "rname", "entry",
    }
    for key in pii_keys:
        assert frame_vars[key] == "[PII-scrubbed]", (
            f"'{key}' was not scrubbed — got {frame_vars[key]!r}"
        )
    # Non-PII retained as-is
    assert frame_vars["retry_count"] == 3


def test_scrubber_preserves_preset_hashed_user_id():
    """Celery workers set_user with sha256[:12] before raising; scrubber must
    preserve that rather than overwrite with _resolve_user_id()'s "anonymous"
    (which is what happens when there's no Flask context in a worker process).

    Without this branch, task-level user attribution is useless — every Celery
    event shows user.id="anonymous".
    """
    import hashlib
    from backend.observability.sentry import before_send

    hashed = hashlib.sha256(b"teacher-xyz").hexdigest()[:12]
    event = {
        "exception": {"values": [{"type": "RuntimeError", "value": "test"}]},
        "user": {"id": hashed},  # simulates task's sentry_sdk.set_user call
    }
    result = before_send(event, {})
    assert result is not None
    assert result["user"]["id"] == hashed, (
        f"Expected hashed id {hashed!r} to be preserved; got {result['user']['id']!r}"
    )


def test_scrubber_replaces_non_hash_preset_user_id():
    """Defense in depth: if something non-hashed (raw email, username) somehow
    reached user.id, scrubber still replaces it so PII can't survive into
    Sentry Cloud through this channel.
    """
    from backend.observability.sentry import before_send

    event = {
        "exception": {"values": [{"type": "RuntimeError", "value": "test"}]},
        "user": {"id": "teacher@example.com"},  # raw email — must not survive
    }
    result = before_send(event, {})
    assert result is not None
    assert result["user"]["id"] != "teacher@example.com"
    # Expect the anonymous fallback since there's no Flask context
    assert result["user"]["id"] == "anonymous"


def test_scrubber_replaces_preset_id_with_wrong_length():
    """13-char string looks hex but wrong length — still replaced."""
    from backend.observability.sentry import before_send

    event = {
        "exception": {"values": [{"type": "RuntimeError", "value": "test"}]},
        "user": {"id": "abcdef1234567"},  # 13 chars, valid hex, wrong length
    }
    result = before_send(event, {})
    assert result["user"]["id"] == "anonymous"
