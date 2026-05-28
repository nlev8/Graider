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
            # PyJWKClient is now constructed with a certifi-backed SSL context
            # (hotfix for PyJWKClientConnectionError in the Railway nixpacks
            # image — the OS CA bundle was missing intermediates for ClassLink's
            # JWKS endpoint, while httpx-via-certifi worked for the same host).
            mock_jwks.assert_called_once()
            args, kwargs = mock_jwks.call_args
            assert args == ("https://example.com/jwks",)
            assert isinstance(kwargs.get("ssl_context"), ssl.SSLContext)
        assert client is mock_jwks.return_value
