"""Tests for Gemini adapter stream_chat (Phase 5a PR D2).

Uses MagicMock chunk sequences. No live API calls.

Gemini's streaming API (google.genai SDK) uses client.models.generate_content_stream()
which yields GenerateContentResponse chunks with .text and .candidates[0].content.parts
(which may contain function_call parts).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
from backend.services.llm_adapter.streaming import (
    FinishEvent,
    TextDelta,
    ToolCallComplete,
    ToolCallDelta,
    UsageEvent,
)
from backend.services.llm_adapter.types import LLMRequest, Message, TextPart


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _text_chunk(text: str):
    chunk = MagicMock()
    chunk.text = text
    # No function_call parts
    part = MagicMock()
    part.text = text
    del part.function_call  # ensure hasattr returns False
    candidate = MagicMock()
    candidate.content.parts = [part]
    chunk.candidates = [candidate]
    chunk.usage_metadata = None
    return chunk


def _tool_chunk(name: str, args: dict):
    """A chunk whose candidate part has a function_call (no text)."""
    fc = MagicMock()
    fc.name = name
    fc.args = args

    part = MagicMock()
    part.function_call = fc
    # Accessing .text on a tool chunk raises ValueError in real Gemini SDK
    type(part).text = property(lambda self: (_ for _ in ()).throw(ValueError("no text")))

    candidate = MagicMock()
    candidate.content.parts = [part]
    candidate.finish_reason = MagicMock()
    candidate.finish_reason.name = "STOP"

    chunk = MagicMock()
    # chunk.text also raises when it's a function-call-only response
    type(chunk).text = property(lambda self: (_ for _ in ()).throw(ValueError("no text")))
    chunk.candidates = [candidate]
    chunk.usage_metadata = None
    return chunk


def _final_chunk_with_usage(prompt_tokens: int = 10, output_tokens: int = 5,
                             finish_reason_name: str = "STOP"):
    usage = MagicMock()
    usage.prompt_token_count = prompt_tokens
    usage.candidates_token_count = output_tokens

    candidate = MagicMock()
    fr = MagicMock()
    fr.name = finish_reason_name
    candidate.finish_reason = fr
    candidate.content.parts = []

    chunk = MagicMock()
    chunk.text = ""
    chunk.candidates = [candidate]
    chunk.usage_metadata = usage
    return chunk


def _simple_request():
    return LLMRequest(
        model="gemini-2.0-flash",
        messages=[Message(role="user", content=[TextPart(text="hi")])],
    )


# ---------------------------------------------------------------------------
# Text-only stream
# ---------------------------------------------------------------------------

@patch("backend.services.llm_adapter.gemini_adapter.genai.Client")
def test_gemini_stream_text_only(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    chunks = [
        _text_chunk("Hello"),
        _text_chunk(" world"),
        _final_chunk_with_usage(10, 5, "STOP"),
    ]
    mock_client.models.generate_content_stream.return_value = iter(chunks)

    adapter = GeminiAdapter(api_key="test-key")
    events = list(adapter.stream_chat(_simple_request()))

    text_deltas = [e for e in events if isinstance(e, TextDelta)]
    assert len(text_deltas) >= 2
    texts = [e.text for e in text_deltas]
    assert "Hello" in texts
    assert " world" in texts

    finish = [e for e in events if isinstance(e, FinishEvent)]
    assert len(finish) == 1
    assert finish[0].finish_reason == "stop"

    usage_events = [e for e in events if isinstance(e, UsageEvent)]
    assert len(usage_events) == 1
    assert usage_events[0].usage.prompt_tokens == 10
    assert usage_events[0].usage.completion_tokens == 5


# ---------------------------------------------------------------------------
# Tool-call stream
# ---------------------------------------------------------------------------

@patch("backend.services.llm_adapter.gemini_adapter.genai.Client")
def test_gemini_stream_tool_call(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    chunks = [
        _tool_chunk("get_weather", {"location": "SF"}),
        _final_chunk_with_usage(15, 8, "STOP"),
    ]
    mock_client.models.generate_content_stream.return_value = iter(chunks)

    adapter = GeminiAdapter(api_key="test-key")
    events = list(adapter.stream_chat(_simple_request()))

    completes = [e for e in events if isinstance(e, ToolCallComplete)]
    assert len(completes) == 1
    tc = completes[0].tool_call
    assert tc.name == "get_weather"
    assert tc.args == {"location": "SF"}

    finish = [e for e in events if isinstance(e, FinishEvent)]
    assert finish[0].finish_reason == "stop"


# ---------------------------------------------------------------------------
# stream=True forwarded to generate_content
# ---------------------------------------------------------------------------

@patch("backend.services.llm_adapter.gemini_adapter.genai.Client")
def test_gemini_stream_passes_stream_true(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content_stream.return_value = iter([_final_chunk_with_usage()])

    adapter = GeminiAdapter(api_key="test-key")
    list(adapter.stream_chat(_simple_request()))

    mock_client.models.generate_content_stream.assert_called_once()
    call_kwargs = mock_client.models.generate_content_stream.call_args.kwargs
    # New SDK uses a dedicated stream method — no stream=True kwarg needed
    assert "config" in call_kwargs


# ---------------------------------------------------------------------------
# emit() events
# ---------------------------------------------------------------------------

@patch("backend.services.llm_adapter.gemini_adapter.emit")
@patch("backend.services.llm_adapter.gemini_adapter.genai.Client")
def test_gemini_stream_emits_start_and_complete(mock_client_cls, mock_emit):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content_stream.return_value = iter([_final_chunk_with_usage()])

    adapter = GeminiAdapter(api_key="test-key")
    list(adapter.stream_chat(_simple_request()))

    event_names = [call.args[0] for call in mock_emit.call_args_list]
    assert "llm.call.start" in event_names
    assert "llm.call.complete" in event_names


# ---------------------------------------------------------------------------
# Phase 5b PR 4 — best-effort stream cancel/close on exit
# ---------------------------------------------------------------------------

def test_gemini_stream_calls_cancel_if_available():
    """Best-effort cleanup: if the stream exposes .cancel(), it's called on exit."""
    cancel_calls = []

    class FakeStream:
        def __iter__(self):
            part = MagicMock()
            part.text = "hi"
            part.function_call = None
            chunk = MagicMock()
            chunk.candidates = [MagicMock()]
            chunk.candidates[0].content.parts = [part]
            chunk.candidates[0].finish_reason = None
            chunk.usage_metadata = None
            return iter([chunk])

        def cancel(self):
            cancel_calls.append("cancelled")

    with patch("backend.services.llm_adapter.gemini_adapter.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content_stream.return_value = FakeStream()

        from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
        from backend.services.llm_adapter.types import LLMRequest, Message, TextPart

        adapter = GeminiAdapter(api_key="test-key")
        req = LLMRequest(
            model="gemini-1.5-flash",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
        )

        gen = adapter.stream_chat(req)
        next(gen)
        gen.close()

        assert cancel_calls == ["cancelled"]


def test_gemini_stream_falls_back_to_close_when_cancel_missing():
    """If .cancel() doesn't exist but .close() does, .close() is called."""
    close_calls = []

    class FakeStream:
        def __iter__(self):
            part = MagicMock()
            part.text = "hi"
            part.function_call = None
            chunk = MagicMock()
            chunk.candidates = [MagicMock()]
            chunk.candidates[0].content.parts = [part]
            chunk.candidates[0].finish_reason = None
            chunk.usage_metadata = None
            return iter([chunk])

        def close(self):
            close_calls.append("closed")

    with patch("backend.services.llm_adapter.gemini_adapter.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content_stream.return_value = FakeStream()

        from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
        from backend.services.llm_adapter.types import LLMRequest, Message, TextPart

        adapter = GeminiAdapter(api_key="test-key")
        req = LLMRequest(
            model="gemini-1.5-flash",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
        )

        gen = adapter.stream_chat(req)
        next(gen)
        gen.close()

        assert close_calls == ["closed"]


def test_gemini_stream_graceful_when_neither_cancel_nor_close_exists():
    """If the stream exposes neither method, adapter does not raise."""
    class FakeStream:
        def __iter__(self):
            part = MagicMock()
            part.text = "hi"
            part.function_call = None
            chunk = MagicMock()
            chunk.candidates = [MagicMock()]
            chunk.candidates[0].content.parts = [part]
            chunk.candidates[0].finish_reason = None
            chunk.usage_metadata = None
            return iter([chunk])
        # No cancel(), no close()

    with patch("backend.services.llm_adapter.gemini_adapter.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content_stream.return_value = FakeStream()

        from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
        from backend.services.llm_adapter.types import LLMRequest, Message, TextPart

        adapter = GeminiAdapter(api_key="test-key")
        req = LLMRequest(
            model="gemini-1.5-flash",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
        )

        # Must not raise
        gen = adapter.stream_chat(req)
        next(gen)
        gen.close()
