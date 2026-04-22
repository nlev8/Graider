"""Tests for Gemini adapter stream_chat (Phase 5a PR D2).

Uses MagicMock chunk sequences. No live API calls.

Gemini's streaming API (generate_content with stream=True) yields
GenerateContentResponse chunks with .text and .candidates[0].content.parts
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

@patch("backend.services.llm_adapter.gemini_adapter.genai")
def test_gemini_stream_text_only(mock_genai):
    mock_model = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model

    chunks = [
        _text_chunk("Hello"),
        _text_chunk(" world"),
        _final_chunk_with_usage(10, 5, "STOP"),
    ]
    mock_model.generate_content.return_value = iter(chunks)

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

@patch("backend.services.llm_adapter.gemini_adapter.genai")
def test_gemini_stream_tool_call(mock_genai):
    mock_model = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model

    chunks = [
        _tool_chunk("get_weather", {"location": "SF"}),
        _final_chunk_with_usage(15, 8, "STOP"),
    ]
    mock_model.generate_content.return_value = iter(chunks)

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

@patch("backend.services.llm_adapter.gemini_adapter.genai")
def test_gemini_stream_passes_stream_true(mock_genai):
    mock_model = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model
    mock_model.generate_content.return_value = iter([_final_chunk_with_usage()])

    adapter = GeminiAdapter(api_key="test-key")
    list(adapter.stream_chat(_simple_request()))

    call_kwargs = mock_model.generate_content.call_args.kwargs
    assert call_kwargs.get("stream") is True


# ---------------------------------------------------------------------------
# emit() events
# ---------------------------------------------------------------------------

@patch("backend.services.llm_adapter.gemini_adapter.emit")
@patch("backend.services.llm_adapter.gemini_adapter.genai")
def test_gemini_stream_emits_start_and_complete(mock_genai, mock_emit):
    mock_model = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model
    mock_model.generate_content.return_value = iter([_final_chunk_with_usage()])

    adapter = GeminiAdapter(api_key="test-key")
    list(adapter.stream_chat(_simple_request()))

    event_names = [call.args[0] for call in mock_emit.call_args_list]
    assert "llm.call.start" in event_names
    assert "llm.call.complete" in event_names
