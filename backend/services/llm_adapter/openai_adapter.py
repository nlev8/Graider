"""OpenAI adapter for the Phase 5a LLM adapter layer.

Maps LLMRequest/Response to/from openai.chat.completions.create.
"""
from __future__ import annotations

import json as _json
import logging
import os
import time
from typing import Any

from openai import OpenAI

from backend.observability.events import emit
from backend.retry import with_retry
from backend.services.llm_adapter.types import (
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

_logger = logging.getLogger(__name__)


def _estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Rough per-1K-token pricing. Update as models evolve."""
    # Values accurate as of 2026-04. Conservative estimate — real billing
    # is authoritative, this is for observability only.
    rates = {
        "gpt-4": (0.03, 0.06),
        "gpt-4-turbo": (0.01, 0.03),
        "gpt-4o": (0.005, 0.015),
        "gpt-4o-mini": (0.00015, 0.0006),
    }
    in_rate, out_rate = rates.get(model, (0.01, 0.03))
    return round(prompt_tokens * in_rate / 1000 + completion_tokens * out_rate / 1000, 6)


def _content_to_openai(content: list) -> str | list[dict[str, Any]]:
    """Map our ContentPart list to OpenAI's message content shape.

    If content is a single TextPart, return a string (OpenAI accepts this
    as a shorthand). Otherwise return the array-of-parts form for
    multimodal input.
    """
    if len(content) == 1 and isinstance(content[0], TextPart):
        return content[0].text

    parts: list[dict[str, Any]] = []
    for p in content:
        if isinstance(p, TextPart):
            parts.append({"type": "text", "text": p.text})
        elif isinstance(p, ImagePart):
            if p.url:
                parts.append({"type": "image_url", "image_url": {"url": p.url}})
            else:
                # base64 data URL
                data_url = f"data:{p.mime_type};base64,{p.base64}"
                parts.append({"type": "image_url", "image_url": {"url": data_url}})
        # ToolUsePart / ToolResultPart are not valid inside message.content
        # for OpenAI — they belong at the tool_calls / tool role level.
    return parts


def _message_to_openai(msg: Message) -> dict[str, Any]:
    result: dict[str, Any] = {"role": msg.role}
    if msg.role == "tool" and msg.tool_call_id:
        result["tool_call_id"] = msg.tool_call_id
    result["content"] = _content_to_openai(msg.content)
    return result


class OpenAIAdapter:
    """Adapter for OpenAI's chat completions API."""

    def __init__(self, api_key: str | None = None):
        self._client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self._provider = "openai"

    def chat(self, request: LLMRequest) -> LLMResponse:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        for msg in request.messages:
            messages.append(_message_to_openai(msg))

        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "timeout": request.timeout,
        }
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.response_format is not None:
            if request.response_format.type == "json_object":
                kwargs["response_format"] = {"type": "json_object"}
            elif request.response_format.type == "json_schema":
                kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": request.response_format.schema,
                }
        if request.tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in request.tools
            ]

        emit(
            "llm.call.start",
            provider=self._provider,
            model=request.model,
            **{k: v for k, v in request.metadata.items() if isinstance(v, (str, int, float, bool))},
        )
        t0 = time.monotonic()

        try:
            raw = with_retry(
                lambda: self._client.chat.completions.create(**kwargs),
                label=f"openai.chat.completions.create({request.model})",
            )
        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            emit(
                "llm.call.error",
                level="warning",
                provider=self._provider,
                model=request.model,
                duration_ms=duration_ms,
                error_kind=type(e).__name__,
            )
            raise

        duration_ms = int((time.monotonic() - t0) * 1000)

        # Map response
        choice = raw.choices[0]
        content_parts = []
        if choice.message.content:
            content_parts.append(TextPart(text=choice.message.content))

        tool_calls: list[ToolCall] = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append(ToolCall(
                    tool_call_id=tc.id,
                    name=tc.function.name,
                    args=_json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments,
                ))

        usage = Usage(
            prompt_tokens=raw.usage.prompt_tokens if raw.usage else 0,
            completion_tokens=raw.usage.completion_tokens if raw.usage else 0,
            cost_usd=_estimate_cost_usd(
                request.model,
                raw.usage.prompt_tokens if raw.usage else 0,
                raw.usage.completion_tokens if raw.usage else 0,
            ),
        )

        emit(
            "llm.call.complete",
            provider=self._provider,
            model=request.model,
            duration_ms=duration_ms,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cost_usd=usage.cost_usd,
            finish_reason=choice.finish_reason,
        )

        return LLMResponse(
            content_parts=content_parts,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=choice.finish_reason,
            provider=self._provider,
            model=raw.model,
        )
