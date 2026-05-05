"""
ClassLink OIDC discovery + JWKS client cache.

Lazily fetches https://launchpad.classlink.com/.well-known/openid-configuration
on first use and caches for 1 hour. JWKS client is cached alongside.

Thread-safety note: Python's GIL makes single-key dict writes atomic, so the
module-level cache dict does not need an explicit lock for correctness under
Flask's threaded server. A brief double-fetch window under high concurrency is
acceptable for a 1-hour TTL.
"""
import logging
import time
from typing import Any, Optional

import httpx
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

CLASSLINK_DISCOVERY_URL = (
    "https://launchpad.classlink.com/.well-known/openid-configuration"
)
_DISCOVERY_TTL_SECONDS = 3600

_cached_config: Optional[dict] = None
_cached_at: float = 0.0
_cached_jwks_client: Optional[PyJWKClient] = None


def _reset_cache_for_tests() -> None:
    """Reset module-level cache. Must only be called from tests."""
    global _cached_config, _cached_at, _cached_jwks_client
    _cached_config = None
    _cached_at = 0.0
    _cached_jwks_client = None


def get_classlink_oidc_config() -> dict[str, Any]:
    """Return discovered OIDC config, cached for _DISCOVERY_TTL_SECONDS.

    Raises RuntimeError if the discovery endpoint returns a non-200 status.
    """
    global _cached_config, _cached_at
    now = time.time()
    if _cached_config and (now - _cached_at) < _DISCOVERY_TTL_SECONDS:
        return _cached_config
    resp = httpx.get(CLASSLINK_DISCOVERY_URL, timeout=10.0)
    if resp.status_code != 200:
        raise RuntimeError(
            f"ClassLink OIDC discovery failed: {resp.status_code}"
        )
    _cached_config = resp.json()
    _cached_at = now
    _invalidate_jwks_client()
    return _cached_config


def _invalidate_jwks_client() -> None:
    """Evict the cached JWKS client so it is rebuilt against the fresh jwks_uri."""
    global _cached_jwks_client
    _cached_jwks_client = None


def get_classlink_jwks_client() -> PyJWKClient:
    """Return PyJWKClient pointed at the discovered jwks_uri.

    Raises RuntimeError if the OIDC config is missing jwks_uri.
    """
    global _cached_jwks_client
    if _cached_jwks_client is not None:
        return _cached_jwks_client
    cfg = get_classlink_oidc_config()
    jwks_uri = cfg.get("jwks_uri")
    if not jwks_uri:
        raise RuntimeError("ClassLink OIDC config missing jwks_uri")
    _cached_jwks_client = PyJWKClient(jwks_uri)
    return _cached_jwks_client
