"""OpenAI adapter for the Phase 5a LLM adapter layer.

Maps LLMRequest/Response to/from openai.chat.completions.create.
"""
from __future__ import annotations

import json as _json
import logging
import os
import time
from typing import Any, Iterator

import sentry_sdk
from openai import OpenAI

from backend.observability.events import emit
from backend.retry import with_retry
from backend.services.llm_adapter.streaming import (
    FinishEvent,
    StreamEvent,
    TextDelta,
    ToolCallComplete,
    ToolCallDelta,
    UsageEvent,
)
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
    """Rough per-1K-token pricing (verify against https://openai.com/pricing
    when adding a new model). Real billing is authoritative — this is for
    observability only."""
    rates = {
        "gpt-4": (0.03, 0.06),
        "gpt-4-turbo": (0.01, 0.03),
        # gpt-4o is $2.50 / $10 per million tokens (not $5 / $15).
        "gpt-4o": (0.0025, 0.010),
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
            sentry_sdk.add_breadcrumb(
                category="llm.call",
                level="warning",
                message=f"openai.chat.completions.create failed for {request.model}",
                data={"provider": self._provider, "model": request.model, "error_kind": type(e).__name__, "duration_ms": duration_ms},
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

        finish_reason = normalize_finish_reason(choice.finish_reason)

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

    def stream_chat(self, request: LLMRequest) -> Iterator[StreamEvent]:
        """Yield StreamEvent instances from a streaming OpenAI completion.

        The initial stream-open call is protected by with_retry(); the
        iteration loop is not (can't retry mid-stream).
        """
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        for msg in request.messages:
            messages.append(_message_to_openai(msg))

        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "timeout": request.timeout,
        }
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
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
            streaming=True,
            **{k: v for k, v in request.metadata.items() if isinstance(v, (str, int, float, bool))},
        )
        t0 = time.monotonic()

        try:
            stream = with_retry(
                lambda: self._client.chat.completions.create(**kwargs),
                label=f"openai.chat.completions.create(stream, {request.model})",
            )
        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            emit(
                "llm.call.error",
                level="warning",
                provider=self._provider,
                model=request.model,
                duration_ms=duration_ms,
                streaming=True,
                error_kind=type(e).__name__,
            )
            sentry_sdk.add_breadcrumb(
                category="llm.call",
                level="warning",
                message=f"openai.chat.completions.create(stream) failed for {request.model}",
                data={"provider": self._provider, "model": request.model, "error_kind": type(e).__name__, "duration_ms": duration_ms},
            )
            raise

        # pending_tool_calls: index -> {id, name, arguments_accumulated}
        pending_tool_calls: dict[int, dict[str, str]] = {}
        usage_event: UsageEvent | None = None
        finish_reason_raw: str | None = None

        try:
            for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None

                # Usage-only chunk (arrives when stream_options include_usage=True)
                if chunk.usage and (not choice or not choice.delta.content):
                    usage_event = UsageEvent(
                        usage=Usage(
                            prompt_tokens=chunk.usage.prompt_tokens or 0,
                            completion_tokens=chunk.usage.completion_tokens or 0,
                            cost_usd=_estimate_cost_usd(
                                request.model,
                                chunk.usage.prompt_tokens or 0,
                                chunk.usage.completion_tokens or 0,
                            ),
                        )
                    )

                if not choice:
                    continue

                delta = choice.delta

                # Text content
                if delta and delta.content:
                    yield TextDelta(text=delta.content)

                # Tool call deltas
                if delta and delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in pending_tool_calls:
                            pending_tool_calls[idx] = {"id": "", "name": "", "arguments": ""}

                        is_first = False
                        if tc_delta.id:
                            pending_tool_calls[idx]["id"] = tc_delta.id
                            is_first = True
                        if tc_delta.function and tc_delta.function.name:
                            pending_tool_calls[idx]["name"] = tc_delta.function.name
                            is_first = True
                        args_fragment = ""
                        if tc_delta.function and tc_delta.function.arguments:
                            args_fragment = tc_delta.function.arguments
                            pending_tool_calls[idx]["arguments"] += args_fragment

                        yield ToolCallDelta(
                            tool_call_id=pending_tool_calls[idx]["id"],
                            name=pending_tool_calls[idx]["name"] if is_first else None,
                            args_delta=args_fragment,
                        )

                if choice.finish_reason:
                    finish_reason_raw = choice.finish_reason

        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            emit(
                "llm.call.error",
                level="warning",
                provider=self._provider,
                model=request.model,
                duration_ms=duration_ms,
                streaming=True,
                error_kind=type(e).__name__,
            )
            sentry_sdk.add_breadcrumb(
                category="llm.call",
                level="warning",
                message=f"openai stream iteration failed for {request.model}",
                data={"provider": self._provider, "model": request.model, "error_kind": type(e).__name__, "duration_ms": duration_ms},
            )
            raise

        # Emit ToolCallComplete for every accumulated tool call
        for idx in sorted(pending_tool_calls.keys()):
            tc = pending_tool_calls[idx]
            if tc["name"]:
                try:
                    args = _json.loads(tc["arguments"]) if tc["arguments"] else {}
                except _json.JSONDecodeError:
                    args = {}
                yield ToolCallComplete(
                    tool_call=ToolCall(
                        tool_call_id=tc["id"] or f"call_{idx}",
                        name=tc["name"],
                        args=args,
                    )
                )

        if usage_event:
            yield usage_event

        finish_reason = normalize_finish_reason(finish_reason_raw)
        yield FinishEvent(finish_reason=finish_reason)

        duration_ms = int((time.monotonic() - t0) * 1000)
        prompt_tokens = usage_event.usage.prompt_tokens if usage_event else 0
        completion_tokens = usage_event.usage.completion_tokens if usage_event else 0
        emit(
            "llm.call.complete",
            provider=self._provider,
            model=request.model,
            duration_ms=duration_ms,
            streaming=True,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=usage_event.usage.cost_usd if usage_event else 0.0,
            finish_reason=finish_reason,
        )
