"""
BYOK (Bring Your Own Key) — Centralized API Key Resolver
=========================================================
Resolution order per request:
  1. contextvars (set by grading thread for child workers)
  2. Supabase per-user keys (via storage.load)
  3. Environment variables (Railway / .env fallback)

Thread safety: Uses contextvars.ContextVar which auto-propagates to
ThreadPoolExecutor child threads in Python 3.12+.
"""

import os
import time
import logging
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

# ── In-memory cache (teacher_id → {keys, ts}) ────────────────
_cache: dict[str, dict] = {}
_CACHE_TTL = 300  # 5 minutes


def get_api_key(provider: str, teacher_id: str | None = None) -> str:
    """Get an API key for a provider.

    Resolution order:
      1. contextvars (grading thread context)
      2. Per-user stored keys (Supabase or file)
      3. Environment variable fallback
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

    # 2. Check per-user stored keys
    if teacher_id and teacher_id != 'local-dev':
        user_keys = _load_user_keys(teacher_id)
        val = user_keys.get(provider, '')
        if val:
            return val

    # 3. Fall back to env var
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
    """Pre-resolve all 3 provider keys for a teacher, with env fallback.

    Returns dict like {'openai': 'sk-...', 'anthropic': 'sk-...', 'gemini': 'AI...'}
    Used to snapshot keys before spawning grading thread.
    """
    user_keys = _load_user_keys(teacher_id) if teacher_id and teacher_id != 'local-dev' else {}
    resolved = {}
    for provider, env_var in _ENV_MAP.items():
        resolved[provider] = user_keys.get(provider, '') or os.getenv(env_var, '')
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
    _cache.pop(teacher_id, None)

    return ok


def check_user_keys(teacher_id: str) -> dict:
    """Check which API keys are configured for a teacher (never exposes values).

    Returns dict like:
      {
        'openai_configured': True,
        'openai_is_own': True,
        'anthropic_configured': True,
        'anthropic_is_own': False,
        ...
      }
    """
    user_keys = _load_user_keys(teacher_id) if teacher_id and teacher_id != 'local-dev' else {}

    result = {}
    for provider, env_var in _ENV_MAP.items():
        has_own = bool(user_keys.get(provider, ''))
        has_env = bool(os.getenv(env_var, ''))
        result[f'{provider}_configured'] = has_own or has_env
        result[f'{provider}_is_own'] = has_own

    return result


def _load_user_keys(teacher_id: str) -> dict:
    """Load user keys from storage with 5-minute cache."""
    if not teacher_id:
        return {}

    cached = _cache.get(teacher_id)
    if cached and (time.time() - cached['ts']) < _CACHE_TTL:
        return cached['keys']

    from backend.storage import load
    keys = load('api_keys', teacher_id) or {}

    _cache[teacher_id] = {'keys': keys, 'ts': time.time()}
    return keys
