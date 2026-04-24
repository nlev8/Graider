"""Tests for OpenAI adapter stream_chat (Phase 5a PR D2).

Uses MagicMock-based chunk sequences representative of real OpenAI streaming
responses. No live API calls.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.services.llm_adapter.openai_adapter import OpenAIAdapter
from backend.services.llm_adapter.streaming import (
    FinishEvent,
    TextDelta,
    ToolCallComplete,
    ToolCallDelta,
    UsageEvent,
)
from backend.services.llm_adapter.types import LLMRequest, Message, TextPart, ToolDef


# ---------------------------------------------------------------------------
# Helpers — build mock OpenAI stream chunks
# ---------------------------------------------------------------------------

def _text_chunk(text: str, finish_reason=None):
    """Simulate a chunk with a text delta."""
    delta = MagicMock()
    delta.content = text
    delta.tool_calls = None

    choice = MagicMock()
    choice.delta = delta
    choice.finish_reason = finish_reason

    chunk = MagicMock()
    chunk.choices = [choice]
    chunk.usage = None
    return chunk


def _tool_chunk(index: int, tool_id: str | None, name: str | None, args_delta: str):
    """Simulate a chunk with a tool_call delta."""
    tc_delta = MagicMock()
    tc_delta.index = index
    tc_delta.id = tool_id
    tc_delta.function = MagicMock()
    tc_delta.function.name = name
    tc_delta.function.arguments = args_delta

    delta = MagicMock()
    delta.content = None
    delta.tool_calls = [tc_delta]

    choice = MagicMock()
    choice.delta = delta
    choice.finish_reason = None

    chunk = MagicMock()
    chunk.choices = [choice]
    chunk.usage = None
    return chunk


def _finish_chunk(finish_reason: str = "stop"):
    """Simulate the final chunk with finish_reason."""
    delta = MagicMock()
    delta.content = None
    delta.tool_calls = None

    choice = MagicMock()
    choice.delta = delta
    choice.finish_reason = finish_reason

    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 5

    chunk = MagicMock()
    chunk.choices = [choice]
    chunk.usage = usage
    return chunk


def _make_adapter():
    with patch("backend.services.llm_adapter.openai_adapter.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        adapter = OpenAIAdapter(api_key="test-key")
        adapter._client = mock_client
    return adapter


def _simple_request(tools=None):
    return LLMRequest(
        model="gpt-4o",
        messages=[Message(role="user", content=[TextPart(text="hello")])],
        tools=tools,
    )


# ---------------------------------------------------------------------------
# Text-only stream
# ---------------------------------------------------------------------------

@patch("backend.services.llm_adapter.openai_adapter.OpenAI")
def test_stream_chat_text_only(mock_cls):
    mock_client = MagicMock()
    mock_cls.return_value = mock_client

    chunks = [
        _text_chunk("Hello"),
        _text_chunk(" world"),
        _finish_chunk("stop"),
    ]
    mock_client.chat.completions.create.return_value = iter(chunks)

    adapter = OpenAIAdapter(api_key="test-key")
    events = list(adapter.stream_chat(_simple_request()))

    text_deltas = [e for e in events if isinstance(e, TextDelta)]
    assert len(text_deltas) == 2
    assert text_deltas[0].text == "Hello"
    assert text_deltas[1].text == " world"

    finish = [e for e in events if isinstance(e, FinishEvent)]
    assert len(finish) == 1
    assert finish[0].finish_reason == "stop"

    usage = [e for e in events if isinstance(e, UsageEvent)]
    assert len(usage) == 1
    assert usage[0].usage.prompt_tokens == 10
    assert usage[0].usage.completion_tokens == 5


# ---------------------------------------------------------------------------
# Tool-call stream — single tool, fragmented args
# ---------------------------------------------------------------------------

@patch("backend.services.llm_adapter.openai_adapter.OpenAI")
def test_stream_chat_single_tool_call(mock_cls):
    mock_client = MagicMock()
    mock_cls.return_value = mock_client

    chunks = [
        # First tool delta — id + name + start of args
        _tool_chunk(0, "call_abc", "get_weather", '{"loc'),
        # Continuation — just more args
        _tool_chunk(0, None, None, 'ation": "SF"}'),
        # Finish with tool_calls reason
        _finish_chunk("tool_calls"),
    ]
    mock_client.chat.completions.create.return_value = iter(chunks)

    adapter = OpenAIAdapter(api_key="test-key")
    events = list(adapter.stream_chat(_simple_request()))

    deltas = [e for e in events if isinstance(e, ToolCallDelta)]
    assert len(deltas) >= 1
    assert deltas[0].tool_call_id == "call_abc"
    assert deltas[0].name == "get_weather"

    completes = [e for e in events if isinstance(e, ToolCallComplete)]
    assert len(completes) == 1
    tc = completes[0].tool_call
    assert tc.name == "get_weather"
    assert tc.args == {"location": "SF"}

    finish = [e for e in events if isinstance(e, FinishEvent)]
    assert finish[0].finish_reason == "tool_use"  # normalized


# ---------------------------------------------------------------------------
# Two tool calls in one stream
# ---------------------------------------------------------------------------

@patch("backend.services.llm_adapter.openai_adapter.OpenAI")
def test_stream_chat_two_tool_calls(mock_cls):
    mock_client = MagicMock()
    mock_cls.return_value = mock_client

    chunks = [
        _tool_chunk(0, "id_0", "tool_a", '{"x": 1}'),
        _tool_chunk(1, "id_1", "tool_b", '{"y": 2}'),
        _finish_chunk("tool_calls"),
    ]
    mock_client.chat.completions.create.return_value = iter(chunks)

    adapter = OpenAIAdapter(api_key="test-key")
    events = list(adapter.stream_chat(_simple_request()))

    completes = [e for e in events if isinstance(e, ToolCallComplete)]
    assert len(completes) == 2
    names = {c.tool_call.name for c in completes}
    assert names == {"tool_a", "tool_b"}


# ---------------------------------------------------------------------------
# stream=True and stream_options forwarded to client
# ---------------------------------------------------------------------------

@patch("backend.services.llm_adapter.openai_adapter.OpenAI")
def test_stream_chat_passes_stream_true(mock_cls):
    mock_client = MagicMock()
    mock_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = iter([_finish_chunk("stop")])

    adapter = OpenAIAdapter(api_key="test-key")
    list(adapter.stream_chat(_simple_request()))

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs.get("stream") is True


# ---------------------------------------------------------------------------
# Empty text chunks are skipped
# ---------------------------------------------------------------------------

@patch("backend.services.llm_adapter.openai_adapter.OpenAI")
def test_stream_chat_skips_empty_text_chunks(mock_cls):
    mock_client = MagicMock()
    mock_cls.return_value = mock_client

    chunks = [
        _text_chunk(""),   # empty — should be skipped
        _text_chunk("Hi"),
        _finish_chunk("stop"),
    ]
    mock_client.chat.completions.create.return_value = iter(chunks)

    adapter = OpenAIAdapter(api_key="test-key")
    events = list(adapter.stream_chat(_simple_request()))

    text_deltas = [e for e in events if isinstance(e, TextDelta)]
    assert len(text_deltas) == 1
    assert text_deltas[0].text == "Hi"


# ---------------------------------------------------------------------------
# emit() events are fired on start, complete, error
# ---------------------------------------------------------------------------

@patch("backend.services.llm_adapter.openai_adapter.emit")
@patch("backend.services.llm_adapter.openai_adapter.OpenAI")
def test_stream_chat_emits_start_and_complete(mock_cls, mock_emit):
    mock_client = MagicMock()
    mock_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = iter([_finish_chunk("stop")])

    adapter = OpenAIAdapter(api_key="test-key")
    list(adapter.stream_chat(_simple_request()))

    event_names = [call.args[0] for call in mock_emit.call_args_list]
    assert "llm.call.start" in event_names
    assert "llm.call.complete" in event_names


def test_openai_stream_chat_fast_fails_when_breaker_open():
    """stream_chat() fast-fails with CircuitBreakerError when the breaker
    is already OPEN. Zero network calls hit the client."""
    import pybreaker
    from backend.services.llm_adapter import breakers

    # Pre-open the breaker for (openai, gpt-4o)
    b = breakers.get_breaker("openai", "gpt-4o")
    for _ in range(breakers.FAIL_MAX):
        try:
            b.call(lambda: (_ for _ in ()).throw(ConnectionError("x")))
        except (ConnectionError, pybreaker.CircuitBreakerError):
            pass
    assert b.current_state == pybreaker.STATE_OPEN

    with patch("backend.services.llm_adapter.openai_adapter.OpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = iter([])

        adapter = OpenAIAdapter(api_key="test-key")
        req = LLMRequest(
            model="gpt-4o",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
        )

        with pytest.raises(pybreaker.CircuitBreakerError):
            list(adapter.stream_chat(req))

        # Zero HTTP calls — breaker short-circuited the stream-open
        mock_client.chat.completions.create.assert_not_called()


# ---------------------------------------------------------------------------
# stream.close() lifecycle tests (Phase 5b PR 4)
# ---------------------------------------------------------------------------

def test_openai_stream_closes_on_exception():
    """If the caller raises during iteration, the adapter must call
    stream.close() via finally."""
    close_calls = []

    class FakeStream:
        def __init__(self):
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content="hi", tool_calls=None), finish_reason=None)]
            chunk.usage = None
            self._chunks = iter([chunk])

        def __iter__(self):
            return self._chunks

        def close(self):
            close_calls.append("closed")

    with patch("backend.services.llm_adapter.openai_adapter.OpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = FakeStream()

        adapter = OpenAIAdapter(api_key="test-key")
        req = LLMRequest(
            model="gpt-4o",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
        )

        gen = adapter.stream_chat(req)
        next(gen)
        gen.close()  # triggers GeneratorExit → propagates through finally

        assert close_calls == ["closed"]


def test_openai_stream_closes_on_normal_completion():
    """stream.close() is called after the iteration loop completes normally."""
    close_calls = []

    class FakeStream:
        def __init__(self):
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content="hi", tool_calls=None), finish_reason="stop")]
            chunk.usage = None
            self._chunks = iter([chunk])

        def __iter__(self):
            return self._chunks

        def close(self):
            close_calls.append("closed")

    with patch("backend.services.llm_adapter.openai_adapter.OpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = FakeStream()

        adapter = OpenAIAdapter(api_key="test-key")
        req = LLMRequest(
            model="gpt-4o",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
        )

        # Exhaust the generator
        list(adapter.stream_chat(req))

        assert close_calls == ["closed"]


def test_openai_stream_raises_overflow_on_large_tool_args(monkeypatch):
    """When cumulative tool_call.arguments exceeds 5 MB, the adapter raises
    LLMToolArgsOverflow and emits the observability event."""
    from backend.services.llm_adapter.types import LLMToolArgsOverflow

    # 6 MB fragment to overflow the 5 MB cap in one go
    big = "x" * (6 * 1024 * 1024)

    def _chunk(args_fragment):
        chunk = MagicMock()
        tc_delta = MagicMock()
        tc_delta.index = 0
        tc_delta.id = "call_123"
        tc_delta.function.name = "huge_tool"
        tc_delta.function.arguments = args_fragment
        chunk.choices = [MagicMock(delta=MagicMock(content=None, tool_calls=[tc_delta]), finish_reason=None)]
        chunk.usage = None
        return chunk

    class FakeStream:
        def __iter__(self):
            return iter([_chunk(big)])

        def close(self):
            pass

    captured_events = []

    def fake_emit(name, **kw):
        captured_events.append((name, kw))

    monkeypatch.setattr("backend.services.llm_adapter.openai_adapter.emit", fake_emit)

    with patch("backend.services.llm_adapter.openai_adapter.OpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = FakeStream()

        adapter = OpenAIAdapter(api_key="test-key")
        req = LLMRequest(
            model="gpt-4o",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
        )

        with pytest.raises(LLMToolArgsOverflow):
            list(adapter.stream_chat(req))

    overflow_events = [e for e in captured_events if e[0] == "llm.tool_call.args_overflow"]
    assert len(overflow_events) >= 1
    assert overflow_events[0][1]["tool_name"] == "huge_tool"
    assert overflow_events[0][1]["provider"] == "openai"
