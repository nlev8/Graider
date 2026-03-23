"""
FERPA/Clever Compliance Utilities
=================================
Centralized compliance primitives for assistant tools:
- require_teacher_id: Guard against unscoped data access
- audit_tool_action: Standardized audit logging for tool operations
- anonymize_for_ai / deanonymize: Strip/restore student PII for external AI calls
"""

import re
import os
import logging

logger = logging.getLogger(__name__)


def _is_supabase_configured():
    return bool(os.getenv('SUPABASE_URL') and os.getenv('SUPABASE_SERVICE_KEY'))


def require_teacher_id(teacher_id):
    """Guard: raise ValueError if teacher_id is missing or invalid in production.

    Allows 'local-dev' when:
    - Supabase is NOT configured (pure local dev), OR
    - FLASK_ENV is 'development' or 'testing' (dev/test with Supabase credentials present)

    Blocks 'local-dev' only in actual production (Supabase configured + FLASK_ENV not dev/test).
    """
    if not teacher_id:
        raise ValueError("teacher_id is required for data access")
    if teacher_id == 'local-dev' and _is_supabase_configured():
        env = os.getenv('FLASK_ENV', '').lower()
        if env not in ('development', 'dev', 'testing', 'test'):
            raise ValueError("local-dev teacher_id not allowed when Supabase is configured in production")


def audit_tool_action(teacher_id, tool_name, action, details=None):
    """Log a tool action to the FERPA audit trail.

    Actions: INVOKE, EXPORT, DELETE, SEND_EMAIL, SEND_AI, MODIFY_DATA
    """
    from backend.utils.audit import audit_log
    formatted_action = f"TOOL_{tool_name}_{action}"
    safe_details = _strip_pii_from_details(details or "")
    audit_log(formatted_action, safe_details, user="teacher", teacher_id=teacher_id)


def _strip_pii_from_details(details):
    """Remove potential student names from audit detail strings."""
    # Replace patterns like "for Maria Garcia" or "student Maria Garcia"
    # This is a best-effort strip — the audit log should never contain full names
    cleaned = re.sub(r'(?:for|student|name[=:])\s*[A-Z][a-z]+\s+[A-Z][a-z]+', 'student_***', details)
    return cleaned[:500]


def anonymize_for_ai(text, roster=None):
    """Replace student names with tokens before sending to external AI.

    Args:
        text: Text containing student PII
        roster: List of dicts with 'student_name' key. REQUIRED in production.

    Returns:
        (anonymized_text, mapping_dict) where mapping_dict maps tokens to real names
    """
    if roster is None:
        if _is_supabase_configured():
            raise ValueError("roster is required for anonymization in production mode")
        logger.warning("anonymize_for_ai called without roster in dev mode — limited anonymization")
        return text, {}

    mapping = {}
    anonymized = text
    counter = 1

    for student in roster:
        name = student.get('student_name', '')
        if not name:
            continue
        token = f"[STUDENT_{counter}]"

        # Handle "First Last" format
        if name in anonymized:
            anonymized = anonymized.replace(name, token)
            mapping[token] = name
            counter += 1
            continue

        # Handle "Last, First" format
        parts = [p.strip() for p in name.split(',')]
        if len(parts) == 2:
            reversed_name = f"{parts[1]} {parts[0]}"
            if reversed_name in anonymized:
                anonymized = anonymized.replace(reversed_name, token)
                mapping[token] = name
                counter += 1
                continue
            if name in anonymized:
                anonymized = anonymized.replace(name, token)
                mapping[token] = name
                counter += 1
                continue

        # Try individual name parts for possessives like "Maria's" or partial references
        name_parts = name.replace(',', '').split()
        found = False
        for part in name_parts:
            if len(part) > 2 and part in anonymized:
                anonymized = anonymized.replace(part, token)
                found = True
        if found and token not in mapping:
            mapping[token] = name
            counter += 1

    return anonymized, mapping


def deanonymize(text, mapping):
    """Restore student names from anonymization tokens."""
    result = text
    for token, name in mapping.items():
        result = result.replace(token, name)
    return result
