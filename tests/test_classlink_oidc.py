"""
Tests for backend.services.classlink_oidc — OIDC discovery + JWKS client cache.

TDD baseline for Task 1 of the SIS compliance hardening sprint
(docs/superpowers/specs/2026-05-05-sis-compliance-hardening-design.md).
"""
import ssl

import pytest
from unittest.mock import patch, MagicMock

from backend.services.classlink_oidc import (
    get_classlink_oidc_config,
    get_classlink_jwks_client,
    _DISCOVERY_TTL_SECONDS,
    _reset_cache_for_tests,
)


@pytest.fixture(autouse=True)
def reset_cache():
    _reset_cache_for_tests()
    yield
    _reset_cache_for_tests()


def test_discovery_fetches_well_known_config():
    fake_config = {
        "issuer": "https://launchpad.classlink.com",
        "jwks_uri": "https://launchpad.classlink.com/oauth2/v2/keys",
        "authorization_endpoint": "https://launchpad.classlink.com/oauth2/v2/auth",
    }
    with patch("backend.services.classlink_oidc.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: fake_config
        )
        cfg = get_classlink_oidc_config()
    assert cfg["issuer"] == "https://launchpad.classlink.com"
    assert cfg["jwks_uri"] == "https://launchpad.classlink.com/oauth2/v2/keys"
    mock_get.assert_called_once_with(
        "https://launchpad.classlink.com/.well-known/openid-configuration",
        timeout=10.0,
    )


def test_discovery_cached_within_ttl():
    fake_config = {"issuer": "iss", "jwks_uri": "jwks"}
    with patch("backend.services.classlink_oidc.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: fake_config)
        get_classlink_oidc_config()
        get_classlink_oidc_config()
        get_classlink_oidc_config()
    assert mock_get.call_count == 1


def test_discovery_failure_raises_classlink_oidc_error():
    from backend.services.classlink_oidc import ClassLinkOIDCError
    with patch("backend.services.classlink_oidc.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=500, text="upstream error")
        with pytest.raises(ClassLinkOIDCError, match="ClassLink OIDC discovery failed"):
            get_classlink_oidc_config()


def test_discovery_failure_message_includes_response_body_excerpt():
    from backend.services.classlink_oidc import ClassLinkOIDCError
    with patch("backend.services.classlink_oidc.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=502, text="bad gateway from upstream"
        )
        with pytest.raises(ClassLinkOIDCError) as exc_info:
            get_classlink_oidc_config()
    assert "502" in str(exc_info.value)
    assert "bad gateway" in str(exc_info.value)


def test_jwks_client_uses_discovered_uri():
    fake_config = {"issuer": "iss", "jwks_uri": "https://example.com/jwks"}
    with patch("backend.services.classlink_oidc.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: fake_config)
        with patch("backend.services.classlink_oidc.PyJWKClient") as mock_jwks:
            client = get_classlink_jwks_client()
            # PyJWKClient is constructed with a certifi-backed SSL context
            # (defensive — kept from PR #594; pyjwt's urllib fallback uses
            # the OS CA bundle which may be missing intermediates on some
            # deploy images). The actual `oidc_invalid` root cause was a
            # WAF User-Agent filter — asserted in the next test.
            mock_jwks.assert_called_once()
            args, kwargs = mock_jwks.call_args
            assert args == ("https://example.com/jwks",)
            assert isinstance(kwargs.get("ssl_context"), ssl.SSLContext)
        assert client is mock_jwks.return_value


def test_jwks_client_sets_non_python_urllib_user_agent():
    """ClassLink's JWKS endpoint at /oauth2/v2/jwks returns HTTP 401 when
    fetched with a User-Agent matching `Python-urllib/X.Y` (urllib's default
    UA). PyJWKClient uses urllib internally, so we must pass a custom UA via
    the `headers` kwarg.

    The original `oidc_invalid` failure in prod was misdiagnosed in PR #594
    as a CA-bundle mismatch — the `PyJWKClientConnectionError` is in fact the
    pyjwt wrapper for HTTPError (HTTP 401), not a TLS error. The certifi
    context shipped in #594 is harmless but did not address the UA filter.

    See `.claude/rules/workflow.md` § Lessons From Incidents (2026-05-28).
    """
    fake_config = {"issuer": "iss", "jwks_uri": "https://example.com/jwks"}
    with patch("backend.services.classlink_oidc.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: fake_config)
        with patch("backend.services.classlink_oidc.PyJWKClient") as mock_jwks:
            get_classlink_jwks_client()
            _args, kwargs = mock_jwks.call_args
    headers = kwargs.get("headers")
    assert headers is not None, (
        "PyJWKClient must receive an explicit headers kwarg so urllib "
        "does not fall back to the default 'Python-urllib/X.Y' User-Agent."
    )
    ua = headers.get("User-Agent", "")
    assert ua, "headers must include a non-empty User-Agent"
    assert not ua.startswith("Python-urllib"), (
        f"User-Agent must not match urllib's default 'Python-urllib/X.Y' "
        f"(ClassLink's JWKS endpoint returns 401 on that UA); got: {ua!r}"
    )
