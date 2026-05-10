"""Gap-fill tests for backend/services/llm_adapter/openai_adapter.py.

Audit MAJOR #4 sprint follow-up to PR #318. Companion to existing
`tests/test_llm_adapter_openai*.py`. Targets the 39 missing LOC
(81.2% baseline → 95%+ goal):

* `_content_to_openai` ImagePart with url/base64/detail variants
* `_message_to_openai`: tool-role with non-string content stringify,
  tool-role fallback (no ToolResultPart), assistant with tool_calls
  + text empty, user role passthrough
* `_expand_messages_for_openai`: multi-ToolResultPart split
* `chat()` kwargs: max_tokens, temperature, response_format=
  json_object, json_schema, tools list, tool_calls in response, no
  message content
* `_estimate_cost_usd`: known/unknown models, gpt-4o specific rate

Per dual-rate-limit precedent: test-only PR merging on green CI when
both Codex (until 2026-05-12) and Gemini (quota exhausted) unavailable.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.services.llm_adapter.openai_adapter import (
    OpenAIAdapter,
    _content_to_openai,
    _expand_messages_for_openai,
    _message_to_openai,
    _estimate_cost_usd,
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
# _content_to_openai variants
# ──────────────────────────────────────────────────────────────────


class TestContentToOpenAI:
    def test_single_text_returns_string(self):
        result = _content_to_openai([TextPart(text="hello")])
        assert result == "hello"

    def test_multimodal_returns_parts_list(self):
        # Multiple parts → array form
        result = _content_to_openai([
            TextPart(text="describe"),
            ImagePart(url="http://x.com/img.png",
                      base64=None, mime_type="image/png"),
        ])
        assert isinstance(result, list)
        assert result[0]["type"] == "text"
        assert result[0]["text"] == "describe"
        assert result[1]["type"] == "image_url"
        assert result[1]["image_url"]["url"] == "http://x.com/img.png"

    def test_base64_image_built_as_data_url(self):
        result = _content_to_openai([
            TextPart(text="x"),
            ImagePart(url=None, base64="AAAA", mime_type="image/png"),
        ])
        # data: URL form
        assert "data:image/png;base64,AAAA" == result[1]["image_url"]["url"]

    def test_image_with_detail_passes_through(self):
        result = _content_to_openai([
            TextPart(text="x"),
            ImagePart(url="http://ex.com/img.jpg",
                      base64=None, mime_type="image/jpeg",
                      detail="high"),
        ])
        assert result[1]["image_url"]["detail"] == "high"


# ──────────────────────────────────────────────────────────────────
# _message_to_openai branches
# ──────────────────────────────────────────────────────────────────


class TestMessageToOpenAI:
    def test_tool_role_with_string_content(self):
        msg = Message(
            role="tool",
            content=[ToolResultPart(tool_call_id="t1", content="result")],
        )
        result = _message_to_openai(msg)
        assert result["role"] == "tool"
        assert result["tool_call_id"] == "t1"
        assert result["content"] == "result"

    def test_tool_role_with_non_string_content_jsonified(self):
        msg = Message(
            role="tool",
            content=[ToolResultPart(tool_call_id="t1",
                                    content={"data": [1, 2]})],
        )
        result = _message_to_openai(msg)
        # Non-string content is JSON-serialized (not str())
        loaded = json.loads(result["content"])
        assert loaded == {"data": [1, 2]}

    def test_tool_role_no_result_part_fallback(self):
        # Tool role with no ToolResultPart → fallback empty content
        msg = Message(
            role="tool",
            content=[TextPart(text="not a result")],
            tool_call_id="t1",
        )
        result = _message_to_openai(msg)
        assert result["role"] == "tool"
        assert result["content"] == ""
        assert result["tool_call_id"] == "t1"

    def test_assistant_with_tool_calls_and_text(self):
        msg = Message(
            role="assistant",
            content=[
                TextPart(text="thinking..."),
                ToolUsePart(tool_call_id="t1", name="get_data",
                            args={"k": "v"}),
            ],
        )
        result = _message_to_openai(msg)
        assert result["role"] == "assistant"
        assert result["content"] == "thinking..."
        assert len(result["tool_calls"]) == 1
        tc = result["tool_calls"][0]
        assert tc["id"] == "t1"
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "get_data"
        # arguments are JSON-serialized
        assert json.loads(tc["function"]["arguments"]) == {"k": "v"}

    def test_assistant_with_only_tool_calls_content_is_none(self):
        msg = Message(
            role="assistant",
            content=[
                ToolUsePart(tool_call_id="t1", name="tool",
                            args={}),
            ],
        )
        result = _message_to_openai(msg)
        # No text → content is None (OpenAI requires content OR tool_calls)
        assert result["content"] is None
        assert "tool_calls" in result

    def test_user_role_passes_through_content(self):
        msg = Message(
            role="user",
            content=[TextPart(text="hello")],
        )
        result = _message_to_openai(msg)
        assert result["role"] == "user"
        # Single TextPart → string shorthand
        assert result["content"] == "hello"


# ──────────────────────────────────────────────────────────────────
# _expand_messages_for_openai - multi-ToolResultPart split
# ──────────────────────────────────────────────────────────────────


class TestExpandMessagesForOpenAI:
    def test_multi_tool_result_parts_split_into_separate_messages(self):
        # One Message.content with 2 ToolResultPart → 2 tool-role messages
        msg = Message(
            role="tool",
            content=[
                ToolResultPart(tool_call_id="t1", content="r1"),
                ToolResultPart(tool_call_id="t2", content="r2"),
            ],
        )
        result = _expand_messages_for_openai([msg])
        assert len(result) == 2
        ids = {m["tool_call_id"] for m in result}
        assert ids == {"t1", "t2"}

    def test_single_tool_result_part_passes_through(self):
        msg = Message(
            role="tool",
            content=[ToolResultPart(tool_call_id="t1", content="r")],
        )
        result = _expand_messages_for_openai([msg])
        assert len(result) == 1
        assert result[0]["tool_call_id"] == "t1"

    def test_non_tool_message_passes_through(self):
        msg = Message(
            role="user",
            content=[TextPart(text="hi")],
        )
        result = _expand_messages_for_openai([msg])
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_multi_tool_result_with_non_string_content_jsonified(self):
        msg = Message(
            role="tool",
            content=[
                ToolResultPart(tool_call_id="t1",
                               content={"a": 1}),
                ToolResultPart(tool_call_id="t2",
                               content={"b": 2}),
            ],
        )
        result = _expand_messages_for_openai([msg])
        for m in result:
            # JSON-serialized
            json.loads(m["content"])


# ──────────────────────────────────────────────────────────────────
# OpenAIAdapter chat() branches
# ──────────────────────────────────────────────────────────────────


def _mock_response(text="ok", tool_calls=None,
                   prompt_tokens=10, completion_tokens=5,
                   finish="stop"):
    msg = MagicMock()
    msg.content = text
    msg.tool_calls = tool_calls
    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = finish
    raw = MagicMock()
    raw.choices = [choice]
    raw.usage = MagicMock(prompt_tokens=prompt_tokens,
                          completion_tokens=completion_tokens)
    raw.model = "gpt-4o-mini"
    return raw


class TestChatKwargsBranches:
    @patch("backend.services.llm_adapter.openai_adapter.OpenAI")
    def test_max_tokens_passed_through(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        adapter = OpenAIAdapter(api_key="test")
        req = LLMRequest(
            model="gpt-4o-mini",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
            max_tokens=500,
        )
        adapter.chat(req)

        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["max_tokens"] == 500

    @patch("backend.services.llm_adapter.openai_adapter.OpenAI")
    def test_temperature_passed_through(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        adapter = OpenAIAdapter(api_key="test")
        req = LLMRequest(
            model="gpt-4o-mini",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
            temperature=0.3,
        )
        adapter.chat(req)
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["temperature"] == 0.3

    @patch("backend.services.llm_adapter.openai_adapter.OpenAI")
    def test_json_object_response_format(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        adapter = OpenAIAdapter(api_key="test")
        req = LLMRequest(
            model="gpt-4o-mini",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
            response_format=ResponseFormat(type="json_object"),
        )
        adapter.chat(req)
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["response_format"] == {"type": "json_object"}

    @patch("backend.services.llm_adapter.openai_adapter.OpenAI")
    def test_json_schema_response_format(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        adapter = OpenAIAdapter(api_key="test")
        req = LLMRequest(
            model="gpt-4o-mini",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
            response_format=ResponseFormat(
                type="json_schema",
                schema={"type": "object",
                        "properties": {"x": {"type": "number"}}},
            ),
        )
        adapter.chat(req)
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["response_format"]["type"] == "json_schema"
        assert "json_schema" in kwargs["response_format"]

    @patch("backend.services.llm_adapter.openai_adapter.OpenAI")
    def test_tools_passed_through(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = _mock_response()

        adapter = OpenAIAdapter(api_key="test")
        req = LLMRequest(
            model="gpt-4o-mini",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
            tools=[ToolDef(name="get_data", description="d",
                           input_schema={"type": "object"})],
        )
        adapter.chat(req)
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert kwargs["tools"][0]["type"] == "function"
        assert kwargs["tools"][0]["function"]["name"] == "get_data"

    @patch("backend.services.llm_adapter.openai_adapter.OpenAI")
    def test_response_with_tool_calls(self, mock_cls):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        # Build response with tool_calls populated
        tc = MagicMock()
        tc.id = "call-1"
        tc.function.name = "get_data"
        tc.function.arguments = json.dumps({"k": "v"})
        mock_client.chat.completions.create.return_value = _mock_response(
            text=None, tool_calls=[tc], finish="tool_calls",
        )

        adapter = OpenAIAdapter(api_key="test")
        req = LLMRequest(
            model="gpt-4o-mini",
            messages=[Message(role="user",
                              content=[TextPart(text="use tool")])],
        )
        resp = adapter.chat(req)
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].tool_call_id == "call-1"
        assert resp.tool_calls[0].name == "get_data"
        assert resp.tool_calls[0].args == {"k": "v"}
        # No content_parts (msg.content was None)
        assert resp.content_parts == []

    @patch("backend.services.llm_adapter.openai_adapter.OpenAI")
    def test_response_with_dict_arguments_passed_directly(self, mock_cls):
        # Some SDK versions return arguments as dict instead of JSON
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        tc = MagicMock()
        tc.id = "call-1"
        tc.function.name = "f"
        tc.function.arguments = {"k": "v"}  # already dict
        mock_client.chat.completions.create.return_value = _mock_response(
            text=None, tool_calls=[tc], finish="tool_calls",
        )

        adapter = OpenAIAdapter(api_key="test")
        req = LLMRequest(
            model="gpt-4o-mini",
            messages=[Message(role="user",
                              content=[TextPart(text="x")])],
        )
        resp = adapter.chat(req)
        # Dict passed directly (not JSON-decoded)
        assert resp.tool_calls[0].args == {"k": "v"}

    @patch("backend.services.llm_adapter.openai_adapter.OpenAI")
    def test_no_usage_field_yields_zero_tokens(self, mock_cls):
        # If usage is None, prompt+completion tokens fall back to 0
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        msg = MagicMock()
        msg.content = "ok"
        msg.tool_calls = None
        choice = MagicMock()
        choice.message = msg
        choice.finish_reason = "stop"
        raw = MagicMock()
        raw.choices = [choice]
        raw.usage = None
        raw.model = "gpt-4o-mini"
        mock_client.chat.completions.create.return_value = raw

        adapter = OpenAIAdapter(api_key="test")
        req = LLMRequest(
            model="gpt-4o-mini",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
        )
        resp = adapter.chat(req)
        assert resp.usage.prompt_tokens == 0
        assert resp.usage.completion_tokens == 0
        assert resp.usage.cost_usd == 0.0


# ──────────────────────────────────────────────────────────────────
# _estimate_cost_usd
# ──────────────────────────────────────────────────────────────────


class TestEstimateCostUsdOpenAI:
    def test_gpt_4o_mini_specific_rate(self):
        # 0.00015 input / 0.0006 output per 1K
        cost = _estimate_cost_usd("gpt-4o-mini", 1000, 1000)
        # 0.00015 + 0.0006 = 0.00075
        assert cost == 0.00075

    def test_gpt_4o_specific_rate(self):
        # 0.0025 / 0.010 per 1K
        cost = _estimate_cost_usd("gpt-4o", 1000, 1000)
        # 0.0025 + 0.010 = 0.0125
        assert cost == 0.0125

    def test_gpt_4_full_rate(self):
        # 0.03 / 0.06 per 1K
        cost = _estimate_cost_usd("gpt-4", 1000, 1000)
        assert cost == 0.09

    def test_unknown_model_uses_default_rate(self):
        # Default: (0.01, 0.03)
        cost = _estimate_cost_usd("unknown-gpt", 1000, 1000)
        assert cost == 0.04

    def test_zero_tokens_zero_cost(self):
        assert _estimate_cost_usd("gpt-4o-mini", 0, 0) == 0.0
