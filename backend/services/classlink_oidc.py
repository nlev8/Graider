"""
ClassLink OIDC discovery + JWKS client cache.

Lazily fetches https://launchpad.classlink.com/.well-known/openid-configuration
on first use and caches for 1 hour. JWKS client is cached alongside.

Thread-safety: under cold-cache concurrency, two parallel callers can both
issue the discovery GET. That brief double-fetch window is acceptable for a
1-hour TTL endpoint. Do NOT copy this pattern to call sites where
deduplication is load-bearing (token exchange, gradebook writes) — use a
`threading.Lock` for those.
"""
import logging
import ssl
import time
from typing import Any, Optional

import certifi
import httpx
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

# Pre-built SSL context using certifi's CA bundle (the same bundle httpx
# uses by default). pyjwt's `PyJWKClient` internally calls
# `urllib.request.urlopen` which would otherwise fall back to the OS CA
# bundle — and the Railway nixpacks image's OS bundle does NOT include all
# of the intermediates that ClassLink's JWKS endpoint serves. The result
# was `PyJWKClientConnectionError` despite the JWKS host being reachable
# (the OIDC discovery doc on the SAME host fetched fine via httpx ~17ms
# earlier). Reusing certifi here eliminates the bundle mismatch.
_CERTIFI_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


class ClassLinkOIDCError(RuntimeError):
    """ClassLink OIDC discovery or JWKS resolution failed.

    Subclasses RuntimeError so existing `except RuntimeError` paths still
    catch it, while letting callers who want to distinguish ClassLink-upstream
    errors from genuine code bugs catch this specifically.
    """

CLASSLINK_DISCOVERY_URL = (
    "https://launchpad.classlink.com/.well-known/openid-configuration"
)
_DISCOVERY_TTL_SECONDS = 3600

_cached_config: Optional[dict[str, Any]] = None
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

    Raises ClassLinkOIDCError if the discovery endpoint returns a non-200 status.
    """
    global _cached_config, _cached_at
    now = time.time()
    if _cached_config and (now - _cached_at) < _DISCOVERY_TTL_SECONDS:
        return _cached_config
    logger.info("Refreshing ClassLink OIDC discovery cache (TTL=%ds)", _DISCOVERY_TTL_SECONDS)
    resp = httpx.get(CLASSLINK_DISCOVERY_URL, timeout=10.0)
    if resp.status_code != 200:
        raise ClassLinkOIDCError(
            f"ClassLink OIDC discovery failed: status={resp.status_code} "
            f"body={resp.text[:200]!r}"
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

    Uses a certifi-backed SSL context so the internal urllib fetch matches
    httpx's behavior (see module-level `_CERTIFI_SSL_CONTEXT` comment for the
    `PyJWKClientConnectionError` incident this guards against).

    Raises ClassLinkOIDCError if the OIDC config is missing jwks_uri.
    """
    global _cached_jwks_client
    if _cached_jwks_client is not None:
        return _cached_jwks_client
    cfg = get_classlink_oidc_config()
    jwks_uri = cfg.get("jwks_uri")
    if not jwks_uri:
        raise ClassLinkOIDCError("ClassLink OIDC config missing jwks_uri")
    _cached_jwks_client = PyJWKClient(jwks_uri, ssl_context=_CERTIFI_SSL_CONTEXT)
    return _cached_jwks_client
