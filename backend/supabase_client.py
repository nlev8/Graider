"""
Canonical Supabase client for Graider.
All modules should import from here instead of creating their own clients.

Provides three variants:
  - get_supabase()          → returns resilient client or None (lenient, for optional features)
  - get_supabase_or_raise() → returns resilient client or raises Exception (strict, for required features)
  - get_raw_supabase()      → returns the unwrapped raw client (opt-out for streaming / custom retry / healthchecks)
"""
import os
from supabase import create_client, Client

_supabase_raw: Client = None
_supabase_resilient = None


def get_raw_supabase() -> Client:
    """Lazy-init raw Supabase admin client WITHOUT retry wrapping.

    Use this only when you need the underlying client — e.g. for long-running
    streaming queries, custom retry logic, or healthchecks that must fail fast.
    Most callers should use get_supabase() or get_supabase_or_raise() instead.
    """
    global _supabase_raw
    if _supabase_raw is None:
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_KEY')
        if url and key:
            _supabase_raw = create_client(url, key)
    return _supabase_raw


def get_supabase():
    """Lazy-init Supabase admin client with automatic retry wrapping.

    Returns a ResilientClient instance (behaves like the raw client but
    every .execute() call is routed through operation-aware retry), or None
    if not configured.
    """
    global _supabase_resilient
    if _supabase_resilient is None:
        raw = get_raw_supabase()
        if raw is not None:
            from backend.supabase_resilient import ResilientClient
            _supabase_resilient = ResilientClient(raw)
    return _supabase_resilient


def get_supabase_or_raise():
    """Lazy-init resilient Supabase client. Raises if not configured."""
    client = get_supabase()
    if client is None:
        raise Exception("Supabase credentials not configured. Check SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")
    return client
