"""Sentry error tracking for Graider — PII-scrubbed, FERPA-safe.

This module is populated incrementally by subsequent plan tasks.
Tasks 2-3 fill in before_send and _resolve_user_id.
Task 4 fills in critical_path.
Task 5 fills in init_sentry.
"""


def init_sentry() -> None:
    """Stub — populated by Task 5."""
    pass


def critical_path(fn):
    """Stub — populated by Task 4."""
    return fn
