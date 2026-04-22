"""Emit a structured log line per API request describing the effective
database access mode and authenticated identity source. Used to
measure traffic splits before and after the USE_PER_USER_JWT flag flip.

Uses backend.observability.events.emit() to serialize structured fields
as JSON inside the log message (for machine parsing by BetterStack, etc.).
"""
from __future__ import annotations

import os

from flask import Flask, g, request, session

from backend.observability.events import emit


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
            emit(
                "request.db_mode",
                path=request.path,
                method=request.method,
                status=response.status_code,
                auth_source=_classify_auth_source(),
                db_mode=_classify_db_mode(),
                user_id=getattr(g, "user_id", None),
            )
        return response
