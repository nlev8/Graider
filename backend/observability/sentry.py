"""Sentry error tracking for Graider — PII-scrubbed, FERPA-safe.

Exposes:
  - before_send(event, hint)    → Sentry hook that scrubs PII
  - critical_path               → decorator (stub, populated in Task 4)
  - init_sentry()               → client init (stub, populated in Task 5)

See docs/superpowers/specs/2026-04-11-observability-sentry-betterstack-design.md.
"""

import hashlib
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# PII field names scrubbed from stack frame locals.
# Keep this list in sync with docs/observability.md § "Known noise sources".
_PII_LOCAL_NAMES = frozenset({
    "student_name", "student_email", "answers", "draft_answers",
    "student_id_number", "submission_row", "results", "feedback",
    "first_name", "last_name", "row", "s", "sdata", "assessment",
    "assessment_content", "student_row", "assessment_data",
})

# Query-param name fragments whose presence indicates a secret.
_SECRET_PARAM_MARKERS = ("token", "key", "secret", "password")

# Exception type names that represent client-side 4xx errors.
# These are dropped entirely — no point paging the developer about a
# garbage request body or an expired session.
_CLIENT_ERROR_TYPES = frozenset({
    "BadRequest", "Unauthorized", "Forbidden", "NotFound",
    "MethodNotAllowed", "UnprocessableEntity", "TooManyRequests",
})


def _is_client_error(event: dict) -> bool:
    """Return True if the event represents a 4xx client error that should be dropped."""
    try:
        exceptions = event.get("exception", {}).get("values", [])
        for exc in exceptions:
            if exc.get("type", "") in _CLIENT_ERROR_TYPES:
                return True
    except Exception:
        # Defensive: never let the scrubber crash — a broken scrubber
        # swallows events silently.
        pass
    return False


def _resolve_user_id() -> str:
    """Return a stable user identifier that is safe for PII-free correlation.

    Returns a 12-char sha256 hash of the Flask g.user_id when inside a
    Flask request context with a teacher attached; returns "anonymous"
    otherwise.

    MUST NOT raise. The Sentry before_send hook runs in many contexts
    (Flask request, background grading thread, Sentry SDK's own worker
    thread flushing events, import-time errors). Touching flask.g
    outside a request context raises RuntimeError, which would crash
    the scrubber and cause Sentry to drop the event entirely — the
    opposite of what we want. Every access to g is guarded.
    """
    try:
        from flask import has_request_context, g
    except ImportError:
        return "anonymous"

    try:
        if not has_request_context():
            return "anonymous"
    except RuntimeError:
        return "anonymous"

    try:
        uid = getattr(g, "user_id", None)
    except RuntimeError:
        return "anonymous"

    if not uid:
        return "anonymous"

    return hashlib.sha256(str(uid).encode()).hexdigest()[:12]


def _scrub_request(request: Optional[dict]) -> None:
    """Strip PII from the request dict on a Sentry event (in place)."""
    if not request:
        return

    # Drop body payloads entirely — they may contain student answers,
    # grading results, teacher notes, anything.
    for key in ("data", "json", "form", "cookies"):
        request.pop(key, None)

    # Redact auth-bearing headers.
    headers = request.get("headers")
    if isinstance(headers, dict):
        for header_key in list(headers.keys()):
            if header_key.lower() in ("authorization", "cookie"):
                headers[header_key] = "[Filtered]"

    # Strip query params whose names look like secrets.
    query = request.get("query_string")
    if isinstance(query, str) and query:
        parts = []
        for param in query.split("&"):
            if "=" in param:
                name, _value = param.split("=", 1)
            else:
                name = param
            if any(marker in name.lower() for marker in _SECRET_PARAM_MARKERS):
                parts.append(f"{name}=[Filtered]")
            else:
                parts.append(param)
        request["query_string"] = "&".join(parts)


def _scrub_frame_locals(event: dict) -> None:
    """Walk every stack frame and replace PII locals with a sentinel (in place)."""
    try:
        exceptions = event.get("exception", {}).get("values", [])
        for exc in exceptions:
            stacktrace = exc.get("stacktrace") or {}
            frames = stacktrace.get("frames", [])
            for frame in frames:
                frame_vars = frame.get("vars")
                if not isinstance(frame_vars, dict):
                    continue
                for name in list(frame_vars.keys()):
                    if name in _PII_LOCAL_NAMES:
                        frame_vars[name] = "[PII-scrubbed]"
    except Exception:
        # Defensive: never let the scrubber crash.
        pass


def before_send(event: dict, hint: dict) -> Optional[dict]:
    """Sentry before_send hook — scrubs PII and drops 4xx errors.

    Returning None drops the event entirely. Returning the (mutated)
    event forwards it to Sentry Cloud.
    """
    if _is_client_error(event):
        return None

    _scrub_request(event.get("request"))
    _scrub_frame_locals(event)

    user = event.setdefault("user", {})
    if isinstance(user, dict):
        user["id"] = _resolve_user_id()
        user.pop("email", None)
        user.pop("username", None)
        user.pop("ip_address", None)

    return event


def critical_path(fn):
    """Stub — populated by Task 4."""
    return fn


def init_sentry() -> None:
    """Stub — populated by Task 5."""
    pass
