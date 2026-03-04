"""
Canonical Supabase client for Graider.
All modules should import from here instead of creating their own clients.

Provides two variants:
  - get_supabase()          → returns client or None (lenient, for optional features)
  - get_supabase_or_raise() → returns client or raises Exception (strict, for required features)
"""
import os
from supabase import create_client, Client

_supabase: Client = None


def get_supabase() -> Client:
    """Lazy-init Supabase admin client. Returns None if not configured."""
    global _supabase
    if _supabase is None:
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_KEY')
        if url and key:
            _supabase = create_client(url, key)
    return _supabase


def get_supabase_or_raise() -> Client:
    """Lazy-init Supabase admin client. Raises if not configured."""
    client = get_supabase()
    if client is None:
        raise Exception("Supabase credentials not configured. Check SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")
    return client
