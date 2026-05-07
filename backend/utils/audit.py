"""
FERPA Compliance Audit Logging
==============================
Dual-writes audit entries to local file + Supabase.
Extracted from app.py to avoid circular imports when used by compliance utilities.
"""

import hashlib
import os
import logging
import re
from datetime import datetime
import sentry_sdk

from backend.utils.redaction import redact_email

AUDIT_LOG_FILE = os.path.expanduser("~/.graider_audit.log")
logger = logging.getLogger(__name__)


# Closes audit MAJOR #10 (Codex full-codebase audit 2026-05-06): centralize
# PII redaction at the audit boundary. Before this change, FERPA posture
# depended on every caller self-redacting; cited example was
# `EMAIL_TEST_SEND` at backend/routes/email_routes.py:163 which passed raw
# email addresses into details. Now `_redact_for_audit()` runs on every
# `details` string + `action` string before it reaches either the local
# file or Supabase.

# Email pattern — replaces full address with redact_email() form.
# Conservative: requires `@` plus a domain with at least one dot.
_EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"
)

# UUID v1-v5 pattern (Clever IDs, Supabase row IDs, submission IDs).
# Standard 8-4-4-4-12 hex with hyphens, case-insensitive.
_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)

# Long opaque hex tokens (32+ chars) — likely session tokens, hashed
# values, or Clever-style IDs. NOT 8-char SHA prefixes (those ARE the
# redaction output and must not be re-redacted).
_LONG_HEX_PATTERN = re.compile(r"\b[0-9a-fA-F]{32,}\b")


def _hash_short(value: str) -> str:
    """Return an 8-char sha256 prefix — same redaction shape as the SIS
    sprint pattern (see backend/clever.py uses)."""
    return hashlib.sha256(str(value).encode()).hexdigest()[:8]


def _redact_for_audit(text: str) -> str:
    """Strip PII from an audit-log details / action string.

    Centralizes the FERPA redaction contract that callers used to be
    responsible for. Apply order matters: emails first (so the @ doesn't
    confuse the UUID pattern), then UUIDs, then long hex tokens.

    Non-PII content (counts, error labels, action names, status codes)
    is preserved.
    """
    if not isinstance(text, str) or not text:
        return text

    def _replace_email(match: re.Match) -> str:
        return redact_email(match.group(0))

    def _replace_uuid(match: re.Match) -> str:
        return f"id={_hash_short(match.group(0))}"

    def _replace_long_hex(match: re.Match) -> str:
        return f"hex={_hash_short(match.group(0))}"

    text = _EMAIL_PATTERN.sub(_replace_email, text)
    text = _UUID_PATTERN.sub(_replace_uuid, text)
    text = _LONG_HEX_PATTERN.sub(_replace_long_hex, text)
    return text


def audit_log(action: str, details: str = "", user: str = "teacher", teacher_id: str = ""):
    """
    FERPA Compliance: Log all data access and modifications.
    Writes to both local file AND Supabase for persistence across deploys.

    Audit MAJOR #10 closure (Codex 2026-05-06): the `details` and `action`
    strings are passed through `_redact_for_audit()` before any write, so
    callers no longer need to self-redact. Emails get the `redact_email()`
    treatment ("a***@example.com"); UUIDs and long hex tokens get
    sha256[:8]-hashed.
    """
    timestamp = datetime.now().isoformat()

    # Centralized redaction — apply before truncation so we never split
    # a partially-redacted email across the 500-char boundary.
    safe_action = _redact_for_audit(action)
    safe_details = _redact_for_audit(details)

    # Resolve teacher_id — prefer explicit, fall back to Flask g.user_id
    resolved_teacher_id = teacher_id
    if not resolved_teacher_id:
        try:
            from flask import g
            resolved_teacher_id = getattr(g, 'user_id', 'unknown')
        except (ImportError, RuntimeError):
            resolved_teacher_id = 'unknown'

    # Local file (immediate, always works)
    try:
        # Format: timestamp | user | action | details | teacher={teacher_id}
        # teacher_id appended LAST so existing 4-field readers (e.g., the
        # /api/ferpa/audit-log endpoint at backend/app.py:265) still parse
        # the first four fields correctly. New 5-field readers can pick up
        # teacher_id from parts[4].
        log_entry = f"{timestamp} | {user} | {safe_action} | {safe_details[:500]} | teacher={resolved_teacher_id}\n"
        with open(AUDIT_LOG_FILE, 'a') as f:
            f.write(log_entry)
    except Exception as e:
        sentry_sdk.capture_exception(e)

    # Supabase (persistent across deploys)
    try:
        try:
            from backend.supabase_client import get_supabase
        except ImportError:
            from supabase_client import get_supabase
        sb = get_supabase()
        if sb:
            sb.table('audit_log').insert({
                'timestamp': timestamp,
                'teacher_id': resolved_teacher_id,
                'action': safe_action,
                'details': safe_details[:500],
                'user_type': user,
            }).execute()
    except Exception as e:
        pass  # Supabase unavailable — local file is the fallback
        sentry_sdk.capture_exception(e)
