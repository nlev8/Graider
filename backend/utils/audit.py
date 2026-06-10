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

from backend.utils.redaction import redact_email, redact_name

AUDIT_LOG_FILE = os.path.expanduser("~/.graider_audit.log")
logger = logging.getLogger(__name__)


# Closes audit MAJOR #10 (Codex full-codebase audit 2026-05-06): centralize
# PII redaction at the audit boundary. Before this change, FERPA posture
# depended on every caller self-redacting; cited example was
# `EMAIL_TEST_SEND` at backend/routes/email_routes.py:163 which passed raw
# email addresses into details. Now `_redact_for_audit()` runs on every
# `details` string + `action` string before it reaches either the local
# file or Supabase.
#
# CONTRACT SCOPE (round-3 Codex MEDIUM fold — expanded from PR #227 round 2;
# VB9 #20 added structured-name-field redaction):
#   - DEDUCTIVELY redacted: emails (a***@example.com), canonical UUIDs
#     (id=<sha:8>), long opaque hex tokens 32+ chars (hex=<sha:8>), and
#     STRUCTURED student-name fields using the `key=value` convention —
#     `student=`, `student_name=`, `name=` -> initials form (e.g.
#     `student=A*** J***`). VB9 #20: defense-in-depth so a caller that
#     forgets to self-redact a student name still cannot leak it verbatim.
#   - NOT REDACTED (caller responsibility — MUST sanitize at the call site):
#     - FREE-FORM names not in a `student=`/`name=` field (regex cannot infer
#       arbitrary name boundaries from prose), teacher/school names under
#       other keys (e.g. `teacher=`), free-form filenames or assignment
#       labels (e.g. "Alice_Smith.docx")
#     - Phone numbers, postal addresses, dates of birth, SSNs
#     - Raw IP addresses (use the geolocated source token if you must)
#     - Short identifiers <32 chars: `student_id[:6]`, custom preset IDs,
#       6-char join codes. These are intentionally untouched because the
#       SIS sprint emits sha256[:8] short hashes that look identical to
#       short hex IDs and must not be re-redacted.
#   - Regex-based redaction cannot infer name boundaries without context.
#     Callers passing PII outside the deductively-redacted set MUST
#     self-redact (e.g. use `student_id_hash` instead of `student_name`,
#     hash filenames, geolocate IP -> region token).
#   - The 3 historical bypass writers (`_audit_log` in assistant_routes,
#     `audit_log_accommodation` in accommodations, `_clever_audit` in
#     clever_routes) now delegate to this function so they get the same
#     pattern coverage. `_clever_audit` additionally pre-redacts before
#     emitting its `logger.info` debug line so Sentry breadcrumbs cannot
#     observe raw PII even if a downstream call later raises.

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

# VB9 #20 (FERPA): structured student-name fields. We CANNOT infer arbitrary
# name boundaries from free text (see CONTRACT SCOPE above) — but the audit
# writers that DO emit a student name use the `key=value` field convention
# (`student=`, `student_name=`, `name=`). This pattern redacts those values
# deterministically as a defense-in-depth backstop so a caller that forgets
# to self-redact a name still cannot leak it verbatim. Anchored on `\b` so
# `filename=`, `assignment=`, `teacher=` are NOT matched (different keys);
# the value runs up to the next ` key=` token or end of string.
_NAME_FIELD_PATTERN = re.compile(
    r"\b(student_name|student|name)=([^=]*?)(?=\s+\S+=|$)",
    re.IGNORECASE,
)


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

    def _replace_name_field(match: re.Match) -> str:
        key = match.group(1)
        redacted = redact_name(match.group(2).strip())
        return f"{key}={redacted}" if redacted else f"{key}="

    text = _EMAIL_PATTERN.sub(_replace_email, text)
    text = _UUID_PATTERN.sub(_replace_uuid, text)
    text = _LONG_HEX_PATTERN.sub(_replace_long_hex, text)
    text = _NAME_FIELD_PATTERN.sub(_replace_name_field, text)
    return text


def _get_audit_supabase():
    """Resolve the Supabase client used by the audit sink.

    Extracted from audit_log() as a single patchable seam (issue #731): the
    test suite autouse-patches this function (tests/conftest.py
    `_isolate_audit_supabase_sink`) so a local pytest run can never insert
    fixture rows into the LIVE audit_log table when the developer .env
    carries production Supabase credentials. Production behavior is
    unchanged — both historical import paths are preserved.
    """
    try:
        from backend.supabase_client import get_supabase
    except ImportError:
        from supabase_client import get_supabase
    return get_supabase()


def audit_log(action: str, details: str = "", user: str = "teacher", teacher_id: str = ""):
    """
    FERPA Compliance: Log all data access and modifications.
    Writes to both local file AND Supabase for persistence across deploys.

    Audit MAJOR #10 closure (Codex 2026-05-06; round-2 narrowed PR #227):
    the `details` and `action` strings are passed through
    `_redact_for_audit()` before any write. The helper REDUCES — but does
    not eliminate — caller responsibility for PII hygiene.

    Coverage (deductive regex):
      - Emails -> "a***@example.com"
      - Canonical UUIDs (8-4-4-4-12 hex) -> "id=<sha256[:8]>"
      - Long opaque hex tokens 32+ chars -> "hex=<sha256[:8]>"
      - Structured student-name fields (`student=`/`student_name=`/`name=`)
        -> initials form (e.g. "student=A*** J***")  [VB9 #20]

    NOT covered (caller MUST sanitize at the call site):
      - Free-form names not in a `student=`/`name=` field, teacher / school
        names under other keys (e.g. `teacher=`)
      - Free-form filenames or assignment labels (e.g. "Alice_Smith.docx")
      - Phone numbers, postal addresses, dates of birth, SSNs
      - Raw IP addresses
      - Short identifiers <32 chars (e.g. `student_id[:6]` prefixes —
        intentionally not double-hashed because the SIS sprint emits its
        own sha256[:8] short hashes that look identical and must not be
        re-redacted)

    See `tests/test_audit_redaction.py::test_names_remain_caller_responsibility_documented_gap`
    for the pinned acknowledged-gap contract.
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
        sb = _get_audit_supabase()
        if sb:
            sb.table('audit_log').insert({
                'timestamp': timestamp,
                'teacher_id': resolved_teacher_id,
                'action': safe_action,
                'details': safe_details[:500],
                'user_type': user,
            }).execute()
    except Exception as e:
        # Supabase unavailable — the local file is the fallback. Record to
        # Sentry AND logs (class name only; audit details may contain PII).
        sentry_sdk.capture_exception(e)
        logger.warning("Audit DB insert failed: %s", type(e).__name__)
