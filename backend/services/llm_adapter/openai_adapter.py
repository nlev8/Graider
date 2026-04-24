"""OpenAI adapter for the Phase 5a LLM adapter layer.

Maps LLMRequest/Response to/from openai.chat.completions.create.
"""
from __future__ import annotations

import json as _json
import logging
import os
import time
from typing import Any, Iterator

import pybreaker
import sentry_sdk
from openai import OpenAI

from backend.observability.events import emit
from backend.services.llm_adapter.breakers import get_breaker
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
    LLMToolArgsOverflow,
    Message,
    TextPart,
    ToolCall,
    ToolResultPart,
    ToolUsePart,
    Usage,
    normalize_finish_reason,
)

# Phase 5b PR 5 — memory cap for streaming tool-call argument accumulation.
# Prevents a runaway model producing unbounded args JSON from consuming
# gigabytes of worker memory. 5 MB accommodates known-large Graider tool
# payloads (generate_document.content, save_assignment_config.document_text,
# generate_worksheet.questions, create_automation.steps) with ~10x headroom.
_MAX_TOOL_ARGS_BYTES = 5 * 1024 * 1024

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
    """Map our ContentPart list to OpenAI's message content shape (for user
    messages — assistant and tool roles have their own handling in
    _message_to_openai because OpenAI splits tool calls out of `content`).

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
            image_url_obj: dict[str, Any] = {
                "url": p.url if p.url else f"data:{p.mime_type};base64,{p.base64}"
            }
            if p.detail:
                image_url_obj["detail"] = p.detail
            parts.append({"type": "image_url", "image_url": image_url_obj})
        # ToolUsePart / ToolResultPart handled at message level by _message_to_openai
    return parts


def _message_to_openai(msg: Message) -> dict[str, Any]:
    # Tool-role messages (tool results) — OpenAI wire format:
    # {"role": "tool", "tool_call_id": "...", "content": "<result as string>"}
    # Each ToolResultPart becomes its own tool-role message; if a single
    # Message.content has multiple ToolResultPart entries, caller should
    # expand via _expand_messages_for_openai (below).
    if msg.role == "tool":
        # Pick the first ToolResultPart — callers should build one tool-role
        # Message per result; _expand_messages_for_openai enforces this.
        for p in msg.content:
            if isinstance(p, ToolResultPart):
                content = p.content if isinstance(p.content, str) else _json.dumps(p.content)
                return {
                    "role": "tool",
                    "tool_call_id": p.tool_call_id,
                    "content": content,
                }
        # Fallback: tool message with no ToolResultPart — stringify whatever's there.
        return {"role": "tool", "tool_call_id": msg.tool_call_id or "", "content": ""}

    # Assistant messages may carry text + tool_use blocks — split them.
    if msg.role == "assistant":
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for p in msg.content:
            if isinstance(p, TextPart):
                text_parts.append(p.text)
            elif isinstance(p, ToolUsePart):
                tool_calls.append({
                    "id": p.tool_call_id,
                    "type": "function",
                    "function": {
                        "name": p.name,
                        "arguments": _json.dumps(p.args),
                    },
                })
            # ImagePart on assistant isn't valid OpenAI shape — skip.
        result: dict[str, Any] = {"role": "assistant"}
        # OpenAI requires content OR tool_calls; content can be null when tool_calls present.
        result["content"] = " ".join(text_parts) if text_parts else None
        if tool_calls:
            result["tool_calls"] = tool_calls
        return result

    # User role — standard content conversion.
    result = {"role": msg.role}
    result["content"] = _content_to_openai(msg.content)
    return result


def _expand_messages_for_openai(messages: list[Message]) -> list[dict[str, Any]]:
    """Expand typed Messages into OpenAI wire format, splitting any
    tool-role Message with multiple ToolResultPart entries into separate
    tool-role messages (OpenAI requires one tool message per tool_call_id).
    """
    out: list[dict[str, Any]] = []
    for msg in messages:
        if msg.role == "tool":
            result_parts = [p for p in msg.content if isinstance(p, ToolResultPart)]
            if len(result_parts) > 1:
                for p in result_parts:
                    content = p.content if isinstance(p.content, str) else _json.dumps(p.content)
                    out.append({
                        "role": "tool",
                        "tool_call_id": p.tool_call_id,
                        "content": content,
                    })
                continue
        out.append(_message_to_openai(msg))
    return out


class OpenAIAdapter:
    """Adapter for OpenAI's chat completions API."""

    def __init__(self, api_key: str | None = None):
        self._client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self._provider = "openai"

    def chat(self, request: LLMRequest) -> LLMResponse:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(_expand_messages_for_openai(request.messages))

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

        breaker = get_breaker(self._provider, request.model)

        def _raw_call():
            return self._client.chat.completions.create(**kwargs)

        def _breakered():
            return breaker.call(_raw_call)

        try:
            raw = with_retry(
                _breakered,
                label=f"openai.chat.completions.create({request.model})",
                non_retryable=(pybreaker.CircuitBreakerError,),
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
        messages.extend(_expand_messages_for_openai(request.messages))

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

        stream_breaker = get_breaker(self._provider, request.model)

        def _raw_stream_call():
            return self._client.chat.completions.create(**kwargs)

        def _breakered_stream():
            return stream_breaker.call(_raw_stream_call)

        try:
            stream = with_retry(
                _breakered_stream,
                label=f"openai.chat.completions.create(stream, {request.model})",
                non_retryable=(pybreaker.CircuitBreakerError,),
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
                                projected = len(pending_tool_calls[idx]["arguments"]) + len(args_fragment)
                                if projected > _MAX_TOOL_ARGS_BYTES:
                                    emit(
                                        "llm.tool_call.args_overflow",
                                        provider=self._provider,
                                        model=request.model,
                                        tool_name=pending_tool_calls[idx]["name"] or "unknown",
                                        bytes_accumulated=len(pending_tool_calls[idx]["arguments"]),
                                    )
                                    raise LLMToolArgsOverflow(
                                        f"tool_call args exceeded {_MAX_TOOL_ARGS_BYTES} bytes "
                                        f"for tool {pending_tool_calls[idx]['name']!r} on {self._provider}"
                                    )
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
        finally:
            # Phase 5b PR 4 — release upstream HTTP connection on client
            # disconnect, error, or normal completion.
            try:
                stream.close()
            except Exception:
                _logger.debug("openai stream.close() raised on cleanup", exc_info=True)

        # Emit ToolCallComplete for every accumulated tool call
        for idx in sorted(pending_tool_calls.keys()):
            tc = pending_tool_calls[idx]
            if tc["name"]:
                try:
                    args = _json.loads(tc["arguments"]) if tc["arguments"] else {}
                except _json.JSONDecodeError:
                    # Malformed tool args (usually from truncated output hitting
                    # max_tokens). Log + breadcrumb so operators can detect — the
                    # tool will execute with empty args rather than crash, but
                    # that's a quality regression worth surfacing.
                    _logger.warning(
                        "Dropping malformed OpenAI tool args for %s (idx=%s): %r",
                        tc["name"], idx, tc["arguments"],
                    )
                    sentry_sdk.add_breadcrumb(
                        category="llm.tool_call",
                        level="warning",
                        message=f"openai tool args JSONDecodeError for {tc['name']}",
                        data={"provider": "openai", "tool_name": tc["name"], "args_len": len(tc["arguments"] or "")},
                    )
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
