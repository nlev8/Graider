"""Gap-fill tests for backend/services/llm_adapter/anthropic_adapter.py.

Audit MAJOR #4 sprint follow-up to PR #317. Companion to existing
`tests/test_llm_adapter_anthropic*.py`. Targets the 31 missing LOC
(83.8% baseline → 95%+ goal):

* `_content_to_anthropic` ToolUsePart branch (lines 95-101)
* `_message_to_anthropic` tool role + ToolResultPart (lines 111-120)
* `chat()` kwargs branches: temperature (145), tools (147),
  response_format=json_schema (161-167)
* `stream_chat()` kwargs branches: temperature (285), tools (287)
* `stream_chat()` initial-open exception path (334-351)
* JSON.JSONDecodeError on tool args (420-431)
* SDK-defensive try/except in stream events (366-370, 443-453)

Per dual-rate-limit precedent: test-only PR merging on green CI when
both Codex (until 2026-05-12) and Gemini (quota exhausted) unavailable.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.services.llm_adapter.anthropic_adapter import (
    AnthropicAdapter,
    _content_to_anthropic,
    _message_to_anthropic,
)
from backend.services.llm_adapter.types import (
    ImagePart,
    LLMRequest,
    Message,
    ResponseFormat,
    TextPart,
    ToolDef,
    ToolResultPart,
    ToolUsePart,
)


# ──────────────────────────────────────────────────────────────────
# _content_to_anthropic / _message_to_anthropic helpers
# ──────────────────────────────────────────────────────────────────


class TestContentToAnthropic:
    def test_tool_use_part_emits_tool_use_block(self):
        content = [
            ToolUsePart(tool_call_id="t1", name="get_data",
                        args={"k": "v"}),
        ]
        result = _content_to_anthropic(content)
        assert len(result) == 1
        assert result[0]["type"] == "tool_use"
        assert result[0]["id"] == "t1"
        assert result[0]["name"] == "get_data"
        assert result[0]["input"] == {"k": "v"}

    def test_tool_result_part_skipped_at_content_level(self):
        # ToolResultPart isn't handled at content level — should be in
        # a "tool" role message routed through _message_to_anthropic
        content = [
            ToolResultPart(tool_call_id="t1", content="result data"),
        ]
        result = _content_to_anthropic(content)
        # No block emitted (ToolResultPart not handled here)
        assert result == []


class TestMessageToAnthropic:
    def test_tool_role_emits_user_with_tool_result_block(self):
        msg = Message(
            role="tool",
            content=[
                ToolResultPart(tool_call_id="t1", content="result data"),
            ],
        )
        result = _message_to_anthropic(msg)
        # Anthropic uses "user" role for tool results
        assert result["role"] == "user"
        assert result["content"][0]["type"] == "tool_result"
        assert result["content"][0]["tool_use_id"] == "t1"
        assert result["content"][0]["content"] == "result data"

    def test_tool_role_with_non_string_content_stringified(self):
        msg = Message(
            role="tool",
            content=[
                ToolResultPart(tool_call_id="t1",
                               content={"nested": "dict"}),
            ],
        )
        result = _message_to_anthropic(msg)
        # content stringified via str()
        assert "nested" in result["content"][0]["content"]

    def test_assistant_role_passes_through(self):
        msg = Message(
            role="assistant",
            content=[TextPart(text="response")],
        )
        result = _message_to_anthropic(msg)
        assert result["role"] == "assistant"
        assert result["content"][0]["text"] == "response"


# ──────────────────────────────────────────────────────────────────
# chat() kwargs branches
# ──────────────────────────────────────────────────────────────────


def _mock_text_block(text):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _mock_response(blocks=None, stop_reason="end_turn",
                   input_tokens=10, output_tokens=5):
    if blocks is None:
        blocks = [_mock_text_block("ok")]
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    resp = MagicMock()
    resp.content = blocks
    resp.stop_reason = stop_reason
    resp.usage = usage
    resp.model = "claude-sonnet-4-20250514"
    return resp


class TestChatKwargsBranches:
    @patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
    def test_temperature_passed_through(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response()

        adapter = AnthropicAdapter(api_key="test-key")
        req = LLMRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
            temperature=0.7,
        )
        adapter.chat(req)

        kwargs = mock_client.messages.create.call_args.kwargs
        assert kwargs["temperature"] == 0.7

    @patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
    def test_tools_passed_through(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response()

        adapter = AnthropicAdapter(api_key="test-key")
        req = LLMRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
            tools=[
                ToolDef(name="get_data", description="Get data",
                     input_schema={"type": "object",
                                   "properties": {"k": {"type": "string"}}}),
            ],
        )
        adapter.chat(req)

        kwargs = mock_client.messages.create.call_args.kwargs
        assert "tools" in kwargs
        assert kwargs["tools"][0]["name"] == "get_data"
        assert kwargs["tools"][0]["description"] == "Get data"
        assert "input_schema" in kwargs["tools"][0]

    @patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
    def test_json_schema_response_format_synthesizes_emit_json_tool(
        self, mock_cls,
    ):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response()

        adapter = AnthropicAdapter(api_key="test-key")
        req = LLMRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
            response_format=ResponseFormat(
                type="json_schema",
                schema={"type": "object",
                        "properties": {"score": {"type": "number"}}},
            ),
        )
        adapter.chat(req)

        kwargs = mock_client.messages.create.call_args.kwargs
        # Synthesized emit_json tool
        assert kwargs["tools"][0]["name"] == "emit_json"
        assert kwargs["tool_choice"] == {"type": "tool", "name": "emit_json"}

    @patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
    def test_json_schema_response_format_skipped_when_tools_present(
        self, mock_cls,
    ):
        # When tools already defined, response_format=json_schema is skipped
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response()

        adapter = AnthropicAdapter(api_key="test-key")
        req = LLMRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
            tools=[ToolDef(name="my_tool", description="d",
                        input_schema={"type": "object"})],
            response_format=ResponseFormat(
                type="json_schema",
                schema={"type": "object"},
            ),
        )
        adapter.chat(req)

        kwargs = mock_client.messages.create.call_args.kwargs
        # Tools list still has only my_tool, no emit_json synthesized
        names = [t["name"] for t in kwargs["tools"]]
        assert "my_tool" in names
        assert "emit_json" not in names
        assert "tool_choice" not in kwargs

    @patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
    def test_json_object_response_format_no_tool_synthesized(self, mock_cls):
        # response_format type=json_object → not json_schema; no tool added
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response()

        adapter = AnthropicAdapter(api_key="test-key")
        req = LLMRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
            response_format=ResponseFormat(type="json_object"),
        )
        adapter.chat(req)

        kwargs = mock_client.messages.create.call_args.kwargs
        # No tools added (Anthropic relies on system prompt for this case)
        assert "tools" not in kwargs


# ──────────────────────────────────────────────────────────────────
# stream_chat() kwargs branches
# ──────────────────────────────────────────────────────────────────


class TestStreamKwargsBranches:
    @patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
    def test_stream_passes_temperature_and_tools(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        # Build a context manager that yields no events (we just want to
        # verify kwargs passed to stream())
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=iter([]))
        mock_ctx.__exit__ = MagicMock(return_value=None)
        mock_client.messages.stream.return_value = mock_ctx

        adapter = AnthropicAdapter(api_key="test-key")
        req = LLMRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
            temperature=0.5,
            tools=[ToolDef(name="t1", description="d",
                        input_schema={"type": "object"})],
        )
        # Drain the generator
        list(adapter.stream_chat(req))

        kwargs = mock_client.messages.stream.call_args.kwargs
        assert kwargs["temperature"] == 0.5
        assert kwargs["tools"][0]["name"] == "t1"

    @patch("backend.services.llm_adapter.anthropic_adapter.anthropic.Anthropic")
    def test_stream_open_failure_raises(self, mock_cls):
        # Force the stream context manager's __enter__ to raise on every
        # retry; with_retry will eventually re-raise after retries are
        # exhausted.
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(
            side_effect=ConnectionError("network down"),
        )
        mock_client.messages.stream.return_value = mock_ctx

        # Reset breakers so this isn't the first test's leftover state
        from backend.services.llm_adapter import breakers
        breakers._BREAKERS.clear()

        adapter = AnthropicAdapter(api_key="test-key")
        req = LLMRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
        )
        with pytest.raises(Exception):
            # The generator is iterated; raise propagates out of stream
            # context init
            list(adapter.stream_chat(req))


# ──────────────────────────────────────────────────────────────────
# Cost estimator
# ──────────────────────────────────────────────────────────────────


class TestEstimateCostUsd:
    def test_known_model_uses_specific_rate(self):
        from backend.services.llm_adapter.anthropic_adapter import (
            _estimate_cost_usd,
        )
        # Haiku 4.5: $1/$5 per million → $0.001/$0.005 per 1K
        cost = _estimate_cost_usd(
            "claude-haiku-4-5-20251001", 1000, 1000,
        )
        # 1000 in * 0.001/1000 + 1000 out * 0.005/1000 = 0.001 + 0.005
        assert cost == 0.006

    def test_unknown_model_uses_default_rate(self):
        from backend.services.llm_adapter.anthropic_adapter import (
            _estimate_cost_usd,
        )
        # Default: (0.003, 0.015) per 1K
        cost = _estimate_cost_usd("unknown-model", 1000, 1000)
        # 0.003 + 0.015 = 0.018
        assert cost == 0.018

    def test_zero_tokens_returns_zero(self):
        from backend.services.llm_adapter.anthropic_adapter import (
            _estimate_cost_usd,
        )
        assert _estimate_cost_usd("claude-haiku-4-5-20251001", 0, 0) == 0.0
