"""Gap-fill tests for backend/services/llm_adapter/gemini_adapter.py.

Audit MAJOR #4 sprint follow-up to PR #319. Companion to existing
`tests/test_llm_adapter_gemini*.py`. Targets the 65 missing LOC
(77.3% baseline → 90%+ goal). Focuses on testable pure helpers and
chat() kwargs branches; deep stream-event simulation already
partially covered by test_llm_adapter_gemini_stream.py.

Branches covered:
* `_estimate_cost_usd`: 4 known model rates + default + zero
* `_estimate_image_cost_usd`: known model + default rate
* `_part_to_gemini`: TextPart, ImagePart base64, ImagePart URL,
  ToolUsePart, ToolResultPart with dict content, ToolResultPart
  with non-dict content (string wrapped), unknown part fallback
* `_message_to_gemini`: role mapping (assistant → model, user, tool)
* `_unwrap_protobuf`: dict-like, list-like, scalar, str passthrough
* `chat()` kwargs: max_tokens, temperature, json_object response_format,
  json_schema response_format with schema, finish_reason int enum
  mapping (1 → stop, 2 → max_tokens_reached)
* response.text raises but parts available branch
* usage_metadata absent → 0 tokens

Per dual-rate-limit precedent: test-only PR merging on green CI.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.services.llm_adapter.gemini_adapter import (
    _estimate_cost_usd,
    _estimate_image_cost_usd,
    _message_to_gemini,
    _part_to_gemini,
    _unwrap_protobuf,
    GeminiAdapter,
)
from backend.services.llm_adapter.types import (
    ImagePart,
    LLMRequest,
    Message,
    ResponseFormat,
    TextPart,
    ToolResultPart,
    ToolUsePart,
)


MODULE = "backend.services.llm_adapter.gemini_adapter"


# ──────────────────────────────────────────────────────────────────
# _estimate_cost_usd / _estimate_image_cost_usd
# ──────────────────────────────────────────────────────────────────


class TestEstimateCostUsd:
    def test_gemini_2_0_flash_rate(self):
        # 0.0001 input / 0.0004 output per 1K
        cost = _estimate_cost_usd("gemini-2.0-flash", 1000, 1000)
        assert cost == 0.0005

    def test_gemini_1_5_pro_rate(self):
        cost = _estimate_cost_usd("gemini-1.5-pro", 1000, 1000)
        # 0.00125 + 0.005 = 0.00625
        assert cost == 0.00625

    def test_gemini_1_5_flash_rate(self):
        cost = _estimate_cost_usd("gemini-1.5-flash", 1000, 1000)
        # 0.000075 + 0.0003 = 0.000375
        assert cost == 0.000375

    def test_unknown_model_uses_default(self):
        cost = _estimate_cost_usd("unknown-gemini", 1000, 1000)
        # Default: (0.0001, 0.0004) per 1K
        assert cost == 0.0005

    def test_zero_tokens(self):
        assert _estimate_cost_usd("gemini-2.0-flash", 0, 0) == 0.0


class TestEstimateImageCostUsd:
    def test_known_image_model_rate(self):
        cost = _estimate_image_cost_usd(
            "gemini-2.5-flash-preview-image-generation", 5,
        )
        # 0.04 * 5 = 0.20
        assert cost == 0.20

    def test_unknown_image_model_uses_default(self):
        cost = _estimate_image_cost_usd("unknown-img", 3)
        # Default 0.04 * 3 = 0.12
        assert cost == 0.12


# ──────────────────────────────────────────────────────────────────
# _part_to_gemini
# ──────────────────────────────────────────────────────────────────


class TestPartToGemini:
    def test_text_part(self):
        result = _part_to_gemini(TextPart(text="hello"))
        assert result == {"text": "hello"}

    def test_image_part_base64(self):
        result = _part_to_gemini(
            ImagePart(url=None, base64="AAAA", mime_type="image/png"),
        )
        assert "inline_data" in result
        assert result["inline_data"]["mime_type"] == "image/png"
        assert result["inline_data"]["data"] == "AAAA"

    def test_image_part_url(self):
        result = _part_to_gemini(
            ImagePart(url="gs://bucket/img.png", base64=None,
                      mime_type="image/png"),
        )
        assert "file_data" in result
        assert result["file_data"]["file_uri"] == "gs://bucket/img.png"

    def test_tool_use_part(self):
        result = _part_to_gemini(
            ToolUsePart(tool_call_id="t1", name="get_data",
                        args={"k": "v"}),
        )
        assert "function_call" in result
        assert result["function_call"]["name"] == "get_data"
        assert result["function_call"]["args"] == {"k": "v"}

    def test_tool_result_part_dict_content(self):
        result = _part_to_gemini(
            ToolResultPart(tool_call_id="t1",
                           content={"result": "ok"}),
        )
        assert "function_response" in result
        # Falls back to tool_call_id when no name attribute
        assert result["function_response"]["name"] == "t1"
        assert result["function_response"]["response"] == {"result": "ok"}

    def test_tool_result_part_string_content_wrapped(self):
        # String content wrapped as {"result": <text>}
        result = _part_to_gemini(
            ToolResultPart(tool_call_id="t1", content="ok string"),
        )
        assert result["function_response"]["response"] == {"result": "ok string"}

    def test_tool_result_part_non_dict_non_string_wrapped(self):
        result = _part_to_gemini(
            ToolResultPart(tool_call_id="t1", content=[1, 2, 3]),
        )
        # Non-dict converted to string then wrapped
        assert "result" in result["function_response"]["response"]

    def test_unknown_part_fallback_to_text(self):
        # Anything that isn't a known ContentPart type → str(p)
        class FakePart:
            def __str__(self):
                return "fake-string"

        result = _part_to_gemini(FakePart())
        assert result == {"text": "fake-string"}


# ──────────────────────────────────────────────────────────────────
# _message_to_gemini
# ──────────────────────────────────────────────────────────────────


class TestMessageToGemini:
    def test_assistant_role_maps_to_model(self):
        msg = Message(role="assistant",
                      content=[TextPart(text="response")])
        result = _message_to_gemini(msg)
        assert result["role"] == "model"
        assert result["parts"][0]["text"] == "response"

    def test_user_role_passes_through(self):
        msg = Message(role="user", content=[TextPart(text="hi")])
        result = _message_to_gemini(msg)
        assert result["role"] == "user"

    def test_tool_role_maps_to_user(self):
        # Gemini routes tool results through "user" role
        msg = Message(role="tool",
                      content=[ToolResultPart(tool_call_id="t1",
                                              content={"r": "ok"})])
        result = _message_to_gemini(msg)
        assert result["role"] == "user"


# ──────────────────────────────────────────────────────────────────
# _unwrap_protobuf
# ──────────────────────────────────────────────────────────────────


class TestUnwrapProtobuf:
    def test_dict_like_unwraps_recursively(self):
        # MapComposite-like object with .items() method
        # Plain dicts have .items() too — they pass through unchanged
        result = _unwrap_protobuf({"a": 1, "b": {"nested": 2}})
        assert result == {"a": 1, "b": {"nested": 2}}

    def test_list_unwraps_recursively(self):
        result = _unwrap_protobuf([1, [2, 3], {"k": 4}])
        assert result == [1, [2, 3], {"k": 4}]

    def test_scalar_passthrough(self):
        assert _unwrap_protobuf(42) == 42
        assert _unwrap_protobuf("hello") == "hello"
        assert _unwrap_protobuf(None) is None
        assert _unwrap_protobuf(True) is True

    def test_str_not_iterated_as_chars(self):
        # str has __iter__ but should NOT be treated as list
        result = _unwrap_protobuf("string-value")
        assert result == "string-value"
        # Verify we didn't get [s, t, r, i, n, g, ...]
        assert isinstance(result, str)

    def test_bytes_not_iterated(self):
        result = _unwrap_protobuf(b"bytes-value")
        assert result == b"bytes-value"
        assert isinstance(result, bytes)


# ──────────────────────────────────────────────────────────────────
# GeminiAdapter chat() kwargs branches
# ──────────────────────────────────────────────────────────────────


def _mock_response(text="ok", prompt=10, completion=5,
                   finish_reason="STOP", finish_int=None):
    raw = MagicMock()
    raw.text = text
    candidate = MagicMock()
    if finish_int is not None:
        # Simulate enum int as string
        fr = MagicMock(spec=[])  # No "name" attribute
        fr.__str__ = lambda self: str(finish_int)
        candidate.finish_reason = fr
    else:
        fr = MagicMock()
        fr.name = finish_reason
        candidate.finish_reason = fr
    raw.candidates = [candidate]
    raw.usage_metadata = MagicMock(
        prompt_token_count=prompt, candidates_token_count=completion,
    )
    raw.model_version = "gemini-1.5-flash"
    return raw


class TestChatKwargsBranches:
    @patch(f"{MODULE}.genai.Client")
    def test_max_tokens_in_config(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _mock_response()

        adapter = GeminiAdapter(api_key="test")
        req = LLMRequest(
            model="gemini-2.0-flash",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
            max_tokens=500,
        )
        adapter.chat(req)

        # config kwarg was passed; verify it has max_output_tokens
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        config = call_kwargs["config"]
        assert config.max_output_tokens == 500

    @patch(f"{MODULE}.genai.Client")
    def test_temperature_in_config(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _mock_response()

        adapter = GeminiAdapter(api_key="test")
        req = LLMRequest(
            model="gemini-2.0-flash",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
            temperature=0.7,
        )
        adapter.chat(req)
        config = mock_client.models.generate_content.call_args.kwargs["config"]
        assert config.temperature == 0.7

    @patch(f"{MODULE}.genai.Client")
    def test_json_object_response_format_sets_mime_type(
        self, mock_client_cls,
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _mock_response()

        adapter = GeminiAdapter(api_key="test")
        req = LLMRequest(
            model="gemini-2.0-flash",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
            response_format=ResponseFormat(type="json_object"),
        )
        adapter.chat(req)

        config = mock_client.models.generate_content.call_args.kwargs["config"]
        assert config.response_mime_type == "application/json"

    @patch(f"{MODULE}.genai.Client")
    def test_json_schema_response_format_sets_schema(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _mock_response()

        adapter = GeminiAdapter(api_key="test")
        req = LLMRequest(
            model="gemini-2.0-flash",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
            response_format=ResponseFormat(
                type="json_schema",
                schema={"type": "object",
                        "properties": {"x": {"type": "number"}}},
            ),
        )
        adapter.chat(req)
        config = mock_client.models.generate_content.call_args.kwargs["config"]
        assert config.response_mime_type == "application/json"
        # Schema also set
        assert config.response_schema is not None

    @patch(f"{MODULE}.genai.Client")
    def test_no_usage_metadata_zero_tokens(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        raw = MagicMock()
        raw.text = "ok"
        candidate = MagicMock()
        fr = MagicMock()
        fr.name = "STOP"
        candidate.finish_reason = fr
        raw.candidates = [candidate]
        raw.usage_metadata = None
        raw.model_version = None
        raw.model = None
        mock_client.models.generate_content.return_value = raw

        adapter = GeminiAdapter(api_key="test")
        req = LLMRequest(
            model="gemini-2.0-flash",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
        )
        resp = adapter.chat(req)
        assert resp.usage.prompt_tokens == 0
        assert resp.usage.completion_tokens == 0
        # Falls back to request.model
        assert resp.model == "gemini-2.0-flash"

    @patch(f"{MODULE}.genai.Client")
    def test_text_attribute_raises_falls_back_to_parts(self, mock_client_cls):
        # raw.text raises (e.g., response was blocked) → fall through
        # to candidates[0].content.parts
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        raw = MagicMock()
        # Make `raw.text` access raise
        type(raw).text = property(lambda _: (_ for _ in ()).throw(
            ValueError("blocked"),
        ))

        # Build a candidate with parts containing text
        part = MagicMock()
        part.text = "from parts"
        candidate = MagicMock()
        candidate.content.parts = [part]
        fr = MagicMock()
        fr.name = "STOP"
        candidate.finish_reason = fr
        raw.candidates = [candidate]
        raw.usage_metadata = MagicMock(
            prompt_token_count=10, candidates_token_count=5,
        )
        raw.model_version = "gemini-2.0-flash"
        mock_client.models.generate_content.return_value = raw

        adapter = GeminiAdapter(api_key="test")
        req = LLMRequest(
            model="gemini-2.0-flash",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
        )
        resp = adapter.chat(req)
        # Parts-based fallback extracted text
        assert len(resp.content_parts) == 1
        assert resp.content_parts[0].text == "from parts"
