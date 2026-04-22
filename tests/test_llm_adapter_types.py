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
