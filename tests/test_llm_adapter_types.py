"""Tests for Phase 5a PR D1 adapter type definitions.

Verifies the shapes of Message, ContentPart, LLMRequest, LLMResponse,
and their frozen-dataclass semantics.
"""
from __future__ import annotations

import pytest

from backend.services.llm_adapter.types import (
    ContentPart,
    ImagePart,
    LLMRequest,
    LLMResponse,
    Message,
    TextPart,
    ToolCall,
    ToolResultPart,
    ToolUsePart,
    Usage,
    normalize_finish_reason,
)


def test_textpart_is_content_part():
    p = TextPart(text="hello")
    assert isinstance(p, TextPart)
    assert p.text == "hello"


def test_imagepart_accepts_url_or_base64():
    p1 = ImagePart(url="https://example.com/img.png", base64=None, mime_type="image/png")
    p2 = ImagePart(url=None, base64="iVBORw0KG...", mime_type="image/png")
    assert p1.url == "https://example.com/img.png"
    assert p2.base64.startswith("iVBORw")


def test_message_with_text_content():
    msg = Message(role="user", content=[TextPart(text="hi")])
    assert msg.role == "user"
    assert len(msg.content) == 1
    assert isinstance(msg.content[0], TextPart)


def test_message_tool_role_has_tool_call_id():
    msg = Message(
        role="tool",
        content=[ToolResultPart(tool_call_id="abc", content="result")],
        tool_call_id="abc",
    )
    assert msg.role == "tool"
    assert msg.tool_call_id == "abc"


def test_llmrequest_minimal():
    req = LLMRequest(
        model="gpt-4",
        messages=[Message(role="user", content=[TextPart(text="hi")])],
    )
    assert req.model == "gpt-4"
    assert req.system_prompt is None
    assert req.tools is None
    assert req.metadata == {}


def test_llmresponse_shape():
    resp = LLMResponse(
        content_parts=[TextPart(text="hello")],
        tool_calls=[],
        usage=Usage(prompt_tokens=5, completion_tokens=3, cost_usd=0.0001),
        finish_reason="stop",
        provider="openai",
        model="gpt-4",
    )
    assert resp.usage.prompt_tokens == 5
    assert resp.finish_reason == "stop"


def test_llmrequest_is_frozen():
    req = LLMRequest(model="gpt-4", messages=[])
    with pytest.raises(Exception):  # FrozenInstanceError in dataclasses
        req.model = "gpt-3.5"  # type: ignore[misc]


def test_tooluse_and_toolresult_parts():
    use = ToolUsePart(tool_call_id="tc1", name="search", args={"query": "test"})
    result = ToolResultPart(tool_call_id="tc1", content="found it")
    assert use.name == "search"
    assert result.content == "found it"


# ---- Finish reason normalization tests -------------------------------


def test_normalize_finish_reason_openai_native():
    # OpenAI emits "stop", "length", "tool_calls", "content_filter".
    assert normalize_finish_reason("stop") == "stop"
    assert normalize_finish_reason("length") == "length"
    assert normalize_finish_reason("tool_calls") == "tool_use"
    assert normalize_finish_reason("content_filter") == "content_filter"


def test_normalize_finish_reason_anthropic_native():
    # Anthropic emits "end_turn", "max_tokens", "stop_sequence", "tool_use".
    assert normalize_finish_reason("end_turn") == "stop"
    assert normalize_finish_reason("max_tokens") == "length"
    assert normalize_finish_reason("stop_sequence") == "stop"
    assert normalize_finish_reason("tool_use") == "tool_use"


def test_normalize_finish_reason_gemini_native():
    # Gemini enum names (uppercased in .name) — lowercased then mapped.
    assert normalize_finish_reason("STOP") == "stop"
    assert normalize_finish_reason("MAX_TOKENS") == "length"
    assert normalize_finish_reason("max_tokens_reached") == "length"
    assert normalize_finish_reason("SAFETY") == "content_filter"
    assert normalize_finish_reason("RECITATION") == "content_filter"


def test_normalize_finish_reason_none_and_unknown():
    assert normalize_finish_reason(None) == "stop"
    assert normalize_finish_reason("") == "stop"
    # Unknown values pass through lowercased — operators still see provider's native word.
    assert normalize_finish_reason("weird_new_reason") == "weird_new_reason"


def test_imagepart_detail_field_optional_default_none():
    from backend.services.llm_adapter.types import ImagePart
    ip = ImagePart(url="http://x", base64=None, mime_type="image/png")
    assert ip.detail is None


def test_imagepart_detail_accepts_literal_values():
    from backend.services.llm_adapter.types import ImagePart
    for d in ("auto", "low", "high"):
        ip = ImagePart(url="http://x", base64=None, mime_type="image/png", detail=d)
        assert ip.detail == d


def test_llm_tool_args_overflow_exception_importable():
    from backend.services.llm_adapter.types import LLMToolArgsOverflow
    exc = LLMToolArgsOverflow("too big")
    assert isinstance(exc, Exception)
    assert str(exc) == "too big"


def test_llm_tool_args_overflow_exported_from_package():
    from backend.services.llm_adapter import LLMToolArgsOverflow
    assert LLMToolArgsOverflow is not None
