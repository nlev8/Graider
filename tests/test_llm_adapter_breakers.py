"""Tests for the LLM adapter circuit breakers (Phase 5b PR 1)."""
from __future__ import annotations

import pybreaker
import pytest

from backend.services.llm_adapter import breakers


@pytest.fixture(autouse=True)
def _reset_breaker_registry():
    """Clear breaker registry between tests so lazy-populated state
    doesn't leak across test boundaries."""
    breakers._BREAKERS.clear()
    yield
    breakers._BREAKERS.clear()


def test_get_breaker_returns_same_instance_per_key():
    b1 = breakers.get_breaker("openai", "gpt-4o")
    b2 = breakers.get_breaker("openai", "gpt-4o")
    assert b1 is b2


def test_get_breaker_per_model_isolation():
    b_4o = breakers.get_breaker("openai", "gpt-4o")
    b_4o_mini = breakers.get_breaker("openai", "gpt-4o-mini")
    assert b_4o is not b_4o_mini


def test_is_user_error_true_for_4xx_names():
    class BadRequestError(Exception):
        pass

    class AuthenticationError(Exception):
        pass

    class RateLimitError(Exception):
        pass

    assert breakers._is_user_error(BadRequestError("bad"))
    assert breakers._is_user_error(AuthenticationError("nope"))
    assert breakers._is_user_error(RateLimitError("429"))


def test_is_user_error_false_for_network_error():
    assert not breakers._is_user_error(ConnectionError("reset"))
    assert not breakers._is_user_error(TimeoutError("slow"))


def test_is_user_error_true_for_429_via_status_code():
    class APIError(Exception):
        def __init__(self, status_code):
            self.status_code = status_code

    assert breakers._is_user_error(APIError(429))
    assert breakers._is_user_error(APIError(404))
    assert not breakers._is_user_error(APIError(500))
    assert not breakers._is_user_error(APIError(503))


def test_breaker_trips_after_5_network_failures():
    b = breakers.get_breaker("openai", "gpt-4o")

    def failing():
        raise ConnectionError("reset by peer")

    for _ in range(5):
        with pytest.raises(ConnectionError):
            b.call(failing)

    with pytest.raises(pybreaker.CircuitBreakerError):
        b.call(failing)


def test_breaker_does_not_trip_on_user_errors():
    b = breakers.get_breaker("openai", "gpt-4o")

    class BadRequestError(Exception):
        pass

    def bad():
        raise BadRequestError("400")

    for _ in range(10):
        with pytest.raises(BadRequestError):
            b.call(bad)

    assert b.current_state == pybreaker.STATE_CLOSED


def test_breaker_does_not_trip_on_429_rate_limit():
    b = breakers.get_breaker("openai", "gpt-4o")

    class RateLimitError(Exception):
        def __init__(self):
            self.status_code = 429

    def rate_limited():
        raise RateLimitError()

    for _ in range(10):
        with pytest.raises(RateLimitError):
            b.call(rate_limited)

    assert b.current_state == pybreaker.STATE_CLOSED


def test_per_model_isolation_real():
    """Flooding gpt-4o failures doesn't open gpt-4o-mini's breaker."""
    b_4o = breakers.get_breaker("openai", "gpt-4o")
    b_mini = breakers.get_breaker("openai", "gpt-4o-mini")

    def failing():
        raise ConnectionError("down")

    for _ in range(5):
        with pytest.raises(ConnectionError):
            b_4o.call(failing)

    with pytest.raises(pybreaker.CircuitBreakerError):
        b_4o.call(failing)

    assert b_mini.current_state == pybreaker.STATE_CLOSED


def test_state_change_emits_observability_event(monkeypatch):
    captured = []

    def fake_emit(event_name, **kwargs):
        captured.append((event_name, kwargs))

    monkeypatch.setattr(breakers, "emit", fake_emit)

    b = breakers.get_breaker("anthropic", "claude-3-sonnet")

    def failing():
        raise ConnectionError("down")

    for _ in range(5):
        with pytest.raises(ConnectionError):
            b.call(failing)

    with pytest.raises(pybreaker.CircuitBreakerError):
        b.call(failing)

    state_change_events = [e for e in captured if e[0] == "llm.breaker.state_change"]
    # First transition should be closed -> open (no initial event is emitted
    # by pybreaker for the lazy-initialized closed state).
    assert len(state_change_events) >= 1
    first = state_change_events[0]
    assert first[1]["provider"] == "anthropic"
    assert first[1]["model"] == "claude-3-sonnet"
    assert first[1]["from_state"] == "closed"
    assert first[1]["to_state"] == "open"


def _rewind_opened_at(breaker: pybreaker.CircuitBreaker, seconds: float) -> None:
    """Rewind the breaker's opened_at timestamp so `reset_timeout` has elapsed.

    Uses pybreaker 1.4.x's state_storage.opened_at setter, which accepts a
    timezone-aware UTC datetime.
    """
    import datetime as _dt

    try:
        from datetime import UTC as _UTC
    except ImportError:  # pragma: no cover — Python <3.11
        _UTC = _dt.timezone.utc

    breaker._state_storage.opened_at = _dt.datetime.now(_UTC) - _dt.timedelta(seconds=seconds)


def test_breaker_half_open_after_reset_timeout():
    """After reset_timeout seconds, the next call transitions open -> half_open
    -> closed (on probe success)."""
    b = breakers.get_breaker("openai", "gpt-4o")

    def failing():
        raise ConnectionError("down")

    for _ in range(5):
        with pytest.raises(ConnectionError):
            b.call(failing)
    assert b.current_state == pybreaker.STATE_OPEN

    _rewind_opened_at(b, breakers.RESET_TIMEOUT + 1.0)

    def succeeds():
        return "ok"

    # Successful probe closes the breaker
    result = b.call(succeeds)
    assert result == "ok"
    assert b.current_state == pybreaker.STATE_CLOSED


def test_breaker_probe_failure_reopens():
    """A failed probe during half-open re-opens the breaker. With
    throw_new_error_on_trip=False the probe's original error propagates."""
    b = breakers.get_breaker("openai", "gpt-4o")

    def failing():
        raise ConnectionError("down")

    for _ in range(5):
        with pytest.raises(ConnectionError):
            b.call(failing)
    assert b.current_state == pybreaker.STATE_OPEN

    _rewind_opened_at(b, breakers.RESET_TIMEOUT + 1.0)

    with pytest.raises(ConnectionError):
        b.call(failing)
    assert b.current_state == pybreaker.STATE_OPEN
