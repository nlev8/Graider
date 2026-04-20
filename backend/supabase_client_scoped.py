"""Request-scoped Supabase client accessor for Phase 4.5.

Returns a per-user Supabase client when all three conditions hold:
  1. USE_PER_USER_JWT env var is "1"
  2. The current Flask request has a validated Supabase Bearer JWT
     (set on g.supabase_jwt by backend/auth.py's check_auth hook)
  3. SUPABASE_URL and SUPABASE_ANON_KEY are configured

Otherwise returns the existing service-role singleton unchanged,
guaranteeing zero behaviour change for non-migrated callers.

Do NOT import this from code paths that don't execute in a Flask
request context (Celery tasks, cron jobs, background threads). Those
must continue importing from backend.supabase_client directly. The
has_request_context() guard below gives a safe fallback, not a
sanctioned pattern.
"""
from __future__ import annotations

import os

from flask import g, has_request_context
from supabase import create_client
from supabase.lib.client_options import ClientOptions

from backend.supabase_client import get_supabase as _get_service_client
from backend.supabase_resilient import ResilientClient


def get_request_supabase():
    """Return the right Supabase client for the current request.

    See module docstring for decision rules. Never raises except when
    USE_PER_USER_JWT=1 AND a request has a JWT AND the required env
    vars are missing — that's a deployment misconfiguration and we
    fail loud rather than silently bypass RLS.
    """
    if os.getenv("USE_PER_USER_JWT", "0") != "1":
        return _get_service_client()

    if not has_request_context():
        # Called from a background path by mistake. Service-role.
        return _get_service_client()

    user_jwt = getattr(g, "supabase_jwt", None)
    if not user_jwt:
        # SSO session, student token, background — all land here.
        return _get_service_client()

    url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not anon_key:
        raise RuntimeError(
            "USE_PER_USER_JWT=1 requires SUPABASE_URL + SUPABASE_ANON_KEY "
            "to be configured. Set them on Railway before flipping the flag."
        )

    raw = create_client(
        url,
        anon_key,
        options=ClientOptions(
            auto_refresh_token=False,
            persist_session=False,
            headers={"Authorization": f"Bearer {user_jwt}"},
        ),
    )
    return ResilientClient(raw)
