"""
BYOK (Bring Your Own Key) — Centralized API Key Resolver
=========================================================
Resolution order per request:
  1. contextvars (set by grading thread for child workers)
  2. Per-teacher stored keys (Supabase or file)
  3. District-level keys (for Clever district-managed accounts)
  4. Environment variables (Railway / .env fallback)

Thread safety: Uses contextvars.ContextVar which auto-propagates to
ThreadPoolExecutor child threads in Python 3.12+.
"""

import os
import time
import logging
import threading
from contextvars import ContextVar

logger = logging.getLogger(__name__)

# ── ContextVar for grading thread propagation ─────────────────
_thread_keys: ContextVar[dict | None] = ContextVar('_thread_keys', default=None)

# Provider → env var mapping
_ENV_MAP = {
    'openai': 'OPENAI_API_KEY',
    'anthropic': 'ANTHROPIC_API_KEY',
    'gemini': 'GEMINI_API_KEY',
}

# ── In-memory cache (teacher_id or district_id → {keys, ts}) ─
_cache: dict[str, dict] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 300  # 5 minutes


def _get_district_id() -> str:
    """Get the current user's district ID from Flask g, if available."""
    try:
        from flask import g
        return getattr(g, 'district_id', '') or ''
    except (ImportError, RuntimeError):
        return ''


def get_api_key(provider: str, teacher_id: str | None = None) -> str:
    """Get an API key for a provider.

    Resolution order:
      1. contextvars (grading thread context)
      2. Per-teacher stored keys (Supabase or file)
      3. District-level keys (Clever districts provide their own API keys)
      4. Environment variable fallback
    """
    provider = provider.lower()
    env_var = _ENV_MAP.get(provider)
    if not env_var:
        return ''

    # 1. Check contextvars (set in grading threads)
    ctx_keys = _thread_keys.get()
    if ctx_keys:
        val = ctx_keys.get(provider, '')
        if val:
            return val

    # 2. Check per-teacher stored keys
    if teacher_id and teacher_id != 'local-dev':
        user_keys = _load_user_keys(teacher_id)
        val = user_keys.get(provider, '')
        if val:
            return val

    # 3. Check district-level keys
    district_id = _get_district_id()
    if district_id:
        district_keys = _load_district_keys(district_id)
        val = district_keys.get(provider, '')
        if val:
            return val

    # 3b. Check district admin setup keys
    try:
        from backend.storage import load as _storage_load
        district_ai = _storage_load("district_ai_keys", "system")
        if district_ai:
            val = district_ai.get(provider, '')
            if val:
                return val
    except Exception:
        pass

    # 4. Fall back to env var
    return os.getenv(env_var, '')


def set_thread_keys(api_keys: dict):
    """Set API keys in contextvars for the current grading thread.

    Called at the start of run_grading_thread(). Auto-propagates
    to ThreadPoolExecutor child threads.
    """
    _thread_keys.set(api_keys)


def clear_thread_keys():
    """Clear API keys from contextvars at end of grading thread."""
    _thread_keys.set(None)


def resolve_keys_for_teacher(teacher_id: str) -> dict:
    """Pre-resolve all 3 provider keys for a teacher, with district + env fallback.

    Returns dict like {'openai': 'sk-...', 'anthropic': 'sk-...', 'gemini': 'AI...'}
    Used to snapshot keys before spawning grading thread.
    """
    user_keys = _load_user_keys(teacher_id) if teacher_id and teacher_id != 'local-dev' else {}
    district_id = _get_district_id()
    district_keys = _load_district_keys(district_id) if district_id else {}
    try:
        from backend.storage import load as _storage_load
        district_admin_keys = _storage_load("district_ai_keys", "system") or {}
    except Exception:
        district_admin_keys = {}
    resolved = {}
    for provider, env_var in _ENV_MAP.items():
        resolved[provider] = (
            user_keys.get(provider, '')
            or district_keys.get(provider, '')
            or district_admin_keys.get(provider, '')
            or os.getenv(env_var, '')
        )
    return resolved


def save_user_keys(teacher_id: str, keys: dict) -> bool:
    """Save (merge) user API keys to storage.

    Args:
        teacher_id: Teacher's Supabase UUID or 'local-dev'
        keys: Dict like {'openai': 'sk-...', 'anthropic': 'sk-ant-...'}
              Only non-empty values are merged; empty strings are skipped.

    Returns True on success.
    """
    from backend.storage import load, save

    existing = load('api_keys', teacher_id) or {}

    for provider in ('openai', 'anthropic', 'gemini'):
        val = keys.get(provider, '')
        if val:  # Only update if non-empty
            existing[provider] = val

    ok = save('api_keys', existing, teacher_id)

    # Invalidate cache
    with _cache_lock:
        _cache.pop(teacher_id, None)

    return ok


def check_user_keys(teacher_id: str) -> dict:
    """Check which API keys are configured for a teacher (never exposes values).

    Returns dict like:
      {
        'openai_configured': True,
        'openai_is_own': True,
        'openai_is_district': False,
        'anthropic_configured': True,
        'anthropic_is_own': False,
        'anthropic_is_district': True,
        ...
      }
    """
    user_keys = _load_user_keys(teacher_id) if teacher_id and teacher_id != 'local-dev' else {}
    district_id = _get_district_id()
    district_keys = _load_district_keys(district_id) if district_id else {}

    result = {}
    for provider, env_var in _ENV_MAP.items():
        has_own = bool(user_keys.get(provider, ''))
        has_district = bool(district_keys.get(provider, ''))
        has_env = bool(os.getenv(env_var, ''))
        result[f'{provider}_configured'] = has_own or has_district or has_env
        result[f'{provider}_is_own'] = has_own
        result[f'{provider}_is_district'] = has_district

    return result


def _load_user_keys(teacher_id: str) -> dict:
    """Load user keys from storage with 5-minute cache."""
    if not teacher_id:
        return {}

    with _cache_lock:
        cached = _cache.get(teacher_id)
        if cached and (time.time() - cached['ts']) < _CACHE_TTL:
            return cached['keys']

    from backend.storage import load
    keys = load('api_keys', teacher_id) or {}

    with _cache_lock:
        _cache[teacher_id] = {'keys': keys, 'ts': time.time()}
    return keys


# ══════════════════════════════════════════════════════════════
# DISTRICT-LEVEL API KEYS
# ══════════════════════════════════════════════════════════════
# Districts (via Clever) can set API keys that apply to all their teachers.
# Stored in Supabase teacher_data with a synthetic teacher_id of "district:{district_id}".
# This avoids a new table — reuses the existing KV store.

_DISTRICT_KEY_PREFIX = "district:"


def _load_district_keys(district_id: str) -> dict:
    """Load district-level API keys from storage with cache."""
    if not district_id:
        return {}

    cache_key = f"{_DISTRICT_KEY_PREFIX}{district_id}"
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and (time.time() - cached['ts']) < _CACHE_TTL:
            return cached['keys']

    from backend.storage import load
    keys = load('api_keys', cache_key) or {}

    with _cache_lock:
        _cache[cache_key] = {'keys': keys, 'ts': time.time()}
    return keys


def save_district_keys(district_id: str, keys: dict) -> bool:
    """Save (merge) district-level API keys.

    Args:
        district_id: The Clever district ID
        keys: Dict like {'openai': 'sk-...', 'anthropic': 'sk-ant-...'}
              Only non-empty values are merged; empty strings are skipped.

    Returns True on success.
    """
    from backend.storage import load, save

    cache_key = f"{_DISTRICT_KEY_PREFIX}{district_id}"
    existing = load('api_keys', cache_key) or {}

    for provider in ('openai', 'anthropic', 'gemini'):
        val = keys.get(provider, '')
        if val:
            existing[provider] = val

    ok = save('api_keys', existing, cache_key)

    # Invalidate cache
    with _cache_lock:
        _cache.pop(cache_key, None)

    if ok:
        logger.info("District API keys saved for %s", district_id)
    return ok


def check_district_keys(district_id: str) -> dict:
    """Check which API keys are configured at district level (never exposes values)."""
    if not district_id:
        return {}
    district_keys = _load_district_keys(district_id)
    return {
        f'{provider}_configured': bool(district_keys.get(provider, ''))
        for provider in _ENV_MAP
    }
