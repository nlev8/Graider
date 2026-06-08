"""
Unit tests for backend/clever.py — coverage push from 71% baseline.

Existing test files cover: callback flow, classes sync, SSO contract,
compliance audit, and end-to-end test_clever.py. This file fills in
the un-covered branches identified by `pytest --cov`:

- get_clever_config: env-fallback path + district config path
- exchange_code_for_token: missing config / non-200 / HTTPError
- get_clever_user: HTTPError / non-200 paths
- _clever_get_with_retry: 200 success / 429 retry / 5xx retry /
  4xx no-retry / HTTPError retry / exhaustion
- sync_roster: paginated success / per-endpoint error / contacts
  non-blocking error
- _next_page_url: relative URL handling

Async functions are driven via `asyncio.run()` so we don't introduce
a dependency on pytest-asyncio.
"""
from __future__ import annotations

import asyncio
import os
from unittest.mock import patch, MagicMock, AsyncMock

import httpx
import pytest


# ──────────────────────────────────────────────────────────────────
# get_clever_config
# ──────────────────────────────────────────────────────────────────


class TestGetCleverConfig:
    def test_returns_district_config_when_sis_type_clever(self, monkeypatch):
        from backend.clever import get_clever_config
        district_cfg = {
            "sis_type": "clever",
            "client_id": "cid",
            "client_secret": "secret",
            "redirect_uri": "https://app.example/cb",
        }
        with patch("backend.storage.load", return_value=district_cfg):
            cfg = get_clever_config()
        assert cfg["client_id"] == "cid"
        assert cfg["client_secret"] == "secret"
        assert cfg["redirect_uri"] == "https://app.example/cb"

    def test_district_config_falls_back_to_env_redirect_uri(self, monkeypatch):
        from backend.clever import get_clever_config
        district_cfg = {
            "sis_type": "clever",
            "client_id": "cid",
            "client_secret": "secret",
            # no redirect_uri in district config
        }
        monkeypatch.setenv("CLEVER_REDIRECT_URI", "https://env.example/cb")
        with patch("backend.storage.load", return_value=district_cfg):
            cfg = get_clever_config()
        assert cfg["redirect_uri"] == "https://env.example/cb"

    def test_district_config_with_non_clever_sis_type_skips(self, monkeypatch):
        # sis_type == 'oneroster' → don't return district config; fall to env
        from backend.clever import get_clever_config
        district_cfg = {"sis_type": "oneroster", "client_id": "x"}
        monkeypatch.setenv("CLEVER_CLIENT_ID", "env-cid")
        monkeypatch.setenv("CLEVER_CLIENT_SECRET", "env-secret")
        monkeypatch.setenv("CLEVER_REDIRECT_URI", "https://env/cb")
        with patch("backend.storage.load", return_value=district_cfg):
            cfg = get_clever_config()
        assert cfg["client_id"] == "env-cid"

    def test_storage_error_falls_back_to_env(self, monkeypatch):
        from backend.clever import get_clever_config
        monkeypatch.setenv("CLEVER_CLIENT_ID", "env-cid")
        monkeypatch.setenv("CLEVER_CLIENT_SECRET", "env-secret")
        monkeypatch.setenv("CLEVER_REDIRECT_URI", "https://env/cb")
        with patch("backend.storage.load", side_effect=Exception("storage down")):
            cfg = get_clever_config()
        assert cfg["client_id"] == "env-cid"

    def test_returns_none_when_no_district_and_no_env(self, monkeypatch):
        from backend.clever import get_clever_config
        monkeypatch.delenv("CLEVER_CLIENT_ID", raising=False)
        monkeypatch.delenv("CLEVER_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("CLEVER_REDIRECT_URI", raising=False)
        with patch("backend.storage.load", return_value=None):
            cfg = get_clever_config()
        assert cfg is None


# ──────────────────────────────────────────────────────────────────
# exchange_code_for_token
# ──────────────────────────────────────────────────────────────────


class TestExchangeCodeForToken:
    def test_returns_none_when_no_config(self):
        from backend.clever import exchange_code_for_token
        with patch("backend.clever.get_clever_config", return_value=None):
            result = asyncio.run(exchange_code_for_token("any-code"))
        assert result is None

    def test_returns_token_dict_on_200(self):
        from backend.clever import exchange_code_for_token
        cfg = {
            "client_id": "cid",
            "client_secret": "secret",
            "redirect_uri": "https://app/cb",
        }
        token_payload = {"access_token": "tok-abc", "token_type": "Bearer"}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = token_payload

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("backend.clever.get_clever_config", return_value=cfg), \
             patch("backend.clever.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(exchange_code_for_token("good-code"))
        assert result == token_payload

    def test_returns_none_on_non_200(self):
        from backend.clever import exchange_code_for_token
        cfg = {"client_id": "c", "client_secret": "s", "redirect_uri": "u"}
        mock_resp = MagicMock()
        mock_resp.status_code = 400

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("backend.clever.get_clever_config", return_value=cfg), \
             patch("backend.clever.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(exchange_code_for_token("bad-code"))
        assert result is None

    def test_returns_none_on_http_error(self):
        from backend.clever import exchange_code_for_token
        cfg = {"client_id": "c", "client_secret": "s", "redirect_uri": "u"}

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("network"))

        with patch("backend.clever.get_clever_config", return_value=cfg), \
             patch("backend.clever.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(exchange_code_for_token("any"))
        assert result is None


# ──────────────────────────────────────────────────────────────────
# get_clever_user
# ──────────────────────────────────────────────────────────────────


class TestGetCleverUser:
    def _make_async_client(self, get_response=None, get_side_effect=None):
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        if get_side_effect is not None:
            client.get = AsyncMock(side_effect=get_side_effect)
        else:
            client.get = AsyncMock(return_value=get_response)
        return client

    def test_returns_none_on_non_200(self):
        from backend.clever import get_clever_user
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_client = self._make_async_client(get_response=mock_resp)
        with patch("backend.clever.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(get_clever_user("bad-token"))
        assert result is None

    def test_returns_none_on_http_error(self):
        from backend.clever import get_clever_user
        mock_client = self._make_async_client(
            get_side_effect=httpx.HTTPError("connection refused")
        )
        with patch("backend.clever.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(get_clever_user("any-token"))
        assert result is None


# ──────────────────────────────────────────────────────────────────
# _clever_get_with_retry — the heart of the retry/backoff path
# ──────────────────────────────────────────────────────────────────


class TestCleverGetWithRetry:
    def _resp(self, status, text="", json_data=None):
        r = MagicMock()
        r.status_code = status
        r.text = text
        if json_data is not None:
            r.json = MagicMock(return_value=json_data)
        return r

    def test_returns_immediately_on_200(self):
        from backend.clever import _clever_get_with_retry
        client = MagicMock()
        client.get = AsyncMock(return_value=self._resp(200, json_data={"data": []}))

        async def driver():
            return await _clever_get_with_retry(client, "https://x", {}, label="t")

        with patch("backend.clever.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            resp = asyncio.run(driver())
        assert resp.status_code == 200
        # No retries — sleep never called
        assert sleep_mock.call_count == 0
        assert client.get.call_count == 1

    def test_retries_on_429_then_succeeds(self):
        from backend.clever import _clever_get_with_retry
        client = MagicMock()
        # 429, 429, 200
        client.get = AsyncMock(side_effect=[
            self._resp(429, text="rate limited"),
            self._resp(429, text="rate limited"),
            self._resp(200, json_data={"data": []}),
        ])

        async def driver():
            return await _clever_get_with_retry(client, "https://x", {}, label="t")

        with patch("backend.clever.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            resp = asyncio.run(driver())
        assert resp.status_code == 200
        # Two sleeps before the successful retry
        assert sleep_mock.call_count == 2
        assert client.get.call_count == 3

    def test_retries_on_5xx_then_succeeds(self):
        from backend.clever import _clever_get_with_retry
        client = MagicMock()
        client.get = AsyncMock(side_effect=[
            self._resp(503, text="upstream"),
            self._resp(200, json_data={"data": []}),
        ])

        async def driver():
            return await _clever_get_with_retry(client, "https://x", {}, label="t")

        with patch("backend.clever.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            resp = asyncio.run(driver())
        assert resp.status_code == 200
        assert sleep_mock.call_count == 1

    def test_no_retry_on_4xx_other_than_429(self):
        # 401/403/404 → return immediately, no retries.
        from backend.clever import _clever_get_with_retry
        client = MagicMock()
        client.get = AsyncMock(return_value=self._resp(403, text="forbidden"))

        async def driver():
            return await _clever_get_with_retry(client, "https://x", {}, label="t")

        with patch("backend.clever.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            resp = asyncio.run(driver())
        assert resp.status_code == 403
        assert sleep_mock.call_count == 0
        assert client.get.call_count == 1

    def test_4xx_error_does_not_log_response_body_pii(self, caplog):
        """FERPA / logging hygiene: a Clever 4xx error body can carry student or
        guardian PII (the roster/contacts fetch paths). The error log must NOT
        include resp.text — only status + label, which are enough to triage."""
        import logging

        from backend.clever import _clever_get_with_retry
        client = MagicMock()
        pii = "Jane Doe guardian@home.edu 555-0100 IEP"
        client.get = AsyncMock(return_value=self._resp(403, text=pii))

        async def driver():
            return await _clever_get_with_retry(client, "https://x", {}, label="contacts")

        with patch("backend.clever.asyncio.sleep", new=AsyncMock()), \
             caplog.at_level(logging.ERROR, logger="backend.clever"):
            resp = asyncio.run(driver())

        assert resp.status_code == 403
        assert pii not in caplog.text, (
            "Clever response body (potential student/guardian PII) must not be logged"
        )
        # Status + label are still logged so failures remain triageable.
        assert "403" in caplog.text
        assert "contacts" in caplog.text

    def test_retries_on_http_error_then_succeeds(self):
        from backend.clever import _clever_get_with_retry
        client = MagicMock()
        client.get = AsyncMock(side_effect=[
            httpx.HTTPError("conn reset"),
            self._resp(200, json_data={"data": []}),
        ])

        async def driver():
            return await _clever_get_with_retry(client, "https://x", {}, label="t")

        with patch("backend.clever.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            resp = asyncio.run(driver())
        assert resp.status_code == 200
        assert sleep_mock.call_count == 1

    def test_http_error_on_last_attempt_raises(self):
        # If the FINAL attempt raises HTTPError, the helper re-raises
        # rather than swallowing.
        from backend.clever import _clever_get_with_retry, MAX_RETRIES
        client = MagicMock()
        # All MAX_RETRIES attempts raise.
        client.get = AsyncMock(side_effect=httpx.HTTPError("network"))

        async def driver():
            return await _clever_get_with_retry(client, "https://x", {}, label="t")

        with patch("backend.clever.asyncio.sleep", new=AsyncMock()):
            with pytest.raises(httpx.HTTPError):
                asyncio.run(driver())
        assert client.get.call_count == MAX_RETRIES

    def test_returns_last_429_after_exhaustion(self):
        # All MAX_RETRIES attempts return 429 — we return the last
        # response after the loop exits.
        from backend.clever import _clever_get_with_retry, MAX_RETRIES
        client = MagicMock()
        client.get = AsyncMock(side_effect=[
            self._resp(429, text="rl") for _ in range(MAX_RETRIES)
        ])

        async def driver():
            return await _clever_get_with_retry(client, "https://x", {}, label="t")

        with patch("backend.clever.asyncio.sleep", new=AsyncMock()):
            resp = asyncio.run(driver())
        assert resp.status_code == 429
        assert client.get.call_count == MAX_RETRIES


# ──────────────────────────────────────────────────────────────────
# sync_roster — paginated fetches for users + sections + contacts
# ──────────────────────────────────────────────────────────────────


class TestSyncRoster:
    def _resp(self, status, json_data=None):
        r = MagicMock()
        r.status_code = status
        r.text = ""
        r.json = MagicMock(return_value=json_data or {})
        return r

    def test_aggregates_paginated_users_and_sections(self):
        # Driver returns:
        #   teachers: 2 pages, 2 + 1 records
        #   students: 1 page, 1 record
        #   sections: 1 page, 2 records
        #   contacts: 1 page, 1 record
        from backend.clever import sync_roster
        teachers_page1 = self._resp(200, {
            "data": [{"data": {"id": "t1"}}, {"data": {"id": "t2"}}],
            "links": [{"rel": "next", "uri": "/v3.0/users?starting_after=t2&role=teacher"}],
        })
        teachers_page2 = self._resp(200, {
            "data": [{"data": {"id": "t3"}}],
            "links": [],  # last page
        })
        students_page = self._resp(200, {
            "data": [{"data": {"id": "s1"}}],
            "links": [],
        })
        sections_page = self._resp(200, {
            "data": [{"data": {"id": "sec1"}}, {"data": {"id": "sec2"}}],
            "links": [],
        })
        contacts_page = self._resp(200, {
            "data": [{"data": {"id": "c1"}}],
            "links": [],
        })

        responses = iter([
            teachers_page1, teachers_page2,
            students_page,
            sections_page,
            contacts_page,
        ])

        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        async def fake_retry(c, url, headers, label=""):
            return next(responses)

        with patch("backend.clever.httpx.AsyncClient", return_value=client), \
             patch("backend.clever._clever_get_with_retry", side_effect=fake_retry):
            result = asyncio.run(sync_roster("token-abc"))

        assert len(result["teachers"]) == 3
        assert len(result["students"]) == 1
        assert len(result["sections"]) == 2
        assert len(result["contacts"]) == 1

    def test_breaks_on_non_200_for_users(self):
        from backend.clever import sync_roster
        # First teachers fetch returns 500 — sync_roster breaks
        # the inner loop and continues to students.
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        responses = iter([
            self._resp(500, {}),   # teachers fail
            self._resp(200, {"data": [{"data": {"id": "s1"}}], "links": []}),  # students ok
            self._resp(200, {"data": [], "links": []}),  # sections empty
            self._resp(200, {"data": [], "links": []}),  # contacts empty
        ])

        async def fake_retry(c, url, headers, label=""):
            return next(responses)

        with patch("backend.clever.httpx.AsyncClient", return_value=client), \
             patch("backend.clever._clever_get_with_retry", side_effect=fake_retry):
            result = asyncio.run(sync_roster("tok"))

        assert result["teachers"] == []
        assert len(result["students"]) == 1

    def test_breaks_on_http_error(self):
        from backend.clever import sync_roster
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        responses = iter([
            httpx.HTTPError("network down"),    # teachers raise
            self._resp(200, {"data": [], "links": []}),  # students
            self._resp(200, {"data": [], "links": []}),  # sections
            self._resp(200, {"data": [], "links": []}),  # contacts
        ])

        async def fake_retry(c, url, headers, label=""):
            r = next(responses)
            if isinstance(r, Exception):
                raise r
            return r

        with patch("backend.clever.httpx.AsyncClient", return_value=client), \
             patch("backend.clever._clever_get_with_retry", side_effect=fake_retry):
            result = asyncio.run(sync_roster("tok"))

        # teachers loop hit HTTPError → break → result still empty
        assert result["teachers"] == []
        # downstream loops still ran
        assert "students" in result and "sections" in result

    def test_contacts_error_is_non_blocking(self):
        from backend.clever import sync_roster
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        responses = iter([
            self._resp(200, {"data": [], "links": []}),  # teachers
            self._resp(200, {"data": [], "links": []}),  # students
            self._resp(200, {"data": [], "links": []}),  # sections
            httpx.HTTPError("contacts upstream"),         # contacts raise
        ])

        async def fake_retry(c, url, headers, label=""):
            r = next(responses)
            if isinstance(r, Exception):
                raise r
            return r

        with patch("backend.clever.httpx.AsyncClient", return_value=client), \
             patch("backend.clever._clever_get_with_retry", side_effect=fake_retry):
            # The contacts HTTPError must NOT propagate — it's logged
            # as non-blocking.
            result = asyncio.run(sync_roster("tok"))

        # Should still return without raising
        assert "teachers" in result


# ──────────────────────────────────────────────────────────────────
# _next_page_url — handles relative + absolute URLs
# ──────────────────────────────────────────────────────────────────


class TestNextPageUrl:
    def test_returns_none_when_no_links(self):
        from backend.clever import _next_page_url
        assert _next_page_url({}) is None
        assert _next_page_url({"links": []}) is None

    def test_returns_none_when_no_next_link(self):
        from backend.clever import _next_page_url
        body = {"links": [{"rel": "self", "uri": "/v3.0/foo"}]}
        assert _next_page_url(body) is None

    def test_resolves_relative_uri_to_absolute(self):
        from backend.clever import _next_page_url
        body = {"links": [{"rel": "next", "uri": "/v3.0/users?starting_after=x"}]}
        url = _next_page_url(body)
        # Implementation prepends CLEVER_API_BASE for relative URIs
        assert url is not None
        assert url.startswith("https://api.clever.com")

    def test_returns_absolute_uri_unchanged(self):
        from backend.clever import _next_page_url
        body = {"links": [{"rel": "next", "uri": "https://api.clever.com/v3.0/foo"}]}
        url = _next_page_url(body)
        assert url == "https://api.clever.com/v3.0/foo"
