"""Tests for the Gemini adapter (Phase 5a PR D1)."""
from __future__ import annotations

import pytest
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
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_gemini_response()

    adapter = GeminiAdapter(api_key="test-key")
    req = LLMRequest(
        model="gemini-2.0-flash",
        system_prompt="You are a study guide generator.",
        messages=[Message(role="user", content=[TextPart(text="Create a guide.")])],
    )
    adapter.chat(req)

    # system_instruction must be passed via the config kwarg to generate_content
    mock_client.models.generate_content.assert_called_once()
    kwargs = mock_client.models.generate_content.call_args.kwargs
    assert kwargs["config"].system_instruction == "You are a study guide generator."


@patch("backend.services.llm_adapter.gemini_adapter.genai")
def test_assistant_role_maps_to_model_role(mock_genai):
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_gemini_response()

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

    mock_client.models.generate_content.assert_called_once()
    kwargs = mock_client.models.generate_content.call_args.kwargs
    contents = kwargs["contents"]
    assert contents[0]["role"] == "user"
    assert contents[1]["role"] == "model"   # "assistant" → "model"
    assert contents[2]["role"] == "user"


@patch("backend.services.llm_adapter.gemini_adapter.genai")
def test_base64_image_maps_to_inline_data(mock_genai):
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_gemini_response()

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

    mock_client.models.generate_content.assert_called_once()
    kwargs = mock_client.models.generate_content.call_args.kwargs
    contents = kwargs["contents"]
    user_parts = contents[0]["parts"]
    img_part = user_parts[0]
    assert "inline_data" in img_part
    assert img_part["inline_data"]["mime_type"] == "image/png"
    assert img_part["inline_data"]["data"] == "AAABBB"


@patch("backend.services.llm_adapter.gemini_adapter.genai")
def test_text_response_extracted(mock_genai):
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_gemini_response(
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
    mock_client = MagicMock()
    mock_genai.Client.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_gemini_response()

    adapter = GeminiAdapter(api_key="test-key")
    req = LLMRequest(
        model="gemini-2.0-flash",
        messages=[Message(role="user", content=[TextPart(text="hi")])],
    )
    adapter.chat(req)

    mock_client.models.generate_content.assert_called_once()
    kwargs = mock_client.models.generate_content.call_args.kwargs
    # system_instruction must NOT be set on the config object when no system prompt given
    assert not hasattr(kwargs["config"], "system_instruction") or kwargs["config"].system_instruction is None


def test_gemini_chat_uses_breaker():
    """Pattern matches OpenAI/Anthropic: 5 strikes open breaker within
    one user call (retries); 6th retry attempt raises CircuitBreakerError
    (non-retryable). Subsequent calls fast-fail."""
    import pybreaker
    from backend.services.llm_adapter import breakers

    breakers._BREAKERS.clear()

    with patch("backend.services.llm_adapter.gemini_adapter.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.side_effect = ConnectionError("down")

        from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
        from backend.services.llm_adapter.types import LLMRequest, Message, TextPart

        adapter = GeminiAdapter(api_key="test-key")
        req = LLMRequest(
            model="gemini-1.5-flash",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
        )

        with pytest.raises(pybreaker.CircuitBreakerError):
            adapter.chat(req)

        with pytest.raises(pybreaker.CircuitBreakerError):
            adapter.chat(req)


def test_gemini_adapter_uses_google_genai_sdk():
    """Post-migration, the adapter should import from google.genai, not
    google.generativeai."""
    import inspect
    import backend.services.llm_adapter.gemini_adapter as mod

    source = inspect.getsource(mod)
    assert "import google.generativeai" not in source, (
        "gemini_adapter.py still imports the deprecated google.generativeai SDK"
    )
    assert "from google import genai" in source
