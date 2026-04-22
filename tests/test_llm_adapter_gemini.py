"""Tests for the Gemini adapter (Phase 5a PR D1)."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
from backend.services.llm_adapter.types import (
    ImagePart,
    LLMRequest,
    LLMResponse,
    Message,
    TextPart,
)


def _mock_gemini_response(text: str = "hello", finish_name: str = "STOP"):
    finish_reason = MagicMock()
    finish_reason.name = finish_name

    candidate = MagicMock()
    candidate.finish_reason = finish_reason

    usage = MagicMock()
    usage.prompt_token_count = 8
    usage.candidates_token_count = 4

    resp = MagicMock()
    resp.text = text
    resp.candidates = [candidate]
    resp.usage_metadata = usage
    return resp


@patch("backend.services.llm_adapter.gemini_adapter.genai")
def test_system_prompt_maps_to_system_instruction(mock_genai):
    mock_model = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model
    mock_model.generate_content.return_value = _mock_gemini_response()

    adapter = GeminiAdapter(api_key="test-key")
    req = LLMRequest(
        model="gemini-2.0-flash",
        system_prompt="You are a study guide generator.",
        messages=[Message(role="user", content=[TextPart(text="Create a guide.")])],
    )
    adapter.chat(req)

    # system_instruction must be passed to GenerativeModel constructor
    call_kwargs = mock_genai.GenerativeModel.call_args.kwargs
    assert call_kwargs.get("system_instruction") == "You are a study guide generator."


@patch("backend.services.llm_adapter.gemini_adapter.genai")
def test_assistant_role_maps_to_model_role(mock_genai):
    mock_model = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model
    mock_model.generate_content.return_value = _mock_gemini_response()

    adapter = GeminiAdapter(api_key="test-key")
    req = LLMRequest(
        model="gemini-2.0-flash",
        messages=[
            Message(role="user", content=[TextPart(text="Hello")]),
            Message(role="assistant", content=[TextPart(text="Hi there")]),
            Message(role="user", content=[TextPart(text="Thanks")]),
        ],
    )
    adapter.chat(req)

    contents = mock_model.generate_content.call_args.args[0]
    assert contents[0]["role"] == "user"
    assert contents[1]["role"] == "model"   # "assistant" → "model"
    assert contents[2]["role"] == "user"


@patch("backend.services.llm_adapter.gemini_adapter.genai")
def test_base64_image_maps_to_inline_data(mock_genai):
    mock_model = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model
    mock_model.generate_content.return_value = _mock_gemini_response()

    adapter = GeminiAdapter(api_key="test-key")
    req = LLMRequest(
        model="gemini-2.0-flash",
        messages=[Message(
            role="user",
            content=[
                ImagePart(url=None, base64="AAABBB", mime_type="image/png"),
                TextPart(text="Describe this image."),
            ],
        )],
    )
    adapter.chat(req)

    contents = mock_model.generate_content.call_args.args[0]
    user_parts = contents[0]["parts"]
    img_part = user_parts[0]
    assert "inline_data" in img_part
    assert img_part["inline_data"]["mime_type"] == "image/png"
    assert img_part["inline_data"]["data"] == "AAABBB"


@patch("backend.services.llm_adapter.gemini_adapter.genai")
def test_text_response_extracted(mock_genai):
    mock_model = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model
    mock_model.generate_content.return_value = _mock_gemini_response(
        text="Here is your study guide."
    )

    adapter = GeminiAdapter(api_key="test-key")
    req = LLMRequest(
        model="gemini-2.0-flash",
        messages=[Message(role="user", content=[TextPart(text="Make a guide.")])],
    )
    resp = adapter.chat(req)

    assert resp.provider == "gemini"
    assert len(resp.content_parts) == 1
    assert isinstance(resp.content_parts[0], TextPart)
    assert resp.content_parts[0].text == "Here is your study guide."
    assert resp.tool_calls == []
    assert resp.usage.prompt_tokens == 8
    assert resp.usage.completion_tokens == 4


@patch("backend.services.llm_adapter.gemini_adapter.genai")
def test_no_system_prompt_omits_system_instruction(mock_genai):
    mock_model = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model
    mock_model.generate_content.return_value = _mock_gemini_response()

    adapter = GeminiAdapter(api_key="test-key")
    req = LLMRequest(
        model="gemini-2.0-flash",
        messages=[Message(role="user", content=[TextPart(text="hi")])],
    )
    adapter.chat(req)

    call_kwargs = mock_genai.GenerativeModel.call_args.kwargs
    assert "system_instruction" not in call_kwargs
