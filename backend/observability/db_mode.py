"""Emit a structured log line per API request describing the effective
database access mode and authenticated identity source. Used to
measure traffic splits before and after the USE_PER_USER_JWT flag flip.

IMPORTANT — logging formatter compatibility: Graider's production
JsonFormatter (backend/utils/logging_utils.py) emits only
timestamp/level/logger/request_id/message/exception and drops any
``extra={...}`` keys passed to logging calls. Sentry uses
FlaskIntegration + CeleryIntegration only; no LoggingIntegration, so
extras don't flow to Sentry either.

Rather than changing the formatter (broad blast radius for a narrow
need), this module emits its fields as a JSON object embedded in the
log MESSAGE body. BetterStack and other aggregators parse
JSON-in-message and index the fields; the existing JsonFormatter
preserves the message as-is.

Trade-off: the message contains JSON-shaped text rather than a
human-readable sentence. Acceptable for a programmatic observability
event like db_mode; not a pattern to spread to every log line.
"""
from __future__ import annotations

import json
import logging
import os

from flask import Flask, g, request, session

_logger = logging.getLogger("backend.db_mode")


def _classify_auth_source() -> str:
    """Return one of: jwt | clever | classlink | student | dev | none.
    Mirrors the branch order in backend/auth.py's check_auth hook.
    """
    if getattr(g, "supabase_jwt", None):
        return "jwt"
    if "clever_user" in session:
        return "clever"
    if "classlink_user" in session:
        return "classlink"
    if request.headers.get("X-Student-Token"):
        return "student"
    if request.headers.get("X-Test-Teacher-Id"):
        return "dev"
    return "none"


def _classify_db_mode() -> str:
    """Return service_role | per_user_jwt."""
    if os.getenv("USE_PER_USER_JWT", "0") != "1":
        return "service_role"
    if getattr(g, "supabase_jwt", None):
        return "per_user_jwt"
    return "service_role"


def register(app: Flask) -> None:
    """Register the after_request logger. Called from backend/app.py."""

    @app.after_request
    def _log_db_mode(response):
        if request.path.startswith("/api/"):
            event = {
                "event": "request.db_mode",
                "path": request.path,
                "method": request.method,
                "status": response.status_code,
                "auth_source": _classify_auth_source(),
                "db_mode": _classify_db_mode(),
                "user_id": getattr(g, "user_id", None),
            }
            # JSON-in-message because JsonFormatter drops extras.
            _logger.info(json.dumps(event, default=str))
        return response
