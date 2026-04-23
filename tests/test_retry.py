"""Tests for backend.retry — unified retry-with-backoff utility."""

import types
from unittest.mock import MagicMock, patch

import pytest

from backend.retry import (
    BASE_DELAY_S,
    JITTER_FACTOR,
    MAX_DELAY_S,
    MAX_RETRIES,
    RETRYABLE_STATUS_CODES,
    _get_retry_after,
    _get_status_code,
    get_retry_delay,
    is_retryable_error,
    with_retry,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_http_error(status_code, headers=None):
    """Create a fake exception with .status_code and optional .response.headers."""
    exc = Exception(f"HTTP {status_code}")
    exc.status_code = status_code
    if headers is not None:
        resp = types.SimpleNamespace(status_code=status_code, headers=headers)
        exc.response = resp
    return exc


def _make_response_error(status_code, headers=None):
    """Create a fake exception where status lives on .response.status_code."""
    exc = Exception(f"HTTP {status_code}")
    resp = types.SimpleNamespace(status_code=status_code, headers=headers or {})
    exc.response = resp
    return exc


# ── get_retry_delay ──────────────────────────────────────────────────────────

class TestGetRetryDelay:
    @patch("backend.retry.random.random", return_value=0.0)
    def test_base_case_attempt_1(self, _mock_rng):
        delay = get_retry_delay(1)
        assert delay == pytest.approx(0.5)

    @patch("backend.retry.random.random", return_value=0.0)
    def test_exponential_growth(self, _mock_rng):
        assert get_retry_delay(1) == pytest.approx(0.5)
        assert get_retry_delay(2) == pytest.approx(1.0)
        assert get_retry_delay(3) == pytest.approx(2.0)
        assert get_retry_delay(4) == pytest.approx(4.0)
        assert get_retry_delay(5) == pytest.approx(8.0)

    @patch("backend.retry.random.random", return_value=0.0)
    def test_capped_at_max_delay(self, _mock_rng):
        delay = get_retry_delay(100)
        assert delay == pytest.approx(MAX_DELAY_S)

    @patch("backend.retry.random.random", return_value=0.0)
    def test_custom_max_delay(self, _mock_rng):
        delay = get_retry_delay(100, max_delay_s=5.0)
        assert delay == pytest.approx(5.0)

    @patch("backend.retry.random.random", return_value=0.0)
    def test_retry_after_override(self, _mock_rng):
        delay = get_retry_delay(1, retry_after="7")
        assert delay == pytest.approx(7.0)

    @patch("backend.retry.random.random", return_value=0.0)
    def test_retry_after_float(self, _mock_rng):
        delay = get_retry_delay(1, retry_after="2.5")
        assert delay == pytest.approx(2.5)

    @patch("backend.retry.random.random", return_value=0.0)
    def test_invalid_retry_after_falls_back(self, _mock_rng):
        delay = get_retry_delay(1, retry_after="not-a-number")
        assert delay == pytest.approx(0.5)

    @patch("backend.retry.random.random", return_value=0.0)
    def test_zero_retry_after_falls_back(self, _mock_rng):
        delay = get_retry_delay(2, retry_after="0")
        assert delay == pytest.approx(1.0)

    @patch("backend.retry.random.random", return_value=1.0)
    def test_jitter_max(self, _mock_rng):
        # attempt=1 -> base=0.5, jitter = 1.0 * 0.25 * 0.5 = 0.125
        delay = get_retry_delay(1)
        assert delay == pytest.approx(0.5 + 0.125)

    def test_jitter_range(self):
        """Delay is always between base and base * (1 + JITTER_FACTOR)."""
        for attempt in range(1, 6):
            base = min(BASE_DELAY_S * (2 ** (attempt - 1)), MAX_DELAY_S)
            for _ in range(50):
                delay = get_retry_delay(attempt)
                assert base <= delay <= base * (1 + JITTER_FACTOR)


# ── _get_status_code / _get_retry_after ──────────────────────────────────────

class TestHelpers:
    def test_status_from_attribute(self):
        exc = _make_http_error(429)
        assert _get_status_code(exc) == 429

    def test_status_from_response(self):
        exc = _make_response_error(503)
        assert _get_status_code(exc) == 503

    def test_no_status(self):
        assert _get_status_code(ValueError("nope")) is None

    def test_retry_after_header(self):
        exc = _make_http_error(429, headers={"Retry-After": "5"})
        assert _get_retry_after(exc) == "5"

    def test_no_retry_after(self):
        exc = _make_http_error(429, headers={})
        assert _get_retry_after(exc) is None


# ── is_retryable_error ───────────────────────────────────────────────────────

class TestIsRetryableError:
    @pytest.mark.parametrize("code", sorted(RETRYABLE_STATUS_CODES))
    def test_retryable_status_codes(self, code):
        assert is_retryable_error(_make_http_error(code)) is True

    @pytest.mark.parametrize("code", [400, 401, 403, 404])
    def test_non_retryable_status_codes(self, code):
        assert is_retryable_error(_make_http_error(code)) is False

    def test_connection_error(self):
        assert is_retryable_error(ConnectionError("reset")) is True

    def test_timeout_error(self):
        assert is_retryable_error(TimeoutError("timed out")) is True

    def test_os_error(self):
        assert is_retryable_error(OSError("network unreachable")) is True

    def test_value_error_not_retryable(self):
        assert is_retryable_error(ValueError("bad input")) is False

    def test_type_error_not_retryable(self):
        assert is_retryable_error(TypeError("wrong type")) is False

    def test_generic_with_status_code_attribute(self):
        exc = Exception("boom")
        exc.status_code = 502
        assert is_retryable_error(exc) is True

    def test_transient_keyword_matching(self):
        assert is_retryable_error(Exception("rate limit exceeded")) is True
        assert is_retryable_error(Exception("Service temporarily unavailable")) is True
        assert is_retryable_error(Exception("Connection reset by peer")) is True

    def test_no_transient_keyword(self):
        assert is_retryable_error(Exception("invalid API key")) is False

    # ── SDK-specific errors (skip if not installed) ──

    def test_openai_rate_limit(self):
        try:
            from openai import RateLimitError
        except ImportError:
            pytest.skip("openai not installed")
        resp = MagicMock()
        resp.status_code = 429
        resp.headers = {}
        exc = RateLimitError(
            message="rate limited",
            response=resp,
            body=None,
        )
        assert is_retryable_error(exc) is True

    def test_openai_internal_server_error(self):
        try:
            from openai import InternalServerError
        except ImportError:
            pytest.skip("openai not installed")
        resp = MagicMock()
        resp.status_code = 500
        resp.headers = {}
        exc = InternalServerError(
            message="internal error",
            response=resp,
            body=None,
        )
        assert is_retryable_error(exc) is True

    def test_anthropic_rate_limit(self):
        try:
            from anthropic import RateLimitError
        except ImportError:
            pytest.skip("anthropic not installed")
        resp = MagicMock()
        resp.status_code = 429
        resp.headers = {}
        exc = RateLimitError(
            message="rate limited",
            response=resp,
            body=None,
        )
        assert is_retryable_error(exc) is True

    def test_auth_error_not_retryable(self):
        try:
            from openai import AuthenticationError
        except ImportError:
            pytest.skip("openai not installed")
        resp = MagicMock()
        resp.status_code = 401
        resp.headers = {}
        exc = AuthenticationError(
            message="bad key",
            response=resp,
            body=None,
        )
        assert is_retryable_error(exc) is False


# ── with_retry ───────────────────────────────────────────────────────────────

class TestWithRetry:
    @patch("backend.retry.time.sleep")
    def test_succeeds_first_try(self, mock_sleep):
        result = with_retry(lambda: 42)
        assert result == 42
        mock_sleep.assert_not_called()

    @patch("backend.retry.time.sleep")
    def test_retries_on_transient_then_succeeds(self, mock_sleep):
        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("reset")
            return "ok"

        result = with_retry(flaky)
        assert result == "ok"
        assert call_count == 3
        assert mock_sleep.call_count == 2

    @patch("backend.retry.time.sleep")
    def test_raises_after_max_retries(self, mock_sleep):
        def always_fail():
            raise ConnectionError("always fails")

        with pytest.raises(ConnectionError, match="always fails"):
            with_retry(always_fail, max_retries=3)
        # 1 initial + 3 retries = 4 calls, 3 sleeps
        assert mock_sleep.call_count == 3

    @patch("backend.retry.time.sleep")
    def test_does_not_retry_non_transient(self, mock_sleep):
        def bad_request():
            raise _make_http_error(400)

        with pytest.raises(Exception, match="HTTP 400"):
            with_retry(bad_request)
        mock_sleep.assert_not_called()

    @patch("backend.retry.random.random", return_value=0.0)
    @patch("backend.retry.time.sleep")
    def test_sleeps_with_correct_backoff(self, mock_sleep, _mock_rng):
        call_count = 0

        def fail_three_times():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise ConnectionError("fail")
            return "done"

        with_retry(fail_three_times)
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert delays == pytest.approx([0.5, 1.0, 2.0])

    @patch("backend.retry.random.random", return_value=0.0)
    @patch("backend.retry.time.sleep")
    def test_respects_retry_after_header(self, mock_sleep, _mock_rng):
        call_count = 0

        def rate_limited_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                exc = _make_http_error(429, headers={"Retry-After": "10"})
                raise exc
            return "ok"

        result = with_retry(rate_limited_once)
        assert result == "ok"
        mock_sleep.assert_called_once_with(pytest.approx(10.0))

    @patch("backend.retry.time.sleep")
    def test_logs_retries_with_label(self, mock_sleep):
        call_count = 0

        def fail_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("oops")
            return "ok"

        with patch("backend.retry.logger") as mock_logger:
            with_retry(fail_once, label="TestCall")
            # Logger uses %-style formatting; check the formatted result.
            args = mock_logger.warning.call_args[0]
            formatted = args[0] % args[1:]
            assert "[TestCall]" in formatted

    @patch("backend.retry.time.sleep")
    def test_custom_max_retries(self, mock_sleep):
        call_count = 0

        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("fail")

        with pytest.raises(ConnectionError):
            with_retry(always_fail, max_retries=2)
        assert call_count == 3  # 1 initial + 2 retries

    @patch("backend.retry.time.sleep")
    def test_returns_value_from_fn(self, mock_sleep):
        assert with_retry(lambda: {"key": "value"}) == {"key": "value"}
        assert with_retry(lambda: [1, 2, 3]) == [1, 2, 3]
        assert with_retry(lambda: None) is None


# ── Constants ────────────────────────────────────────────────────────────────

class TestConstants:
    def test_constants_values(self):
        assert BASE_DELAY_S == 0.5
        assert MAX_DELAY_S == 32.0
        assert MAX_RETRIES == 5
        assert JITTER_FACTOR == 0.25
        assert RETRYABLE_STATUS_CODES == {408, 429, 500, 502, 503, 504, 529}


# ── Integration helpers ─────────────────────────────────────────────────────

def _make_sdk_error(status_code, message="error"):
    """Create a lightweight stub exception that mimics SDK error shape."""
    err = Exception(message)
    err.status_code = status_code
    err.response = MagicMock(status_code=status_code, headers={})
    return err


# ── Integration tests: simulated API failure patterns ────────────────────────

class TestRetryIntegration:

    @patch("backend.retry.random.random", return_value=0.0)
    @patch("backend.retry.time.sleep")
    def test_retry_openai_rate_limit_then_success(self, mock_sleep, _mock_rng):
        """Simulate OpenAI 429 twice with Retry-After: 1, then succeed."""
        call_count = 0

        def openai_rate_limited():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                exc = _make_sdk_error(429, "Rate limit exceeded")
                exc.response = MagicMock(
                    status_code=429,
                    headers={"Retry-After": "1"},
                )
                raise exc
            return {"choices": [{"message": {"content": "Hello"}}]}

        result = with_retry(openai_rate_limited, label="OpenAI")
        assert result == {"choices": [{"message": {"content": "Hello"}}]}
        assert call_count == 3
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert delays == [pytest.approx(1.0), pytest.approx(1.0)]

    @patch("backend.retry.random.random", return_value=0.0)
    @patch("backend.retry.time.sleep")
    def test_retry_anthropic_503_then_success(self, mock_sleep, _mock_rng):
        """Simulate Anthropic 503 once, then succeed."""
        call_count = 0

        def anthropic_503():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise _make_sdk_error(503, "Service temporarily unavailable")
            return {"content": [{"text": "Response"}]}

        result = with_retry(anthropic_503, label="Anthropic")
        assert result == {"content": [{"text": "Response"}]}
        assert call_count == 2

    @patch("backend.retry.random.random", return_value=0.0)
    @patch("backend.retry.time.sleep")
    def test_retry_connection_reset_recovery(self, mock_sleep, _mock_rng):
        """Simulate ConnectionError once, then succeed."""
        call_count = 0

        def conn_reset():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Connection reset by peer")
            return "recovered"

        result = with_retry(conn_reset)
        assert result == "recovered"
        assert call_count == 2

    @patch("backend.retry.random.random", return_value=0.0)
    @patch("backend.retry.time.sleep")
    def test_retry_total_delay_reasonable(self, mock_sleep, _mock_rng):
        """Exhaust 5 retries with ConnectionError; verify backoff schedule."""
        def always_fail():
            raise ConnectionError("network down")

        with pytest.raises(ConnectionError, match="network down"):
            with_retry(always_fail, max_retries=5)

        assert mock_sleep.call_count == 5
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert delays == pytest.approx([0.5, 1.0, 2.0, 4.0, 8.0])
        assert sum(delays) == pytest.approx(15.5)

    @patch("backend.retry.time.sleep")
    def test_with_retry_raises_non_retryable_immediately(self, mock_sleep):
        """Exceptions listed in non_retryable propagate on first occurrence,
        even if they would otherwise match is_retryable_error()."""

        class FakeCircuitOpen(Exception):
            pass

        call_count = {"n": 0}

        def flaky():
            call_count["n"] += 1
            raise FakeCircuitOpen("breaker open")

        with pytest.raises(FakeCircuitOpen):
            with_retry(flaky, max_retries=5, non_retryable=(FakeCircuitOpen,))

        # First-attempt raise — no retries, no sleep loop.
        assert call_count["n"] == 1
        mock_sleep.assert_not_called()
