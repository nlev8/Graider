"""Regression tests for issue #343 — Anthropic adapter `emit_json` not
auto-decoded back into a TextPart.

When a caller sets `request.response_format = ResponseFormat(type="json_schema",
schema=...)` on `AnthropicAdapter.chat()`, the adapter synthesizes an
`emit_json` tool with `tool_choice={"type": "tool", "name": "emit_json"}`
to force Anthropic to return structured output. Pre-fix the response
came back as a `ToolCall(name="emit_json", args=...)` and the caller had
to know about the convention to find their JSON in `tool_calls[0]`
instead of `content_parts[0].text`.

That broke the `response_format` abstraction: OpenAI/Gemini adapters
deliver JSON in `content_parts[0].text`. These tests pin the Anthropic
adapter to the same contract — when the adapter itself synthesized the
`emit_json` tool, it should auto-decode the response into a TextPart so
callers see the same shape across providers.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from backend.services.llm_adapter.anthropic_adapter import AnthropicAdapter
from backend.services.llm_adapter.types import (
    LLMRequest,
    Message,
    ResponseFormat,
    TextPart,
    ToolDef,
)


def _mock_tool_use_block(name, input_):
    block = MagicMock()
    block.type = "tool_use"
    block.id = "tool_use_abc"
    block.name = name
    block.input = input_
    return block


def _mock_text_block(text):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _mock_response(blocks, stop_reason="tool_use"):
    usage = MagicMock()
    usage.input_tokens = 10
    usage.output_tokens = 5
    resp = MagicMock()
    resp.content = blocks
    resp.stop_reason = stop_reason
    resp.usage = usage
    resp.model = "claude-sonnet-4-20250514"
    return resp


class TestEmitJsonAutoDecode:
    """When `response_format=json_schema` is set AND the adapter synthesized
    the `emit_json` tool, the resulting `tool_use` block is auto-decoded
    into a `TextPart` so callers don't have to know about the convention."""

    @patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
    def test_emit_json_tool_use_becomes_text_part(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        payload = {"score": 87, "feedback": "good work"}
        mock_client.messages.create.return_value = _mock_response(
            [_mock_tool_use_block("emit_json", payload)],
        )

        adapter = AnthropicAdapter(api_key="test-key")
        req = LLMRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content=[TextPart(text="grade")])],
            response_format=ResponseFormat(
                type="json_schema",
                schema={"type": "object",
                        "properties": {"score": {"type": "number"}}},
            ),
        )
        resp = adapter.chat(req)

        text_parts = [p for p in resp.content_parts if isinstance(p, TextPart)]
        assert len(text_parts) == 1, (
            f"expected exactly one TextPart from emit_json auto-decode, "
            f"got content_parts={resp.content_parts}"
        )
        assert json.loads(text_parts[0].text) == payload

    @patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
    def test_emit_json_tool_use_not_surfaced_in_tool_calls(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(
            [_mock_tool_use_block("emit_json", {"score": 87})],
        )

        adapter = AnthropicAdapter(api_key="test-key")
        req = LLMRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content=[TextPart(text="grade")])],
            response_format=ResponseFormat(
                type="json_schema",
                schema={"type": "object"},
            ),
        )
        resp = adapter.chat(req)

        assert resp.tool_calls == [], (
            "caller never asked for tools — emit_json must be absorbed by "
            f"the response_format auto-decode, got tool_calls={resp.tool_calls}"
        )

    @patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
    def test_emit_json_finish_reason_normalized_to_stop(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(
            [_mock_tool_use_block("emit_json", {"k": "v"})],
            stop_reason="tool_use",
        )

        adapter = AnthropicAdapter(api_key="test-key")
        req = LLMRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content=[TextPart(text="x")])],
            response_format=ResponseFormat(
                type="json_schema",
                schema={"type": "object"},
            ),
        )
        resp = adapter.chat(req)

        # Caller asked for JSON content, not a tool call. From their
        # perspective the model is "done" — stop_reason should reflect
        # that, matching OpenAI/Gemini json_schema responses.
        assert resp.finish_reason == "stop", (
            f"emit_json auto-decode should rewrite finish_reason from "
            f"tool_use → stop; got {resp.finish_reason}"
        )


class TestEmitJsonAutoDecodeOnlyWhenSynthesized:
    """Auto-decode must NOT fire when the adapter didn't synthesize the
    emit_json tool — otherwise we'd swallow a legitimate user-defined
    tool that happens to share the name."""

    @patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
    def test_user_tools_present_emit_json_stays_a_tool_call(self, mock_cls):
        """When user passed `tools=[...]`, the json_schema branch is
        skipped (existing behavior). If a model returns `emit_json` it
        must be a regular tool call — we did not synthesize it."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(
            [_mock_tool_use_block("emit_json", {"k": "v"})],
        )

        adapter = AnthropicAdapter(api_key="test-key")
        req = LLMRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content=[TextPart(text="x")])],
            tools=[ToolDef(name="my_tool", description="d",
                           input_schema={"type": "object"})],
            response_format=ResponseFormat(
                type="json_schema", schema={"type": "object"},
            ),
        )
        resp = adapter.chat(req)

        # emit_json must remain a tool call (we didn't synthesize it).
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "emit_json"
        # And no auto-decoded TextPart.
        assert not any(isinstance(p, TextPart) for p in resp.content_parts)

    @patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
    def test_other_tool_name_unchanged_when_emit_json_synthesized(
        self, mock_cls,
    ):
        """Adapter synthesized emit_json, but model called a *different*
        tool (would be a model bug, but we shouldn't swallow it). Pin
        that only the literal `emit_json` name is auto-decoded."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(
            [_mock_tool_use_block("not_emit_json", {"k": "v"})],
        )

        adapter = AnthropicAdapter(api_key="test-key")
        req = LLMRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content=[TextPart(text="x")])],
            response_format=ResponseFormat(
                type="json_schema", schema={"type": "object"},
            ),
        )
        resp = adapter.chat(req)

        # Off-name tool stays a tool call.
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "not_emit_json"
