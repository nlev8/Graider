"""
FERPA Compliance Audit Logging
==============================
Dual-writes audit entries to local file + Supabase.
Extracted from app.py to avoid circular imports when used by compliance utilities.
"""

import os
import logging
from datetime import datetime
import sentry_sdk

AUDIT_LOG_FILE = os.path.expanduser("~/.graider_audit.log")
logger = logging.getLogger(__name__)


def audit_log(action: str, details: str = "", user: str = "teacher", teacher_id: str = ""):
    """
    FERPA Compliance: Log all data access and modifications.
    Writes to both local file AND Supabase for persistence across deploys.
    Logs do not contain actual student data — only action metadata.
    """
    timestamp = datetime.now().isoformat()

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
        log_entry = f"{timestamp} | teacher={resolved_teacher_id} | {user} | {action} | {details[:500]}\n"
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
                'action': action,
                'details': details[:500],
                'user_type': user,
            }).execute()
    except Exception as e:
        pass  # Supabase unavailable — local file is the fallback
        sentry_sdk.capture_exception(e)
