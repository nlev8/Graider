"""Tests for Anthropic adapter stream_chat (Phase 5a PR D2).

Uses MagicMock-based event sequences representative of the Anthropic
server-sent event stream. No live API calls.

Anthropic stream event types used:
  message_start, content_block_start, content_block_delta,
  content_block_stop, message_delta, message_stop
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.services.llm_adapter.anthropic_adapter import AnthropicAdapter
from backend.services.llm_adapter.streaming import (
    FinishEvent,
    TextDelta,
    ToolCallComplete,
    ToolCallDelta,
    UsageEvent,
)
from backend.services.llm_adapter.types import LLMRequest, Message, TextPart


# ---------------------------------------------------------------------------
# Helpers — build mock Anthropic stream events
# ---------------------------------------------------------------------------

def _event(type_: str, **kwargs):
    ev = MagicMock()
    ev.type = type_
    for k, v in kwargs.items():
        setattr(ev, k, v)
    return ev


def _text_delta_event(text: str, index: int = 0):
    delta = MagicMock()
    delta.type = "text_delta"
    delta.text = text

    ev = MagicMock()
    ev.type = "content_block_delta"
    ev.index = index
    ev.delta = delta
    return ev


def _tool_delta_event(partial_json: str, index: int = 1):
    delta = MagicMock()
    delta.type = "input_json_delta"
    delta.partial_json = partial_json

    ev = MagicMock()
    ev.type = "content_block_delta"
    ev.index = index
    ev.delta = delta
    return ev


def _content_block_start_text(index: int = 0):
    block = MagicMock()
    block.type = "text"

    ev = MagicMock()
    ev.type = "content_block_start"
    ev.index = index
    ev.content_block = block
    return ev


def _content_block_start_tool(index: int, tool_id: str, name: str):
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name

    ev = MagicMock()
    ev.type = "content_block_start"
    ev.index = index
    ev.content_block = block
    return ev


def _content_block_stop(index: int = 0):
    ev = MagicMock()
    ev.type = "content_block_stop"
    ev.index = index
    return ev


def _message_delta_event(stop_reason: str = "end_turn",
                         input_tokens: int = 10, output_tokens: int = 5):
    usage = MagicMock()
    usage.output_tokens = output_tokens

    delta = MagicMock()
    delta.stop_reason = stop_reason

    ev = MagicMock()
    ev.type = "message_delta"
    ev.delta = delta
    ev.usage = usage
    return ev


def _message_start_event(input_tokens: int = 10):
    usage = MagicMock()
    usage.input_tokens = input_tokens

    message = MagicMock()
    message.usage = usage

    ev = MagicMock()
    ev.type = "message_start"
    ev.message = message
    return ev


def _message_stop_event():
    ev = MagicMock()
    ev.type = "message_stop"
    return ev


def _simple_request():
    return LLMRequest(
        model="claude-haiku-4-5-20251001",
        messages=[Message(role="user", content=[TextPart(text="hi")])],
    )


# ---------------------------------------------------------------------------
# Text-only stream
# ---------------------------------------------------------------------------

@patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
def test_anthropic_stream_text_only(mock_cls):
    mock_client = MagicMock()
    mock_cls.return_value = mock_client

    events = [
        _message_start_event(input_tokens=10),
        _content_block_start_text(0),
        _text_delta_event("Hello", 0),
        _text_delta_event(" world", 0),
        _content_block_stop(0),
        _message_delta_event("end_turn", input_tokens=10, output_tokens=5),
        _message_stop_event(),
    ]
    # Anthropic's stream context manager — simulate with __enter__ returning the event iter
    stream_ctx = MagicMock()
    stream_ctx.__enter__ = MagicMock(return_value=iter(events))
    stream_ctx.__exit__ = MagicMock(return_value=False)
    mock_client.messages.stream.return_value = stream_ctx

    adapter = AnthropicAdapter(api_key="test-key")
    result = list(adapter.stream_chat(_simple_request()))

    text_deltas = [e for e in result if isinstance(e, TextDelta)]
    assert len(text_deltas) == 2
    assert text_deltas[0].text == "Hello"
    assert text_deltas[1].text == " world"

    finish = [e for e in result if isinstance(e, FinishEvent)]
    assert len(finish) == 1
    assert finish[0].finish_reason == "stop"  # "end_turn" normalized

    usage_events = [e for e in result if isinstance(e, UsageEvent)]
    assert len(usage_events) == 1
    assert usage_events[0].usage.completion_tokens == 5


# ---------------------------------------------------------------------------
# Tool-use stream
# ---------------------------------------------------------------------------

@patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
def test_anthropic_stream_tool_call(mock_cls):
    mock_client = MagicMock()
    mock_cls.return_value = mock_client

    events = [
        _message_start_event(input_tokens=15),
        _content_block_start_tool(0, "toolu_abc", "get_weather"),
        _tool_delta_event('{"loc', 0),
        _tool_delta_event('ation": "SF"}', 0),
        _content_block_stop(0),
        _message_delta_event("tool_use", output_tokens=8),
        _message_stop_event(),
    ]
    stream_ctx = MagicMock()
    stream_ctx.__enter__ = MagicMock(return_value=iter(events))
    stream_ctx.__exit__ = MagicMock(return_value=False)
    mock_client.messages.stream.return_value = stream_ctx

    adapter = AnthropicAdapter(api_key="test-key")
    result = list(adapter.stream_chat(_simple_request()))

    deltas = [e for e in result if isinstance(e, ToolCallDelta)]
    assert len(deltas) >= 1
    assert deltas[0].tool_call_id == "toolu_abc"
    assert deltas[0].name == "get_weather"

    completes = [e for e in result if isinstance(e, ToolCallComplete)]
    assert len(completes) == 1
    tc = completes[0].tool_call
    assert tc.name == "get_weather"
    assert tc.args == {"location": "SF"}

    finish = [e for e in result if isinstance(e, FinishEvent)]
    assert finish[0].finish_reason == "tool_use"


# ---------------------------------------------------------------------------
# emit() events
# ---------------------------------------------------------------------------

@patch("backend.services.llm_adapter.anthropic_adapter.emit")
@patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
def test_anthropic_stream_emits_start_and_complete(mock_cls, mock_emit):
    mock_client = MagicMock()
    mock_cls.return_value = mock_client

    events = [
        _message_start_event(),
        _message_delta_event("end_turn", output_tokens=3),
        _message_stop_event(),
    ]
    stream_ctx = MagicMock()
    stream_ctx.__enter__ = MagicMock(return_value=iter(events))
    stream_ctx.__exit__ = MagicMock(return_value=False)
    mock_client.messages.stream.return_value = stream_ctx

    adapter = AnthropicAdapter(api_key="test-key")
    list(adapter.stream_chat(_simple_request()))

    event_names = [call.args[0] for call in mock_emit.call_args_list]
    assert "llm.call.start" in event_names
    assert "llm.call.complete" in event_names


@patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
def test_anthropic_stream_raises_overflow_on_large_tool_args(mock_cls, monkeypatch):
    """When accumulated input_json_delta fragments exceed 5 MB, the adapter
    raises LLMToolArgsOverflow and emits the observability event."""
    from backend.services.llm_adapter.types import LLMToolArgsOverflow

    mock_client = MagicMock()
    mock_cls.return_value = mock_client

    big = "x" * (6 * 1024 * 1024)  # single-fragment overflow

    events = [
        _message_start_event(input_tokens=10),
        _content_block_start_tool(1, "toolu_big", "huge_tool"),
        _tool_delta_event(big, 1),
    ]
    stream_ctx = MagicMock()
    stream_ctx.__enter__ = MagicMock(return_value=iter(events))
    stream_ctx.__exit__ = MagicMock(return_value=False)
    mock_client.messages.stream.return_value = stream_ctx

    captured_events = []

    def fake_emit(name, **kw):
        captured_events.append((name, kw))

    monkeypatch.setattr("backend.services.llm_adapter.anthropic_adapter.emit", fake_emit)

    adapter = AnthropicAdapter(api_key="test-key")
    with pytest.raises(LLMToolArgsOverflow):
        list(adapter.stream_chat(_simple_request()))

    overflow_events = [e for e in captured_events if e[0] == "llm.tool_call.args_overflow"]
    assert len(overflow_events) >= 1
    assert overflow_events[0][1]["tool_name"] == "huge_tool"
    assert overflow_events[0][1]["provider"] == "anthropic"


@patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
def test_anthropic_stream_error_mid_iteration_emits_breadcrumb_and_event(mock_cls, monkeypatch):
    """A mid-iteration exception during stream iteration fires
    llm.call.error + sentry breadcrumb; the exception propagates."""
    captured_events = []
    breadcrumbs = []
    monkeypatch.setattr("backend.services.llm_adapter.anthropic_adapter.emit",
                       lambda name, **kw: captured_events.append((name, kw)))
    monkeypatch.setattr("backend.services.llm_adapter.anthropic_adapter.sentry_sdk.add_breadcrumb",
                       lambda **kw: breadcrumbs.append(kw))

    mock_client = MagicMock()
    mock_cls.return_value = mock_client

    # Iterator that yields one event then raises mid-stream
    def failing_iter():
        yield _message_start_event(input_tokens=10)
        yield _content_block_start_text(0)
        yield _text_delta_event("hi", 0)
        raise ConnectionError("died mid-stream")

    stream_ctx = MagicMock()
    stream_ctx.__enter__ = MagicMock(return_value=failing_iter())
    stream_ctx.__exit__ = MagicMock(return_value=False)
    mock_client.messages.stream.return_value = stream_ctx

    adapter = AnthropicAdapter(api_key="test-key")
    with pytest.raises(ConnectionError):
        list(adapter.stream_chat(_simple_request()))

    errors = [e for e in captured_events if e[0] == "llm.call.error"]
    assert len(errors) >= 1
    assert errors[-1][1]["error_kind"] == "ConnectionError"
    assert errors[-1][1]["streaming"] is True
    assert len(breadcrumbs) >= 1
