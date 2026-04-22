"""Anthropic adapter for the Phase 5a LLM adapter layer.

Maps LLMRequest/Response to/from anthropic.messages.create.

Key differences from OpenAI:
- system_prompt maps to top-level system= param (NOT a message role)
- message content is always a list of typed blocks, never a plain string
- image input uses {"type": "image", "source": {"type": "base64"|"url", ...}}
- tool_use blocks in response content are extracted into tool_calls
- stop_reason "tool_use" maps to finish_reason "tool_use"
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import anthropic

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
    normalize_finish_reason,
)

_logger = logging.getLogger(__name__)


def _estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Rough per-1K-token pricing for Anthropic models."""
    rates = {
        "claude-opus-4-20250514": (0.015, 0.075),
        "claude-sonnet-4-20250514": (0.003, 0.015),
        "claude-haiku-4-5-20251001": (0.00025, 0.00125),
    }
    in_rate, out_rate = rates.get(model, (0.003, 0.015))
    return round(prompt_tokens * in_rate / 1000 + completion_tokens * out_rate / 1000, 6)


def _content_to_anthropic(content: list) -> list[dict[str, Any]]:
    """Map our ContentPart list to Anthropic's message content block list."""
    blocks: list[dict[str, Any]] = []
    for p in content:
        if isinstance(p, TextPart):
            blocks.append({"type": "text", "text": p.text})
        elif isinstance(p, ImagePart):
            if p.base64:
                blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": p.mime_type,
                        "data": p.base64,
                    },
                })
            else:
                blocks.append({
                    "type": "image",
                    "source": {
                        "type": "url",
                        "url": p.url,
                    },
                })
        elif isinstance(p, ToolUsePart):
            blocks.append({
                "type": "tool_use",
                "id": p.tool_call_id,
                "name": p.name,
                "input": p.args,
            })
        # ToolResultPart should be in a "tool" role message, handled at message level
    return blocks


def _message_to_anthropic(msg: Message) -> dict[str, Any]:
    # Anthropic uses "user" and "assistant" — "tool" role is not used;
    # tool results are "user" messages with tool_result blocks.
    if msg.role == "tool":
        # Convert ToolResultPart content into a tool_result block
        blocks: list[dict[str, Any]] = []
        for p in msg.content:
            if isinstance(p, ToolResultPart):
                result_content = p.content if isinstance(p.content, str) else str(p.content)
                blocks.append({
                    "type": "tool_result",
                    "tool_use_id": p.tool_call_id,
                    "content": result_content,
                })
        return {"role": "user", "content": blocks}

    role = "user" if msg.role == "user" else "assistant"
    return {"role": role, "content": _content_to_anthropic(msg.content)}


class AnthropicAdapter:
    """Adapter for Anthropic's Messages API."""

    def __init__(self, api_key: str | None = None):
        self._client = anthropic.Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self._provider = "anthropic"

    def chat(self, request: LLMRequest) -> LLMResponse:
        messages = [_message_to_anthropic(msg) for msg in request.messages]

        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens or 1024,
        }
        if request.system_prompt:
            kwargs["system"] = request.system_prompt
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.tools:
            kwargs["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
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
                lambda: self._client.messages.create(**kwargs),
                label=f"anthropic.messages.create({request.model})",
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

        # Map response blocks into content_parts and tool_calls
        content_parts = []
        tool_calls: list[ToolCall] = []
        for block in raw.content:
            if block.type == "text":
                content_parts.append(TextPart(text=block.text))
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    tool_call_id=block.id,
                    name=block.name,
                    args=block.input if isinstance(block.input, dict) else {},
                ))
                # Also surface as ToolUsePart in content_parts for callers
                # that inspect content_parts (e.g. multi-turn reconstruction)
                content_parts.append(ToolUsePart(
                    tool_call_id=block.id,
                    name=block.name,
                    args=block.input if isinstance(block.input, dict) else {},
                ))

        prompt_tokens = raw.usage.input_tokens if raw.usage else 0
        completion_tokens = raw.usage.output_tokens if raw.usage else 0
        usage = Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=_estimate_cost_usd(request.model, prompt_tokens, completion_tokens),
        )

        finish_reason = normalize_finish_reason(raw.stop_reason)

        emit(
            "llm.call.complete",
            provider=self._provider,
            model=request.model,
            duration_ms=duration_ms,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cost_usd=usage.cost_usd,
            finish_reason=finish_reason,
        )

        return LLMResponse(
            content_parts=content_parts,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=finish_reason,
            provider=self._provider,
            model=raw.model,
        )
