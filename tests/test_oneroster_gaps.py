"""Gap-fill unit tests for backend/oneroster.py.

Audit MAJOR #4 sprint follow-up to PR #300. Targets the 65 uncovered
LOC (67% baseline → ~100%). Module is the OneRoster v1p1 SIS client.

Branches covered
* OneRosterClient._ensure_token (lines 36-51): full OAuth client_
  credentials flow with httpx.post mock — token cache, expires_in
  default fallback, raises on bad response
* OneRosterClient._get_with_retry (lines 63-80): 401 token refresh,
  429 backoff, 5xx backoff, max-retries exhausted
* OneRosterClient._post_with_retry — already partially covered;
  fill 401-refresh + 429-backoff + max-retries paths
* OneRosterClient._get_paginated (lines 124-143): full multi-page
  walk + early-break on partial page
* OneRosterClient.fetch_roster (lines 154-206): teacher-scoped vs
  all-classes branches, school filter, demographics fetch failure
  swallow
* get_oneroster_config (lines 411-447): per-teacher hit, district
  fallback with teacher_sourced_id lookup, env-var fallback,
  per-teacher exception swallow + district exception swallow
"""
from __future__ import annotations

import asyncio
import os
from unittest.mock import patch, MagicMock, AsyncMock

import httpx
import pytest


# ──────────────────────────────────────────────────────────────────
# _ensure_token (OAuth client_credentials)
# ──────────────────────────────────────────────────────────────────


class TestEnsureToken:
    def test_obtains_new_token(self):
        from backend.oneroster import OneRosterClient

        post_resp = MagicMock()
        post_resp.raise_for_status = MagicMock()
        post_resp.json.return_value = {
            "access_token": "tok-1", "expires_in": 7200,
        }
        client_mock = MagicMock()
        client_mock.post = AsyncMock(return_value=post_resp)

        cli = OneRosterClient(
            base_url="https://x.example",
            client_id="ci",
            client_secret="cs",
            token_url="https://x.example/token",
        )
        # Trigger _ensure_token
        asyncio.run(cli._ensure_token(client_mock))
        assert cli._token == "tok-1"
        # post called once with form-encoded body
        client_mock.post.assert_called_once()
        kwargs = client_mock.post.call_args.kwargs
        assert kwargs["data"]["grant_type"] == "client_credentials"
        assert kwargs["data"]["client_id"] == "ci"
        assert kwargs["data"]["client_secret"] == "cs"

    def test_uses_cached_token_when_not_expired(self):
        from backend.oneroster import OneRosterClient
        cli = OneRosterClient(
            base_url="x", client_id="c", client_secret="s",
        )
        # Pre-populate token + far-future expiry
        cli._token = "cached-tok"
        cli._token_expires = 999999999999
        client_mock = MagicMock()
        client_mock.post = AsyncMock()  # should NOT be called

        asyncio.run(cli._ensure_token(client_mock))
        client_mock.post.assert_not_called()
        assert cli._token == "cached-tok"

    def test_sends_basic_auth_header_alongside_body_credentials(self):
        """OAuth client_credentials grant per RFC 6749 §2.3.1 allows credentials
        in EITHER the request body OR an HTTP Basic Authorization header. The
        spec recommends Basic for any client capable of it. Some OneRoster
        vendors (notably ClassLink's Roster Server) REQUIRE Basic and reject
        body-only credentials with `401 UNAUTHORIZED`. Other vendors only
        accept body credentials.

        This test pins that _ensure_token sends BOTH credential channels
        (Basic header via httpx's `auth=` kwarg AND body fields) so the
        client works against the union of all vendor implementations.

        Regression: 2026-05-29 cert-tenant diagnostic against the ClassLink
        Test District (tenant 2284) — production code sent credentials in
        the body only and got `401 UNAUTHORIZED` from ClassLink's `/token`
        endpoint. Direct curl with `-u client_id:secret` (Basic) succeeded
        with HTTP 200. The diagnostic script (which uses the same
        OneRosterClient) reproduced the failure. Adding Basic auth alongside
        body credentials makes the client work for both vendor styles.
        """
        from backend.oneroster import OneRosterClient

        post_resp = MagicMock()
        post_resp.raise_for_status = MagicMock()
        post_resp.json.return_value = {"access_token": "tok-basic", "expires_in": 3600}
        client_mock = MagicMock()
        client_mock.post = AsyncMock(return_value=post_resp)

        cli = OneRosterClient(
            base_url="https://x.example",
            client_id="my-id",
            client_secret="my-secret",
            token_url="https://x.example/token",
        )
        asyncio.run(cli._ensure_token(client_mock))

        # Token obtained
        assert cli._token == "tok-basic"

        # Basic auth via httpx's auth= kwarg (the new invariant this PR pins)
        client_mock.post.assert_called_once()
        kwargs = client_mock.post.call_args.kwargs
        assert kwargs.get("auth") == ("my-id", "my-secret"), (
            "OAuth client_credentials grant MUST send HTTP Basic auth header. "
            f"Got auth kwarg: {kwargs.get('auth')!r}"
        )

        # Body credentials still sent (maximal compatibility — some vendors
        # only accept body, opposite of ClassLink which only accepts Basic).
        assert kwargs["data"]["grant_type"] == "client_credentials"
        assert kwargs["data"]["client_id"] == "my-id"
        assert kwargs["data"]["client_secret"] == "my-secret"

        # Source-equality pin (opus I-2 on PR #603): both channels MUST derive
        # from the same instance attributes. A future refactor that pulled
        # Basic from env while body used self.client_id would slip past the
        # literal-value assertions above; this pin trips that scenario.
        assert kwargs["auth"] == (
            kwargs["data"]["client_id"], kwargs["data"]["client_secret"]
        ), "Basic auth and body credentials must come from the same source"

    def test_default_expires_in_when_omitted(self):
        from backend.oneroster import OneRosterClient
        post_resp = MagicMock()
        post_resp.raise_for_status = MagicMock()
        post_resp.json.return_value = {"access_token": "tok-default"}
        client_mock = MagicMock()
        client_mock.post = AsyncMock(return_value=post_resp)

        cli = OneRosterClient(
            base_url="x", client_id="c", client_secret="s",
        )
        asyncio.run(cli._ensure_token(client_mock))
        # Default expires_in is 3600 → token_expires ~ now+3600
        # Just assert it's at least 60 seconds in the future.
        import time
        assert cli._token_expires > time.time() + 60


# ──────────────────────────────────────────────────────────────────
# _get_with_retry retry/refresh/backoff branches
# ──────────────────────────────────────────────────────────────────


class TestGetWithRetry:
    def _make_client(self, cli):
        cli._token = "tok-1"
        cli._token_expires = 999999999999
        return MagicMock()

    def test_success_returns_json(self):
        from backend.oneroster import OneRosterClient
        cli = OneRosterClient("x", "c", "s")
        cli._token = "t"; cli._token_expires = 999999999999

        resp = MagicMock(status_code=200)
        resp.json.return_value = {"data": "ok"}
        client_mock = MagicMock()
        client_mock.get = AsyncMock(return_value=resp)

        result = asyncio.run(
            cli._get_with_retry(client_mock, "https://x.example/r"),
        )
        assert result == {"data": "ok"}

    def test_401_refreshes_token_and_retries(self):
        from backend.oneroster import OneRosterClient
        cli = OneRosterClient("x", "c", "s")
        cli._token = "stale-tok"
        cli._token_expires = 999999999999

        # First response 401 → token cleared → second response 200
        resp_401 = MagicMock(status_code=401)
        resp_200 = MagicMock(status_code=200)
        resp_200.json.return_value = {"data": "ok"}

        # _ensure_token will be called twice (once before each attempt).
        # On the second call (token cleared), it must refresh. Mock
        # client.post for the refresh.
        post_resp = MagicMock()
        post_resp.raise_for_status = MagicMock()
        post_resp.json.return_value = {
            "access_token": "fresh-tok", "expires_in": 3600,
        }

        client_mock = MagicMock()
        client_mock.post = AsyncMock(return_value=post_resp)
        client_mock.get = AsyncMock(side_effect=[resp_401, resp_200])

        result = asyncio.run(
            cli._get_with_retry(client_mock, "https://x.example/r"),
        )
        assert result == {"data": "ok"}
        assert cli._token == "fresh-tok"

    def test_429_triggers_backoff_then_succeeds(self):
        from backend.oneroster import OneRosterClient
        cli = OneRosterClient("x", "c", "s")
        cli._token = "t"; cli._token_expires = 999999999999

        resp_429 = MagicMock(status_code=429)
        resp_200 = MagicMock(status_code=200)
        resp_200.json.return_value = {"data": "ok"}

        client_mock = MagicMock()
        client_mock.get = AsyncMock(side_effect=[resp_429, resp_200])

        with patch(
            "backend.oneroster.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = asyncio.run(
                cli._get_with_retry(client_mock, "https://x.example/r"),
            )
        assert result == {"data": "ok"}

    def test_5xx_triggers_backoff_then_succeeds(self):
        from backend.oneroster import OneRosterClient
        cli = OneRosterClient("x", "c", "s")
        cli._token = "t"; cli._token_expires = 999999999999

        resp_503 = MagicMock(status_code=503)
        resp_200 = MagicMock(status_code=200)
        resp_200.json.return_value = {"data": "ok"}

        client_mock = MagicMock()
        client_mock.get = AsyncMock(side_effect=[resp_503, resp_200])

        with patch(
            "backend.oneroster.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = asyncio.run(
                cli._get_with_retry(client_mock, "https://x.example/r"),
            )
        assert result == {"data": "ok"}

    def test_max_retries_exhausted_raises(self):
        # All MAX_RETRIES attempts return 503 → exits the loop and
        # raises HTTPStatusError on line 80.
        from backend.oneroster import OneRosterClient
        cli = OneRosterClient("x", "c", "s")
        cli._token = "t"; cli._token_expires = 999999999999

        resp_503 = MagicMock(status_code=503)
        resp_503.request = MagicMock()
        client_mock = MagicMock()
        client_mock.get = AsyncMock(return_value=resp_503)

        with patch(
            "backend.oneroster.asyncio.sleep",
            new_callable=AsyncMock,
        ), patch("backend.oneroster.MAX_RETRIES", 2):
            with pytest.raises(httpx.HTTPStatusError, match="Max retries"):
                asyncio.run(
                    cli._get_with_retry(client_mock, "https://x.example/r"),
                )

    def test_4xx_other_raises_immediately(self):
        from backend.oneroster import OneRosterClient
        cli = OneRosterClient("x", "c", "s")
        cli._token = "t"; cli._token_expires = 999999999999

        resp_403 = MagicMock(status_code=403)
        resp_403.raise_for_status.side_effect = httpx.HTTPStatusError(
            "forbidden", request=MagicMock(), response=resp_403,
        )
        client_mock = MagicMock()
        client_mock.get = AsyncMock(return_value=resp_403)

        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(
                cli._get_with_retry(client_mock, "https://x.example/r"),
            )


# ──────────────────────────────────────────────────────────────────
# _post_with_retry retry/refresh/backoff branches
# ──────────────────────────────────────────────────────────────────


class TestPostWithRetry:
    def test_201_returns_json(self):
        from backend.oneroster import OneRosterClient
        cli = OneRosterClient("x", "c", "s")
        cli._token = "t"; cli._token_expires = 999999999999

        resp = MagicMock(status_code=201)
        resp.json.return_value = {"created": True}
        client_mock = MagicMock()
        client_mock.post = AsyncMock(return_value=resp)

        result = asyncio.run(
            cli._post_with_retry(
                client_mock, "https://x.example/r", {"x": 1},
            ),
        )
        assert result == {"created": True}

    def test_401_refreshes_token_then_succeeds(self):
        from backend.oneroster import OneRosterClient
        cli = OneRosterClient("x", "c", "s")
        cli._token = "stale"; cli._token_expires = 999999999999

        resp_401 = MagicMock(status_code=401)
        resp_200 = MagicMock(status_code=200)
        resp_200.json.return_value = {"x": 1}

        post_token_resp = MagicMock()
        post_token_resp.raise_for_status = MagicMock()
        post_token_resp.json.return_value = {
            "access_token": "fresh", "expires_in": 3600,
        }

        client_mock = MagicMock()
        # The same client.post is used for OAuth refresh AND business
        # POSTs. Provide a side_effect list:
        # 1. Business POST → 401
        # 2. Token refresh → 200 with access_token
        # 3. Business POST retry → 200
        client_mock.post = AsyncMock(side_effect=[
            resp_401, post_token_resp, resp_200,
        ])

        result = asyncio.run(
            cli._post_with_retry(
                client_mock, "https://x.example/r", {"x": 1},
            ),
        )
        assert result == {"x": 1}

    def test_429_backoff_then_succeeds(self):
        from backend.oneroster import OneRosterClient
        cli = OneRosterClient("x", "c", "s")
        cli._token = "t"; cli._token_expires = 999999999999

        resp_429 = MagicMock(status_code=429)
        resp_200 = MagicMock(status_code=200)
        resp_200.json.return_value = {"ok": True}
        client_mock = MagicMock()
        client_mock.post = AsyncMock(side_effect=[resp_429, resp_200])

        with patch(
            "backend.oneroster.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = asyncio.run(
                cli._post_with_retry(
                    client_mock, "https://x.example/r", {},
                ),
            )
        assert result == {"ok": True}

    def test_max_retries_exhausted_raises(self):
        # All MAX_RETRIES attempts return 503 → exits and raises
        # HTTPStatusError on line 116.
        from backend.oneroster import OneRosterClient
        cli = OneRosterClient("x", "c", "s")
        cli._token = "t"; cli._token_expires = 999999999999

        resp_503 = MagicMock(status_code=503)
        resp_503.request = MagicMock()
        client_mock = MagicMock()
        client_mock.post = AsyncMock(return_value=resp_503)

        with patch(
            "backend.oneroster.asyncio.sleep",
            new_callable=AsyncMock,
        ), patch("backend.oneroster.MAX_RETRIES", 2):
            with pytest.raises(httpx.HTTPStatusError, match="Max retries"):
                asyncio.run(
                    cli._post_with_retry(
                        client_mock, "https://x.example/r", {},
                    ),
                )


# ──────────────────────────────────────────────────────────────────
# _get_paginated
# ──────────────────────────────────────────────────────────────────


class TestGetPaginated:
    def test_walks_pages_until_partial(self):
        from backend.oneroster import OneRosterClient
        # Override DEFAULT_PAGE_LIMIT for clarity
        from backend import oneroster as mod
        cli = OneRosterClient("https://x.example", "c", "s")
        cli._token = "t"; cli._token_expires = 999999999999

        # 3 pages: 100, 100, 50. limit=100 → break on the 50.
        # Build a sequence of _get_with_retry responses.
        responses = [
            {"items": [{"id": str(i)} for i in range(100)]},
            {"items": [{"id": str(i)} for i in range(100, 200)]},
            {"items": [{"id": str(i)} for i in range(200, 250)]},
        ]
        seq = iter(responses)

        async def fake_get(client, url, label=""):
            return next(seq)

        with patch.object(cli, "_get_with_retry", fake_get), patch(
            "backend.oneroster.DEFAULT_PAGE_LIMIT", 100,
        ):
            result = asyncio.run(
                cli._get_paginated(MagicMock(), "/items", "items"),
            )
        assert len(result) == 250

    def test_empty_first_page_returns_empty(self):
        from backend.oneroster import OneRosterClient
        cli = OneRosterClient("https://x.example", "c", "s")
        cli._token = "t"; cli._token_expires = 999999999999

        async def fake_get(client, url, label=""):
            return {"items": []}

        with patch.object(cli, "_get_with_retry", fake_get):
            result = asyncio.run(
                cli._get_paginated(MagicMock(), "/items", "items"),
            )
        assert result == []

    def test_separator_appended_to_path_with_existing_query(self):
        # When path already has '?', the limit/offset use '&' separator
        from backend.oneroster import OneRosterClient
        cli = OneRosterClient("https://x.example", "c", "s")
        cli._token = "t"; cli._token_expires = 999999999999

        captured_urls = []

        async def fake_get(client, url, label=""):
            captured_urls.append(url)
            return {"items": []}

        with patch.object(cli, "_get_with_retry", fake_get):
            asyncio.run(cli._get_paginated(
                MagicMock(), "/items?filter=x", "items",
            ))
        # The query separator picked '&'
        assert "?filter=x&limit=" in captured_urls[0]


# ──────────────────────────────────────────────────────────────────
# fetch_roster
# ──────────────────────────────────────────────────────────────────


class TestFetchRoster:
    def test_teacher_scoped_path(self):
        from backend.oneroster import OneRosterClient
        cli = OneRosterClient("https://x.example", "c", "s")

        # Track which paths are paginated
        paths_called = []

        async def fake_paginated(client, path, key, label=""):
            paths_called.append(path)
            return [{"id": "1"}]

        async def fake_ensure(client):
            cli._token = "t"; cli._token_expires = 999999999999

        with patch.object(cli, "_get_paginated", fake_paginated), \
             patch.object(cli, "_ensure_token", fake_ensure), \
             patch(
                 "backend.oneroster.httpx.AsyncClient",
             ) as ac_mock:
            ac_mock.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(),
            )
            ac_mock.return_value.__aexit__ = AsyncMock()
            roster = asyncio.run(
                cli.fetch_roster(teacher_sourced_id="teacher-1"),
            )
        # Teacher-scoped path was used
        assert "/teachers/teacher-1/classes" in paths_called
        # All other resources fetched too
        assert "/enrollments" in paths_called
        assert "/students" in paths_called
        assert "/teachers" in paths_called
        assert "/demographics" in paths_called
        assert len(roster["classes"]) == 1

    def test_all_classes_with_school_filter(self):
        from backend.oneroster import OneRosterClient
        cli = OneRosterClient("https://x.example", "c", "s")

        # Classes returned by the all-classes endpoint:
        # - sec-1 belongs to school-A (matching)
        # - sec-2 belongs to school-B via the schools[] list
        # - sec-3 has no school match
        all_classes = [
            {"sourcedId": "sec-1",
             "school": {"sourcedId": "school-A"}},
            {"sourcedId": "sec-2",
             "schools": [{"sourcedId": "school-A"}]},
            {"sourcedId": "sec-3",
             "school": {"sourcedId": "school-other"},
             "schools": [{"sourcedId": "school-other"}]},
        ]
        # Each subsequent paginated call returns empty
        responses_iter = iter([
            all_classes,  # /classes
            [],            # /enrollments
            [],            # /students
            [],            # /teachers
            [],            # /demographics
        ])

        async def fake_paginated(client, path, key, label=""):
            return next(responses_iter)

        async def fake_ensure(client):
            pass

        with patch.object(cli, "_get_paginated", fake_paginated), \
             patch.object(cli, "_ensure_token", fake_ensure), \
             patch(
                 "backend.oneroster.httpx.AsyncClient",
             ) as ac_mock:
            ac_mock.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(),
            )
            ac_mock.return_value.__aexit__ = AsyncMock()
            roster = asyncio.run(
                cli.fetch_roster(school_id="school-A"),
            )
        # sec-1 (school dict match) AND sec-2 (schools list match) kept
        kept_ids = [c["sourcedId"] for c in roster["classes"]]
        assert "sec-1" in kept_ids
        assert "sec-2" in kept_ids
        # sec-3 dropped
        assert "sec-3" not in kept_ids

    def test_demographics_failure_swallowed(self):
        from backend.oneroster import OneRosterClient
        cli = OneRosterClient("https://x.example", "c", "s")

        # First 4 paginated calls succeed; demographics raises.
        call_count = {"i": 0}

        async def fake_paginated(client, path, key, label=""):
            call_count["i"] += 1
            if path == "/demographics":
                raise RuntimeError("demographics endpoint dead")
            return []

        async def fake_ensure(client):
            pass

        with patch.object(cli, "_get_paginated", fake_paginated), \
             patch.object(cli, "_ensure_token", fake_ensure), \
             patch(
                 "backend.oneroster.httpx.AsyncClient",
             ) as ac_mock:
            ac_mock.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(),
            )
            ac_mock.return_value.__aexit__ = AsyncMock()
            # Must not raise; demographics gets logged + replaced with []
            roster = asyncio.run(cli.fetch_roster())
        assert roster["demographics"] == []


# ──────────────────────────────────────────────────────────────────
# get_oneroster_config
# ──────────────────────────────────────────────────────────────────


class TestGetOneRosterConfig:
    def test_per_teacher_config_hit(self, monkeypatch):
        from backend.oneroster import get_oneroster_config

        def loader(key, tid):
            if key == "oneroster_config" and tid == "teacher-1":
                return {
                    "base_url": "https://x.example",
                    "client_id": "ci",
                    "client_secret": "cs",
                    "token_url": "https://x.example/token",
                    "school_id": "sch-1",
                    "teacher_sourced_id": "ts-1",
                }
            return None

        with patch("backend.storage.load", side_effect=loader):
            cfg = get_oneroster_config(teacher_id="teacher-1")
        assert cfg["base_url"] == "https://x.example"
        assert cfg["teacher_sourced_id"] == "ts-1"

    def test_per_teacher_exception_swallowed_falls_through(
        self, monkeypatch,
    ):
        # Per-teacher load raises → falls through to district config
        # which also doesn't return → falls through to env vars
        for k in (
            "ONEROSTER_BASE_URL", "ONEROSTER_CLIENT_ID",
            "ONEROSTER_CLIENT_SECRET",
        ):
            monkeypatch.delenv(k, raising=False)

        def loader(key, tid):
            if key == "oneroster_config":
                raise RuntimeError("storage flaky")
            return None

        with patch("backend.storage.load", side_effect=loader):
            from backend.oneroster import get_oneroster_config
            cfg = get_oneroster_config(teacher_id="teacher-1")
        assert cfg is None

    def test_district_config_with_teacher_sourced_id(self, monkeypatch):
        # Per-teacher config absent → district config used + teacher
        # sourcedId loaded separately.
        def loader(key, tid):
            if key == "oneroster_config":
                return None
            if key == "district:sis_config" and tid == "system":
                return {
                    "sis_type": "oneroster",
                    "base_url": "https://district.example",
                    "client_id": "dist-ci",
                    "client_secret": "dist-cs",
                    "token_url": "https://district.example/token",
                    "school_id": "school-A",
                }
            if key == "oneroster_teacher_id" and tid == "teacher-1":
                return "ts-from-mapping"
            return None

        with patch("backend.storage.load", side_effect=loader):
            from backend.oneroster import get_oneroster_config
            cfg = get_oneroster_config(teacher_id="teacher-1")
        assert cfg["base_url"] == "https://district.example"
        assert cfg["teacher_sourced_id"] == "ts-from-mapping"
        assert cfg["_source"] == "district"

    def test_district_teacher_lookup_failure_swallowed(self, monkeypatch):
        def loader(key, tid):
            if key == "oneroster_config":
                return None
            if key == "district:sis_config":
                return {
                    "sis_type": "oneroster",
                    "base_url": "https://x.example",
                    "client_id": "ci",
                    "client_secret": "cs",
                    "token_url": "https://x.example/token",
                    "school_id": "sch",
                }
            if key == "oneroster_teacher_id":
                raise RuntimeError("flake")
            return None

        with patch("backend.storage.load", side_effect=loader):
            from backend.oneroster import get_oneroster_config
            cfg = get_oneroster_config(teacher_id="teacher-1")
        # teacher_sourced_id falls through to None; rest of config
        # carries district values.
        assert cfg["teacher_sourced_id"] is None
        assert cfg["_source"] == "district"

    def test_district_query_exception_falls_to_env(self, monkeypatch):
        # Both per-teacher AND district config raise → env-var fallback
        monkeypatch.setenv("ONEROSTER_BASE_URL", "https://env.example")
        monkeypatch.setenv("ONEROSTER_CLIENT_ID", "env-ci")
        monkeypatch.setenv("ONEROSTER_CLIENT_SECRET", "env-cs")
        monkeypatch.setenv(
            "ONEROSTER_TOKEN_URL", "https://env.example/token",
        )
        monkeypatch.setenv("ONEROSTER_SCHOOL_ID", "env-sch")

        with patch(
            "backend.storage.load",
            side_effect=RuntimeError("storage offline"),
        ):
            from backend.oneroster import get_oneroster_config
            cfg = get_oneroster_config(teacher_id="teacher-1")
        assert cfg["base_url"] == "https://env.example"
        assert cfg["client_id"] == "env-ci"
        assert cfg["school_id"] == "env-sch"

    def test_district_non_oneroster_skipped(self, monkeypatch):
        # district config exists but sis_type=clever → falls through
        for k in (
            "ONEROSTER_BASE_URL", "ONEROSTER_CLIENT_ID",
            "ONEROSTER_CLIENT_SECRET",
        ):
            monkeypatch.delenv(k, raising=False)

        def loader(key, tid):
            if key == "oneroster_config":
                return None
            if key == "district:sis_config":
                return {"sis_type": "clever", "base_url": "https://x"}
            return None

        with patch("backend.storage.load", side_effect=loader):
            from backend.oneroster import get_oneroster_config
            assert get_oneroster_config() is None

    def test_env_missing_returns_none(self, monkeypatch):
        for k in (
            "ONEROSTER_BASE_URL", "ONEROSTER_CLIENT_ID",
            "ONEROSTER_CLIENT_SECRET",
        ):
            monkeypatch.delenv(k, raising=False)
        with patch("backend.storage.load", return_value=None):
            from backend.oneroster import get_oneroster_config
            assert get_oneroster_config() is None
