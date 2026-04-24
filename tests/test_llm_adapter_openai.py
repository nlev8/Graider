"""Tests for the OpenAI adapter (Phase 5a PR D1)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.services.llm_adapter.openai_adapter import OpenAIAdapter
from backend.services.llm_adapter.types import (
    ImagePart,
    LLMRequest,
    LLMResponse,
    Message,
    ResponseFormat,
    TextPart,
)


def _mock_openai_response(text: str = "hello", finish_reason: str = "stop"):
    choice = MagicMock()
    choice.message.content = text
    choice.message.tool_calls = None
    choice.finish_reason = finish_reason

    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 5
    usage.total_tokens = 15

    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    resp.model = "gpt-4"
    return resp


@patch("backend.services.llm_adapter.openai_adapter.OpenAI")
def test_adapter_maps_simple_text_message(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response()

    adapter = OpenAIAdapter(api_key="test-key")
    req = LLMRequest(
        model="gpt-4",
        messages=[Message(role="user", content=[TextPart(text="hello")])],
    )
    resp = adapter.chat(req)

    assert resp.provider == "openai"
    assert resp.model == "gpt-4"
    assert resp.content_parts == [TextPart(text="hello")]
    assert resp.finish_reason == "stop"
    assert resp.usage.prompt_tokens == 10

    # Verify the mapping sent to OpenAI
    mock_client.chat.completions.create.assert_called_once()
    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-4"
    assert kwargs["messages"] == [{"role": "user", "content": "hello"}]


@patch("backend.services.llm_adapter.openai_adapter.OpenAI")
def test_adapter_maps_system_prompt_to_system_message(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response()

    adapter = OpenAIAdapter(api_key="test-key")
    req = LLMRequest(
        model="gpt-4",
        system_prompt="You are a helpful assistant.",
        messages=[Message(role="user", content=[TextPart(text="hi")])],
    )
    adapter.chat(req)

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["messages"][0] == {
        "role": "system",
        "content": "You are a helpful assistant.",
    }
    assert kwargs["messages"][1] == {"role": "user", "content": "hi"}


@patch("backend.services.llm_adapter.openai_adapter.OpenAI")
def test_adapter_maps_image_part_to_image_url_content(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response()

    adapter = OpenAIAdapter(api_key="test-key")
    req = LLMRequest(
        model="gpt-4",
        messages=[Message(
            role="user",
            content=[
                TextPart(text="What's in this image?"),
                ImagePart(url="https://example.com/x.png", base64=None, mime_type="image/png"),
            ],
        )],
    )
    adapter.chat(req)

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    user_msg = kwargs["messages"][0]
    assert user_msg["role"] == "user"
    assert isinstance(user_msg["content"], list)
    assert user_msg["content"][0] == {"type": "text", "text": "What's in this image?"}
    assert user_msg["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "https://example.com/x.png"},
    }


@patch("backend.services.llm_adapter.openai_adapter.OpenAI")
def test_adapter_maps_base64_image_to_data_url(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response()

    adapter = OpenAIAdapter(api_key="test-key")
    req = LLMRequest(
        model="gpt-4o",
        messages=[Message(
            role="user",
            content=[
                ImagePart(url=None, base64="AAABBB", mime_type="image/jpeg"),
                TextPart(text="Describe this."),
            ],
        )],
    )
    adapter.chat(req)

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    user_msg = kwargs["messages"][0]
    img_part = user_msg["content"][0]
    assert img_part["type"] == "image_url"
    assert img_part["image_url"]["url"] == "data:image/jpeg;base64,AAABBB"


@patch("backend.services.llm_adapter.openai_adapter.OpenAI")
def test_adapter_maps_json_object_response_format(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response(text='{"key": "val"}')

    adapter = OpenAIAdapter(api_key="test-key")
    req = LLMRequest(
        model="gpt-4o-mini",
        messages=[Message(role="user", content=[TextPart(text="Give me JSON")])],
        response_format=ResponseFormat(type="json_object"),
    )
    adapter.chat(req)

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}


def test_openai_chat_uses_breaker():
    """5 consecutive network errors trip the breaker; subsequent calls fail fast.

    with_retry makes up to 6 total attempts (1 initial + 5 retries). The first
    5 raw failures trip the breaker (fail_max=5). The 6th retry attempt hits the
    already-open breaker and raises CircuitBreakerError, which non_retryable
    propagates immediately. So the first user-level call raises CircuitBreakerError
    (not ConnectionError), and all subsequent calls also raise CircuitBreakerError.
    """
    import pybreaker
    from backend.services.llm_adapter import breakers

    breakers._BREAKERS.clear()

    with patch("backend.services.llm_adapter.openai_adapter.OpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = ConnectionError("down")

        adapter = OpenAIAdapter(api_key="test-key")
        req = LLMRequest(
            model="gpt-4o",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
        )

        # After 5 raw strikes the breaker opens; the 6th attempt inside retry
        # hits the open breaker → CircuitBreakerError propagates immediately.
        with pytest.raises(pybreaker.CircuitBreakerError):
            adapter.chat(req)

        # Subsequent calls also hit the OPEN breaker → CircuitBreakerError
        with pytest.raises(pybreaker.CircuitBreakerError):
            adapter.chat(req)


def test_openai_chat_breaker_error_is_not_retried():
    """When breaker is already OPEN, with_retry sees CircuitBreakerError
    as non-retryable and propagates it without backoff."""
    import pybreaker
    from backend.services.llm_adapter import breakers

    breakers._BREAKERS.clear()

    # Pre-open the breaker
    b = breakers.get_breaker("openai", "gpt-4o")
    # Force open by recording 5 failures directly
    for _ in range(5):
        try:
            b.call(lambda: (_ for _ in ()).throw(ConnectionError("x")))
        except ConnectionError:
            pass
        except pybreaker.CircuitBreakerError:
            pass
    assert b.current_state == pybreaker.STATE_OPEN

    with patch("backend.services.llm_adapter.openai_adapter.OpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        call_count = {"n": 0}

        def side_effect(**_):
            call_count["n"] += 1
            return MagicMock()

        mock_client.chat.completions.create.side_effect = side_effect

        adapter = OpenAIAdapter(api_key="test-key")
        req = LLMRequest(
            model="gpt-4o",
            messages=[Message(role="user", content=[TextPart(text="hi")])],
        )

        with pytest.raises(pybreaker.CircuitBreakerError):
            adapter.chat(req)

        # Zero network calls — breaker short-circuited, retry didn't cycle
        assert call_count["n"] == 0


@patch("backend.services.llm_adapter.openai_adapter.OpenAI")
def test_openai_adapter_passes_image_detail_through(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response()

    adapter = OpenAIAdapter(api_key="test-key")
    req = LLMRequest(
        model="gpt-4o",
        messages=[Message(
            role="user",
            content=[
                TextPart(text="OCR this"),
                ImagePart(url="http://img", base64=None, mime_type="image/png", detail="high"),
            ],
        )],
    )
    adapter.chat(req)

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    user_msg = kwargs["messages"][0]
    image_part = next(p for p in user_msg["content"] if p["type"] == "image_url")
    assert image_part["image_url"]["detail"] == "high"


@patch("backend.services.llm_adapter.openai_adapter.OpenAI")
def test_openai_adapter_omits_image_detail_when_none(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_openai_response()

    adapter = OpenAIAdapter(api_key="test-key")
    req = LLMRequest(
        model="gpt-4o",
        messages=[Message(
            role="user",
            content=[
                TextPart(text="hi"),
                ImagePart(url="http://img", base64=None, mime_type="image/png"),
            ],
        )],
    )
    adapter.chat(req)

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    user_msg = kwargs["messages"][0]
    image_part = next(p for p in user_msg["content"] if p["type"] == "image_url")
    assert "detail" not in image_part["image_url"]
