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

# Pre-built SSL context using certifi's CA bundle. Defensive — pyjwt's
# `PyJWKClient` calls `urllib.request.urlopen` internally, which would
# otherwise fall back to the OS CA bundle (which on some images may not
# include every intermediate ClassLink serves). PR #594 added this in the
# belief it was the fix for `PyJWKClientConnectionError`; see the
# `_CLASSLINK_JWKS_HEADERS` comment below for what was actually wrong.
_CERTIFI_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# ClassLink's JWKS endpoint at /oauth2/v2/jwks returns HTTP 401 specifically
# when the request's User-Agent header matches `Python-urllib/X.Y` (urllib's
# default). Every other UA — empty, "Mozilla", "curl/8.0", any custom string,
# the implicit User-Agent that httpx sets — returns HTTP 200. PyJWKClient
# uses urllib internally (not httpx), so unless we set the `headers` kwarg
# its requests get rejected at ClassLink's WAF and pyjwt wraps the resulting
# `HTTPError(401)` in `PyJWKClientConnectionError` — a generic class that
# also covers TLS failures, which is what led PR #594 to misdiagnose this
# as a CA-bundle problem. The wrapped `err:` payload in the original Railway
# log would have read `"HTTP Error 401: Unauthorized"` — read those payloads
# before inferring root cause from class names alone (see
# `.claude/rules/workflow.md` § Lessons From Incidents 2026-05-28).
_CLASSLINK_JWKS_HEADERS = {
    "User-Agent": "Graider/1.0 (+https://app.graider.live)",
}


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

    Passes an explicit `headers` kwarg with a non-`Python-urllib` User-Agent
    so ClassLink's WAF does not 401 the JWKS fetch — that 401 was the actual
    root cause of the `oidc_invalid` SSO failure mis-attributed to a CA
    bundle in PR #594. Also passes a certifi-backed `ssl_context` defensively;
    see the `_CERTIFI_SSL_CONTEXT` and `_CLASSLINK_JWKS_HEADERS` comments.

    Raises ClassLinkOIDCError if the OIDC config is missing jwks_uri.
    """
    global _cached_jwks_client
    if _cached_jwks_client is not None:
        return _cached_jwks_client
    cfg = get_classlink_oidc_config()
    jwks_uri = cfg.get("jwks_uri")
    if not jwks_uri:
        raise ClassLinkOIDCError("ClassLink OIDC config missing jwks_uri")
    _cached_jwks_client = PyJWKClient(
        jwks_uri,
        ssl_context=_CERTIFI_SSL_CONTEXT,
        headers=_CLASSLINK_JWKS_HEADERS,
    )
    return _cached_jwks_client
