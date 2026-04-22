"""Tests for the Anthropic adapter (Phase 5a PR D1)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.services.llm_adapter.anthropic_adapter import AnthropicAdapter
from backend.services.llm_adapter.types import (
    ImagePart,
    LLMRequest,
    Message,
    TextPart,
    ToolUsePart,
)


def _mock_text_block(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _mock_tool_use_block(tool_id: str, name: str, args: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = args
    return block


def _mock_anthropic_response(blocks=None, stop_reason="end_turn",
                              input_tokens=10, output_tokens=5):
    if blocks is None:
        blocks = [_mock_text_block("hello")]
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    resp = MagicMock()
    resp.content = blocks
    resp.stop_reason = stop_reason
    resp.usage = usage
    resp.model = "claude-sonnet-4-20250514"
    return resp


@patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
def test_system_prompt_maps_to_top_level_system_param(mock_cls):
    mock_client = MagicMock()
    mock_cls.return_value = mock_client
    mock_client.messages.create.return_value = _mock_anthropic_response()

    adapter = AnthropicAdapter(api_key="test-key")
    req = LLMRequest(
        model="claude-sonnet-4-20250514",
        system_prompt="You are a grader.",
        messages=[Message(role="user", content=[TextPart(text="Grade this.")])],
    )
    adapter.chat(req)

    kwargs = mock_client.messages.create.call_args.kwargs
    # system must be a top-level kwarg, NOT embedded in messages
    assert kwargs["system"] == "You are a grader."
    for msg in kwargs["messages"]:
        assert msg["role"] != "system", "system should not appear as a message role"


@patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
def test_simple_text_response(mock_cls):
    mock_client = MagicMock()
    mock_cls.return_value = mock_client
    mock_client.messages.create.return_value = _mock_anthropic_response(
        blocks=[_mock_text_block("The answer is 42.")]
    )

    adapter = AnthropicAdapter(api_key="test-key")
    req = LLMRequest(
        model="claude-sonnet-4-20250514",
        messages=[Message(role="user", content=[TextPart(text="What is the answer?")])],
    )
    resp = adapter.chat(req)

    assert resp.provider == "anthropic"
    assert len(resp.content_parts) == 1
    assert isinstance(resp.content_parts[0], TextPart)
    assert resp.content_parts[0].text == "The answer is 42."
    assert resp.tool_calls == []
    assert resp.usage.prompt_tokens == 10
    assert resp.usage.completion_tokens == 5


@patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
def test_base64_image_maps_to_anthropic_source_block(mock_cls):
    mock_client = MagicMock()
    mock_cls.return_value = mock_client
    mock_client.messages.create.return_value = _mock_anthropic_response()

    adapter = AnthropicAdapter(api_key="test-key")
    req = LLMRequest(
        model="claude-sonnet-4-20250514",
        messages=[Message(
            role="user",
            content=[
                ImagePart(url=None, base64="AAABBB", mime_type="image/png"),
                TextPart(text="What do you see?"),
            ],
        )],
    )
    adapter.chat(req)

    kwargs = mock_client.messages.create.call_args.kwargs
    user_msg = kwargs["messages"][0]
    assert user_msg["role"] == "user"
    img_block = user_msg["content"][0]
    assert img_block["type"] == "image"
    assert img_block["source"]["type"] == "base64"
    assert img_block["source"]["media_type"] == "image/png"
    assert img_block["source"]["data"] == "AAABBB"


@patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
def test_url_image_maps_to_url_source_block(mock_cls):
    mock_client = MagicMock()
    mock_cls.return_value = mock_client
    mock_client.messages.create.return_value = _mock_anthropic_response()

    adapter = AnthropicAdapter(api_key="test-key")
    req = LLMRequest(
        model="claude-sonnet-4-20250514",
        messages=[Message(
            role="user",
            content=[ImagePart(url="https://ex.com/img.png", base64=None, mime_type="image/png")],
        )],
    )
    adapter.chat(req)

    kwargs = mock_client.messages.create.call_args.kwargs
    img_block = kwargs["messages"][0]["content"][0]
    assert img_block["source"]["type"] == "url"
    assert img_block["source"]["url"] == "https://ex.com/img.png"


@patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
def test_tool_use_response_extracted_into_tool_calls(mock_cls):
    mock_client = MagicMock()
    mock_cls.return_value = mock_client
    mock_client.messages.create.return_value = _mock_anthropic_response(
        blocks=[_mock_tool_use_block("tc1", "get_data", {"param": "value"})],
        stop_reason="tool_use",
    )

    adapter = AnthropicAdapter(api_key="test-key")
    req = LLMRequest(
        model="claude-sonnet-4-20250514",
        messages=[Message(role="user", content=[TextPart(text="Use the tool.")])],
    )
    resp = adapter.chat(req)

    assert len(resp.tool_calls) == 1
    tc = resp.tool_calls[0]
    assert tc.tool_call_id == "tc1"
    assert tc.name == "get_data"
    assert tc.args == {"param": "value"}
    assert resp.finish_reason == "tool_use"
    # ToolUsePart also appears in content_parts for multi-turn reconstruction
    tool_parts = [p for p in resp.content_parts if isinstance(p, ToolUsePart)]
    assert len(tool_parts) == 1


@patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
def test_no_system_prompt_omits_system_kwarg(mock_cls):
    mock_client = MagicMock()
    mock_cls.return_value = mock_client
    mock_client.messages.create.return_value = _mock_anthropic_response()

    adapter = AnthropicAdapter(api_key="test-key")
    req = LLMRequest(
        model="claude-sonnet-4-20250514",
        messages=[Message(role="user", content=[TextPart(text="hi")])],
    )
    adapter.chat(req)

    kwargs = mock_client.messages.create.call_args.kwargs
    assert "system" not in kwargs
