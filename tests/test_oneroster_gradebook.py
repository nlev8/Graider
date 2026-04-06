"""Tests for OneRosterClient gradebook methods: create_line_item, create_result, get_line_items."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from backend.oneroster import OneRosterClient


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_client():
    """Return a OneRosterClient with fake credentials."""
    return OneRosterClient(
        base_url="https://sis.example.com/ims/oneroster/v1p1",
        client_id="test-client-id",
        client_secret="test-client-secret",
    )


def mock_post_response(status_code, body):
    """Build a mock httpx Response for a POST endpoint."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.raise_for_status = MagicMock()
    resp.request = MagicMock()
    return resp


def mock_get_response(status_code, body):
    """Build a mock httpx Response for a GET endpoint."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.raise_for_status = MagicMock()
    resp.request = MagicMock()
    return resp


# ── create_line_item ───────────────────────────────────────────────────────────


class TestCreateLineItem:
    def test_returns_line_item_dict_on_201(self):
        """create_line_item should return the lineItem dict on HTTP 201."""
        client = make_client()
        client._token = "fake-token"
        client._token_expires = 9999999999

        line_item_body = {
            "lineItem": {
                "sourcedId": "li-uuid-1",
                "title": "Midterm Exam",
                "class": {"sourcedId": "cls-1"},
                "resultValueMax": 100.0,
                "dueDate": "2026-04-10",
            }
        }
        post_resp = mock_post_response(201, line_item_body)

        async def run():
            with patch("httpx.AsyncClient") as MockClient:
                mock_http = AsyncMock()
                MockClient.return_value.__aenter__.return_value = mock_http
                mock_http.post.return_value = post_resp
                return await client.create_line_item(
                    title="Midterm Exam",
                    class_sourced_id="cls-1",
                    max_score=100.0,
                    due_date="2026-04-10",
                )

        result = asyncio.run(run())
        assert result["sourcedId"] == "li-uuid-1"
        assert result["title"] == "Midterm Exam"
        assert result["resultValueMax"] == 100.0

    def test_returns_line_item_dict_on_200(self):
        """create_line_item should also accept HTTP 200 (some SIS return 200)."""
        client = make_client()
        client._token = "fake-token"
        client._token_expires = 9999999999

        line_item_body = {
            "lineItem": {
                "sourcedId": "li-uuid-2",
                "title": "Quiz 1",
                "class": {"sourcedId": "cls-2"},
                "resultValueMax": 50.0,
            }
        }
        post_resp = mock_post_response(200, line_item_body)

        async def run():
            with patch("httpx.AsyncClient") as MockClient:
                mock_http = AsyncMock()
                MockClient.return_value.__aenter__.return_value = mock_http
                mock_http.post.return_value = post_resp
                return await client.create_line_item(
                    title="Quiz 1",
                    class_sourced_id="cls-2",
                    max_score=50.0,
                )

        result = asyncio.run(run())
        assert result["sourcedId"] == "li-uuid-2"
        assert result["resultValueMax"] == 50.0

    def test_posts_to_line_items_endpoint(self):
        """create_line_item should POST to /lineItems."""
        client = make_client()
        client._token = "fake-token"
        client._token_expires = 9999999999

        line_item_body = {"lineItem": {"sourcedId": "li-x", "title": "Homework 1"}}
        post_resp = mock_post_response(201, line_item_body)

        captured_url = []

        async def run():
            with patch("httpx.AsyncClient") as MockClient:
                mock_http = AsyncMock()
                MockClient.return_value.__aenter__.return_value = mock_http

                async def capture_post(url, **kwargs):
                    captured_url.append(url)
                    return post_resp

                mock_http.post.side_effect = capture_post
                return await client.create_line_item(
                    title="Homework 1",
                    class_sourced_id="cls-99",
                    max_score=20.0,
                )

        asyncio.run(run())
        assert len(captured_url) == 1
        assert "/lineItems" in captured_url[0]

    def test_sourced_id_is_auto_generated_uuid(self):
        """create_line_item should generate a UUID sourcedId for the lineItem."""
        client = make_client()
        client._token = "fake-token"
        client._token_expires = 9999999999

        captured_payloads = []
        line_item_body = {"lineItem": {"sourcedId": "li-auto", "title": "Essay"}}
        post_resp = mock_post_response(201, line_item_body)

        async def run():
            with patch("httpx.AsyncClient") as MockClient:
                mock_http = AsyncMock()
                MockClient.return_value.__aenter__.return_value = mock_http

                async def capture_post(url, **kwargs):
                    captured_payloads.append(kwargs)
                    return post_resp

                mock_http.post.side_effect = capture_post
                return await client.create_line_item(
                    title="Essay",
                    class_sourced_id="cls-1",
                    max_score=10.0,
                )

        asyncio.run(run())
        assert len(captured_payloads) == 1
        payload = captured_payloads[0]
        # The POST body should contain a sourcedId (UUID format check: has hyphens)
        body = payload.get("json", {})
        line_item = body.get("lineItem", {})
        sourced_id = line_item.get("sourcedId", "")
        assert "-" in sourced_id  # UUID contains hyphens

    def test_due_date_optional(self):
        """create_line_item should work without a due_date."""
        client = make_client()
        client._token = "fake-token"
        client._token_expires = 9999999999

        line_item_body = {"lineItem": {"sourcedId": "li-noduedate", "title": "Classwork"}}
        post_resp = mock_post_response(201, line_item_body)

        async def run():
            with patch("httpx.AsyncClient") as MockClient:
                mock_http = AsyncMock()
                MockClient.return_value.__aenter__.return_value = mock_http
                mock_http.post.return_value = post_resp
                return await client.create_line_item(
                    title="Classwork",
                    class_sourced_id="cls-5",
                    max_score=25.0,
                )

        result = asyncio.run(run())
        assert result is not None
        assert result["sourcedId"] == "li-noduedate"

    def test_raises_on_non_200_201(self):
        """create_line_item should raise on 400 or other non-success codes."""
        client = make_client()
        client._token = "fake-token"
        client._token_expires = 9999999999

        error_resp = mock_post_response(400, {})
        error_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400 Bad Request", request=MagicMock(), response=error_resp
        )

        async def run():
            with patch("httpx.AsyncClient") as MockClient:
                mock_http = AsyncMock()
                MockClient.return_value.__aenter__.return_value = mock_http
                mock_http.post.return_value = error_resp
                return await client.create_line_item(
                    title="Bad Item",
                    class_sourced_id="cls-bad",
                    max_score=10.0,
                )

        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(run())


# ── get_line_items ─────────────────────────────────────────────────────────────


class TestGetLineItems:
    def test_returns_list_of_line_items(self):
        """get_line_items should return the list of lineItems for a class."""
        client = make_client()
        client._token = "fake-token"
        client._token_expires = 9999999999

        line_items_body = {
            "lineItems": [
                {"sourcedId": "li-1", "title": "Midterm"},
                {"sourcedId": "li-2", "title": "Final"},
            ]
        }
        get_resp = mock_get_response(200, line_items_body)

        async def run():
            with patch("httpx.AsyncClient") as MockClient:
                mock_http = AsyncMock()
                MockClient.return_value.__aenter__.return_value = mock_http
                mock_http.get.return_value = get_resp
                return await client.get_line_items("cls-1")

        result = asyncio.run(run())
        assert len(result) == 2
        assert result[0]["sourcedId"] == "li-1"
        assert result[1]["title"] == "Final"

    def test_returns_empty_list_when_no_line_items(self):
        """get_line_items should return an empty list when the class has none."""
        client = make_client()
        client._token = "fake-token"
        client._token_expires = 9999999999

        get_resp = mock_get_response(200, {"lineItems": []})

        async def run():
            with patch("httpx.AsyncClient") as MockClient:
                mock_http = AsyncMock()
                MockClient.return_value.__aenter__.return_value = mock_http
                mock_http.get.return_value = get_resp
                return await client.get_line_items("cls-empty")

        result = asyncio.run(run())
        assert result == []

    def test_url_contains_class_filter(self):
        """get_line_items should filter by classSourcedId in the query string."""
        client = make_client()
        client._token = "fake-token"
        client._token_expires = 9999999999

        get_resp = mock_get_response(200, {"lineItems": []})
        captured_urls = []

        async def run():
            with patch("httpx.AsyncClient") as MockClient:
                mock_http = AsyncMock()
                MockClient.return_value.__aenter__.return_value = mock_http

                async def capture_get(url, **kwargs):
                    captured_urls.append(url)
                    return get_resp

                mock_http.get.side_effect = capture_get
                return await client.get_line_items("cls-42")

        asyncio.run(run())
        assert len(captured_urls) == 1
        url = captured_urls[0]
        assert "lineItems" in url
        assert "cls-42" in url


# ── create_result ──────────────────────────────────────────────────────────────


class TestCreateResult:
    def test_returns_result_dict_on_201(self):
        """create_result should return the result dict on HTTP 201."""
        client = make_client()
        client._token = "fake-token"
        client._token_expires = 9999999999

        result_body = {
            "result": {
                "sourcedId": "res-uuid-1",
                "score": 88.0,
                "scoreStatus": "fully graded",
                "lineItem": {"sourcedId": "li-1"},
                "student": {"sourcedId": "stu-1"},
            }
        }
        post_resp = mock_post_response(201, result_body)

        async def run():
            with patch("httpx.AsyncClient") as MockClient:
                mock_http = AsyncMock()
                MockClient.return_value.__aenter__.return_value = mock_http
                mock_http.post.return_value = post_resp
                return await client.create_result(
                    line_item_id="li-1",
                    student_sourced_id="stu-1",
                    score=88.0,
                    max_score=100.0,
                )

        result = asyncio.run(run())
        assert result["sourcedId"] == "res-uuid-1"
        assert result["score"] == 88.0
        assert result["scoreStatus"] == "fully graded"

    def test_returns_result_dict_on_200(self):
        """create_result should also accept HTTP 200."""
        client = make_client()
        client._token = "fake-token"
        client._token_expires = 9999999999

        result_body = {
            "result": {
                "sourcedId": "res-uuid-2",
                "score": 72.0,
                "scoreStatus": "fully graded",
            }
        }
        post_resp = mock_post_response(200, result_body)

        async def run():
            with patch("httpx.AsyncClient") as MockClient:
                mock_http = AsyncMock()
                MockClient.return_value.__aenter__.return_value = mock_http
                mock_http.post.return_value = post_resp
                return await client.create_result(
                    line_item_id="li-2",
                    student_sourced_id="stu-2",
                    score=72.0,
                    max_score=100.0,
                )

        result = asyncio.run(run())
        assert result["sourcedId"] == "res-uuid-2"

    def test_posts_to_correct_endpoint(self):
        """create_result should POST to /lineItems/{line_item_id}/results."""
        client = make_client()
        client._token = "fake-token"
        client._token_expires = 9999999999

        result_body = {"result": {"sourcedId": "res-x", "score": 90.0}}
        post_resp = mock_post_response(201, result_body)
        captured_urls = []

        async def run():
            with patch("httpx.AsyncClient") as MockClient:
                mock_http = AsyncMock()
                MockClient.return_value.__aenter__.return_value = mock_http

                async def capture_post(url, **kwargs):
                    captured_urls.append(url)
                    return post_resp

                mock_http.post.side_effect = capture_post
                return await client.create_result(
                    line_item_id="li-99",
                    student_sourced_id="stu-99",
                    score=90.0,
                    max_score=100.0,
                )

        asyncio.run(run())
        assert len(captured_urls) == 1
        assert "/lineItems/li-99/results" in captured_urls[0]

    def test_payload_contains_score_status_fully_graded(self):
        """create_result should set scoreStatus to 'fully graded' in payload."""
        client = make_client()
        client._token = "fake-token"
        client._token_expires = 9999999999

        result_body = {"result": {"sourcedId": "res-y", "score": 95.0}}
        post_resp = mock_post_response(201, result_body)
        captured_payloads = []

        async def run():
            with patch("httpx.AsyncClient") as MockClient:
                mock_http = AsyncMock()
                MockClient.return_value.__aenter__.return_value = mock_http

                async def capture_post(url, **kwargs):
                    captured_payloads.append(kwargs)
                    return post_resp

                mock_http.post.side_effect = capture_post
                return await client.create_result(
                    line_item_id="li-1",
                    student_sourced_id="stu-1",
                    score=95.0,
                    max_score=100.0,
                )

        asyncio.run(run())
        body = captured_payloads[0].get("json", {})
        result_obj = body.get("result", {})
        assert result_obj.get("scoreStatus") == "fully graded"

    def test_payload_contains_score_and_comment(self):
        """create_result should include score and optional comment in payload."""
        client = make_client()
        client._token = "fake-token"
        client._token_expires = 9999999999

        result_body = {"result": {"sourcedId": "res-z", "score": 78.0}}
        post_resp = mock_post_response(201, result_body)
        captured_payloads = []

        async def run():
            with patch("httpx.AsyncClient") as MockClient:
                mock_http = AsyncMock()
                MockClient.return_value.__aenter__.return_value = mock_http

                async def capture_post(url, **kwargs):
                    captured_payloads.append(kwargs)
                    return post_resp

                mock_http.post.side_effect = capture_post
                return await client.create_result(
                    line_item_id="li-3",
                    student_sourced_id="stu-3",
                    score=78.0,
                    max_score=100.0,
                    comment="Good effort on section 2.",
                )

        asyncio.run(run())
        body = captured_payloads[0].get("json", {})
        result_obj = body.get("result", {})
        assert result_obj.get("score") == 78.0
        assert result_obj.get("comment") == "Good effort on section 2."

    def test_comment_defaults_to_empty_string(self):
        """create_result should default comment to empty string when not given."""
        client = make_client()
        client._token = "fake-token"
        client._token_expires = 9999999999

        result_body = {"result": {"sourcedId": "res-nocomment", "score": 55.0}}
        post_resp = mock_post_response(201, result_body)
        captured_payloads = []

        async def run():
            with patch("httpx.AsyncClient") as MockClient:
                mock_http = AsyncMock()
                MockClient.return_value.__aenter__.return_value = mock_http

                async def capture_post(url, **kwargs):
                    captured_payloads.append(kwargs)
                    return post_resp

                mock_http.post.side_effect = capture_post
                return await client.create_result(
                    line_item_id="li-4",
                    student_sourced_id="stu-4",
                    score=55.0,
                    max_score=100.0,
                )

        asyncio.run(run())
        body = captured_payloads[0].get("json", {})
        result_obj = body.get("result", {})
        assert result_obj.get("comment") == ""

    def test_raises_on_error_status(self):
        """create_result should raise on 400 or other non-success codes."""
        client = make_client()
        client._token = "fake-token"
        client._token_expires = 9999999999

        error_resp = mock_post_response(422, {})
        error_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "422 Unprocessable", request=MagicMock(), response=error_resp
        )

        async def run():
            with patch("httpx.AsyncClient") as MockClient:
                mock_http = AsyncMock()
                MockClient.return_value.__aenter__.return_value = mock_http
                mock_http.post.return_value = error_resp
                return await client.create_result(
                    line_item_id="li-bad",
                    student_sourced_id="stu-bad",
                    score=50.0,
                    max_score=100.0,
                )

        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(run())


# ── _post_with_retry ───────────────────────────────────────────────────────────


class TestPostWithRetry:
    def test_returns_json_on_201(self):
        """_post_with_retry should return parsed JSON on HTTP 201."""
        client = make_client()
        client._token = "fake-token"
        client._token_expires = 9999999999

        resp_201 = mock_post_response(201, {"lineItem": {"sourcedId": "li-retry-1"}})

        async def run():
            mock_http = AsyncMock()
            mock_http.post.return_value = resp_201
            return await client._post_with_retry(
                mock_http,
                "https://sis.example.com/ims/oneroster/v1p1/lineItems",
                payload={"lineItem": {"sourcedId": "li-retry-1"}},
                label="test-post",
            )

        result = asyncio.run(run())
        assert result.get("lineItem", {}).get("sourcedId") == "li-retry-1"

    def test_returns_json_on_200(self):
        """_post_with_retry should return parsed JSON on HTTP 200."""
        client = make_client()
        client._token = "fake-token"
        client._token_expires = 9999999999

        resp_200 = mock_post_response(200, {"result": {"sourcedId": "res-200"}})

        async def run():
            mock_http = AsyncMock()
            mock_http.post.return_value = resp_200
            return await client._post_with_retry(
                mock_http,
                "https://sis.example.com/ims/oneroster/v1p1/lineItems/li-1/results",
                payload={"result": {}},
                label="test-post-200",
            )

        result = asyncio.run(run())
        assert result.get("result", {}).get("sourcedId") == "res-200"

    def test_retries_on_429(self):
        """_post_with_retry should retry on HTTP 429 (rate limit)."""
        client = make_client()
        client._token = "fake-token"
        client._token_expires = 9999999999

        resp_429 = mock_post_response(429, {})
        resp_201 = mock_post_response(201, {"lineItem": {"sourcedId": "li-retried"}})

        call_count = 0

        async def run():
            nonlocal call_count
            mock_http = AsyncMock()

            async def side_effect(url, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return resp_429
                return resp_201

            mock_http.post.side_effect = side_effect
            with patch("asyncio.sleep", new=AsyncMock()):
                return await client._post_with_retry(
                    mock_http,
                    "https://sis.example.com/ims/oneroster/v1p1/lineItems",
                    payload={"lineItem": {}},
                    label="test-429",
                )

        result = asyncio.run(run())
        assert call_count == 2
        assert result.get("lineItem", {}).get("sourcedId") == "li-retried"

    def test_refreshes_token_on_401(self):
        """_post_with_retry should refresh the token and retry on HTTP 401."""
        client = make_client()
        client._token = "stale-token"
        client._token_expires = 9999999999

        resp_401 = mock_post_response(401, {})
        resp_201 = mock_post_response(201, {"lineItem": {"sourcedId": "li-after-401"}})

        call_count = 0
        ensure_token_calls = []

        async def run():
            nonlocal call_count
            mock_http = AsyncMock()

            async def side_effect(url, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return resp_401
                return resp_201

            mock_http.post.side_effect = side_effect

            original_ensure_token = client._ensure_token

            async def mock_ensure_token(c):
                ensure_token_calls.append(1)
                client._token = "fresh-token"

            client._ensure_token = mock_ensure_token

            result = await client._post_with_retry(
                mock_http,
                "https://sis.example.com/ims/oneroster/v1p1/lineItems",
                payload={"lineItem": {}},
                label="test-401",
            )
            client._ensure_token = original_ensure_token
            return result

        result = asyncio.run(run())
        assert call_count == 2
        assert result.get("lineItem", {}).get("sourcedId") == "li-after-401"
